"""Focused regressions for derive-equation result persistence wiring."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_DOC = REPO_ROOT / "src/gpd/commands/derive-equation.md"
WORKFLOW_DOC = REPO_ROOT / "src/gpd/specs/workflows/derive-equation.md"


def test_derive_equation_command_doc_promises_registry_writeback() -> None:
    text = COMMAND_DOC.read_text(encoding="utf-8")

    assert "Record the derived equation in the project's `intermediate_results` registry" in text
    assert "using `gpd result upsert` when project state is available" in text
    assert "standalone runs stop after writing the derivation document" in text
    assert "do not write project registry state" in text


def test_derive_equation_workflow_reuses_prior_results_and_persists_final_equation() -> None:
    text = WORKFLOW_DOC.read_text(encoding="utf-8")

    assert "inspect `intermediate_results` before re-deriving" in text
    assert "existing canonical equation/result entries related to the target" in text
    assert "result_id: [stable registry ID, if persisted]" in text
    assert "**Step 6: Persist Canonical Result**" in text
    assert "gpd result upsert --id \"{result_id}\"" in text
    assert "gpd result upsert --equation \"{final_equation}\"" in text
    assert "falls back to a unique exact description match" in text
    assert "If `gpd result upsert` reports multiple matches for the same equation or description" in text
    assert "gpd result add --id \"{result_id}\"" in text
    assert "gpd result update \"{result_id}\"" in text
    assert "Keep `verified=false` unless the derivation also produced verification evidence" in text
    assert "Skip registry write-back entirely" in text
