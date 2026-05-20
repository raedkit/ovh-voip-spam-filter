"""Ensure sensitive or volatile paths are gitignored."""

from __future__ import annotations

from pathlib import Path

GITIGNORE_PATH = Path(__file__).resolve().parent.parent / ".gitignore"

# (path-to-check, must-be-listed-pattern-in-gitignore)
REQUIRED_IGNORES = [
    ".ovh-credentials.json",  # secrets file (local dev convenience)
    "cache/",  # Saracroche snapshot cache
    "output/",  # generated CSVs
    ".venv/",  # python venv
    ".claude/",  # tool-specific working dir
]


def test_gitignore_exists() -> None:
    assert GITIGNORE_PATH.exists(), f"{GITIGNORE_PATH} must exist"


def test_required_paths_are_gitignored() -> None:
    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    patterns = {
        line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")
    }
    for required in REQUIRED_IGNORES:
        assert required in patterns, (
            f"{required!r} is not gitignored. Found patterns: {sorted(patterns)}"
        )
