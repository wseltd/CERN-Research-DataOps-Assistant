"""Contract test for repository .gitignore entries."""

from __future__ import annotations

from pathlib import Path


REQUIRED_PATTERNS = (
    "__pycache__/",
    ".venv/",
    "*.egg-info/",
    ".pytest_cache/",
    ".coverage*",
    "htmlcov/",
    "data/",
)
BANNED_PATTERNS = ("node_modules/", ".terraform/", "target/")


def test_gitignore_includes_python_cache_venv_coverage_local_data_and_agent_patterns() -> None:
    """Ensure .gitignore includes required local-first Python patterns only."""
    gitignore_path = Path(__file__).resolve().parents[1] / ".gitignore"
    lines = [
        line.strip()
        for line in gitignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert all(pattern in lines for pattern in REQUIRED_PATTERNS)
    assert all(pattern not in lines for pattern in BANNED_PATTERNS)
