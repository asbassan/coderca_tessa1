"""
Minimal feed-analysis agents for the first Tessa1 end-to-end flow.

These agents stay deterministic so the architecture remains inspectable:
- ProfileAgent interprets the profile into ranking-ready intent
- RetrievalRankingAgent computes explicit score breakdowns
- SynthesisAgent turns ranked facts into concise explanations
"""

from __future__ import annotations

import re
import time
from typing import Optional

from .copilot_client import CopilotClient
from .models import (
    FeedPhaseResult,
    FeedPost,
    ProfileIntent,
    ScoreBreakdown,
    ScoringConfig,
    UserProfile,
)
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
        if term in topic_tags:
            matched.append(term)
            continue

        if " " in term:
            if term in text:
                matched.append(term)
            continue

        if term in text_tokens:
            matched.append(term)

    return sorted(set(matched))


PROFILE_EXPANSION_MAP: dict[str, list[str]] = {
    "machine learning": ["ai", "ranking", "recommenders"],
    "ranking": ["recommenders", "feed systems", "personalization"],
    "technology": ["microsoft", "ai", "platforms"],
    "microsoft": ["technology", "platforms", "cloud", "ai"],
    "ai": ["machine learning", "ranking", "technology"],
    "product management": ["platforms", "growth", "consumer tech"],
    "analytics": ["measurement", "experimentation"],
    "economics": ["economy", "markets", "government"],
    "policy": ["government", "regulation", "economy"],
    "research": ["analysis", "deep dives"],
    "palestine": ["middle east", "security", "diplomacy"],
    "security": ["diplomacy", "geopolitics"],
    "apple": ["mobile", "consumer tech", "platforms"],
}


def _extract_headline_terms(headline: str) -> list[str]:
    headline_lower = headline.lower()
    derived_terms: list[str] = []

    if "engineer" in headline_lower or "ml" in headline_lower:
        derived_terms.extend(["technology", "ai"])
    if "ranking" in headline_lower:
        derived_terms.extend(["ranking", "personalization"])
    if "policy" in headline_lower or "econom" in headline_lower:
        derived_terms.extend(["economy", "government"])
    if "research" in headline_lower:
        derived_terms.extend(["analysis"])
    if "product" in headline_lower:
        derived_terms.extend(["platforms", "consumer tech"])

    return sorted(set(derived_terms))


def _infer_profile_modes(profile: UserProfile) -> list[str]:
    signals = " ".join(profile.topic_signals + _extract_headline_terms(profile.headline))
    modes: list[str] = []

    if any(term in signals for term in ["python", "machine learning", "ranking", "ai"]):
        modes.append("technical-builder")
    if any(term in signals for term in ["economy", "markets", "policy", "government"]):
        modes.append("business-analyst")
    if any(term in signals for term in ["palestine", "security", "diplomacy", "middle east"]):
        modes.append("geopolitics-researcher")
    if any(term in signals for term in ["product", "platforms", "consumer tech", "mobile", "apple"]):
        modes.append("product-operator")

    return modes or ["generalist-reader"]


