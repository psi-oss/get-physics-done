from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaAxis,
    ResearchPersonaCapsule,
    ResearchPersonaError,
    ResearchPersonaFact,
    build_research_persona_capsule,
)
from gpd.core.research_persona_applications import (
    DoppelgangerBrief,
    ScientificTasteAssessment,
    TasteAxisScore,
    build_doppelganger_brief,
    build_expertise_explanation_plan,
    build_expertise_explanation_plan_payload,
    build_researcher_doppelganger_payload,
    build_scientific_taste_assessment,
    build_scientific_taste_check_payload,
)

SAFE_FACT = "SAFE_APPLICATION_CANARY theorem-first derivations with executable checks"
PRIVATE_FACT = "PRIVATE_APPLICATION_CANARY local path /tmp/private-research-note"
PROJECT_FACT = "PROJECT_APPLICATION_CANARY unpublished collaborator detail"
NEVER_FACT = "NEVER_APPLICATION_CANARY identity secret"
TASTE_AXES = (
    "novelty",
    "tractability",
    "evidence_appetite",
    "math_emphasis",
    "code_emphasis",
    "experiment_emphasis",
    "theory_emphasis",
    "applied_emphasis",
    "risk_tolerance",
)


def _fact(fact_id: str, value: str, privacy: str, category: str = "workstyle") -> ResearchPersonaFact:
    return ResearchPersonaFact(
        id=fact_id,
        category=category,
        value=value,
        confidence="confirmed",
        privacy=privacy,
        sources=["user_statement"],
    )


def _persona() -> ResearchPersona:
    return ResearchPersona(
        facts=[
            _fact("fact.safe", SAFE_FACT, "safe_to_share"),
            _fact("fact.private", PRIVATE_FACT, "private_local"),
            _fact("fact.project", PROJECT_FACT, "project_private"),
            _fact("fact.never", NEVER_FACT, "never_prompt"),
        ],
        axes=[
            ResearchPersonaAxis(
                id="math_emphasis",
                name="math emphasis",
                value=0.85,
                confidence="confirmed",
                privacy="safe_to_share",
            ),
            ResearchPersonaAxis(
                id="risk_tolerance",
                name="risk tolerance",
                value=-0.4,
                confidence="confirmed",
                privacy="safe_to_share",
            ),
            ResearchPersonaAxis(
                id="private_novelty",
                name="novelty",
                value=1.0,
                confidence="confirmed",
                privacy="private_local",
            ),
        ],
        standing_preferences=[
            "Prefer precise definitions before implementation",
            "Use rigorous tests for claims",
        ],
        negative_preferences=["Avoid hand-wavy motivation"],
        tools=["pytest", "uv"],
        research_areas=["quantum field theory", "symbolic computation"],
        expertise=["advanced theorem proving", "researcher-level perturbation theory"],
        workstyle=["derive the toy model first"],
        scientific_taste=["novel but tractable ideas with strong evidence"],
    )


def _render(payload: object) -> str:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")  # type: ignore[attr-defined]
    return json.dumps(payload, sort_keys=True, default=str)


def _assert_private_canaries_absent(payload: object) -> None:
    rendered = _render(payload)
    for needle in (PRIVATE_FACT, PROJECT_FACT, NEVER_FACT):
        assert needle not in rendered


def _rubric_by_axis(assessment: ScientificTasteAssessment) -> dict[str, TasteAxisScore]:
    return {entry.axis: entry for entry in assessment.rubric}


def test_doppelganger_brief_uses_prompt_capsule_and_keeps_private_facts_out() -> None:
    brief = build_doppelganger_brief(
        _persona(),
        topic="symbolic amplitude simplification",
        project_summary="Create a tractable proof-guided implementation plan.",
    )
    rendered = _render(brief)

    assert brief.prompt_safety.capsule_role == "doppelganger"
    assert brief.prompt_safety.used_capsule_semantics is True
    assert brief.prompt_safety.non_prompt_persona_fields_included is False
    assert SAFE_FACT in rendered
    _assert_private_canaries_absent(brief)
    assert brief.constraints
    assert brief.likely_questions
    assert brief.likely_objections
    assert brief.suggested_next_moves


