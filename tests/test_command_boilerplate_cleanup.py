"""Regression test for command prompt boilerplate cleanup."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
AGENT_INFRASTRUCTURE = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "orchestration" / "agent-infrastructure.md"

LEGACY_COMMENT_FRAGMENTS = (
    "Tool names and @ includes are platform-specific.",
    "Allowed-tools are runtime-specific.",
    "Tool names and @ includes are runtime-specific.",
)

MODEL_FACING_DIRS = (COMMANDS_DIR, AGENTS_DIR)

UNRESOLVED_PLACEHOLDER_RE = re.compile(r"(?:^|\n)\s*(?:<!--\s*)?(?:TODO|FIXME|PLACEHOLDER)(?:\b|:)")

LEGACY_BACKCOMPAT_WORDING = (
    "backcompat",
    "back-compat",
    "backward compatibility",
    "backwards compatibility",
)


def test_model_facing_sources_do_not_keep_runtime_boilerplate_html_comments() -> None:
    for directory in MODEL_FACING_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for fragment in LEGACY_COMMENT_FRAGMENTS:
                assert fragment not in text, f"{path.relative_to(REPO_ROOT)} still contains: {fragment}"


def test_model_facing_prompts_do_not_ship_unresolved_placeholders() -> None:
    for directory in MODEL_FACING_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            assert not UNRESOLVED_PLACEHOLDER_RE.search(text), (
                f"{path.relative_to(REPO_ROOT)} still contains an unresolved placeholder marker"
            )


def test_model_facing_prompts_do_not_use_legacy_backcompat_wording() -> None:
    for directory in MODEL_FACING_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in LEGACY_BACKCOMPAT_WORDING:
                assert phrase not in text, f"{path.relative_to(REPO_ROOT)} still contains {phrase}"


def test_consistency_checker_uses_canonical_gpd_return_fields() -> None:
    path = AGENTS_DIR / "gpd-consistency-checker.md"
    text = path.read_text(encoding="utf-8")
    assert "phase_checked" not in text
    assert "  phase: [phase or milestone scope]" in text
    assert "  field_assessment:" in text
    assert "    checks_performed: [count]" in text
    assert "    issues_found: [count]" in text


def test_agent_infrastructure_uses_runtime_neutral_delegation_language() -> None:
    text = AGENT_INFRASTRUCTURE.read_text(encoding="utf-8")
    assert "Agent Delegation Checklist" in text
    assert "Before delegating to any agent" in text
    assert "Before spawning any agent" not in text
    assert "Spawning unnecessary agents" not in text
