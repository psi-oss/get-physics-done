"""Tests for gpd.strategy.triage_context — PhysicsTriageContext + compute_phase_signal."""

from __future__ import annotations

from unittest.mock import MagicMock

from gpd.strategy.bundle_loader import ActionSpec, BundleLoader, MergedBundle
from gpd.strategy.router import ReferenceRouter
from gpd.strategy.triage_context import (
    PhysicsTriageContext,
    _extract_action_modes,
    _safe_float,
    _safe_int,
    compute_phase_signal,
)

# ---------------------------------------------------------------------------
# compute_phase_signal
# ---------------------------------------------------------------------------


class TestComputePhaseSignal:
    def test_formulation_phase(self):
        result = compute_phase_signal({"budget_fraction_remaining": 0.9, "avg_score": 0.0, "total_visits": 2})
        assert result["phase"] == "formulation"
        assert result["exploration_pressure"] == 0.9

    def test_derivation_phase(self):
        result = compute_phase_signal({"budget_fraction_remaining": 0.5, "avg_score": 30.0, "total_visits": 20})
        assert result["phase"] == "derivation"
        assert 0.0 < result["exploration_pressure"] < 1.0

    def test_validation_low_budget(self):
        result = compute_phase_signal({"budget_fraction_remaining": 0.1, "avg_score": 20.0, "total_visits": 50})
        assert result["phase"] == "validation"
        assert result["exploration_pressure"] == 0.2

    def test_validation_high_score(self):
        result = compute_phase_signal({"budget_fraction_remaining": 0.5, "avg_score": 80.0, "total_visits": 15})
        assert result["phase"] == "validation"

    def test_empty_stats(self):
        result = compute_phase_signal({})
        assert result["phase"] == "formulation"
        assert result["budget_fraction"] == 1.0

    def test_returns_budget_fraction(self):
        result = compute_phase_signal({"budget_fraction_remaining": 0.42})
        assert result["budget_fraction"] == 0.42

    def test_exploration_pressure_rounded(self):
        result = compute_phase_signal({"budget_fraction_remaining": 0.55, "avg_score": 10.0, "total_visits": 20})
        # Should be rounded to 3 decimal places
        pressure = result["exploration_pressure"]
        assert pressure == round(pressure, 3)


# ---------------------------------------------------------------------------
# _extract_action_modes
# ---------------------------------------------------------------------------


class TestExtractActionModes:
    def test_explicit_modes(self):
        action = ActionSpec(
            action_id="Work",
            extra={
                "modes": [
                    {"mode_id": "compute", "summary": "Run computation", "triage_guidance": "Use for math"},
                    {"mode_id": "verify", "summary": "Verify result"},
                ]
            },
        )
        modes = _extract_action_modes(action)
        assert len(modes) == 2
        assert modes[0]["mode_id"] == "compute"
        assert modes[1]["mode_id"] == "verify"

    def test_synthesized_default_mode(self):
        action = ActionSpec(
            action_id="Plan",
            title="Planning Action",
            summary="Plan the approach",
            triage_guidance="Use when you need to plan",
        )
        modes = _extract_action_modes(action)
        assert len(modes) == 1
        assert modes[0]["mode_id"] == "default"
        assert "plan" in modes[0]["triage_guidance"].lower()

    def test_no_modes_no_guidance(self):
        action = ActionSpec(action_id="Empty")
        modes = _extract_action_modes(action)
        assert modes == []

    def test_invalid_modes_skipped(self):
        action = ActionSpec(
            action_id="Bad",
            extra={"modes": [{"no_mode_id": True}, {"mode_id": "ok", "summary": "valid"}]},
        )
        modes = _extract_action_modes(action)
        assert len(modes) == 1
        assert modes[0]["mode_id"] == "ok"

    def test_modes_none_extra(self):
        action = ActionSpec(action_id="NoExtra")
        action.extra = {}
        modes = _extract_action_modes(action)
        assert modes == []


# ---------------------------------------------------------------------------
# _safe_float / _safe_int
# ---------------------------------------------------------------------------


