"""Focused regressions for derive-equation result persistence wiring."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_DOC = REPO_ROOT / "src/gpd/commands/derive-equation.md"
WORKFLOW_DOC = REPO_ROOT / "src/gpd/specs/workflows/derive-equation.md"


def test_derive_equation_command_doc_promises_registry_writeback() -> None:
    text = COMMAND_DOC.read_text(encoding="utf-8")

    assert "Record the derived equation in the project's `intermediate_results` registry through the executable `gpd result persist-derived` bridge" in text
    assert "the workflow reuses or carries forward a stable `result_id` request on reruns" in text
    assert "actual canonical `result_id`" in text
    assert "skips cleanly when no recoverable project state exists" in text
    assert "standalone runs stop after writing the derivation document" in text
    assert "do not write project registry state" in text


def test_derive_equation_workflow_reuses_prior_results_and_persists_final_equation() -> None:
    text = WORKFLOW_DOC.read_text(encoding="utf-8")

    assert "inspect `intermediate_results` before re-deriving" in text
    assert "existing canonical equation/result entries related to the target" in text
    assert "result_id: [stable registry ID, if persisted]" in text
    assert "**Step 6: Persist Canonical Result**" in text
    assert "Persist the final derived equation through the executable `gpd result persist-derived` bridge when project state is available." in text
    assert "gpd result persist-derived --id \"{result_id}\" --derivation-slug \"{derivation_slug}\"" in text
    assert "gpd result persist-derived --derivation-slug \"{derivation_slug}\" --equation \"{final_equation}\"" in text
    assert "Otherwise it derives a stable `requested_result_id` from the derivation slug and phase before delegating to the canonical upsert path" in text
    assert "If `gpd result persist-derived` reports multiple matches for the same equation or description" in text
    assert "`requested_result_id` is the stable derivation-oriented ID the workflow asked for." in text
    assert "`result_id` is the actual canonical registry entry that was persisted or reused." in text
    assert "Carry the resulting `result_id` forward in the derivation workflow context and any downstream handoff metadata (`last_result_id` in pause/resume surfaces) so later reruns can target the same canonical registry entry without rediscovering it from prose." in text
    assert "Keep `verified=false` unless the derivation also produced verification evidence" in text
    assert "Skip registry write-back entirely" in text
    assert "status=skipped" in text
    assert "reason=no_recoverable_project_state" in text
    assert "Final derived equation persisted through the executable `gpd result persist-derived` bridge in project mode, with the actual persisted canonical `result_id` retained for later reruns" in text
