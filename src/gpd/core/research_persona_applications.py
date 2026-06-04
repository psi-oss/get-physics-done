"""Prompt-safe advisory previews built from Research Persona capsules.

The helpers in this module are deterministic and side-effect free. They accept
either a private ``ResearchPersona`` object, which is immediately projected into
a role capsule, or a prebuilt prompt capsule. They never read or write the
machine-local persona store.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaCapsule,
    ResearchPersonaCapsuleRole,
    ResearchPersonaError,
    build_research_persona_capsule,
)

__all__ = [
    "AdvisoryConstraint",
    "DoppelgangerBrief",
    "ExpertiseExplanationPlan",
    "PersonaApplicationPromptSafety",
    "ScientificTasteAssessment",
    "TASTE_AXIS_IDS",
    "TasteAxisScore",
    "build_doppelganger_brief",
    "build_expertise_explanation_plan",
    "build_expertise_explanation_plan_payload",
    "build_expertise_explanation_preview",
    "build_research_persona_doppelganger_payload",
    "build_research_persona_explain_plan_payload",
    "build_research_persona_taste_check_payload",
    "build_researcher_doppelganger_payload",
    "build_researcher_doppelganger_preview",
    "build_scientific_taste_assessment",
    "build_scientific_taste_check_payload",
    "build_scientific_taste_preview",
    "rank_scientific_taste_preview",
]

PERSONA_APPLICATION_SCHEMA_VERSION = 1

TasteAxisId = Literal[
    "novelty",
    "tractability",
    "evidence_appetite",
    "math_emphasis",
    "code_emphasis",
    "experiment_emphasis",
    "theory_emphasis",
    "applied_emphasis",
    "risk_tolerance",
]
TasteLabel = Literal["low", "medium", "high"]
ConstraintKind = Literal["prefer", "avoid", "tool", "domain", "style", "verification", "privacy"]
ApplicationFeature = Literal["researcher_doppelganger", "expertise_aware_explanations", "scientific_taste_model"]

TASTE_AXIS_IDS: tuple[str, ...] = (
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

_CAPSULE_LIST_FIELDS: tuple[str, ...] = (
    "standing_preferences",
    "negative_preferences",
    "tools",
    "research_areas",
    "expertise",
    "workstyle",
    "scientific_taste",
)
_UNBOUNDED_PAYLOAD_LIST_FIELDS = {"rubric"}
_SUMMARY_LIMIT = 5
_TEXT_LIMIT = 12

_AXIS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "novelty": ("novel", "novelty", "original", "creative", "new", "surprising", "unexplored"),
    "tractability": ("tractable", "feasible", "minimal", "simple", "robust", "practical", "bounded"),
    "evidence_appetite": (
        "evidence",
        "proof",
        "test",
        "validated",
        "benchmark",
        "experiment",
        "derivation",
        "citation",
        "rigorous",
    ),
    "math_emphasis": ("math", "theorem", "proof", "derivation", "formal", "analytic", "equation", "symbolic"),
    "code_emphasis": ("code", "implementation", "software", "test", "pytest", "api", "simulation", "notebook"),
    "experiment_emphasis": ("experiment", "empirical", "benchmark", "measurement", "data", "numerical"),
    "theory_emphasis": ("theory", "theoretical", "fundamental", "formal", "proof", "model", "derivation"),
    "applied_emphasis": ("applied", "application", "engineering", "deploy", "practical", "product", "workflow"),
    "risk_tolerance": ("risk", "ambitious", "speculative", "bold", "exploratory", "uncertain", "creative"),
}
_LOWERING_KEYWORDS: dict[str, tuple[str, ...]] = {
    "risk_tolerance": ("conservative", "safe", "low-risk", "careful", "incremental"),
    "novelty": ("standard", "conventional", "established", "incremental"),
}
_EXPERTISE_BEGINNER = ("new to", "beginner", "intro", "basic", "learning", "unfamiliar")
_EXPERTISE_ADVANCED = ("expert", "advanced", "deep", "researcher", "specialist", "theorem", "proof")


class _PersonaApplicationModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _normalize_required_string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    return text


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("must be a string or null")
    text = value.strip()
    return text or None


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("must be a list of strings")
    for item in value:
        if not isinstance(item, str):
            raise ValueError("must contain only strings")
    return _dedupe_text(item.strip() for item in value)


def _dedupe_text(values: Iterable[str], *, limit: int | None = None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
        if limit is not None and len(normalized) >= limit:
            break
    return normalized


def _clamp_unit_interval(value: object) -> float:
    if type(value) is bool or not isinstance(value, (int, float)):
        raise ValueError("must be a number between 0 and 1")
    normalized = float(value)
    if normalized < 0.0 or normalized > 1.0:
        raise ValueError("must be between 0 and 1")
    return round(normalized, 3)


def _label_for_score(score: float) -> TasteLabel:
    if score < 0.34:
        return "low"
    if score < 0.67:
        return "medium"
    return "high"


class PersonaApplicationPromptSafety(_PersonaApplicationModel):
    """Auditable boundary for a prompt-facing persona application preview."""

    capsule_role: ResearchPersonaCapsuleRole
    capsule_purpose: Literal["prompt"] = "prompt"
    capsule_summary: str
    used_capsule_semantics: bool = True
    non_prompt_persona_fields_included: bool = False
    private_detail_policy: str = (
        "Only fields already present in the supplied prompt capsule may influence this advisory payload."
    )

    @field_validator("capsule_summary", "private_detail_policy", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> str:
        return _normalize_required_string(value)


class AdvisoryConstraint(_PersonaApplicationModel):
    """One deterministic constraint inferred from a prompt-safe persona capsule."""

    kind: ConstraintKind
    text: str
    source_field: str | None = None

    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> str:
        return _normalize_required_string(value)

    @field_validator("source_field", mode="before")
    @classmethod
    def _normalize_source_field(cls, value: object) -> str | None:
        return _normalize_optional_string(value)


class TasteAxisScore(_PersonaApplicationModel):
    """Deterministic score for one scientific-taste axis."""

    axis: TasteAxisId
    score: float
    label: TasteLabel
    rationale: str
    signals: list[str] = Field(default_factory=list)

    @field_validator("score", mode="before")
    @classmethod
    def _normalize_score(cls, value: object) -> float:
        return _clamp_unit_interval(value)

    @field_validator("rationale", mode="before")
    @classmethod
    def _normalize_rationale(cls, value: object) -> str:
        return _normalize_required_string(value)

    @field_validator("signals", mode="before")
    @classmethod
    def _normalize_signals(cls, value: object) -> list[str]:
        return _normalize_string_list(value)

    @model_validator(mode="after")
    def _validate_label_matches_score(self) -> TasteAxisScore:
        expected = _label_for_score(self.score)
        if self.label != expected:
            raise ValueError(f"label must be {expected!r} for score {self.score}")
        return self


class DoppelgangerBrief(_PersonaApplicationModel):
    """Preview of how the user might frame, constrain, and critique a topic."""

    schema_version: int = PERSONA_APPLICATION_SCHEMA_VERSION
    feature: Literal["researcher_doppelganger"] = "researcher_doppelganger"
    topic: str
    project_summary: str | None = None
    prompt_safety: PersonaApplicationPromptSafety
    constraints: list[AdvisoryConstraint] = Field(default_factory=list)
    likely_questions: list[str] = Field(default_factory=list)
    likely_objections: list[str] = Field(default_factory=list)
    suggested_next_moves: list[str] = Field(default_factory=list)
    style_instructions: list[str] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        if type(value) is not int or value != PERSONA_APPLICATION_SCHEMA_VERSION:
            raise ValueError("schema_version must be the integer 1")
        return value

    @field_validator("topic", mode="before")
    @classmethod
    def _normalize_topic(cls, value: object) -> str:
        return _normalize_required_string(value)

    @field_validator("project_summary", mode="before")
    @classmethod
    def _normalize_project_summary(cls, value: object) -> str | None:
        return _normalize_optional_string(value)

    @field_validator(
        "likely_questions",
        "likely_objections",
        "suggested_next_moves",
        "style_instructions",
        mode="before",
    )
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return _normalize_string_list(value)


class ExpertiseExplanationPlan(_PersonaApplicationModel):
    """Preview plan for calibrating an explanation to the user's expertise."""

    schema_version: int = PERSONA_APPLICATION_SCHEMA_VERSION
    feature: Literal["expertise_aware_explanations"] = "expertise_aware_explanations"
    question: str
    project_summary: str | None = None
    prompt_safety: PersonaApplicationPromptSafety
    calibration_level: Literal["introductory", "intermediate", "advanced"]
    assumed_background: list[str] = Field(default_factory=list)
    emphasize: list[str] = Field(default_factory=list)
    compress_or_skip: list[str] = Field(default_factory=list)
    likely_questions: list[str] = Field(default_factory=list)
    explanation_constraints: list[AdvisoryConstraint] = Field(default_factory=list)
    verification_hooks: list[str] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        if type(value) is not int or value != PERSONA_APPLICATION_SCHEMA_VERSION:
            raise ValueError("schema_version must be the integer 1")
        return value

    @field_validator("question", mode="before")
    @classmethod
    def _normalize_question(cls, value: object) -> str:
        return _normalize_required_string(value)

    @field_validator("project_summary", mode="before")
    @classmethod
    def _normalize_project_summary(cls, value: object) -> str | None:
        return _normalize_optional_string(value)

    @field_validator(
        "assumed_background",
        "emphasize",
        "compress_or_skip",
        "likely_questions",
        "verification_hooks",
        mode="before",
    )
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return _normalize_string_list(value)


