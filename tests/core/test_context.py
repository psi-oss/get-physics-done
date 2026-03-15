"""Tests for gpd.core.context — context assembly for AI agent commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.context import (
    _generate_slug,
    _is_phase_complete,
    _normalize_phase_name,
    init_execute_phase,
    init_map_research,
    init_milestone_op,
    init_new_milestone,
    init_new_project,
    init_plan_phase,
    init_progress,
    init_quick,
    init_resume,
    init_todos,
    init_verify_work,
    load_config,
)
from gpd.core.errors import ConfigError, ValidationError

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"

# ─── Helpers ───────────────────────────────────────────────────────────────────


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project structure and return project root."""
    planning = tmp_path / ".gpd"
    planning.mkdir()
    (planning / "phases").mkdir()
    return tmp_path


def _create_phase_dir(tmp_path: Path, name: str) -> Path:
    """Create a phase directory and return its path."""
    phase_dir = tmp_path / ".gpd" / "phases" / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir


def _create_config(tmp_path: Path, config: dict) -> Path:
    """Write config.json and return its path."""
    config_path = tmp_path / ".gpd" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config))
    return config_path


def _create_roadmap(tmp_path: Path, content: str) -> Path:
    """Write ROADMAP.md and return its path."""
    roadmap = tmp_path / ".gpd" / "ROADMAP.md"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(content)
    return roadmap


