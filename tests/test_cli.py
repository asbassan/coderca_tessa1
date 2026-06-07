from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from coderca_tessa1.cli import main
from coderca_tessa1.models import FeedPhaseResult, FeedPost, FeedReport, ScoreBreakdown, UserProfile


def _make_report() -> FeedReport:
    user = UserProfile(
        user_id="user-ava-ml",
        name="Ava Patel",
        headline="ML engineer exploring ranking systems",
    )
    post = FeedPost(
        post_id="post-1",
        author="Reuters",
        title="Microsoft expands cloud platform",
        body="Microsoft platform growth story",
        topics=["microsoft"],
        source="Reuters",
    )
    score = ScoreBreakdown(
        post_id="post-1",
        total_score=9.5,
        explanation_facts=[
            "primary intent: microsoft",
            "candidate plan: shortlisted for reranking",
        ],
    )
    return FeedReport(
        feed_request_id="feed-123",
        timestamp=datetime(2026, 6, 4, tzinfo=timezone.utc),
        selected_user=user,
        candidate_posts_count=20,
        ranked_posts=[score],
        top_posts=[post],
        phase_results=[FeedPhaseResult(agent_name="ProfileAgent")],
        overall_summary=(
            "Selected 1 posts for Ava Patel from 20 candidates "
            "with strongest alignment to microsoft."
        ),
        explanations=["Rank #1: Microsoft expands cloud platform scored 9.50 for Ava Patel."],
    )


def test_cli_list_users_outputs_available_profiles(monkeypatch) -> None:
    class StubLoader:
        def load_user_profiles(self) -> list[UserProfile]:
            return [
                UserProfile(
                    user_id="user-ava-ml",
                    name="Ava Patel",
                    headline="ML engineer exploring ranking systems",
                ),
                UserProfile(
                    user_id="user-econ",
                    name="Lina Shah",
                    headline="Economics researcher following policy",
                ),
            ]

    monkeypatch.setattr("coderca_tessa1.cli.FeedInputLoader", StubLoader)

    result = CliRunner().invoke(main, ["list-users"])

    assert result.exit_code == 0
    assert "Available Tessa1 demo users" in result.output
    assert "user-ava-ml: Ava Patel" in result.output
    assert "user-econ: Lina Shah" in result.output


