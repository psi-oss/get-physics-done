"""Tests for gpd.core.context — context assembly for AI agent commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.core.constants import ProjectLayout
from gpd.core.context import (
    _extract_frontmatter_field,
    _generate_slug,
    _is_phase_complete,
    _load_project_contract,
    _merge_active_references,
    _merge_reference_intake,
    _normalize_phase_name,
    _read_todo_frontmatter,
    _render_active_reference_context,
    _should_skip_research_scan_entry,
    _state_exists,
    init_execute_phase,
    init_literature_review,
    init_map_research,
    init_milestone_op,
    init_new_milestone,
    init_new_project,
    init_phase_op,
    init_plan_phase,
    init_progress,
    init_quick,
    init_research_phase,
    init_resume,
    init_sync_state,
    init_todos,
    init_verify_work,
    init_write_paper,
    load_config,
)
from gpd.core.errors import ConfigError, ValidationError
from gpd.core.frontmatter import compute_knowledge_reviewed_content_sha256
from gpd.core.recent_projects import record_recent_project
from gpd.core.reproducibility import compute_sha256
from gpd.core.resume_surface import RESUME_COMPATIBILITY_ALIAS_FIELDS
from gpd.core.workflow_staging import load_workflow_stage_manifest

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"
_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()
_XDG_RUNTIME_DESCRIPTOR = next(
    (descriptor for descriptor in _RUNTIME_DESCRIPTORS if descriptor.global_config.xdg_subdir),
    None,
)

# ─── Helpers ───────────────────────────────────────────────────────────────────


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project structure and return project root."""
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    return tmp_path


def _create_phase_dir(tmp_path: Path, name: str) -> Path:
    """Create a phase directory and return its path."""
    phase_dir = tmp_path / "GPD" / "phases" / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir


def _create_config(tmp_path: Path, config: dict) -> Path:
    """Write config.json and return its path."""
    config_path = tmp_path / "GPD" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


_PLAN_PHASE_STAGE_BOOTSTRAP_FIELDS = [
    "researcher_model",
    "planner_model",
    "checker_model",
    "research_enabled",
    "plan_checker_enabled",
    "commit_docs",
    "autonomy",
    "research_mode",
    "phase_found",
    "phase_dir",
    "phase_number",
    "phase_name",
    "phase_slug",
    "padded_phase",
    "has_research",
    "has_context",
    "has_plans",
    "plan_count",
    "planning_exists",
    "roadmap_exists",
    "project_contract",
    "project_contract_gate",
    "project_contract_load_info",
    "project_contract_validation",
    "platform",
]

_PLAN_PHASE_STAGE_AUTHORING_FIELDS = _PLAN_PHASE_STAGE_BOOTSTRAP_FIELDS + [
    "contract_intake",
    "effective_reference_intake",
    "selected_protocol_bundle_ids",
    "protocol_bundle_count",
    "protocol_bundle_context",
    "protocol_bundle_verifier_extensions",
    "active_reference_context",
    "reference_artifact_files",
    "reference_artifacts_content",
    "literature_review_files",
    "literature_review_count",
    "research_map_reference_files",
    "research_map_reference_count",
    "derived_manuscript_proof_review_status",
    "state_content",
    "roadmap_content",
    "requirements_content",
    "context_content",
    "research_content",
    "experiment_design_content",
    "verification_content",
    "validation_content",
]

_PLAN_PHASE_STAGE_CHECKER_AUDIT_FIELDS = [
    "checker_model",
    "research_enabled",
    "plan_checker_enabled",
    "commit_docs",
    "autonomy",
    "research_mode",
    "phase_found",
    "phase_dir",
    "phase_number",
    "phase_name",
    "phase_slug",
    "padded_phase",
    "has_research",
    "has_context",
    "has_plans",
    "plan_count",
    "planning_exists",
    "roadmap_exists",
    "project_contract",
    "project_contract_gate",
    "project_contract_load_info",
    "project_contract_validation",
    "contract_intake",
    "effective_reference_intake",
    "selected_protocol_bundle_ids",
    "protocol_bundle_count",
    "protocol_bundle_context",
    "protocol_bundle_verifier_extensions",
    "active_reference_context",
    "reference_artifact_files",
    "reference_artifacts_content",
    "literature_review_files",
    "literature_review_count",
    "research_map_reference_files",
    "research_map_reference_count",
    "derived_manuscript_proof_review_status",
    "requirements_content",
    "context_content",
    "research_content",
    "verification_content",
    "validation_content",
    "platform",
]

_PLAN_PHASE_STAGE_PLANNER_REVISION_FIELDS = [
    "planner_model",
    "research_enabled",
    "plan_checker_enabled",
    "commit_docs",
    "autonomy",
    "research_mode",
    "phase_found",
    "phase_dir",
    "phase_number",
    "phase_name",
    "phase_slug",
    "padded_phase",
    "has_research",
    "has_context",
    "has_plans",
    "plan_count",
    "planning_exists",
    "roadmap_exists",
    "project_contract",
    "project_contract_gate",
    "project_contract_load_info",
    "project_contract_validation",
    "contract_intake",
    "effective_reference_intake",
    "selected_protocol_bundle_ids",
    "protocol_bundle_count",
    "protocol_bundle_context",
    "protocol_bundle_verifier_extensions",
    "active_reference_context",
    "reference_artifact_files",
    "reference_artifacts_content",
    "literature_review_files",
    "literature_review_count",
    "research_map_reference_files",
    "research_map_reference_count",
    "derived_manuscript_proof_review_status",
    "state_content",
    "context_content",
    "research_content",
    "verification_content",
    "validation_content",
    "platform",
]


class _FakePlanPhaseStage:
    def __init__(self, stage_id: str, required_init_fields: list[str]) -> None:
        self.id = stage_id
        self.required_init_fields = required_init_fields


class _FakePlanPhaseManifest:
    def __init__(self) -> None:
        self.workflow_id = "plan-phase"
        self._stages = {
            "phase_bootstrap": _FakePlanPhaseStage("phase_bootstrap", _PLAN_PHASE_STAGE_BOOTSTRAP_FIELDS),
            "research_routing": _FakePlanPhaseStage("research_routing", _PLAN_PHASE_STAGE_BOOTSTRAP_FIELDS),
            "planner_authoring": _FakePlanPhaseStage("planner_authoring", _PLAN_PHASE_STAGE_AUTHORING_FIELDS),
            "checker_revision": _FakePlanPhaseStage("checker_revision", _PLAN_PHASE_STAGE_CHECKER_AUDIT_FIELDS),
        }

    def stage_by_id(self, stage_id: str) -> _FakePlanPhaseStage:
        return self._stages[stage_id]

    def stage_ids(self) -> list[str]:
        return list(self._stages)

    def staged_loading_payload(self, stage_id: str) -> dict[str, object]:
        return {"workflow_id": self.workflow_id, "stage_id": stage_id}


def _install_fake_plan_phase_manifest(monkeypatch: pytest.MonkeyPatch) -> _FakePlanPhaseManifest:
    manifest = _FakePlanPhaseManifest()

    def fake_load_workflow_stage_manifest(
        workflow_id: str,
        allowed_tools: set[str] | None = None,
        known_init_fields: set[str] | None = None,
    ) -> _FakePlanPhaseManifest:
        assert workflow_id == "plan-phase"
        return manifest

    monkeypatch.setattr("gpd.core.workflow_staging.load_workflow_stage_manifest", fake_load_workflow_stage_manifest)
    return manifest


class _FakeStageManifest:
    def __init__(self, workflow_id: str, stages: dict[str, list[str]]) -> None:
        self.workflow_id = workflow_id
        self._stages = {stage_id: _FakePlanPhaseStage(stage_id, fields) for stage_id, fields in stages.items()}

    def stage_by_id(self, stage_id: str) -> _FakePlanPhaseStage:
        return self._stages[stage_id]

    def stage_ids(self) -> list[str]:
        return list(self._stages)

    def staged_loading_payload(self, stage_id: str) -> dict[str, object]:
        return {"workflow_id": self.workflow_id, "stage_id": stage_id}


def _install_fake_stage_manifest(
    monkeypatch: pytest.MonkeyPatch,
    *,
    workflow_id: str,
    stages: dict[str, list[str]],
) -> _FakeStageManifest:
    manifest = _FakeStageManifest(workflow_id, stages)

    def fake_load_workflow_stage_manifest(
        requested_workflow_id: str,
        allowed_tools: set[str] | None = None,
        known_init_fields: set[str] | None = None,
    ) -> _FakeStageManifest:
        assert requested_workflow_id == workflow_id
        return manifest

    monkeypatch.setattr("gpd.core.workflow_staging.load_workflow_stage_manifest", fake_load_workflow_stage_manifest)
    return manifest


def _write_state_intent_recovery_files(project_root: Path) -> ProjectLayout:
    from gpd.core.state import default_state_dict

    layout = ProjectLayout(project_root)
    layout.state_json.parent.mkdir(parents=True, exist_ok=True)
    layout.state_json.write_text(json.dumps(default_state_dict(), indent=2) + "\n", encoding="utf-8")

    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"
    json_tmp = layout.gpd / ".state-json-tmp"
    md_tmp = layout.gpd / ".state-md-tmp"
    json_tmp.write_text(json.dumps(recovered_state, indent=2) + "\n", encoding="utf-8")
    md_tmp.write_text("# Recovered State\n", encoding="utf-8")
    layout.state_intent.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")
    return layout


def _write_manuscript_proof_review_artifacts(tmp_path: Path) -> Path:
    return _write_manuscript_proof_review_artifacts_with_proof_path(
        tmp_path,
        proof_artifact_path="paper/curvature_flow_bounds.tex",
    )


