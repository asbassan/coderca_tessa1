import json
from pathlib import Path

from coderca_tessa1.input_loader import FeedInputLoader
from coderca_tessa1.models import FeedPost


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_users_json_has_required_profile_fields() -> None:
    users = json.loads((PROJECT_ROOT / "data" / "users.json").read_text(encoding="utf-8"))

    assert len(users) >= 3

    for user in users:
        assert user["user_id"]
        assert user["name"]
        assert user["headline"]
        assert isinstance(user["skills"], list)
        assert isinstance(user["interests"], list)
        assert isinstance(user["recent_engagement_topics"], list)


def test_scoring_json_has_visible_feature_definitions() -> None:
    scoring = json.loads((PROJECT_ROOT / "config" / "scoring.json").read_text(encoding="utf-8"))

    assert scoring["top_k"] >= 1
    assert scoring["weights"]["topic_overlap_weight"] > 0
    assert scoring["weights"]["skill_overlap_weight"] > 0
    assert "feature_definitions" in scoring
    assert "topic_overlap" in scoring["feature_definitions"]
    assert "recency_bucket" in scoring["feature_definitions"]


def test_feed_input_loader_builds_structured_profiles_and_scoring_config() -> None:
    loader = FeedInputLoader(project_root=PROJECT_ROOT, max_posts=3)

    users = loader.load_user_profiles()
    scoring = loader.load_scoring_config()

    assert users[0].user_id == "user-ava-ml"
    assert users[0].metadata["notes"]
    assert scoring.top_k == 5
    assert scoring.weight_for("topic_overlap_weight") == 4.0
    assert scoring.bucket_bonus_for("recency", "recent") == 2.0


def test_feed_input_loader_load_inputs_aggregates_all_structured_inputs(monkeypatch) -> None:
    loader = FeedInputLoader(project_root=PROJECT_ROOT, max_posts=2)

    monkeypatch.setattr(
        "coderca_tessa1.input_loader.build_feed_posts",
        lambda max_rows: [
            FeedPost(
                post_id="post-1",
                author="Reuters",
                title="Economy update",
                body="Economy update body",
                topics=["economy"],
                popularity_bucket="medium",
                recency_bucket="recent",
                source="Reuters",
            )
        ],
    )

    inputs = loader.load_inputs()

    assert len(inputs.users) >= 3
    assert len(inputs.posts) == 1
    assert inputs.scoring_config.feature_definitions["topic_overlap"]
    assert inputs.get_user_by_id("user-mateo-econ") is not None
