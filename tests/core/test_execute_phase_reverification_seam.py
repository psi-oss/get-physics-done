"""Focused assertions for the execute-phase re-verification seam."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _read(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def test_execute_phase_reverification_routes_on_typed_status_not_legacy_verifier_text() -> None:
    workflow = _read("execute-phase.md")

    assert "Automatically re-verify the phase to confirm gaps are closed:" in workflow
    assert "gpd_return.status: completed" in workflow
    assert "gpd_return.status: checkpoint" in workflow
    assert "gpd_return.status: blocked" in workflow
    assert "gpd_return.status: failed" in workflow
    assert "gpd_return.files_written" in workflow
    assert "verification_status: passed | gaps_found | expert_needed | human_needed" in workflow
    assert "After the artifact gate passes, use the canonical verifier verdict from `gpd_return.verification_status` or the written report frontmatter:" in workflow
    assert "Return verification status: passed | gaps_found." not in workflow
    assert "bare `passed | gaps_found` text as the routing surface" in workflow
    assert "Do not infer success from prose headings or untyped routing." in workflow
    assert "If the verifier output is malformed or omits `gpd_return.status`" in workflow


def test_execute_phase_reverification_requires_files_written_and_disk_artifact_gate() -> None:
    workflow = _read("execute-phase.md")

    assert 'subagent_type="gpd-verifier"' in workflow
    assert "files_written" in workflow
    assert "VERIFICATION.md" in workflow
    assert "The same path appears in `gpd_return.files_written`." in workflow
    assert "Do not accept `gpd_return.status: completed` until" in workflow
    assert "exists on disk" in workflow
    assert "Do not let a stale existing verification file satisfy the success path." in workflow
    assert "If the verifier output is malformed or omits `gpd_return.status`" in workflow
    assert "stale preexisting verification file" in workflow or "stale existing verification file" in workflow


def test_execute_phase_reverification_keeps_fail_closed_on_spawn_errors_and_stale_reports() -> None:
    workflow = _read("execute-phase.md")

    assert "If the verifier agent fails to spawn or returns an error" in workflow
    assert "Do not mark the phase complete or clear gap-closure state" in workflow
    assert "Do not trust the runtime handoff status by itself." in workflow
    assert "Do not let a stale existing verification file satisfy the success path." in workflow
    assert "report remaining gaps and STOP -- do not auto-loop" in workflow
