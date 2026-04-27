"""Focused assertions for the shared delegation reference contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATION_REFERENCES = REPO_ROOT / "src/gpd/specs/references/orchestration"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
    assert (
        "File-producing or state-sensitive spawned prompts must include this block directly in the prompt text" in text
    )
    assert "adjacent documented exemption" in text


def test_runtime_delegation_note_reuses_the_same_one_shot_and_artifact_language() -> None:
    text = _read(ORCHESTRATION_REFERENCES / "runtime-delegation-note.md")

    assert "agent-delegation.md" in text
    assert "one-shot" in text
    assert "`status: checkpoint`" in text
    assert "Artifact gate" in text
    assert "Fresh-continuation ownership" in text
    assert "Empty-model omission" in text
    assert "`readonly=false`" in text
    assert "execute sequentially in the main context" in text


def test_agent_infrastructure_points_spawned_write_contract_to_canonical_delegation_reference() -> None:
    text = _read(ORCHESTRATION_REFERENCES / "agent-infrastructure.md")
    write_contract = text.split("## Spawned Agent Write Contract", maxsplit=1)[1].split(
        "## gpd CLI State Commands", maxsplit=1
    )[0]

    assert "references/orchestration/agent-delegation.md" in write_contract
    assert "commit_authority" in write_contract
    assert "write_scope" in write_contract
    assert "shared_state_policy" in write_contract
    assert "<spawn_contract>" not in write_contract


def test_continuation_prompt_frames_the_spawn_as_a_fresh_continuation_not_an_in_run_wait() -> None:
    text = _read(TEMPLATES_DIR / "continuation-prompt.md")

    assert "fresh continuation handoff owned by the orchestrator" in text
    assert "Do not wait for the user inside the spawned run." in text
    assert "If the checkpoint payload names expected artifacts, verify them on disk before continuing" in text
    assert (
        "New executor verifies prior commits, incorporates user response, "
        "verifies any required artifacts, and continues execution" in text
    )
    assert "wait here for the user" not in text
    assert "wait for the user inside the same handoff" not in text
