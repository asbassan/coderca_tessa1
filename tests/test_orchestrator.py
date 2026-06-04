from datetime import datetime, timezone

from coderca_tessa1.models import FeedInputs, FeedPost, ScoringConfig, UserProfile
from coderca_tessa1.orchestrator import Orchestrator


class StubLoader:
    def __init__(self, inputs: FeedInputs):
        self.inputs = inputs
        self.max_posts = 0

    def load_inputs(self) -> FeedInputs:
        return self.inputs


def test_orchestrator_returns_ranked_feed_report() -> None:
    user = UserProfile(
        user_id="user-ava-ml",
        name="Ava Patel",
        headline="ML engineer exploring ranking systems",
        skills=["python", "ranking"],
        interests=["microsoft", "technology"],
        recent_engagement_topics=["microsoft"],
        preferred_sources=["Reuters"],
    )
    posts = [
        FeedPost(
            post_id="post-1",
            author="Reuters",
            title="Microsoft expands cloud platform",
            body="Microsoft platform growth story",
            topics=["microsoft"],
            popularity_bucket="medium",
            recency_bucket="recent",
            source="Reuters",
            published_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        FeedPost(
            post_id="post-2",
            author="BBC",
            title="Economy update",
            body="Global markets update",
            topics=["economy"],
            popularity_bucket="low",
            recency_bucket="stale",
            source="BBC",
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
    ]
    scoring = ScoringConfig(
        top_k=2,
        weights={
            "topic_overlap_weight": 4.0,
            "skill_overlap_weight": 3.0,
            "recent_engagement_weight": 2.5,
            "preferred_source_weight": 1.5,
            "author_affinity_weight": 1.0,
        },
        bucket_bonuses={
            "popularity": {"high": 2.0, "medium": 1.0, "low": 0.0, "unknown": 0.0},
            "recency": {"recent": 2.0, "warm": 1.0, "stale": 0.0, "unknown": 0.0},
        },
        feature_definitions={"topic_overlap": "test"},
    )
    loader = StubLoader(FeedInputs(users=[user], posts=posts, scoring_config=scoring))
    orchestrator = Orchestrator(input_loader=loader, enable_runlog=False)

    report, runlog = orchestrator.investigate(user_id="user-ava-ml", max_posts=2)

    assert runlog is None
    assert report.selected_user.user_id == "user-ava-ml"
    assert [phase.agent_name for phase in report.phase_results] == [
        "ProfileAgent",
        "RetrievalRankingAgent",
        "SynthesisAgent",
    ]
    assert len(report.top_posts) == 2
    assert report.ranked_posts[0].post_id == "post-1"
    assert report.ranked_posts[0].total_score > report.ranked_posts[1].total_score
    assert report.explanations
    assert "microsoft" in report.explanations[0].lower()