class ScientificTasteAssessment(_PersonaApplicationModel):
    """Deterministic taste and risk preview for a project idea."""

    schema_version: int = PERSONA_APPLICATION_SCHEMA_VERSION
    feature: Literal["scientific_taste_model"] = "scientific_taste_model"
    project_summary: str
    prompt_safety: PersonaApplicationPromptSafety
    rubric: list[TasteAxisScore]
    overall_alignment: float
    overall_label: TasteLabel
    likely_attractions: list[str] = Field(default_factory=list)
    likely_concerns: list[str] = Field(default_factory=list)
    de_risking_moves: list[str] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        if type(value) is not int or value != PERSONA_APPLICATION_SCHEMA_VERSION:
            raise ValueError("schema_version must be the integer 1")
        return value

    @field_validator("project_summary", mode="before")
    @classmethod
    def _normalize_project_summary(cls, value: object) -> str:
        return _normalize_required_string(value)

    @field_validator("overall_alignment", mode="before")
    @classmethod
    def _normalize_overall_alignment(cls, value: object) -> float:
        return _clamp_unit_interval(value)

    @field_validator("likely_attractions", "likely_concerns", "de_risking_moves", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return _normalize_string_list(value)

    @model_validator(mode="after")
    def _validate_overall_label(self) -> ScientificTasteAssessment:
        expected = _label_for_score(self.overall_alignment)
        if self.overall_label != expected:
            raise ValueError(f"overall_label must be {expected!r} for overall_alignment {self.overall_alignment}")
        axes = [entry.axis for entry in self.rubric]
        if axes != list(TASTE_AXIS_IDS):
            raise ValueError("rubric must contain the canonical taste axes in order")
        return self


def build_doppelganger_brief(
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule,
    *,
    topic: str,
    project_summary: str | None = None,
) -> DoppelgangerBrief:
    """Return a prompt-safe Researcher Doppelganger preview for a topic."""

    normalized_topic = _normalize_required_string(topic)
    normalized_project = _normalize_optional_string(project_summary)
    capsule = _coerce_capsule(persona_or_capsule, role="doppelganger")
    constraints = _constraints_from_capsule(capsule)
    fields = _capsule_text_fields(capsule)
    taste = _score_taste_axes(capsule)

    likely_questions = _topic_questions(
        normalized_topic,
        fields=fields,
        taste=taste,
        project_summary=normalized_project,
    )
    likely_objections = _topic_objections(normalized_topic, capsule=capsule, taste=taste)
    suggested_next_moves = _next_moves(normalized_topic, capsule=capsule, taste=taste)
    style_instructions = _style_instructions(capsule)

    return DoppelgangerBrief(
        topic=normalized_topic,
        project_summary=normalized_project,
        prompt_safety=_prompt_safety(capsule),
        constraints=constraints,
        likely_questions=likely_questions,
        likely_objections=likely_objections,
        suggested_next_moves=suggested_next_moves,
        style_instructions=style_instructions,
    )


def build_expertise_explanation_plan(
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule,
    *,
    question: str,
    project_summary: str | None = None,
) -> ExpertiseExplanationPlan:
    """Return a deterministic explanation plan calibrated by prompt-safe expertise."""

    normalized_question = _normalize_required_string(question)
    normalized_project = _normalize_optional_string(project_summary)
    capsule = _coerce_capsule(persona_or_capsule, role="explainer")
    taste = _score_taste_axes(capsule)
    calibration_level = _calibration_level(capsule)
    constraints = _constraints_from_capsule(capsule)
    assumed_background = _dedupe_text([*capsule.expertise, *capsule.research_areas], limit=_SUMMARY_LIMIT)
    emphasize = _explanation_emphasis(capsule, taste=taste)
    compress_or_skip = _compress_or_skip(capsule, calibration_level=calibration_level)
    likely_questions = _explanation_questions(normalized_question, capsule=capsule, taste=taste)
    verification_hooks = _verification_hooks(capsule, taste=taste)

    return ExpertiseExplanationPlan(
        question=normalized_question,
        project_summary=normalized_project,
        prompt_safety=_prompt_safety(capsule),
        calibration_level=calibration_level,
        assumed_background=assumed_background,
        emphasize=emphasize,
        compress_or_skip=compress_or_skip,
        likely_questions=likely_questions,
        explanation_constraints=constraints,
        verification_hooks=verification_hooks,
    )


def build_scientific_taste_assessment(
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule,
    *,
    project_summary: str,
) -> ScientificTasteAssessment:
    """Return a prompt-safe Scientific Taste Model preview for a project idea."""

    normalized_project = _normalize_required_string(project_summary)
    capsule = _coerce_capsule(persona_or_capsule, role="taste")
    rubric = _score_taste_axes(capsule)
    overall = _overall_alignment(project_summary=normalized_project, rubric=rubric)

    return ScientificTasteAssessment(
        project_summary=normalized_project,
        prompt_safety=_prompt_safety(capsule),
        rubric=rubric,
        overall_alignment=overall,
        overall_label=_label_for_score(overall),
        likely_attractions=_taste_attractions(normalized_project, capsule=capsule, rubric=rubric),
        likely_concerns=_taste_concerns(normalized_project, capsule=capsule, rubric=rubric),
        de_risking_moves=_taste_de_risking_moves(capsule, rubric=rubric),
    )


def build_researcher_doppelganger_payload(
    *,
    capsule: ResearchPersonaCapsule | None = None,
    persona_capsule: ResearchPersonaCapsule | None = None,
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule | None = None,
    task: str | None = None,
    focus: str | None = None,
    max_items: int | None = None,
    **_: object,
) -> dict[str, object]:
    """Return a JSON-ready Researcher Doppelganger preview payload."""

    source = _payload_source(capsule, persona_capsule, persona_or_capsule, role="doppelganger")
    source_capsule = _coerce_capsule(source, role="doppelganger")
    topic = _first_text(focus, task, fallback="current research task")
    project_summary = task if focus and task != focus else None
    payload = build_doppelganger_brief(
        source_capsule,
        topic=topic,
        project_summary=project_summary,
    ).model_dump(mode="json")
    payload = _application_payload_metadata(payload, application="doppelganger", capsule=source_capsule)
    return _bounded_payload_lists(payload, max_items=max_items)


def build_research_persona_doppelganger_payload(**kwargs: object) -> dict[str, object]:
    """Compatibility alias for the Researcher Doppelganger payload."""

    return build_researcher_doppelganger_payload(**kwargs)


def build_researcher_doppelganger_preview(
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule,
    *,
    topic: str,
    project_summary: str | None = None,
) -> DoppelgangerBrief:
    """Semantic preview alias for acceptance and orchestration surfaces."""

    return build_doppelganger_brief(persona_or_capsule, topic=topic, project_summary=project_summary)


def build_expertise_explanation_plan_payload(
    *,
    capsule: ResearchPersonaCapsule | None = None,
    persona_capsule: ResearchPersonaCapsule | None = None,
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule | None = None,
    task: str | None = None,
    plan: object | None = None,
    plan_document: object | None = None,
    audience: str | None = None,
    max_items: int | None = None,
    **_: object,
) -> dict[str, object]:
    """Return a JSON-ready Expertise-Aware Explanations preview payload."""

    source = _payload_source(capsule, persona_capsule, persona_or_capsule, role="explainer")
    source_capsule = _coerce_capsule(source, role="explainer")
    question = _first_text(
        task,
        audience,
        _document_summary(plan_document if plan_document is not None else plan),
        fallback="current explanation request",
    )
    project_summary = _document_summary(plan_document if plan_document is not None else plan)
    payload = build_expertise_explanation_plan(
        source_capsule,
        question=question,
        project_summary=project_summary,
    ).model_dump(mode="json")
    if audience:
        payload["audience"] = audience
    payload = _application_payload_metadata(payload, application="explain_plan", capsule=source_capsule)
    return _bounded_payload_lists(payload, max_items=max_items)


def build_research_persona_explain_plan_payload(**kwargs: object) -> dict[str, object]:
    """Compatibility alias for expertise-aware explanation payloads."""

    return build_expertise_explanation_plan_payload(**kwargs)


def build_expertise_explanation_preview(
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule,
    *,
    question: str,
    project_summary: str | None = None,
) -> ExpertiseExplanationPlan:
    """Semantic preview alias for expertise-aware explanations."""

    return build_expertise_explanation_plan(
        persona_or_capsule,
        question=question,
        project_summary=project_summary,
    )


def build_scientific_taste_check_payload(
    *,
    capsule: ResearchPersonaCapsule | None = None,
    persona_capsule: ResearchPersonaCapsule | None = None,
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule | None = None,
    task: str | None = None,
    candidate: object | None = None,
    candidate_document: object | None = None,
    focus: str | None = None,
    max_items: int | None = None,
    **_: object,
) -> dict[str, object]:
    """Return a JSON-ready Scientific Taste Model preview payload."""

    source = _payload_source(capsule, persona_capsule, persona_or_capsule, role="taste")
    source_capsule = _coerce_capsule(source, role="taste")
    candidate_summary = _document_summary(candidate_document if candidate_document is not None else candidate)
    project_summary = _first_text(focus, task, candidate_summary, fallback="current research direction")
    payload = build_scientific_taste_assessment(source_capsule, project_summary=project_summary).model_dump(mode="json")
    payload = _application_payload_metadata(payload, application="taste_check", capsule=source_capsule)
    return _bounded_payload_lists(payload, max_items=max_items)


def build_research_persona_taste_check_payload(**kwargs: object) -> dict[str, object]:
    """Compatibility alias for scientific-taste payloads."""

    return build_scientific_taste_check_payload(**kwargs)


def build_scientific_taste_preview(
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule,
    *,
    project_summary: str,
) -> ScientificTasteAssessment:
    """Semantic preview alias for scientific-taste assessment."""

    return build_scientific_taste_assessment(persona_or_capsule, project_summary=project_summary)


def rank_scientific_taste_preview(
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule,
    *,
    project_summary: str,
) -> ScientificTasteAssessment:
    """Ranking-oriented alias for the Scientific Taste Model preview."""

    return build_scientific_taste_assessment(persona_or_capsule, project_summary=project_summary)


def _coerce_capsule(
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule,
    *,
    role: ResearchPersonaCapsuleRole,
) -> ResearchPersonaCapsule:
    if isinstance(persona_or_capsule, ResearchPersona):
        return build_research_persona_capsule(persona_or_capsule, role=role)
    if isinstance(persona_or_capsule, ResearchPersonaCapsule):
        if persona_or_capsule.role != role:
            raise ResearchPersonaError(f"{role} application requires a {role} capsule or a ResearchPersona")
        if persona_or_capsule.purpose != "prompt":
            raise ResearchPersonaError(f"{role} application requires a prompt-purpose capsule")
        return persona_or_capsule
    raise ResearchPersonaError("persona application helpers require ResearchPersona or ResearchPersonaCapsule input")


def _payload_source(
    capsule: ResearchPersonaCapsule | None,
    persona_capsule: ResearchPersonaCapsule | None,
    persona_or_capsule: ResearchPersona | ResearchPersonaCapsule | None,
    *,
    role: ResearchPersonaCapsuleRole,
) -> ResearchPersona | ResearchPersonaCapsule:
    source = persona_or_capsule or capsule or persona_capsule
    if source is None:
        raise ResearchPersonaError(f"{role} payload requires a prompt-safe persona capsule")
    return source


def _first_text(*values: str | None, fallback: str) -> str:
    for value in values:
        if value is None:
            continue
        normalized = _normalize_optional_string(value)
        if normalized:
            return normalized
    return fallback


def _document_summary(document: object | None) -> str | None:
    if document is None:
        return None
    if isinstance(document, str):
        return _normalize_optional_string(document)
    if isinstance(document, dict):
        for key in ("summary", "question", "task", "title", "claim", "topic", "project_summary"):
            value = document.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return str(document)[:240].strip() or None


def _bounded_payload_lists(payload: dict[str, object], *, max_items: int | None) -> dict[str, object]:
    if max_items is None:
        return payload
    limit = max(1, int(max_items))
    bounded = dict(payload)
    for key, value in list(bounded.items()):
        if key not in _UNBOUNDED_PAYLOAD_LIST_FIELDS and isinstance(value, list):
            bounded[key] = value[:limit]
    return bounded


def _application_payload_metadata(
    payload: dict[str, object],
    *,
    application: str,
    capsule: ResearchPersonaCapsule,
) -> dict[str, object]:
    enriched = dict(payload)
    enriched.setdefault("application", application)
    enriched.setdefault("mode", "advisory_preview")
    enriched.setdefault("prompt_safe", True)
    enriched.setdefault("raw_profile_exposed", False)
    enriched.setdefault("persona_capsule", _persona_capsule_metadata(capsule))
    return enriched


def _persona_capsule_metadata(capsule: ResearchPersonaCapsule) -> dict[str, object]:
    counts: dict[str, int] = {
        "facts": len(capsule.facts),
        "axes": len(capsule.axes),
    }
    for field_name in _CAPSULE_LIST_FIELDS:
        counts[field_name] = len(getattr(capsule, field_name))
    return {
        "source": "research_persona_capsule",
        "role": capsule.role,
        "purpose": capsule.purpose,
        "counts": counts,
        "summary": capsule.summary,
    }


def _prompt_safety(capsule: ResearchPersonaCapsule) -> PersonaApplicationPromptSafety:
    return PersonaApplicationPromptSafety(capsule_role=capsule.role, capsule_summary=capsule.summary)


def _capsule_text_fields(capsule: ResearchPersonaCapsule) -> dict[str, list[str]]:
    fields = {field_name: list(getattr(capsule, field_name)) for field_name in _CAPSULE_LIST_FIELDS}
    fields["facts"] = _dedupe_text(
        str(fact.get("value", "")).strip() for fact in capsule.facts if isinstance(fact, dict)
    )
    fields["axes"] = _dedupe_text(_axis_text(axis) for axis in capsule.axes if isinstance(axis, dict))
    return fields


def _axis_text(axis: dict[str, object]) -> str:
    parts = [str(axis.get("id", "")), str(axis.get("name", ""))]
    value = axis.get("value")
    if isinstance(value, (int, float)) and type(value) is not bool:
        parts.append(f"{float(value):.2f}")
    return " ".join(part for part in parts if part.strip())


def _constraints_from_capsule(capsule: ResearchPersonaCapsule) -> list[AdvisoryConstraint]:
    constraints: list[AdvisoryConstraint] = []
    constraints.extend(
        AdvisoryConstraint(kind="prefer", text=value, source_field="standing_preferences")
        for value in capsule.standing_preferences[:_SUMMARY_LIMIT]
    )
    constraints.extend(
        AdvisoryConstraint(kind="avoid", text=value, source_field="negative_preferences")
        for value in capsule.negative_preferences[:_SUMMARY_LIMIT]
    )
    constraints.extend(AdvisoryConstraint(kind="tool", text=value, source_field="tools") for value in capsule.tools[:4])
    constraints.extend(
        AdvisoryConstraint(kind="domain", text=value, source_field="research_areas")
        for value in capsule.research_areas[:4]
    )
    constraints.extend(
        AdvisoryConstraint(kind="style", text=value, source_field="workstyle") for value in capsule.workstyle[:4]
    )
    fact_values = _dedupe_text(str(fact.get("value", "")).strip() for fact in capsule.facts if isinstance(fact, dict))
    constraints.extend(
        AdvisoryConstraint(kind="verification", text=value, source_field="facts") for value in fact_values[:4]
    )
    constraints.append(
        AdvisoryConstraint(
            kind="privacy",
            text="Treat this advisory as capsule-derived style guidance, not as durable memory or a raw profile dump.",
            source_field=None,
        )
    )
    return constraints[:_TEXT_LIMIT]


def _score_taste_axes(capsule: ResearchPersonaCapsule) -> list[TasteAxisScore]:
    fields = _capsule_text_fields(capsule)
    corpus = _flatten_text_fields(fields)
    axis_scores: list[TasteAxisScore] = []
    for axis_id in TASTE_AXIS_IDS:
        score, signals = _score_axis(axis_id, capsule=capsule, corpus=corpus)
        axis_scores.append(
            TasteAxisScore(
                axis=axis_id,
                score=score,
                label=_label_for_score(score),
                rationale=_axis_rationale(axis_id, score, signals),
                signals=signals[:_SUMMARY_LIMIT],
            )
        )
    return axis_scores


def _flatten_text_fields(fields: dict[str, list[str]]) -> list[str]:
    return _dedupe_text(item for values in fields.values() for item in values)


def _score_axis(
    axis_id: str,
    *,
    capsule: ResearchPersonaCapsule,
    corpus: Sequence[str],
) -> tuple[float, list[str]]:
    score = 0.5
    signals: list[str] = []

    axis_value = _safe_axis_value(capsule, axis_id)
    if axis_value is not None:
        score = (axis_value + 1.0) / 2.0
        signals.append(f"axis:{axis_id}={axis_value:.2f}")

    keyword_hits = _keyword_hits(corpus, _AXIS_KEYWORDS[axis_id])
    if keyword_hits:
        score += min(0.3, 0.07 * len(keyword_hits))
        signals.extend(keyword_hits)

    lowering_hits = _keyword_hits(corpus, _LOWERING_KEYWORDS.get(axis_id, ()))
    if lowering_hits:
        score -= min(0.25, 0.08 * len(lowering_hits))
        signals.extend(f"down:{hit}" for hit in lowering_hits)

    if axis_id == "experiment_emphasis" and not keyword_hits:
        score -= 0.12
    if axis_id == "code_emphasis" and capsule.tools:
        score += 0.08
        signals.extend(f"tool:{tool}" for tool in capsule.tools[:2])
    if axis_id == "evidence_appetite" and (capsule.negative_preferences or capsule.workstyle):
        score += 0.05
    if axis_id == "risk_tolerance" and capsule.negative_preferences:
        score -= 0.05

    return round(max(0.0, min(1.0, score)), 3), _dedupe_text(signals)


def _safe_axis_value(capsule: ResearchPersonaCapsule, axis_id: str) -> float | None:
    target_tokens = _axis_match_tokens(axis_id)
    for axis in capsule.axes:
        if not isinstance(axis, dict):
            continue
        axis_text = " ".join(str(axis.get(key, "")) for key in ("id", "name")).casefold()
        if not any(token in axis_text for token in target_tokens):
            continue
        value = axis.get("value")
        if type(value) is bool or not isinstance(value, (int, float)):
            continue
        return max(-1.0, min(1.0, float(value)))
    return None


def _axis_match_tokens(axis_id: str) -> tuple[str, ...]:
    if axis_id.endswith("_emphasis"):
        return (axis_id, axis_id.removesuffix("_emphasis"))
    return (axis_id,)


def _keyword_hits(corpus: Sequence[str], keywords: Sequence[str]) -> list[str]:
    hits: list[str] = []
    for text in corpus:
        lowered = text.casefold()
        for keyword in keywords:
            if keyword.casefold() in lowered:
                hits.append(text)
                break
    return _dedupe_text(hits, limit=_SUMMARY_LIMIT)


def _axis_rationale(axis_id: str, score: float, signals: Sequence[str]) -> str:
    label = _label_for_score(score)
    if signals:
        return f"{label} {axis_id.replace('_', ' ')} from {len(signals)} prompt-safe signal(s)."
    return f"{label} {axis_id.replace('_', ' ')} from neutral capsule defaults."


def _topic_questions(
    topic: str,
    *,
    fields: dict[str, list[str]],
    taste: Sequence[TasteAxisScore],
    project_summary: str | None,
) -> list[str]:
    questions = [
        f"What is the smallest falsifiable claim about {topic}?",
        f"Which assumptions in {topic} should be made explicit first?",
    ]
    if project_summary:
        questions.append(f"How does the project summary constrain the scope of {topic}?")
    if _score_for(taste, "evidence_appetite") >= 0.67:
        questions.append(f"What evidence would disconfirm the proposed direction for {topic}?")
    if _score_for(taste, "math_emphasis") >= 0.67:
        questions.append(f"Can {topic} be reduced to a precise definition, lemma, or invariant?")
    if fields["tools"]:
        questions.append(f"Which trusted tool should check the first concrete artifact for {topic}?")
    return _dedupe_text(questions, limit=_TEXT_LIMIT)


def _topic_objections(
    topic: str,
    *,
    capsule: ResearchPersonaCapsule,
    taste: Sequence[TasteAxisScore],
) -> list[str]:
    objections = [f"The proposal for {topic} may be too vague until success and failure modes are pinned down."]
    objections.extend(
        f"It may conflict with the stated negative preference: {value}" for value in capsule.negative_preferences[:3]
    )
    if _score_for(taste, "tractability") >= 0.67:
        objections.append(f"The plan for {topic} should justify why it is tractable before broad exploration.")
    if _score_for(taste, "risk_tolerance") < 0.34:
        objections.append(f"The plan for {topic} may need a lower-risk baseline before speculative work.")
    return _dedupe_text(objections, limit=_TEXT_LIMIT)


def _next_moves(
    topic: str,
    *,
    capsule: ResearchPersonaCapsule,
    taste: Sequence[TasteAxisScore],
) -> list[str]:
    moves = [f"Write a one-page claim map for {topic} with assumptions, tests, and unknowns."]
    if _score_for(taste, "math_emphasis") >= _score_for(taste, "code_emphasis"):
        moves.append(f"Derive the cleanest formal toy case for {topic} before adding machinery.")
    else:
        moves.append(f"Build a minimal executable probe for {topic} and record the first failure mode.")
    if capsule.tools:
        moves.append(f"Use {', '.join(capsule.tools[:3])} for the first verification pass.")
    if _score_for(taste, "experiment_emphasis") >= 0.67:
        moves.append(f"Define an empirical benchmark for {topic} before optimizing the idea.")
    return _dedupe_text(moves, limit=_TEXT_LIMIT)


def _style_instructions(capsule: ResearchPersonaCapsule) -> list[str]:
    values = [*capsule.workstyle[:4], *capsule.standing_preferences[:4]]
    if not values:
        values.append("Keep recommendations explicit about assumptions, uncertainty, and verification.")
    return _dedupe_text(values, limit=8)


def _calibration_level(capsule: ResearchPersonaCapsule) -> Literal["introductory", "intermediate", "advanced"]:
    corpus = _flatten_text_fields(_capsule_text_fields(capsule))
    beginner_hits = _keyword_hits(corpus, _EXPERTISE_BEGINNER)
    advanced_hits = _keyword_hits(corpus, _EXPERTISE_ADVANCED)
    if advanced_hits and len(advanced_hits) >= len(beginner_hits):
        return "advanced"
    if beginner_hits:
        return "introductory"
    if len(capsule.expertise) + len(capsule.research_areas) >= 3:
        return "advanced"
    return "intermediate"


def _explanation_emphasis(
    capsule: ResearchPersonaCapsule,
    *,
    taste: Sequence[TasteAxisScore],
) -> list[str]:
    emphasis: list[str] = []
    if _score_for(taste, "math_emphasis") >= 0.67:
        emphasis.append("Start with definitions, assumptions, and the core derivation.")
    if _score_for(taste, "code_emphasis") >= 0.67:
        emphasis.append("Include implementation consequences and a small executable check.")
    if _score_for(taste, "experiment_emphasis") >= 0.67:
        emphasis.append("Tie claims to measurable outcomes or benchmark design.")
    if _score_for(taste, "evidence_appetite") >= 0.67:
        emphasis.append("Separate established facts, plausible inferences, and open questions.")
    emphasis.extend(capsule.standing_preferences[:3])
    if not emphasis:
        emphasis.append("Use a concise intermediate explanation with explicit assumptions.")
    return _dedupe_text(emphasis, limit=_TEXT_LIMIT)


def _compress_or_skip(
    capsule: ResearchPersonaCapsule,
    *,
    calibration_level: str,
) -> list[str]:
    compress: list[str] = []
    if calibration_level == "advanced":
        compress.append("Basic motivation and textbook background unless the question asks for it.")
    if capsule.negative_preferences:
        compress.extend(capsule.negative_preferences[:4])
    if not compress:
        compress.append("Do not skip setup that is needed to make notation and assumptions unambiguous.")
    return _dedupe_text(compress, limit=8)


def _explanation_questions(
    question: str,
    *,
    capsule: ResearchPersonaCapsule,
    taste: Sequence[TasteAxisScore],
) -> list[str]:
    questions = [f"What level of detail is needed for the answer to: {question}"]
    if capsule.research_areas:
        questions.append(f"Should the explanation connect to {', '.join(capsule.research_areas[:3])}?")
    if _score_for(taste, "math_emphasis") >= 0.67:
        questions.append("Would a derivation or limiting case be more useful than prose?")
    if _score_for(taste, "code_emphasis") >= 0.67:
        questions.append("Should the explanation include runnable pseudocode or test hooks?")
    return _dedupe_text(questions, limit=_TEXT_LIMIT)


def _verification_hooks(
    capsule: ResearchPersonaCapsule,
    *,
    taste: Sequence[TasteAxisScore],
) -> list[str]:
    hooks = ["State what would change the conclusion."]
    if _score_for(taste, "math_emphasis") >= 0.67:
        hooks.append("Check dimensions, limiting cases, and proof obligations.")
    if _score_for(taste, "code_emphasis") >= 0.67:
        hooks.append("Name a concrete test or reproducible computation.")
    if capsule.tools:
        hooks.append(f"Prefer familiar tools where relevant: {', '.join(capsule.tools[:3])}.")
    return _dedupe_text(hooks, limit=8)


def _overall_alignment(
    *,
    project_summary: str,
    rubric: Sequence[TasteAxisScore],
) -> float:
    project_tokens = _project_axis_matches(project_summary)
    if not project_tokens:
        return round(sum(score.score for score in rubric) / len(rubric), 3)

    weighted_sum = 0.0
    total_weight = 0.0
    for score in rubric:
        weight = 1.5 if score.axis in project_tokens else 1.0
        weighted_sum += score.score * weight
        total_weight += weight
    return round(weighted_sum / total_weight, 3)


def _project_axis_matches(project_summary: str) -> set[str]:
    lowered = project_summary.casefold()
    matches: set[str] = set()
    for axis_id, keywords in _AXIS_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(keyword.casefold())}\b", lowered) for keyword in keywords):
            matches.add(axis_id)
    return matches


