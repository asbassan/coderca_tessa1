"""
Minimal feed-analysis agents for the first Tessa1 end-to-end flow.

These agents stay deterministic so the architecture remains inspectable:
- ProfileAgent extracts normalized profile signals
- RetrievalRankingAgent computes explicit score breakdowns
- SynthesisAgent turns ranked facts into concise explanations
"""

from __future__ import annotations

import re
import time
from typing import Optional

from .copilot_client import CopilotClient
from .models import FeedPhaseResult, FeedPost, ScoreBreakdown, ScoringConfig, UserProfile
from .runlog import RunLog


def _normalize(values: list[str]) -> list[str]:
    return [value.strip().lower() for value in values if value and value.strip()]


def _text_blob(post: FeedPost) -> str:
    return " ".join(
        part for part in [post.title, post.headline, post.body, post.source, *post.topics] if part
    ).lower()


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _match_terms(terms: list[str], post: FeedPost) -> list[str]:
    text = _text_blob(post)
    text_tokens = _tokenize(text)
    topic_tags = set(post.normalized_topics)
    matched: list[str] = []

    for term in _normalize(terms):
        if term in topic_tags or term in text or term in text_tokens:
            matched.append(term)

    return sorted(set(matched))


class ProfileAgent:
    """Extract structured profile facts for the selected viewer."""

    agent_name = "ProfileAgent"

    def analyze(self, profile: UserProfile, runlog: Optional[RunLog] = None) -> FeedPhaseResult:
        start = time.time()
        facts = {
            "user_id": profile.user_id,
            "skills": _normalize(profile.skills),
            "interests": _normalize(profile.interests),
            "recent_engagement_topics": _normalize(profile.recent_engagement_topics),
            "preferred_sources": _normalize(profile.preferred_sources),
            "topic_signals": profile.topic_signals,
        }

        if runlog:
            runlog.agent_start(self.agent_name)
            runlog.info(self.agent_name, f"Prepared {len(profile.topic_signals)} topic signals")
            runlog.agent_end(
                self.agent_name,
                findings_count=0,
                confidence=1.0,
                duration_ms=(time.time() - start) * 1000,
            )

        return FeedPhaseResult(
            agent_name=self.agent_name,
            facts=facts,
            analysis=(
                f"Prepared normalized profile signals for {profile.name} across skills, interests, "
                f"recent engagement, and preferred sources."
            ),
            execution_time_ms=(time.time() - start) * 1000,
        )