class TestSafeConversions:
    def test_safe_float_valid(self):
        assert _safe_float(3.14, default=0.0) == 3.14

    def test_safe_float_none(self):
        assert _safe_float(None, default=5.0) == 5.0

    def test_safe_float_string(self):
        assert _safe_float("not a number", default=1.0) == 1.0

    def test_safe_float_int_input(self):
        assert _safe_float(42, default=0.0) == 42.0

    def test_safe_int_valid(self):
        assert _safe_int(10, default=0) == 10

    def test_safe_int_none(self):
        assert _safe_int(None, default=99) == 99

    def test_safe_int_string(self):
        assert _safe_int("bad", default=7) == 7


# ---------------------------------------------------------------------------
# PhysicsTriageContext
# ---------------------------------------------------------------------------


def _make_context(
    *,
    domain: str | None = "qft",
    actions: dict[str, ActionSpec] | None = None,
    skills: dict | None = None,
    route_protocol_result: str | None = "perturbation-theory",
) -> PhysicsTriageContext:
    """Build a PhysicsTriageContext with mock dependencies."""
    loader = MagicMock(spec=BundleLoader)
    merged = MagicMock(spec=MergedBundle)
    merged.actions = actions or {
        "Work": ActionSpec(
            action_id="Work",
            title="Work",
            summary="Do work",
            triage_guidance="Use for computation",
        ),
        "Plan": ActionSpec(
            action_id="Plan",
            title="Plan",
            summary="Plan approach",
            triage_guidance="Use for planning",
        ),
    }
    loader.merged = merged
    loader.get_skill_names.return_value = skills or ["dimensional-analysis", "limiting-cases"]

    router = MagicMock(spec=ReferenceRouter)
    router.route_protocol.return_value = route_protocol_result

    return PhysicsTriageContext(
        bundle_loader=loader,
        reference_router=router,
        domain=domain,
    )


