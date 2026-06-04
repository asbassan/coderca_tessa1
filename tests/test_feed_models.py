from datetime import datetime, timezone
from pathlib import Path

from tessa1.dataset_loader import FeedPostRecord, load_uci_news_dataframe, record_to_feed_post
from tessa1.models import (
    FeedContext,
    FeedPhaseResult,
    FeedReport,
    ScoreBreakdown,
    UserProfile,
)


def test_user_profile_topic_signals_are_normalized_and_deduplicated() -> None:
    profile = UserProfile(
        user_id="user-1",
        name="Tessa Demo",
        headline="AI engineer",
        skills=["Machine Learning", "python", "python"],
        interests=["Feed Systems", "machine learning"],
        recent_engagement_topics=["ranking", "Feed Systems"],
    )

    assert profile.topic_signals == [
        "machine learning",
        "python",
        "feed systems",
        "ranking",
    ]


def test_record_to_feed_post_maps_dataset_record_to_shared_model() -> None:
    record = FeedPostRecord(
        post_id="post-42",
        title="Ranking for engineers",
        headline="How ranking systems evolve",
        source="Engineering Weekly",
        topic="AI",
        published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        linkedin_popularity=250.0,
        facebook_popularity=120.0,
        googleplus_popularity=10.0,
        popularity_bucket="medium",
        recency_bucket="recent",
    )

    post = record_to_feed_post(record)

    assert post.post_id == "post-42"
    assert post.author == "Engineering Weekly"
    assert post.body == "How ranking systems evolve"
    assert post.normalized_topics == ["ai"]
    assert post.metadata["dataset"] == "uci_news_popularity"


def test_feed_context_tracks_phase_results() -> None:
    context = FeedContext(
        feed_request_id="feed-1",
        start_time=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )
    result = FeedPhaseResult(agent_name="ProfileAgent", facts={"skills": 3})

    context.add_phase_result(result)

    assert context.get_result_by_agent("ProfileAgent") == result
    assert context.get_result_by_agent("MissingAgent") is None


def test_feed_report_formats_ranked_posts() -> None:
    profile = UserProfile(
        user_id="user-1",
        name="Tessa Demo",
        headline="AI engineer",
    )
    post = record_to_feed_post(
        FeedPostRecord(
            post_id="post-42",
            title="Ranking for engineers",
            headline="How ranking systems evolve",
            source="Engineering Weekly",
            topic="AI",
            published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            linkedin_popularity=250.0,
            facebook_popularity=120.0,
            googleplus_popularity=10.0,
            popularity_bucket="medium",
            recency_bucket="recent",
        )
    )
    score = ScoreBreakdown(
        post_id="post-42",
        total_score=7.5,
        topic_overlap_score=4.0,
        skill_overlap_score=2.0,
        popularity_bonus=1.0,
        recency_bonus=0.5,
        explanation_facts=["topic overlap: ai", "recent post"],
    )
    report = FeedReport(
        feed_request_id="feed-1",
        timestamp=datetime(2026, 6, 3, tzinfo=timezone.utc),
        selected_user=profile,
        candidate_posts_count=12,
        ranked_posts=[score],
        top_posts=[post],
        phase_results=[],
        overall_summary="Ranked one post for demo output.",
    )

    rendered = report.to_text()

    assert "Tessa1 Feed Report" in rendered
    assert "Ranking for engineers" in rendered
    assert "total_score=7.50" in rendered
    assert "topic overlap: ai" in rendered


def test_load_uci_news_dataframe_reads_local_csv_snapshot(tmp_path: Path) -> None:
    csv_path = tmp_path / "News_Final.csv"
    csv_path.write_text(
        (
            '"IDLink","Title","Headline","Source","Topic","PublishDate","SentimentTitle",'
            '"SentimentHeadline","Facebook","GooglePlus","LinkedIn"\n'
            '"1","Sample title","Sample headline","Reuters","economy",'
            '"2026-01-01 00:00:00",0.1,0.2,10,11,12\n'
        ),
        encoding="utf-8",
    )

    frame = load_uci_news_dataframe(csv_path=csv_path)

    assert list(frame.columns)[:5] == ["IDLink", "Title", "Headline", "Source", "Topic"]
    assert frame.iloc[0]["LinkedIn"] == 12
