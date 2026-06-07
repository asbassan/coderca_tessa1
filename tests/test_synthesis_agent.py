from coderca_tessa1.feed_agents import ProfileAgent, RetrievalRankingAgent, SynthesisAgent
from coderca_tessa1.models import FeedPost, ScoringConfig, UserProfile


def _make_scoring_config() -> ScoringConfig:
    return ScoringConfig(
        top_k=3,
        weights={
            "topic_overlap_weight": 4.0,
            "skill_overlap_weight": 3.0,
            "recent_engagement_weight": 2.5,
            "preferred_source_weight": 1.5,
        },
        bucket_bonuses={
            "popularity": {"high": 2.0, "medium": 1.0, "low": 0.0, "unknown": 0.0},
            "recency": {"recent": 2.0, "warm": 1.0, "stale": 0.0, "unknown": 0.0},
        },
        ranking_policy={
            "candidate_pool_multiplier": 2.0,
            "min_candidate_pool": 3.0,
            "focus_topic_bonus": 1.5,
            "preferred_source_shortlist_bonus": 0.75,
            "exploration_bonus": 0.5,
            "source_repeat_penalty": 1.0,
            "topic_repeat_penalty": 0.5,
        },
    )


def test_synthesis_agent_plans_audience_style_and_contrastive_explanations() -> None:
    profile = UserProfile(
        user_id="user-ava-ml",
        name="Ava Patel",
        headline="ML engineer exploring ranking systems",
        skills=["machine learning", "ranking"],
        interests=["microsoft", "technology"],
        recent_engagement_topics=["microsoft"],
        preferred_sources=["Reuters"],
    )
    _, intent = ProfileAgent().analyze(profile)
    posts = [
        FeedPost(
            post_id="post-1",
            author="Reuters",
            title="Microsoft expands cloud platform",
            body="Microsoft platform growth story for AI teams",
            topics=["microsoft", "technology"],
            source="Reuters",
            recency_bucket="recent",
            popularity_bucket="high",
        ),
        FeedPost(
            post_id="post-2",
            author="TechRadar",
            title="Microsoft tooling update",
            body="New developer tooling for cloud teams",
            topics=["microsoft"],
            source="TechRadar",
            recency_bucket="warm",
            popularity_bucket="medium",
        ),
    ]
    scoring = _make_scoring_config()
    _, ranked = RetrievalRankingAgent().rank(profile, intent, posts, scoring)

    result, explanations = SynthesisAgent().synthesize(profile, posts, ranked, scoring)

    assert result.facts["audience_style"] == "technical"
    assert result.facts["contrast_pairs"] == ["post-1>post-2"]
    assert explanations[0].startswith("Rank #1:")
    assert "Selected factors:" in explanations[0]
    assert "strongest baseline" in explanations[0]
    assert (
        "ranks below the post above" in explanations[1]
        or "trails the post above" in explanations[1]
    )
    assert explanations[1].count(";") <= 3
