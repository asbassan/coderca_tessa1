from coderca_tessa1.feed_agents import ProfileAgent
from coderca_tessa1.models import FeedPost, ScoringConfig, UserProfile


def test_profile_agent_interprets_weighted_topics_and_modes() -> None:
    profile = UserProfile(
        user_id="user-ava-ml",
        name="Ava Patel",
        headline="ML engineer exploring ranking systems",
        skills=["python", "machine learning", "ranking"],
        interests=["microsoft", "technology"],
        recent_engagement_topics=["microsoft"],
        preferred_sources=["Reuters"],
    )

    result, intent = ProfileAgent().analyze(profile)

    assert result.agent_name == "ProfileAgent"
    assert intent.primary_topics
    assert "microsoft" in intent.weighted_topic_intents
    assert "ai" in intent.expanded_topics or "ai" in intent.primary_topics or "ai" in intent.secondary_topics
    assert "technical-builder" in intent.profile_modes


def test_profile_agent_intent_can_match_expanded_topic_in_post() -> None:
    profile = UserProfile(
        user_id="user-ava-ml",
        name="Ava Patel",
        headline="ML engineer exploring ranking systems",
        skills=["machine learning"],
        interests=["microsoft"],
        recent_engagement_topics=["ranking"],
    )
    _, intent = ProfileAgent().analyze(profile)

    post = FeedPost(
        post_id="post-1",
        author="TechCrunch",
        title="AI tools reshape software teams",
        body="New AI platforms are changing engineering workflows.",
        topics=["ai"],
        source="TechCrunch",
    )
    scoring = ScoringConfig(weights={"topic_overlap_weight": 4.0, "skill_overlap_weight": 3.0, "recent_engagement_weight": 2.5})

    from coderca_tessa1.feed_agents import RetrievalRankingAgent

    _, ranked_posts = RetrievalRankingAgent().rank(
        profile=profile,
        profile_intent=intent,
        posts=[post],
        scoring_config=scoring,
    )

    assert ranked_posts[0].total_score > 0
    assert any("intent" in fact for fact in ranked_posts[0].explanation_facts)