def _taste_attractions(
    project_summary: str,
    *,
    capsule: ResearchPersonaCapsule,
    rubric: Sequence[TasteAxisScore],
) -> list[str]:
    attractions = [
        f"{score.axis.replace('_', ' ')} looks aligned with the persona."
        for score in rubric
        if score.score >= 0.67 and score.axis in _project_axis_matches(project_summary)
    ]
    if not attractions:
        high_scores = [score for score in rubric if score.score >= 0.67]
        attractions.extend(f"Strong persona signal: {score.axis.replace('_', ' ')}." for score in high_scores[:3])
    attractions.extend(capsule.scientific_taste[:3])
    return _dedupe_text(
        attractions or ["No strong attraction signal beyond neutral capsule defaults."],
        limit=_TEXT_LIMIT,
    )


def _taste_concerns(
    project_summary: str,
    *,
    capsule: ResearchPersonaCapsule,
    rubric: Sequence[TasteAxisScore],
) -> list[str]:
    project_axes = _project_axis_matches(project_summary)
    concerns = [
        f"{score.axis.replace('_', ' ')} may be a mismatch for this project."
        for score in rubric
        if score.score < 0.34 and score.axis in project_axes
    ]
    concerns.extend(f"Known negative preference: {value}" for value in capsule.negative_preferences[:3])
    if not concerns and _score_for(rubric, "tractability") < 0.5:
        concerns.append("Tractability evidence is thin in the prompt-safe persona signals.")
    return _dedupe_text(concerns or ["No strong concern signal from the prompt-safe capsule."], limit=_TEXT_LIMIT)


def _taste_de_risking_moves(
    capsule: ResearchPersonaCapsule,
    *,
    rubric: Sequence[TasteAxisScore],
) -> list[str]:
    moves = ["Define a short falsification checklist before committing to the idea."]
    if _score_for(rubric, "tractability") < 0.67:
        moves.append("Reduce the first milestone until it can be checked by one artifact.")
    if _score_for(rubric, "evidence_appetite") >= 0.67:
        moves.append("Attach every major claim to a proof, citation, benchmark, or explicit assumption.")
    if _score_for(rubric, "risk_tolerance") < 0.5:
        moves.append("Pair the ambitious version with a conservative baseline.")
    if capsule.tools:
        moves.append(f"Use familiar tooling for the first pass: {', '.join(capsule.tools[:3])}.")
    return _dedupe_text(moves, limit=_TEXT_LIMIT)


def _score_for(rubric: Sequence[TasteAxisScore], axis: str) -> float:
    for score in rubric:
        if score.axis == axis:
            return score.score
    return 0.5
