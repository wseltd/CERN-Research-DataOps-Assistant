"""Documentation contract test for README scope boundaries."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
README_PATH = PROJECT_ROOT / "README.md"
REQUIRED_SCOPE_HEADERS = ("## Trade-offs", "## Limitations", "## Non-goals")
OUT_OF_SCOPE_FEATURE_KEYWORDS = (
    "hosted deployment",
    "remote services",
    "cloud/services",
    "cloud services",
    "saas",
    "managed service",
    "managed services",
    "internet-facing api",
    "internet-facing apis",
)
ALLOWED_SCOPE_SECTIONS = {"## Limitations", "## Non-goals"}
LIMITATION_EXCLUSION_MARKERS = (
    "no ",
    "not ",
    "without ",
    "excluded",
    "does not",
    "do not",
    "is not",
    "are not",
)


def test_readme_enforces_local_only_scope_and_required_sections() -> None:
    """Ensure scope-boundary features appear only as explicit exclusions."""
    assert README_PATH.is_file()

    readme_text = README_PATH.read_text(encoding="utf-8")
    assert all(header in readme_text for header in REQUIRED_SCOPE_HEADERS)

    current_section = ""
    invalid_scope_mentions: list[str] = []
    for raw_line in readme_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_section = line

        normalized_line = line.lower()
        if not any(keyword in normalized_line for keyword in OUT_OF_SCOPE_FEATURE_KEYWORDS):
            continue

        if current_section not in ALLOWED_SCOPE_SECTIONS:
            invalid_scope_mentions.append(line)
            continue

        if current_section == "## Limitations" and not any(
            marker in normalized_line for marker in LIMITATION_EXCLUSION_MARKERS
        ):
            invalid_scope_mentions.append(line)

    assert not invalid_scope_mentions