class RetrievalRankingAgent:
    """Compute deterministic ranking scores for each user-post pair."""

    agent_name = "RetrievalRankingAgent"

    def rank(
        self,
        profile: UserProfile,
        posts: list[FeedPost],
        scoring_config: ScoringConfig,
        runlog: Optional[RunLog] = None,
    ) -> tuple[FeedPhaseResult, list[ScoreBreakdown]]:
        start = time.time()

        ranked_posts = [self._score_post(profile, post, scoring_config) for post in posts]
        ranked_posts.sort(
            key=lambda score: (
                score.total_score,
                score.topic_overlap_score,
                score.recency_bonus,
                score.popularity_bonus,
            ),
            reverse=True,
        )

        facts = {
            "scored_posts": len(ranked_posts),
            "top_post_ids": [score.post_id for score in ranked_posts[: scoring_config.top_k]],
            "top_scores": [round(score.total_score, 2) for score in ranked_posts[: scoring_config.top_k]],
        }

        if runlog:
            runlog.agent_start(self.agent_name)
            runlog.info(self.agent_name, f"Scored {len(ranked_posts)} posts for {profile.user_id}")
            runlog.agent_end(
                self.agent_name,
                findings_count=len(ranked_posts[: scoring_config.top_k]),
                confidence=1.0,
                duration_ms=(time.time() - start) * 1000,
            )

        return (
            FeedPhaseResult(
                agent_name=self.agent_name,
                facts=facts,
                analysis=(
                    f"Computed deterministic ranking scores for {len(ranked_posts)} candidate posts "
                    f"using topic, skill, recency, popularity, and source signals."
                ),
                execution_time_ms=(time.time() - start) * 1000,
            ),
            ranked_posts,
        )

    def _score_post(
        self,
        profile: UserProfile,
        post: FeedPost,
        scoring_config: ScoringConfig,
    ) -> ScoreBreakdown:
        matched_topics = _match_terms(profile.interests, post)
        matched_skills = _match_terms(profile.skills, post)
        matched_recent = _match_terms(profile.recent_engagement_topics, post)
        preferred_source_match = post.source.lower() in _normalize(profile.preferred_sources)

        topic_overlap_score = len(matched_topics) * scoring_config.weight_for("topic_overlap_weight")
        skill_overlap_score = len(matched_skills) * scoring_config.weight_for("skill_overlap_weight")
        recent_engagement_score = len(matched_recent) * scoring_config.weight_for(
            "recent_engagement_weight"
        )
        affinity_bonus = (
            scoring_config.weight_for("preferred_source_weight") if preferred_source_match else 0.0
        )
        popularity_bonus = scoring_config.bucket_bonus_for("popularity", post.popularity_bucket)
        recency_bonus = scoring_config.bucket_bonus_for("recency", post.recency_bucket)

        explanation_facts: list[str] = []
        if matched_topics:
            explanation_facts.append(f"topic match: {', '.join(matched_topics)}")
        if matched_recent:
            explanation_facts.append(f"recent engagement: {', '.join(matched_recent)}")
        if matched_skills:
            explanation_facts.append(f"skill match: {', '.join(matched_skills)}")
        if preferred_source_match:
            explanation_facts.append(f"preferred source: {post.source}")
        if recency_bonus > 0:
            explanation_facts.append(f"recency bucket: {post.recency_bucket}")
        if popularity_bonus > 0:
            explanation_facts.append(f"popularity bucket: {post.popularity_bucket}")

        total_score = (
            topic_overlap_score
            + skill_overlap_score
            + recent_engagement_score
            + affinity_bonus
            + popularity_bonus
            + recency_bonus
        )

        return ScoreBreakdown(
            post_id=post.post_id,
            total_score=total_score,
            topic_overlap_score=topic_overlap_score + recent_engagement_score,
            skill_overlap_score=skill_overlap_score,
            popularity_bonus=popularity_bonus,
            recency_bonus=recency_bonus,
            affinity_bonus=affinity_bonus,
            explanation_facts=explanation_facts,
            matched_topics=matched_topics + matched_recent,
            matched_skills=matched_skills,
            metadata={
                "preferred_source_match": preferred_source_match,
                "post_source": post.source,
            },
        )


class SynthesisAgent:
    """Create concise ranked-feed explanations from deterministic score facts."""

    agent_name = "SynthesisAgent"

    def __init__(self, copilot_client: Optional[CopilotClient] = None):
        self.client = copilot_client

    def synthesize(
        self,
        profile: UserProfile,
        top_posts: list[FeedPost],
        ranked_posts: list[ScoreBreakdown],
        scoring_config: ScoringConfig,
        runlog: Optional[RunLog] = None,
    ) -> tuple[FeedPhaseResult, list[str]]:
        start = time.time()
        score_lookup = {score.post_id: score for score in ranked_posts}
        explanations = [
            self._explain_post(profile, post, score_lookup[post.post_id], scoring_config)
            for post in top_posts
            if post.post_id in score_lookup
        ]

        if runlog:
            runlog.agent_start(self.agent_name)
            runlog.info(self.agent_name, f"Generated {len(explanations)} feed explanations")
            runlog.agent_end(
                self.agent_name,
                findings_count=len(explanations),
                confidence=1.0,
                duration_ms=(time.time() - start) * 1000,
            )

        return (
            FeedPhaseResult(
                agent_name=self.agent_name,
                facts={
                    "explanation_count": len(explanations),
                    "top_post_ids": [post.post_id for post in top_posts],
                },
                analysis=(
                    f"Generated concise explanations for the top {len(explanations)} ranked posts "
                    f"for {profile.name}."
                ),
                execution_time_ms=(time.time() - start) * 1000,
            ),
            explanations,
        )

    def _explain_post(
        self,
        profile: UserProfile,
        post: FeedPost,
        score: ScoreBreakdown,
        scoring_config: ScoringConfig,
    ) -> str:
        why = "; ".join(score.explanation_facts) if score.explanation_facts else "baseline ranking signals"
        return (
            f"{post.display_title} ranked for {profile.name} with score {score.total_score:.2f} because of "
            f"{why}."
        )