def _write_project_contract_state(tmp_path: Path) -> None:
    """Persist the Stage 0 project contract fixture into state.json."""
    from gpd.core.state import default_state_dict

    state = default_state_dict()
    state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    (tmp_path / ".gpd" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_stat_mech_project(tmp_path: Path) -> None:
    project = tmp_path / ".gpd" / "PROJECT.md"
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
        "scope": {
            "question": "What finite-size scaling collapse and benchmark comparison does the simulation recover?",
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
                "required_actions": ["read", "compare", "cite"],
            }
        ],
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
    (tmp_path / ".gpd" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_numerical_relativity_project(tmp_path: Path) -> None:
    project = tmp_path / ".gpd" / "PROJECT.md"
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
        "scope": {
            "question": "Does the BSSN evolution reproduce benchmark waveform and remnant behavior?",
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
                "locator": "Trusted numerical-relativity waveform catalog",
                "role": "benchmark",
                "why_it_matters": "Provides decisive waveform and remnant anchors",
                "required_actions": ["read", "compare", "cite"],
            }
        ],
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
    (tmp_path / ".gpd" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_current_execution(tmp_path: Path, payload: dict[str, object]) -> None:
    observability = tmp_path / ".gpd" / "observability"
    observability.mkdir(parents=True, exist_ok=True)
    (observability / "current-execution.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_literature_review_anchor_file(tmp_path: Path) -> None:
    literature_dir = tmp_path / ".gpd" / "literature"
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


def _write_research_map_anchor_files(tmp_path: Path) -> None:
    map_dir = tmp_path / ".gpd" / "research-map"
    map_dir.mkdir(parents=True, exist_ok=True)
    (map_dir / "REFERENCES.md").write_text(
        """# Reference and Anchor Map

## Active Anchor Registry

| Anchor | Type | Source / Locator | What It Constrains | Required Action | Carry Forward To |
| ------ | ---- | ---------------- | ------------------ | --------------- | ---------------- |
| prior-baseline | prior artifact | `.gpd/phases/01-test-phase/01-SUMMARY.md` | Baseline summary for calibration and later comparisons | use | planning/execution |
| benchmark-paper | benchmark | Author et al., Journal, 2024 | Published comparison target for the decisive observable | read/compare/cite | verification/writing |

## Benchmarks and Comparison Targets

- Universal crossing window
  - Source: Author et al., Journal, 2024
  - Compared in: `.gpd/phases/01-test-phase/01-SUMMARY.md`
  - Status: pending

## Prior Artifacts and Baselines

- `.gpd/phases/01-test-phase/01-SUMMARY.md`: Prior baseline summary that later phases must keep visible

## Open Reference Questions

- Need collaboration note with the definitive normalization
""",
        encoding="utf-8",
    )
    (map_dir / "VALIDATION.md").write_text(
        """# Validation and Cross-Checks

## Comparison with Literature

- Result from Author et al., Journal, 2024: agreement still needs confirmation
  - Comparison in: `.gpd/phases/01-test-phase/01-SUMMARY.md`
""",
        encoding="utf-8",
    )


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

    def test_custom_config(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"autonomy": "yolo", "review_cadence": "dense", "research_mode": "exploit"})
        config = load_config(tmp_path)
        assert config["autonomy"] == "yolo"
        assert config["review_cadence"] == "dense"
        assert config["research_mode"] == "exploit"

    def test_nested_config(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"workflow": {"research": False, "plan_checker": False}})
        config = load_config(tmp_path)
        assert config["research"] is False
        assert config["plan_checker"] is False

    def test_parallelization_bool(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"parallelization": False})
        config = load_config(tmp_path)
        assert config["parallelization"] is False

    def test_malformed_config_raises(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        config_path = tmp_path / ".gpd" / "config.json"
        config_path.write_text("not valid json {{{")
        with pytest.raises(ConfigError, match="Malformed config.json"):
            load_config(tmp_path)


# ─── init_execute_phase ────────────────────────────────────────────────────────


class TestInitExecutePhase:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan")
        (phase_dir / "a-SUMMARY.md").write_text("summary")

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
        (tmp_path / ".gpd" / "STATE.md").write_text("# State\nstuff")

        ctx = init_execute_phase(tmp_path, "1", includes={"state"})
        assert ctx["state_content"] == "# State\nstuff"

    def test_json_only_state_counts_as_existing(self, tmp_path: Path) -> None:
        from gpd.core.state import default_state_dict

        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan")
        (tmp_path / ".gpd" / "state.json").write_text(json.dumps(default_state_dict()), encoding="utf-8")

        ctx = init_execute_phase(tmp_path, "1")

        assert ctx["state_exists"] is True

    def test_surfaces_active_reference_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan")
        _write_project_contract_state(tmp_path)

        ctx = init_execute_phase(tmp_path, "1")

        assert ctx["project_contract"]["references"][0]["id"] == "ref-benchmark"
        assert "Published comparison target" in ctx["active_reference_context"]

    def test_ingests_reference_artifacts_without_project_contract(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan")
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_execute_phase(tmp_path, "1")

        assert ctx["project_contract"] is None
        assert ctx["derived_active_reference_count"] >= 2
        assert ctx["active_reference_count"] >= 2
        assert "Benchmark Ref 2024" in ctx["active_reference_context"]
        assert ".gpd/phases/01-test-phase/01-SUMMARY.md" in ctx["active_reference_context"]
        assert ".gpd/research-map/REFERENCES.md" in ctx["active_reference_context"]
        assert "critical slope" in "\n".join(ctx["effective_reference_intake"]["known_good_baselines"])
        assert ".gpd/phases/01-test-phase/01-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]

    def test_surfaces_live_execution_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan")
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
        (phase_dir / "a-PLAN.md").write_text("plan")
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
        (phase_dir / "a-PLAN.md").write_text("plan")
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
        (phase_dir / "a-PLAN.md").write_text("plan")
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
        (phase_dir / "a-PLAN.md").write_text("plan")
        _write_stat_mech_project(tmp_path)
        _write_bundle_ready_contract_state(tmp_path)

        ctx = init_execute_phase(tmp_path, "1")
        checklist = get_bundle_checklist(ctx["selected_protocol_bundle_ids"])

        assert checklist["found"] is True
        assert checklist["bundle_checks"] == ctx["protocol_bundle_verifier_extensions"]


# ─── init_plan_phase ──────────────────────────────────────────────────────────


class TestInitPlanPhase:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "02-analysis")
        (phase_dir / "RESEARCH.md").write_text("research")

        ctx = init_plan_phase(tmp_path, "2")
        assert ctx["phase_found"] is True
        assert ctx["phase_number"] == "02"
        assert ctx["has_research"] is True
        assert ctx["has_plans"] is False
        assert ctx["padded_phase"] == "02"

    def test_includes_research(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "02-analysis")
        (phase_dir / "RESEARCH.md").write_text("findings here")

        ctx = init_plan_phase(tmp_path, "2", includes={"research"})
        assert ctx["research_content"] == "findings here"

    def test_surfaces_active_reference_context_and_reference_artifacts(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        literature_dir = tmp_path / ".gpd" / "literature"
        literature_dir.mkdir()
        (literature_dir / "benchmark-REVIEW.md").write_text("# Literature Review\nbenchmark details")
        map_dir = tmp_path / ".gpd" / "research-map"
        map_dir.mkdir()
        (map_dir / "REFERENCES.md").write_text("# References Map\nanchor registry")
        (map_dir / "VALIDATION.md").write_text("# Validation Map\nbenchmark checks")

        ctx = init_plan_phase(tmp_path, "2")

        assert ctx["project_contract"]["references"][0]["id"] == "ref-benchmark"
        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert ctx["active_reference_count"] == 1
        assert "[ref-benchmark]" in ctx["active_reference_context"]
        assert ".gpd/literature/benchmark-REVIEW.md" in ctx["literature_review_files"]
        assert ".gpd/research-map/REFERENCES.md" in ctx["research_map_reference_files"]
        assert ".gpd/research-map/VALIDATION.md" in ctx["reference_artifact_files"]
        assert "benchmark details" in ctx["reference_artifacts_content"]
        assert "anchor registry" in ctx["reference_artifacts_content"]

    def test_merges_contract_and_artifact_reference_intake(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_plan_phase(tmp_path, "2")

        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark", "lit-anchor-benchmark-ref-2024"]
        assert "ref-benchmark" in ctx["effective_reference_intake"]["must_read_refs"]
        assert "lit-anchor-benchmark-ref-2024" in ctx["effective_reference_intake"]["must_read_refs"]
        assert "benchmark-paper" not in ctx["effective_reference_intake"]["must_read_refs"]
        assert ".gpd/phases/01-test-phase/01-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]
        assert ctx["active_reference_count"] >= ctx["derived_active_reference_count"]
        assert ".gpd/research-map/REFERENCES.md" in ctx["active_reference_context"]
        assert "unresolved reference token" not in ctx["active_reference_context"]

    def test_merges_structured_reference_fields_into_project_contract(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_plan_phase(tmp_path, "2")
        references = {ref["id"]: ref for ref in ctx["project_contract"]["references"]}

        assert references["ref-benchmark"]["aliases"] == ["benchmark-paper"]
        assert references["ref-benchmark"]["applies_to"] == ["claim-benchmark"]
        assert references["ref-benchmark"]["carry_forward_to"] == ["verification", "writing"]
        assert references["ref-benchmark"]["required_actions"] == ["read", "compare", "cite"]
        assert references["ref-benchmark"]["must_surface"] is True
        assert references["prior-baseline"]["kind"] == "prior_artifact"
        assert references["prior-baseline"]["required_actions"] == ["use"]
        assert references["prior-baseline"]["carry_forward_to"] == ["planning", "execution"]

    def test_does_not_persist_canonical_reference_merges(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "02-analysis")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        state_path = tmp_path / ".gpd" / "state.json"
        before = state_path.read_text(encoding="utf-8")

        ctx = init_plan_phase(tmp_path, "2")

        after = state_path.read_text(encoding="utf-8")
        stored = json.loads(after)

        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark", "lit-anchor-benchmark-ref-2024"]
        assert stored["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
        assert before == after
        assert not (tmp_path / ".gpd" / "STATE.md").exists()

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
        assert ctx["has_existing_project"] is False
        assert ctx["planning_exists"] is False

    def test_detects_research_files(self, tmp_path: Path) -> None:
        (tmp_path / "calc.py").write_text("import numpy")
        ctx = init_new_project(tmp_path)
        assert ctx["has_research_files"] is True
        assert ctx["has_existing_project"] is True

    def test_ignores_runtime_owned_dirs_when_detecting_research_files(self, tmp_path: Path) -> None:
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".codex" / "calc.py").write_text("print('runtime mirror')", encoding="utf-8")
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "notes.py").write_text("print('runtime mirror')", encoding="utf-8")
        (tmp_path / ".config" / "opencode").mkdir(parents=True)
        (tmp_path / ".config" / "opencode" / "script.py").write_text("print('runtime mirror')", encoding="utf-8")

        ctx = init_new_project(tmp_path)

        assert ctx["has_research_files"] is False
        assert ctx["has_existing_project"] is False

    def test_detects_manifest(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]")
        ctx = init_new_project(tmp_path)
        assert ctx["has_project_manifest"] is True


# ─── init_new_milestone ───────────────────────────────────────────────────────


class TestInitNewMilestone:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Setup Phase\n")

        ctx = init_new_milestone(tmp_path)
        assert ctx["current_milestone"] == "v1.0"
        assert ctx["current_milestone_name"] == "Setup Phase"

    def test_surfaces_project_contract_and_effective_reference_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Setup Phase\n")
        _write_project_contract_state(tmp_path)
        _write_literature_review_anchor_file(tmp_path)
        _write_research_map_anchor_files(tmp_path)

        ctx = init_new_milestone(tmp_path)

        assert ctx["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
        assert ctx["contract_intake"]["must_read_refs"] == ["ref-benchmark", "lit-anchor-benchmark-ref-2024"]
        assert "ref-benchmark" in ctx["effective_reference_intake"]["must_read_refs"]
        assert ".gpd/phases/01-test-phase/01-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]
        assert "Benchmark Ref 2024" in ctx["active_reference_context"]
        assert ".gpd/research-map/REFERENCES.md" in ctx["reference_artifact_files"]


# ─── init_quick ───────────────────────────────────────────────────────────────


class TestInitQuick:
    def test_first_quick_task(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_quick(tmp_path, "Fix tensor product calculation")
        assert ctx["next_num"] == 1
        assert ctx["slug"] is not None
        assert "fix" in ctx["slug"]
        assert ctx["task_dir"] is not None

    def test_increments_number(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        quick_dir = tmp_path / ".gpd" / "quick"
        quick_dir.mkdir()
        (quick_dir / "1-first-task").mkdir()
        (quick_dir / "2-second-task").mkdir()

        ctx = init_quick(tmp_path, "next task")
        assert ctx["next_num"] == 3

    def test_permission_error_on_quick_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _setup_project(tmp_path)
        quick_dir = tmp_path / ".gpd" / "quick"
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
        (tmp_path / ".gpd" / "current-agent-id.txt").write_text("agent-123\n")

        ctx = init_resume(tmp_path)
        assert ctx["has_interrupted_agent"] is True
        assert ctx["interrupted_agent_id"] == "agent-123"

    def test_json_only_state_counts_as_existing(self, tmp_path: Path) -> None:
        from gpd.core.state import default_state_dict

        _setup_project(tmp_path)
        (tmp_path / ".gpd" / "state.json").write_text(json.dumps(default_state_dict()), encoding="utf-8")

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
                "resume_file": ".gpd/phases/03-analysis/.continue-here.md",
                "updated_at": "2026-03-10T12:00:00+00:00",
            },
        )

        ctx = init_resume(tmp_path)

        assert ctx["resume_mode"] == "bounded_segment"
        assert ctx["active_execution_segment"]["segment_id"] == "seg-4"
        assert ctx["segment_candidates"][0]["source"] == "current_execution"

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
                "checkpoint_reason": "pre-fanout",
                "pre_fanout_review_pending": True,
                "updated_at": "2026-03-10T12:00:00+00:00",
            },
        )

        ctx = init_resume(tmp_path)

        assert ctx["active_execution_segment"]["phase"] == "03"
        assert ctx["active_execution_segment"]["plan"] == "02"
        assert ctx["active_execution_segment"]["checkpoint_reason"] == "pre_fanout"
        candidate = ctx["segment_candidates"][0]
        assert candidate["phase"] == "03"
        assert candidate["plan"] == "02"
        assert candidate["checkpoint_reason"] == "pre_fanout"

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

        assert ctx["resume_mode"] == "bounded_segment"
        assert ctx["execution_pre_fanout_review_pending"] is True
        assert ctx["execution_skeptical_requestioning_required"] is True
        candidate = ctx["segment_candidates"][0]
        assert candidate["checkpoint_reason"] == "pre_fanout"
        assert candidate["pre_fanout_review_pending"] is True
        assert candidate["skeptical_requestioning_required"] is True
        assert candidate["weakest_unchecked_anchor"] == "Ref-01 benchmark figure"
        assert candidate["disconfirming_observation"] == "Direct observable misses the literature band."
        assert candidate["downstream_locked"] is True

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
                "checkpoint_reason": "pre_fanout",
                "pre_fanout_review_pending": True,
                "pre_fanout_review_cleared": True,
                "downstream_locked": True,
                "updated_at": "2026-03-10T12:00:00+00:00",
            },
        )

        ctx = init_resume(tmp_path)

        assert ctx["resume_mode"] == "bounded_segment"
        assert ctx["execution_pre_fanout_review_pending"] is True
        assert ctx["execution_downstream_locked"] is True
        assert ctx["active_execution_segment"]["pre_fanout_review_cleared"] is True
        assert ctx["segment_candidates"][0]["checkpoint_reason"] == "pre_fanout"
        assert ctx["segment_candidates"][0]["pre_fanout_review_cleared"] is True

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

        assert ctx["resume_mode"] is None
        assert ctx["segment_candidates"] == []
        assert ctx["active_execution_segment"]["segment_id"] == "seg-4"


