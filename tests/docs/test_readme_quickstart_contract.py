"""Documentation contract tests for README quickstart and CLI usage."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
README_PATH = PROJECT_ROOT / "README.md"
REQUIRED_QUICKSTART_COMMANDS = (
    "python3 -m venv .venv",
    "source .venv/bin/activate",
    "python -m pip install --upgrade pip",
    "python -m pip install -e .",
    "cern-dataops --help",
)


def test_readme_contains_clean_checkout_quickstart_and_help_command() -> None:
    """Ensure README includes clean-checkout setup and CLI help usage."""
    assert README_PATH.is_file()

    readme_text = README_PATH.read_text(encoding="utf-8")
    assert "## Quickstart" in readme_text
    assert "## CLI Usage" in readme_text
    assert "From a clean checkout:" in readme_text

    quickstart_section = readme_text.split("## Quickstart", maxsplit=1)[1].split(
        "## CLI Usage",
        maxsplit=1,
    )[0]
    assert all(command in quickstart_section for command in REQUIRED_QUICKSTART_COMMANDS)

    cli_usage_section = readme_text.split("## CLI Usage", maxsplit=1)[1]
    assert "cern-dataops --help" in cli_usage_section
