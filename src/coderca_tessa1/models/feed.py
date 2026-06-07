"""
Feed-oriented data models for Tessa1.

These models define the domain contract for the feed retrieval harness:
- UserProfile: the target user whose feed is being ranked
- FeedPost: a normalized candidate post/article
- ScoreBreakdown: deterministic score components for a user-post pair
- FeedPhaseResult: output from a feed-specific agent phase
- FeedContext: state carried through the feed pipeline
- FeedReport: final ranked feed artifact
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _normalize_tags(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        candidate = value.strip().lower()
        if not candidate or candidate in seen:
            continue

        seen.add(candidate)
        normalized.append(candidate)

    return normalized


@dataclass
class UserProfile:
    """Normalized user profile used for deterministic ranking."""

    user_id: str
    name: str
    headline: str
    skills: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    recent_engagement_topics: list[str] = field(default_factory=list)
    preferred_sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def topic_signals(self) -> list[str]:
        """Return all profile-level topical signals in normalized form."""
        return _normalize_tags(
            [
                *self.skills,
                *self.interests,
                *self.recent_engagement_topics,
            ]
        )


@dataclass
class ProfileIntent:
    """Interpreted profile state used by ranking and explanations."""

    user_id: str
    primary_topics: list[str] = field(default_factory=list)
    secondary_topics: list[str] = field(default_factory=list)
    expanded_topics: list[str] = field(default_factory=list)
    skill_signals: list[str] = field(default_factory=list)
    recent_topics: list[str] = field(default_factory=list)
    preferred_sources: list[str] = field(default_factory=list)
    profile_modes: list[str] = field(default_factory=list)
    weighted_topic_intents: dict[str, float] = field(default_factory=dict)
    summary: str = ""


@dataclass
class FeedPost:
    """Normalized candidate post used across the Tessa feed pipeline."""

    post_id: str
    author: str
    title: str
    body: str
    topics: list[str] = field(default_factory=list)
    popularity_bucket: str = "low"
    recency_bucket: str = "unknown"
    source: str = ""
    published_at: datetime | None = None
    headline: str = ""
    linkedin_popularity: float = 0.0
    facebook_popularity: float = 0.0
    googleplus_popularity: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_title(self) -> str:
        """Return the best available human-readable title for the post."""
        return self.title or self.headline or self.post_id

    @property
    def normalized_topics(self) -> list[str]:
        """Return normalized post topics for matching and scoring."""
        return _normalize_tags(self.topics)


@dataclass
class ScoreBreakdown:
    """Deterministic score components for a ranked feed candidate."""

    post_id: str
    total_score: float
    topic_overlap_score: float = 0.0
    skill_overlap_score: float = 0.0
    popularity_bonus: float = 0.0
    recency_bonus: float = 0.0
    affinity_bonus: float = 0.0
    explanation_facts: list[str] = field(default_factory=list)
    matched_topics: list[str] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoringConfig:
    """Deterministic ranking policy exposed as a demo inspection surface."""

    top_k: int = 5
    weights: dict[str, float] = field(default_factory=dict)
    bucket_bonuses: dict[str, dict[str, float]] = field(default_factory=dict)
    ranking_policy: dict[str, float] = field(default_factory=dict)
    feature_definitions: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def weight_for(self, key: str, default: float = 0.0) -> float:
        return float(self.weights.get(key, default))

    def bucket_bonus_for(self, category: str, bucket: str, default: float = 0.0) -> float:
        return float(self.bucket_bonuses.get(category, {}).get(bucket, default))

    def policy_for(self, key: str, default: float = 0.0) -> float:
        return float(self.ranking_policy.get(key, default))


@dataclass
class FeedPhaseResult:
    """Result emitted by a single feed-oriented agent phase."""

    agent_name: str
    executed: bool = True
    facts: dict[str, Any] = field(default_factory=dict)
    analysis: str = ""
    execution_time_ms: float = 0.0
    confidence: float = 1.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.executed and self.error is None


@dataclass
class FeedContext:
    """State accumulated while building a ranked feed for a user."""

    feed_request_id: str
    start_time: datetime
    end_time: datetime | None = None
    selected_user: UserProfile | None = None
    candidate_posts: list[FeedPost] = field(default_factory=list)
    selected_agents: list[str] = field(default_factory=list)
    phase_results: list[FeedPhaseResult] = field(default_factory=list)
    ranked_posts: list[ScoreBreakdown] = field(default_factory=list)
    overall_analysis: str = ""
    top_k: int = 5

    def add_phase_result(self, result: FeedPhaseResult) -> None:
        self.phase_results.append(result)

    def get_result_by_agent(self, agent_name: str) -> FeedPhaseResult | None:
        for result in self.phase_results:
            if result.agent_name == agent_name:
                return result
        return None

    @property
    def duration_seconds(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class FeedInputs:
    """Structured feed inputs loaded by the harness before agent execution."""

    users: list[UserProfile]
    posts: list[FeedPost]
    scoring_config: ScoringConfig

    def get_user_by_id(self, user_id: str) -> UserProfile | None:
        for user in self.users:
            if user.user_id == user_id:
                return user
        return None


@dataclass
class FeedReport:
    """Final ranked feed report artifact for a single user request."""

    feed_request_id: str
    timestamp: datetime
    selected_user: UserProfile
    candidate_posts_count: int
    ranked_posts: list[ScoreBreakdown]
    top_posts: list[FeedPost]
    phase_results: list[FeedPhaseResult]
    overall_summary: str
    explanations: list[str] = field(default_factory=list)
    architecture_mapping: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        """Format the ranked feed into a compact CLI-friendly report."""
        lines = [
            "=" * 70,
            "Tessa1 Feed Report",
            "=" * 70,
            f"Request ID: {self.feed_request_id}",
            f"Timestamp: {self.timestamp.isoformat()}",
            f"User: {self.selected_user.name} ({self.selected_user.headline})",
            f"Candidates evaluated: {self.candidate_posts_count}",
            "",
            "Overall Summary:",
            f"  {self.overall_summary}",
            "",
            "Top Ranked Posts:",
        ]

        score_lookup = {score.post_id: score for score in self.ranked_posts}
        for index, post in enumerate(self.top_posts, start=1):
            score = score_lookup.get(post.post_id)
            lines.append(f"  {index}. {post.display_title} [{post.post_id}]")
            lines.append(
                f"     author={post.author} total_score={score.total_score:.2f}"
                if score
                else f"     author={post.author}"
            )
            if score and score.explanation_facts:
                lines.append(f"     why={' | '.join(score.explanation_facts)}")
            if index < len(self.top_posts):
                lines.append("")

        if self.explanations:
            lines.append("")
            lines.append("Generated Explanations:")
            for explanation in self.explanations:
                lines.append(f"  - {explanation}")

        if self.architecture_mapping:
            lines.append("")
            lines.append("Architecture Mapping:")
            for step in self.architecture_mapping:
                lines.append(f"  - {step}")

        return "\n".join(lines)
