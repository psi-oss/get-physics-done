"""Focused assertions for derive-equation result persistence wiring."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_DOC = REPO_ROOT / "src/gpd/commands/derive-equation.md"
WORKFLOW_DOC = REPO_ROOT / "src/gpd/specs/workflows/derive-equation.md"


def test_derive_equation_command_doc_promises_registry_writeback() -> None:
    text = COMMAND_DOC.read_text(encoding="utf-8")

    assert 'gpd --raw validate command-context derive-equation "$ARGUMENTS"' in text
    assert "empty standalone launches stay blocked" in text
    assert "Keep standalone/current-workspace durable derivation artifacts under `GPD/analysis/` rooted at the invoking workspace." in text
    assert "canonical result lookup via `gpd result search`" in text
    assert 'direct stored-result inspection via `gpd result show "{result_id}"`' in text
    assert "Write the derivation artifact to a phase sibling only when authoritative phase context exists" in text
    assert "Record the derived equation in the project's `intermediate_results` registry through the executable `gpd result persist-derived` bridge only when authoritative phase context is available" in text
    assert "the workflow reuses or carries forward a stable `result_id` request on reruns" in text
    assert "actual canonical `result_id`" in text
    assert "seeds continuity automatically through the canonical continuation path when an active continuation context exists" in text
    assert "If no argument is given, you will be asked what to derive." not in text
    assert "`--carry-forward-last-result`" not in text
    assert "runs without authoritative phase context stop after writing the derivation document under the current-workspace `GPD/analysis/` tree" in text
    assert "do not write project registry state" in text


def test_derive_equation_workflow_reuses_prior_results_and_persists_final_equation() -> None:
    text = WORKFLOW_DOC.read_text(encoding="utf-8")

    assert 'INIT=$(gpd --raw init progress --include state,config --no-project-reentry)' in text
    assert "gpd --raw init phase-op --include state,config" not in text
    assert "Treat phase context as authoritative only when the bootstrap surfaces a concrete phase number and phase directory" in text
    assert "inspect `intermediate_results` before re-deriving" in text
    assert "existing canonical equation/result entries related to the target" in text
    assert "Use `gpd result search` to locate the canonical result first" in text
    assert 'use `gpd result show "{result_id}"` for the direct stored-result view' in text
    assert "result_id: [stable registry ID, if persisted]" in text
    assert "**Step 6: Persist Canonical Result**" in text
    assert "Persist the final derived equation through the executable `gpd result persist-derived` bridge only when project state is available and the phase context is authoritative." in text
    assert "gpd result persist-derived --id \"{result_id}\" --derivation-slug \"{derivation_slug}\"" in text
    assert "gpd result persist-derived --derivation-slug \"{derivation_slug}\" --equation \"{final_equation}\"" in text
    assert "Otherwise it derives a stable `requested_result_id` from the derivation slug and phase before delegating to the canonical upsert path" in text
    assert "If `gpd result persist-derived` reports multiple matches for the same equation or description" in text
    assert "`requested_result_id` is the stable derivation-oriented ID the workflow asked for." in text
    assert "`result_id` is the actual canonical registry entry that was persisted or reused." in text
    assert "`requested_result_redirected=true` means the requested derivation-oriented ID was redirected to an existing canonical entry" in text
    assert "If an active continuation context exists, the canonical path seeds continuity automatically from the actual `result_id`" in text
    assert "`--carry-forward-last-result`" not in text
    assert "Keep `verified=false` unless the derivation also produced verification evidence" in text
    assert "If `state_exists` is true but authoritative phase context is missing:" in text
    assert "Skip registry write-back entirely" in text
    assert "Do not synthesize `--phase` from `current_phase` prose, an ancestor project, or a guessed numeric label." in text
    assert "status=skipped" in text
    assert "reason=no_recoverable_project_state" in text
    assert "Final derived equation persisted through the executable `gpd result persist-derived` bridge in project mode" in text
    assert "actual persisted canonical `result_id` retained for later reruns and carried into canonical continuation for later pause/resume continuity" in text
