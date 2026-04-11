"""Shared helpers for Phase 15 contract tests.

The helpers are intentionally repo-local and lightweight so contract tests can
read one authoritative registry instead of duplicating family metadata.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

PHASE15_SCHEMA_VERSION = 1
PHASE15_PHASE = "15"
PHASE15_WAVE = "F2-F5"
PHASE15_ARTIFACT_ROOT = Path("artifacts/phases/15-verification-contract/verification/fixes")
PHASE15_INDEX_PATH = PHASE15_ARTIFACT_ROOT / "index.json"
PHASE15_PR_TEMPLATE_PATH = Path(".github/pull_request_template.md")

PHASE15_CHECKLIST_ITEMS = (
    "Red exact repro",
    "Green exact fix",
    "Green adjacent checks",
    "Artifact JSON written",
)


@dataclass(frozen=True, slots=True)
class Phase15ContractFamily:
    """One fixed family tracked by the Phase 15 verification registry."""

    bug_id: str
    family_id: str
    family_title: str
    contract_test: str
    artifact_path: str
    status: str = "planned"
    classification: str = "verification_contract"


PHASE15_FAMILIES: tuple[Phase15ContractFamily, ...] = (
    Phase15ContractFamily(
        bug_id="phase-read-model-alignment",
        family_id="phase-read-model-alignment",
        family_title="phase/read-model alignment",
        contract_test="tests/test_bug_phase_read_model_alignment.py",
        artifact_path=str(PHASE15_ARTIFACT_ROOT / "phase-read-model-alignment.json"),
        status="verified",
    ),
    Phase15ContractFamily(
        bug_id="placeholder-sentinel-normalization",
        family_id="placeholder-sentinel-normalization",
        family_title="placeholder/sentinel normalization",
        contract_test="tests/test_bug_placeholder_sentinel_normalization.py",
        artifact_path=str(PHASE15_ARTIFACT_ROOT / "placeholder-sentinel-normalization.json"),
        status="ready",
    ),
    Phase15ContractFamily(
        bug_id="query-result-registry-projection",
        family_id="query-result-registry-projection",
        family_title="query/result registry projection",
        contract_test="tests/core/test_projection_query_result.py",
        artifact_path=str(PHASE15_ARTIFACT_ROOT / "query-result-registry-projection.json"),
        status="verified",
        classification="cross_surface_projection_contract",
    ),
    Phase15ContractFamily(
        bug_id="nested-root-readonly-probe-parity",
        family_id="nested-root-readonly-probe-parity",
        family_title="nested-root read-only probe parity",
        contract_test="tests/test_bug_nested_root_readonly_probe_parity.py",
        artifact_path=str(PHASE15_ARTIFACT_ROOT / "nested-root-readonly-probe-parity.json"),
        status="closed",
        classification="projection_bug",
    ),
    Phase15ContractFamily(
        bug_id="resume-recent-selection-control",
        family_id="resume-recent-selection-control",
        family_title="resume recent selection control",
        contract_test="tests/test_bug_resume_state_continuity.py",
        artifact_path=str(PHASE15_ARTIFACT_ROOT / "resume-recent-selection-control.json"),
        status="closed",
    ),
    Phase15ContractFamily(
        bug_id="canonical-session-continuation-access",
        family_id="canonical-session-continuation-access",
        family_title="canonical session / continuation access",
        contract_test="tests/test_bug_resume_state_continuity.py",
        artifact_path=str(PHASE15_ARTIFACT_ROOT / "canonical-session-continuation-access.json"),
        status="closed",
    ),
    Phase15ContractFamily(
        bug_id="runtime-bridge-classification",
        family_id="runtime-bridge-classification",
        family_title="runtime bridge classification",
        contract_test="tests/test_bug_runtime_recovery_contract.py",
        artifact_path=str(PHASE15_ARTIFACT_ROOT / "runtime-bridge-classification.json"),
        status="closed",
        classification="cross_surface_recovery_contract",
    ),
    Phase15ContractFamily(
        bug_id="doctor-target-readiness-contract",
        family_id="doctor-target-readiness-contract",
        family_title="doctor target / readiness contract",
        contract_test="tests/test_bug_runtime_recovery_contract.py",
        artifact_path=str(PHASE15_ARTIFACT_ROOT / "doctor-target-readiness-contract.json"),
        status="closed",
        classification="cross_surface_recovery_contract",
    ),
    Phase15ContractFamily(
        bug_id="observability-degraded-visibility",
        family_id="observability-degraded-visibility",
        family_title="observability degraded visibility",
        contract_test="tests/test_bug_runtime_recovery_contract.py",
        artifact_path=str(PHASE15_ARTIFACT_ROOT / "observability-degraded-visibility.json"),
        status="closed",
        classification="cross_surface_recovery_contract",
    ),
)


def phase15_contract_index() -> dict[str, object]:
    """Return the canonical on-disk registry payload for Phase 15."""

    return {
        "schema_version": PHASE15_SCHEMA_VERSION,
        "phase": PHASE15_PHASE,
        "wave": PHASE15_WAVE,
        "artifact_root": str(PHASE15_ARTIFACT_ROOT),
        "families": [asdict(family) for family in PHASE15_FAMILIES],
        "checklist_items": list(PHASE15_CHECKLIST_ITEMS),
    }


def load_phase15_contract_index(path: Path | None = None) -> dict[str, object]:
    """Load the Phase 15 contract index from disk."""

    index_path = path or PHASE15_INDEX_PATH
    return json.loads(index_path.read_text(encoding="utf-8"))


def phase15_family_ids() -> tuple[str, ...]:
    """Return the canonical family identifiers in registry order."""

    return tuple(family.family_id for family in PHASE15_FAMILIES)


def phase15_checklist_items() -> tuple[str, ...]:
    """Return the Phase 15 checklist gate labels."""

    return PHASE15_CHECKLIST_ITEMS
