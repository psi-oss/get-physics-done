"""Parity tests for documented state status vocabulary."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.core.state import VALID_STATUSES

REPO_ROOT = Path(__file__).resolve().parents[2]


def _status_schema_values() -> list[str]:
    text = (REPO_ROOT / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8")
    match = re.search(r"\*\*Valid `status` values:\*\*\n\n```\n(?P<values>.*?)\n```", text, re.DOTALL)
    assert match is not None
    return [value.strip() for value in match.group("values").replace("\n", " ").split(",") if value.strip()]


def _roadmap_status_values() -> list[str]:
    text = (REPO_ROOT / "src/gpd/specs/templates/roadmap.md").read_text(encoding="utf-8")
    match = re.search(r"<status_values>\n(?P<body>.*?)\n\s*</status_values>", text, re.DOTALL)
    assert match is not None
    return re.findall(r"^- `([^`]+)` -", match.group("body"), re.MULTILINE)


def test_state_schema_status_values_match_core_state() -> None:
    assert _status_schema_values() == VALID_STATUSES

    text = (REPO_ROOT / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8")
    match = re.search(r"VALID_STATUSES list \((?P<count>\d+) values\)", text)
    assert match is not None
    assert int(match.group("count")) == len(VALID_STATUSES)


def test_roadmap_status_values_match_core_state() -> None:
    assert _roadmap_status_values() == VALID_STATUSES