def test_cli_demo_feed_renders_and_writes_report_and_runlog(tmp_path: Path, monkeypatch) -> None:
    class StubRunLog:
        def __init__(self) -> None:
            self.investigation_id = "feed-123"
            self.output_dir = tmp_path / "runlogs"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.scratchpads: dict[str, list[str]] = {}

        def save(self, output_path: str | None = None, **kwargs: str) -> None:
            file_format = kwargs.get("format", "text")
            target = (
                Path(output_path)
                if output_path
                else self.output_dir / f"{self.investigation_id}.txt"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            content = "json runlog" if file_format == "json" else "text runlog"
            target.write_text(content, encoding="utf-8")

    class StubOrchestrator:
        def __init__(self, enable_runlog: bool, use_real_llm: bool) -> None:
            self.enable_runlog = enable_runlog
            self.use_real_llm = use_real_llm

        def investigate(
            self,
            user_id: str | None = None,
            max_posts: int = 20,
            investigation_id: str | None = None,
        ) -> tuple[FeedReport, StubRunLog]:
            assert user_id == "user-ava-ml"
            assert max_posts == 20
            assert investigation_id == "feed-123"
            assert self.use_real_llm is True
            return _make_report(), StubRunLog()

    monkeypatch.setattr("coderca_tessa1.cli.Orchestrator", StubOrchestrator)

    report_path = tmp_path / "artifacts" / "ava-feed.txt"
    runlog_path = tmp_path / "logs" / "ava-runlog.txt"
    result = CliRunner().invoke(
        main,
        [
            "demo-feed",
            "--user-id",
            "user-ava-ml",
            "--max-posts",
            "20",
            "--id",
            "feed-123",
            "--output",
            str(report_path),
            "--runlog-output",
            str(runlog_path),
        ],
    )

    assert result.exit_code == 0
    assert "Tessa1 Feed Report" in result.output
    assert f"[OK] Report saved to: {report_path}" in result.output
    assert f"[OK] Runlog saved to: {runlog_path}" in result.output
    assert report_path.read_text(encoding="utf-8").startswith("=" * 70)
    assert runlog_path.read_text(encoding="utf-8") == "text runlog"
    assert runlog_path.with_suffix(".json").read_text(encoding="utf-8") == "json runlog"


def test_cli_demo_feed_saves_default_report_artifact(tmp_path: Path, monkeypatch) -> None:
    class StubOrchestrator:
        def __init__(self, enable_runlog: bool, use_real_llm: bool) -> None:
            self.enable_runlog = enable_runlog
            self.use_real_llm = use_real_llm

        def investigate(
            self,
            user_id: str | None = None,
            max_posts: int = 20,
            investigation_id: str | None = None,
        ) -> tuple[FeedReport, None]:
            assert self.use_real_llm is True
            return _make_report(), None

    monkeypatch.setattr("coderca_tessa1.cli.Orchestrator", StubOrchestrator)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "demo-feed",
                "--user-id",
                "user-ava-ml",
                "--max-posts",
                "20",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert "[OK] Report saved to: artifacts\\feed-123.txt" in result.output.replace("/", "\\")
        assert Path("artifacts/feed-123.txt").exists()


def test_cli_init_checks_files_and_prepares_directories(monkeypatch) -> None:
    class StubLoader:
        def __init__(self) -> None:
            self.users_path = Path("data/users.json")
            self.scoring_path = Path("config/scoring.json")

        def load_user_profiles(self) -> list[UserProfile]:
            return [
                UserProfile(
                    user_id="user-ava-ml",
                    name="Ava Patel",
                    headline="ML engineer exploring ranking systems",
                )
            ]

        def load_scoring_config(self):
            class StubScoring:
                top_k = 5

            return StubScoring()

    class StubFrame:
        index = list(range(10))

    monkeypatch.setattr("coderca_tessa1.cli.FeedInputLoader", StubLoader)
    monkeypatch.setattr("coderca_tessa1.cli.load_uci_news_dataframe", lambda: StubFrame())
    monkeypatch.setattr("coderca_tessa1.cli.COPILOT_SDK_AVAILABLE", True)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init"])

        assert result.exit_code == 0
        assert result.output.index("[OK] GitHub Copilot SDK:") < result.output.index(
            "[OK] artifacts directory:"
        )
        assert result.output.index("[OK] artifacts directory:") < result.output.index(
            "[OK] users.json:"
        )
        assert "[OK] users.json:" in result.output
        assert "[OK] scoring.json:" in result.output
        assert "[OK] News_Final.csv:" in result.output
        assert "[OK] GitHub Copilot SDK:" in result.output
        assert Path("artifacts").exists()
        assert Path("runlogs").exists()


def test_cli_global_init_flag_runs_initialization(monkeypatch) -> None:
    class StubLoader:
        def __init__(self) -> None:
            self.users_path = Path("data/users.json")
            self.scoring_path = Path("config/scoring.json")

        def load_user_profiles(self) -> list[UserProfile]:
            return [UserProfile(user_id="u1", name="User One", headline="Demo")]

        def load_scoring_config(self):
            class StubScoring:
                top_k = 3

            return StubScoring()

    class StubFrame:
        index = list(range(2))

    monkeypatch.setattr("coderca_tessa1.cli.FeedInputLoader", StubLoader)
    monkeypatch.setattr("coderca_tessa1.cli.load_uci_news_dataframe", lambda: StubFrame())
    monkeypatch.setattr("coderca_tessa1.cli.COPILOT_SDK_AVAILABLE", True)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["--init"])

        assert result.exit_code == 0
        assert "Initializing Tessa1" in result.output
        assert "[OK] Tessa1 initialization complete." in result.output


def test_cli_init_fails_when_sdk_is_missing(monkeypatch) -> None:
    class StubLoader:
        def __init__(self) -> None:
            self.users_path = Path("data/users.json")
            self.scoring_path = Path("config/scoring.json")

        def load_user_profiles(self) -> list[UserProfile]:
            return [UserProfile(user_id="u1", name="User One", headline="Demo")]

        def load_scoring_config(self):
            class StubScoring:
                top_k = 3

            return StubScoring()

    class StubFrame:
        index = list(range(2))

    monkeypatch.setattr("coderca_tessa1.cli.FeedInputLoader", StubLoader)
    monkeypatch.setattr("coderca_tessa1.cli.load_uci_news_dataframe", lambda: StubFrame())
    monkeypatch.setattr("coderca_tessa1.cli.COPILOT_SDK_AVAILABLE", False)

    result = CliRunner().invoke(main, ["init"])

    assert result.exit_code == 1
    assert "[FAIL] GitHub Copilot SDK:" in result.output
    assert "[FAIL] Fix the issues above before running the default real-LLM flow." in result.output


def test_cli_demo_feed_handles_missing_dataset(monkeypatch) -> None:
    class StubOrchestrator:
        def __init__(self, enable_runlog: bool, use_real_llm: bool) -> None:
            self.enable_runlog = enable_runlog
            self.use_real_llm = use_real_llm

        def investigate(
            self,
            user_id: str | None = None,
            max_posts: int = 20,
            investigation_id: str | None = None,
        ) -> tuple[FeedReport, None]:
            raise FileNotFoundError(
                "Local dataset snapshot not found: data\\raw\\uci_news\\News_Final.csv"
            )

    monkeypatch.setattr("coderca_tessa1.cli.Orchestrator", StubOrchestrator)

    result = CliRunner().invoke(main, ["demo-feed"])

    assert result.exit_code == 1
    assert "Local dataset snapshot not found" in result.output
    assert "Make sure the local UCI CSV snapshot exists" in result.output
