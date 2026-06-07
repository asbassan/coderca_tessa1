"""CLI entry point for the Tessa1 feed retrieval demo."""

from __future__ import annotations

from pathlib import Path

import click

from .copilot_client import COPILOT_SDK_AVAILABLE, SDK_IMPORT_ERROR
from .dataset_loader import load_uci_news_dataframe
from .input_loader import FeedInputLoader
from .orchestrator import Orchestrator
from .runlog import RunLog


def _write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _default_report_path(feed_request_id: str) -> Path:
    return Path("artifacts") / f"{feed_request_id}.txt"


def _print_check(label: str, ok: bool, detail: str) -> None:
    status = "[OK]" if ok else "[FAIL]"
    click.echo(f"{status} {label}: {detail}")


def _save_runlog(runlog: RunLog, runlog_output: Path | None) -> tuple[Path, Path]:
    if runlog_output is None:
        text_path = runlog.output_dir / f"{runlog.investigation_id}.txt"
        json_path = runlog.output_dir / f"{runlog.investigation_id}.json"
        runlog.save(format="text")
        runlog.save(format="json")
        return text_path, json_path

    text_path = runlog_output
    text_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = (
        text_path.with_suffix(".json")
        if text_path.suffix
        else text_path.parent / f"{text_path.name}.json"
    )
    runlog.save(str(text_path), format="text")
    runlog.save(str(json_path), format="json")
    return text_path, json_path


@click.group(invoke_without_command=True)
@click.option(
    "--init",
    "run_init_flag",
    is_flag=True,
    help="Run Tessa1 initialization checks and setup.",
)
@click.version_option()
@click.pass_context
def main(ctx: click.Context, run_init_flag: bool) -> None:
    """Tessa1 feed retrieval harness demo."""
    if run_init_flag:
        ctx.invoke(init)
        return

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
def init() -> None:
    """Check required inputs and prepare local output folders for Tessa1."""
    loader = FeedInputLoader()
    artifacts_dir = Path("artifacts")
    runlogs_dir = Path("runlogs")

    click.echo("Initializing Tessa1")
    click.echo("=" * 70)

    ok = True

    if COPILOT_SDK_AVAILABLE:
        _print_check(
            "GitHub Copilot SDK",
            True,
            (
                "package is installed; machine-level Copilot auth "
                "will be exercised on first real LLM run"
            ),
        )
    else:
        ok = False
        _print_check(
            "GitHub Copilot SDK",
            False,
            (
                f"package import failed: {SDK_IMPORT_ERROR}"
                if SDK_IMPORT_ERROR
                else "package not available; install github-copilot-sdk for default real LLM mode"
            ),
        )

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    runlogs_dir.mkdir(parents=True, exist_ok=True)
    _print_check("artifacts directory", True, str(artifacts_dir.resolve()))
    _print_check("runlogs directory", True, str(runlogs_dir.resolve()))

    try:
        users = loader.load_user_profiles()
        _print_check("users.json", True, f"{len(users)} profiles loaded from {loader.users_path}")
    except Exception as exc:
        ok = False
        _print_check("users.json", False, str(exc))

    try:
        scoring = loader.load_scoring_config()
        _print_check("scoring.json", True, f"top_k={scoring.top_k} from {loader.scoring_path}")
    except Exception as exc:
        ok = False
        _print_check("scoring.json", False, str(exc))

    try:
        frame = load_uci_news_dataframe()
        _print_check(
            "News_Final.csv",
            True,
            f"{len(frame.index)} rows readable from dataset snapshot",
        )
    except Exception as exc:
        ok = False
        _print_check("News_Final.csv", False, str(exc))

    if ok:
        click.echo("")
        click.echo("[OK] Tessa1 initialization complete.")
        click.echo("Next steps:")
        click.echo("  1. Run: coderca_tessa1 list-users")
        click.echo("  2. Run: coderca_tessa1 demo-feed --user-id user-ava-ml --max-posts 20")
        raise SystemExit(0)

    click.echo("")
    click.echo("[FAIL] Fix the issues above before running the default real-LLM flow.")
    raise SystemExit(1)


@main.command("list-users")
def list_users() -> None:
    """List the synthetic demo users available to the feed harness."""
    try:
        users = FeedInputLoader().load_user_profiles()
    except FileNotFoundError as exc:
        click.echo(f"[ERROR] {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo("Available Tessa1 demo users")
    click.echo("=" * 70)
    for user in users:
        click.echo(f"{user.user_id}: {user.name} - {user.headline}")


@main.command("demo-feed")
@click.option(
    "--user-id",
    help="Demo user ID. Run 'coderca_tessa1 list-users' to discover values.",
)
@click.option(
    "--max-posts",
    default=20,
    type=click.IntRange(1),
    show_default=True,
    help="Maximum number of candidate posts to evaluate.",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Optional path for the rendered feed report file.",
)
@click.option(
    "--save-report/--no-save-report",
    default=True,
    show_default=True,
    help="Save the rendered feed report to a file.",
)
@click.option("--id", "investigation_id", help="Optional request ID for the feed run.")
@click.option(
    "--save-runlog/--no-save-runlog",
    default=True,
    show_default=True,
    help="Save the execution runlog alongside the report.",
)
@click.option(
    "--runlog-output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Optional path for the text runlog file. JSON will be written beside it.",
)
@click.option(
    "--use-real-llm/--no-use-real-llm",
    default=True,
    show_default=True,
    help="Use the Copilot SDK for synthesis when available.",
)
def demo_feed(
    user_id: str | None,
    max_posts: int,
    output: Path | None,
    save_report: bool,
    investigation_id: str | None,
    save_runlog: bool,
    runlog_output: Path | None,
    use_real_llm: bool,
) -> None:
    """Run the Tessa1 feed ranking demo end to end."""
    try:
        orchestrator = Orchestrator(enable_runlog=save_runlog, use_real_llm=use_real_llm)
        report, runlog = orchestrator.investigate(
            user_id=user_id,
            max_posts=max_posts,
            investigation_id=investigation_id,
        )
    except FileNotFoundError as exc:
        click.echo(f"[ERROR] {exc}", err=True)
        click.echo(
            "Make sure the local UCI CSV snapshot exists at data\\raw\\uci_news\\News_Final.csv.",
            err=True,
        )
        raise SystemExit(1) from exc
    except ValueError as exc:
        click.echo(f"[ERROR] {exc}", err=True)
        if "Unknown user_id" in str(exc):
            click.echo("Run 'coderca_tessa1 list-users' to see valid demo users.", err=True)
        raise SystemExit(1) from exc

    rendered = report.to_text()
    click.echo(rendered)

    report_path = output or _default_report_path(report.feed_request_id)
    if save_report:
        _write_text_file(report_path, rendered)
        click.echo(f"[OK] Report saved to: {report_path}")

    if save_runlog and runlog is not None:
        text_path, json_path = _save_runlog(runlog, runlog_output)
        click.echo(f"[OK] Runlog saved to: {text_path}")
        click.echo(f"[OK] Runlog JSON saved to: {json_path}")
