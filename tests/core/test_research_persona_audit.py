from __future__ import annotations

import json

from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaAxis,
    ResearchPersonaFact,
)
from gpd.core.research_persona_audit import (
    ResearchPersonaAuditReport,
    audit_research_persona_profile,
)

NOW = "2026-06-04T12:00:00Z"
CHECK_CAPSULE = "capsule_not_ready"
CHECK_DISPUTED = "disputed_fact"
CHECK_DUPLICATE = "duplicate_fact"
CHECK_INVALID_CONFIDENCE = "invalid_confidence"
CHECK_INVALID_PRIVACY = "invalid_privacy"
CHECK_INVALID_SOURCE = "invalid_source_kind"
CHECK_MISSING_EVIDENCE = "missing_evidence_refs"
CHECK_MODEL = "model_validation"
CHECK_NEVER = "never_prompt_fact"
CHECK_ORPHAN_AXIS = "orphan_axis_fact_ids"
CHECK_PRIVATE = "private_not_prompt_projected"
CHECK_STALE = "stale_fact"
CHECK_UNCONFIRMED = "unconfirmed_fact"
SEVERITY_ERROR = "error"
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
OP_TOMBSTONE = "tombstone_fact"
OP_UPDATE = "update"
ROLE_DOPPELGANGER = "doppelganger"
ROLE_EXPLAINER = "explainer"
ROLE_TASTE = "taste"
PRIVATE_TOKEN = "AUDIT_PRIVATE_CANARY local notebook detail"
NEVER_TOKEN = "AUDIT_NEVER_CANARY identity detail"


def _fact(
    fact_id: str,
    *,
    value: str,
    privacy: str = "safe_to_share",
    confidence: str = "confirmed",
    category: str = "workstyle",
    evidence_refs: list[str] | None = None,
) -> ResearchPersonaFact:
    return ResearchPersonaFact(
        id=fact_id,
        category=category,
        value=value,
        privacy=privacy,
        confidence=confidence,
        sources=["user_statement"],
        evidence_refs=evidence_refs or [],
    )


def _checks(report: ResearchPersonaAuditReport) -> set[str]:
    return {finding.check for finding in report.findings}


def _findings_by_check(report: ResearchPersonaAuditReport) -> dict[str, list[str | None]]:
    rows: dict[str, list[str | None]] = {}
    for finding in report.findings:
        rows.setdefault(finding.check, []).append(finding.subject_id)
    return rows


def test_audit_reports_quality_controls_and_candidate_patch_without_storage_mutation() -> None:
    persona = ResearchPersona(
        facts=[
            _fact(
                "fact.private",
                value=PRIVATE_TOKEN,
                privacy="private_local",
                confidence="inferred",
            ),
            _fact("fact.never", value=NEVER_TOKEN, privacy="never_prompt"),
            _fact("fact.stale", value="Prefer theorem-first reviews", confidence="stale", evidence_refs=["ev:1"]),
            _fact("fact.disputed", value="Avoid all code", confidence="disputed", evidence_refs=["ev:2"]),
            _fact("fact.dup.a", value="Use pytest for executable checks", evidence_refs=["ev:3"]),
            _fact("fact.dup.b", value="use pytest for executable checks", evidence_refs=["ev:4"]),
        ],
        axes=[
            ResearchPersonaAxis(
                id="axis.math",
                name="math emphasis",
                value=0.9,
                privacy="safe_to_share",
                confidence="confirmed",
                fact_ids=["fact.dup.a", "fact.missing"],
            )
        ],
    )

    report = audit_research_persona_profile(persona, now=NOW)
    checks = _checks(report)
    operations = [operation.op for operation in report.candidate_patch.operations]
    rendered = json.dumps(report.model_dump(mode="json"), sort_keys=True)

    assert isinstance(report, ResearchPersonaAuditReport)
    assert report.valid is True
    assert report.read_only is True
    assert report.writes_persona_storage is False
    assert report.severity_counts[SEVERITY_ERROR] >= 2
    assert report.severity_counts[SEVERITY_WARNING] >= 4
    assert report.severity_counts[SEVERITY_INFO] >= 2
    assert {
        CHECK_DISPUTED,
        CHECK_DUPLICATE,
        CHECK_MISSING_EVIDENCE,
        CHECK_NEVER,
        CHECK_ORPHAN_AXIS,
        CHECK_PRIVATE,
        CHECK_STALE,
        CHECK_UNCONFIRMED,
    } <= checks
    assert OP_TOMBSTONE in operations
    assert OP_UPDATE in operations
    assert PRIVATE_TOKEN not in rendered
    assert NEVER_TOKEN not in rendered


def test_audit_flags_capsule_readiness_for_application_roles() -> None:
    persona = ResearchPersona(
        facts=[
            _fact(
                "fact.only-private",
                value=PRIVATE_TOKEN,
                privacy="private_local",
                evidence_refs=["ev:private"],
            )
        ]
    )

    report = audit_research_persona_profile(persona, now=NOW)
    readiness = {row.role: row for row in report.capsule_readiness}

    assert set(readiness) == {ROLE_DOPPELGANGER, ROLE_EXPLAINER, ROLE_TASTE}
    assert all(row.prompt_safe is True for row in readiness.values())
    assert all(row.ready is False for row in readiness.values())
    assert CHECK_CAPSULE in _checks(report)


def test_audit_uses_existing_model_validation_for_invalid_literals() -> None:
    raw_profile = {
        "schema_version": 1,
        "facts": [
            {
                "id": "fact.bad",
                "category": "tool",
                "value": "Julia",
                "confidence": "certain",
                "privacy": "public",
                "sources": ["email"],
            }
        ],
        "axes": [
            {
                "id": "axis.bad",
                "confidence": "certain",
                "privacy": "public",
            }
        ],
    }

    report = audit_research_persona_profile(raw_profile, now=NOW)
    rows = _findings_by_check(report)

    assert report.valid is False
    assert CHECK_MODEL in rows
    assert CHECK_INVALID_CONFIDENCE in rows
    assert CHECK_INVALID_PRIVACY in rows
    assert CHECK_INVALID_SOURCE in rows
    assert report.candidate_patch.operations == []


def test_audit_can_suppress_informational_privacy_findings() -> None:
    persona = ResearchPersona(
        facts=[
            _fact(
                "fact.private",
                value=PRIVATE_TOKEN,
                privacy="private_local",
                evidence_refs=["ev:private"],
            ),
            _fact("fact.never", value=NEVER_TOKEN, privacy="never_prompt", evidence_refs=["ev:never"]),
        ]
    )

    report = audit_research_persona_profile(persona, now=NOW, include_info=False)

    assert SEVERITY_INFO not in {finding.severity for finding in report.findings}
    assert CHECK_PRIVATE not in _checks(report)
    assert CHECK_NEVER not in _checks(report)