# ─── init_verify_work ─────────────────────────────────────────────────────────


class TestInitVerifyWork:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "VERIFICATION.md").write_text("verified")

        ctx = init_verify_work(tmp_path, "1")
        assert ctx["phase_found"] is True
        assert ctx["has_verification"] is True

    def test_missing_phase_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="phase is required"):
            init_verify_work(tmp_path, "")

    def test_exposes_active_reference_context(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_project_contract_state(tmp_path)

        ctx = init_verify_work(tmp_path, "1")

        assert ctx["project_contract"]["references"][0]["role"] == "benchmark"
        assert "## Active Reference Registry" in ctx["active_reference_context"]

    def test_exposes_selected_protocol_bundle_ids(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        _write_stat_mech_project(tmp_path)
        _write_bundle_ready_contract_state(tmp_path)

        ctx = init_verify_work(tmp_path, "1")

        assert "stat-mech-simulation" in ctx["selected_protocol_bundle_ids"]
        assert "Verifier extensions:" in ctx["protocol_bundle_context"]


# ─── init_todos ───────────────────────────────────────────────────────────────


class TestInitTodos:
    def test_empty_todos(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_todos(tmp_path)
        assert ctx["todo_count"] == 0
        assert ctx["todos"] == []

    def test_finds_todos(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        pending = tmp_path / ".gpd" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "check-convergence.md").write_text(
            'title: "Check convergence"\narea: numerical\ncreated: 2026-03-01'
        )

        ctx = init_todos(tmp_path)
        assert ctx["todo_count"] == 1
        assert ctx["todos"][0]["title"] == "Check convergence"
        assert ctx["todos"][0]["area"] == "numerical"

    def test_area_filter(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        pending = tmp_path / ".gpd" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "a.md").write_text("title: A\narea: theory")
        (pending / "b.md").write_text("title: B\narea: numerical")

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

    def test_counts_phases(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        # Complete phase
        p1 = _create_phase_dir(tmp_path, "01-setup")
        (p1 / "a-PLAN.md").write_text("plan")
        (p1 / "a-SUMMARY.md").write_text("summary")
        # Incomplete phase
        p2 = _create_phase_dir(tmp_path, "02-analysis")
        (p2 / "b-PLAN.md").write_text("plan")

        ctx = init_milestone_op(tmp_path)
        assert ctx["phase_count"] == 2
        assert ctx["completed_phases"] == 1
        assert ctx["all_phases_complete"] is False


# ─── init_map_research ────────────────────────────────────────────────────────


class TestInitMapResearch:
    def test_no_maps(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_map_research(tmp_path)
        assert ctx["has_maps"] is False
        assert ctx["existing_maps"] == []

    def test_existing_maps(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        map_dir = tmp_path / ".gpd" / "research-map"
        map_dir.mkdir()
        (map_dir / "theory.md").write_text("# Theory Map")

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
        assert ".gpd/phases/01-test-phase/01-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]


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
        (p1 / "a-PLAN.md").write_text("plan")
        (p1 / "a-SUMMARY.md").write_text("summary")
        # In-progress phase
        p2 = _create_phase_dir(tmp_path, "02-analysis")
        (p2 / "b-PLAN.md").write_text("plan")
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
        (phase_dir / "b-PLAN.md").write_text("plan")

        state = default_state_dict()
        state["position"]["current_phase"] = "03"
        (tmp_path / ".gpd" / "state.json").write_text(json.dumps(state), encoding="utf-8")

        ctx = init_progress(tmp_path)

        assert ctx["state_exists"] is True
        assert ctx["current_phase"]["number"] == "02"

    def test_detects_paused_state(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / ".gpd" / "STATE.md").write_text(
            "# State\n**Status:** Paused\n**Stopped at:** 2026-03-01T12:00:00Z"
        )

        ctx = init_progress(tmp_path)
        assert ctx["paused_at"] == "2026-03-01T12:00:00Z"

    def test_progress_rejects_legacy_autonomy_values(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"autonomy": "guided"})

        with pytest.raises(ConfigError, match="Invalid config.json values"):
            init_progress(tmp_path)

    def test_progress_prefers_live_execution_pause_state(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_current_execution(
            tmp_path,
            {
                "session_id": "sess-2",
                "phase": "02",
                "segment_status": "paused",
                "resume_file": ".gpd/phases/02-analysis/.continue-here.md",
                "updated_at": "2026-03-11T08:00:00+00:00",
            },
        )

        ctx = init_progress(tmp_path)

        assert ctx["paused_at"] == "2026-03-11T08:00:00+00:00"
        assert ctx["execution_resumable"] is True
        assert ctx["has_work_in_progress"] is True

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
                "resume_file": ".gpd/phases/02-analysis/.continue-here.md",
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
        (tmp_path / ".gpd" / "PROJECT.md").write_text("# My Project")

        ctx = init_progress(tmp_path, includes={"project"})
        assert ctx["project_content"] == "# My Project"

    def test_progress_exposes_reference_registry(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_project_contract_state(tmp_path)

        ctx = init_progress(tmp_path)

        assert ctx["project_contract"]["references"][0]["must_surface"] is True
        assert "Recover known limiting behavior" in ctx["active_reference_context"]


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


# ─── init_phase_op ────────────────────────────────────────────────────────────


class TestInitPhaseOp:
    """Tests for init_phase_op context assembly."""

    def test_no_phase_returns_phase_found_false(self, tmp_path):
        """init_phase_op with no phase should set phase_found=False."""
        from gpd.core.context import init_phase_op
        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()
        (gpd_dir / "config.json").write_text("{}", encoding="utf-8")

        result = init_phase_op(tmp_path)
        assert isinstance(result, dict)
        assert result.get("phase_found") is False

    def test_with_phase_directory(self, tmp_path):
        """init_phase_op with existing phase should set phase_found=True."""
        from gpd.core.context import init_phase_op
        gpd_dir = tmp_path / ".gpd"
        phases_dir = gpd_dir / "phases" / "01-test"
        phases_dir.mkdir(parents=True)
        (gpd_dir / "config.json").write_text("{}", encoding="utf-8")

        result = init_phase_op(tmp_path, phase="1")
        assert isinstance(result, dict)
        # Phase should be found since we created the directory
        if result.get("phase_found"):
            assert "01" in str(result.get("phase_number", ""))