class ProfileAgent:
    """Interpret the selected viewer into ranking-ready intent."""

    agent_name = "ProfileAgent"

    def analyze(
        self,
        profile: UserProfile,
        runlog: Optional[RunLog] = None,
    ) -> tuple[FeedPhaseResult, ProfileIntent]:
        start = time.time()
        skill_signals = _normalize(profile.skills)
        interests = _normalize(profile.interests)
        recent_topics = _normalize(profile.recent_engagement_topics)
        preferred_sources = _normalize(profile.preferred_sources)
        headline_terms = _extract_headline_terms(profile.headline)

        weighted_topic_intents: dict[str, float] = {}
        expanded_topics: list[str] = []

        self._boost_terms(weighted_topic_intents, skill_signals, 2.0)
        self._boost_terms(weighted_topic_intents, interests, 3.0)
        self._boost_terms(weighted_topic_intents, recent_topics, 4.0)
        self._boost_terms(weighted_topic_intents, headline_terms, 1.5)

        seed_terms = sorted(set(skill_signals + interests + recent_topics + headline_terms))
        for term in seed_terms:
            expansions = PROFILE_EXPANSION_MAP.get(term, [])
            expanded_topics.extend(expansions)
            self._boost_terms(weighted_topic_intents, expansions, 1.0)

        ordered_topics = [
            topic
            for topic, _ in sorted(
                weighted_topic_intents.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        primary_topics = ordered_topics[:3]
        secondary_topics = ordered_topics[3:6]
        normalized_expanded_topics = [
            topic
            for topic in sorted(set(expanded_topics))
            if topic not in primary_topics and topic not in secondary_topics
        ]

        profile_intent = ProfileIntent(
            user_id=profile.user_id,
            primary_topics=primary_topics,
            secondary_topics=secondary_topics,
            expanded_topics=normalized_expanded_topics,
            skill_signals=skill_signals,
            recent_topics=recent_topics,
            preferred_sources=preferred_sources,
            profile_modes=_infer_profile_modes(profile),
            weighted_topic_intents=weighted_topic_intents,
            summary=(
                f"Primary focus: {', '.join(primary_topics) if primary_topics else 'general interest'}; "
                f"modes: {', '.join(_infer_profile_modes(profile))}."
            ),
        )
        facts = {
            "user_id": profile.user_id,
            "primary_topics": profile_intent.primary_topics,
            "secondary_topics": profile_intent.secondary_topics,
            "expanded_topics": profile_intent.expanded_topics,
            "profile_modes": profile_intent.profile_modes,
            "weighted_topic_intents": profile_intent.weighted_topic_intents,
            "preferred_sources": profile_intent.preferred_sources,
        }

        if runlog:
            runlog.agent_start(self.agent_name)
            runlog.info(
                self.agent_name,
                f"Interpreted {profile.name} into {len(profile_intent.weighted_topic_intents)} ranking signals",
            )
            runlog.agent_end(
                self.agent_name,
                findings_count=0,
                confidence=1.0,
                duration_ms=(time.time() - start) * 1000,
            )

        return (
            FeedPhaseResult(
                agent_name=self.agent_name,
                facts=facts,
                analysis=(
                    f"Interpreted {profile.name}'s raw profile into weighted interests, expanded topics, "
                    f"and profile modes for downstream ranking."
                ),
                execution_time_ms=(time.time() - start) * 1000,
            ),
            profile_intent,
        )

    def _boost_terms(self, weighted_topic_intents: dict[str, float], terms: list[str], weight: float) -> None:
        for term in terms:
            normalized = term.strip().lower()
            if not normalized:
                continue
            weighted_topic_intents[normalized] = weighted_topic_intents.get(normalized, 0.0) + weight


class RetrievalRankingAgent:
    """Plan, shortlist, and rerank candidates for each user-post pair."""

    agent_name = "RetrievalRankingAgent"

    def rank(
        self,
        profile: UserProfile,
        profile_intent: ProfileIntent,
        posts: list[FeedPost],
        scoring_config: ScoringConfig,
        runlog: Optional[RunLog] = None,
    ) -> tuple[FeedPhaseResult, list[ScoreBreakdown]]:
        start = time.time()

        scored_posts = [
            self._score_post(profile, profile_intent, post, scoring_config) for post in posts
        ]
        ranking_plan = self._build_ranking_plan(profile_intent, scored_posts, scoring_config)
        shortlisted_posts = self._shortlist_candidates(scored_posts, ranking_plan, scoring_config)
        ranked_posts = self._diversity_rerank(shortlisted_posts, scoring_config)
        ranked_posts.extend(
            score
            for score in sorted(
                scored_posts,
                key=lambda item: (
                    item.total_score,
                    item.topic_overlap_score,
                    item.recency_bonus,
                    item.popularity_bonus,
                ),
                reverse=True,
            )
            if score.post_id not in {ranked.post_id for ranked in ranked_posts}
        )

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
            "scored_posts": len(scored_posts),
            "shortlisted_posts": len(shortlisted_posts),
            "ranking_plan": ranking_plan,
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
                    f"Planned a candidate pool, shortlisted posts, and reranked {len(shortlisted_posts)} candidates "
                    f"using interpreted profile intent plus topic, skill, recency, popularity, source, and diversity signals."
                ),
                execution_time_ms=(time.time() - start) * 1000,
            ),
            ranked_posts,
        )

    def _build_ranking_plan(
        self,
        profile_intent: ProfileIntent,
        scored_posts: list[ScoreBreakdown],
        scoring_config: ScoringConfig,
    ) -> dict[str, object]:
        active_topics = profile_intent.primary_topics[:]
        if len(active_topics) < 3:
            active_topics.extend(
                topic for topic in profile_intent.secondary_topics if topic not in active_topics
            )
        shortlist_size = max(
            int(scoring_config.top_k * scoring_config.policy_for("candidate_pool_multiplier", 4.0)),
            int(scoring_config.policy_for("min_candidate_pool", 12.0)),
        )

        exploration_candidates = sum(
            1
            for score in scored_posts
            if score.popularity_bonus > 0 or score.recency_bonus > 0
        )

        return {
            "active_topics": active_topics[:5],
            "profile_modes": profile_intent.profile_modes,
            "preferred_sources": profile_intent.preferred_sources,
            "shortlist_size": min(shortlist_size, len(scored_posts)),
            "exploration_candidates": exploration_candidates,
        }

    def _shortlist_candidates(
        self,
        scored_posts: list[ScoreBreakdown],
        ranking_plan: dict[str, object],
        scoring_config: ScoringConfig,
    ) -> list[ScoreBreakdown]:
        active_topics = set(ranking_plan.get("active_topics", []))
        preferred_sources = set(ranking_plan.get("preferred_sources", []))
        shortlist_size = int(ranking_plan.get("shortlist_size", len(scored_posts)))
        focus_topic_bonus = scoring_config.policy_for("focus_topic_bonus", 1.5)
        preferred_source_bonus = scoring_config.policy_for("preferred_source_shortlist_bonus", 0.75)
        exploration_bonus = scoring_config.policy_for("exploration_bonus", 0.5)

        def shortlist_score(score: ScoreBreakdown) -> tuple[float, float, float, float]:
            metadata = score.metadata
            matched_topics = set(score.matched_topics)
            shortlist_bonus = 0.0

            if active_topics & matched_topics:
                shortlist_bonus += focus_topic_bonus
            if metadata.get("preferred_source_match"):
                shortlist_bonus += preferred_source_bonus
            if score.popularity_bonus > 0 or score.recency_bonus > 0:
                shortlist_bonus += exploration_bonus

            metadata["shortlist_bonus"] = shortlist_bonus
            metadata["shortlisted"] = shortlist_bonus > 0 or score.total_score > 0

            return (
                score.total_score + shortlist_bonus,
                score.topic_overlap_score,
                score.recency_bonus,
                score.popularity_bonus,
            )

        shortlisted = sorted(scored_posts, key=shortlist_score, reverse=True)[:shortlist_size]
        for score in shortlisted:
            score.explanation_facts.append("candidate plan: shortlisted for reranking")
        return shortlisted

    def _diversity_rerank(
        self,
        shortlisted_posts: list[ScoreBreakdown],
        scoring_config: ScoringConfig,
    ) -> list[ScoreBreakdown]:
        remaining = shortlisted_posts[:]
        ordered: list[ScoreBreakdown] = []
        seen_sources: dict[str, int] = {}
        seen_topics: dict[str, int] = {}
        source_repeat_penalty = scoring_config.policy_for("source_repeat_penalty", 0.75)
        topic_repeat_penalty = scoring_config.policy_for("topic_repeat_penalty", 0.5)

        while remaining:
            best_score: Optional[ScoreBreakdown] = None
            best_adjusted_total = float("-inf")

            for score in remaining:
                source = str(score.metadata.get("post_source", "")).lower()
                repeated_topics = sum(seen_topics.get(topic, 0) for topic in set(score.matched_topics))
                adjusted_total = (
                    score.total_score
                    - seen_sources.get(source, 0) * source_repeat_penalty
                    - repeated_topics * topic_repeat_penalty
                )

                if adjusted_total > best_adjusted_total:
                    best_adjusted_total = adjusted_total
                    best_score = score

            if best_score is None:
                break

            source = str(best_score.metadata.get("post_source", "")).lower()
            repeated_source_count = seen_sources.get(source, 0)
            repeated_topic_count = sum(
                seen_topics.get(topic, 0) for topic in set(best_score.matched_topics)
            )
            diversity_penalty = (
                repeated_source_count * source_repeat_penalty
                + repeated_topic_count * topic_repeat_penalty
            )
            best_score.metadata["diversity_penalty"] = diversity_penalty
            best_score.metadata["adjusted_total_score"] = best_adjusted_total
            if diversity_penalty > 0:
                best_score.explanation_facts.append(
                    f"diversity rerank applied: -{diversity_penalty:.2f}"
                )
            else:
                best_score.explanation_facts.append("diversity rerank: preserved a fresh source/topic mix")

            ordered.append(best_score)
            remaining.remove(best_score)
            seen_sources[source] = seen_sources.get(source, 0) + 1
            for topic in set(best_score.matched_topics):
                seen_topics[topic] = seen_topics.get(topic, 0) + 1

        return ordered

    def _score_post(
        self,
        profile: UserProfile,
        profile_intent: ProfileIntent,
        post: FeedPost,
        scoring_config: ScoringConfig,
    ) -> ScoreBreakdown:
        matched_primary = _match_terms(profile_intent.primary_topics, post)
        matched_secondary = _match_terms(profile_intent.secondary_topics, post)
        matched_expanded = _match_terms(profile_intent.expanded_topics, post)
        matched_skills = _match_terms(profile_intent.skill_signals, post)
        matched_recent = _match_terms(profile_intent.recent_topics, post)
        preferred_source_match = post.source.lower() in profile_intent.preferred_sources

        topic_overlap_score = (
            len(matched_primary) * scoring_config.weight_for("topic_overlap_weight")
            + len(matched_secondary) * scoring_config.weight_for("topic_overlap_weight") * 0.5
            + len(matched_expanded) * scoring_config.weight_for("topic_overlap_weight") * 0.25
        )
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
        if matched_primary:
            explanation_facts.append(f"primary intent: {', '.join(matched_primary)}")
        if matched_secondary:
            explanation_facts.append(f"secondary intent: {', '.join(matched_secondary)}")
        if matched_expanded:
            explanation_facts.append(f"expanded intent: {', '.join(matched_expanded)}")
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
            matched_topics=matched_primary + matched_secondary + matched_expanded + matched_recent,
            matched_skills=matched_skills,
            metadata={
                "preferred_source_match": preferred_source_match,
                "post_source": post.source,
                "profile_modes": profile_intent.profile_modes,
                "diversity_penalty": 0.0,
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
