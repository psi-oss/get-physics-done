"""GPD contracts -- shared data types for conventions, planning, and verification."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError

from gpd.core.utils import dedupe_preserve_order

__all__ = [
    "ConventionLock",
    "VerificationEvidence",
    "ContractProofParameter",
    "ContractProofHypothesis",
    "ContractProofConclusionClause",
    "ContractProofAudit",
    "THEOREM_STYLE_STATEMENT_REGEX_PATTERNS",
    "CONTRACT_OBSERVABLE_KIND_VALUES",
    "CONTRACT_CLAIM_KIND_VALUES",
    "THEOREM_CLAIM_KIND_VALUES",
    "CONTRACT_DELIVERABLE_KIND_VALUES",
    "CONTRACT_ACCEPTANCE_TEST_KIND_VALUES",
    "CONTRACT_ACCEPTANCE_AUTOMATION_VALUES",
    "CONTRACT_REFERENCE_KIND_VALUES",
    "CONTRACT_REFERENCE_ROLE_VALUES",
    "CONTRACT_REFERENCE_ACTION_VALUES",
    "CONTRACT_LINK_RELATION_VALUES",
    "CONTRACT_CONTEXT_INTAKE_FIELD_NAMES",
    "CONTRACT_APPROACH_POLICY_FIELD_NAMES",
    "CONTRACT_UNCERTAINTY_MARKER_FIELD_NAMES",
    "PROOF_ACCEPTANCE_TEST_KINDS",
    "PROOF_HYPOTHESIS_CATEGORY_VALUES",
    "PROOF_AUDIT_REVIEWER",
    "PROOF_AUDIT_QUANTIFIER_STATUS_VALUES",
    "PROOF_AUDIT_SCOPE_STATUS_VALUES",
    "PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES",
    "ContractEvidenceStatus",
    "ContractEvidenceEntry",
    "ContractResultEntry",
    "ContractReferenceActionStatus",
    "ContractReferenceUsage",
    "ContractForbiddenProxyStatus",
    "ContractForbiddenProxyResult",
    "ContractResults",
    "parse_contract_results_data_artifact",
    "parse_contract_results_data_strict",
    "parse_comparison_verdicts_data_strict",
    "SuggestedContractCheck",
    "ComparisonVerdict",
    "PROJECT_CONTRACT_MAPPING_LIST_FIELDS",
    "PROJECT_CONTRACT_TOP_LEVEL_LIST_FIELDS",
    "PROJECT_CONTRACT_COLLECTION_LIST_FIELDS",
    "ContractScope",
    "ContractContextIntake",
    "ContractApproachPolicy",
    "ContractObservable",
    "ContractClaim",
    "ContractDeliverable",
    "ContractAcceptanceTest",
    "ContractReference",
    "ContractForbiddenProxy",
    "ContractLink",
    "ContractUncertaintyMarkers",
    "ResearchContract",
    "collect_plan_contract_integrity_errors",
    "collect_proof_bearing_claim_integrity_errors",
    "contract_has_explicit_context_intake",
    "claim_requires_proof_audit",
    "statement_looks_theorem_like",
    "collect_proof_audit_alignment_errors",
    "ProjectContractParseResult",
    "parse_project_contract_data_strict",
    "parse_project_contract_data_salvage",
    "collect_contract_integrity_errors",
    "contract_from_data",
    "contract_from_data_salvage",
]


THEOREM_STYLE_STATEMENT_REGEX_PATTERNS: tuple[str, ...] = (
    r"^\s*(?:prove|show)\s+that\b",
    r"\bfor\s+all\b",
    r"\bfor\s+every\b",
    r"\b(?:there\s+)?exists\b",
    r"\bexistence\b",
    r"\bunique\b",
    r"\buniqueness\b",
)
_THEOREM_STYLE_STATEMENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern) for pattern in THEOREM_STYLE_STATEMENT_REGEX_PATTERNS
)

CONTRACT_OBSERVABLE_KIND_VALUES: tuple[str, ...] = (
    "scalar",
    "curve",
    "map",
    "classification",
    "proof_obligation",
    "other",
)
CONTRACT_CLAIM_KIND_VALUES: tuple[str, ...] = (
    "theorem",
    "lemma",
    "corollary",
    "proposition",
    "result",
    "claim",
    "other",
)
THEOREM_CLAIM_KIND_VALUES: tuple[str, ...] = ("theorem", "lemma", "corollary", "proposition", "claim")
CONTRACT_DELIVERABLE_KIND_VALUES: tuple[str, ...] = (
    "figure",
    "table",
    "dataset",
    "data",
    "derivation",
    "code",
    "note",
    "report",
    "other",
)
CONTRACT_ACCEPTANCE_TEST_KIND_VALUES: tuple[str, ...] = (
    "existence",
    "schema",
    "benchmark",
    "consistency",
    "cross_method",
    "limiting_case",
    "symmetry",
    "dimensional_analysis",
    "convergence",
    "oracle",
    "proxy",
    "reproducibility",
    "proof_hypothesis_coverage",
    "proof_parameter_coverage",
    "proof_quantifier_domain",
    "claim_to_proof_alignment",
    "lemma_dependency_closure",
    "counterexample_search",
    "human_review",
    "other",
)
CONTRACT_ACCEPTANCE_AUTOMATION_VALUES: tuple[str, ...] = ("automated", "hybrid", "human")
CONTRACT_REFERENCE_KIND_VALUES: tuple[str, ...] = ("paper", "dataset", "prior_artifact", "spec", "user_anchor", "other")
CONTRACT_REFERENCE_ROLE_VALUES: tuple[str, ...] = (
    "definition",
    "benchmark",
    "method",
    "must_consider",
    "background",
    "other",
)
CONTRACT_REFERENCE_ACTION_VALUES: tuple[str, ...] = ("read", "use", "compare", "cite", "avoid")
CONTRACT_LINK_RELATION_VALUES: tuple[str, ...] = (
    "supports",
    "computes",
    "visualizes",
    "benchmarks",
    "depends_on",
    "evaluated_by",
    "proves",
    "uses_hypothesis",
    "depends_on_lemma",
    "other",
)
CONTRACT_CONTEXT_INTAKE_FIELD_NAMES: tuple[str, ...] = (
    "must_read_refs",
    "must_include_prior_outputs",
    "user_asserted_anchors",
    "known_good_baselines",
    "context_gaps",
    "crucial_inputs",
)
CONTRACT_APPROACH_POLICY_FIELD_NAMES: tuple[str, ...] = (
    "formulations",
    "allowed_estimator_families",
    "forbidden_estimator_families",
    "allowed_fit_families",
    "forbidden_fit_families",
    "stop_and_rethink_conditions",
)
CONTRACT_UNCERTAINTY_MARKER_FIELD_NAMES: tuple[str, ...] = (
    "weakest_anchors",
    "unvalidated_assumptions",
    "competing_explanations",
    "disconfirming_observations",
)
PROOF_HYPOTHESIS_CATEGORY_VALUES: tuple[str, ...] = (
    "assumption",
    "precondition",
    "regime",
    "definition",
    "lemma",
    "other",
)
PROOF_AUDIT_QUANTIFIER_STATUS_VALUES: tuple[str, ...] = (
    "matched",
    "narrowed",
    "mismatched",
    "unclear",
)
PROOF_AUDIT_SCOPE_STATUS_VALUES: tuple[str, ...] = (
    "matched",
    "narrower_than_claim",
    "mismatched",
    "unclear",
)
PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES: tuple[str, ...] = (
    "none_found",
    "counterexample_found",
    "not_attempted",
    "narrowed_claim",
)

def _normalize_optional_str(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _normalize_non_empty_optional_str(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("must be a non-empty string")
        return stripped
    return value


def _normalize_required_str(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped
    return value


def _has_explanatory_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_non_empty_list(value: object) -> bool:
    return isinstance(value, list) and bool(value)


def _has_explanatory_contract_entry_content(*, summary: object = None, notes: object = None, evidence: object = None) -> bool:
    return _has_explanatory_text(summary) or _has_explanatory_text(notes) or _has_non_empty_list(evidence)


def _contract_result_gap_message(status: str) -> str:
    return f"status={status} requires summary, notes, or evidence explaining the gap"


def _contract_reference_gap_message(status: str) -> str:
    return f"status={status} requires summary or evidence explaining what is missing"


def _contract_forbidden_proxy_gap_message(status: str) -> str:
    return f"status={status} requires notes or evidence explaining the proxy issue"


def _normalize_strict_bool(value: object) -> object:
    if type(value) is bool:
        return value
    raise ValueError("must be a boolean")


def _normalize_optional_sha256(value: object) -> object:
    normalized = _normalize_optional_str(value)
    if normalized is None:
        return None
    lowered = str(normalized).lower()
    if len(lowered) != 64 or any(ch not in "0123456789abcdef" for ch in lowered):
        raise ValueError("must be a lowercase 64-hex digest")
    return lowered


def _normalize_string_list(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return [stripped]
    if not isinstance(value, list):
        return value
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            normalized.append(item)
            continue
        stripped = item.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        normalized.append(stripped)
    return normalized


def _normalize_strict_string_list(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return [stripped]
    if not isinstance(value, list):
        return value
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            normalized.append(item)
            continue
        stripped = item.strip()
        if not stripped:
            raise ValueError("must not contain blank entries")
        if stripped in seen:
            raise ValueError(f"duplicate entry not allowed: {stripped}")
        seen.add(stripped)
        normalized.append(stripped)
    return normalized


def _normalize_strict_literal_choice_list(value: object, choices: tuple[str, ...]) -> object:
    normalized = _normalize_strict_string_list(value)
    if not isinstance(normalized, list):
        return normalized

    canonicalized: list[object] = []
    seen: set[str] = set()
    for item in normalized:
        if not isinstance(item, str):
            canonicalized.append(item)
            continue
        choice = _normalize_literal_choice(item, choices)
        if not isinstance(choice, str):
            canonicalized.append(choice)
            continue
        if choice in seen:
            raise ValueError(f"duplicate entry not allowed: {choice}")
        seen.add(choice)
        canonicalized.append(choice)
    return canonicalized


def statement_looks_theorem_like(statement: str | None) -> bool:
    if not isinstance(statement, str):
        return False
    normalized = " ".join(statement.lower().split())
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _THEOREM_STYLE_STATEMENT_PATTERNS)


def is_placeholder_only_guidance_text(value: str) -> bool:
    """Return whether *value* is only placeholder guidance and not actionable context."""

    lowered = value.casefold().strip()
    if not lowered:
        return True
    return any(pattern.fullmatch(lowered) for pattern in _PLACEHOLDER_ONLY_GUIDANCE_PATTERNS)


_PLAN_REFERENCE_LOCATOR_PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:tbd|todo|unknown|unclear|none|n/?a|placeholder)\s*$"),
    re.compile(r"\btbd\b"),
    re.compile(r"\btodo\b"),
    re.compile(r"\bunknown\b"),
    re.compile(r"\bunclear\b"),
    re.compile(r"\bplaceholder\b"),
    re.compile(r"\bto be determined\b"),
)
_PLAN_CITATION_LOCATOR_YEAR_PATTERN = re.compile(r"\b(?:18|19|20)\d{2}\b")
_PLAN_REFERENCE_LOCATOR_CONCRETE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:doi\s*[:/]|https?://(?:doi\.org/|arxiv\.org/abs/)|arxiv\s*:)\S+"),
    re.compile(r"^\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}(?:v\d+)?$"),
    # Old-style arXiv ID: archive/YYMMNNN. Bare archives (math, physics, cs,
    # nlin, stat) are whitelisted explicitly; all other archives require a
    # separator (hep-th, cond-mat, math.DG, etc.). econ and eess are included
    # defensively (created post-2007, never had old-style IDs).
    re.compile(r"^(?:(?:math|physics|cs|nlin|stat|econ|eess)|[a-z][a-z0-9]*(?:[-.][a-z][a-z0-9]*)+)/\d{2}(?:0[1-9]|1[0-2])\d{3}(?:v\d+)?$"),
    re.compile(r"^10\.\d{4,9}/\S+$"),
)
_PLAN_GROUNDING_TEXT_DIRECT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:need(?:s)? grounding|grounding needed)\s*$"),
    re.compile(r"\bunknown\b"),
    re.compile(r"\bundecided\b"),
    re.compile(r"\bunclear\b"),
    re.compile(r"\bmissing\b"),
    re.compile(r"\bnot (?:yet )?established\b"),
    re.compile(r"\bnot (?:yet )?selected\b"),
    re.compile(r"\bstill to identify\b"),
    re.compile(r"\btbd\b"),
    re.compile(r"\bto be determined\b"),
    re.compile(r"\bmust establish\b"),
    re.compile(r"\bestablish later\b"),
    re.compile(r"\bno\b.+\byet\b"),
)
_PLAN_GROUNDING_TEXT_QUESTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:which|what)\b"),
    re.compile(r"\?$"),
)
_PLAN_GROUNDING_TEXT_SELECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bserve as\b"),
    re.compile(r"\btreat as\b"),
    re.compile(r"\buse as\b"),
    re.compile(r"\bchoose\b"),
    re.compile(r"\bselect\b"),
    re.compile(r"\bpick\b"),
    re.compile(r"\bdecisive\b"),
)
_PLAN_GROUNDING_TEXT_BLOCKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bunknown\b"),
    re.compile(r"\bundecided\b"),
    re.compile(r"\bunclear\b"),
    re.compile(r"\bmissing\b"),
    re.compile(r"\bnot (?:yet )?established\b"),
    re.compile(r"\bnot (?:yet )?selected\b"),
    re.compile(r"\bstill to identify\b"),
    re.compile(r"\btbd\b"),
    re.compile(r"\bto be determined\b"),
    re.compile(r"\bmust establish\b"),
    re.compile(r"\bestablish later\b"),
    re.compile(r"\bno\b.+\byet\b"),
)
_USER_ASSERTED_ANCHOR_PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:tbd|todo|unknown|unclear|none|n/?a|placeholder)\s*$"),
    re.compile(r"\btbd\b"),
    re.compile(r"\btodo\b"),
    re.compile(r"\bplaceholder\b"),
    re.compile(r"\bto be determined\b"),
)
_PLACEHOLDER_ONLY_GUIDANCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:tbd|todo|unknown|unclear|none|n/?a|placeholder)\s*$"),
)
_PROJECT_ARTIFACT_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"[\\/]+"),
    re.compile(r"^(?:\.{1,2}|~)(?:[\\/]|$)"),
    re.compile(r"\.[A-Za-z0-9]{1,8}$"),
)


def _looks_like_project_artifact_path(value: str) -> bool:
    """Return whether *value* looks like a concrete project-local artifact path."""

    candidate = value.strip()
    if not candidate:
        return False
    return bool(
        re.search(r"[\\/]+", candidate)
        or re.search(r"^(?:\.{1,2}|~)(?:[\\/]|$)", candidate)
    )


def _is_project_artifact_path(value: str, *, project_root: Path | None = None) -> bool:
    """Return whether *value* names a concrete project-local artifact path."""

    candidate = value.strip()
    if not candidate or "://" in candidate:
        return False
    if not any(pattern.search(candidate) for pattern in _PROJECT_ARTIFACT_PATH_PATTERNS):
        return False

    if project_root is None:
        if any(pattern.search(candidate.casefold()) for pattern in _PLAN_REFERENCE_LOCATOR_CONCRETE_PATTERNS):
            return False
        return _looks_like_project_artifact_path(candidate)

    root = project_root.expanduser().resolve(strict=False)
    path = Path(candidate).expanduser()
    resolved = (path if path.is_absolute() else root / path).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    return resolved.is_file()


def _is_unresolved_project_artifact_path(value: str) -> bool:
    """Return whether *value* names an artifact path that needs a project root."""

    candidate_path = Path(value.strip()).expanduser()
    return candidate_path.is_absolute() or ".." in candidate_path.parts


def _is_citation_like_locator(value: str) -> bool:
    """Return whether *value* looks like an explicit citation rather than a vague anchor."""

    lowered = value.casefold().strip()
    if not lowered:
        return False
    if not _PLAN_CITATION_LOCATOR_YEAR_PATTERN.search(lowered):
        return False
    if re.search(r"\bet al\.?\b", lowered):
        return True

    parts = [part.strip() for part in re.split(r"[;,]", lowered) if part.strip()]
    if len(parts) >= 3:
        return any(" " in part for part in parts[:-1])
    if len(parts) == 2:
        return bool(
            re.search(r"\(\s*(?:18|19|20)\d{2}\s*\)", parts[1])
            and (" " in parts[0] or " " in parts[1])
        )
    return False


def _is_concrete_external_http_locator(value: str, *, reference_kind: str) -> bool:
    """Return whether *value* is a concrete external URL for the requested kind."""

    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    path = parsed.path.strip()
    if path in {"", "/"}:
        return False

    if reference_kind in {"dataset", "prior_artifact", "spec"}:
        return True
    if reference_kind not in {"paper", "other"}:
        return False

    netloc = parsed.netloc.casefold()
    if netloc.endswith("doi.org"):
        return True
    if netloc.endswith("arxiv.org") and path.startswith("/abs/") and len(path) > len("/abs/"):
        return True
    lowered = value.casefold()
    if not re.search(r"\b10\.\d{4,9}/\S+", lowered):
        return False
    return any(
        marker in lowered
        for marker in (
            "/abstract/",
            "/article/",
            "/articles/",
            "/doi/",
            "/full/",
            "/fulltext/",
            "/pdf/",
            "journals.",
            "journal.",
            "proceedings",
            "conference",
        )
    )


def _is_concrete_text_grounding(value: str, *, project_root: Path | None = None) -> bool:
    """Return whether *value* names locator-grade grounding rather than filler."""

    lowered = value.casefold().strip()
    if not lowered:
        return False
    if any(pattern.search(lowered) for pattern in _PLAN_REFERENCE_LOCATOR_CONCRETE_PATTERNS):
        return True
    if _is_citation_like_locator(value):
        return True
    if _is_project_artifact_path(value, project_root=project_root):
        if project_root is None and _is_unresolved_project_artifact_path(value):
            return False
        return True
    if any(
        _is_concrete_external_http_locator(value, reference_kind=reference_kind)
        for reference_kind in ("paper", "dataset", "prior_artifact", "spec")
    ):
        return True
    if any(pattern.search(lowered) for pattern in _PLAN_GROUNDING_TEXT_DIRECT_PATTERNS):
        return False
    if (
        all(pattern.search(lowered) for pattern in _PLAN_GROUNDING_TEXT_QUESTION_PATTERNS)
        and any(pattern.search(lowered) for pattern in _PLAN_GROUNDING_TEXT_SELECTION_PATTERNS)
    ):
        return False
    if any(pattern.search(lowered) for pattern in _PLAN_REFERENCE_LOCATOR_PLACEHOLDER_PATTERNS):
        return False
    return False


def _is_concrete_reference_locator(
    value: str,
    *,
    reference_kind: str = "paper",
    project_root: Path | None = None,
) -> bool:
    """Return whether *value* names a concrete reference locator rather than a placeholder."""

    lowered = value.casefold().strip()
    if not lowered:
        return False
    if any(pattern.search(lowered) for pattern in _PLAN_REFERENCE_LOCATOR_CONCRETE_PATTERNS):
        return True
    if reference_kind in {"paper", "other"} and _is_citation_like_locator(value):
        return True
    if _is_concrete_external_http_locator(value, reference_kind=reference_kind):
        return True
    if _is_project_artifact_path(value, project_root=project_root):
        return reference_kind in {"dataset", "prior_artifact", "spec"}
    if any(pattern.search(lowered) for pattern in _PLAN_REFERENCE_LOCATOR_PLACEHOLDER_PATTERNS):
        return False
    if reference_kind == "user_anchor":
        return _is_concrete_text_grounding(value, project_root=project_root)
    return False


def _is_context_intake_locator_grounding(
    value: str,
    *,
    project_root: Path | None = None,
    require_existing_project_artifacts: bool = False,
) -> bool:
    """Return whether a context-intake anchor/baseline is concrete enough to count."""

    if require_existing_project_artifacts and _is_project_artifact_path(value, project_root=None):
        if project_root is None:
            return False
        return _is_project_artifact_path(value, project_root=project_root)
    return _is_concrete_text_grounding(value, project_root=project_root)


def _has_concrete_grounding_entries(
    values: list[str],
    *,
    field_name: str,
    project_root: Path | None = None,
    require_existing_project_artifacts: bool = False,
) -> bool:
    """Return whether any grounding entry is concrete for the requested field."""

    if field_name == "must_include_prior_outputs":
        if require_existing_project_artifacts:
            if project_root is None:
                return False
            return any(
                _is_project_artifact_path(value, project_root=project_root)
                for value in values
            )
        return any(_is_project_artifact_path(value, project_root=project_root) for value in values)
    if field_name in {"user_asserted_anchors", "known_good_baselines"}:
        return any(
            _is_context_intake_locator_grounding(
                value,
                project_root=project_root,
                require_existing_project_artifacts=require_existing_project_artifacts,
            )
            for value in values
        )
    raise ValueError(f"Unsupported grounding field {field_name!r}")


def _has_concrete_must_surface_reference(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
    require_existing_project_artifacts: bool = False,
) -> bool:
    """Return whether the contract includes a concrete must_surface reference."""

    for reference in contract.references:
        if not reference.must_surface:
            continue
        if not _is_concrete_reference_locator(
            reference.locator,
            reference_kind=reference.kind,
            project_root=project_root,
        ):
            continue
        if not require_existing_project_artifacts:
            return True
        if not _is_project_artifact_path(reference.locator, project_root=None):
            return True
        if project_root is not None and _is_project_artifact_path(reference.locator, project_root=project_root):
            return True
    return False


PROJECT_CONTRACT_MAPPING_LIST_FIELDS: dict[str, tuple[str, ...]] = {
    "scope": ("in_scope", "out_of_scope", "unresolved_questions"),
    "context_intake": (
        "must_read_refs",
        "must_include_prior_outputs",
        "user_asserted_anchors",
        "known_good_baselines",
        "context_gaps",
        "crucial_inputs",
    ),
    "approach_policy": (
        "formulations",
        "allowed_estimator_families",
        "forbidden_estimator_families",
        "allowed_fit_families",
        "forbidden_fit_families",
        "stop_and_rethink_conditions",
    ),
    "uncertainty_markers": (
        "weakest_anchors",
        "unvalidated_assumptions",
        "competing_explanations",
        "disconfirming_observations",
    ),
}
PROJECT_CONTRACT_TOP_LEVEL_LIST_FIELDS: tuple[str, ...] = (
    "observables",
    "claims",
    "deliverables",
    "acceptance_tests",
    "references",
    "forbidden_proxies",
    "links",
)
PROJECT_CONTRACT_COLLECTION_LIST_FIELDS: dict[str, tuple[str, ...]] = {
    "claims": ("observables", "deliverables", "acceptance_tests", "references", "quantifiers", "proof_deliverables"),
    "deliverables": ("must_contain",),
    "acceptance_tests": ("evidence_required",),
    "references": ("aliases", "applies_to", "carry_forward_to", "required_actions"),
    "links": ("verified_by",),
}


def _collect_project_contract_list_member_errors(data: object) -> list[str]:
    """Reject blank or duplicate list members before model normalization."""

    if not isinstance(data, dict):
        return []

    errors: list[str] = []

    def _blank_string(value: object) -> bool:
        return isinstance(value, str) and not value.strip()

    def _check_string_list(value: object, *, path: str) -> None:
        if not isinstance(value, list):
            return
        seen: set[str] = set()
        for index, item in enumerate(value):
            if not isinstance(item, str):
                continue
            stripped = item.strip()
            if not stripped:
                errors.append(f"{path}.{index} must not be blank")
                continue
            if stripped in seen:
                errors.append(f"{path}.{index} is a duplicate")
                continue
            seen.add(stripped)

    def _check_mapping_lists(mapping: object, *, path_prefix: str, field_names: tuple[str, ...]) -> None:
        if not isinstance(mapping, dict):
            return
        for field_name in field_names:
            if field_name in mapping:
                _check_string_list(mapping[field_name], path=f"{path_prefix}.{field_name}")

    def _check_collection_item_lists(collection_name: str, field_names: tuple[str, ...]) -> None:
        raw_collection = data.get(collection_name)
        if not isinstance(raw_collection, list):
            return
        for index, item in enumerate(raw_collection):
            if isinstance(item, dict):
                _check_mapping_lists(item, path_prefix=f"{collection_name}.{index}", field_names=field_names)
                if collection_name == "claims":
                    parameters = item.get("parameters")
                    if isinstance(parameters, list):
                        for param_index, parameter in enumerate(parameters):
                            if isinstance(parameter, dict) and isinstance(parameter.get("aliases"), str):
                                if not _blank_string(parameter["aliases"]):
                                    errors.append(
                                        f"{collection_name}.{index}.parameters.{param_index}.aliases must be a list, not str"
                                    )
                            if isinstance(parameter, dict) and "aliases" in parameter:
                                _check_string_list(
                                    parameter["aliases"],
                                    path=f"{collection_name}.{index}.parameters.{param_index}.aliases",
                                )
                    hypotheses = item.get("hypotheses")
                    if isinstance(hypotheses, list):
                        for hypothesis_index, hypothesis in enumerate(hypotheses):
                            if isinstance(hypothesis, dict) and isinstance(hypothesis.get("symbols"), str):
                                if not _blank_string(hypothesis["symbols"]):
                                    errors.append(
                                        f"{collection_name}.{index}.hypotheses.{hypothesis_index}.symbols must be a list, not str"
                                    )
                            if isinstance(hypothesis, dict) and "symbols" in hypothesis:
                                _check_string_list(
                                    hypothesis["symbols"],
                                    path=f"{collection_name}.{index}.hypotheses.{hypothesis_index}.symbols",
                                )

    for section_name, field_names in PROJECT_CONTRACT_MAPPING_LIST_FIELDS.items():
        _check_mapping_lists(data.get(section_name), path_prefix=section_name, field_names=field_names)
    for collection_name, field_names in PROJECT_CONTRACT_COLLECTION_LIST_FIELDS.items():
        _check_collection_item_lists(collection_name, field_names)

    return errors


def _collect_strict_nested_proof_list_scalar_drift_errors(data: object) -> list[str]:
    """Reject blank nested proof-list scalar drift without mutating authored input."""

    if not isinstance(data, dict):
        return []

    errors: list[str] = []
    claims = data.get("claims")
    if not isinstance(claims, list):
        return errors

    for claim_index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        parameters = claim.get("parameters")
        if isinstance(parameters, list):
            for param_index, parameter in enumerate(parameters):
                if isinstance(parameter, dict) and isinstance(parameter.get("aliases"), str) and not parameter["aliases"].strip():
                    errors.append(f"claims.{claim_index}.parameters.{param_index}.aliases must be a list, not str")
        hypotheses = claim.get("hypotheses")
        if isinstance(hypotheses, list):
            for hypothesis_index, hypothesis in enumerate(hypotheses):
                if isinstance(hypothesis, dict) and isinstance(hypothesis.get("symbols"), str) and not hypothesis["symbols"].strip():
                    errors.append(f"claims.{claim_index}.hypotheses.{hypothesis_index}.symbols must be a list, not str")

    return errors


class _StrictContractResultsInput(dict[str, object]):
    """Marker mapping for strict contract-results validation contexts."""


_STRICT_CONTRACT_RESULTS_STRING_LIST_FIELDS: dict[str, tuple[str, ...]] = {
    "claims": ("linked_ids",),
    "deliverables": ("linked_ids",),
    "acceptance_tests": ("linked_ids",),
    "references": ("completed_actions", "missing_actions"),
}
_STRICT_PROOF_AUDIT_STRING_LIST_FIELDS: tuple[str, ...] = (
    "covered_hypothesis_ids",
    "missing_hypothesis_ids",
    "covered_parameter_symbols",
    "missing_parameter_symbols",
    "uncovered_quantifiers",
    "uncovered_conclusion_clause_ids",
)
_RECOVERABLE_ARTIFACT_CONTRACT_RESULTS_STRING_LIST_PATHS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(claims|deliverables|acceptance_tests)\.[^.]+\.linked_ids$"),
    re.compile(r"^references\.[^.]+\.(completed_actions|missing_actions)$"),
    re.compile(
        r"^(claims|deliverables|acceptance_tests|references|forbidden_proxies)\.[^.]+\.evidence\.\d+\."
        r"(covered_hypothesis_ids|missing_hypothesis_ids|covered_parameter_symbols|missing_parameter_symbols|"
        r"uncovered_conclusion_clause_ids)$"
    ),
    re.compile(
        r"^(claims|deliverables|acceptance_tests)\.[^.]+\.proof_audit\."
        r"(covered_hypothesis_ids|missing_hypothesis_ids|covered_parameter_symbols|missing_parameter_symbols|"
        r"uncovered_quantifiers|uncovered_conclusion_clause_ids)$"
    ),
    re.compile(
        r"^uncertainty_markers\."
        r"(weakest_anchors|unvalidated_assumptions|competing_explanations|disconfirming_observations)$"
    ),
)


def _normalize_literal_choice(value: object, choices: tuple[str, ...]) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return stripped
        for choice in choices:
            if stripped.casefold() == choice.casefold():
                return choice
        return stripped
    return value


def _normalize_exact_literal_choice(value: object, choices: tuple[str, ...]) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return stripped
        for choice in choices:
            if stripped.casefold() == choice.casefold():
                if stripped != choice:
                    raise ValueError(f"must use exact literal {choice!r}")
                return choice
        return stripped
    return value


def _normalize_literal_choice_list(value: object, choices: tuple[str, ...]) -> object:
    normalized = _normalize_string_list(value)
    if not isinstance(normalized, list):
        return normalized

    canonicalized: list[object] = []
    seen: set[str] = set()
    for item in normalized:
        if not isinstance(item, str):
            canonicalized.append(item)
            continue
        choice = _normalize_literal_choice(item, choices)
        if not isinstance(choice, str):
            canonicalized.append(choice)
            continue
        if choice in seen:
            continue
        seen.add(choice)
        canonicalized.append(choice)
    return canonicalized


def normalize_contract_results_input(value: object) -> object:
    """Normalize contract-results input before strict ``ContractResults`` validation."""
    if not isinstance(value, dict):
        return value

    return _StrictContractResultsInput(dict(value))


def _collect_strict_contract_results_errors(value: _StrictContractResultsInput) -> list[str]:
    """Return strict contract-results shape errors before Pydantic defaults apply."""

    errors: list[str] = []

    def _require_exact_literal(raw_value: object, *, path: str, choices: tuple[str, ...]) -> None:
        if not isinstance(raw_value, str):
            return
        stripped = raw_value.strip()
        if not stripped:
            return
        for choice in choices:
            if stripped.casefold() == choice.casefold() and stripped != choice:
                errors.append(f"{path} must use exact literal {choice!r}")
                return

    def _check_string_list_entries(
        raw_value: object,
        *,
        path: str,
        literal_choices: tuple[str, ...] | None = None,
    ) -> None:
        if not isinstance(raw_value, list):
            return

        seen: set[str] = set()
        for index, item in enumerate(raw_value):
            if not isinstance(item, str):
                continue
            stripped = item.strip()
            if not stripped:
                errors.append(f"{path}.{index} must not be blank")
                continue

            normalized = stripped
            if literal_choices is not None:
                matched_choice = next(
                    (choice for choice in literal_choices if stripped.casefold() == choice.casefold()),
                    None,
                )
                if matched_choice is not None:
                    if item != matched_choice:
                        errors.append(f"{path}.{index} must use exact literal {matched_choice!r}")
                    normalized = matched_choice

            if normalized in seen:
                errors.append(f"{path}.{index} is a duplicate")
                continue
            seen.add(normalized)

    def _check_evidence_items(entries: object, *, path_prefix: str) -> None:
        if not isinstance(entries, list):
            return
        for index, item in enumerate(entries):
            if not isinstance(item, dict):
                continue
            for field_name in (
                "covered_hypothesis_ids",
                "missing_hypothesis_ids",
                "covered_parameter_symbols",
                "missing_parameter_symbols",
                "uncovered_conclusion_clause_ids",
            ):
                if isinstance(item.get(field_name), str):
                    errors.append(f"{path_prefix}.{index}.{field_name} must be a list, not str")
                _check_string_list_entries(
                    item.get(field_name),
                    path=f"{path_prefix}.{index}.{field_name}",
                )
            _require_exact_literal(
                item.get("confidence"),
                path=f"{path_prefix}.{index}.confidence",
                choices=("high", "medium", "low", "unreliable"),
            )
            _require_exact_literal(
                item.get("quantifier_status"),
                path=f"{path_prefix}.{index}.quantifier_status",
                choices=PROOF_AUDIT_QUANTIFIER_STATUS_VALUES,
            )
            _require_exact_literal(
                item.get("counterexample_status"),
                path=f"{path_prefix}.{index}.counterexample_status",
                choices=PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES,
            )

    for section_name in ("claims", "deliverables", "acceptance_tests", "references", "forbidden_proxies"):
        section = value.get(section_name)
        if not isinstance(section, dict):
            continue
        for entry_id, entry in section.items():
            if isinstance(entry, dict) and "status" not in entry:
                errors.append(
                    f"{section_name}.{entry_id}.status must be explicit in contract-backed contract_results"
                )
            if isinstance(entry, dict):
                _check_evidence_items(entry.get("evidence"), path_prefix=f"{section_name}.{entry_id}.evidence")
                if section_name in {"claims", "deliverables", "acceptance_tests"}:
                    _require_exact_literal(
                        entry.get("status"),
                        path=f"{section_name}.{entry_id}.status",
                        choices=("passed", "partial", "failed", "blocked", "not_attempted"),
                    )
                elif section_name == "references":
                    _require_exact_literal(
                        entry.get("status"),
                        path=f"{section_name}.{entry_id}.status",
                        choices=("completed", "missing", "not_applicable"),
                    )
                elif section_name == "forbidden_proxies":
                    _require_exact_literal(
                        entry.get("status"),
                        path=f"{section_name}.{entry_id}.status",
                        choices=("rejected", "violated", "unresolved", "not_applicable"),
                    )
                status = entry.get("status")
                if section_name in {"claims", "deliverables", "acceptance_tests"} and status in {"failed", "blocked"}:
                    if not _has_explanatory_contract_entry_content(
                        summary=entry.get("summary"),
                        notes=entry.get("notes"),
                        evidence=entry.get("evidence"),
                    ):
                        errors.append(
                            f"{section_name}.{entry_id}.{_contract_result_gap_message(str(status))}"
                        )
                elif section_name == "references" and status == "missing":
                    if not _has_explanatory_contract_entry_content(
                        summary=entry.get("summary"),
                        evidence=entry.get("evidence"),
                    ):
                        errors.append(
                            f"{section_name}.{entry_id}.{_contract_reference_gap_message(str(status))}"
                        )
                elif section_name == "forbidden_proxies" and status in {"violated", "unresolved"}:
                    if not _has_explanatory_contract_entry_content(
                        notes=entry.get("notes"),
                        evidence=entry.get("evidence"),
                    ):
                        errors.append(
                            f"{section_name}.{entry_id}.{_contract_forbidden_proxy_gap_message(str(status))}"
                        )

    for section_name, field_names in _STRICT_CONTRACT_RESULTS_STRING_LIST_FIELDS.items():
        section = value.get(section_name)
        if not isinstance(section, dict):
            continue
        for entry_id, entry in section.items():
            if not isinstance(entry, dict):
                continue
            for field_name in field_names:
                if isinstance(entry.get(field_name), str):
                    errors.append(f"{section_name}.{entry_id}.{field_name} must be a list, not str")
                _check_string_list_entries(
                    entry.get(field_name),
                    path=f"{section_name}.{entry_id}.{field_name}",
                    literal_choices=CONTRACT_REFERENCE_ACTION_VALUES if section_name == "references" else None,
                )
            proof_audit = entry.get("proof_audit")
            if not isinstance(proof_audit, dict):
                continue
            if "completeness" not in proof_audit:
                errors.append(
                    f"{section_name}.{entry_id}.proof_audit.completeness must be explicit in contract-backed contract_results"
                )
            _require_exact_literal(
                proof_audit.get("completeness"),
                path=f"{section_name}.{entry_id}.proof_audit.completeness",
                choices=("complete", "incomplete"),
            )
            for field_name in _STRICT_PROOF_AUDIT_STRING_LIST_FIELDS:
                if isinstance(proof_audit.get(field_name), str):
                    errors.append(f"{section_name}.{entry_id}.proof_audit.{field_name} must be a list, not str")
                _check_string_list_entries(
                    proof_audit.get(field_name),
                    path=f"{section_name}.{entry_id}.proof_audit.{field_name}",
                )

    markers = value.get("uncertainty_markers")
    if isinstance(markers, dict):
        for field_name in (
            "weakest_anchors",
            "unvalidated_assumptions",
            "competing_explanations",
            "disconfirming_observations",
        ):
            if isinstance(markers.get(field_name), str):
                errors.append(f"uncertainty_markers.{field_name} must be a list, not str")
            _check_string_list_entries(
                markers.get(field_name),
                path=f"uncertainty_markers.{field_name}",
            )
        if not markers.get("weakest_anchors"):
            errors.append(
                "uncertainty_markers.weakest_anchors must be non-empty in contract-backed contract_results"
            )
        if not markers.get("disconfirming_observations"):
            errors.append(
                "uncertainty_markers.disconfirming_observations must be non-empty in contract-backed contract_results"
            )

    return errors


def _collect_artifact_contract_results_errors(value: object) -> list[str]:
    """Return contract-results artifact blockers while tolerating harmless drift."""

    if not isinstance(value, dict):
        return ["contract_results must be an object"]

    errors = _collect_strict_contract_results_errors(value)
    if "uncertainty_markers" not in value:
        errors.append("uncertainty_markers must be explicit in contract-backed contract_results")

    def _is_recoverable(error: str) -> bool:
        if " must use exact literal " in error:
            return True
        suffix = " must be a list, not str"
        if not error.endswith(suffix):
            return False
        path = error.removesuffix(suffix)
        return any(pattern.fullmatch(path) for pattern in _RECOVERABLE_ARTIFACT_CONTRACT_RESULTS_STRING_LIST_PATHS)

    return [error for error in errors if not _is_recoverable(error)]


class ConventionLock(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    metric_signature: str | None = None
    fourier_convention: str | None = None
    natural_units: str | None = None
    gauge_choice: str | None = None
    regularization_scheme: str | None = None
    renormalization_scheme: str | None = None
    coordinate_system: str | None = None
    spin_basis: str | None = None
    state_normalization: str | None = None
    coupling_convention: str | None = None
    index_positioning: str | None = None
    time_ordering: str | None = None
    commutation_convention: str | None = None
    levi_civita_sign: str | None = None
    generator_normalization: str | None = None
    covariant_derivative_sign: str | None = None
    gamma_matrix_convention: str | None = None
    creation_annihilation_order: str | None = None
    custom_conventions: dict[str, str] = Field(default_factory=dict)


class VerificationEvidence(BaseModel):
    """Structured provenance for a verification event attached to a result."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    verified_at: str | None = None
    verifier: str | None = None
    method: str = "manual"
    confidence: Literal["high", "medium", "low", "unreliable"] = "medium"
    evidence_path: str | None = None
    trace_id: str | None = None
    commit_sha: str | None = None
    notes: str | None = None
    claim_id: str | None = None
    deliverable_id: str | None = None
    acceptance_test_id: str | None = None
    reference_id: str | None = None
    forbidden_proxy_id: str | None = None
    proof_claim_id: str | None = None
    covered_hypothesis_ids: list[str] = Field(default_factory=list)
    missing_hypothesis_ids: list[str] = Field(default_factory=list)
    covered_parameter_symbols: list[str] = Field(default_factory=list)
    missing_parameter_symbols: list[str] = Field(default_factory=list)
    uncovered_conclusion_clause_ids: list[str] = Field(default_factory=list)
    quantifier_status: Literal[*PROOF_AUDIT_QUANTIFIER_STATUS_VALUES] | None = None
    counterexample_status: Literal[*PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES] | None = None
    proof_artifact_path: str | None = None
    proof_artifact_sha256: str | None = None
    claim_statement_sha256: str | None = None

    @field_validator(
        "claim_id",
        "deliverable_id",
        "acceptance_test_id",
        "reference_id",
        "forbidden_proxy_id",
        "proof_claim_id",
        mode="before",
    )
    @classmethod
    def _normalize_optional_contract_id(cls, value: object) -> object:
        return _normalize_optional_str(value)

    @field_validator(
        "covered_hypothesis_ids",
        "missing_hypothesis_ids",
        "covered_parameter_symbols",
        "missing_parameter_symbols",
        "uncovered_conclusion_clause_ids",
        mode="before",
    )
    @classmethod
    def _normalize_optional_string_lists(cls, value: object) -> object:
        return _normalize_string_list(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, value: object) -> object:
        return _normalize_literal_choice(value, ("high", "medium", "low", "unreliable"))

    @field_validator("quantifier_status", mode="before")
    @classmethod
    def _normalize_quantifier_status(cls, value: object) -> object:
        return _normalize_literal_choice(
            _normalize_optional_str(value),
            PROOF_AUDIT_QUANTIFIER_STATUS_VALUES,
        )

    @field_validator("counterexample_status", mode="before")
    @classmethod
    def _normalize_counterexample_status(cls, value: object) -> object:
        return _normalize_literal_choice(
            _normalize_optional_str(value),
            PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES,
        )

    @field_validator("proof_artifact_path", "proof_artifact_sha256", "claim_statement_sha256", mode="before")
    @classmethod
    def _normalize_optional_proof_fields(cls, value: object) -> object:
        return _normalize_optional_str(value)