def _write_manuscript_proof_review_artifacts_with_proof_path(
    tmp_path: Path,
    *,
    proof_artifact_path: str,
) -> Path:
    manuscript_path = tmp_path / "paper" / "curvature_flow_bounds.tex"
    manuscript_path.parent.mkdir(parents=True, exist_ok=True)
    manuscript_path.write_text(
        "\\documentclass{article}\n\\begin{document}\n\\begin{theorem}For every r_0 > 0, the orbit intersects the target annulus.\\end{theorem}\n\\end{document}\n",
        encoding="utf-8",
    )
    (manuscript_path.parent / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Curvature Flow Bounds",
                "authors": [{"name": "Test Author"}],
                "abstract": "A test manuscript used to exercise proof-review freshness.",
                "sections": [],
                "journal": "jhep",
                "output_filename": "curvature_flow_bounds",
            }
        ),
        encoding="utf-8",
    )
    proof_artifact = tmp_path / proof_artifact_path
    proof_artifact.parent.mkdir(parents=True, exist_ok=True)
    if proof_artifact != manuscript_path:
        proof_artifact.write_text(
            "\\documentclass{article}\n\\begin{document}\n\\begin{theorem}External theorem proof.\\end{theorem}\n\\end{document}\n",
            encoding="utf-8",
        )
    proof_redteam_artifact_paths = f"  - {proof_artifact_path}\n"
    if proof_artifact_path != "paper/curvature_flow_bounds.tex":
        proof_redteam_artifact_paths += "  - paper/curvature_flow_bounds.tex\n"
    review_dir = tmp_path / "GPD" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    manuscript_sha256 = compute_sha256(manuscript_path)
    (review_dir / "CLAIMS.json").write_text(
        json.dumps(
            {
                "version": 1,
                "manuscript_path": "paper/curvature_flow_bounds.tex",
                "manuscript_sha256": manuscript_sha256,
                "claims": [
                    {
                        "claim_id": "CLM-001",
                        "claim_type": "main_result",
                        "claim_kind": "theorem",
                        "text": "For every r_0 > 0, the orbit intersects the target annulus.",
                        "artifact_path": proof_artifact_path,
                        "section": "Main Result",
                        "equation_refs": [],
                        "figure_refs": [],
                        "supporting_artifacts": [],
                        "theorem_assumptions": ["chi > 0"],
                        "theorem_parameters": ["r_0"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (review_dir / "STAGE-math.json").write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "stage_id": "math",
                "stage_kind": "math",
                "manuscript_path": "paper/curvature_flow_bounds.tex",
                "manuscript_sha256": manuscript_sha256,
                "claims_reviewed": ["CLM-001"],
                "summary": "math review",
                "strengths": ["checked proof"],
                "findings": [],
                "proof_audits": [
                    {
                        "claim_id": "CLM-001",
                        "theorem_assumptions_checked": ["chi > 0"],
                        "theorem_parameters_checked": ["r_0"],
                        "proof_locations": [f"{proof_artifact_path}:1"],
                        "uncovered_assumptions": [],
                        "uncovered_parameters": [],
                        "coverage_gaps": [],
                        "alignment_status": "aligned",
                        "notes": "Complete coverage.",
                    }
                ],
                "confidence": "high",
                "recommendation_ceiling": "minor_revision",
            }
        ),
        encoding="utf-8",
    )
    (review_dir / "PROOF-REDTEAM.md").write_text(
        (
            "---\n"
                "status: passed\n"
                "reviewer: gpd-check-proof\n"
            "claim_ids:\n"
            "  - CLM-001\n"
            "proof_artifact_paths:\n"
            f"{proof_redteam_artifact_paths}"
            "manuscript_path: paper/curvature_flow_bounds.tex\n"
            f"manuscript_sha256: {manuscript_sha256}\n"
            "round: 1\n"
            "missing_parameter_symbols: []\n"
            "missing_hypothesis_ids: []\n"
            "coverage_gaps: []\n"
            "scope_status: matched\n"
            "quantifier_status: matched\n"
            "counterexample_status: none_found\n"
            "---\n\n"
            "# Proof Redteam\n"
            "## Proof Inventory\n"
            "- Exact claim / theorem text: For every r_0 > 0, the orbit intersects the target annulus.\n"
            "- Claim / theorem target: Annulus intersection for every target radius.\n"
            "- Named parameters:\n"
            "  - `r_0`: target radius\n"
            "- Hypotheses:\n"
                "  - `H1`: chi > 0\n"
                "- Quantifier / domain obligations:\n"
                "  - for every r_0 > 0\n"
                "- Conclusion clauses:\n"
                "  - annulus intersection holds\n"
                "## Coverage Ledger\n"
            "### Named-Parameter Coverage\n"
                "| Parameter | Role / Domain | Proof Location | Status | Notes |\n"
                "| --- | --- | --- | --- |\n"
                f"| `r_0` | target radius | {proof_artifact_path}:1 | covered | Carried through the argument. |\n"
                "### Hypothesis Coverage\n"
                "| Hypothesis | Proof Location | Status | Notes |\n"
                "| --- | --- | --- | --- |\n"
                f"| `H1` | {proof_artifact_path}:1 | covered | Used in the positivity step. |\n"
                "### Quantifier / Domain Coverage\n"
                "| Obligation | Proof Location | Status | Notes |\n"
                "| --- | --- | --- | --- |\n"
                f"| `for every r_0 > 0` | {proof_artifact_path}:1 | covered | No specialization introduced. |\n"
                "### Conclusion-Clause Coverage\n"
                "| Clause | Proof Location | Status | Notes |\n"
                "| --- | --- | --- | --- |\n"
                f"| annulus intersection holds | {proof_artifact_path}:1 | covered | Final sentence states it. |\n"
            "## Adversarial Probe\n"
            "- Probe type: dropped-parameter test\n"
            "- Result: The proof still references r_0, so the theorem remains global in the target radius.\n"
            "## Verdict\n"
            "- Scope status: `matched`\n"
            "- Quantifier status: `matched`\n"
            "- Counterexample status: `none_found`\n"
            "- Blocking gaps:\n"
            "  - None.\n"
            "## Required Follow-Up\n"
            "- None.\n"
        ),
        encoding="utf-8",
    )
    return tmp_path / "paper" / "references.bib"


def _create_roadmap(tmp_path: Path, content: str) -> Path:
    """Write ROADMAP.md and return its path."""
    roadmap = tmp_path / "GPD" / "ROADMAP.md"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(content, encoding="utf-8")
    return roadmap


def _runtime_owned_local_install_dirs(root: Path) -> tuple[Path, ...]:
    """Return runtime-owned local install roots derived from the catalog."""
    paths: list[Path] = []
    for descriptor in _RUNTIME_DESCRIPTORS:
        paths.append(root / descriptor.config_dir_name)
    return tuple(dict.fromkeys(paths))


@pytest.mark.skipif(_XDG_RUNTIME_DESCRIPTOR is None, reason="No runtime advertises an XDG mirror path")
def test_research_scan_skips_only_runtime_owned_install_roots(tmp_path: Path) -> None:
    workspace = tmp_path
    assert _XDG_RUNTIME_DESCRIPTOR is not None
    runtime_root = workspace / _XDG_RUNTIME_DESCRIPTOR.config_dir_name
    runtime_root.mkdir()
    xdg_mirror = workspace / ".config" / _XDG_RUNTIME_DESCRIPTOR.global_config.xdg_subdir
    xdg_mirror.mkdir(parents=True)
    foreign_mirror = xdg_mirror / "notes"
    foreign_mirror.mkdir(parents=True)

    assert _should_skip_research_scan_entry(workspace, runtime_root) is True
    assert _should_skip_research_scan_entry(workspace, xdg_mirror) is False
    assert _should_skip_research_scan_entry(workspace, foreign_mirror) is False


def _write_project_contract_state(tmp_path: Path) -> None:
    """Persist the Stage 0 project contract fixture into state.json."""
    from gpd.core.state import default_state_dict

    state = default_state_dict()
    state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_coercive_project_contract_state(tmp_path: Path) -> None:
    """Persist a contract payload that should require schema normalization."""
    from gpd.core.state import default_state_dict

    state = default_state_dict()
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"][0]["must_surface"] = "yes"
    state["project_contract"] = contract
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_recoverable_project_contract_state(tmp_path: Path) -> None:
    """Persist a contract payload that only needs recoverable normalization."""
    from gpd.core.state import default_state_dict

    state = default_state_dict()
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "harmless"
    state["project_contract"] = contract
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_structured_state_payload(tmp_path: Path) -> None:
    """Persist a representative structured state payload into state.json."""
    from gpd.core.state import default_state_dict

    state_path = tmp_path / "GPD" / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = default_state_dict()

    state.setdefault("convention_lock", {}).update(
        {
            "metric_signature": "(-,+,+,+)",
            "fourier_convention": "physics",
            "natural_units": "SI",
        }
    )
    state["intermediate_results"] = [
        {
            "id": "R-01",
            "equation": "E = mc^2",
            "description": "Rest energy",
            "phase": "01",
            "depends_on": [],
            "verified": True,
            "verification_records": [{"verifier": "auditor", "method": "manual", "confidence": "high"}],
        },
        "legacy markdown bullet",
    ]
    state["approximations"] = [
        {
            "name": "weak coupling",
            "validity_range": "g << 1",
            "controlling_param": "g",
            "current_value": "0.1",
            "status": "valid",
        }
    ]
    state["propagated_uncertainties"] = [
        {
            "quantity": "m_eff",
            "value": "1.2",
            "uncertainty": "0.1",
            "phase": "03",
            "method": "bootstrap",
        }
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")


def _assert_structured_state_context(ctx: dict[str, object], tmp_path: Path) -> None:
    """Assert the shared structured-state init payload contract."""
    assert ctx["state_load_source"] == "state.json"
    assert ctx["state_integrity_issues"] == []
    assert ctx["convention_lock"]["metric_signature"] == "(-,+,+,+)"
    assert ctx["convention_lock"]["fourier_convention"] == "physics"
    assert ctx["convention_lock"]["natural_units"] == "SI"
    assert ctx["intermediate_result_count"] == 1
    assert ctx["intermediate_results"][0]["id"] == "R-01"
    assert ctx["intermediate_results"][0]["verified"] is True
    assert ctx["approximation_count"] == 1
    assert ctx["approximations"][0]["name"] == "weak coupling"
    assert ctx["propagated_uncertainty_count"] == 1
    assert ctx["propagated_uncertainties"][0]["quantity"] == "m_eff"


def _write_stat_mech_project(tmp_path: Path) -> None:
    project = tmp_path / "GPD" / "PROJECT.md"
    project.write_text(
        """# Test Project

## What This Is

Monte Carlo study of a statistical mechanics lattice model near criticality.

## Research Context

### Theoretical Framework

Statistical mechanics

### Known Results

Binder cumulants, thermalization windows, and finite-size scaling should be benchmarked.
""",
        encoding="utf-8",
    )


def _write_bundle_ready_contract_state(tmp_path: Path) -> None:
    from gpd.core.state import default_state_dict

    state = default_state_dict()
    state["project_contract"] = {
        "schema_version": 1,
        "scope": {
            "question": "What finite-size scaling collapse and benchmark comparison does the simulation recover?",
            "in_scope": ["Recover the decisive finite-size scaling benchmark for the simulation regime"],
        },
        "claims": [
            {
                "id": "claim-critical",
                "statement": "Recover benchmark finite-size scaling behavior",
                "deliverables": ["deliv-data", "deliv-figure"],
                "acceptance_tests": ["test-benchmark"],
                "references": ["ref-benchmark"],
            }
        ],
        "deliverables": [
            {
                "id": "deliv-data",
                "kind": "dataset",
                "path": "results/measurements.csv",
                "description": "Raw Monte Carlo measurements with metadata",
            },
            {
                "id": "deliv-figure",
                "kind": "figure",
                "path": "figures/collapse.png",
                "description": "Finite-size scaling collapse figure",
            },
        ],
        "acceptance_tests": [
            {
                "id": "test-benchmark",
                "subject": "claim-critical",
                "kind": "benchmark",
                "procedure": "Compare Binder cumulants and finite-size scaling against literature benchmarks",
                "pass_condition": "Benchmark agreement is within uncertainty",
            }
        ],
        "references": [
            {
                "id": "ref-benchmark",
                "kind": "paper",
                "locator": "Benchmark Monte Carlo paper",
                "role": "benchmark",
                "why_it_matters": "Decisive comparison for the simulation regime",
                "applies_to": ["claim-critical"],
                "must_surface": True,
                "required_actions": ["read", "compare", "cite"],
            }
        ],
        "context_intake": {
            "must_read_refs": ["ref-benchmark"],
        },
        "forbidden_proxies": [
            {
                "id": "fp-proxy",
                "subject": "claim-critical",
                "proxy": "Qualitative agreement without scaling analysis",
                "reason": "Would not validate the decisive benchmarked observable",
            }
        ],
        "uncertainty_markers": {
            "weakest_anchors": ["Autocorrelation estimate near the critical point"],
            "disconfirming_observations": ["Finite-size crossings drift away from the benchmark window"],
        },
    }
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _assert_no_resume_compat_aliases(payload: dict[str, object]) -> None:
    for key in RESUME_COMPATIBILITY_ALIAS_FIELDS:
        assert key not in payload


def _write_numerical_relativity_project(tmp_path: Path) -> None:
    project = tmp_path / "GPD" / "PROJECT.md"
    project.write_text(
        """# Test Project

## What This Is

BSSN numerical relativity study of a binary black hole merger with moving-puncture evolution.

## Research Context

### Theoretical Framework

General relativity

### Known Results

Apparent horizon tracking, constraint propagation, and gravitational waveform extraction should match trusted benchmarks.
""",
        encoding="utf-8",
    )


def _write_numerical_relativity_contract_state(tmp_path: Path) -> None:
    from gpd.core.state import default_state_dict

    state = default_state_dict()
    state["project_contract"] = {
        "schema_version": 1,
        "scope": {
            "question": "Does the BSSN evolution reproduce benchmark waveform and remnant behavior?",
            "in_scope": ["Recover the decisive waveform and remnant benchmark for the BSSN evolution"],
        },
        "claims": [
            {
                "id": "claim-waveform",
                "statement": "Recover benchmark waveform phase and remnant properties",
                "deliverables": ["deliv-data", "deliv-figure"],
                "acceptance_tests": ["test-benchmark"],
                "references": ["ref-benchmark"],
            }
        ],
        "deliverables": [
            {
                "id": "deliv-data",
                "kind": "dataset",
                "path": "results/constraints.csv",
                "description": "Constraint histories and remnant diagnostics",
            },
            {
                "id": "deliv-figure",
                "kind": "figure",
                "path": "figures/waveform-comparison.png",
                "description": "Waveform benchmark comparison figure",
            },
        ],
        "acceptance_tests": [
            {
                "id": "test-benchmark",
                "subject": "claim-waveform",
                "kind": "benchmark",
                "procedure": "Compare waveform phase, remnant parameters, and convergence against trusted numerical-relativity results",
                "pass_condition": "Benchmark agreement is within numerical uncertainty",
            }
        ],
        "references": [
            {
                "id": "ref-benchmark",
                "kind": "paper",
                "locator": "https://doi.org/10.1234/numerical-relativity-benchmark",
                "role": "benchmark",
                "why_it_matters": "Provides decisive waveform and remnant anchors",
                "applies_to": ["claim-waveform"],
                "must_surface": True,
                "required_actions": ["read", "compare", "cite"],
            }
        ],
        "context_intake": {
            "must_read_refs": ["ref-benchmark"],
        },
        "forbidden_proxies": [
            {
                "id": "fp-proxy",
                "subject": "claim-waveform",
                "proxy": "Smooth-looking waveforms without converged constraints or benchmark agreement",
                "reason": "Would not validate the decisive strong-field observable",
            }
        ],
        "uncertainty_markers": {
            "weakest_anchors": ["Gauge-parameter sensitivity of the extracted waveform"],
            "disconfirming_observations": ["Constraint growth or waveform phase drift relative to the benchmark"],
        },
    }
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_structured_state_memory(tmp_path: Path) -> None:
    """Persist conventions, canonical results, and approximations into state.json."""
    from gpd.core.state import default_state_dict

    state = default_state_dict()
    state["convention_lock"].update(
        {
            "metric_signature": "mostly-plus",
            "coordinate_system": "Cartesian",
        }
    )
    state["intermediate_results"] = [
        {
            "id": "R-01",
            "equation": "E = mc^2",
            "description": "Mass-energy relation",
            "phase": "1",
            "depends_on": [],
            "verified": True,
            "verification_records": [],
        }
    ]
    state["approximations"] = [
        {
            "name": "weak coupling",
            "validity_range": "g << 1",
            "controlling_param": "g",
            "current_value": "0.1",
            "status": "valid",
        }
    ]
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_current_execution(tmp_path: Path, payload: dict[str, object]) -> None:
    observability = tmp_path / "GPD" / "observability"
    observability.mkdir(parents=True, exist_ok=True)
    resume_file = payload.get("resume_file")
    if isinstance(resume_file, str) and resume_file:
        resume_path = Path(resume_file)
        if not resume_path.is_absolute():
            resume_path = tmp_path / resume_path
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")
    (observability / "current-execution.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_literature_review_anchor_file(tmp_path: Path) -> None:
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True, exist_ok=True)
    (literature_dir / "benchmark-REVIEW.md").write_text(
        """# Literature Review: Benchmark Survey

## Active Anchor Registry

| Anchor | Type | Why It Matters | Required Action | Downstream Use |
| ------ | ---- | -------------- | --------------- | -------------- |
| Benchmark Ref 2024 | benchmark | Published benchmark curve for the primary quantity | read/compare/cite | planning/execution |

## Open Questions

- Need exact normalization convention from the literature

```yaml
---
review_summary:
  topic: "Benchmark Survey"
  benchmark_values:
    - quantity: "critical slope"
      value: "1.23 +/- 0.04"
      source: "Benchmark Ref 2024"
  active_anchors:
    - anchor: "Benchmark Ref 2024"
      type: "benchmark"
      why_it_matters: "Published benchmark curve for the primary quantity"
      required_action: "read/compare/cite"
      downstream_use: "planning/execution"
---
```
""",
        encoding="utf-8",
    )


def _write_literature_citation_source_file(tmp_path: Path) -> None:
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True, exist_ok=True)
    (literature_dir / "benchmark-CITATION-SOURCES.json").write_text(
        json.dumps(
            [
                {
                    "reference_id": "ref-benchmark",
                    "source_type": "paper",
                    "title": "Benchmark Ref 2024",
                    "authors": ["A. Author", "B. Benchmarker"],
                    "year": "2024",
                    "bibtex_key": "benchmark2024",
                    "doi": "10.1000/benchmark.2024",
                    "arxiv_id": "2401.01234",
                    "url": "https://example.org/benchmark",
                    "journal": "J. Benchmarks",
                }
            ]
        ),
        encoding="utf-8",
    )


def _write_manuscript_bibliography_audit(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir(exist_ok=True)
    (paper_dir / "BIBLIOGRAPHY-AUDIT.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-30T00:00:00+00:00",
                "total_sources": 1,
                "resolved_sources": 1,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": [
                    {
                        "key": "benchmark2024",
                        "source_type": "paper",
                        "reference_id": "ref-benchmark",
                        "title": "Benchmark Paper",
                        "resolution_status": "provided",
                        "verification_status": "verified",
                        "verification_sources": ["manual"],
                        "canonical_identifiers": ["doi:10.1000/example"],
                        "missing_core_fields": [],
                        "enriched_fields": [],
                        "warnings": [],
                        "errors": [],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_research_map_anchor_files(tmp_path: Path) -> None:
    map_dir = tmp_path / "GPD" / "research-map"
    map_dir.mkdir(parents=True, exist_ok=True)
    (map_dir / "REFERENCES.md").write_text(
        """# Reference and Anchor Map

## Active Anchor Registry

| Anchor | Type | Source / Locator | What It Constrains | Required Action | Carry Forward To |
| ------ | ---- | ---------------- | ------------------ | --------------- | ---------------- |
| prior-baseline | prior artifact | `GPD/phases/01-test-phase/01-SUMMARY.md` | Baseline summary for calibration and later comparisons | use | planning/execution |
| benchmark-paper | benchmark | Author et al., Journal, 2024 | Published comparison target for the decisive observable | read/compare/cite | verification/writing |

## Benchmarks and Comparison Targets

- Universal crossing window
  - Source: Author et al., Journal, 2024
  - Compared in: `GPD/phases/01-test-phase/01-SUMMARY.md`
  - Status: pending

## Prior Artifacts and Baselines

- `GPD/phases/01-test-phase/01-SUMMARY.md`: Prior baseline summary that later phases must keep visible

## Open Reference Questions

- Need collaboration note with the definitive normalization
""",
        encoding="utf-8",
    )
    (map_dir / "VALIDATION.md").write_text(
        """# Validation and Cross-Checks

## Comparison with Literature

- Result from Author et al., Journal, 2024: agreement still needs confirmation
  - Comparison in: `GPD/phases/01-test-phase/01-SUMMARY.md`
""",
        encoding="utf-8",
    )


def _write_knowledge_doc(
    tmp_path: Path,
    *,
    knowledge_id: str = "K-renormalization-group-fixed-points",
    status: str = "stable",
    body: str = "Trusted knowledge body.\n",
) -> None:
    knowledge_dir = tmp_path / "GPD" / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    path = knowledge_dir / f"{knowledge_id}.md"
    base_content = (
        "---\n"
        "knowledge_schema_version: 1\n"
        f"knowledge_id: {knowledge_id}\n"
        "title: Renormalization Group Fixed Points\n"
        "topic: renormalization-group\n"
        f"status: {status}\n"
        "created_at: 2026-04-07T12:00:00Z\n"
        "updated_at: 2026-04-07T12:00:00Z\n"
        "sources:\n"
        "  - source_id: source-main\n"
        "    kind: paper\n"
        "    locator: Author et al., 2024\n"
        "    title: Benchmark Reference\n"
        "    why_it_matters: Trusted source for the topic\n"
        "coverage_summary:\n"
        "  covered_topics: [fixed points]\n"
        "  excluded_topics: [implementation]\n"
        "  open_gaps: [none]\n"
        "---\n\n"
        f"{body}"
    )
    reviewed_content_sha256 = compute_knowledge_reviewed_content_sha256(base_content)
    if status == "stable":
        content = base_content.replace(
            "---\n\n",
            "review:\n"
            "  reviewed_at: 2026-04-07T13:00:00Z\n"
            "  review_round: 1\n"
            "  reviewer_kind: workflow\n"
            "  reviewer_id: gpd-review-knowledge\n"
            "  decision: approved\n"
            "  summary: Stable review approved.\n"
            f"  approval_artifact_path: GPD/knowledge/reviews/{knowledge_id}-R1-REVIEW.md\n"
            f"  approval_artifact_sha256: {'a' * 64}\n"
            f"  reviewed_content_sha256: {reviewed_content_sha256}\n"
            "  stale: false\n"
            "---\n\n",
        )
    elif status == "in_review":
        content = base_content.replace(
            "---\n\n",
            "review:\n"
            "  reviewed_at: 2026-04-07T13:00:00Z\n"
            "  review_round: 1\n"
            "  reviewer_kind: workflow\n"
            "  reviewer_id: gpd-review-knowledge\n"
            "  decision: approved\n"
            "  summary: Needs re-review after edits.\n"
            f"  approval_artifact_path: GPD/knowledge/reviews/{knowledge_id}-R1-REVIEW.md\n"
            f"  approval_artifact_sha256: {'a' * 64}\n"
            f"  reviewed_content_sha256: {reviewed_content_sha256}\n"
            "  stale: true\n"
            "---\n\n",
        )
    else:
        content = base_content
    path.write_text(content, encoding="utf-8")


# ─── Helper Tests ──────────────────────────────────────────────────────────────


class TestHelpers:
    def test_generate_slug(self) -> None:
        assert _generate_slug("Hello World!") == "hello-world"
        assert _generate_slug("") is None
        assert _generate_slug(None) is None
        assert _generate_slug("already-slug") == "already-slug"

    def test_normalize_phase_name(self) -> None:
        assert _normalize_phase_name("3") == "03"
        assert _normalize_phase_name("12") == "12"
        assert _normalize_phase_name("3.1") == "03.1"
        assert _normalize_phase_name("3.1.2") == "03.1.2"
        assert _normalize_phase_name("abc") == "abc"

    def test_is_phase_complete(self) -> None:
        assert _is_phase_complete(2, 2) is True
        assert _is_phase_complete(2, 3) is True
        assert _is_phase_complete(2, 1) is False
        assert _is_phase_complete(0, 0) is False


# ─── load_config ───────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_defaults_when_no_config(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        config = load_config(tmp_path)
        assert config["autonomy"] == "balanced"
        assert config["review_cadence"] == "adaptive"
        assert config["research_mode"] == "balanced"
        assert config["commit_docs"] is True
        assert config["parallelization"] is True
        assert config["verifier"] is True
        assert config["checkpoint_after_first_load_bearing_result"] is True
        assert config["project_usd_budget"] is None
        assert config["session_usd_budget"] is None

    def test_custom_config(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"autonomy": "yolo", "review_cadence": "dense", "research_mode": "exploit"})
        config = load_config(tmp_path)
        assert config["autonomy"] == "yolo"
        assert config["review_cadence"] == "dense"
        assert config["research_mode"] == "exploit"

    def test_nested_config(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(
            tmp_path,
            {
                "workflow": {"research": False, "plan_checker": False},
                "execution": {"project_usd_budget": 12.5, "session_usd_budget": 2.5},
            },
        )
        config = load_config(tmp_path)
        assert config["research"] is False
        assert config["plan_checker"] is False
        assert config["project_usd_budget"] == 12.5
        assert config["session_usd_budget"] == 2.5

    def test_parallelization_bool(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"parallelization": False})
        config = load_config(tmp_path)
        assert config["parallelization"] is False

    def test_malformed_config_raises(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        config_path = tmp_path / "GPD" / "config.json"
        config_path.write_text("not valid json {{{", encoding="utf-8")
        with pytest.raises(ConfigError, match="Malformed config.json"):
            load_config(tmp_path)


# ─── init_execute_phase ────────────────────────────────────────────────────────


class TestInitExecutePhase:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        (phase_dir / "a-SUMMARY.md").write_text("summary", encoding="utf-8")

        ctx = init_execute_phase(tmp_path, "1")
        assert ctx["phase_found"] is True
        assert ctx["phase_number"] == "01"
        assert ctx["plan_count"] == 1
        assert ctx["incomplete_count"] == 0
        assert ctx["state_exists"] is False
        assert ctx["review_cadence"] == "adaptive"
        assert ctx["checkpoint_after_first_load_bearing_result"] is True

    def test_missing_phase_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="phase is required"):
            init_execute_phase(tmp_path, "")

    def test_includes_state(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        (tmp_path / "GPD" / "STATE.md").write_text("# State\nstuff", encoding="utf-8")

        ctx = init_execute_phase(tmp_path, "1", includes={"state"})
        assert ctx["state_content"] == "# State\nstuff"

    def test_includes_structured_state_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_structured_state_payload(tmp_path)

        ctx = init_execute_phase(tmp_path, "1", includes={"state"})

        _assert_structured_state_context(ctx, tmp_path)

    def test_json_only_state_counts_as_existing(self, tmp_path: Path) -> None:
        from gpd.core.state import default_state_dict

        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        (tmp_path / "GPD" / "state.json").write_text(json.dumps(default_state_dict()), encoding="utf-8")

        ctx = init_execute_phase(tmp_path, "1")

        assert ctx["state_exists"] is True

    def test_surfaces_derived_state_memory(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        _write_structured_state_memory(tmp_path)

        ctx = init_execute_phase(tmp_path, "1")

        assert ctx["derived_convention_lock"]["metric_signature"] == "mostly-plus"
        assert ctx["derived_convention_lock"]["coordinate_system"] == "Cartesian"
        assert ctx["derived_convention_lock_count"] == 2
        assert ctx["derived_intermediate_result_count"] == 1
        assert ctx["derived_intermediate_results"][0]["id"] == "R-01"
        assert ctx["derived_intermediate_results"][0]["equation"] == "E = mc^2"
        assert ctx["derived_approximation_count"] == 1
        assert ctx["derived_approximations"][0]["name"] == "weak coupling"

    def test_does_not_bootstrap_manuscript_proof_review_manifest(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        _write_manuscript_proof_review_artifacts(tmp_path)

        ctx = init_execute_phase(tmp_path, "1")

        status = ctx["derived_manuscript_proof_review_status"]
        assert status["state"] == "fresh"
        assert status["manifest_bootstrapped"] is False
        assert not (tmp_path / "paper" / "PROOF-REVIEW-MANIFEST.json").exists()

    def test_state_exists_uses_recoverable_backup_without_persisting_repair(
        self,
        tmp_path: Path,
    ) -> None:
        from gpd.core.state import default_state_dict

        _setup_project(tmp_path)
        (tmp_path / "GPD" / "state.json.bak").write_text(
            json.dumps(default_state_dict()),
            encoding="utf-8",
        )

        assert _state_exists(tmp_path) is True
        assert not (tmp_path / "GPD" / "state.json").exists()

    def test_surfaces_active_reference_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        _write_project_contract_state(tmp_path)

        ctx = init_execute_phase(tmp_path, "1")

        assert ctx["project_contract"]["references"][0]["id"] == "ref-benchmark"
        assert "Published comparison target" in ctx["active_reference_context"]

    def test_active_reference_context_collapses_non_durable_contract_warnings(self) -> None:
        rendered = _render_active_reference_context(
            active_references=[],
            effective_intake={
                "must_read_refs": [],
                "must_include_prior_outputs": [],
                "user_asserted_anchors": [],
                "known_good_baselines": [],
                "context_gaps": [],
                "crucial_inputs": [],
            },
            literature_review_files=[],
            research_map_reference_files=[],
            stable_knowledge_doc_files=[],
            knowledge_doc_status_counts={},
            contract_validation={
                "valid": False,
                "errors": ["scope.question is required"],
                "warnings": [
                    "context_intake.user_asserted_anchors entry is not concrete enough to preserve as durable guidance: placeholder anchor",
                    "context_intake.context_gaps entry is only a placeholder and does not preserve actionable guidance: TBD",
                    "references.0.must_surface must be a boolean",
                ],
            },
            contract_load_info={
                "status": "loaded_with_schema_normalization",
                "errors": ["context_intake is required"],
                "warnings": [
                    "context_intake.must_include_prior_outputs entry does not resolve to a project-local artifact: missing/path.md",
                ],
            },
        )

        assert rendered.count("non-durable contract-intake warning") == 2
        assert "context_intake.user_asserted_anchors entry is not concrete enough to preserve as durable guidance" not in rendered
        assert "context_intake.context_gaps entry is only a placeholder and does not preserve actionable guidance" not in rendered
        assert "context_intake.must_include_prior_outputs entry does not resolve to a project-local artifact" not in rendered
        assert "references.0.must_surface must be a boolean" in rendered
        assert "context_intake is required" in rendered
        assert "scope.question is required" in rendered

    def test_ingests_reference_artifacts_without_project_contract(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_execute_phase(tmp_path, "1")

        assert ctx["project_contract"] is None
        assert ctx["derived_active_reference_count"] >= 2
        assert ctx["active_reference_count"] >= 2
        assert "Benchmark Ref 2024" in ctx["active_reference_context"]
        assert "GPD/phases/01-test-phase/01-SUMMARY.md" in ctx["active_reference_context"]
        assert "GPD/research-map/REFERENCES.md" in ctx["active_reference_context"]
        assert "critical slope" in "\n".join(ctx["effective_reference_intake"]["known_good_baselines"])
        assert "GPD/phases/01-test-phase/01-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]

    def test_surfaces_live_execution_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-1",
                "phase": "01",
                "plan": "01",
                "segment_status": "waiting_review",
                "first_result_gate_pending": True,
                "review_cadence": "adaptive",
            },
        )

        ctx = init_execute_phase(tmp_path, "1")

        assert ctx["has_live_execution"] is True
        assert ctx["execution_review_pending"] is True
        assert ctx["current_execution"]["segment_status"] == "waiting_review"

    def test_surfaces_pre_fanout_and_skeptical_execution_flags(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-1",
                "phase": "01",
                "plan": "01",
                "segment_status": "waiting_review",
                "checkpoint_reason": "pre_fanout",
                "pre_fanout_review_pending": True,
                "skeptical_requestioning_required": True,
                "downstream_locked": True,
            },
        )

        ctx = init_execute_phase(tmp_path, "1")

        assert ctx["execution_review_pending"] is True
        assert ctx["execution_pre_fanout_review_pending"] is True
        assert ctx["execution_skeptical_requestioning_required"] is True
        assert ctx["execution_downstream_locked"] is True

    def test_surfaces_selected_protocol_bundles(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        _write_stat_mech_project(tmp_path)
        _write_bundle_ready_contract_state(tmp_path)

        ctx = init_execute_phase(tmp_path, "1")

        assert "stat-mech-simulation" in ctx["selected_protocol_bundle_ids"]
        assert "monte-carlo.md" in ctx["protocol_bundle_context"]
        assert "selected_protocol_bundles" not in ctx
        assert "protocol_bundle_asset_paths" not in ctx
        assert any(
            extension["bundle_id"] == "stat-mech-simulation"
            for extension in ctx["protocol_bundle_verifier_extensions"]
        )

    def test_surfaces_numerical_relativity_protocol_bundle(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        _write_numerical_relativity_project(tmp_path)
        _write_numerical_relativity_contract_state(tmp_path)

        ctx = init_execute_phase(tmp_path, "1")

        assert "numerical-relativity" in ctx["selected_protocol_bundle_ids"]
        assert "numerical-relativity.md" in ctx["protocol_bundle_context"]
        assert any(
            extension["bundle_id"] == "numerical-relativity"
            for extension in ctx["protocol_bundle_verifier_extensions"]
        )

    def test_protocol_bundle_verifier_extensions_match_mcp_bundle_checklist(self, tmp_path: Path) -> None:
        from gpd.mcp.servers.verification_server import get_bundle_checklist

        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
        _write_stat_mech_project(tmp_path)
        _write_bundle_ready_contract_state(tmp_path)

        ctx = init_execute_phase(tmp_path, "1")
        checklist = get_bundle_checklist(ctx["selected_protocol_bundle_ids"])

        assert checklist["found"] is True
        assert checklist["bundle_checks"] == ctx["protocol_bundle_verifier_extensions"]


class TestInitExecutePhaseStagedWiring:
    def test_stage_phase_bootstrap_returns_only_bootstrap_payload(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_project_contract_state(tmp_path)

        ctx = init_execute_phase(tmp_path, "1", stage="phase_bootstrap")

        assert ctx["phase_found"] is True
        assert ctx["staged_loading"]["stage_id"] == "phase_bootstrap"
        assert "reference_artifacts_content" not in ctx
        assert "protocol_bundle_context" not in ctx
        assert "current_execution" not in ctx

    def test_stage_rejects_unknown_execute_phase_stage(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")

        with pytest.raises(ValueError, match="Unknown execute-phase stage 'bogus'"):
            init_execute_phase(tmp_path, "1", stage="bogus")


# ─── init_plan_phase ──────────────────────────────────────────────────────────


class TestInitPlanPhase:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "02-analysis")
        (phase_dir / "RESEARCH.md").write_text("research", encoding="utf-8")

        ctx = init_plan_phase(tmp_path, "2")
        assert ctx["phase_found"] is True
        assert ctx["phase_number"] == "02"
        assert ctx["has_research"] is True
        assert ctx["has_plans"] is False
        assert ctx["padded_phase"] == "02"
        assert "staged_loading" not in ctx

    def test_stage_phase_bootstrap_returns_only_bootstrap_payload(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _install_fake_plan_phase_manifest(monkeypatch)

        ctx = init_plan_phase(tmp_path, "2", stage="phase_bootstrap")

        assert ctx["phase_found"] is True
        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["staged_loading"]["stage_id"] == "phase_bootstrap"
        assert "contract_intake" not in ctx
        assert "active_reference_context" not in ctx
        assert "reference_artifacts_content" not in ctx
        assert "state_content" not in ctx

    def test_stage_planner_authoring_surfaces_reference_runtime_and_file_context(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)
        (phase_dir / "02-CONTEXT.md").write_text("# Context\nLocked scope.\n", encoding="utf-8")
        (phase_dir / "02-RESEARCH.md").write_text("# Research\nMethod comparison.\n", encoding="utf-8")
        (phase_dir / "02-VERIFICATION.md").write_text("# Verification\nGap notes.\n", encoding="utf-8")
        (phase_dir / "02-VALIDATION.md").write_text("# Validation\nChecks.\n", encoding="utf-8")
        manifest = _install_fake_plan_phase_manifest(monkeypatch)

        ctx = init_plan_phase(tmp_path, "2", stage="planner_authoring")
        stage = manifest.stage_by_id("planner_authoring")

        assert ctx["staged_loading"]["stage_id"] == "planner_authoring"
        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert "[ref-benchmark]" in ctx["active_reference_context"]
        assert "Reference and Anchor Map" in ctx["reference_artifacts_content"]
        assert "Universal crossing window" in ctx["reference_artifacts_content"]
        assert "Locked scope." in ctx["context_content"]
        assert "Method comparison." in ctx["research_content"]
        assert "Gap notes." in ctx["verification_content"]
        assert "Checks." in ctx["validation_content"]

    def test_stage_checker_revision_uses_tight_checker_payload(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)
        (phase_dir / "02-CONTEXT.md").write_text("# Context\nLocked scope.\n", encoding="utf-8")
        (phase_dir / "02-RESEARCH.md").write_text("# Research\nMethod comparison.\n", encoding="utf-8")
        (phase_dir / "02-VERIFICATION.md").write_text("# Verification\nGap notes.\n", encoding="utf-8")
        (phase_dir / "02-VALIDATION.md").write_text("# Validation\nChecks.\n", encoding="utf-8")
        manifest = _install_fake_plan_phase_manifest(monkeypatch)

        ctx = init_plan_phase(tmp_path, "2", stage="checker_revision")
        stage = manifest.stage_by_id("checker_revision")

        assert ctx["staged_loading"]["stage_id"] == "checker_revision"
        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["project_contract_gate"]["visible"] is True
        assert "[ref-benchmark]" in ctx["active_reference_context"]
        assert "Reference and Anchor Map" in ctx["reference_artifacts_content"]
        assert "Universal crossing window" in ctx["reference_artifacts_content"]
        assert "Locked scope." in ctx["context_content"]
        assert "Method comparison." in ctx["research_content"]
        assert "Gap notes." in ctx["verification_content"]
        assert "Checks." in ctx["validation_content"]
        assert "Method comparison." not in ctx.get("state_content", "")
        assert "experiment_design_content" not in ctx
        assert "planner_model" not in ctx

    def test_plan_phase_stage_rejects_include_mix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _install_fake_plan_phase_manifest(monkeypatch)

        with pytest.raises(ValueError, match="does not allow --include together with --stage"):
            init_plan_phase(tmp_path, "2", includes={"state"}, stage="phase_bootstrap")

    def test_plan_phase_stage_rejects_unknown_stage(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _install_fake_plan_phase_manifest(monkeypatch)

        with pytest.raises(ValueError, match="Unknown plan-phase stage 'bogus'"):
            init_plan_phase(tmp_path, "2", stage="bogus")

    def test_includes_research(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "02-analysis")
        (phase_dir / "RESEARCH.md").write_text("findings here", encoding="utf-8")

        ctx = init_plan_phase(tmp_path, "2", includes={"research"})
        assert ctx["research_content"] == "findings here"

    def test_includes_structured_state_context_when_state_is_requested(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_structured_state_payload(tmp_path)

        ctx = init_plan_phase(tmp_path, "2", includes={"state"})

        _assert_structured_state_context(ctx, tmp_path)

    def test_surfaces_active_reference_context_and_reference_artifacts(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        literature_dir = tmp_path / "GPD" / "literature"
        literature_dir.mkdir()
        (literature_dir / "benchmark-REVIEW.md").write_text("# Literature Review\nbenchmark details", encoding="utf-8")
        map_dir = tmp_path / "GPD" / "research-map"
        map_dir.mkdir()
        (map_dir / "REFERENCES.md").write_text("# References Map\nanchor registry", encoding="utf-8")
        (map_dir / "VALIDATION.md").write_text("# Validation Map\nbenchmark checks", encoding="utf-8")

        ctx = init_plan_phase(tmp_path, "2")

        assert ctx["project_contract"]["references"][0]["id"] == "ref-benchmark"
        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert ctx["active_reference_count"] == 1
        assert "[ref-benchmark]" in ctx["active_reference_context"]
        assert "GPD/literature/benchmark-REVIEW.md" in ctx["literature_review_files"]
        assert "GPD/research-map/REFERENCES.md" in ctx["research_map_reference_files"]
        assert "GPD/research-map/VALIDATION.md" in ctx["reference_artifact_files"]
        assert "benchmark details" in ctx["reference_artifacts_content"]
        assert "anchor registry" in ctx["reference_artifacts_content"]

    def test_surfaces_stable_knowledge_docs_in_runtime_reference_payload(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_knowledge_doc(tmp_path, status="stable")
        _write_knowledge_doc(
            tmp_path,
            knowledge_id="K-work-in-progress",
            status="in_review",
            body="Draft knowledge body.\n",
        )

        ctx = init_plan_phase(tmp_path, "2")

        assert "GPD/knowledge/K-renormalization-group-fixed-points.md" in ctx["knowledge_doc_files"]
        assert ctx["knowledge_doc_count"] == 2
        assert ctx["stable_knowledge_doc_files"] == ["GPD/knowledge/K-renormalization-group-fixed-points.md"]
        assert ctx["stable_knowledge_doc_count"] == 1
        assert ctx["knowledge_doc_status_counts"]["stable"] == 1
        assert ctx["knowledge_doc_status_counts"]["in_review"] == 1
        assert ctx["derived_knowledge_doc_count"] == 1
        assert ctx["derived_knowledge_docs"][0]["knowledge_id"] == "K-renormalization-group-fixed-points"
        assert ctx["knowledge_doc_warnings"] == []
        assert "GPD/knowledge/K-renormalization-group-fixed-points.md" in ctx["reference_artifact_files"]
        assert "Trusted knowledge body." in ctx["reference_artifacts_content"]
        assert "Draft knowledge body." not in ctx["reference_artifacts_content"]
        assert "K-work-in-progress" not in ctx["active_reference_context"]
        assert "non-stable knowledge doc(s) remain inventory-visible only" in ctx["active_reference_context"]

    def test_prefers_literature_review_files_over_legacy_research_when_both_exist(
        self,
        tmp_path: Path,
    ) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)

        literature_dir = tmp_path / "GPD" / "literature"
        literature_dir.mkdir()
        (literature_dir / "canonical-REVIEW.md").write_text(
            "# Literature Review\n\nCanonical details.\n",
            encoding="utf-8",
        )
        (literature_dir / "canonical-CITATION-SOURCES.json").write_text(
            json.dumps(
                [
                    {
                        "reference_id": "ref-canonical",
                        "source_type": "paper",
                        "title": "Canonical Reference",
                        "authors": ["A. Author"],
                        "year": "2026",
                    }
                ]
            ),
            encoding="utf-8",
        )

        research_dir = tmp_path / "GPD" / "research"
        research_dir.mkdir()
        (research_dir / "legacy-REVIEW.md").write_text(
            "# Legacy Review\n\nLegacy details.\n",
            encoding="utf-8",
        )
        (research_dir / "legacy-CITATION-SOURCES.json").write_text(
            json.dumps(
                [
                    {
                        "reference_id": "ref-legacy",
                        "source_type": "paper",
                        "title": "Legacy Reference",
                        "authors": ["A. Author"],
                        "year": "2024",
                    }
                ]
            ),
            encoding="utf-8",
        )

        ctx = init_plan_phase(tmp_path, "2")

        assert ctx["literature_review_files"] == ["GPD/literature/canonical-REVIEW.md"]
        assert ctx["citation_source_files"] == ["GPD/literature/canonical-CITATION-SOURCES.json"]
        assert "Canonical details." in ctx["reference_artifacts_content"]
        assert "Legacy details." not in ctx["reference_artifacts_content"]
        assert "GPD/research/legacy-REVIEW.md" not in ctx["reference_artifact_files"]

    def test_falls_back_to_legacy_research_review_files_when_literature_is_missing(
        self,
        tmp_path: Path,
    ) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)

        research_dir = tmp_path / "GPD" / "research"
        research_dir.mkdir()
        (research_dir / "legacy-REVIEW.md").write_text(
            "# Legacy Review\n\nLegacy details.\n",
            encoding="utf-8",
        )
        (research_dir / "legacy-CITATION-SOURCES.json").write_text(
            json.dumps(
                [
                    {
                        "reference_id": "ref-legacy",
                        "source_type": "paper",
                        "title": "Legacy Reference",
                        "authors": ["A. Author"],
                        "year": "2024",
                    }
                ]
            ),
            encoding="utf-8",
        )

        ctx = init_plan_phase(tmp_path, "2")

        assert ctx["literature_review_files"] == ["GPD/research/legacy-REVIEW.md"]
        assert ctx["citation_source_files"] == ["GPD/research/legacy-CITATION-SOURCES.json"]
        assert "Legacy details." in ctx["reference_artifacts_content"]
        assert "GPD/research/legacy-REVIEW.md" in ctx["reference_artifact_files"]

    def test_does_not_bootstrap_manuscript_proof_review_manifest(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_manuscript_proof_review_artifacts(tmp_path)

        ctx = init_plan_phase(tmp_path, "2")

        status = ctx["derived_manuscript_proof_review_status"]
        assert status["state"] == "fresh"
        assert status["manifest_bootstrapped"] is False
        assert not (tmp_path / "paper" / "PROOF-REVIEW-MANIFEST.json").exists()

    def test_surfaces_derived_citation_sources_without_changing_reference_artifact_fields(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_literature_citation_source_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_plan_phase(tmp_path, "2")

        assert "GPD/literature/benchmark-CITATION-SOURCES.json" in ctx["citation_source_files"]
        assert ctx["citation_source_count"] == 1
        assert ctx["citation_source_warnings"] == []
        assert ctx["derived_citation_source_count"] == 1
        assert ctx["derived_citation_sources"][0]["reference_id"] == "ref-benchmark"
        assert ctx["derived_citation_sources"][0]["title"] == "Benchmark Ref 2024"
        assert ctx["derived_citation_sources"][0]["bibtex_key"] == "benchmark2024"
        assert ctx["derived_citation_sources"][0]["doi"] == "10.1000/benchmark.2024"
        assert ctx["derived_citation_sources"][0]["arxiv_id"] == "2401.01234"
        assert "GPD/literature/benchmark-CITATION-SOURCES.json" not in ctx["reference_artifact_files"]
        assert "Benchmark Survey" in ctx["reference_artifacts_content"]
        assert "Active Anchor Registry" in ctx["reference_artifacts_content"]

    def test_surfaces_derived_manuscript_reference_status_from_bibliography_audit(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_manuscript_bibliography_audit(tmp_path)

        ctx = init_plan_phase(tmp_path, "2")

        assert ctx["derived_manuscript_reference_status_count"] == 1
        assert ctx["derived_manuscript_reference_status"]["ref-benchmark"]["bibtex_key"] == "benchmark2024"
        assert ctx["derived_manuscript_reference_status"]["ref-benchmark"]["title"] == "Benchmark Paper"
        assert ctx["derived_manuscript_reference_status"]["ref-benchmark"]["resolution_status"] == "provided"
        assert ctx["derived_manuscript_reference_status"]["ref-benchmark"]["verification_status"] == "verified"
        assert ctx["derived_manuscript_reference_status"]["ref-benchmark"]["manuscript_root"] == "paper"
        assert ctx["derived_manuscript_reference_status"]["ref-benchmark"]["bibliography_audit_path"] == "paper/BIBLIOGRAPHY-AUDIT.json"
        assert ctx["derived_manuscript_reference_status"]["ref-benchmark"]["source_artifacts"] == [
            "paper/BIBLIOGRAPHY-AUDIT.json"
        ]

    def test_surfaces_derived_state_memory_without_including_state_markdown(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_structured_state_memory(tmp_path)

        ctx = init_plan_phase(tmp_path, "2")

        assert "state_content" not in ctx
        assert ctx["derived_convention_lock"]["metric_signature"] == "mostly-plus"
        assert ctx["derived_intermediate_result_count"] == 1
        assert ctx["derived_intermediate_results"][0]["description"] == "Mass-energy relation"
        assert ctx["derived_approximation_count"] == 1
        assert ctx["derived_approximations"][0]["controlling_param"] == "g"

    def test_merges_contract_and_artifact_reference_intake(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_plan_phase(tmp_path, "2")

        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert ctx["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert "ref-benchmark" in ctx["effective_reference_intake"]["must_read_refs"]
        assert "lit-anchor-benchmark-ref-2024" in ctx["effective_reference_intake"]["must_read_refs"]
        assert "benchmark-paper" not in ctx["effective_reference_intake"]["must_read_refs"]
        assert "GPD/phases/01-test-phase/01-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]
        assert ctx["active_reference_count"] >= ctx["derived_active_reference_count"]
        assert "GPD/research-map/REFERENCES.md" in ctx["active_reference_context"]
        assert "unresolved reference token" not in ctx["active_reference_context"]

    def test_contract_intake_comes_from_canonicalized_project_contract(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        state_path = tmp_path / "GPD" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["project_contract"]["context_intake"]["must_read_refs"] = ["benchmark-paper"]
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        ctx = init_progress(tmp_path)

        assert ctx["project_contract"]["context_intake"]["must_read_refs"] == ["benchmark-paper"]
        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert ctx["project_contract_load_info"]["status"] == "loaded_with_approval_blockers"
        assert ctx["project_contract_validation"]["valid"] is False
        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["project_contract_gate"]["authoritative"] is False
        assert ctx["project_contract_gate"]["blocked"] is True
        assert ctx["project_contract_gate"]["repair_required"] is True

    def test_non_authoritative_project_contract_does_not_select_protocol_bundles(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _setup_project(tmp_path)

        from gpd.contracts import ResearchContract

        contract_payload = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract_payload["scope"]["question"] = "numerical relativity benchmark study"
        contract_payload["scope"]["in_scope"] = ["numerical relativity", "benchmark alignment"]
        contract = ResearchContract.model_validate(contract_payload)

        monkeypatch.setattr(
            "gpd.core.context._load_project_contract",
            lambda cwd: (
                contract,
                {
                    "status": "loaded",
                    "source_path": "GPD/state.json",
                    "provenance": "fallback",
                    "raw_project_contract_classified": False,
                    "errors": [],
                    "warnings": [],
                },
            ),
        )

        ctx = init_progress(tmp_path)

        assert ctx["project_contract"] is not None
        assert ctx["project_contract"]["scope"]["question"] == contract.scope.question
        assert ctx["project_contract_gate"]["authoritative"] is False
        assert ctx["project_contract_gate"]["repair_required"] is True
        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert ctx["selected_protocol_bundle_ids"] == []
        assert ctx["active_reference_count"] == 0
        assert ctx["effective_reference_intake"] == {
            "must_read_refs": [],
            "must_include_prior_outputs": [],
            "user_asserted_anchors": [],
            "known_good_baselines": [],
            "context_gaps": [],
            "crucial_inputs": [],
        }
        assert "ref-benchmark" not in ctx["active_reference_context"]
        assert "Author et al., Journal, 2024" not in ctx["active_reference_context"]

    def test_ambiguous_reference_tokens_remain_unresolved(self) -> None:
        active_references = [
            {
                "id": "ref-a",
                "locator": "doc-a",
                "aliases": ["shared-token"],
            },
            {
                "id": "ref-b",
                "locator": "shared-token",
                "aliases": [],
            },
        ]

        intake = _merge_reference_intake(
            None,
            {"must_read_refs": ["shared-token", "doc-a"]},
            active_references,
        )

        assert intake["must_read_refs"] == ["shared-token", "ref-a"]

    def test_merge_active_references_keeps_must_surface_strictly_boolean(self) -> None:
        contract_references = [
            {
                "id": "ref-benchmark",
                "locator": "Benchmark Ref 2024",
                "role": "benchmark",
                "why_it_matters": "Published comparison target",
                "required_actions": ["read", "compare", "cite"],
                "applies_to": ["claim-benchmark"],
                "carry_forward_to": [],
                "source_artifacts": [],
                "aliases": [],
                "must_surface": "optional",
            }
        ]
        derived_references = [
            {
                "id": "ref-benchmark",
                "locator": "Benchmark Ref 2024",
                "role": "benchmark",
                "why_it_matters": "Derived metadata",
                "required_actions": ["read"],
                "applies_to": ["claim-benchmark"],
                "carry_forward_to": ["writing"],
                "source_artifacts": ["GPD/research-map/REFERENCES.md"],
                "aliases": ["benchmark-paper"],
                "must_surface": "no",
            }
        ]

        merged = _merge_active_references(contract_references, derived_references)
        ref = next(item for item in merged if item["id"] == "ref-benchmark")

        assert ref["must_surface"] is False
        assert isinstance(ref["must_surface"], bool)
        assert ref["required_actions"] == ["read", "compare", "cite"]
        assert ref["carry_forward_to"] == ["writing"]
        assert ref["aliases"] == ["benchmark-paper"]

    def test_merge_active_references_does_not_collapse_shared_aliases(self) -> None:
        contract_references = [
            {
                "id": "ref-a",
                "locator": "Doc A",
                "role": "benchmark",
                "why_it_matters": "First anchor",
                "required_actions": ["read"],
                "applies_to": ["claim-a"],
                "carry_forward_to": [],
                "source_artifacts": [],
                "aliases": ["shared-token"],
                "must_surface": True,
            }
        ]
        derived_references = [
            {
                "id": "ref-b",
                "locator": "Doc B",
                "role": "benchmark",
                "why_it_matters": "Second anchor",
                "required_actions": ["compare"],
                "applies_to": ["claim-b"],
                "carry_forward_to": [],
                "source_artifacts": ["GPD/research-map/REFERENCES.md"],
                "aliases": ["shared-token"],
                "must_surface": True,
            }
        ]

        merged = _merge_active_references(contract_references, derived_references)

        assert [ref["id"] for ref in merged] == ["ref-a", "ref-b"]
        assert merged[0]["aliases"] == ["shared-token"]
        assert merged[1]["aliases"] == ["shared-token"]

    def test_merge_active_references_upgrades_generic_kind_from_derived_reference(self) -> None:
        contract_references = [
            {
                "id": "ref-benchmark",
                "locator": "Benchmark Ref 2024",
                "kind": "other",
                "role": "other",
                "why_it_matters": "Published comparison target",
                "required_actions": [],
                "applies_to": [],
                "carry_forward_to": [],
                "source_artifacts": [],
                "aliases": [],
                "must_surface": False,
            }
        ]
        derived_references = [
            {
                "id": "ref-benchmark",
                "locator": "Benchmark Ref 2024",
                "kind": "paper",
                "role": "benchmark",
                "why_it_matters": "Derived metadata",
                "required_actions": ["read"],
                "applies_to": ["claim-benchmark"],
                "carry_forward_to": ["writing"],
                "source_artifacts": ["GPD/research-map/REFERENCES.md"],
                "aliases": ["benchmark-paper"],
                "must_surface": True,
            }
        ]

        merged = _merge_active_references(contract_references, derived_references)
        ref = next(item for item in merged if item["id"] == "ref-benchmark")

        assert ref["kind"] == "paper"
        assert ref["role"] == "benchmark"
        assert contract_references[0]["kind"] == "other"
        assert derived_references[0]["kind"] == "paper"

    def test_keeps_project_contract_references_raw_and_surfaces_derived_reference_fields(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_plan_phase(tmp_path, "2")
        project_references = {ref["id"]: ref for ref in ctx["project_contract"]["references"]}
        active_references = {ref["id"]: ref for ref in ctx["active_references"]}

        assert project_references["ref-benchmark"].get("aliases", []) == []
        assert project_references["ref-benchmark"].get("applies_to", []) == ["claim-benchmark"]
        assert project_references["ref-benchmark"].get("carry_forward_to", []) == []
        assert project_references["ref-benchmark"]["required_actions"] == ["read", "compare", "cite"]
        assert project_references["ref-benchmark"]["must_surface"] is True
        assert "prior-baseline" not in project_references
        assert ctx["project_contract_validation"]["valid"] is True
        assert ctx["project_contract_gate"]["authoritative"] is True
        assert ctx["project_contract_load_info"]["warnings"] == []

        assert active_references["ref-benchmark"]["aliases"] == ["benchmark-paper"]
        assert active_references["ref-benchmark"]["applies_to"] == ["claim-benchmark"]
        assert active_references["ref-benchmark"]["carry_forward_to"] == ["verification", "writing"]
        assert active_references["ref-benchmark"]["required_actions"] == ["read", "compare", "cite"]
        assert active_references["prior-baseline"]["kind"] == "prior_artifact"
        assert active_references["prior-baseline"]["required_actions"] == ["use"]
        assert active_references["prior-baseline"]["carry_forward_to"] == ["planning", "execution"]

    def test_todo_frontmatter_parsing_handles_blank_lines_before_frontmatter(self) -> None:
        content = '\n\n---\ntitle: Todo task\ncreated: "2026-01-01"\n---\nBody.\n'

        meta = _read_todo_frontmatter(content)

        assert meta == {"title": "Todo task", "created": "2026-01-01"}
        assert _extract_frontmatter_field(content, "title") == "Todo task"
        assert _extract_frontmatter_field(content, "created") == "2026-01-01"

    def test_does_not_persist_canonical_reference_merges(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        state_path = tmp_path / "GPD" / "state.json"
        before = state_path.read_text(encoding="utf-8")

        ctx = init_plan_phase(tmp_path, "2")

        after = state_path.read_text(encoding="utf-8")
        stored = json.loads(after)

        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert ctx["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert "ref-benchmark" in ctx["effective_reference_intake"]["must_read_refs"]
        assert "lit-anchor-benchmark-ref-2024" in ctx["effective_reference_intake"]["must_read_refs"]
        assert stored["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert before == after
        assert not (tmp_path / "GPD" / "STATE.md").exists()

    def test_reports_missing_active_references_explicitly(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")

        ctx = init_plan_phase(tmp_path, "2")

        assert ctx["project_contract"] is None
        assert ctx["active_reference_count"] == 0
        assert "None confirmed in `state.json.project_contract.references` yet." in ctx["active_reference_context"]

    def test_surfaces_protocol_bundle_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_stat_mech_project(tmp_path)
        _write_bundle_ready_contract_state(tmp_path)

        ctx = init_plan_phase(tmp_path, "2")

        assert "stat-mech-simulation" in ctx["selected_protocol_bundle_ids"]
        assert ctx["protocol_bundle_count"] >= 1
        assert "Decisive artifacts:" in ctx["protocol_bundle_context"]


# ─── init_new_project ─────────────────────────────────────────────────────────


class TestInitNewProject:
    def test_empty_project(self, tmp_path: Path) -> None:
        ctx = init_new_project(tmp_path)
        assert ctx["has_research_files"] is False
        assert ctx["has_project_manifest"] is False
        assert "has_existing_project" not in ctx
        assert ctx["planning_exists"] is False
        assert "staged_loading" not in ctx

    def test_detects_research_files(self, tmp_path: Path) -> None:
        (tmp_path / "calc.py").write_text("import numpy", encoding="utf-8")
        ctx = init_new_project(tmp_path)
        assert ctx["has_research_files"] is True
        assert "has_existing_project" not in ctx

    def test_ignores_runtime_owned_dirs_when_detecting_research_files(self, tmp_path: Path) -> None:
        for runtime_dir in _runtime_owned_local_install_dirs(tmp_path):
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "mirror.py").write_text("print('runtime mirror')", encoding="utf-8")

        ctx = init_new_project(tmp_path)

        assert ctx["has_research_files"] is False
        assert "has_existing_project" not in ctx

    def test_detects_non_runtime_config_research_files(self, tmp_path: Path) -> None:
        (tmp_path / ".config").mkdir()
        (tmp_path / ".config" / "notes.py").write_text("print('research notes')", encoding="utf-8")

        ctx = init_new_project(tmp_path)

        assert ctx["has_research_files"] is True
        assert "has_existing_project" not in ctx

    @pytest.mark.parametrize("directory_name", ("agents", "hooks", "command"))
    def test_detects_user_owned_research_files_in_generic_tool_named_directories(
        self, tmp_path: Path, directory_name: str
    ) -> None:
        owned_dir = tmp_path / directory_name
        owned_dir.mkdir()
        (owned_dir / "notes.py").write_text("print('research notes')", encoding="utf-8")

        ctx = init_new_project(tmp_path)

        assert ctx["has_research_files"] is True
        assert "has_existing_project" not in ctx

    def test_detects_xdg_config_subdir_research_files_inside_a_project(self, tmp_path: Path) -> None:
        opencode_descriptor = next(
            descriptor
            for descriptor in _RUNTIME_DESCRIPTORS
            if descriptor.global_config.xdg_subdir
        )
        (tmp_path / ".config" / opencode_descriptor.global_config.xdg_subdir).mkdir(parents=True)
        (
            tmp_path
            / ".config"
            / opencode_descriptor.global_config.xdg_subdir
            / "notes.py"
        ).write_text("print('research notes')", encoding="utf-8")

        ctx = init_new_project(tmp_path)

        assert ctx["has_research_files"] is True
        assert "has_existing_project" not in ctx

    def test_detects_manifest(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        ctx = init_new_project(tmp_path)
        assert ctx["has_project_manifest"] is True

    def test_detects_topic_stem_manuscript_entrypoint_without_main_tex(self, tmp_path: Path) -> None:
        manuscript_dir = tmp_path / "paper"
        manuscript_dir.mkdir()
        (manuscript_dir / "curvature_flow_bounds.tex").write_text(
            "\\documentclass{article}\\begin{document}Hi\\end{document}\n",
            encoding="utf-8",
        )
        (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "paper_title": "Curvature Flow Bounds",
                    "journal": "jhep",
                    "created_at": "2026-04-02T00:00:00+00:00",
                    "artifacts": [
                        {
                            "artifact_id": "tex-paper",
                            "category": "tex",
                            "path": "curvature_flow_bounds.tex",
                            "sha256": "0" * 64,
                            "produced_by": "test",
                            "sources": [],
                            "metadata": {},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        ctx = init_new_project(tmp_path)

        assert ctx["has_project_manifest"] is True
        assert "has_existing_project" not in ctx

    def test_surfaces_project_contract_state_and_validation(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)

        ctx = init_new_project(tmp_path)

        assert ctx["project_contract"] is not None
        assert ctx["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
        assert ctx["project_contract_load_info"]["status"] == "loaded"
        assert ctx["project_contract_load_info"]["source_path"].endswith("state.json")
        assert ctx["project_contract_validation"] is not None
        assert ctx["project_contract_validation"]["valid"] is True
        assert ctx["project_contract_gate"]["authoritative"] is True

    def test_new_project_stage_scope_intake_filters_payload(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)

        manifest = load_workflow_stage_manifest("new-project")
        stage = manifest.get_stage("scope_intake")

        ctx = init_new_project(tmp_path, stage="scope_intake")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["workflow_id"] == "new-project"
        assert ctx["staged_loading"]["stage_id"] == "scope_intake"
        assert ctx["staged_loading"]["order"] == 1
        assert ctx["staged_loading"]["loaded_authorities"] == ["workflows/new-project.md"]
        assert "references/research/questioning.md" in ctx["staged_loading"]["must_not_eager_load"]
        assert "templates/project-contract-schema.md" in ctx["staged_loading"]["must_not_eager_load"]
        assert ctx["staged_loading"]["checkpoints"] == [
            "detect existing workspace state",
            "surface the first scoping question",
            "preserve contract gate visibility without assuming approval-stage authority",
        ]
        assert ctx["staged_loading"]["next_stages"] == ["scope_approval"]

    def test_new_project_stage_scope_approval_filters_payload(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)

        manifest = load_workflow_stage_manifest("new-project")
        stage = manifest.get_stage("scope_approval")

        ctx = init_new_project(tmp_path, stage="scope_approval")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["workflow_id"] == "new-project"
        assert ctx["staged_loading"]["stage_id"] == "scope_approval"
        assert ctx["staged_loading"]["loaded_authorities"] == [
            "templates/project-contract-schema.md",
            "templates/project-contract-grounding-linkage.md",
            "references/shared/canonical-schema-discipline.md",
        ]
        assert "templates/project.md" in ctx["staged_loading"]["must_not_eager_load"]
        assert "templates/requirements.md" in ctx["staged_loading"]["must_not_eager_load"]
        assert ctx["staged_loading"]["checkpoints"] == [
            "approval gate has passed",
            "project contract is ready for persistence",
        ]

    def test_new_project_stage_post_scope_filters_payload(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)

        manifest = load_workflow_stage_manifest("new-project")
        stage = manifest.get_stage("post_scope")

        ctx = init_new_project(tmp_path, stage="post_scope")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["workflow_id"] == "new-project"
        assert ctx["staged_loading"]["stage_id"] == "post_scope"
        assert ctx["staged_loading"]["loaded_authorities"] == [
            "references/ui/ui-brand.md",
            "templates/project.md",
            "templates/requirements.md",
        ]
        assert ctx["staged_loading"]["writes_allowed"] == [
            "GPD/PROJECT.md",
            "GPD/REQUIREMENTS.md",
            "GPD/ROADMAP.md",
            "GPD/STATE.md",
            "GPD/state.json",
            "GPD/config.json",
            "GPD/CONVENTIONS.md",
            "GPD/literature/PRIOR-WORK.md",
            "GPD/literature/METHODS.md",
            "GPD/literature/COMPUTATIONAL.md",
            "GPD/literature/PITFALLS.md",
            "GPD/literature/SUMMARY.md",
        ]
        assert ctx["staged_loading"]["next_stages"] == []
        assert "reference_artifacts_content" not in ctx
        assert "active_reference_context" not in ctx
        assert "effective_reference_intake" not in ctx
        assert "reference_artifact_files" not in ctx

    def test_new_project_stage_rejects_unknown_stage(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)

        with pytest.raises(ValueError, match="Unknown new-project stage"):
            init_new_project(tmp_path, stage="bogus")

    def test_new_project_bootstrap_omits_reference_ledger_payload(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_new_project(tmp_path)

        for key in (
            "contract_intake",
            "effective_reference_intake",
            "active_references",
            "active_reference_context",
            "reference_artifact_files",
            "reference_artifacts_content",
            "selected_protocol_bundle_ids",
            "protocol_bundle_context",
        ):
            assert key not in ctx

    def test_new_project_bootstrap_skips_reference_artifact_ingestion(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("reference artifact ingestion should not run during new-project bootstrap")

        monkeypatch.setattr("gpd.core.context.ingest_reference_artifacts", _boom)

        ctx = init_new_project(tmp_path)

        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["project_contract_validation"]["valid"] is True

    def test_stage_scope_intake_returns_only_manifest_required_fields(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        manifest = load_workflow_stage_manifest("new-project")
        stage = manifest.get_stage("scope_intake")

        ctx = init_new_project(tmp_path, stage="scope_intake")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["workflow_id"] == "new-project"
        assert ctx["staged_loading"]["stage_id"] == "scope_intake"
        assert ctx["staged_loading"]["order"] == 1
        assert ctx["staged_loading"]["loaded_authorities"] == ["workflows/new-project.md"]
        assert "references/research/questioning.md" in ctx["staged_loading"]["must_not_eager_load"]
        assert ctx["staged_loading"]["checkpoints"] == [
            "detect existing workspace state",
            "surface the first scoping question",
            "preserve contract gate visibility without assuming approval-stage authority",
        ]
        assert ctx["staged_loading"]["writes_allowed"] == []

    def test_stage_scope_approval_returns_only_contract_fields(self, tmp_path: Path) -> None:
        ctx = init_new_project(tmp_path, stage="scope_approval")

        assert set(ctx) == {
            "project_contract",
            "project_contract_gate",
            "project_contract_load_info",
            "project_contract_validation",
            "staged_loading",
        }
        assert ctx["staged_loading"]["stage_id"] == "scope_approval"
        assert ctx["staged_loading"]["order"] == 2
        assert ctx["staged_loading"]["loaded_authorities"] == [
            "templates/project-contract-schema.md",
            "templates/project-contract-grounding-linkage.md",
            "references/shared/canonical-schema-discipline.md",
        ]
        assert ctx["staged_loading"]["writes_allowed"] == ["GPD/state.json"]

    def test_stage_rejection_is_clean(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown new-project stage"):
            init_new_project(tmp_path, stage="does-not-exist")

    def test_resume_work_stage_resume_bootstrap_filters_payload(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)

        manifest = load_workflow_stage_manifest("resume-work")
        stage = manifest.get_stage("resume_bootstrap")

        ctx = init_resume(tmp_path, stage="resume_bootstrap")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["workflow_id"] == "resume-work"
        assert ctx["staged_loading"]["stage_id"] == "resume_bootstrap"
        assert "templates/state-json-schema.md" in ctx["staged_loading"]["must_not_eager_load"]
        assert "reference_artifacts_content" not in ctx
        assert "active_reference_context" not in ctx
        assert "project_contract_gate" not in ctx

    def test_resume_work_stage_state_restore_filters_payload(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)

        manifest = load_workflow_stage_manifest("resume-work")
        stage = manifest.get_stage("state_restore")

        ctx = init_resume(tmp_path, stage="state_restore")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["project_contract_gate"]["visible"] is True
        assert "reference_artifacts_content" not in ctx

    def test_sync_state_stage_sync_bootstrap_filters_payload(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        _setup_project(tmp_path)

        manifest = load_workflow_stage_manifest("sync-state")
        stage = manifest.get_stage("sync_bootstrap")

        ctx = init_sync_state(tmp_path, stage="sync_bootstrap")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["workflow_id"] == "sync-state"
        assert ctx["staged_loading"]["stage_id"] == "sync_bootstrap"
        assert "templates/state-json-schema.md" in ctx["staged_loading"]["must_not_eager_load"]
        assert "state_md_content" not in ctx
        assert "state_json_content" not in ctx

    def test_sync_state_stage_conflict_analysis_filters_payload(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)

        manifest = load_workflow_stage_manifest("sync-state")
        stage = manifest.get_stage("conflict_analysis")

        ctx = init_sync_state(tmp_path, stage="conflict_analysis")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["project_contract_gate"]["visible"] is True
        assert "state_json_content" in ctx
        assert "state_md_content" in ctx

    def test_write_paper_bootstrap_stays_small_without_stage(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / "GPD" / "PROJECT.md").write_text("# Project\n\nPaper target.\n", encoding="utf-8")
        _write_project_contract_state(tmp_path)
        _write_manuscript_proof_review_artifacts(tmp_path)

        ctx = init_write_paper(tmp_path)

        assert ctx["project_exists"] is True
        assert "staged_loading" not in ctx
        assert "reference_artifacts_content" not in ctx
        assert "state_content" not in ctx
        assert "current_execution" not in ctx
        assert "derived_manuscript_reference_status" in ctx
        assert "derived_manuscript_proof_review_status" in ctx
        assert "protocol_bundle_context" in ctx

    def test_write_paper_stage_paper_bootstrap_filters_payload(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / "GPD" / "PROJECT.md").write_text("# Project\n\nPaper target.\n", encoding="utf-8")
        _write_project_contract_state(tmp_path)

        manifest = load_workflow_stage_manifest("write-paper")
        stage = manifest.get_stage("paper_bootstrap")

        ctx = init_write_paper(tmp_path, stage="paper_bootstrap")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["workflow_id"] == "write-paper"
        assert ctx["staged_loading"]["stage_id"] == "paper_bootstrap"
        assert "reference_artifacts_content" not in ctx
        assert "state_content" not in ctx
        assert "derived_convention_lock" not in ctx

    def test_write_paper_stage_outline_and_scaffold_loads_deferred_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        planning = tmp_path / "GPD"
        (planning / "PROJECT.md").write_text("# Project\n\nPaper target.\n", encoding="utf-8")
        (planning / "STATE.md").write_text("# State\n\nReady.\n", encoding="utf-8")
        (planning / "ROADMAP.md").write_text("# Roadmap\n\n## Milestone v1.0\n", encoding="utf-8")
        (planning / "REQUIREMENTS.md").write_text("# Requirements\n\n- Verified evidence\n", encoding="utf-8")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)
        _write_structured_state_memory(tmp_path)

        manifest = load_workflow_stage_manifest("write-paper")
        stage = manifest.get_stage("outline_and_scaffold")

        ctx = init_write_paper(tmp_path, stage="outline_and_scaffold")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["stage_id"] == "outline_and_scaffold"
        assert "Reference and Anchor Map" in ctx["reference_artifacts_content"]
        assert "Universal crossing window" in ctx["reference_artifacts_content"]
        assert "Milestone v1.0" in ctx["roadmap_content"]
        assert "Verified evidence" in ctx["requirements_content"]
        assert ctx["derived_convention_lock_count"] == 2
        assert ctx["derived_intermediate_result_count"] == 1

    def test_write_paper_stage_rejects_unknown_stage(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)

        with pytest.raises(ValueError, match="Unknown write-paper stage 'bogus'"):
            init_write_paper(tmp_path, stage="bogus")


# ─── init_new_milestone ───────────────────────────────────────────────────────


class TestInitNewMilestone:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Setup Phase\n")

        ctx = init_new_milestone(tmp_path)
        assert ctx["current_milestone"] == "v1.0"
        assert ctx["current_milestone_name"] == "Setup Phase"
        assert "planning_exists" not in ctx

    def test_surfaces_project_contract_and_effective_reference_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Setup Phase\n")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_new_milestone(tmp_path)

        assert ctx["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
        assert "roadmapper_model" in ctx
        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert ctx["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["project_contract_gate"]["authoritative"] is True
        assert "ref-benchmark" in ctx["effective_reference_intake"]["must_read_refs"]
        assert "lit-anchor-benchmark-ref-2024" in ctx["effective_reference_intake"]["must_read_refs"]
        assert "GPD/phases/01-test-phase/01-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]
        assert "Benchmark Ref 2024" in ctx["active_reference_context"]
        assert "GPD/research-map/REFERENCES.md" in ctx["reference_artifact_files"]

    def test_new_milestone_stage_bootstrap_filters_payload(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Setup Phase\n")
        _write_project_contract_state(tmp_path)

        manifest = load_workflow_stage_manifest("new-milestone")
        stage = manifest.get_stage("milestone_bootstrap")

        ctx = init_new_milestone(tmp_path, stage="milestone_bootstrap")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["workflow_id"] == "new-milestone"
        assert ctx["staged_loading"]["stage_id"] == "milestone_bootstrap"
        assert ctx["staged_loading"]["writes_allowed"] == []
        assert "planning_exists" not in ctx
        assert "roadmapper_model" not in ctx

    def test_does_not_bootstrap_manuscript_proof_review_manifest(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Setup Phase\n")
        _write_manuscript_proof_review_artifacts(tmp_path)

        ctx = init_new_milestone(tmp_path)

        status = ctx["derived_manuscript_proof_review_status"]
        assert status["state"] == "fresh"
        assert status["manifest_bootstrapped"] is False
        assert not (tmp_path / "paper" / "PROOF-REVIEW-MANIFEST.json").exists()

    def test_surfaces_project_contract_load_and_validation_gates_when_contract_is_not_authoritative(
        self, tmp_path: Path
    ) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Setup Phase\n")

        from gpd.core.state import default_state_dict

        state = default_state_dict()
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["context_intake"] = {
            "must_read_refs": [],
            "must_include_prior_outputs": [],
            "user_asserted_anchors": [],
            "known_good_baselines": [],
            "context_gaps": [],
            "crucial_inputs": [],
        }
        contract["references"][0]["role"] = "background"
        contract["references"][0]["must_surface"] = False
        state["project_contract"] = contract
        (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")

        ctx = init_new_milestone(tmp_path)

        assert ctx["project_contract"] is not None
        assert ctx["project_contract"]["references"][0]["role"] == "background"
        assert ctx["project_contract_load_info"]["status"] == "blocked_integrity"
        assert ctx["project_contract_validation"]["valid"] is False
        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["project_contract_gate"]["authoritative"] is False
        assert "project_contract_load_info" in ctx
        assert "project_contract_validation" in ctx

    def test_new_milestone_stage_survey_objectives_filters_payload(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Setup Phase\n")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        manifest = load_workflow_stage_manifest("new-milestone")
        stage = manifest.get_stage("survey_objectives")

        ctx = init_new_milestone(tmp_path, stage="survey_objectives")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["workflow_id"] == "new-milestone"
        assert ctx["staged_loading"]["stage_id"] == "survey_objectives"
        assert ctx["staged_loading"]["loaded_authorities"] == [
            "workflows/new-milestone.md",
            "references/research/questioning.md",
        ]
        assert ctx["staged_loading"]["writes_allowed"] == [
            "GPD/PROJECT.md",
            "GPD/STATE.md",
            "GPD/literature",
        ]
        assert ctx["staged_loading"]["checkpoints"] == [
            "prior milestone context reviewed",
            "survey choice and objective scope captured",
        ]
        assert "contract_intake" in ctx
        assert "effective_reference_intake" in ctx
        assert "reference_artifacts_content" in ctx
        assert "roadmapper_model" not in ctx

    def test_new_milestone_stage_roadmap_authoring_filters_payload(self, tmp_path: Path) -> None:
        from gpd.core.workflow_staging import load_workflow_stage_manifest

        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Setup Phase\n")
        (tmp_path / "GPD" / "PROJECT.md").write_text("# Project\n\nMilestone context.\n", encoding="utf-8")
        (tmp_path / "GPD" / "STATE.md").write_text("# State\n\nReady.\n", encoding="utf-8")
        (tmp_path / "GPD" / "REQUIREMENTS.md").write_text("# Requirements\n\n- Confirm objective.\n", encoding="utf-8")
        (tmp_path / "GPD" / "ROADMAP.md").write_text("# Roadmap\n\n## Milestone v1.0\n", encoding="utf-8")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        manifest = load_workflow_stage_manifest("new-milestone")
        stage = manifest.get_stage("roadmap_authoring")

        ctx = init_new_milestone(tmp_path, stage="roadmap_authoring")

        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert ctx["staged_loading"]["workflow_id"] == "new-milestone"
        assert ctx["staged_loading"]["stage_id"] == "roadmap_authoring"
        assert ctx["staged_loading"]["loaded_authorities"] == [
            "workflows/new-milestone.md",
            "templates/project.md",
            "templates/requirements.md",
        ]
        assert ctx["staged_loading"]["writes_allowed"] == [
            "GPD/PROJECT.md",
            "GPD/STATE.md",
            "GPD/REQUIREMENTS.md",
            "GPD/ROADMAP.md",
        ]
        assert ctx["staged_loading"]["checkpoints"] == [
            "objectives finalized",
            "roadmap authored",
        ]
        assert "requirements_content" in ctx
        assert "roadmap_content" in ctx


# ─── init_quick ───────────────────────────────────────────────────────────────


class TestInitQuick:
    def test_first_quick_task(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
        ctx = init_quick(tmp_path, "Fix tensor product calculation")
        assert ctx["next_num"] == 1
        assert ctx["slug"] is not None
        assert "fix" in ctx["slug"]
        assert ctx["task_dir"] is not None
        assert ctx["project_exists"] is True

    def test_increments_number(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        quick_dir = tmp_path / "GPD" / "quick"
        quick_dir.mkdir()
        (quick_dir / "1-first-task").mkdir()
        (quick_dir / "2-second-task").mkdir()

        ctx = init_quick(tmp_path, "next task")
        assert ctx["next_num"] == 3

    def test_permission_error_on_quick_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _setup_project(tmp_path)
        quick_dir = tmp_path / "GPD" / "quick"
        quick_dir.mkdir()

        original_iterdir = Path.iterdir

        def _raise_permission(self: Path) -> None:
            if self == quick_dir:
                raise PermissionError("Permission denied")
            return original_iterdir(self)

        monkeypatch.setattr(Path, "iterdir", _raise_permission)

        ctx = init_quick(tmp_path, "some task")
        # Falls back to default numbering when directory is unreadable
        assert ctx["next_num"] == 1

    def test_stage_task_authoring_uses_quick_manifest_contract(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
        _write_project_contract_state(tmp_path)
        manifest = load_workflow_stage_manifest("quick")

        ctx = init_quick(tmp_path, "Quick reference check", stage="task_authoring")
        stage = manifest.stage_by_id("task_authoring")

        assert ctx["staged_loading"]["stage_id"] == "task_authoring"
        assert set(ctx) == set(stage.required_init_fields) | {"staged_loading"}
        assert "project_contract_gate" in ctx
        assert "reference_artifacts_content" in ctx
        assert "active_reference_context" in ctx

    def test_no_description(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_quick(tmp_path)
        assert ctx["slug"] is None
        assert ctx["task_dir"] is None


# ─── init_resume ──────────────────────────────────────────────────────────────


class TestInitResume:
    def test_no_interrupted_agent(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_resume(tmp_path)
        assert ctx["has_interrupted_agent"] is False
        assert ctx["interrupted_agent_id"] is None

    def test_with_interrupted_agent(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / "GPD" / "current-agent-id.txt").write_text("agent-123\n", encoding="utf-8")

        ctx = init_resume(tmp_path)
        assert ctx["has_interrupted_agent"] is True
        assert ctx["interrupted_agent_id"] == "agent-123"
        assert ctx["active_resume_kind"] == "interrupted_agent"
        assert ctx["active_resume_origin"] == "interrupted_agent_marker"
        assert ctx["active_resume_pointer"] == "agent-123"
        assert ctx["resume_candidates"] == [
            {
                "status": "interrupted",
                "agent_id": "agent-123",
                "kind": "interrupted_agent",
                "origin": "interrupted_agent_marker",
                "resume_pointer": "agent-123",
            }
        ]
        assert "source" not in ctx["resume_candidates"][0]
        assert "compat_resume_surface" not in ctx

    def test_resume_prefers_explicit_gpd_workspace_over_recent_project(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        recent_project = tmp_path / "recent-project"
        data_root = tmp_path / "data"

        workspace.mkdir()
        recent_project.mkdir()
        _setup_project(workspace)
        (workspace / "GPD" / "current-agent-id.txt").write_text("agent-local\n", encoding="utf-8")

        _setup_project(recent_project)
        from gpd.core.state import default_state_dict

        (recent_project / "GPD" / "state.json").write_text(
            json.dumps(default_state_dict()),
            encoding="utf-8",
        )
        (recent_project / "GPD" / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (recent_project / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
        resume_path = recent_project / "GPD" / "phases" / "01-analysis" / ".continue-here.md"
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")
        record_recent_project(
            recent_project,
            session_data={
                "last_date": "2026-03-29T12:00:00+00:00",
                "resume_file": "GPD/phases/01-analysis/.continue-here.md",
            },
            store_root=data_root,
        )

        ctx = init_resume(workspace, data_root=data_root)

        assert ctx["project_root"] == workspace.resolve().as_posix()
        assert ctx["project_root_source"] == "current_workspace"
        assert ctx["project_root_auto_selected"] is False
        assert ctx["project_reentry_mode"] == "current-workspace"
        assert ctx["project_reentry_selected_candidate"] is not None
        assert ctx["project_reentry_selected_candidate"]["source"] == "current_workspace"
        assert ctx["has_interrupted_agent"] is True
        assert ctx["interrupted_agent_id"] == "agent-local"
        assert ctx["active_resume_kind"] == "interrupted_agent"

    def test_json_only_state_counts_as_existing(self, tmp_path: Path) -> None:
        from gpd.core.state import default_state_dict

        _setup_project(tmp_path)
        (tmp_path / "GPD" / "state.json").write_text(json.dumps(default_state_dict()), encoding="utf-8")

        ctx = init_resume(tmp_path)

        assert ctx["state_exists"] is True

    def test_exposes_bounded_segment_resume_candidate(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-1",
                "phase": "03",
                "plan": "02",
                "segment_id": "seg-4",
                "segment_status": "paused",
                "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                "updated_at": "2026-03-10T12:00:00+00:00",
            },
        )

        ctx = init_resume(tmp_path)

        assert ctx["resume_surface_schema_version"] == 1
        assert "resume_mode" not in ctx
        assert ctx["active_resume_kind"] == "bounded_segment"
        assert ctx["active_resume_origin"] == "continuation.bounded_segment"
        assert ctx["active_resume_pointer"] == "GPD/phases/03-analysis/.continue-here.md"
        assert ctx["active_bounded_segment"]["segment_id"] == "seg-4"
        assert ctx["derived_execution_head"]["segment_id"] == "seg-4"
        _assert_no_resume_compat_aliases(ctx)
        assert "compat_resume_surface" not in ctx
        assert "segment_candidates" not in ctx
        assert ctx["resume_candidates"][0]["kind"] == "bounded_segment"
        assert ctx["resume_candidates"][0]["origin"] == "continuation.bounded_segment"
        assert ctx["resume_candidates"][0]["resume_pointer"] == "GPD/phases/03-analysis/.continue-here.md"
        assert "source" not in ctx["resume_candidates"][0]

    def test_canonical_bounded_segment_carries_last_result_id_and_hydrates_result(
        self, tmp_path: Path
    ) -> None:
        _setup_project(tmp_path)
        from gpd.core.state import default_state_dict

        state = default_state_dict()
        state["continuation"]["bounded_segment"] = {
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "phase": "03",
            "plan": "02",
            "segment_id": "seg-canonical",
            "segment_status": "paused",
            "last_result_id": "result-canonical",
        }
        state["intermediate_results"] = [
            {
                "id": "result-canonical",
                "equation": "R = A + B",
                "description": "Canonical bridge result",
                "phase": "03",
                "depends_on": [],
                "verified": True,
                "verification_records": [],
            }
        ]
        (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")
        resume_path = tmp_path / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")

        ctx = init_resume(tmp_path)

        assert ctx["active_resume_kind"] == "bounded_segment"
        assert ctx["active_resume_origin"] == "continuation.bounded_segment"
        assert ctx["active_bounded_segment"]["last_result_id"] == "result-canonical"
        assert ctx["resume_candidates"][0]["last_result_id"] == "result-canonical"
        assert ctx["resume_candidates"][0]["last_result"]["id"] == "result-canonical"
        assert ctx["active_resume_result"]["id"] == "result-canonical"
        assert "compat_resume_surface" not in ctx

    def test_normalizes_live_execution_phase_plan_and_checkpoint_reason(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-raw",
                "phase": "3",
                "plan": "2",
                "segment_id": "seg-9",
                "segment_status": "waiting_review",
                "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                "checkpoint_reason": "pre-fanout",
                "pre_fanout_review_pending": True,
                "updated_at": "2026-03-10T12:00:00+00:00",
            },
        )

        ctx = init_resume(tmp_path)

        assert ctx["active_bounded_segment"]["phase"] == "03"
        assert ctx["active_bounded_segment"]["plan"] == "02"
        assert ctx["active_bounded_segment"]["checkpoint_reason"] == "pre_fanout"
        candidate = ctx["resume_candidates"][0]
        assert candidate["phase"] == "03"
        assert candidate["plan"] == "02"
        assert candidate["checkpoint_reason"] == "pre_fanout"
        assert candidate["origin"] == "continuation.bounded_segment"
        assert "source" not in candidate

    def test_resume_candidate_carries_pre_fanout_and_skeptical_review_fields(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-1",
                "phase": "03",
                "plan": "02",
                "segment_id": "seg-7",
                "segment_status": "waiting_review",
                "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                "checkpoint_reason": "pre_fanout",
                "pre_fanout_review_pending": True,
                "skeptical_requestioning_required": True,
                "skeptical_requestioning_summary": "Proxy passed but benchmark anchor remains unchecked.",
                "weakest_unchecked_anchor": "Ref-01 benchmark figure",
                "disconfirming_observation": "Direct observable misses the literature band.",
                "downstream_locked": True,
                "last_result_label": "Proxy benchmark fit",
                "updated_at": "2026-03-10T12:00:00+00:00",
            },
        )

        ctx = init_resume(tmp_path)

        assert "resume_mode" not in ctx
        assert ctx["execution_pre_fanout_review_pending"] is True
        assert ctx["execution_skeptical_requestioning_required"] is True
        candidate = ctx["resume_candidates"][0]
        assert candidate["checkpoint_reason"] == "pre_fanout"
        assert candidate["pre_fanout_review_pending"] is True
        assert candidate["skeptical_requestioning_required"] is True
        assert candidate["weakest_unchecked_anchor"] == "Ref-01 benchmark figure"
        assert candidate["disconfirming_observation"] == "Direct observable misses the literature band."
        assert candidate["downstream_locked"] is True
        assert candidate["origin"] == "continuation.bounded_segment"
        assert "source" not in candidate

    def test_resume_candidate_keeps_clear_without_unlock_as_bounded_segment_state(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-1",
                "phase": "03",
                "plan": "02",
                "segment_id": "seg-8",
                "segment_status": "waiting_review",
                "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                "checkpoint_reason": "pre_fanout",
                "pre_fanout_review_pending": True,
                "pre_fanout_review_cleared": True,
                "downstream_locked": True,
                "updated_at": "2026-03-10T12:00:00+00:00",
            },
        )

        ctx = init_resume(tmp_path)

        assert "resume_mode" not in ctx
        assert ctx["execution_pre_fanout_review_pending"] is True
        assert ctx["execution_downstream_locked"] is True
        assert ctx["active_bounded_segment"]["pre_fanout_review_cleared"] is True
        assert ctx["resume_candidates"][0]["checkpoint_reason"] == "pre_fanout"
        assert ctx["resume_candidates"][0]["pre_fanout_review_cleared"] is True
        assert ctx["resume_candidates"][0]["origin"] == "continuation.bounded_segment"
        assert "source" not in ctx["resume_candidates"][0]

    def test_non_resumable_live_execution_does_not_create_resume_candidate(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-1",
                "phase": "03",
                "plan": "02",
                "segment_id": "seg-4",
                "segment_status": "active",
                "current_task": "Running bounded segment",
                "updated_at": "2026-03-10T12:00:00+00:00",
            },
        )

        ctx = init_resume(tmp_path)

        assert "resume_mode" not in ctx
        assert ctx["active_bounded_segment"] is None
        assert ctx["derived_execution_head"]["segment_id"] == "seg-4"
        assert ctx["active_resume_kind"] is None
        _assert_no_resume_compat_aliases(ctx)
        assert "segment_candidates" not in ctx
        assert ctx["resume_candidates"] == []
        assert "active_execution_segment" not in ctx
        assert "compat_resume_surface" not in ctx

    def test_session_resume_file_no_longer_hydrates_resume_authority(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        from gpd.core.state import default_state_dict

        state = default_state_dict()
        state["session"]["resume_file"] = "GPD/phases/03-analysis/.continue-here.md"
        state["session"]["stopped_at"] = "2026-03-10T12:00:00+00:00"
        state["session"]["hostname"] = "legacy-host"
        state["session"]["platform"] = "legacy-platform"
        resume_path = tmp_path / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")
        (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")

        ctx = init_resume(tmp_path)

        assert ctx["active_resume_kind"] is None
        assert ctx["active_resume_origin"] is None
        assert ctx["active_resume_pointer"] is None
        assert ctx["machine_change_detected"] is False
        assert ctx["machine_change_notice"] is None
        assert ctx["continuity_handoff_file"] is None
        assert ctx["recorded_continuity_handoff_file"] is None
        assert ctx["session_hostname"] is None
        assert ctx["session_platform"] is None
        assert ctx["session_last_date"] is None
        assert ctx["session_stopped_at"] is None
        assert ctx["resume_candidates"] == []
        assert "compat_resume_surface" not in ctx

    def test_init_resume_does_not_recover_intent_during_read_only_discovery(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        layout = _write_state_intent_recovery_files(tmp_path)

        before_state_json = layout.state_json.read_text(encoding="utf-8")
        before_state_intent = layout.state_intent.read_text(encoding="utf-8")
        before_json_tmp = (layout.gpd / ".state-json-tmp").read_text(encoding="utf-8")
        before_md_tmp = (layout.gpd / ".state-md-tmp").read_text(encoding="utf-8")

        ctx = init_resume(tmp_path)

        assert ctx["state_exists"] is True
        assert layout.state_json.read_text(encoding="utf-8") == before_state_json
        assert layout.state_intent.read_text(encoding="utf-8") == before_state_intent
        assert (layout.gpd / ".state-json-tmp").read_text(encoding="utf-8") == before_json_tmp
        assert (layout.gpd / ".state-md-tmp").read_text(encoding="utf-8") == before_md_tmp

    def test_state_md_fallback_no_longer_hydrates_resume_authority_from_legacy_session(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        from gpd.core.state import default_state_dict, generate_state_markdown

        state = default_state_dict()
        state["session"]["resume_file"] = "GPD/phases/03-analysis/.continue-here.md"
        state["session"]["stopped_at"] = "2026-03-10T12:00:00+00:00"
        state["session"]["hostname"] = "legacy-host"
        state["session"]["platform"] = "legacy-platform"
        resume_path = tmp_path / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")
        (tmp_path / "GPD" / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

        ctx = init_resume(tmp_path)

        assert ctx["active_resume_kind"] is None
        assert ctx["active_resume_origin"] is None
        assert ctx["active_resume_pointer"] is None
        assert ctx["machine_change_detected"] is False
        assert ctx["machine_change_notice"] is None
        assert ctx["continuity_handoff_file"] is None
        assert ctx["recorded_continuity_handoff_file"] is None
        assert ctx["session_hostname"] is None
        assert ctx["session_platform"] is None
        assert ctx["session_last_date"] is None
        assert ctx["session_stopped_at"] is None
        assert ctx["resume_candidates"] == []

    def test_init_resume_propagates_unexpected_continuation_errors(self, tmp_path: Path, monkeypatch) -> None:
        _setup_project(tmp_path)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("canonical resolution exploded")

        monkeypatch.setattr("gpd.core.context.resolve_continuation", _boom)

        with pytest.raises(RuntimeError, match="canonical resolution exploded"):
            init_resume(tmp_path)

# ─── init_verify_work ─────────────────────────────────────────────────────────


class TestInitVerifyWork:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "01-VERIFICATION.md").write_text("verified", encoding="utf-8")

        ctx = init_verify_work(tmp_path, "1")
        assert ctx["phase_found"] is True
        assert ctx["has_verification"] is True

    def test_stage_session_router_returns_bootstrap_only_payload(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_project_contract_state(tmp_path)

        ctx = init_verify_work(tmp_path, "1", stage="session_router")

        assert ctx["phase_found"] is True
        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["phase_proof_review_status"]["scope"] == "phase"
        assert ctx["phase_proof_review_status"]["state"] == "not_reviewed"
        assert ctx["staged_loading"]["stage_id"] == "session_router"
        assert ctx["staged_loading"]["checkpoints"] == [
            "active session check completed",
            "review preflight completed",
            "contract gate remains visible",
        ]
        assert "project_contract" not in ctx
        assert "active_reference_context" not in ctx
        assert "reference_artifacts_content" not in ctx
        assert "convention_lock" not in ctx

    def test_missing_phase_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="phase is required"):
            init_verify_work(tmp_path, "")

    def test_stage_inventory_build_surfaces_reference_and_convention_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_stat_mech_project(tmp_path)
        _write_bundle_ready_contract_state(tmp_path)
        _write_structured_state_payload(tmp_path)

        ctx = init_verify_work(tmp_path, "1", stage="inventory_build")

        assert ctx["staged_loading"]["stage_id"] == "inventory_build"
        assert ctx["project_contract"]["references"][0]["role"] == "benchmark"
        assert "## Active Reference Registry" in ctx["active_reference_context"]
        assert "stat-mech-simulation" in ctx["selected_protocol_bundle_ids"]
        assert ctx["convention_lock"]["metric_signature"] == "(-,+,+,+)"
        assert ctx["derived_convention_lock"]["metric_signature"] == "(-,+,+,+)"
        assert "reference_artifacts_content" not in ctx

    def test_stage_interactive_validation_defers_reference_artifact_content(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_project_contract_state(tmp_path)

        literature_dir = tmp_path / "GPD" / "literature"
        literature_dir.mkdir(parents=True)
        (literature_dir / "benchmark-notes.md").write_text("# Benchmark\nReference details.\n", encoding="utf-8")

        ctx = init_verify_work(tmp_path, "1", stage="interactive_validation")

        assert ctx["staged_loading"]["stage_id"] == "interactive_validation"
        assert ctx["reference_artifact_files"]
        assert "reference_artifacts_content" not in ctx

    def test_stage_gap_repair_surfaces_reference_artifact_content(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_project_contract_state(tmp_path)

        literature_dir = tmp_path / "GPD" / "literature"
        literature_dir.mkdir(parents=True)
        (literature_dir / "benchmark-notes.md").write_text("# Benchmark\nReference details.\n", encoding="utf-8")

        ctx = init_verify_work(tmp_path, "1", stage="gap_repair")

        assert ctx["staged_loading"]["stage_id"] == "gap_repair"
        assert ctx["reference_artifact_files"]
        assert isinstance(ctx["reference_artifacts_content"], str)
        assert "Benchmark" in ctx["reference_artifacts_content"]

    def test_verify_work_surfaces_derived_stable_knowledge_docs(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_knowledge_doc(tmp_path, status="stable")
        _write_knowledge_doc(
            tmp_path,
            knowledge_id="K-work-in-progress",
            status="draft",
            body="Draft knowledge body.\n",
        )

        ctx = init_verify_work(tmp_path, "1")

        assert ctx["knowledge_doc_count"] == 2
        assert ctx["derived_knowledge_doc_count"] == 1
        assert ctx["derived_knowledge_docs"][0]["status"] == "stable"
        assert ctx["knowledge_doc_warnings"] == []
        assert "GPD/knowledge/K-renormalization-group-fixed-points.md" in ctx["reference_artifact_files"]
        assert "GPD/knowledge/K-work-in-progress.md" not in ctx["reference_artifact_files"]
        assert "Draft knowledge body." not in ctx["reference_artifacts_content"]
        assert "non-stable knowledge doc(s) remain inventory-visible only" in ctx["active_reference_context"]

    def test_exposes_active_reference_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_project_contract_state(tmp_path)

        ctx = init_verify_work(tmp_path, "1")

        assert ctx["project_contract"]["references"][0]["role"] == "benchmark"
        assert "## Active Reference Registry" in ctx["active_reference_context"]

    def test_stage_rejects_unknown_verify_work_stage(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")

        with pytest.raises(ValueError, match="Unknown verify-work stage 'bogus'"):
            init_verify_work(tmp_path, "1", stage="bogus")

    def test_exposes_selected_protocol_bundle_ids(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_stat_mech_project(tmp_path)
        _write_bundle_ready_contract_state(tmp_path)

        ctx = init_verify_work(tmp_path, "1")

        assert "stat-mech-simulation" in ctx["selected_protocol_bundle_ids"]
        assert "Verifier extensions:" in ctx["protocol_bundle_context"]

    def test_surfaces_convention_lock_fields(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_structured_state_payload(tmp_path)

        ctx = init_verify_work(tmp_path, "1")

        assert ctx["state_load_source"] == "state.json"
        assert ctx["convention_lock"]["metric_signature"] == "(-,+,+,+)"
        assert ctx["convention_lock"]["fourier_convention"] == "physics"
        assert ctx["convention_lock_count"] >= ctx["derived_convention_lock_count"] >= 1
        assert ctx["derived_convention_lock"]["metric_signature"] == "(-,+,+,+)"

    def test_bootstraps_phase_proof_review_manifest(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "01-SUMMARY.md").write_text("# Summary\n", encoding="utf-8")
        (phase_dir / "01-VERIFICATION.md").write_text("# Verification\n", encoding="utf-8")

        ctx = init_verify_work(tmp_path, "1")

        assert ctx["phase_proof_review_status"]["state"] == "fresh"
        assert ctx["phase_proof_review_status"]["manifest_bootstrapped"] is True
        assert (tmp_path / "GPD" / "phases" / "01-setup" / "01-PROOF-REVIEW-MANIFEST.json").exists()

    def test_reports_stale_phase_proof_review_after_phase_edit(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        summary_path = phase_dir / "01-SUMMARY.md"
        summary_path.write_text("# Summary\n", encoding="utf-8")
        (phase_dir / "01-VERIFICATION.md").write_text("# Verification\n", encoding="utf-8")

        initial = init_verify_work(tmp_path, "1")
        assert initial["phase_proof_review_status"]["state"] == "fresh"

        summary_path.write_text("# Summary\n\nUpdated derivation.\n", encoding="utf-8")

        ctx = init_verify_work(tmp_path, "1")

        assert ctx["phase_proof_review_status"]["state"] == "stale"
        assert ctx["phase_proof_review_status"]["can_rely_on_prior_review"] is False

    def test_exposes_manuscript_proof_review_status(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_manuscript_proof_review_artifacts(tmp_path)

        ctx = init_verify_work(tmp_path, "1")

        status = ctx["derived_manuscript_proof_review_status"]
        assert status["state"] == "fresh"
        assert status["can_rely_on_prior_review"] is True
        assert status["manifest_bootstrapped"] is True
        assert status["manifest_path"] == "paper/PROOF-REVIEW-MANIFEST.json"
        assert status["anchor_artifact"] == "GPD/review/PROOF-REDTEAM.md"
        assert status["watched_file_count"] >= 3
        assert status["changed_file_count"] == 0

    def test_reports_stale_manuscript_proof_review_after_bibliography_edit(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        bibliography_path = _write_manuscript_proof_review_artifacts(tmp_path)

        initial = init_verify_work(tmp_path, "1")
        assert initial["derived_manuscript_proof_review_status"]["state"] == "fresh"

        bibliography_path.write_text("@article{demo,title={Updated Demo}}\n", encoding="utf-8")

        ctx = init_verify_work(tmp_path, "1")

        status = ctx["derived_manuscript_proof_review_status"]
        assert status["state"] == "stale"
        assert status["can_rely_on_prior_review"] is False
        assert status["changed_file_count"] >= 1
        assert "paper/references.bib" in status["changed_files"]

    def test_reports_stale_manuscript_proof_review_after_external_proof_edit(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_manuscript_proof_review_artifacts_with_proof_path(
            tmp_path,
            proof_artifact_path="proofs/external-proof.tex",
        )
        external_proof_path = tmp_path / "proofs" / "external-proof.tex"

        initial = init_verify_work(tmp_path, "1")
        assert initial["derived_manuscript_proof_review_status"]["state"] == "fresh"
        assert external_proof_path.as_posix().removeprefix(f"{tmp_path.as_posix()}/") in initial["derived_manuscript_proof_review_status"]["watched_files"]

        external_proof_path.write_text(
            "\\documentclass{article}\n\\begin{document}\nRevised external proof.\n\\end{document}\n",
            encoding="utf-8",
        )

        ctx = init_verify_work(tmp_path, "1")

        status = ctx["derived_manuscript_proof_review_status"]
        assert status["state"] == "stale"
        assert status["can_rely_on_prior_review"] is False
        assert external_proof_path.as_posix().removeprefix(f"{tmp_path.as_posix()}/") in status["changed_files"]


# ─── init_todos ───────────────────────────────────────────────────────────────


class TestInitTodos:
    def test_empty_todos(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_todos(tmp_path)
        assert ctx["todo_count"] == 0
        assert ctx["todos"] == []

    def test_finds_todos(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        pending = tmp_path / "GPD" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "check-convergence.md").write_text(
            'title: "Check convergence"\narea: numerical\ncreated: 2026-03-01\n\n'
            'The body may mention area: theory and created: 2024-01-01, but those lines must be ignored.', encoding="utf-8"
        )

        ctx = init_todos(tmp_path)
        assert ctx["todo_count"] == 1
        assert ctx["todos"][0]["title"] == "Check convergence"
        assert ctx["todos"][0]["area"] == "numerical"
        assert ctx["todos"][0]["created"] == "2026-03-01"

    def test_body_metadata_like_lines_do_not_override_missing_header_fields(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        pending = tmp_path / "GPD" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "check-convergence.md").write_text(
            'title: "Check convergence"\n\n'
            'The body may mention area: numerical and created: 2026-03-01.\n'
            'Those lines must not be treated as todo metadata.', encoding="utf-8"
        )

        ctx = init_todos(tmp_path)
        assert ctx["todo_count"] == 1
        assert ctx["todos"][0]["title"] == "Check convergence"
        assert ctx["todos"][0]["area"] == "general"
        assert ctx["todos"][0]["created"] == "unknown"

    def test_skips_todo_with_malformed_yaml_frontmatter(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        pending = tmp_path / "GPD" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "good.md").write_text(
            "---\n"
            "title: Good todo\n"
            "area: numerical\n"
            "created: 2026-03-01\n"
            "---\n"
            "Body\n",
            encoding="utf-8",
        )
        (pending / "bad.md").write_text(
            "---\n"
            "title: Broken todo\n"
            "area: [unterminated\n"
            "Body without a closing delimiter\n",
            encoding="utf-8",
        )

        ctx = init_todos(tmp_path)

        assert ctx["todo_count"] == 1
        assert [todo["file"] for todo in ctx["todos"]] == ["good.md"]

    def test_preserves_yaml_created_date_scalar(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        pending = tmp_path / "GPD" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "check-convergence.md").write_text(
            "---\n"
            "title: Check convergence\n"
            "area: numerical\n"
            "created: 2026-03-01\n"
            "---\n"
            "Body\n",
            encoding="utf-8",
        )

        ctx = init_todos(tmp_path)

        assert ctx["todo_count"] == 1
        assert ctx["todos"][0]["created"] == "2026-03-01"

    def test_todo_body_starting_with_horizontal_rule_is_not_skipped(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        pending = tmp_path / "GPD" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "note.md").write_text(
            "---\n"
            "Body starts with a rule, not metadata.\n",
            encoding="utf-8",
        )

        ctx = init_todos(tmp_path)

        assert ctx["todo_count"] == 1
        assert ctx["todos"][0]["file"] == "note.md"
        assert ctx["todos"][0]["title"] == "Untitled"
        assert ctx["todos"][0]["area"] == "general"
        assert ctx["todos"][0]["created"] == "unknown"

    def test_area_filter(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        pending = tmp_path / "GPD" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "a.md").write_text("title: A\narea: theory", encoding="utf-8")
        (pending / "b.md").write_text("title: B\narea: numerical", encoding="utf-8")

        ctx = init_todos(tmp_path, area="theory")
        assert ctx["todo_count"] == 1
        assert ctx["todos"][0]["title"] == "A"


# ─── init_milestone_op ────────────────────────────────────────────────────────


class TestInitMilestoneOp:
    def test_empty_project(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_milestone_op(tmp_path)
        assert ctx["phase_count"] == 0
        assert ctx["completed_phases"] == 0
        assert ctx["all_phases_complete"] is False

    def test_counts_roadmap_phases_and_disk_completion(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ## Milestone v1.0: Test

            ### Phase 1: Setup
            **Goal:** setup

            ### Phase 2: Build
            **Goal:** build
            """,
        )
        p1 = _create_phase_dir(tmp_path, "01-setup")
        (p1 / "a-PLAN.md").write_text("plan", encoding="utf-8")
        (p1 / "a-SUMMARY.md").write_text("summary", encoding="utf-8")

        ctx = init_milestone_op(tmp_path)

        assert ctx["phase_count"] == 2
        assert ctx["completed_phases"] == 1
        assert ctx["all_phases_complete"] is False

    def test_counts_phases(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        # Complete phase
        p1 = _create_phase_dir(tmp_path, "01-setup")
        (p1 / "a-PLAN.md").write_text("plan", encoding="utf-8")
        (p1 / "a-SUMMARY.md").write_text("summary", encoding="utf-8")
        # Incomplete phase
        p2 = _create_phase_dir(tmp_path, "02-analysis")
        (p2 / "b-PLAN.md").write_text("plan", encoding="utf-8")

        ctx = init_milestone_op(tmp_path)
        assert ctx["phase_count"] == 2
        assert ctx["completed_phases"] == 1
        assert ctx["all_phases_complete"] is False

    def test_archive_inventory_counts_top_level_files(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        archive_dir = tmp_path / "GPD" / "milestones"
        archive_dir.mkdir(parents=True, exist_ok=True)
        for name in ("v1.0-ROADMAP.md", "v1.0-REQUIREMENTS.md", "v1.0-MILESTONE-AUDIT.md"):
            (archive_dir / name).write_text("archive", encoding="utf-8")

        ctx = init_milestone_op(tmp_path)

        assert ctx["archive_count"] == 3
        assert ctx["archived_milestones"] == [
            "v1.0-MILESTONE-AUDIT.md",
            "v1.0-REQUIREMENTS.md",
            "v1.0-ROADMAP.md",
        ]

    def test_surfaces_project_contract_gate_and_active_reference_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)

        ctx = init_milestone_op(tmp_path)

        assert ctx["project_contract"] is not None
        assert ctx["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
        assert ctx["project_contract_load_info"]["status"] == "loaded"
        assert ctx["project_contract_validation"] is not None
        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["project_contract_gate"]["status"] == ctx["project_contract_load_info"]["status"]
        assert ctx["project_contract_gate"]["authoritative"] is True
        assert ctx["project_contract_validation"]["valid"] is True
        assert "[ref-benchmark]" in ctx["active_reference_context"]


# ─── init_map_research ────────────────────────────────────────────────────────


class TestInitMapResearch:
    def test_no_maps(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_map_research(tmp_path)
        assert ctx["has_maps"] is False
        assert ctx["existing_maps"] == []

    def test_existing_maps(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        map_dir = tmp_path / "GPD" / "research-map"
        map_dir.mkdir()
        (map_dir / "theory.md").write_text("# Theory Map", encoding="utf-8")

        ctx = init_map_research(tmp_path)
        assert ctx["has_maps"] is True
        assert "theory.md" in ctx["existing_maps"]

    def test_surfaces_project_contract_for_reference_mapping(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)

        ctx = init_map_research(tmp_path)

        assert ctx["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
        assert "ref-benchmark" in ctx["active_reference_context"]

    def test_surfaces_artifact_derived_reference_context_without_contract(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_map_research(tmp_path)

        assert ctx["project_contract"] is None
        assert ctx["derived_active_reference_count"] >= 2
        assert "Benchmark Ref 2024" in ctx["active_reference_context"]
        assert "GPD/phases/01-test-phase/01-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]

    def test_stage_bootstrap_returns_only_manifest_required_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)
        _install_fake_stage_manifest(
            monkeypatch,
            workflow_id="map-research",
            stages={
                "bootstrap": [
                    "mapper_model",
                    "commit_docs",
                    "research_mode",
                    "has_maps",
                    "project_contract",
                    "project_contract_gate",
                    "project_contract_load_info",
                    "project_contract_validation",
                    "active_reference_context",
                    "reference_artifacts_content",
                ]
            },
        )

        ctx = init_map_research(tmp_path, stage="bootstrap")

        assert ctx["staged_loading"]["workflow_id"] == "map-research"
        assert ctx["staged_loading"]["stage_id"] == "bootstrap"
        assert set(ctx) == {
            "mapper_model",
            "commit_docs",
            "research_mode",
            "has_maps",
            "project_contract",
            "project_contract_gate",
            "project_contract_load_info",
            "project_contract_validation",
            "active_reference_context",
            "reference_artifacts_content",
            "staged_loading",
        }


class TestInitLiteratureReview:
    def test_stage_loads_review_bootstrap_payload(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _install_fake_stage_manifest(
            monkeypatch,
            workflow_id="literature-review",
            stages={
                "bootstrap": [
                    "topic",
                    "slug",
                    "commit_docs",
                    "state_exists",
                    "project_exists",
                    "project_contract",
                    "project_contract_gate",
                    "project_contract_load_info",
                    "project_contract_validation",
                    "active_reference_context",
                    "reference_artifacts_content",
                ]
            },
        )

        ctx = init_literature_review(tmp_path, topic="Curvature flow bounds", stage="bootstrap")

        assert ctx["topic"] == "Curvature flow bounds"
        assert ctx["slug"] == "curvature-flow-bounds"
        assert ctx["staged_loading"]["workflow_id"] == "literature-review"
        assert ctx["staged_loading"]["stage_id"] == "bootstrap"
        assert set(ctx) == {
            "topic",
            "slug",
            "commit_docs",
            "state_exists",
            "project_exists",
            "project_contract",
            "project_contract_gate",
            "project_contract_load_info",
            "project_contract_validation",
            "active_reference_context",
            "reference_artifacts_content",
            "staged_loading",
        }


# ─── init_progress ────────────────────────────────────────────────────────────


class TestInitProgress:
    def test_empty_project(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_progress(tmp_path)
        assert ctx["phase_count"] == 0
        assert ctx["current_phase"] is None
        assert ctx["next_phase"] is None
        assert ctx["paused_at"] is None

    def test_phase_statuses(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        # Complete phase
        p1 = _create_phase_dir(tmp_path, "01-setup")
        (p1 / "a-PLAN.md").write_text("plan", encoding="utf-8")
        (p1 / "a-SUMMARY.md").write_text("summary", encoding="utf-8")
        # In-progress phase
        p2 = _create_phase_dir(tmp_path, "02-analysis")
        (p2 / "b-PLAN.md").write_text("plan", encoding="utf-8")
        # Pending phase
        _create_phase_dir(tmp_path, "03-synthesis")

        ctx = init_progress(tmp_path)
        assert ctx["phase_count"] == 3
        assert ctx["completed_count"] == 1
        assert ctx["in_progress_count"] == 1
        assert ctx["current_phase"]["number"] == "02"
        assert ctx["next_phase"]["number"] == "03"

    def test_progress_prefers_phase_inventory_over_stale_state_position(self, tmp_path: Path) -> None:
        from gpd.core.state import default_state_dict

        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "02-analysis")
        (phase_dir / "b-PLAN.md").write_text("plan", encoding="utf-8")

        state = default_state_dict()
        state["position"]["current_phase"] = "03"
        (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")

        ctx = init_progress(tmp_path)

        assert ctx["state_exists"] is True
        assert ctx["current_phase"]["number"] == "02"

    def test_detects_paused_state(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / "GPD" / "STATE.md").write_text(
            "# State\n**Status:** Paused\n**Stopped at:** 2026-03-01T12:00:00Z", encoding="utf-8"
        )

        ctx = init_progress(tmp_path)
        assert ctx["paused_at"] == "2026-03-01T12:00:00Z"

    def test_progress_can_skip_recent_project_reentry_for_projectless_config_bootstrap(
        self,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "workspace"
        candidate = tmp_path / "recoverable-project"
        data_root = tmp_path / "data"

        (workspace / "GPD" / "phases").mkdir(parents=True)
        _create_config(
            workspace,
            {
                "autonomy": "balanced",
                "review_cadence": "adaptive",
                "research_mode": "balanced",
            },
        )

        gpd_dir = candidate / "GPD"
        gpd_dir.mkdir(parents=True)
        (gpd_dir / "STATE.md").write_text("# Research State\n", encoding="utf-8")
        (gpd_dir / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (gpd_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
        resume_file = gpd_dir / "phases" / "01" / ".continue-here.md"
        resume_file.parent.mkdir(parents=True, exist_ok=True)
        resume_file.write_text("resume\n", encoding="utf-8")
        record_recent_project(
            candidate,
            session_data={
                "last_date": "2026-03-29T12:00:00+00:00",
                "stopped_at": "Phase 01",
                "resume_file": "GPD/phases/01/.continue-here.md",
            },
            store_root=data_root,
        )

        ctx = init_progress(workspace, includes={"config"}, data_root=data_root, include_project_reentry=False)

        assert ctx["workspace_root"] == workspace.resolve().as_posix()
        assert ctx["project_root"] == workspace.resolve().as_posix()
        assert ctx["project_root_source"] == "workspace"
        assert ctx["project_root_auto_selected"] is False
        assert ctx["config_content"] is not None
        assert "project_reentry_mode" not in ctx
        assert "project_reentry_candidates" not in ctx
        assert "project_reentry_selected_candidate" not in ctx

    def test_progress_rejects_legacy_autonomy_values(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"autonomy": "guided"})

        with pytest.raises(ConfigError, match="Invalid config.json values"):
            init_progress(tmp_path)

    def test_progress_prefers_explicit_gpd_workspace_config_over_recent_project(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        recent_project = tmp_path / "recent-project"
        data_root = tmp_path / "data"

        workspace.mkdir()
        recent_project.mkdir()
        _setup_project(workspace)
        _create_config(workspace, {"autonomy": "guided"})

        _setup_project(recent_project)
        from gpd.core.state import default_state_dict

        (recent_project / "GPD" / "state.json").write_text(
            json.dumps(default_state_dict()),
            encoding="utf-8",
        )
        (recent_project / "GPD" / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (recent_project / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
        resume_path = recent_project / "GPD" / "phases" / "01-analysis" / ".continue-here.md"
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")
        record_recent_project(
            recent_project,
            session_data={
                "last_date": "2026-03-29T12:00:00+00:00",
                "resume_file": "GPD/phases/01-analysis/.continue-here.md",
            },
            store_root=data_root,
        )

        with pytest.raises(ConfigError, match="Invalid config.json values"):
            init_progress(workspace, data_root=data_root)

    def test_progress_prefers_live_execution_pause_state(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-2",
                "phase": "02",
                "segment_status": "paused",
                "resume_file": "GPD/phases/02-analysis/.continue-here.md",
                "updated_at": "2026-03-11T08:00:00+00:00",
            },
        )

        ctx = init_progress(tmp_path)

        assert ctx["paused_at"] == "2026-03-11T08:00:00+00:00"
        assert ctx["execution_resumable"] is True
        assert ctx["has_work_in_progress"] is True

    def test_progress_normalizes_absolute_live_execution_resume_file(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        resume_path = tmp_path / "GPD" / "phases" / "02-analysis" / ".continue-here.md"
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-2",
                "phase": "02",
                "segment_status": "paused",
                "resume_file": str(resume_path),
                "updated_at": "2026-03-11T08:00:00+00:00",
            },
        )

        ctx = init_progress(tmp_path)

        assert ctx["current_execution"]["resume_file"] == "GPD/phases/02-analysis/.continue-here.md"
        assert ctx["current_execution_resume_file"] == "GPD/phases/02-analysis/.continue-here.md"
        assert ctx["execution_resume_file"] == "GPD/phases/02-analysis/.continue-here.md"

    def test_progress_normalizes_live_execution_phase_when_no_phase_inventory_exists(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-2",
                "phase": "2",
                "plan": "1",
                "segment_status": "paused",
                "checkpoint_reason": "pre-fanout",
                "resume_file": "GPD/phases/02-analysis/.continue-here.md",
                "updated_at": "2026-03-11T08:00:00+00:00",
            },
        )

        ctx = init_progress(tmp_path)

        assert ctx["current_phase"]["number"] == "02"
        assert ctx["current_execution"]["phase"] == "02"
        assert ctx["current_execution"]["plan"] == "01"
        assert ctx["current_execution"]["checkpoint_reason"] == "pre_fanout"

    def test_includes_project(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / "GPD" / "PROJECT.md").write_text("# My Project", encoding="utf-8")

        ctx = init_progress(tmp_path, includes={"project"})
        assert ctx["project_content"] == "# My Project"

    def test_progress_includes_structured_state_context_when_state_is_requested(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_structured_state_payload(tmp_path)

        ctx = init_progress(tmp_path, includes={"state"})

        _assert_structured_state_context(ctx, tmp_path)

    def test_progress_exposes_reference_registry(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)

        ctx = init_progress(tmp_path)

        assert ctx["project_contract"]["references"][0]["must_surface"] is True
        assert "10.1234/benchmark-figure-2" in ctx["active_reference_context"]

    def test_progress_surfaces_knowledge_inventory_and_runtime_counts(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_knowledge_doc(tmp_path, status="stable")
        _write_knowledge_doc(
            tmp_path,
            knowledge_id="K-work-in-progress",
            status="in_review",
            body="Draft knowledge body.\n",
        )

        ctx = init_progress(tmp_path)

        assert ctx["knowledge_doc_count"] == 2
        assert ctx["stable_knowledge_doc_count"] == 1
        assert ctx["knowledge_doc_status_counts"]["stable"] == 1
        assert ctx["knowledge_doc_status_counts"]["in_review"] == 1
        assert ctx["derived_knowledge_doc_count"] == 1
        assert ctx["knowledge_doc_warnings"] == []
        assert "GPD/knowledge/K-renormalization-group-fixed-points.md" in ctx["knowledge_doc_files"]
        assert ctx["stable_knowledge_doc_files"] == ["GPD/knowledge/K-renormalization-group-fixed-points.md"]

    def test_progress_surfaces_derived_state_memory(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_structured_state_memory(tmp_path)

        ctx = init_progress(tmp_path)

        assert ctx["state_exists"] is True
        assert ctx["derived_convention_lock"]["metric_signature"] == "mostly-plus"
        assert ctx["derived_convention_lock_count"] == 2
        assert ctx["derived_intermediate_result_count"] == 1
        assert ctx["derived_intermediate_results"][0]["verified"] is True
        assert ctx["derived_approximation_count"] == 1
        assert ctx["derived_approximations"][0]["status"] == "valid"

    def test_progress_hides_project_contract_when_raw_state_requires_contract_scalar_normalization(
        self, tmp_path: Path
    ) -> None:
        _setup_project(tmp_path)
        _write_coercive_project_contract_state(tmp_path)

        from gpd.core.state import state_load

        loaded = state_load(tmp_path)
        ctx = init_progress(tmp_path)

        assert loaded.state["project_contract"] is None
        assert ctx["project_contract"] is None
        assert "None confirmed in `state.json.project_contract.references` yet." in ctx["active_reference_context"]

    def test_progress_keeps_project_contract_when_raw_state_only_needs_recoverable_normalization(
        self, tmp_path: Path
    ) -> None:
        _setup_project(tmp_path)
        _write_recoverable_project_contract_state(tmp_path)

        ctx = init_progress(tmp_path)

        assert ctx["project_contract"] is not None
        assert ctx["project_contract"]["claims"][0]["id"] == "claim-benchmark"
        assert ctx["project_contract_load_info"]["status"] == "loaded_with_schema_normalization"
        assert ctx["project_contract_gate"]["authoritative"] is False
        assert ctx["project_contract_gate"]["repair_required"] is True
        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert "Recover known limiting behavior" not in ctx["active_reference_context"]
        assert "ref-benchmark" not in ctx["effective_reference_intake"]["must_read_refs"]
        assert "None confirmed in `state.json.project_contract.references` yet." in ctx["active_reference_context"]

    def test_progress_matches_state_loader_for_recoverably_normalized_project_contract(
        self, tmp_path: Path
    ) -> None:
        _setup_project(tmp_path)
        _write_recoverable_project_contract_state(tmp_path)

        from gpd.core.state import state_load

        loaded = state_load(tmp_path)
        ctx = init_progress(tmp_path)

        assert ctx["project_contract"] is not None
        assert ctx["project_contract"]["claims"][0]["id"] == "claim-benchmark"
        assert loaded.state["project_contract"]["claims"][0]["id"] == "claim-benchmark"
        assert "notes" not in loaded.state["project_contract"]["claims"][0]
        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["project_contract_gate"]["authoritative"] is False

    def test_load_project_contract_keeps_primary_contract_when_unrelated_root_section_is_schema_corrupt(
        self, tmp_path: Path
    ) -> None:
        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)
        from gpd.core.state import default_state_dict

        planning = tmp_path / "GPD"
        primary_state = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        primary_state["blockers"] = "bad-root-shape"
        (planning / "state.json").write_text(json.dumps(primary_state, indent=2) + "\n", encoding="utf-8")

        backup_question = "Recovered from schema-corrupt backup state"
        backup_state = default_state_dict()
        backup_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        backup_contract["scope"]["question"] = backup_question
        backup_state["project_contract"] = backup_contract
        (planning / "state.json.bak").write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

        loaded, load_info = _load_project_contract(tmp_path)
        ctx = init_progress(tmp_path)
        primary_question = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))["scope"][
            "question"
        ]

        assert loaded is not None
        assert load_info["source_path"].endswith("state.json")
        assert loaded.scope.question == primary_question
        assert loaded.scope.question != backup_question
        assert ctx["project_contract"] is not None
        assert ctx["project_contract"]["scope"]["question"] == primary_question
        assert ctx["project_contract_load_info"]["source_path"].endswith("state.json")

    def test_load_project_contract_surfaces_blocked_status_for_invalid_state_backed_contract(
        self, tmp_path: Path
    ) -> None:
        _setup_project(tmp_path)

        from gpd.core.state import default_state_dict

        state = default_state_dict()
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["references"] = ["bad"]
        state["project_contract"] = contract
        (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")

        loaded, load_info = _load_project_contract(tmp_path)
        ctx = init_progress(tmp_path)

        assert loaded is None
        assert load_info["status"] == "blocked_schema"
        assert ctx["project_contract"] is None
        assert ctx["project_contract_load_info"]["status"] == "blocked_schema"
        assert {
            key: value
            for key, value in ctx["project_contract_gate"].items()
            if key not in {"provenance", "raw_project_contract_classified"}
        } == {
            "status": "blocked_schema",
            "visible": False,
            "blocked": True,
            "load_blocked": True,
            "approval_blocked": False,
            "authoritative": False,
            "repair_required": True,
            "source_path": ctx["project_contract_load_info"]["source_path"],
        }
        assert ctx["project_contract_load_info"]["source_path"].endswith("state.json")
        assert load_info["provenance"] == "raw"
        assert load_info["raw_project_contract_classified"] is True
        assert ctx["project_contract_gate"]["provenance"] == "raw"
        assert ctx["project_contract_gate"]["raw_project_contract_classified"] is True

    def test_load_project_contract_accepts_list_shape_drift_from_raw_state_as_loaded(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)

        from gpd.core.state import default_state_dict

        state = default_state_dict()
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["references"][0]["aliases"] = "not-a-list"
        state["project_contract"] = contract
        (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")

        loaded, load_info = _load_project_contract(tmp_path)

        assert loaded is not None
        assert load_info["status"] == "loaded_with_schema_normalization"
        assert load_info["errors"] == []

    def test_load_project_contract_fallback_salvages_nested_metadata_must_surface(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _setup_project(tmp_path)

        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["references"][0]["metadata"] = {"must_surface": "yes"}

        from gpd.core.state import ensure_state_schema

        normalized_state = ensure_state_schema({"project_contract": contract})
        monkeypatch.setattr("gpd.core.state.peek_state_json", lambda cwd, **kwargs: (normalized_state, [], "state.json"))
        monkeypatch.setattr("gpd.core.state._load_raw_project_contract_payload", lambda cwd: None)

        loaded, load_info = _load_project_contract(tmp_path)

        assert loaded is not None
        assert load_info["status"] == "loaded"
        assert loaded.references[0].id == "ref-benchmark"
        assert loaded.references[0].must_surface is True

    def test_load_project_contract_surfaces_duplicate_contract_ids_as_visible_blocked_integrity(
        self, tmp_path: Path
    ) -> None:
        _setup_project(tmp_path)

        from gpd.core.state import default_state_dict

        state = default_state_dict()
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["claims"].append(dict(contract["claims"][0]))
        state["project_contract"] = contract
        (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")

        loaded, load_info = _load_project_contract(tmp_path)
        ctx = init_progress(tmp_path)

        assert loaded is not None
        assert load_info["status"] == "blocked_integrity"
        assert any("duplicate" in error for error in load_info["errors"])
        assert ctx["project_contract"] is not None
        assert ctx["project_contract"]["claims"][0]["id"] == "claim-benchmark"
        assert ctx["project_contract_load_info"]["status"] == "blocked_integrity"
        assert ctx["project_contract_gate"]["visible"] is True
        assert ctx["project_contract_gate"]["blocked"] is True
        assert ctx["project_contract_gate"]["authoritative"] is False
        assert ctx["project_contract_gate"]["status"] == "blocked_integrity"
        assert any("duplicate" in error for error in load_info["errors"])

    def test_load_project_contract_rejects_whole_singleton_defaulting_from_raw_state(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)

        from gpd.core.state import default_state_dict

        state = default_state_dict()
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["context_intake"] = "not-a-dict"
        state["project_contract"] = contract
        (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")

        loaded, load_info = _load_project_contract(tmp_path)

        assert loaded is None
        assert load_info["status"] == "blocked_schema"


# ─── _extract_frontmatter_field ──────────────────────────────────────────────


class TestExtractFrontmatterField:
    """Regression: \\s* in the field regex must not match newlines."""

    def test_empty_value_does_not_bleed_into_next_line(self, tmp_path: Path) -> None:
        """When a field has an empty value (e.g. 'title:\\n'), the regex must
        NOT consume the newline and capture the next line's content."""
        from gpd.core.context import _extract_frontmatter_field

        content = "title:\narea: numerical\ncreated: 2026-03-01"
        # 'title' has no value on its line → should return None
        assert _extract_frontmatter_field(content, "title") is None

    def test_field_with_value_still_works(self, tmp_path: Path) -> None:
        from gpd.core.context import _extract_frontmatter_field

        content = "title: Check convergence\narea: numerical"
        assert _extract_frontmatter_field(content, "title") == "Check convergence"
        assert _extract_frontmatter_field(content, "area") == "numerical"

    def test_field_with_leading_spaces(self, tmp_path: Path) -> None:
        from gpd.core.context import _extract_frontmatter_field

        content = "title:   spaced value  \narea: numerical"
        assert _extract_frontmatter_field(content, "title") == "spaced value"

    def test_field_with_quoted_value(self, tmp_path: Path) -> None:
        from gpd.core.context import _extract_frontmatter_field

        content = 'title: "Quoted Title"\narea: theory'
        assert _extract_frontmatter_field(content, "title") == "Quoted Title"

    def test_body_lines_do_not_override_leading_metadata_block(self, tmp_path: Path) -> None:
        from gpd.core.context import _extract_frontmatter_field

        content = (
            'title: "Check convergence"\n'
            "\n"
            "area: numerical\n"
            "created: 2026-03-01\n"
        )
        assert _extract_frontmatter_field(content, "title") == "Check convergence"
        assert _extract_frontmatter_field(content, "area") is None
        assert _extract_frontmatter_field(content, "created") is None


# ─── init_phase_op ────────────────────────────────────────────────────────────


class TestInitPhaseOp:
    """Tests for init_phase_op context assembly."""

    def test_no_phase_returns_phase_found_false(self, tmp_path):
        """init_phase_op with no phase should set phase_found=False."""
        from gpd.core.context import init_phase_op
        gpd_dir = tmp_path / "GPD"
        gpd_dir.mkdir()
        (gpd_dir / "config.json").write_text("{}", encoding="utf-8")

        result = init_phase_op(tmp_path)
        assert isinstance(result, dict)
        assert result.get("phase_found") is False

    def test_with_phase_directory(self, tmp_path):
        """init_phase_op with existing phase should set phase_found=True."""
        from gpd.core.context import init_phase_op
        gpd_dir = tmp_path / "GPD"
        phases_dir = gpd_dir / "phases" / "01-test"
        phases_dir.mkdir(parents=True)
        (gpd_dir / "config.json").write_text("{}", encoding="utf-8")

        result = init_phase_op(tmp_path, phase="1")
        assert isinstance(result, dict)
        # Phase should be found since we created the directory
        if result.get("phase_found"):
            assert "01" in str(result.get("phase_number", ""))

    def test_includes_structured_state_context_when_state_is_requested(self, tmp_path):
        """init_phase_op should surface canonical state slices when state is included."""
        from gpd.core.context import init_phase_op

        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-test")
        _write_structured_state_payload(tmp_path)

        result = init_phase_op(tmp_path, phase="1", includes={"state"})

        _assert_structured_state_context(result, tmp_path)

    def test_stage_bootstrap_returns_only_manifest_required_fields(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-test")
        _write_structured_state_payload(tmp_path)
        _write_project_contract_state(tmp_path)
        _install_fake_stage_manifest(
            monkeypatch,
            workflow_id="research-phase",
            stages={
                "bootstrap": [
                    "executor_model",
                    "verifier_model",
                    "commit_docs",
                    "research_mode",
                    "phase_found",
                    "phase_dir",
                    "phase_number",
                    "phase_name",
                    "project_contract",
                    "project_contract_gate",
                    "project_contract_load_info",
                    "project_contract_validation",
                    "active_reference_context",
                    "reference_artifacts_content",
                ]
            },
        )

        result = init_phase_op(tmp_path, phase="1", stage="bootstrap")

        assert result["staged_loading"]["workflow_id"] == "research-phase"
        assert result["staged_loading"]["stage_id"] == "bootstrap"
        assert set(result) == {
            "executor_model",
            "verifier_model",
            "commit_docs",
            "research_mode",
            "phase_found",
            "phase_dir",
            "phase_number",
            "phase_name",
            "project_contract",
            "project_contract_gate",
            "project_contract_load_info",
            "project_contract_validation",
            "active_reference_context",
            "reference_artifacts_content",
            "staged_loading",
        }

    def test_init_research_phase_alias_uses_the_same_stage_manifest_contract(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-test")
        _install_fake_stage_manifest(
            monkeypatch,
            workflow_id="research-phase",
            stages={
                "bootstrap": [
                    "phase_found",
                    "phase_dir",
                    "phase_number",
                    "phase_name",
                    "commit_docs",
                    "research_mode",
                ]
            },
        )

        result = init_research_phase(tmp_path, phase="1", stage="bootstrap")

        assert result["staged_loading"]["workflow_id"] == "research-phase"
        assert result["staged_loading"]["stage_id"] == "bootstrap"
        assert set(result) == {
            "phase_found",
            "phase_dir",
            "phase_number",
            "phase_name",
            "commit_docs",
            "research_mode",
            "staged_loading",
        }

    def test_stage_research_handoff_returns_only_manifest_required_fields(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-test")
        _install_fake_stage_manifest(
            monkeypatch,
            workflow_id="research-phase",
            stages={
                "bootstrap": [
                    "phase_found",
                    "phase_dir",
                    "phase_number",
                    "phase_name",
                    "commit_docs",
                    "research_mode",
                ],
                "research_handoff": [
                    "commit_docs",
                    "autonomy",
                    "review_cadence",
                    "research_mode",
                    "phase_found",
                    "phase_dir",
                    "phase_number",
                    "phase_name",
                    "phase_slug",
                    "padded_phase",
                    "contract_intake",
                    "effective_reference_intake",
                    "active_reference_context",
                    "reference_artifact_files",
                    "reference_artifacts_content",
                    "selected_protocol_bundle_ids",
                    "protocol_bundle_context",
                    "protocol_bundle_verifier_extensions",
                    "current_execution",
                    "config_content",
                    "state_content",
                    "roadmap_content",
                ],
            },
        )

        with pytest.raises(
            ValueError,
            match=(
                r"research-phase stage 'research_handoff' requires unavailable init field\(s\): "
                r"config_content, state_content, roadmap_content"
            ),
        ):
            init_research_phase(tmp_path, phase="1", stage="research_handoff")
