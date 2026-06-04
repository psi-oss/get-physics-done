"""Read-only quality audit for Research Persona profiles."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gpd.core.research_persona import (
    RESEARCH_PERSONA_CAPSULE_ROLE_VALUES,
    RESEARCH_PERSONA_CONFIDENCE_VALUES,
    RESEARCH_PERSONA_PRIVACY_VALUES,
    RESEARCH_PERSONA_SOURCE_KIND_VALUES,
    RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS,
    ResearchPersona,
    ResearchPersonaAxis,
    ResearchPersonaError,
    ResearchPersonaFact,
    ResearchPersonaPatch,
    ResearchPersonaPatchOperation,
    ResearchPersonaTombstone,
    build_research_persona_capsule,
    parse_research_persona_data_strict,
    project_research_persona,
    validate_research_persona,
)

__all__ = [
    "ResearchPersonaAuditFinding",
    "ResearchPersonaAuditPatchAction",
    "ResearchPersonaAuditReport",
    "ResearchPersonaCapsuleReadiness",
    "audit_research_persona_profile",
]


ResearchPersonaAuditSeverity = Literal["info", "warning", "error"]
ResearchPersonaAuditSubjectKind = Literal["profile", "fact", "axis", "capsule", "model"]
_AUDIT_SCHEMA_VERSION = "research_persona_audit.v1"
_CANDIDATE_REASON = "Candidate maintenance patch from read-only research persona audit."
_SENSITIVE_PROMPT_CATEGORIES = {"contact", "identity", "collaborator", "private_paper"}
_READINESS_ROLES = ("doppelganger", "explainer", "taste")
_WORD_RE = re.compile(r"[a-z0-9]+")


class _FrozenAuditModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ResearchPersonaAuditFinding(_FrozenAuditModel):
    """One value-redacted profile quality finding."""

    check: str
    severity: ResearchPersonaAuditSeverity
    subject_kind: ResearchPersonaAuditSubjectKind
    subject_id: str | None = None
    message: str
    evidence: dict[str, object] = Field(default_factory=dict)

    @field_validator("check", "message", mode="before")
    @classmethod
    def _required_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        text = value.strip()
        if not text:
            raise ValueError("must not be blank")
        return text

    @field_validator("subject_id", mode="before")
    @classmethod
    def _optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be a string or null")
        return value.strip() or None


class ResearchPersonaAuditPatchAction(_FrozenAuditModel):
    """Suggested maintenance action. Applying it requires the normal patch route."""

    action: str
    severity: ResearchPersonaAuditSeverity
    target_kind: Literal["profile", "fact", "axis", "capsule"]
    target_id: str | None = None
    reason: str
    requires_user_approval: bool = True
    candidate_patch: ResearchPersonaPatch | None = None

    @field_validator("action", "reason", mode="before")
    @classmethod
    def _required_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        text = value.strip()
        if not text:
            raise ValueError("must not be blank")
        return text

    @field_validator("target_id", mode="before")
    @classmethod
    def _optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be a string or null")
        return value.strip() or None


class ResearchPersonaCapsuleReadiness(_FrozenAuditModel):
    """Prompt-capsule readiness summary for one application role."""

    role: Literal[*RESEARCH_PERSONA_CAPSULE_ROLE_VALUES]
    ready: bool
    prompt_safe: bool = True
    counts: dict[str, int] = Field(default_factory=dict)
    missing_signals: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchPersonaAuditReport(_FrozenAuditModel):
    """Strict JSON-ready read-only audit report."""

    schema_version: Literal["research_persona_audit.v1"] = _AUDIT_SCHEMA_VERSION
    generated_at: str
    valid: bool
    read_only: bool = True
    writes_persona_storage: bool = False
    counts: dict[str, int] = Field(default_factory=dict)
    prompt_projection_counts: dict[str, int] = Field(default_factory=dict)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    findings: list[ResearchPersonaAuditFinding] = Field(default_factory=list)
    capsule_readiness: list[ResearchPersonaCapsuleReadiness] = Field(default_factory=list)
    suggested_candidate_patch_actions: list[ResearchPersonaAuditPatchAction] = Field(default_factory=list)
    candidate_patch: ResearchPersonaPatch = Field(default_factory=ResearchPersonaPatch)


def _now_datetime(now: str | datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC).replace(microsecond=0)
    if isinstance(now, datetime):
        parsed = now
    elif isinstance(now, str):
        text = now.strip()
        if not text:
            raise ResearchPersonaError("now must not be blank")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ResearchPersonaError("now must be an ISO-8601 datetime") from exc
    else:
        raise ResearchPersonaError("now must be an ISO-8601 string, datetime, or null")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _counts_from_payload(payload: dict[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field_name in ("facts", "axes", *RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS):
        value = payload.get(field_name)
        counts[field_name] = len(value) if isinstance(value, list) else 0
    return counts


def _severity_counts(findings: list[ResearchPersonaAuditFinding]) -> dict[str, int]:
    counts = Counter(finding.severity for finding in findings)
    return {severity: counts.get(severity, 0) for severity in ("info", "warning", "error")}


def _finding(
    check: str,
    severity: ResearchPersonaAuditSeverity,
    subject_kind: ResearchPersonaAuditSubjectKind,
    message: str,
    *,
    subject_id: str | None = None,
    evidence: dict[str, object] | None = None,
) -> ResearchPersonaAuditFinding:
    return ResearchPersonaAuditFinding(
        check=check,
        severity=severity,
        subject_kind=subject_kind,
        subject_id=subject_id,
        message=message,
        evidence=evidence or {},
    )


def _action(
    action: str,
    severity: ResearchPersonaAuditSeverity,
    target_kind: Literal["profile", "fact", "axis", "capsule"],
    reason: str,
    *,
    target_id: str | None = None,
    candidate_patch: ResearchPersonaPatch | None = None,
) -> ResearchPersonaAuditPatchAction:
    return ResearchPersonaAuditPatchAction(
        action=action,
        severity=severity,
        target_kind=target_kind,
        target_id=target_id,
        reason=reason,
        candidate_patch=candidate_patch,
    )


def _raw_validation_findings(data: object) -> list[ResearchPersonaAuditFinding]:
    findings: list[ResearchPersonaAuditFinding] = []
    result = validate_research_persona(data)
    if result.valid:
        return findings
    for message in result.errors:
        findings.append(
            _finding(
                "model_validation",
                "error",
                "model",
                message,
                evidence={"source": "ResearchPersona.model_validate"},
            )
        )
    if not isinstance(data, dict):
        return findings

    facts = data.get("facts")
    if isinstance(facts, list):
        for index, item in enumerate(facts):
            if not isinstance(item, dict):
                continue
            subject_id = str(item.get("id") or f"facts[{index}]")
            _append_literal_findings(
                findings,
                item,
                subject_kind="fact",
                subject_id=subject_id,
                fields={
                    "privacy": RESEARCH_PERSONA_PRIVACY_VALUES,
                    "confidence": RESEARCH_PERSONA_CONFIDENCE_VALUES,
                },
            )
            sources = item.get("sources")
            if isinstance(sources, list):
                for source in sources:
                    if source not in RESEARCH_PERSONA_SOURCE_KIND_VALUES:
                        findings.append(
                            _finding(
                                "invalid_source_kind",
                                "error",
                                "fact",
                                "Fact contains an unsupported source kind.",
                                subject_id=subject_id,
                                evidence={"source_kind": str(source)},
                            )
                        )

    axes = data.get("axes")
    if isinstance(axes, list):
        for index, item in enumerate(axes):
            if not isinstance(item, dict):
                continue
            subject_id = str(item.get("id") or f"axes[{index}]")
            _append_literal_findings(
                findings,
                item,
                subject_kind="axis",
                subject_id=subject_id,
                fields={
                    "privacy": RESEARCH_PERSONA_PRIVACY_VALUES,
                    "confidence": RESEARCH_PERSONA_CONFIDENCE_VALUES,
                },
            )
    return findings


def _append_literal_findings(
    findings: list[ResearchPersonaAuditFinding],
    item: dict[str, object],
    *,
    subject_kind: Literal["fact", "axis"],
    subject_id: str,
    fields: dict[str, tuple[str, ...]],
) -> None:
    for field_name, choices in fields.items():
        value = item.get(field_name)
        if value is None or value in choices:
            continue
        findings.append(
            _finding(
                f"invalid_{field_name}",
                "error",
                subject_kind,
                f"{subject_kind.capitalize()} contains an unsupported {field_name}.",
                subject_id=subject_id,
                evidence={field_name: str(value)},
            )
        )


def _normalize_value(value: str) -> str:
    return " ".join(_WORD_RE.findall(value.casefold()))


def _token_set(value: str) -> set[str]:
    return set(_WORD_RE.findall(value.casefold()))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _remove_fact_patch(fact_id: str, *, reason: str) -> ResearchPersonaPatch:
    return ResearchPersonaPatch(
        source_kind="manual_patch",
        reason=reason,
        tombstones=[
            ResearchPersonaTombstone(
                fact_id=fact_id,
                reason=reason,
                source_kind="manual_patch",
            )
        ],
        operations=[
            ResearchPersonaPatchOperation(
                op="tombstone_fact",
                fact_id=fact_id,
                reason=reason,
            )
        ],
    )


def _repair_axis_patch(axis: ResearchPersonaAxis, fact_ids: list[str], *, reason: str) -> ResearchPersonaPatch:
    return ResearchPersonaPatch(
        source_kind="manual_patch",
        reason=reason,
        operations=[
            ResearchPersonaPatchOperation(
                op="update",
                path=f"/axes/{axis.id}",
                value={"fact_ids": fact_ids},
                reason=reason,
            )
        ],
    )


def _append_fact_quality_findings(
    persona: ResearchPersona,
    *,
    now: datetime,
    stale_after_days: int,
    findings: list[ResearchPersonaAuditFinding],
    actions: list[ResearchPersonaAuditPatchAction],
) -> None:
    stale_cutoff = now - timedelta(days=stale_after_days)
    prompt = project_research_persona(persona, purpose="prompt")
    prompt_fact_ids = {
        str(item.get("id")) for item in prompt.get("facts", []) if isinstance(item, dict) and item.get("id") is not None
    }

    for fact in persona.facts:
        if fact.confidence == "disputed":
            findings.append(
                _finding(
                    "disputed_fact",
                    "error",
                    "fact",
                    "Fact is disputed and should not silently steer future work.",
                    subject_id=fact.id,
                    evidence={"category": fact.category},
                )
            )
            actions.append(
                _action(
                    "review_disputed_fact",
                    "error",
                    "fact",
                    "Resolve, replace, or tombstone the disputed fact through the governed patch route.",
                    target_id=fact.id,
                )
            )
        if fact.confidence == "stale":
            findings.append(
                _finding(
                    "stale_fact",
                    "warning",
                    "fact",
                    "Fact is marked stale and needs reconfirmation or removal.",
                    subject_id=fact.id,
                    evidence={"category": fact.category},
                )
            )
            actions.append(
                _action(
                    "refresh_stale_fact",
                    "warning",
                    "fact",
                    "Reconfirm the fact, lower its influence, or tombstone it after user review.",
                    target_id=fact.id,
                )
            )
        if fact.confidence == "inferred" and fact.last_confirmed_at is None:
            findings.append(
                _finding(
                    "unconfirmed_fact",
                    "warning",
                    "fact",
                    "Inferred fact has not been explicitly confirmed.",
                    subject_id=fact.id,
                    evidence={"category": fact.category},
                )
            )
            actions.append(
                _action(
                    "confirm_or_revise_fact",
                    "warning",
                    "fact",
                    "Ask the user to confirm, revise, or remove the inferred fact.",
                    target_id=fact.id,
                )
            )
        _append_fact_time_findings(fact, now=now, stale_cutoff=stale_cutoff, findings=findings, actions=actions)
        _append_fact_privacy_findings(fact, prompt_fact_ids=prompt_fact_ids, findings=findings, actions=actions)
        _append_fact_evidence_findings(fact, findings=findings, actions=actions)


def _append_fact_time_findings(
    fact: ResearchPersonaFact,
    *,
    now: datetime,
    stale_cutoff: datetime,
    findings: list[ResearchPersonaAuditFinding],
    actions: list[ResearchPersonaAuditPatchAction],
) -> None:
    confirmed_at = _parse_optional_datetime(fact.last_confirmed_at)
    if fact.last_confirmed_at is not None and confirmed_at is None:
        findings.append(
            _finding(
                "invalid_last_confirmed_at",
                "warning",
                "fact",
                "Fact has a last_confirmed_at value that is not ISO-8601 parseable.",
                subject_id=fact.id,
            )
        )
    elif confirmed_at is not None and confirmed_at < stale_cutoff:
        findings.append(
            _finding(
                "stale_confirmation",
                "warning",
                "fact",
                "Fact has not been reconfirmed within the configured freshness window.",
                subject_id=fact.id,
                evidence={"last_confirmed_at": fact.last_confirmed_at},
            )
        )
        actions.append(
            _action(
                "reconfirm_fact",
                "warning",
                "fact",
                "Reconfirm the fact before relying on it for personalized behavior.",
                target_id=fact.id,
            )
        )

    expires_at = _parse_optional_datetime(fact.expires_at)
    if fact.expires_at is not None and expires_at is None:
        findings.append(
            _finding(
                "invalid_expires_at",
                "warning",
                "fact",
                "Fact has an expires_at value that is not ISO-8601 parseable.",
                subject_id=fact.id,
            )
        )
    elif expires_at is not None and expires_at <= now:
        findings.append(
            _finding(
                "expired_fact",
                "warning",
                "fact",
                "Fact is past its expiry timestamp.",
                subject_id=fact.id,
                evidence={"expires_at": fact.expires_at},
            )
        )
        actions.append(
            _action(
                "remove_or_refresh_expired_fact",
                "warning",
                "fact",
                "Refresh the fact with user approval or tombstone it through apply-patch.",
                target_id=fact.id,
            )
        )


def _append_fact_privacy_findings(
    fact: ResearchPersonaFact,
    *,
    prompt_fact_ids: set[str],
    findings: list[ResearchPersonaAuditFinding],
    actions: list[ResearchPersonaAuditPatchAction],
) -> None:
    if fact.privacy == "never_prompt":
        findings.append(
            _finding(
                "never_prompt_fact",
                "info",
                "fact",
                "Fact is explicitly excluded from prompt-facing projections.",
                subject_id=fact.id,
                evidence={"category": fact.category},
            )
        )
        return
    if fact.id not in prompt_fact_ids:
        findings.append(
            _finding(
                "private_not_prompt_projected",
                "info",
                "fact",
                "Fact is private and will not project to prompt-safe capsules.",
                subject_id=fact.id,
                evidence={"privacy": fact.privacy, "category": fact.category},
            )
        )
        actions.append(
            _action(
                "review_prompt_shareability",
                "info",
                "fact",
                "If useful for agent behavior, ask the user before creating a safe_to_share replacement.",
                target_id=fact.id,
            )
        )
    if fact.privacy == "safe_to_share" and fact.category in _SENSITIVE_PROMPT_CATEGORIES:
        findings.append(
            _finding(
                "sensitive_prompt_fact",
                "warning",
                "fact",
                "Safe-to-share fact belongs to a sensitive category and should be reconfirmed.",
                subject_id=fact.id,
                evidence={"category": fact.category},
            )
        )


def _append_fact_evidence_findings(
    fact: ResearchPersonaFact,
    *,
    findings: list[ResearchPersonaAuditFinding],
    actions: list[ResearchPersonaAuditPatchAction],
) -> None:
    if fact.sources and not fact.evidence_refs:
        findings.append(
            _finding(
                "missing_evidence_refs",
                "warning",
                "fact",
                "Fact names sources but has no evidence_refs for review.",
                subject_id=fact.id,
                evidence={"source_count": len(fact.sources)},
            )
        )
        actions.append(
            _action(
                "attach_evidence_refs",
                "warning",
                "fact",
                "Attach evidence references from a consented source-ingestion packet.",
                target_id=fact.id,
            )
        )


def _append_axis_findings(
    persona: ResearchPersona,
    *,
    findings: list[ResearchPersonaAuditFinding],
    actions: list[ResearchPersonaAuditPatchAction],
) -> None:
    fact_ids = {fact.id for fact in persona.facts}
    for axis in persona.axes:
        missing_ids = [fact_id for fact_id in axis.fact_ids if fact_id not in fact_ids]
        if missing_ids:
            kept_ids = [fact_id for fact_id in axis.fact_ids if fact_id in fact_ids]
            reason = f"Remove orphan fact references from axis {axis.id}."
            patch = _repair_axis_patch(axis, kept_ids, reason=reason)
            findings.append(
                _finding(
                    "orphan_axis_fact_ids",
                    "error",
                    "axis",
                    "Axis references fact ids that are not present in the profile.",
                    subject_id=axis.id,
                    evidence={"missing_fact_ids": missing_ids},
                )
            )
            actions.append(
                _action(
                    "repair_axis_fact_ids",
                    "error",
                    "axis",
                    reason,
                    target_id=axis.id,
                    candidate_patch=patch,
                )
            )
        if axis.evidence_refs == [] and axis.fact_ids == []:
            findings.append(
                _finding(
                    "axis_without_evidence",
                    "warning",
                    "axis",
                    "Axis has neither fact_ids nor evidence_refs backing it.",
                    subject_id=axis.id,
                )
            )
            actions.append(
                _action(
                    "attach_axis_evidence",
                    "warning",
                    "axis",
                    "Attach backing facts or evidence references to the axis.",
                    target_id=axis.id,
                )
            )


def _append_duplicate_findings(
    persona: ResearchPersona,
    *,
    findings: list[ResearchPersonaAuditFinding],
    actions: list[ResearchPersonaAuditPatchAction],
) -> None:
    by_key: dict[tuple[str, str], list[ResearchPersonaFact]] = defaultdict(list)
    for fact in persona.facts:
        by_key[(fact.category, _normalize_value(fact.value))].append(fact)

    tombstone_ids: set[str] = set()
    for group in by_key.values():
        if len(group) < 2:
            continue
        keeper = sorted(group, key=lambda fact: fact.id)[0]
        for duplicate in sorted(group, key=lambda fact: fact.id)[1:]:
            reason = f"Review duplicate-ish fact {duplicate.id}; likely duplicate of {keeper.id}."
            patch = _remove_fact_patch(duplicate.id, reason=reason)
            tombstone_ids.add(duplicate.id)
            findings.append(
                _finding(
                    "duplicate_fact",
                    "warning",
                    "fact",
                    "Fact has the same normalized category and value as another fact.",
                    subject_id=duplicate.id,
                    evidence={"possible_duplicate_of": keeper.id, "category": duplicate.category},
                )
            )
            actions.append(
                _action(
                    "review_duplicate_fact",
                    "warning",
                    "fact",
                    reason,
                    target_id=duplicate.id,
                    candidate_patch=patch,
                )
            )

    facts_by_category: dict[str, list[ResearchPersonaFact]] = defaultdict(list)
    for fact in persona.facts:
        facts_by_category[fact.category].append(fact)
    for category_facts in facts_by_category.values():
        for index, left in enumerate(category_facts):
            left_tokens = _token_set(left.value)
            for right in category_facts[index + 1 :]:
                if right.id in tombstone_ids:
                    continue
                score = _jaccard(left_tokens, _token_set(right.value))
                if score < 0.82:
                    continue
                findings.append(
                    _finding(
                        "near_duplicate_fact",
                        "warning",
                        "fact",
                        "Fact is textually similar to another fact in the same category.",
                        subject_id=right.id,
                        evidence={
                            "possible_duplicate_of": left.id,
                            "category": right.category,
                            "similarity": round(score, 3),
                        },
                    )
                )
                actions.append(
                    _action(
                        "review_near_duplicate_fact",
                        "warning",
                        "fact",
                        "Merge, rewrite, or tombstone one of the near-duplicate facts after user review.",
                        target_id=right.id,
                    )
                )


def _capsule_counts(capsule_payload: dict[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field_name in (
        "facts",
        "axes",
        "standing_preferences",
        "negative_preferences",
        "tools",
        "research_areas",
        "expertise",
        "workstyle",
        "scientific_taste",
    ):
        value = capsule_payload.get(field_name)
        counts[field_name] = len(value) if isinstance(value, list) else 0
    return counts


def _capsule_category_counts(capsule_payload: dict[str, object]) -> Counter[str]:
    counts: Counter[str] = Counter()
    facts = capsule_payload.get("facts")
    if isinstance(facts, list):
        for fact in facts:
            if isinstance(fact, dict) and isinstance(fact.get("category"), str):
                counts[str(fact["category"])] += 1
    return counts


def _readiness_for_role(persona: ResearchPersona, role: str) -> ResearchPersonaCapsuleReadiness:
    capsule = build_research_persona_capsule(persona, role=role)
    payload = capsule.model_dump(mode="json")
    counts = _capsule_counts(payload)
    categories = _capsule_category_counts(payload)
    missing: list[str] = []
    warnings: list[str] = []

    if role == "doppelganger":
        signal_count = (
            counts["facts"]
            + counts["standing_preferences"]
            + counts["negative_preferences"]
            + counts["tools"]
            + counts["research_areas"]
            + counts["expertise"]
            + counts["workstyle"]
            + counts["scientific_taste"]
        )
        if signal_count < 2:
            missing.append("at least two prompt-safe preference, expertise, workstyle, or taste signals")
    elif role == "explainer":
        signal_count = (
            counts["expertise"]
            + counts["research_areas"]
            + counts["tools"]
            + counts["workstyle"]
            + categories["expertise"]
            + categories["research_area"]
            + categories["tool"]
            + categories["workstyle"]
        )
        if signal_count < 1:
            missing.append("prompt-safe expertise, tool, research-area, or workstyle signal")
    elif role == "taste":
        taste_axis_count = sum(
            1
            for axis in payload.get("axes", [])
            if isinstance(axis, dict) and "taste" in str(axis.get("id", "")).casefold()
        )
        signal_count = (
            counts["scientific_taste"]
            + categories["scientific_taste"]
            + categories["taste"]
            + categories["research_area"]
            + taste_axis_count
        )
        if signal_count < 1:
            missing.append("prompt-safe scientific taste, taste axis, or research-area signal")

    if counts["facts"] == 0:
        warnings.append("No prompt-safe facts are available for this role.")
    return ResearchPersonaCapsuleReadiness(
        role=role,  # type: ignore[arg-type]
        ready=not missing,
        prompt_safe=True,
        counts=counts,
        missing_signals=missing,
        warnings=warnings,
    )


def _capsule_readiness(
    persona: ResearchPersona,
    *,
    findings: list[ResearchPersonaAuditFinding],
    actions: list[ResearchPersonaAuditPatchAction],
) -> list[ResearchPersonaCapsuleReadiness]:
    readiness_rows = [_readiness_for_role(persona, role) for role in _READINESS_ROLES]
    for row in readiness_rows:
        if row.ready:
            continue
        findings.append(
            _finding(
                "capsule_not_ready",
                "warning",
                "capsule",
                "Role capsule lacks enough prompt-safe persona signal.",
                subject_id=row.role,
                evidence={"missing_signals": list(row.missing_signals)},
            )
        )
        actions.append(
            _action(
                "add_prompt_safe_persona_signal",
                "warning",
                "capsule",
                "Use build-persona or source ingestion to add user-approved safe_to_share signals for this role.",
                target_id=row.role,
            )
        )
    return readiness_rows


def _combined_candidate_patch(actions: list[ResearchPersonaAuditPatchAction]) -> ResearchPersonaPatch:
    operations: list[ResearchPersonaPatchOperation] = []
    tombstones: list[ResearchPersonaTombstone] = []
    seen_operations: set[str] = set()
    seen_tombstones: set[str] = set()
    for action in actions:
        patch = action.candidate_patch
        if patch is None:
            continue
        for operation in patch.operations:
            key = operation.model_dump_json()
            if key in seen_operations:
                continue
            seen_operations.add(key)
            operations.append(operation)
        for tombstone in patch.tombstones:
            key = tombstone.fact_id
            if key in seen_tombstones:
                continue
            seen_tombstones.add(key)
            tombstones.append(tombstone)
    return ResearchPersonaPatch(
        source_kind="manual_patch",
        reason=_CANDIDATE_REASON,
        operations=operations,
        tombstones=tombstones,
    )


def _filter_findings(
    findings: list[ResearchPersonaAuditFinding],
    actions: list[ResearchPersonaAuditPatchAction],
    *,
    include_info: bool,
) -> tuple[list[ResearchPersonaAuditFinding], list[ResearchPersonaAuditPatchAction]]:
    if include_info:
        return findings, actions
    return (
        [finding for finding in findings if finding.severity != "info"],
        [action for action in actions if action.severity != "info"],
    )


def _report(
    *,
    generated_at: str,
    valid: bool,
    counts: dict[str, int] | None = None,
    prompt_projection_counts: dict[str, int] | None = None,
    findings: list[ResearchPersonaAuditFinding],
    actions: list[ResearchPersonaAuditPatchAction],
    capsule_readiness: list[ResearchPersonaCapsuleReadiness] | None = None,
) -> ResearchPersonaAuditReport:
    candidate_patch = _combined_candidate_patch(actions)
    return ResearchPersonaAuditReport(
        generated_at=generated_at,
        valid=valid,
        counts=counts or {},
        prompt_projection_counts=prompt_projection_counts or {},
        severity_counts=_severity_counts(findings),
        findings=findings,
        capsule_readiness=capsule_readiness or [],
        suggested_candidate_patch_actions=actions,
        candidate_patch=candidate_patch,
    )


def audit_research_persona_profile(
    data: object,
    *,
    now: str | datetime | None = None,
    stale_after_days: int = 180,
    include_info: bool = True,
) -> ResearchPersonaAuditReport:
    """Return a read-only maintenance audit for a research persona profile."""

    if stale_after_days < 1:
        raise ResearchPersonaError("stale_after_days must be at least 1")
    now_dt = _now_datetime(now)
    generated_at = now_dt.isoformat().replace("+00:00", "Z")
    raw_findings = _raw_validation_findings(data)
    if raw_findings:
        findings, actions = _filter_findings(raw_findings, [], include_info=include_info)
        return _report(generated_at=generated_at, valid=False, findings=findings, actions=actions)

    persona = parse_research_persona_data_strict(data)
    findings: list[ResearchPersonaAuditFinding] = []
    actions: list[ResearchPersonaAuditPatchAction] = []
    _append_fact_quality_findings(
        persona,
        now=now_dt,
        stale_after_days=stale_after_days,
        findings=findings,
        actions=actions,
    )
    _append_axis_findings(persona, findings=findings, actions=actions)
    _append_duplicate_findings(persona, findings=findings, actions=actions)
    readiness = _capsule_readiness(persona, findings=findings, actions=actions)
    findings, actions = _filter_findings(findings, actions, include_info=include_info)
    prompt_projection = project_research_persona(persona, purpose="prompt")
    return _report(
        generated_at=generated_at,
        valid=True,
        counts=_counts_from_payload(persona.model_dump(mode="json")),
        prompt_projection_counts=_counts_from_payload(prompt_projection),
        findings=findings,
        actions=actions,
        capsule_readiness=readiness,
    )
