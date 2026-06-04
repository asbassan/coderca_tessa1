from coderca_tessa1.feed_agents import ProfileAgent, RetrievalRankingAgent
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


def test_retrieval_ranking_agent_emits_ranking_plan_and_shortlist() -> None:
    profile = UserProfile(
        user_id="user-1",
        name="Ava",
        headline="ML engineer exploring ranking systems",
        skills=["machine learning", "ranking"],
        interests=["microsoft", "technology"],
        recent_engagement_topics=["microsoft"],
        preferred_sources=["Reuters"],
    )
    _, intent = ProfileAgent().analyze(profile)
    posts = [
        FeedPost(post_id="1", author="Reuters", title="Microsoft cloud update", body="cloud", topics=["microsoft"], source="Reuters", recency_bucket="recent"),
        FeedPost(post_id="2", author="TechRadar", title="Microsoft Office update", body="office", topics=["microsoft"], source="TechRadar"),
        FeedPost(post_id="3", author="BBC", title="Economy view", body="markets", topics=["economy"], source="BBC", popularity_bucket="high"),
    ]

    result, ranked = RetrievalRankingAgent().rank(profile, intent, posts, _make_scoring_config())

    assert result.facts["ranking_plan"]["active_topics"]
    assert result.facts["shortlisted_posts"] >= 3
    assert ranked[0].metadata["adjusted_total_score"] >= ranked[0].total_score - 1.0
    assert any("candidate plan" in fact for fact in ranked[0].explanation_facts)


def test_retrieval_ranking_agent_applies_diversity_rerank() -> None:
    profile = UserProfile(
        user_id="user-1",
        name="Ava",
        headline="ML engineer exploring ranking systems",
        skills=["machine learning"],
        interests=["microsoft"],
        recent_engagement_topics=["microsoft"],
    )
    _, intent = ProfileAgent().analyze(profile)
    posts = [
        FeedPost(post_id="1", author="Source A", title="Microsoft update 1", body="microsoft", topics=["microsoft"], source="Source A"),
        FeedPost(post_id="2", author="Source A", title="Microsoft update 2", body="microsoft", topics=["microsoft"], source="Source A"),
        FeedPost(post_id="3", author="Source B", title="Microsoft update 3", body="microsoft", topics=["microsoft"], source="Source B"),
    ]

    _, ranked = RetrievalRankingAgent().rank(profile, intent, posts, _make_scoring_config())

    assert ranked[0].post_id == "1"
    assert ranked[1].post_id == "3"
    assert ranked[1].metadata["diversity_penalty"] == 0.5
    assert any("diversity rerank" in fact for fact in ranked[1].explanation_facts)