class ContractProofParameter(BaseModel):
    """A quantified or free parameter that a proof-bearing claim depends on."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    symbol: str
    domain_or_type: str | None = None
    aliases: list[str] = Field(default_factory=list)
    required_in_proof: bool = True
    notes: str | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalize_symbol(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("domain_or_type", mode="before")
    @classmethod
    def _normalize_domain_or_type(cls, value: object) -> object:
        return _normalize_optional_str(value)

    @field_validator("aliases", mode="before")
    @classmethod
    def _normalize_aliases(cls, value: object) -> object:
        return _normalize_string_list(value)

    @field_validator("notes", mode="before")
    @classmethod
    def _normalize_notes(cls, value: object) -> object:
        return _normalize_optional_str(value)

    @field_validator("required_in_proof", mode="before")
    @classmethod
    def _normalize_required_in_proof(cls, value: object) -> object:
        return _normalize_strict_bool(value)


class ContractProofHypothesis(BaseModel):
    """A named hypothesis or regime restriction for a proof-bearing claim."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    text: str
    symbols: list[str] = Field(default_factory=list)
    category: Literal[*PROOF_HYPOTHESIS_CATEGORY_VALUES] = "assumption"
    required_in_proof: bool = True

    @field_validator("id", "text", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("symbols", mode="before")
    @classmethod
    def _normalize_symbols(cls, value: object) -> object:
        return _normalize_string_list(value)

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, value: object) -> object:
        return _normalize_literal_choice(
            _normalize_required_str(value),
            PROOF_HYPOTHESIS_CATEGORY_VALUES,
        )

    @field_validator("required_in_proof", mode="before")
    @classmethod
    def _normalize_required_in_proof(cls, value: object) -> object:
        return _normalize_strict_bool(value)