def test_application_helpers_reject_raw_profile_dumps() -> None:
    raw_profile = _persona().model_dump(mode="json")

    with pytest.raises(ResearchPersonaError):
        build_doppelganger_brief(raw_profile, topic="anything")  # type: ignore[arg-type]


def test_application_helpers_require_matching_role_when_given_capsule() -> None:
    capsule = build_research_persona_capsule(_persona(), role="planner")

    with pytest.raises(ResearchPersonaError):
        build_scientific_taste_assessment(capsule, project_summary="A careful proof project.")


def test_expertise_plan_calibrates_to_advanced_math_and_code_preferences() -> None:
    plan = build_expertise_explanation_plan(
        _persona(),
        question="How should the Ward identity check be explained?",
    )
    rendered = _render(plan)

    assert plan.prompt_safety.capsule_role == "explainer"
    assert plan.calibration_level == "advanced"
    assert SAFE_FACT in rendered
    _assert_private_canaries_absent(plan)
    assert plan.assumed_background
    assert plan.emphasize
    assert plan.compress_or_skip
    assert plan.verification_hooks


def test_scientific_taste_assessment_has_canonical_deterministic_rubric() -> None:
    summary = "A novel theorem-first code tool with rigorous tests and a tractable first milestone."
    assessment = build_scientific_taste_assessment(_persona(), project_summary=summary)
    repeated = build_scientific_taste_assessment(_persona(), project_summary=summary)
    scores = _rubric_by_axis(assessment)

    assert assessment == repeated
    assert tuple(scores) == TASTE_AXES
    assert assessment.prompt_safety.capsule_role == "taste"
    assert all(0.0 <= entry.score <= 1.0 for entry in assessment.rubric)
    assert scores["math_emphasis"].label == "high"
    assert scores["risk_tolerance"].label in {"low", "medium"}
    assert assessment.overall_label in {"low", "medium", "high"}
    assert assessment.likely_attractions
    assert assessment.likely_concerns
    assert assessment.de_risking_moves
    _assert_private_canaries_absent(assessment)


def test_capsule_input_is_used_without_needing_private_profile() -> None:
    capsule = ResearchPersonaCapsule(
        role="taste",
        summary="taste capsule",
        standing_preferences=["prefer proofs"],
        tools=["pytest"],
        scientific_taste=["tractable novelty"],
    )

    assessment = build_scientific_taste_assessment(capsule, project_summary="A proof-heavy tractable idea.")

    assert assessment.prompt_safety.capsule_role == "taste"
    assert assessment.rubric
    assert assessment.likely_attractions


def test_application_payload_wrappers_are_json_ready_and_prompt_safe() -> None:
    metadata_keys = ("prompt_safe", "raw_profile_exposed", "persona_capsule")
    payloads = [
        build_researcher_doppelganger_payload(persona_or_capsule=_persona(), task="derive a Ward identity"),
        build_expertise_explanation_plan_payload(
            persona_or_capsule=_persona(),
            plan_document={"summary": "explain the proof obligation"},
        ),
        build_scientific_taste_check_payload(
            persona_or_capsule=_persona(),
            candidate_document={"summary": "a tractable theorem-first code project"},
        ),
    ]

    for payload in payloads:
        rendered = _render(payload)

        assert payload[metadata_keys[0]] is True
        assert payload[metadata_keys[1]] is False
        assert isinstance(payload[metadata_keys[2]], dict)
        assert json.loads(rendered)
        _assert_private_canaries_absent(payload)


def test_output_models_are_strict_and_immutable() -> None:
    brief = build_doppelganger_brief(_persona(), topic="renormalization checks")
    payload = brief.model_dump(mode="json")
    payload["legacy"] = True

    with pytest.raises(ValidationError):
        DoppelgangerBrief.model_validate(payload)

    with pytest.raises(ValidationError):
        brief.topic = "changed"  # type: ignore[misc]


def test_taste_axis_labels_must_match_scores() -> None:
    with pytest.raises(ValidationError):
        TasteAxisScore(axis="novelty", score=0.95, label="low", rationale="forced mismatch")
