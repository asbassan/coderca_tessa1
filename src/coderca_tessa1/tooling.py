"""Helpers for locating required local tooling."""

from pathlib import Path
import shutil


def resolve_gh_command() -> str:
    """Return a usable GitHub CLI executable path on Windows-friendly setups."""
    gh_path = shutil.which("gh")
    if gh_path:
        return gh_path

    known_path = Path(r"C:\Program Files\GitHub CLI\gh.exe")
    if known_path.exists():
        return str(known_path)

    return "gh"