class TestPhysicsTriageContext:
    def test_build_context_keys(self):
        ctx = _make_context()
        result = ctx.build_context(
            state={},
            node_id="n1",
            dag_stats={"budget_fraction_remaining": 0.9, "total_visits": 2},
        )
        assert set(result.keys()) == {
            "mode_descriptions",
            "relevant_protocols",
            "recommended_skills",
            "convention_summary",
            "phase_signal",
            "gpd_phase",
            "open_questions",
            "verification_focus",
            "required_tools",
            "shared_claims",
        }

    def test_mode_descriptions(self):
        ctx = _make_context()
        result = ctx.build_context(state={}, node_id="n1", dag_stats={})
        modes = result["mode_descriptions"]
        assert len(modes) == 2
        action_ids = {m["action_id"] for m in modes}
        assert "Work" in action_ids

    def test_relevant_protocols_with_domain(self):
        ctx = _make_context(domain="qft", route_protocol_result="perturbation-theory")
        result = ctx.build_context(state={}, node_id="n1", dag_stats={})
        assert result["relevant_protocols"] == ["perturbation-theory"]

    def test_relevant_protocols_no_domain(self):
        ctx = _make_context(domain=None)
        result = ctx.build_context(state={}, node_id="n1", dag_stats={})
        assert result["relevant_protocols"] == []

    def test_relevant_protocols_no_match(self):
        ctx = _make_context(domain="qft", route_protocol_result=None)
        result = ctx.build_context(state={}, node_id="n1", dag_stats={})
        assert result["relevant_protocols"] == []

    def test_recommended_skills(self):
        ctx = _make_context(skills=["skill-a", "skill-b"])
        result = ctx.build_context(state={}, node_id="n1", dag_stats={})
        assert result["recommended_skills"] == ["skill-a", "skill-b"]

    def test_convention_summary_no_lock(self):
        ctx = _make_context()
        result = ctx.build_context(state={}, node_id="n1", dag_stats={})
        assert "0/" in result["convention_summary"]
        assert "conventions locked" in result["convention_summary"]

    def test_convention_summary_with_lock(self):
        ctx = _make_context()
        lock = {"metric_signature": "mostly-minus", "natural_units": "c=hbar=1"}
        result = ctx.build_context(
            state={"convention_lock": lock},
            node_id="n1",
            dag_stats={},
        )
        assert "2/" in result["convention_summary"]

    def test_convention_summary_bogus_values_not_counted(self):
        ctx = _make_context()
        lock = {"metric_signature": "none", "natural_units": "c=hbar=1"}
        result = ctx.build_context(
            state={"convention_lock": lock},
            node_id="n1",
            dag_stats={},
        )
        # "TBD" is a bogus value, so only natural_units is counted
        assert "1/" in result["convention_summary"]

    def test_open_questions_from_strings(self):
        ctx = _make_context()
        result = ctx.build_context(
            state={"open_questions": ["What is mass?", "Why spin?"]},
            node_id="n1",
            dag_stats={},
        )
        assert result["open_questions"] == ["What is mass?", "Why spin?"]

    def test_open_questions_prefer_typed_gpd_state(self):
        ctx = _make_context()
        result = ctx.build_context(
            state={
                "payload": {
                    "open_questions": ["legacy question"],
                    "gpd": {
                        "open_questions": [
                            {
                                "id": "q1",
                                "question": "What is the correct matching scale?",
                                "priority": "high",
                                "context": "Needed before the next branch split",
                            }
                        ]
                    },
                }
            },
            node_id="n1",
            dag_stats={},
        )
        assert result["open_questions"] == ["What is the correct matching scale?"]

    def test_open_questions_from_dicts(self):
        ctx = _make_context()
        result = ctx.build_context(
            state={"open_questions": [{"text": "Q1"}, {"question": "Q2"}, {"description": "Q3"}]},
            node_id="n1",
            dag_stats={},
        )
        assert result["open_questions"] == ["Q1", "Q2", "Q3"]

    def test_open_questions_empty_strings_skipped(self):
        ctx = _make_context()
        result = ctx.build_context(
            state={"open_questions": ["Valid", "", "  ", "Also valid"]},
            node_id="n1",
            dag_stats={},
        )
        assert result["open_questions"] == ["Valid", "Also valid"]

    def test_open_questions_not_a_list(self):
        ctx = _make_context()
        result = ctx.build_context(
            state={"open_questions": "not a list"},
            node_id="n1",
            dag_stats={},
        )
        assert result["open_questions"] == []

    def test_gpd_phase_and_orchestration_fields(self):
        ctx = _make_context()
        result = ctx.build_context(
            state={
                "payload": {
                    "gpd": {
                        "phase": {"id": "3", "name": "Verification", "status": "active"},
                        "verification_focus": [
                            {
                                "id": "vf1",
                                "check": "Recover the weak-coupling limit",
                                "priority": "critical",
                                "rationale": "This branch hinges on the asymptotic regime",
                            }
                        ],
                        "required_tools": [{"name": "sympy", "purpose": "Check simplifications", "required": True}],
                        "shared_claims": [
                            {"id": "sc1", "claim": "The saddle is stable", "status": "candidate", "confidence": 0.6}
                        ],
                    }
                }
            },
            node_id="n1",
            dag_stats={},
        )
        assert result["gpd_phase"] == {"id": "3", "name": "Verification", "status": "active"}
        assert result["verification_focus"][0]["id"] == "vf1"
        assert result["required_tools"][0]["name"] == "sympy"
        assert result["shared_claims"][0]["claim"] == "The saddle is stable"

    def test_phase_signal_included(self):
        ctx = _make_context()
        result = ctx.build_context(
            state={},
            node_id="n1",
            dag_stats={"budget_fraction_remaining": 0.1},
        )
        assert result["phase_signal"]["phase"] == "validation"

    def test_no_merged_bundle(self):
        loader = MagicMock(spec=BundleLoader)
        loader.merged = None
        loader.get_skill_names.return_value = []
        router = MagicMock(spec=ReferenceRouter)
        ctx = PhysicsTriageContext(bundle_loader=loader, reference_router=router)
        result = ctx.build_context(state={}, node_id="n1", dag_stats={})
        assert result["mode_descriptions"] == []