class ContractProofConclusionClause(BaseModel):
    """One conclusion clause that the proof must establish."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    text: str

    @field_validator("id", "text", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)


class ContractProofAudit(BaseModel):
    """Machine-readable proof-obligation audit for theorem-bearing claims."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    completeness: Literal["complete", "incomplete"] = "incomplete"
    reviewed_at: str | None = None
    reviewer: str | None = None
    summary: str | None = None
    proof_artifact_path: str | None = None
    proof_artifact_sha256: str | None = None
    audit_artifact_path: str | None = None
    audit_artifact_sha256: str | None = None
    claim_statement_sha256: str | None = None
    covered_hypothesis_ids: list[str] = Field(default_factory=list)
    missing_hypothesis_ids: list[str] = Field(default_factory=list)
    covered_parameter_symbols: list[str] = Field(default_factory=list)
    missing_parameter_symbols: list[str] = Field(default_factory=list)
    uncovered_quantifiers: list[str] = Field(default_factory=list)
    uncovered_conclusion_clause_ids: list[str] = Field(default_factory=list)
    quantifier_status: Literal[*PROOF_AUDIT_QUANTIFIER_STATUS_VALUES] = "unclear"
    scope_status: Literal[*PROOF_AUDIT_SCOPE_STATUS_VALUES] = "unclear"
    counterexample_status: Literal[*PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES] = "not_attempted"
    stale: bool = False

    @field_validator(
        "reviewed_at",
        "reviewer",
        "summary",
        "proof_artifact_path",
        "audit_artifact_path",
        mode="before",
    )
    @classmethod
    def _normalize_optional_fields(cls, value: object) -> object:
        return _normalize_optional_str(value)

    @field_validator(
        "proof_artifact_sha256",
        "audit_artifact_sha256",
        "claim_statement_sha256",
        mode="before",
    )
    @classmethod
    def _normalize_sha256_fields(cls, value: object) -> object:
        return _normalize_optional_sha256(value)

    @field_validator(
        "covered_hypothesis_ids",
        "missing_hypothesis_ids",
        "covered_parameter_symbols",
        "missing_parameter_symbols",
        "uncovered_quantifiers",
        "uncovered_conclusion_clause_ids",
        mode="before",
    )
    @classmethod
    def _normalize_list_fields(cls, value: object) -> object:
        return _normalize_strict_string_list(value)

    @field_validator("completeness", mode="before")
    @classmethod
    def _normalize_completeness(cls, value: object) -> object:
        return _normalize_literal_choice(_normalize_required_str(value), ("complete", "incomplete"))

    @field_validator("quantifier_status", mode="before")
    @classmethod
    def _normalize_quantifier_status(cls, value: object) -> object:
        return _normalize_literal_choice(
            _normalize_required_str(value),
            PROOF_AUDIT_QUANTIFIER_STATUS_VALUES,
        )

    @field_validator("scope_status", mode="before")
    @classmethod
    def _normalize_scope_status(cls, value: object) -> object:
        return _normalize_literal_choice(
            _normalize_required_str(value),
            PROOF_AUDIT_SCOPE_STATUS_VALUES,
        )

    @field_validator("counterexample_status", mode="before")
    @classmethod
    def _normalize_counterexample_status(cls, value: object) -> object:
        return _normalize_literal_choice(
            _normalize_required_str(value),
            PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES,
        )

    @field_validator("stale", mode="before")
    @classmethod
    def _normalize_stale(cls, value: object) -> object:
        return _normalize_strict_bool(value)

    @field_validator("reviewer")
    @classmethod
    def _validate_reviewer(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != PROOF_AUDIT_REVIEWER:
            raise ValueError(f"reviewer must be {PROOF_AUDIT_REVIEWER}")
        return value

    @model_validator(mode="after")
    def _validate_complete_audit(self) -> ContractProofAudit:
        if self.completeness != "complete":
            return self

        if not self.reviewed_at:
            raise ValueError("completeness=complete requires reviewed_at")
        if self.reviewer != PROOF_AUDIT_REVIEWER:
            raise ValueError(f"completeness=complete requires reviewer={PROOF_AUDIT_REVIEWER}")
        if not self.proof_artifact_path:
            raise ValueError("completeness=complete requires proof_artifact_path")
        if not self.proof_artifact_sha256:
            raise ValueError("completeness=complete requires proof_artifact_sha256")
        if not self.audit_artifact_path:
            raise ValueError("completeness=complete requires audit_artifact_path")
        if not self.audit_artifact_sha256:
            raise ValueError("completeness=complete requires audit_artifact_sha256")
        if not self.claim_statement_sha256:
            raise ValueError("completeness=complete requires claim_statement_sha256")
        if self.stale:
            raise ValueError("completeness=complete requires stale=false")
        if self.missing_hypothesis_ids:
            raise ValueError("completeness=complete requires missing_hypothesis_ids to be empty")
        if self.missing_parameter_symbols:
            raise ValueError("completeness=complete requires missing_parameter_symbols to be empty")
        if self.uncovered_quantifiers:
            raise ValueError("completeness=complete requires uncovered_quantifiers to be empty")
        if self.uncovered_conclusion_clause_ids:
            raise ValueError("completeness=complete requires uncovered_conclusion_clause_ids to be empty")
        if self.quantifier_status == "mismatched":
            raise ValueError("completeness=complete is incompatible with quantifier_status=mismatched")
        if self.scope_status != "matched":
            raise ValueError("completeness=complete requires scope_status=matched")
        if self.counterexample_status != "none_found":
            raise ValueError("completeness=complete requires counterexample_status=none_found")
        return self


ContractEvidenceStatus = Literal["passed", "partial", "failed", "blocked", "not_attempted"]
ContractReferenceAction = Literal["read", "use", "compare", "cite", "avoid"]
PROOF_ACCEPTANCE_TEST_KINDS: tuple[str, ...] = (
    "proof_hypothesis_coverage",
    "proof_parameter_coverage",
    "proof_quantifier_domain",
    "claim_to_proof_alignment",
    "lemma_dependency_closure",
    "counterexample_search",
)
PROOF_AUDIT_REVIEWER = "gpd-check-proof"


class ContractEvidenceEntry(BaseModel):
    """Structured evidence item tied back to contract IDs."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    summary: str | None = None
    evidence: list[VerificationEvidence] = Field(default_factory=list)
    notes: str | None = None


class ContractResultEntry(ContractEvidenceEntry):
    """Execution or verification outcome for a contract subject."""

    status: ContractEvidenceStatus = "not_attempted"
    linked_ids: list[str] = Field(default_factory=list)
    path: str | None = None
    proof_audit: ContractProofAudit | None = None

    @field_validator("linked_ids", mode="before")
    @classmethod
    def _normalize_linked_ids(cls, value: object) -> object:
        return _normalize_strict_string_list(value)

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> object:
        return _normalize_literal_choice(value, ("passed", "partial", "failed", "blocked", "not_attempted"))

    @model_validator(mode="after")
    def _validate_gap_explanation(self) -> ContractResultEntry:
        if self.status in {"failed", "blocked"} and not _has_explanatory_contract_entry_content(
            summary=self.summary,
            notes=self.notes,
            evidence=self.evidence,
        ):
            raise ValueError(_contract_result_gap_message(self.status))
        return self


ContractReferenceActionStatus = Literal["completed", "missing", "not_applicable"]


class ContractReferenceUsage(BaseModel):
    """Status for required actions on a contract reference anchor."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    status: ContractReferenceActionStatus = "missing"
    completed_actions: list[ContractReferenceAction] = Field(default_factory=list)
    missing_actions: list[ContractReferenceAction] = Field(default_factory=list)
    summary: str | None = None
    evidence: list[VerificationEvidence] = Field(default_factory=list)

    @field_validator("completed_actions", "missing_actions", mode="before")
    @classmethod
    def _normalize_action_lists(cls, value: object) -> object:
        return _normalize_strict_literal_choice_list(value, CONTRACT_REFERENCE_ACTION_VALUES)

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> object:
        return _normalize_literal_choice(value, ("completed", "missing", "not_applicable"))

    @model_validator(mode="after")
    def _validate_action_status(self) -> ContractReferenceUsage:
        completed = set(self.completed_actions)
        missing = set(self.missing_actions)
        overlap = sorted(completed.intersection(missing))

        if overlap:
            raise ValueError(
                "completed_actions and missing_actions must not overlap: " + ", ".join(overlap)
            )
        if self.status == "completed":
            if not self.completed_actions:
                raise ValueError("status=completed requires completed_actions")
            if self.missing_actions:
                raise ValueError("status=completed requires missing_actions to be empty")
        elif self.status == "missing":
            if not self.missing_actions:
                raise ValueError("status=missing requires missing_actions")
        elif self.completed_actions or self.missing_actions:
            raise ValueError("status=not_applicable requires completed_actions and missing_actions to be empty")
        if self.status == "missing" and not _has_explanatory_contract_entry_content(
            summary=self.summary,
            evidence=self.evidence,
        ):
            raise ValueError(_contract_reference_gap_message(self.status))

        return self


ContractForbiddenProxyStatus = Literal["rejected", "violated", "unresolved", "not_applicable"]


class ContractForbiddenProxyResult(BaseModel):
    """Status for a forbidden-proxy guardrail."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    status: ContractForbiddenProxyStatus = "unresolved"
    notes: str | None = None
    evidence: list[VerificationEvidence] = Field(default_factory=list)

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> object:
        return _normalize_literal_choice(value, ("rejected", "violated", "unresolved", "not_applicable"))

    @model_validator(mode="after")
    def _validate_gap_explanation(self) -> ContractForbiddenProxyResult:
        if self.status in {"violated", "unresolved"} and not _has_explanatory_contract_entry_content(
            notes=self.notes,
            evidence=self.evidence,
        ):
            raise ValueError(_contract_forbidden_proxy_gap_message(self.status))
        return self


class ContractResults(BaseModel):
    """Execution-facing outcome ledger keyed to canonical contract IDs."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    claims: dict[str, ContractResultEntry] = Field(default_factory=dict)
    deliverables: dict[str, ContractResultEntry] = Field(default_factory=dict)
    acceptance_tests: dict[str, ContractResultEntry] = Field(default_factory=dict)
    references: dict[str, ContractReferenceUsage] = Field(default_factory=dict)
    forbidden_proxies: dict[str, ContractForbiddenProxyResult] = Field(default_factory=dict)
    uncertainty_markers: ContractUncertaintyMarkers = Field(default_factory=lambda: ContractUncertaintyMarkers())

    @model_validator(mode="before")
    @classmethod
    def _validate_strict_contract_results(cls, value: object) -> object:
        if isinstance(value, _StrictContractResultsInput):
            errors = _collect_strict_contract_results_errors(value)
            if "uncertainty_markers" not in value:
                errors.append("uncertainty_markers must be explicit in contract-backed contract_results")
            if errors:
                raise ValueError("; ".join(errors))
        return value

    @field_validator(
        "claims",
        "deliverables",
        "acceptance_tests",
        "references",
        "forbidden_proxies",
        mode="before",
    )
    @classmethod
    def _normalize_mapping_sections(cls, value: object) -> object:
        return value


def parse_contract_results_data_strict(value: object) -> ContractResults:
    """Return strict contract-results data for runtime and artifact boundaries."""

    if not isinstance(value, dict):
        raise ValueError("contract_results must be an object")
    return ContractResults.model_validate(normalize_contract_results_input(value))


def parse_contract_results_data_artifact(value: object) -> ContractResults:
    """Parse contract-results data for SUMMARY / VERIFICATION frontmatter with narrow salvage."""

    errors = _collect_artifact_contract_results_errors(value)
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(value, dict):
        raise ValueError("contract_results must be an object")
    return ContractResults.model_validate(value)


def _format_pydantic_validation_errors(exc: PydanticValidationError) -> list[str]:
    messages: list[str] = []
    seen: set[str] = set()
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "value"
        message = str(error.get("msg", "validation failed")).strip() or "validation failed"
        input_value = error.get("input")

        if message == "Field required":
            formatted = f"{location} is required"
        elif "valid dictionary" in message.lower():
            actual_type = type(input_value).__name__
            formatted = f"{location} must be an object, not {actual_type}"
        elif message == "Value error, must not be blank":
            formatted = f"{location} must not be blank"
        elif message in {"Value error, must be a non-empty string", "Value error, value must not be blank"}:
            formatted = f"{location} must be a non-empty string"
        else:
            formatted = f"{location}: {message}"
        if formatted in seen:
            continue
        seen.add(formatted)
        messages.append(formatted)
    return messages or [str(exc)]


def parse_comparison_verdicts_data_strict(value: object) -> list[ComparisonVerdict]:
    """Return strict comparison-verdict data for runtime and artifact boundaries."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("expected a list")

    verdicts: list[ComparisonVerdict] = []
    for index, entry in enumerate(value):
        try:
            verdicts.append(ComparisonVerdict.model_validate(entry))
        except PydanticValidationError as exc:
            details = "; ".join(f"[{index}] {message}" for message in _format_pydantic_validation_errors(exc))
            raise ValueError(details) from exc
    return verdicts


class SuggestedContractCheck(BaseModel):
    """Structured gap to add when the contract is missing decisive verification."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    check: str
    reason: str
    suggested_subject_kind: Literal["claim", "deliverable", "acceptance_test", "reference"] | None = None
    suggested_subject_id: str | None = None
    evidence_path: str | None = None

    @field_validator("check", "reason", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("suggested_subject_kind", mode="before")
    @classmethod
    def _normalize_optional_kind(cls, value: object) -> object:
        return _normalize_literal_choice(
            _normalize_optional_str(value),
            ("claim", "deliverable", "acceptance_test", "reference"),
        )

    @field_validator("suggested_subject_id", "evidence_path", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, value: object) -> object:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def _validate_subject_binding_pair(self) -> SuggestedContractCheck:
        has_kind = self.suggested_subject_kind is not None
        has_id = self.suggested_subject_id is not None
        if has_kind != has_id:
            raise ValueError("suggested_subject_kind and suggested_subject_id must appear together")
        return self


class ComparisonVerdict(BaseModel):
    """Machine-readable verdict for an internal or external comparison."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    subject_id: str
    subject_kind: Literal["claim", "deliverable", "acceptance_test", "reference"]
    subject_role: Literal["decisive", "supporting", "supplemental", "other"]
    reference_id: str | None = None
    comparison_kind: Literal["benchmark", "prior_work", "experiment", "cross_method", "baseline", "other"] = "other"
    metric: str | None = None
    threshold: str | None = None
    verdict: Literal["pass", "tension", "fail", "inconclusive"] = "inconclusive"
    recommended_action: str | None = None
    notes: str | None = None

    @field_validator("subject_id", mode="before")
    @classmethod
    def _normalize_subject_id(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("subject_kind", "subject_role", "comparison_kind", "verdict", mode="before")
    @classmethod
    def _normalize_required_literals(cls, value: object, info: ValidationInfo) -> object:
        normalized = _normalize_required_str(value)
        field_choices = {
            "subject_kind": ("claim", "deliverable", "acceptance_test", "reference"),
            "subject_role": ("decisive", "supporting", "supplemental", "other"),
            "comparison_kind": ("benchmark", "prior_work", "experiment", "cross_method", "baseline", "other"),
            "verdict": ("pass", "tension", "fail", "inconclusive"),
        }
        return _normalize_exact_literal_choice(normalized, field_choices[info.field_name])

    @field_validator("reference_id", "metric", "threshold", "recommended_action", "notes", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, value: object) -> object:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def _validate_decisive_reference_binding(self) -> ComparisonVerdict:
        if (
            self.subject_role == "decisive"
            and self.comparison_kind in {"benchmark", "prior_work", "experiment", "baseline"}
            and self.subject_kind != "reference"
            and self.reference_id is None
        ):
            raise ValueError(
                "must include reference_id or use subject_kind: reference "
                f"for decisive {self.comparison_kind} comparisons"
            )
        return self

    def anchored_reference_ids(self, known_reference_ids: set[str] | None = None) -> set[str]:
        """Return contract reference anchors named by this verdict.

        ``reference_id`` is the explicit anchor field. ``subject_kind: reference``
        also anchors the verdict directly to the referenced contract node.
        """

        anchors: set[str] = set()
        if self.reference_id is not None:
            anchors.add(self.reference_id)
        if self.subject_kind == "reference":
            anchors.add(self.subject_id)
        if known_reference_ids is None:
            return anchors
        return anchors.intersection(known_reference_ids)


class ContractScope(BaseModel):
    """High-level problem boundary for a project or phase."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    question: str
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)

    @field_validator("question", mode="before")
    @classmethod
    def _normalize_question(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("in_scope", "out_of_scope", "unresolved_questions", mode="before")
    @classmethod
    def _normalize_scope_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractContextIntake(BaseModel):
    """Inputs the user says must stay visible during execution."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    must_read_refs: list[str] = Field(default_factory=list)
    must_include_prior_outputs: list[str] = Field(default_factory=list)
    user_asserted_anchors: list[str] = Field(default_factory=list)
    known_good_baselines: list[str] = Field(default_factory=list)
    context_gaps: list[str] = Field(default_factory=list)
    crucial_inputs: list[str] = Field(default_factory=list)

    @field_validator(
        "must_read_refs",
        "must_include_prior_outputs",
        "user_asserted_anchors",
        "known_good_baselines",
        "context_gaps",
        "crucial_inputs",
        mode="before",
    )
    @classmethod
    def _normalize_intake_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractApproachPolicy(BaseModel):
    """Representation, estimator, and rethink guardrails that must survive downstream."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    formulations: list[str] = Field(default_factory=list)
    allowed_estimator_families: list[str] = Field(default_factory=list)
    forbidden_estimator_families: list[str] = Field(default_factory=list)
    allowed_fit_families: list[str] = Field(default_factory=list)
    forbidden_fit_families: list[str] = Field(default_factory=list)
    stop_and_rethink_conditions: list[str] = Field(default_factory=list)

    @field_validator(
        "formulations",
        "allowed_estimator_families",
        "forbidden_estimator_families",
        "allowed_fit_families",
        "forbidden_fit_families",
        "stop_and_rethink_conditions",
        mode="before",
    )
    @classmethod
    def _normalize_policy_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractObservable(BaseModel):
    """A target quantity or behavior the work needs to establish."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    name: str
    kind: Literal["scalar", "curve", "map", "classification", "proof_obligation", "other"] = "other"
    definition: str
    regime: str | None = None
    units: str | None = None

    @field_validator("id", "name", "definition", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("regime", "units", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, value: object) -> object:
        return _normalize_non_empty_optional_str(value)

    @field_validator("kind", mode="before")
    @classmethod
    def _normalize_kind(cls, value: object) -> object:
        return _normalize_literal_choice(_normalize_required_str(value), CONTRACT_OBSERVABLE_KIND_VALUES)


class ContractClaim(BaseModel):
    """A statement the phase must establish."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    statement: str
    claim_kind: Literal["theorem", "lemma", "corollary", "proposition", "result", "claim", "other"] = "other"
    observables: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    acceptance_tests: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    parameters: list[ContractProofParameter] = Field(default_factory=list)
    hypotheses: list[ContractProofHypothesis] = Field(default_factory=list)
    quantifiers: list[str] = Field(default_factory=list)
    conclusion_clauses: list[ContractProofConclusionClause] = Field(default_factory=list)
    proof_deliverables: list[str] = Field(default_factory=list)

    @field_validator("id", "statement", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator(
        "observables",
        "deliverables",
        "acceptance_tests",
        "references",
        "quantifiers",
        "proof_deliverables",
        mode="before",
    )
    @classmethod
    def _normalize_id_lists(cls, value: object) -> object:
        return _normalize_string_list(value)

    @field_validator("claim_kind", mode="before")
    @classmethod
    def _normalize_claim_kind(cls, value: object) -> object:
        return _normalize_literal_choice(_normalize_required_str(value), CONTRACT_CLAIM_KIND_VALUES)


class ContractDeliverable(BaseModel):
    """An artifact the phase must produce."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    kind: Literal["figure", "table", "dataset", "data", "derivation", "code", "note", "report", "other"] = "other"
    path: str | None = None
    description: str
    must_contain: list[str] = Field(default_factory=list)

    @field_validator("id", "description", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("kind", mode="before")
    @classmethod
    def _normalize_kind(cls, value: object) -> object:
        return _normalize_literal_choice(_normalize_required_str(value), CONTRACT_DELIVERABLE_KIND_VALUES)

    @field_validator("path", mode="before")
    @classmethod
    def _normalize_optional_path(cls, value: object) -> object:
        return _normalize_optional_str(value)

    @field_validator("must_contain", mode="before")
    @classmethod
    def _normalize_must_contain(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractAcceptanceTest(BaseModel):
    """A concrete check proving whether a claim or deliverable succeeded."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    subject: str
    kind: Literal[
        "existence",
        "schema",
        "benchmark",
        "consistency",
        "cross_method",
        "limiting_case",
        "symmetry",
        "dimensional_analysis",
        "convergence",
        "oracle",
        "proxy",
        "reproducibility",
        "proof_hypothesis_coverage",
        "proof_parameter_coverage",
        "proof_quantifier_domain",
        "claim_to_proof_alignment",
        "lemma_dependency_closure",
        "counterexample_search",
        "human_review",
        "other",
    ] = "other"
    procedure: str
    pass_condition: str
    evidence_required: list[str] = Field(default_factory=list)
    automation: Literal["automated", "hybrid", "human"] = "hybrid"

    @field_validator("id", "subject", "procedure", "pass_condition", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("kind", mode="before")
    @classmethod
    def _normalize_kind(cls, value: object) -> object:
        return _normalize_literal_choice(_normalize_required_str(value), CONTRACT_ACCEPTANCE_TEST_KIND_VALUES)

    @field_validator("automation", mode="before")
    @classmethod
    def _normalize_automation(cls, value: object) -> object:
        return _normalize_literal_choice(_normalize_required_str(value), CONTRACT_ACCEPTANCE_AUTOMATION_VALUES)

    @field_validator("evidence_required", mode="before")
    @classmethod
    def _normalize_evidence_required(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractReference(BaseModel):
    """A literature, dataset, or artifact anchor the workflow must respect."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    kind: Literal["paper", "dataset", "prior_artifact", "spec", "user_anchor", "other"] = "other"
    locator: str
    aliases: list[str] = Field(default_factory=list)
    role: Literal["definition", "benchmark", "method", "must_consider", "background", "other"] = "other"
    why_it_matters: str
    applies_to: list[str] = Field(default_factory=list)
    carry_forward_to: list[str] = Field(default_factory=list)
    must_surface: bool = False
    required_actions: list[ContractReferenceAction] = Field(default_factory=list)

    @field_validator("id", "locator", "why_it_matters", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("kind", "role", mode="before")
    @classmethod
    def _normalize_literal_fields(cls, value: object, info: ValidationInfo) -> object:
        normalized = _normalize_required_str(value)
        if info.field_name == "kind":
            return _normalize_literal_choice(normalized, CONTRACT_REFERENCE_KIND_VALUES)
        return _normalize_literal_choice(normalized, CONTRACT_REFERENCE_ROLE_VALUES)

    @field_validator("aliases", "applies_to", "carry_forward_to", mode="before")
    @classmethod
    def _normalize_reference_lists(cls, value: object) -> object:
        return _normalize_string_list(value)

    @field_validator("required_actions", mode="before")
    @classmethod
    def _normalize_required_actions(cls, value: object) -> object:
        return _normalize_literal_choice_list(value, CONTRACT_REFERENCE_ACTION_VALUES)

    @field_validator("must_surface", mode="before")
    @classmethod
    def _normalize_must_surface(cls, value: object) -> object:
        return _normalize_strict_bool(value)


class ContractForbiddenProxy(BaseModel):
    """A proxy or shortcut that should not be accepted as success."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    subject: str
    proxy: str
    reason: str

    @field_validator("id", "subject", "proxy", "reason", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)


class ContractLink(BaseModel):
    """A machine-readable dependency from one contract node to another."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    source: str
    target: str
    relation: Literal[
        "supports",
        "computes",
        "visualizes",
        "benchmarks",
        "depends_on",
        "evaluated_by",
        "proves",
        "uses_hypothesis",
        "depends_on_lemma",
        "other",
    ] = "other"
    verified_by: list[str] = Field(default_factory=list)

    @field_validator("id", "source", "target", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("relation", mode="before")
    @classmethod
    def _normalize_relation(cls, value: object) -> object:
        return _normalize_literal_choice(_normalize_required_str(value), CONTRACT_LINK_RELATION_VALUES)

    @field_validator("verified_by", mode="before")
    @classmethod
    def _normalize_verified_by(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractUncertaintyMarkers(BaseModel):
    """Structured skepticism markers carried alongside the contract."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    weakest_anchors: list[str] = Field(default_factory=list)
    unvalidated_assumptions: list[str] = Field(default_factory=list)
    competing_explanations: list[str] = Field(default_factory=list)
    disconfirming_observations: list[str] = Field(default_factory=list)

    @field_validator(
        "weakest_anchors",
        "unvalidated_assumptions",
        "competing_explanations",
        "disconfirming_observations",
        mode="before",
    )
    @classmethod
    def _normalize_uncertainty_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class ResearchContract(BaseModel):
    """Canonical contract shared across planning, execution, and verification."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    schema_version: Literal[1] = 1
    scope: ContractScope
    context_intake: ContractContextIntake = Field(default_factory=ContractContextIntake)
    approach_policy: ContractApproachPolicy = Field(default_factory=ContractApproachPolicy)
    observables: list[ContractObservable] = Field(default_factory=list)
    claims: list[ContractClaim] = Field(default_factory=list)
    deliverables: list[ContractDeliverable] = Field(default_factory=list)
    acceptance_tests: list[ContractAcceptanceTest] = Field(default_factory=list)
    references: list[ContractReference] = Field(default_factory=list)
    forbidden_proxies: list[ContractForbiddenProxy] = Field(default_factory=list)
    links: list[ContractLink] = Field(default_factory=list)
    uncertainty_markers: ContractUncertaintyMarkers = Field(default_factory=lambda: ContractUncertaintyMarkers())


_CONTRACT_ID_GROUPS: tuple[tuple[str, str], ...] = (
    ("observable", "observables"),
    ("claim", "claims"),
    ("deliverable", "deliverables"),
    ("acceptance test", "acceptance_tests"),
    ("reference", "references"),
    ("forbidden proxy", "forbidden_proxies"),
    ("link", "links"),
)
_AMBIGUOUS_TARGET_ID_KINDS: tuple[str, ...] = ("claim", "deliverable", "acceptance test", "reference")


def _contract_ids_by_kind(contract: ResearchContract) -> dict[str, set[str]]:
    return {
        kind: {item.id for item in getattr(contract, field_name)}
        for kind, field_name in _CONTRACT_ID_GROUPS
    }


def claim_requires_proof_audit(claim: ContractClaim, observable_kind_by_id: dict[str, str]) -> bool:
    return (
        claim.claim_kind in THEOREM_CLAIM_KIND_VALUES
        or statement_looks_theorem_like(claim.statement)
        or bool(claim.parameters)
        or bool(claim.hypotheses)
        or bool(claim.quantifiers)
        or bool(claim.conclusion_clauses)
        or bool(claim.proof_deliverables)
        or any(observable_kind_by_id.get(observable_id) == "proof_obligation" for observable_id in claim.observables)
    )


def collect_proof_audit_alignment_errors(
    claim: ContractClaim,
    audit: ContractProofAudit,
    *,
    deliverable_path_by_id: dict[str, str | None] | None = None,
) -> list[str]:
    """Return proof-audit mismatches against the declared theorem/proof contract."""

    errors: list[str] = []

    hypothesis_ids = {hypothesis.id for hypothesis in claim.hypotheses}
    parameter_symbols = {parameter.symbol for parameter in claim.parameters}
    conclusion_clause_ids = {clause.id for clause in claim.conclusion_clauses}
    required_hypothesis_ids = {hypothesis.id for hypothesis in claim.hypotheses if hypothesis.required_in_proof}
    required_parameter_symbols = {parameter.symbol for parameter in claim.parameters if parameter.required_in_proof}

    unknown_hypothesis_ids = set(audit.covered_hypothesis_ids).union(audit.missing_hypothesis_ids) - hypothesis_ids
    if unknown_hypothesis_ids:
        errors.append(
            f"claim {claim.id} proof_audit references unknown hypothesis ids: {', '.join(sorted(unknown_hypothesis_ids))}"
        )

    unknown_parameter_symbols = (
        set(audit.covered_parameter_symbols).union(audit.missing_parameter_symbols) - parameter_symbols
    )
    if unknown_parameter_symbols:
        errors.append(
            "claim "
            f"{claim.id} proof_audit references unknown parameter symbols: {', '.join(sorted(unknown_parameter_symbols))}"
        )

    unknown_conclusion_clause_ids = set(audit.uncovered_conclusion_clause_ids) - conclusion_clause_ids
    if unknown_conclusion_clause_ids:
        errors.append(
            "claim "
            f"{claim.id} proof_audit references unknown conclusion clause ids: {', '.join(sorted(unknown_conclusion_clause_ids))}"
        )

    missing_required_hypothesis_ids = required_hypothesis_ids - set(audit.covered_hypothesis_ids)
    if missing_required_hypothesis_ids:
        errors.append(
            "claim "
            f"{claim.id} proof_audit does not cover required hypothesis ids: {', '.join(sorted(missing_required_hypothesis_ids))}"
        )

    missing_required_parameter_symbols = required_parameter_symbols - set(audit.covered_parameter_symbols)
    if missing_required_parameter_symbols:
        errors.append(
            "claim "
            f"{claim.id} proof_audit does not cover required parameter symbols: {', '.join(sorted(missing_required_parameter_symbols))}"
        )

    if set(audit.missing_hypothesis_ids).intersection(required_hypothesis_ids):
        errors.append(f"claim {claim.id} proof_audit leaves required hypotheses marked missing")
    if set(audit.missing_parameter_symbols).intersection(required_parameter_symbols):
        errors.append(f"claim {claim.id} proof_audit leaves required parameter symbols marked missing")
    if claim.quantifiers and audit.quantifier_status == "unclear":
        errors.append(f"claim {claim.id} proof_audit quantifier_status must be explicit for quantified claims")

    if audit.claim_statement_sha256:
        statement_sha256 = hashlib.sha256(claim.statement.encode("utf-8")).hexdigest()
        if audit.claim_statement_sha256 != statement_sha256:
            errors.append(f"claim {claim.id} proof_audit.claim_statement_sha256 does not match the current claim statement")

    if audit.reviewer and audit.reviewer != PROOF_AUDIT_REVIEWER:
        errors.append(f"claim {claim.id} proof_audit.reviewer must be {PROOF_AUDIT_REVIEWER}")

    if deliverable_path_by_id:
        allowed_paths = {
            path
            for deliverable_id in claim.proof_deliverables
            if (path := deliverable_path_by_id.get(deliverable_id))
        }
        if audit.proof_artifact_path and allowed_paths and audit.proof_artifact_path not in allowed_paths:
            errors.append(
                f"claim {claim.id} proof_audit.proof_artifact_path must match a declared proof_deliverables path"
            )

    if audit.audit_artifact_path and "proof-redteam" not in Path(audit.audit_artifact_path).name.lower():
        errors.append(
            f"claim {claim.id} proof_audit.audit_artifact_path must point to a proof-redteam artifact"
        )

    return errors


def collect_contract_integrity_errors(contract: ResearchContract) -> list[str]:
    """Return semantic integrity errors that require a cross-contract view."""

    ids_by_kind = _contract_ids_by_kind(contract)
    owners_by_id: dict[str, list[str]] = defaultdict(list)
    errors: list[str] = []

    for kind, field_name in _CONTRACT_ID_GROUPS:
        counts: dict[str, int] = defaultdict(int)
        for item in getattr(contract, field_name):
            counts[item.id] += 1
        for item_id, count in sorted(counts.items()):
            if count > 1:
                errors.append(f"duplicate {kind} id {item_id}")

    for kind in _AMBIGUOUS_TARGET_ID_KINDS:
        for item_id in ids_by_kind[kind]:
            owners_by_id[item_id].append(kind)

    for item_id, owner_kinds in sorted(owners_by_id.items()):
        unique_kinds = tuple(dict.fromkeys(owner_kinds))
        if len(unique_kinds) < 2:
            continue
        kinds_text = ", ".join(unique_kinds)
        errors.append(f"contract id {item_id} is reused across {kinds_text}; target resolution is ambiguous")

    declared_contract_ids = {
        item_id
        for ids in ids_by_kind.values()
        for item_id in ids
    }
    for reference in contract.references:
        for target in reference.carry_forward_to:
            if target in declared_contract_ids:
                errors.append(
                    f"reference {reference.id} carry_forward_to must name workflow scope, not contract id {target}"
                )

    return errors


def collect_proof_bearing_claim_integrity_errors(contract: ResearchContract) -> list[str]:
    """Return proof-bearing claim integrity errors shared by project and plan contracts."""

    observable_kind_by_id = {observable.id: observable.kind for observable in contract.observables}
    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    acceptance_test_kind_by_id = {test.id: test.kind for test in contract.acceptance_tests}

    issues: list[str] = []
    for claim in contract.claims:
        for proof_deliverable_id in claim.proof_deliverables:
            if proof_deliverable_id not in deliverable_ids:
                issues.append(f"claim {claim.id} references unknown proof deliverable {proof_deliverable_id}")

        if not claim_requires_proof_audit(claim, observable_kind_by_id):
            continue

        if claim.claim_kind == "other":
            issues.append(f"claim {claim.id} missing claim_kind for proof-bearing claim")
        if not claim.proof_deliverables:
            issues.append(f"claim {claim.id} missing proof_deliverables")
        if not claim.parameters:
            issues.append(f"claim {claim.id} missing parameters for proof-bearing claim")
        if not claim.hypotheses:
            issues.append(f"claim {claim.id} missing hypotheses for proof-bearing claim")
        if not claim.conclusion_clauses:
            issues.append(f"claim {claim.id} missing conclusion_clauses for proof-bearing claim")
        if not any(
            acceptance_test_kind_by_id.get(test_id) in PROOF_ACCEPTANCE_TEST_KINDS
            for test_id in claim.acceptance_tests
        ):
            issues.append(f"claim {claim.id} missing proof-specific acceptance_tests")

    return issues


def _collect_project_local_grounding_integrity_errors(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> list[str]:
    """Return integrity errors for project-local grounding that cannot be resolved safely."""

    errors: list[str] = []

    for value in contract.context_intake.must_include_prior_outputs:
        if not _looks_like_project_artifact_path(value):
            continue
        if project_root is None:
            errors.append(
                "context_intake.must_include_prior_outputs entry requires a resolved project_root "
                f"to verify artifact grounding: {value}"
            )
            continue
        if not _is_project_artifact_path(value, project_root=project_root):
            errors.append(
                f"context_intake.must_include_prior_outputs entry does not resolve to a project-local artifact: {value}"
            )

    for field_name, values in (
        ("user_asserted_anchors", contract.context_intake.user_asserted_anchors),
        ("known_good_baselines", contract.context_intake.known_good_baselines),
    ):
        for value in values:
            if not _is_project_artifact_path(value, project_root=None):
                continue
            if project_root is None:
                errors.append(
                    f"context_intake.{field_name} entry requires a resolved project_root "
                    f"to verify artifact grounding: {value}"
                )
                continue
            if not _is_project_artifact_path(value, project_root=project_root):
                errors.append(
                    f"context_intake.{field_name} entry does not resolve to a project-local artifact: {value}"
                )

    for reference in contract.references:
        if not reference.must_surface or not _looks_like_project_artifact_path(reference.locator):
            continue
        if project_root is None:
            errors.append(
                f"reference {reference.id} must_surface locator requires a resolved project_root "
                f"to verify artifact grounding: {reference.locator}"
            )
            continue
        if not _is_project_artifact_path(reference.locator, project_root=project_root):
            errors.append(
                f"reference {reference.id} must_surface locator does not resolve to a project-local artifact: {reference.locator}"
            )

    return errors


def _has_contract_grounding_context(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
    require_existing_project_artifacts: bool = False,
) -> bool:
    """Return whether the contract carries explicit grounding outside references."""

    return any(
        (
            _has_concrete_grounding_entries(
                contract.context_intake.must_include_prior_outputs,
                field_name="must_include_prior_outputs",
                project_root=project_root,
                require_existing_project_artifacts=require_existing_project_artifacts,
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.user_asserted_anchors,
                field_name="user_asserted_anchors",
                project_root=project_root,
                require_existing_project_artifacts=require_existing_project_artifacts,
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.known_good_baselines,
                field_name="known_good_baselines",
                project_root=project_root,
                require_existing_project_artifacts=require_existing_project_artifacts,
            ),
        )
    )


def contract_has_explicit_context_intake(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> bool:
    """Return whether ``context_intake`` carries any concrete, model-useful guidance."""

    has_reference_guidance = any(
        _is_concrete_reference_locator(
            reference.locator,
            reference_kind=reference.kind,
            project_root=project_root,
        )
        for reference in contract.references
        if reference.id in contract.context_intake.must_read_refs
    )
    has_prior_output_guidance = any(
        _looks_like_project_artifact_path(value)
        for value in contract.context_intake.must_include_prior_outputs
    )
    has_anchor_guidance = any(
        _is_context_intake_locator_grounding(
            value,
            project_root=project_root,
            require_existing_project_artifacts=True,
        )
        for value in contract.context_intake.user_asserted_anchors
    )
    has_baseline_guidance = any(
        _is_context_intake_locator_grounding(
            value,
            project_root=project_root,
            require_existing_project_artifacts=True,
        )
        for value in contract.context_intake.known_good_baselines
    )
    has_text_guidance = any(
        not is_placeholder_only_guidance_text(value)
        for value in (*contract.context_intake.context_gaps, *contract.context_intake.crucial_inputs)
    )

    return any(
        (
            has_reference_guidance,
            has_prior_output_guidance,
            has_anchor_guidance,
            has_baseline_guidance,
            has_text_guidance,
        )
    )


def _is_scoping_contract(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
    require_existing_project_artifacts: bool = False,
) -> bool:
    """Return whether the contract is still framing the work rather than proving it."""

    return (
        not contract.claims
        and not contract.acceptance_tests
        and (
            bool(contract.observables)
            or bool(contract.deliverables)
            or bool(contract.scope.unresolved_questions)
            or _has_contract_grounding_context(
                contract,
                project_root=project_root,
                require_existing_project_artifacts=require_existing_project_artifacts,
            )
        )
    )


def _is_exploratory_contract(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
    require_existing_project_artifacts: bool = False,
) -> bool:
    """Return whether the contract semantics describe setup/exploratory work."""

    exploratory_test_kinds = {
        "existence",
        "schema",
        "human_review",
        "consistency",
        "limiting_case",
        "symmetry",
        "dimensional_analysis",
        "convergence",
        "other",
    }
    exploratory_deliverable_kinds = {"code", "note", "report", "derivation", "figure", "table", "dataset", "data", "other"}

    return (
        not _is_scoping_contract(
            contract,
            project_root=project_root,
            require_existing_project_artifacts=require_existing_project_artifacts,
        )
        and (
            bool(contract.acceptance_tests)
            or _has_contract_grounding_context(
                contract,
                project_root=project_root,
                require_existing_project_artifacts=require_existing_project_artifacts,
            )
        )
        and all(test.kind in exploratory_test_kinds for test in contract.acceptance_tests)
        and all(deliverable.kind in exploratory_deliverable_kinds for deliverable in contract.deliverables)
    )


def collect_plan_contract_integrity_errors(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> list[str]:
    """Return the full semantic integrity error set for plan-style contracts."""

    issues = list(collect_contract_integrity_errors(contract))
    scoping_contract = _is_scoping_contract(
        contract,
        project_root=project_root,
        require_existing_project_artifacts=True,
    )
    exploratory_contract = _is_exploratory_contract(
        contract,
        project_root=project_root,
        require_existing_project_artifacts=True,
    )

    if not contract.claims and not scoping_contract:
        issues.append("missing claims")
    if not contract.deliverables and not scoping_contract:
        issues.append("missing deliverables")
    if not contract.acceptance_tests and not scoping_contract:
        issues.append("missing acceptance_tests")
    if not contract.references and not (
        _has_contract_grounding_context(
            contract,
            project_root=project_root,
            require_existing_project_artifacts=True,
        )
        or exploratory_contract
        or scoping_contract
    ):
        issues.append("missing references or explicit grounding context")
    if not contract.forbidden_proxies and not (exploratory_contract or scoping_contract):
        issues.append("missing forbidden_proxies")
    if not contract.uncertainty_markers.weakest_anchors:
        issues.append("missing uncertainty_markers.weakest_anchors")
    if not contract.uncertainty_markers.disconfirming_observations:
        issues.append("missing uncertainty_markers.disconfirming_observations")
    if scoping_contract and not (
        contract.observables
        or contract.deliverables
        or contract.scope.unresolved_questions
        or _has_contract_grounding_context(
            contract,
            project_root=project_root,
            require_existing_project_artifacts=True,
        )
    ):
        issues.append("scoping contracts must preserve at least one target, open question, or carry-forward input")

    observable_ids = {observable.id for observable in contract.observables}
    claim_ids = {claim.id for claim in contract.claims}
    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    acceptance_test_ids = {test.id for test in contract.acceptance_tests}
    reference_ids = {reference.id for reference in contract.references}
    known_ids = claim_ids | deliverable_ids | acceptance_test_ids | reference_ids

    if contract.references and not _has_concrete_must_surface_reference(
        contract,
        project_root=project_root,
        require_existing_project_artifacts=True,
    ) and not _has_contract_grounding_context(
        contract,
        project_root=project_root,
        require_existing_project_artifacts=True,
    ):
        issues.append("references must include at least one must_surface=true anchor")
    for must_read_ref in contract.context_intake.must_read_refs:
        if must_read_ref not in reference_ids:
            issues.append(f"context_intake.must_read_refs references unknown reference {must_read_ref}")

    for claim in contract.claims:
        if not claim.deliverables:
            issues.append(f"claim {claim.id} missing deliverables")
        if not claim.acceptance_tests:
            issues.append(f"claim {claim.id} missing acceptance_tests")
        for observable_id in claim.observables:
            if observable_id not in observable_ids:
                issues.append(f"claim {claim.id} references unknown observable {observable_id}")
        for deliverable_id in claim.deliverables:
            if deliverable_id not in deliverable_ids:
                issues.append(f"claim {claim.id} references unknown deliverable {deliverable_id}")
        for test_id in claim.acceptance_tests:
            if test_id not in acceptance_test_ids:
                issues.append(f"claim {claim.id} references unknown acceptance test {test_id}")
        for reference_id in claim.references:
            if reference_id not in reference_ids:
                issues.append(f"claim {claim.id} references unknown reference {reference_id}")

        if len({parameter.symbol for parameter in claim.parameters}) != len(claim.parameters):
            issues.append(f"claim {claim.id} has duplicate proof parameter symbols")
        if len({hypothesis.id for hypothesis in claim.hypotheses}) != len(claim.hypotheses):
            issues.append(f"claim {claim.id} has duplicate proof hypothesis ids")
        if len({clause.id for clause in claim.conclusion_clauses}) != len(claim.conclusion_clauses):
            issues.append(f"claim {claim.id} has duplicate conclusion clause ids")

    for test in contract.acceptance_tests:
        if test.subject not in claim_ids and test.subject not in deliverable_ids:
            issues.append(f"acceptance test {test.id} targets unknown subject {test.subject}")
        for evidence_id in test.evidence_required:
            if evidence_id not in known_ids:
                issues.append(f"acceptance test {test.id} references unknown evidence {evidence_id}")

    for reference in contract.references:
        if reference.must_surface and not reference.required_actions:
            issues.append(f"reference {reference.id} is must_surface but missing required_actions")
        if reference.must_surface and not reference.applies_to:
            issues.append(f"reference {reference.id} is must_surface but missing applies_to")
        for applies_to_id in reference.applies_to:
            if applies_to_id not in claim_ids and applies_to_id not in deliverable_ids:
                issues.append(f"reference {reference.id} applies_to unknown target {applies_to_id}")

    for forbidden_proxy in contract.forbidden_proxies:
        if forbidden_proxy.subject not in claim_ids and forbidden_proxy.subject not in deliverable_ids:
            issues.append(
                f"forbidden proxy {forbidden_proxy.id} targets unknown subject {forbidden_proxy.subject}"
            )

    for link in contract.links:
        if link.source not in known_ids:
            issues.append(f"link {link.id} references unknown source {link.source}")
        if link.target not in known_ids:
            issues.append(f"link {link.id} references unknown target {link.target}")
        for verification_id in link.verified_by:
            if verification_id not in acceptance_test_ids:
                issues.append(f"link {link.id} references unknown acceptance test {verification_id}")

    issues.extend(collect_proof_bearing_claim_integrity_errors(contract))

    return issues


class ProjectContractParseResult(BaseModel):
    """Structured result for project-contract payload parsing boundaries."""

    model_config = ConfigDict(frozen=True)

    contract: ResearchContract | None = None
    blocking_errors: list[str] = Field(default_factory=list)
    recoverable_errors: list[str] = Field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        return [*self.blocking_errors, *self.recoverable_errors]

    @property
    def warnings(self) -> list[str]:
        return list(self.recoverable_errors)


def _project_contract_parse_result(
    *,
    contract: ResearchContract | None = None,
    blocking_errors: list[str] | None = None,
    recoverable_errors: list[str] | None = None,
) -> ProjectContractParseResult:
    return ProjectContractParseResult(
        contract=contract,
        blocking_errors=dedupe_preserve_order(blocking_errors or []),
        recoverable_errors=dedupe_preserve_order(recoverable_errors or []),
    )


def _parse_project_contract_data(
    data: object,
    *,
    strict: bool,
) -> ProjectContractParseResult:
    if not isinstance(data, dict):
        return _project_contract_parse_result(blocking_errors=["project contract must be a JSON object"])

    from gpd.core.contract_validation import _collect_list_shape_drift_errors, salvage_project_contract

    contract, schema_findings = salvage_project_contract(data)
    list_shape_drift_errors = _collect_list_shape_drift_errors(data)
    if strict:
        from gpd.core.contract_validation import (
            _collect_literal_case_drift_errors,
            _project_contract_schema_version_missing_error,
            split_project_contract_schema_findings,
        )

        schema_warnings, schema_errors = split_project_contract_schema_findings(
            schema_findings,
            allow_case_drift_recovery=False,
        )
        blocking_errors = [
            *_collect_literal_case_drift_errors(data),
            *schema_errors,
            *schema_warnings,
            *list_shape_drift_errors,
            *_collect_project_contract_list_member_errors(data),
            *_collect_strict_nested_proof_list_scalar_drift_errors(data),
        ]
        schema_version_error = _project_contract_schema_version_missing_error(data)
        if schema_version_error is not None:
            blocking_errors = [schema_version_error, *blocking_errors]
        if contract is None:
            if not blocking_errors and schema_findings:
                blocking_errors = list(schema_findings)
            if not blocking_errors:
                blocking_errors = ["project contract could not be normalized"]
            return _project_contract_parse_result(blocking_errors=blocking_errors)
        integrity_errors = collect_contract_integrity_errors(contract)
        blocking_errors.extend(integrity_errors)
        if blocking_errors:
            return _project_contract_parse_result(blocking_errors=blocking_errors)
        return _project_contract_parse_result(contract=contract)

    from gpd.core.contract_validation import split_project_contract_schema_findings

    schema_warnings, schema_errors = split_project_contract_schema_findings(
        schema_findings,
        allow_case_drift_recovery=True,
    )
    recoverable_errors = [*schema_warnings, *list_shape_drift_errors, *_collect_project_contract_list_member_errors(data)]
    blocking_errors = [*schema_errors]
    if contract is None:
        if not blocking_errors and schema_findings:
            blocking_errors = list(schema_findings)
        if not blocking_errors:
            blocking_errors = ["project contract could not be normalized"]
        blocking_error_set = set(blocking_errors)
        recoverable_errors = [error for error in recoverable_errors if error not in blocking_error_set]
        return _project_contract_parse_result(
            blocking_errors=blocking_errors,
            recoverable_errors=recoverable_errors,
        )

    integrity_errors = collect_contract_integrity_errors(contract)
    if integrity_errors:
        blocking_errors.extend(integrity_errors)
    if blocking_errors:
        blocking_error_set = set(blocking_errors)
        recoverable_errors = [error for error in recoverable_errors if error not in blocking_error_set]
        return _project_contract_parse_result(
            contract=contract,
            blocking_errors=blocking_errors,
            recoverable_errors=recoverable_errors,
        )
    return _project_contract_parse_result(contract=contract, recoverable_errors=recoverable_errors)


def parse_project_contract_data_strict(data: object) -> ProjectContractParseResult:
    """Strictly parse an authored project-contract payload.

    This entrypoint is for model-facing or authoring boundaries where recoverable
    salvage is undesirable. Inputs that would require schema normalization
    (singleton list drift, extra keys, defaulted singleton sections, coercive
    scalars) are rejected explicitly instead of being silently canonicalized.
    Read/repair flows should continue to use ``contract_from_data_salvage()``
    or the lower-level salvage helpers.
    """

    return _parse_project_contract_data(data, strict=True)


def parse_project_contract_data_salvage(data: object) -> ProjectContractParseResult:
    """Salvage a project-contract payload while still surfacing recoverable findings."""

    return _parse_project_contract_data(data, strict=False)


def contract_from_data(
    data: object,
    *,
    allow_recoverable_warnings: bool = False,
    require_draft_validity: bool = False,
    project_root: Path | None = None,
) -> ResearchContract | None:
    """Return a validated :class:`ResearchContract` when *data* is a mapping.

    This entrypoint is strict by default and fails closed on recoverable
    schema drift. Callers that need repair-oriented salvage should use
    :func:`contract_from_data_salvage` explicitly. Callers that preserve
    contracts back into state can additionally require draft-level scoping
    validity.
    """

    if not isinstance(data, dict):
        return None
    if allow_recoverable_warnings:
        return contract_from_data_salvage(
            data,
            require_draft_validity=require_draft_validity,
            project_root=project_root,
        )

    strict_result = parse_project_contract_data_strict(data)
    if strict_result.contract is None or strict_result.errors:
        return None
    if require_draft_validity:
        from gpd.core.contract_validation import validate_project_contract

        draft_validation = validate_project_contract(strict_result.contract, mode="draft", project_root=project_root)
        if not draft_validation.valid:
            return None
    return strict_result.contract


def contract_from_data_salvage(
    data: object,
    *,
    require_draft_validity: bool = False,
    project_root: Path | None = None,
) -> ResearchContract | None:
    """Return a salvaged :class:`ResearchContract` for repair/migration callers."""

    if not isinstance(data, dict):
        return None
    from gpd.core.contract_validation import validate_project_contract

    salvage_result = parse_project_contract_data_salvage(data)
    if salvage_result.contract is None or salvage_result.blocking_errors:
        return None
    if require_draft_validity:
        draft_validation = validate_project_contract(salvage_result.contract, mode="draft", project_root=project_root)
        if not draft_validation.valid:
            return None
    return salvage_result.contract
