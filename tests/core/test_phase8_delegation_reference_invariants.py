"""Focused regressions for the shared delegation reference contract."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.registry import _parse_spawn_contracts

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATION_REFERENCES = REPO_ROOT / "src/gpd/specs/references/orchestration"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str, next_heading: str | None = None) -> str:
    pattern = rf"^## {re.escape(heading)}\n(?P<body>.*)"
    if next_heading is not None:
        pattern = rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## {re.escape(next_heading)}\n)"

    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    assert match is not None, f"Missing section: {heading}"
    return match.group("body")


def _single_fenced_block(section: str) -> str:
    assert section.count("```") == 2
    matches = re.findall(r"```[^\n]*\n(.*?)\n```", section, flags=re.DOTALL)
    assert len(matches) == 1
    return matches[0]


def test_agent_delegation_reference_makes_one_shot_checkpoint_and_artifact_gate_explicit() -> None:
    text = _read(ORCHESTRATION_REFERENCES / "agent-delegation.md")

    assert "canonical delegation contract" in text
    assert "Delegation Invariants" in text
    assert "One-shot handoff" in text
    assert "returns `status: checkpoint` and stops" in text
    assert "Artifact gate" in text
    assert "verified on disk" in text
    assert "Fresh continuation ownership" in text
    assert "spawn a fresh continuation handoff" in text
    assert "must not wait for the user inside the same handoff" in text


def test_agent_delegation_task_example_keeps_one_clean_fence_and_no_injected_checklist() -> None:
    text = _read(ORCHESTRATION_REFERENCES / "agent-delegation.md")
    section = _section(text, "task() Delegation Block", next_heading="Runtime Alternatives")
    fence = _single_fenced_block(section)

    assert fence.count("task(") == 1
    assert fence.count("readonly=false") == 1
    assert "Do not use `@...` references inside task() prompt strings." not in fence
    assert "Fresh context:" not in fence
    assert "write_scope:" not in fence


def test_agent_delegation_spawn_contract_example_uses_nested_write_scope() -> None:
    text = _read(ORCHESTRATION_REFERENCES / "agent-delegation.md")
    section = _section(text, "Prompt Contract Addendum", next_heading="Platform Note Template")
    contracts = _parse_spawn_contracts(_single_fenced_block(section), owner_name="agent-delegation reference")

    assert len(contracts) == 1
    write_scope = contracts[0]["write_scope"]
    assert isinstance(write_scope, dict)
    assert write_scope["allowed_paths"]


def test_runtime_delegation_note_reuses_the_same_one_shot_and_artifact_language() -> None:
    text = _read(ORCHESTRATION_REFERENCES / "runtime-delegation-note.md")

    assert "one-shot handoff" in text
    assert "`status: checkpoint`" in text
    assert "verify the expected artifacts on disk before marking the handoff complete" in text
    assert "The orchestrator owns any fresh continuation handoff." in text
    assert "Always pass `readonly=false` for file-producing agents." in text


def test_continuation_prompt_frames_the_spawn_as_a_fresh_continuation_not_an_in_run_wait() -> None:
    text = _read(TEMPLATES_DIR / "continuation-prompt.md")

    assert "fresh continuation handoff owned by the orchestrator" in text
    assert "Do not wait for the user inside the spawned run." in text
    assert (
        "If the checkpoint payload names expected artifacts, verify them on disk "
        "before continuing" in text
    )
    assert (
        "New executor verifies prior commits, incorporates user response, "
        "verifies any required artifacts, and continues execution" in text
    )
    assert "wait here for the user" not in text
    assert "wait for the user inside the same handoff" not in text


def test_agent_delegation_reference_platform_note_stays_single_and_ends_cleanly() -> None:
    text = _read(ORCHESTRATION_REFERENCES / "agent-delegation.md")
    section = _section(text, "Platform Note Template")
    fence = _single_fenced_block(section)

    assert "Do not use `@...` references inside task() prompt strings." not in fence
    assert "Fresh context:" not in fence
    assert "write_scope:" not in fence
    tail = section.rsplit("```", 1)[-1]
    assert tail.strip() == ""
