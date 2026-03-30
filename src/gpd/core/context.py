"""Context assembly for AI agent commands.

Each function gathers project state and produces a structured dict consumed by agent prompts.

Delegates to :mod:`gpd.core.config` for configuration loading and model-tier
resolution so that defaults and model profiles are defined in exactly one place.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from gpd.adapters.install_utils import AGENTS_DIR_NAME, FLAT_COMMANDS_DIR_NAME, GPD_INSTALL_DIR_NAME, HOOKS_DIR_NAME
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.contracts import ConventionLock, ResearchContract
from gpd.core import state as _state_module
from gpd.core.config import GPDProjectConfig
from gpd.core.config import load_config as _load_config_structured
from gpd.core.config import resolve_model as _resolve_model_canonical
from gpd.core.constants import (
    AGENT_ID_FILENAME,
    CONFIG_FILENAME,
    CONTEXT_SUFFIX,
    MILESTONES_DIR_NAME,
    PHASES_DIR_NAME,
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    PROJECT_FILENAME,
    REQUIREMENTS_FILENAME,
    RESEARCH_MAP_DIR_NAME,
    RESEARCH_SUFFIX,
    ROADMAP_FILENAME,
    STANDALONE_CONTEXT,
    STANDALONE_PLAN,
    STANDALONE_RESEARCH,
    STANDALONE_VALIDATION,
    STATE_MD_FILENAME,
    TODOS_DIR_NAME,
    VALIDATION_SUFFIX,
    VERIFICATION_SUFFIX,
    ProjectLayout,
)
from gpd.core.continuation import ContinuationResumeSource, resolve_continuation
from gpd.core.errors import ValidationError
from gpd.core.extras import approximation_list
from gpd.core.phases import _milestone_completion_snapshot
from gpd.core.project_reentry import resolve_project_reentry
from gpd.core.protocol_bundles import render_protocol_bundle_context, select_protocol_bundles
from gpd.core.reference_ingestion import ingest_manuscript_reference_status, ingest_reference_artifacts
from gpd.core.results import result_list
from gpd.core.resume_surface import (
    build_resume_candidate,
    build_resume_compat_surface,
    build_resume_segment_candidate,
    canonicalize_resume_public_payload,
    resume_origin_for_bounded_segment,
    resume_origin_for_handoff,
    resume_origin_for_interrupted_agent,
)
from gpd.core.state import (
    EM_DASH,
    _current_machine_identity,
    _finalize_project_contract_gate,
)
from gpd.core.state import peek_state_json as _peek_state_json
from gpd.core.utils import (
    generate_slug as _generate_slug_impl,
)
from gpd.core.utils import is_phase_complete as _is_phase_complete
from gpd.core.utils import matching_phase_artifact_count as _matching_phase_artifact_count
from gpd.core.utils import phase_normalize as _phase_normalize_impl
from gpd.core.utils import phase_sort_key as _phase_sort_key
from gpd.core.utils import safe_read_file as _safe_read_file
from gpd.core.utils import safe_read_file_truncated as _safe_read_file_truncated

logger = logging.getLogger(__name__)


# Research file extensions for project detection.
_RESEARCH_EXTENSIONS = frozenset({".tex", ".ipynb", ".py", ".jl", ".f90"})
_RUNTIME_CONFIG_DIRS = frozenset(descriptor.config_dir_name for descriptor in iter_runtime_descriptors())
_LITERATURE_DIR_NAME = "literature"
_REFERENCE_MAP_DOCS = ("REFERENCES.md", "VALIDATION.md")
_LITERATURE_INCLUDE_LIMIT = 2
_RESEARCH_MAP_INCLUDE_LIMIT = 4
_REFERENCE_ROLE_PRIORITY = {
    "benchmark": 0,
    "must_consider": 1,
    "definition": 2,
    "method": 3,
    "background": 4,
    "other": 5,
}

_RESUME_FILE_CLEAR_VALUES = frozenset({"[not set]", "none", "null"})
_RESUME_SURFACE_SCHEMA_VERSION = 1

# Directories to skip when scanning for research files.
_RUNTIME_IGNORED_SCAN_PATHS = frozenset(
    {
        (descriptor.config_dir_name,)
        for descriptor in iter_runtime_descriptors()
    }
    | {
        (".config", descriptor.global_config.xdg_subdir)
        for descriptor in iter_runtime_descriptors()
        if descriptor.global_config.xdg_subdir
    }
)
_IGNORE_DIRS = frozenset(
    {
        ".git",
        PLANNING_DIR_NAME,
        *_RUNTIME_CONFIG_DIRS,
        ".venv",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".vscode",
        ".idea",
        "node_modules",
        "__pycache__",
        GPD_INSTALL_DIR_NAME,
        AGENTS_DIR_NAME,
        FLAT_COMMANDS_DIR_NAME,
        HOOKS_DIR_NAME,
    }
)

__all__ = [
    "init_execute_phase",
    "init_map_research",
    "init_milestone_op",
    "init_new_milestone",
    "init_new_project",
    "init_phase_op",
    "init_plan_phase",
    "init_progress",
    "init_quick",
    "init_resume",
    "init_todos",
    "init_verify_work",
    "load_config",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _path_exists(cwd: Path, target: str) -> bool:
    """Check if a relative path exists under cwd."""
    return (cwd / target).exists()


def _state_exists(cwd: Path) -> bool:
    """Return whether the project has recoverable state from JSON or STATE.md."""
    state, _state_issues, _state_source = _peek_state_json(cwd)
    return isinstance(state, dict)


def _structured_state_objects(value: object) -> list[dict[str, object]]:
    """Return only structured mapping entries from a state section."""
    if not isinstance(value, list):
        return []
    structured: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, Mapping):
            structured.append(dict(item))
    return structured


def _build_structured_state_runtime_context(cwd: Path) -> dict[str, object]:
    """Build structured canonical state slices for init payloads."""
    state, state_issues, state_source = _peek_state_json(cwd)
    source = state_source.as_posix() if isinstance(state_source, Path) else str(state_source) if state_source else None
    if not isinstance(state, dict):
        return {
            "state_load_source": source,
            "state_integrity_issues": list(state_issues or []),
            "convention_lock": {},
            "intermediate_results": [],
            "intermediate_result_count": 0,
            "approximations": [],
            "approximation_count": 0,
            "propagated_uncertainties": [],
            "propagated_uncertainty_count": 0,
        }

    convention_lock = state.get("convention_lock")
    intermediate_results = _structured_state_objects(state.get("intermediate_results"))
    approximations = _structured_state_objects(state.get("approximations"))
    propagated_uncertainties = _structured_state_objects(state.get("propagated_uncertainties"))
    return {
        "state_load_source": source,
        "state_integrity_issues": list(state_issues or []),
        "convention_lock": dict(convention_lock) if isinstance(convention_lock, Mapping) else {},
        "intermediate_results": intermediate_results,
        "intermediate_result_count": len(intermediate_results),
        "approximations": approximations,
        "approximation_count": len(approximations),
        "propagated_uncertainties": propagated_uncertainties,
        "propagated_uncertainty_count": len(propagated_uncertainties),
    }


def _resolve_reentry_context(cwd: Path, *, data_root: Path | None = None) -> tuple[Path, dict[str, object]]:
    """Return the effective project root plus shared re-entry metadata."""

    resolution = resolve_project_reentry(cwd, data_root=data_root)
    selected_project_root = resolution.resolved_project_root
    effective_cwd = selected_project_root or cwd.expanduser().resolve(strict=False)
    metadata: dict[str, object] = {
        "workspace_root": resolution.workspace_root,
        "project_root": selected_project_root.as_posix() if selected_project_root is not None else None,
        "project_root_source": resolution.source or "workspace",
        "project_root_auto_selected": resolution.auto_selected,
        "project_reentry_mode": resolution.mode,
        "project_reentry_requires_selection": resolution.requires_user_selection,
        "project_reentry_selected_candidate": (
            resolution.selected_candidate.model_dump(mode="json")
            if resolution.selected_candidate is not None
            else None
        ),
        "project_reentry_candidates": [candidate.model_dump(mode="json") for candidate in resolution.candidates],
    }
    return effective_cwd, metadata


def _generate_slug(text: str | None) -> str | None:
    """Generate a URL-friendly slug from text.

    Thin wrapper around :func:`gpd.core.utils.generate_slug` that also
    accepts ``None`` (returning ``None`` immediately).
    """
    if not text:
        return None
    return _generate_slug_impl(text)


def _normalize_phase_name(phase: str) -> str:
    """Pad top-level phase number to 2 digits. E.g. '3' -> '03', '3.1' -> '03.1'.

    Delegates to :func:`gpd.core.utils.phase_normalize`.
    """
    return _phase_normalize_impl(phase)



def _find_phase_artifact(phase_dir: Path, suffix: str, standalone: str | None = None) -> str | None:
    """Find file content matching a suffix pattern in a phase directory (truncated)."""
    if not phase_dir.is_dir():
        return None
    for f in sorted(phase_dir.iterdir()):
        if f.is_file() and (f.name.endswith(suffix) or (standalone is not None and f.name == standalone)):
            return _safe_read_file_truncated(f)
    return None


def _compute_branch_name(
    config: dict,
    phase_number: str | None,
    phase_slug: str | None,
    milestone_version: str,
    milestone_slug: str | None,
) -> str | None:
    """Compute the git branch name based on branching strategy."""
    strategy = config.get("branching_strategy", "none")
    if strategy in ("per-phase", "phase") and phase_number:
        template = config.get("phase_branch_template", "gpd/phase-{phase}-{slug}")
        return template.replace("{phase}", phase_number).replace("{slug}", phase_slug or "phase")
    if strategy in ("per-milestone", "milestone"):
        template = config.get("milestone_branch_template", "gpd/{milestone}-{slug}")
        return template.replace("{milestone}", milestone_version).replace("{slug}", milestone_slug or "milestone")
    return None


def _extract_frontmatter_field(content: str, field: str) -> str | None:
    """Extract a bare field: value from frontmatter-like content."""
    match = re.search(rf"^{re.escape(field)}:[ \t]*(.+)$", content, re.MULTILINE)
    if not match:
        return None
    val = match.group(1).strip()
    # Strip surrounding quotes
    if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
        val = val[1:-1]
    return val or None


def _load_project_contract(cwd: Path) -> tuple[ResearchContract | None, dict[str, object]]:
    """Load the canonical project contract and return load diagnostics."""
    return _state_module._load_project_contract_for_runtime_context(cwd)


def _sorted_markdown_files(directory: Path) -> list[Path]:
    """Return markdown files in a directory, sorted by name."""
    try:
        return sorted(
            path for path in directory.iterdir() if path.is_file() and path.suffix == ".md"
        )
    except FileNotFoundError:
        return []


def _relative_posix(cwd: Path, path: Path) -> str:
    """Return a stable repo-relative POSIX path."""
    return path.relative_to(cwd).as_posix()


def _serialize_active_references(contract: ResearchContract | None) -> list[dict[str, object]]:
    """Return contract references ordered by planning relevance."""
    if contract is None:
        return []

    refs = sorted(
        contract.references,
        key=lambda ref: (
            0 if ref.must_surface else 1,
            _REFERENCE_ROLE_PRIORITY.get(ref.role, 99),
            ref.id,
        ),
    )
    serialized: list[dict[str, object]] = []
    for ref in refs:
        payload = ref.model_dump(mode="json")
        payload["source_kind"] = "project_contract"
        payload["source_artifacts"] = []
        serialized.append(payload)
    return serialized


def _append_unique_strings(target: list[str], values: list[object] | tuple[object, ...]) -> None:
    """Append string values without duplicating normalized entries."""
    for value in values:
        text = str(value).strip()
        if text and text not in target:
            target.append(text)


def _should_skip_research_scan_entry(cwd: Path, entry: Path) -> bool:
    """Return whether *entry* should be skipped during research-file discovery."""

    if entry.name in _IGNORE_DIRS:
        return True

    try:
        relative_parts = entry.relative_to(cwd).parts
    except ValueError:
        return False
    for ignored_parts in _RUNTIME_IGNORED_SCAN_PATHS:
        ignored_length = len(ignored_parts)
        if ignored_length == 0 or len(relative_parts) < ignored_length:
            continue
        for offset in range(len(relative_parts) - ignored_length + 1):
            if relative_parts[offset : offset + ignored_length] == ignored_parts:
                return True
    return False


def _reference_identity_tokens(values: list[object]) -> set[str]:
    """Return normalized identity tokens for matching related anchor records."""
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
        if normalized:
            tokens.add(normalized)
    return tokens


def _build_active_reference_lookup(
    active_references: list[dict[str, object]],
) -> tuple[dict[str, dict[str, object]], dict[str, str], set[str]]:
    """Return active-reference lookup tables and ambiguous token markers."""
    by_id: dict[str, dict[str, object]] = {}
    token_matches: dict[str, set[str]] = {}
    for ref in active_references:
        ref_id = str(ref.get("id") or "").strip()
        locator = str(ref.get("locator") or "").strip()
        if ref_id:
            by_id[ref_id] = ref
            token_matches.setdefault(ref_id.casefold(), set()).add(ref_id)
        if ref_id and locator:
            token_matches.setdefault(locator.casefold(), set()).add(ref_id)
        for alias in ref.get("aliases", []):
            alias_text = str(alias).strip()
            if alias_text and ref_id:
                token_matches.setdefault(alias_text.casefold(), set()).add(ref_id)
    token_to_id: dict[str, str] = {}
    ambiguous_tokens: set[str] = set()
    for token, ref_ids in token_matches.items():
        if len(ref_ids) == 1:
            token_to_id[token] = next(iter(ref_ids))
        elif len(ref_ids) > 1:
            ambiguous_tokens.add(token)
    return by_id, token_to_id, ambiguous_tokens


def _resolve_reference_token(
    token: object,
    *,
    token_to_id: dict[str, str],
    ambiguous_tokens: set[str],
) -> str:
    """Resolve a reference token without collapsing ambiguous aliases or locators."""
    token_text = str(token).strip()
    if not token_text:
        return token_text
    token_key = token_text.casefold()
    if token_key in ambiguous_tokens:
        return token_text
    return token_to_id.get(token_key, token_text)


def _merge_reference_record(merged: dict[str, dict[str, object]], ref: dict[str, object]) -> None:
    """Merge one active-reference record into the merged registry."""
    ref_id = str(ref.get("id") or "").strip()
    locator = str(ref.get("locator") or "").strip()
    target = merged.get(ref_id) if ref_id else None

    if target is None and locator:
        locator_key = locator.casefold()
        for candidate in merged.values():
            if str(candidate.get("locator") or "").strip().casefold() == locator_key:
                target = candidate
                break
    if target is None:
        incoming_tokens = _reference_identity_tokens([ref_id, locator, *list(ref.get("aliases") or [])])
        for candidate in merged.values():
            candidate_tokens = _reference_identity_tokens(
                [
                    candidate.get("id"),
                    candidate.get("locator"),
                    *list(candidate.get("aliases") or []),
                ]
            )
            if incoming_tokens and candidate_tokens and incoming_tokens.intersection(candidate_tokens):
                target = candidate
                break

    if target is None:
        payload = dict(ref)
        payload["required_actions"] = list(ref.get("required_actions") or [])
        payload["applies_to"] = list(ref.get("applies_to") or [])
        payload["carry_forward_to"] = list(ref.get("carry_forward_to") or [])
        payload["source_artifacts"] = list(ref.get("source_artifacts") or [])
        payload["aliases"] = list(ref.get("aliases") or [])
        if ref_id:
            merged[ref_id] = payload
        else:
            merged[f"derived-{len(merged) + 1:03d}"] = payload
        return

    if ref_id and ref_id != str(target.get("id") or "").strip():
        _append_unique_strings(target.setdefault("aliases", []), [ref_id])

    if str(ref.get("role") or "").strip() and str(target.get("role") or "other").strip() == "other":
        target["role"] = ref.get("role")
    why = str(ref.get("why_it_matters") or "").strip()
    if why:
        existing_why = str(target.get("why_it_matters") or "").strip()
        if existing_why and why not in existing_why:
            target["why_it_matters"] = f"{existing_why}; {why}"
        elif not existing_why:
            target["why_it_matters"] = why
    _append_unique_strings(target.setdefault("required_actions", []), list(ref.get("required_actions") or []))
    _append_unique_strings(target.setdefault("applies_to", []), list(ref.get("applies_to") or []))
    _append_unique_strings(target.setdefault("carry_forward_to", []), list(ref.get("carry_forward_to") or []))
    _append_unique_strings(target.setdefault("source_artifacts", []), list(ref.get("source_artifacts") or []))
    _append_unique_strings(target.setdefault("aliases", []), list(ref.get("aliases") or []))
    target["must_surface"] = bool(target.get("must_surface") or ref.get("must_surface"))


def _merge_active_references(
    contract_references: list[dict[str, object]],
    derived_references: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Merge contract-backed and artifact-derived references into one registry."""
    merged: dict[str, dict[str, object]] = {}
    for ref in contract_references:
        _merge_reference_record(merged, ref)
    for ref in derived_references:
        _merge_reference_record(merged, ref)
    return sorted(
        merged.values(),
        key=lambda ref: (
            0 if ref.get("must_surface") else 1,
            _REFERENCE_ROLE_PRIORITY.get(str(ref.get("role") or "other"), 99),
            str(ref.get("id") or ""),
        ),
    )


def _merge_reference_intake(
    contract: ResearchContract | None,
    derived_intake: dict[str, list[str]],
    active_references: list[dict[str, object]],
) -> dict[str, list[str]]:
    """Return the effective carry-forward intake from contract + parsed artifacts."""
    merged = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    _, token_to_id, ambiguous_tokens = _build_active_reference_lookup(active_references)
    if contract is not None:
        intake = contract.context_intake.model_dump(mode="json")
        for key in merged:
            _append_unique_strings(merged[key], list(intake.get(key) or []))
    for key in merged:
        _append_unique_strings(merged[key], list(derived_intake.get(key) or []))
    canonical_must_read_refs: list[str] = []
    for token in merged["must_read_refs"]:
        resolved = _resolve_reference_token(
            token,
            token_to_id=token_to_id,
            ambiguous_tokens=ambiguous_tokens,
        )
        _append_unique_strings(canonical_must_read_refs, [resolved])
    merged["must_read_refs"] = canonical_must_read_refs
    return merged


def _canonical_contract_reference_payload(
    active_references: list[dict[str, object]],
    *,
    allowed_subject_ids: set[str],
) -> list[dict[str, object]]:
    """Return contract-safe reference payloads derived from active references."""

    payloads: list[dict[str, object]] = []
    for ref in active_references:
        ref_id = str(ref.get("id") or "").strip()
        locator = str(ref.get("locator") or "").strip()
        if not ref_id or not locator:
            continue
        payloads.append(
            {
                "id": ref_id,
                "kind": str(ref.get("kind") or "other"),
                "locator": locator,
                "aliases": [str(item).strip() for item in list(ref.get("aliases") or []) if str(item).strip()],
                "role": str(ref.get("role") or "other"),
                "why_it_matters": str(ref.get("why_it_matters") or "").strip() or locator,
                "applies_to": [item for item in list(ref.get("applies_to") or []) if item in allowed_subject_ids],
                "carry_forward_to": [
                    str(item).strip() for item in list(ref.get("carry_forward_to") or []) if str(item).strip()
                ],
                "must_surface": bool(ref.get("must_surface")),
                "required_actions": list(ref.get("required_actions") or []),
            }
        )
    return payloads


def _merge_contract_reference_payload(
    existing: dict[str, object],
    derived: dict[str, object],
    *,
    allowed_subject_ids: set[str],
) -> dict[str, object]:
    """Merge one derived anchor into an existing contract reference payload."""

    payload = dict(existing)
    if not str(payload.get("kind") or "").strip():
        payload["kind"] = derived.get("kind")
    if not str(payload.get("locator") or "").strip():
        payload["locator"] = derived.get("locator")
    merged_aliases: list[str] = [str(item).strip() for item in list(payload.get("aliases") or []) if str(item).strip()]
    _append_unique_strings(merged_aliases, list(derived.get("aliases") or []))
    payload["aliases"] = merged_aliases
    if str(payload.get("role") or "other").strip() == "other" and str(derived.get("role") or "").strip():
        payload["role"] = derived.get("role")

    existing_why = str(payload.get("why_it_matters") or "").strip()
    derived_why = str(derived.get("why_it_matters") or "").strip()
    if not existing_why and derived_why:
        payload["why_it_matters"] = derived_why
    elif existing_why and derived_why and derived_why not in existing_why:
        payload["why_it_matters"] = f"{existing_why}; {derived_why}"

    merged_applies_to: list[str] = [item for item in list(payload.get("applies_to") or []) if item in allowed_subject_ids]
    _append_unique_strings(
        merged_applies_to,
        [item for item in list(derived.get("applies_to") or []) if item in allowed_subject_ids],
    )
    payload["applies_to"] = merged_applies_to
    merged_carry_forward_to: list[str] = [
        str(item).strip() for item in list(payload.get("carry_forward_to") or []) if str(item).strip()
    ]
    _append_unique_strings(merged_carry_forward_to, list(derived.get("carry_forward_to") or []))
    payload["carry_forward_to"] = merged_carry_forward_to

    merged_actions: list[str] = list(payload.get("required_actions") or [])
    _append_unique_strings(merged_actions, list(derived.get("required_actions") or []))
    payload["required_actions"] = merged_actions
    payload["must_surface"] = bool(payload.get("must_surface") or derived.get("must_surface"))
    return payload


def _canonical_contract_intake(
    contract: ResearchContract,
    *,
    active_references: list[dict[str, object]],
    effective_reference_intake: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Return additive canonical intake with canonicalized reference IDs."""

    del effective_reference_intake  # Artifact-derived intake stays in ``effective_reference_intake`` only.

    intake = contract.context_intake.model_dump(mode="json")
    _, token_to_id, ambiguous_tokens = _build_active_reference_lookup(active_references)
    canonical_must_read_refs: list[str] = []
    for token in list(intake.get("must_read_refs") or []):
        resolved = _resolve_reference_token(
            token,
            token_to_id=token_to_id,
            ambiguous_tokens=ambiguous_tokens,
        )
        _append_unique_strings(canonical_must_read_refs, [resolved])
    intake["must_read_refs"] = canonical_must_read_refs
    return intake


def _canonicalize_project_contract(
    contract: ResearchContract | None,
    *,
    active_references: list[dict[str, object]],
    effective_reference_intake: dict[str, list[str]],
) -> tuple[ResearchContract | None, list[str]]:
    """Return the canonical contract after merging durable anchor context."""

    if contract is None:
        return None, []

    payload = contract.model_dump(mode="json")
    payload["context_intake"] = _canonical_contract_intake(
        contract,
        active_references=active_references,
        effective_reference_intake=effective_reference_intake,
    )
    allowed_subject_ids = {
        str(item.get("id") or "").strip()
        for item in [*payload.get("claims", []), *payload.get("deliverables", [])]
        if str(item.get("id") or "").strip()
    }
    canonical_refs = _canonical_contract_reference_payload(
        active_references,
        allowed_subject_ids=allowed_subject_ids,
    )
    refs_by_id = {
        str(ref.get("id") or "").strip(): ref
        for ref in canonical_refs
        if str(ref.get("id") or "").strip()
    }
    refs_by_locator = {
        str(ref.get("locator") or "").strip().casefold(): ref
        for ref in canonical_refs
        if str(ref.get("locator") or "").strip()
    }
    merged_references: list[dict[str, object]] = []
    for existing in list(payload.get("references") or []):
        ref_id = str(existing.get("id") or "").strip()
        locator_key = str(existing.get("locator") or "").strip().casefold()
        derived = refs_by_id.get(ref_id)
        if derived is None and locator_key:
            derived = refs_by_locator.get(locator_key)
        merged = (
            _merge_contract_reference_payload(existing, derived, allowed_subject_ids=allowed_subject_ids)
            if derived is not None
            else existing
        )
        merged_references.append(merged)
    payload["references"] = merged_references
    try:
        return ResearchContract.model_validate(payload), []
    except PydanticValidationError as exc:
        validation_errors = [
            f"{'.'.join(str(part) for part in error.get('loc', ())) or 'project_contract'}: {str(error.get('msg', 'validation failed')).strip() or 'validation failed'}"
            for error in exc.errors()
        ]
        warning = "canonical project_contract merge failed validation; keeping original contract: " + "; ".join(
            validation_errors
        )
        logger.warning(warning)
        return contract, [warning]
    except Exception as exc:
        warning = f"canonical project_contract merge failed unexpectedly; keeping original contract: {exc}"
        logger.warning(warning)
        return contract, [warning]


def _render_active_reference_context(
    active_references: list[dict[str, object]],
    effective_intake: dict[str, list[str]],
    literature_review_files: list[str],
    research_map_reference_files: list[str],
    contract_validation: dict[str, object] | None = None,
    contract_load_info: dict[str, object] | None = None,
) -> str:
    """Render a compact text block of anchors and carry-forward inputs."""
    lines: list[str] = ["## Active Reference Registry"]
    refs_by_id, _, _ = _build_active_reference_lookup(active_references)

    if active_references:
        for ref in active_references:
            actions = ", ".join(str(action) for action in ref.get("required_actions", [])) or "review"
            applies_to = ", ".join(str(item) for item in ref.get("applies_to", [])) or "global"
            carry_forward_to = ", ".join(str(item) for item in ref.get("carry_forward_to", []))
            kind = str(ref.get("kind") or "other")
            must_surface = " | must surface" if ref.get("must_surface") else ""
            carry_forward_note = f" | carry forward: {carry_forward_to}" if carry_forward_to else ""
            source_artifacts = ", ".join(str(item) for item in ref.get("source_artifacts", []) if item)
            source_note = f" | source: {source_artifacts}" if source_artifacts else ""
            lines.append(
                f"- [{ref['id']}] {ref['locator']} | kind: {kind} | role: {ref['role']}{must_surface} | "
                f"actions: {actions} | applies_to: {applies_to}{carry_forward_note} | "
                f"why: {ref['why_it_matters']}{source_note}"
            )
    else:
        if literature_review_files or research_map_reference_files:
            lines.append("- No structured anchors parsed yet; raw reference artifacts are available below.")
        else:
            lines.append("- None confirmed in `state.json.project_contract.references` yet.")

    if contract_load_info is not None:
        load_status = str(contract_load_info.get("status") or "").strip()
        load_warnings = list(contract_load_info.get("warnings") or [])
        load_errors = list(contract_load_info.get("errors") or [])
        if load_status.startswith("blocked") or load_warnings:
            lines.extend(["", "## Project Contract Intake"])
            lines.append(f"- Load status: {load_status.replace('_', ' ')}")
            source_path = str(contract_load_info.get("source_path") or "").strip()
            if source_path:
                lines.append(f"- Source: {source_path}")
            for error in load_errors:
                lines.append(f"- Blocker: {error}")
            for warning in load_warnings:
                lines.append(f"- Warning: {warning}")

    if contract_validation is not None:
        lines.extend(["", "## Project Contract Validation"])
        if contract_validation.get("valid") is True:
            lines.append("- Approval status: ready")
        else:
            lines.append("- Approval status: blocked")
        for error in list(contract_validation.get("errors") or []):
            lines.append(f"- Blocker: {error}")
        for warning in list(contract_validation.get("warnings") or []):
            lines.append(f"- Warning: {warning}")

    lines.extend(
        [
            "",
            "## Carry-Forward Inputs",
            "### Must-Read References",
        ]
    )
    if effective_intake["must_read_refs"]:
        for item in effective_intake["must_read_refs"]:
            ref = refs_by_id.get(item)
            if ref is None:
                lines.append(f"- {item} | unresolved reference token")
                continue
            actions = ", ".join(str(action) for action in ref.get("required_actions", [])) or "review"
            lines.append(f"- [{item}] {ref['locator']} | actions: {actions} | role: {ref.get('role', 'other')}")
    else:
        lines.append("- None confirmed yet.")

    lines.append("")
    lines.append("### Prior Outputs and Baselines")
    if effective_intake["must_include_prior_outputs"]:
        lines.extend(f"- {item}" for item in effective_intake["must_include_prior_outputs"])
    else:
        lines.append("- None confirmed yet.")
    if effective_intake["known_good_baselines"]:
        lines.extend(f"- Baseline: {item}" for item in effective_intake["known_good_baselines"])
    if effective_intake["crucial_inputs"]:
        lines.extend(f"- Crucial input: {item}" for item in effective_intake["crucial_inputs"])

    lines.append("")
    lines.append("### User-Asserted Anchors and Gaps")
    if effective_intake["user_asserted_anchors"]:
        lines.extend(f"- Anchor: {item}" for item in effective_intake["user_asserted_anchors"])
    else:
        lines.append("- No additional user-asserted anchors recorded.")
    if effective_intake["context_gaps"]:
        lines.extend(f"- Gap: {item}" for item in effective_intake["context_gaps"])

    lines.append("")
    lines.append("## Reference Artifacts Available")
    if literature_review_files:
        lines.extend(f"- Literature review: {path}" for path in literature_review_files)
    if research_map_reference_files:
        lines.extend(f"- Research map: {path}" for path in research_map_reference_files)
    if not literature_review_files and not research_map_reference_files:
        lines.append("- No literature-review or research-map anchor artifacts found yet.")

    return "\n".join(lines)


def _reference_artifact_payload(cwd: Path) -> dict[str, object]:
    """Collect durable reference artifacts for downstream planning and verification."""
    literature_dir = cwd / PLANNING_DIR_NAME / _LITERATURE_DIR_NAME
    literature_paths = _sorted_markdown_files(literature_dir)
    research_map_dir = cwd / PLANNING_DIR_NAME / RESEARCH_MAP_DIR_NAME
    research_map_paths = _sorted_markdown_files(research_map_dir)
    prioritized_research_map_paths = [
        research_map_dir / name for name in _REFERENCE_MAP_DOCS if (research_map_dir / name).is_file()
    ]
    prioritized_names = {path.name for path in prioritized_research_map_paths}
    prioritized_research_map_paths.extend(path for path in research_map_paths if path.name not in prioritized_names)

    literature_review_files = [_relative_posix(cwd, path) for path in literature_paths]
    research_map_reference_files = [_relative_posix(cwd, path) for path in prioritized_research_map_paths]

    content_sections: list[str] = []
    selected_artifacts = [
        *prioritized_research_map_paths[:_RESEARCH_MAP_INCLUDE_LIMIT],
        *literature_paths[:_LITERATURE_INCLUDE_LIMIT],
    ]
    for path in selected_artifacts:
        content = _safe_read_file_truncated(path)
        if not content:
            continue
        content_sections.append(f"## {path.relative_to(cwd).as_posix()}\n{content}")

    return {
        "literature_review_files": literature_review_files,
        "literature_review_count": len(literature_review_files),
        "research_map_reference_files": research_map_reference_files,
        "research_map_reference_count": len(research_map_reference_files),
        "reference_artifact_files": [*research_map_reference_files, *literature_review_files],
        "reference_artifacts_content": "\n\n".join(content_sections) if content_sections else None,
    }


def _build_reference_runtime_context(cwd: Path) -> dict[str, object]:
    """Build shared reference/anchor context for workflow init payloads."""
    contract, project_contract_load_info = _load_project_contract(cwd)
    artifact_payload = _reference_artifact_payload(cwd)
    artifact_ingestion = ingest_reference_artifacts(
        cwd,
        literature_review_files=list(artifact_payload["literature_review_files"]),
        research_map_reference_files=list(artifact_payload["research_map_reference_files"]),
    )
    manuscript_reference_status = ingest_manuscript_reference_status(cwd)
    derived_references = [ref.to_context_dict() for ref in artifact_ingestion.references]
    derived_citation_sources = [item.to_context_dict() for item in artifact_ingestion.citation_sources]
    derived_manuscript_reference_status = {
        record.reference_id: record.to_context_dict()
        for record in manuscript_reference_status.reference_status
    }
    active_references = _merge_active_references(_serialize_active_references(contract), derived_references)
    effective_reference_intake = _merge_reference_intake(
        contract,
        artifact_ingestion.intake.to_dict(),
        active_references,
    )
    visible_contract, canonicalization_warnings = _canonicalize_project_contract(
        contract,
        active_references=active_references,
        effective_reference_intake=effective_reference_intake,
    )
    if canonicalization_warnings:
        project_contract_load_info = {
            **project_contract_load_info,
            "warnings": [*list(project_contract_load_info.get("warnings") or []), *canonicalization_warnings],
        }
    project_contract_load_info, project_contract_validation, project_contract_gate = _finalize_project_contract_gate(
        cwd,
        visible_contract,
        project_contract_load_info,
    )
    project_text = _safe_read_file(cwd / PLANNING_DIR_NAME / PROJECT_FILENAME)
    selected_protocol_bundles = select_protocol_bundles(project_text, visible_contract)

    bundle_verifier_extensions: list[dict[str, object]] = []
    for bundle in selected_protocol_bundles:
        for extension in bundle.verifier_extensions:
            bundle_verifier_extensions.append(
                {
                    "bundle_id": bundle.bundle_id,
                    "bundle_title": bundle.title,
                    **extension.model_dump(mode="json"),
                }
            )

    return {
        "project_contract": visible_contract.model_dump(mode="json") if visible_contract is not None else None,
        "project_contract_validation": project_contract_validation,
        "project_contract_load_info": project_contract_load_info,
        "project_contract_gate": project_contract_gate,
        "contract_intake": visible_contract.context_intake.model_dump(mode="json") if visible_contract is not None else None,
        "effective_reference_intake": effective_reference_intake,
        "derived_active_references": derived_references,
        "derived_active_reference_count": len(derived_references),
        "citation_source_files": list(artifact_ingestion.citation_source_files),
        "citation_source_count": len(artifact_ingestion.citation_source_files),
        "citation_source_warnings": list(artifact_ingestion.citation_source_warnings),
        "derived_citation_sources": derived_citation_sources,
        "derived_citation_source_count": len(derived_citation_sources),
        "derived_manuscript_reference_status": derived_manuscript_reference_status,
        "derived_manuscript_reference_status_count": len(derived_manuscript_reference_status),
        "active_references": active_references,
        "active_reference_count": len(active_references),
        "selected_protocol_bundle_ids": [bundle.bundle_id for bundle in selected_protocol_bundles],
        "protocol_bundle_count": len(selected_protocol_bundles),
        "protocol_bundle_verifier_extensions": bundle_verifier_extensions,
        "protocol_bundle_context": render_protocol_bundle_context(selected_protocol_bundles),
        "active_reference_context": _render_active_reference_context(
            active_references,
            effective_reference_intake,
            artifact_payload["literature_review_files"],
            artifact_payload["research_map_reference_files"],
            project_contract_validation,
            project_contract_load_info,
        ),
        **artifact_payload,
    }


def _has_structured_state_value(value: object) -> bool:
    """Return whether a derived state value should be surfaced."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _build_state_memory_runtime_context(cwd: Path) -> dict[str, object]:
    """Build shared structured state-memory context for init surfaces."""
    state, _state_issues, _state_source = _peek_state_json(cwd)
    if not isinstance(state, dict):
        return {
            "derived_convention_lock": {},
            "derived_convention_lock_count": 0,
            "derived_intermediate_results": [],
            "derived_intermediate_result_count": 0,
            "derived_approximations": [],
            "derived_approximation_count": 0,
        }

    raw_lock = state.get("convention_lock")
    derived_convention_lock: dict[str, object] = {}
    if isinstance(raw_lock, Mapping):
        try:
            normalized_lock = ConventionLock(**raw_lock).model_dump(mode="json", exclude_none=True)
        except PydanticValidationError:
            normalized_lock = {}
        derived_convention_lock = {
            key: value for key, value in normalized_lock.items() if _has_structured_state_value(value)
        }

    derived_results = [result.model_dump(mode="json") for result in result_list(state)]
    derived_approximations = [approx.model_dump(mode="json") for approx in approximation_list(state)]

    return {
        "derived_convention_lock": derived_convention_lock,
        "derived_convention_lock_count": len(derived_convention_lock),
        "derived_intermediate_results": derived_results,
        "derived_intermediate_result_count": len(derived_results),
        "derived_approximations": derived_approximations,
        "derived_approximation_count": len(derived_approximations),
    }


def _build_execution_runtime_context(cwd: Path) -> dict[str, object]:
    """Build shared live execution-state context for orchestration surfaces."""
    from gpd.core.observability import get_current_execution

    snapshot = get_current_execution(cwd)
    state, _state_issues, _state_source = _peek_state_json(cwd)
    position = state.get("position") if isinstance(state, dict) else {}
    session = state.get("session") if isinstance(state, dict) else {}
    machine = _current_machine_identity()
    current_hostname = machine.get("hostname")
    current_platform = machine.get("platform")
    session_hostname = session.get("hostname") if isinstance(session, dict) else None
    session_platform = session.get("platform") if isinstance(session, dict) else None
    session_last_date = session.get("last_date") if isinstance(session, dict) else None
    session_stopped_at = session.get("stopped_at") if isinstance(session, dict) else None
    current_execution_resume_file = _normalize_runtime_resume_file(
        cwd,
        snapshot.resume_file if snapshot is not None else None,
        require_exists=True,
    )
    current_execution_payload = snapshot.model_dump(mode="json") if snapshot is not None else None
    if isinstance(current_execution_payload, dict):
        current_execution_payload["resume_file"] = current_execution_resume_file
    resume_projection = _resolve_resume_projection(
        cwd,
        state=state,
        current_execution=current_execution_payload,
    )
    execution_resume_file_source = None
    if resume_projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT:
        execution_resume_file_source = "current_execution"
    elif resume_projection.active_resume_source == ContinuationResumeSource.HANDOFF:
        execution_resume_file_source = "session_resume_file"

    paused_states = {"paused", "awaiting_user", "ready_to_continue", "waiting_review", "blocked"}
    segment_status = (snapshot.segment_status or "").lower() if snapshot is not None else ""
    is_resumable = bool(resume_projection.resumable)
    paused_at = (
        snapshot.updated_at
        if snapshot is not None and segment_status in paused_states
        else (position.get("paused_at") if isinstance(position, dict) else None)
    )
    resume_file = resume_projection.active_resume_file
    machine_change_detected = bool(
        session_hostname
        and session_platform
        and (
            session_hostname != current_hostname
            or session_platform != current_platform
        )
    )
    machine_change_notice = None
    if machine_change_detected:
        machine_change_notice = (
            "Machine change detected: "
            f"last active on {session_hostname} ({session_platform}); "
            f"current machine {current_hostname} ({current_platform}). "
            "The project state is portable and does not require repair. "
            "Rerun the installer if runtime-local config may be stale on this machine."
        )

    return {
        "current_execution": current_execution_payload,
        "has_live_execution": snapshot is not None,
        "execution_review_pending": bool(
            snapshot
            and (
                snapshot.first_result_gate_pending
                or snapshot.pre_fanout_review_pending
                or snapshot.skeptical_requestioning_required
                or snapshot.waiting_for_review
            )
        ),
        "execution_pre_fanout_review_pending": bool(snapshot and snapshot.pre_fanout_review_pending),
        "execution_skeptical_requestioning_required": bool(
            snapshot and snapshot.skeptical_requestioning_required
        ),
        "execution_downstream_locked": bool(snapshot and snapshot.downstream_locked),
        "execution_blocked": bool(snapshot and snapshot.blocked_reason),
        "execution_resumable": is_resumable,
        "execution_paused_at": paused_at,
        "current_execution_resume_file": current_execution_resume_file,
        "session_resume_file": resume_projection.handoff_resume_file,
        "recorded_session_resume_file": resume_projection.recorded_handoff_resume_file,
        "missing_session_resume_file": resume_projection.missing_handoff_resume_file,
        "execution_resume_file": resume_file,
        "execution_resume_file_source": execution_resume_file_source,
        "resume_projection": resume_projection,
        "current_hostname": current_hostname,
        "current_platform": current_platform,
        "session_hostname": session_hostname,
        "session_platform": session_platform,
        "session_last_date": session_last_date,
        "session_stopped_at": session_stopped_at,
        "machine_change_detected": machine_change_detected,
        "machine_change_notice": machine_change_notice,
    }


def _normalize_runtime_resume_file(
    cwd: Path,
    resume_file: object,
    *,
    require_exists: bool = False,
) -> str | None:
    """Return a portable repo-local resume pointer when one can be trusted."""
    if not isinstance(resume_file, str):
        return None

    normalized = resume_file.strip()
    if not normalized or normalized == EM_DASH or normalized.casefold() in _RESUME_FILE_CLEAR_VALUES:
        return None

    resolved_cwd = cwd.resolve(strict=False)
    candidate = Path(normalized).expanduser()
    if candidate.is_absolute():
        try:
            normalized = candidate.resolve(strict=False).relative_to(resolved_cwd).as_posix()
        except (OSError, ValueError):
            return None
        candidate = Path(normalized)

    if candidate.is_absolute():
        return None

    resolved_target = (cwd / candidate).resolve(strict=False)
    try:
        resolved_target.relative_to(resolved_cwd)
    except (OSError, ValueError):
        return None

    if require_exists and not resolved_target.exists():
        return None

    return candidate.as_posix()


def _resolve_resume_projection(
    cwd: Path,
    *,
    state: dict[str, object] | None,
    current_execution: dict[str, object] | None,
):
    try:
        return resolve_continuation(cwd, state=state, current_execution=current_execution)
    except Exception as exc:
        logger.warning(
            "Canonical continuation resolution failed; falling back to legacy session continuity: %s",
            exc,
        )
        legacy_state = {"session": state.get("session")} if isinstance(state, dict) else {}
        return resolve_continuation(cwd, state=legacy_state, current_execution=current_execution)


def _resume_projection_source_name(resume_projection: object) -> str | None:
    source = getattr(resume_projection, "source", None)
    if hasattr(source, "value"):
        source = source.value
    if not isinstance(source, str):
        return None
    stripped = source.strip()
    return stripped or None


def _bounded_segment_resume_origin(resume_projection: object) -> str:
    continuation = getattr(resume_projection, "continuation", None)
    segment = getattr(continuation, "bounded_segment", None)
    recorded_by = getattr(segment, "recorded_by", None)
    return resume_origin_for_bounded_segment(
        recorded_by=recorded_by if isinstance(recorded_by, str) else None,
        source=_resume_projection_source_name(resume_projection),
    )


def _handoff_resume_origin(resume_projection: object) -> str:
    continuation = getattr(resume_projection, "continuation", None)
    handoff = getattr(continuation, "handoff", None)
    recorded_by = getattr(handoff, "recorded_by", None)
    return resume_origin_for_handoff(
        recorded_by=recorded_by if isinstance(recorded_by, str) else None,
        source=_resume_projection_source_name(resume_projection),
    )


def _handoff_last_result_id(resume_projection: object) -> str | None:
    continuation = getattr(resume_projection, "continuation", None)
    handoff = getattr(continuation, "handoff", None)
    last_result_id = getattr(handoff, "last_result_id", None)
    if not isinstance(last_result_id, str):
        return None
    stripped = last_result_id.strip()
    return stripped or None


def _build_resume_result_lookup(cwd: Path) -> dict[str, dict[str, object]]:
    """Return canonical results keyed by ID for resume hydration."""
    state, _state_issues, _state_source = _peek_state_json(cwd)
    if not isinstance(state, dict):
        return {}
    try:
        return {
            result.id: result.model_dump(mode="json")
            for result in result_list(state)
            if isinstance(result.id, str) and result.id.strip()
        }
    except (PydanticValidationError, TypeError, ValueError) as exc:
        logger.warning("Resume result hydration unavailable: %s", exc)
        return {}


def _hydrate_resume_result(
    candidate: Mapping[str, object],
    result_lookup_by_id: Mapping[str, dict[str, object]],
) -> dict[str, object]:
    """Attach the canonical result payload when a candidate carries `last_result_id`."""
    hydrated = dict(candidate)
    last_result_id = hydrated.get("last_result_id")
    if not isinstance(last_result_id, str):
        return hydrated
    lookup_key = last_result_id.strip()
    if not lookup_key:
        return hydrated
    last_result = result_lookup_by_id.get(lookup_key)
    if isinstance(last_result, Mapping):
        hydrated["last_result"] = dict(last_result)
    return hydrated


def _select_active_resume_candidate(
    resume_candidates: list[dict[str, object]],
    *,
    active_resume_kind: str | None,
    active_resume_pointer: str | None,
) -> dict[str, object] | None:
    """Return the candidate currently selected as the active resume target."""
    if not isinstance(active_resume_kind, str):
        return None
    active_kind = active_resume_kind.strip()
    if not active_kind:
        return None
    active_pointer = active_resume_pointer.strip() if isinstance(active_resume_pointer, str) and active_resume_pointer.strip() else None

    if active_pointer is not None:
        for candidate in resume_candidates:
            if str(candidate.get("kind") or "").strip() != active_kind:
                continue
            if candidate.get("resume_pointer") != active_pointer:
                continue
            return candidate

    for candidate in resume_candidates:
        if str(candidate.get("kind") or "").strip() == active_kind:
            return candidate
    return None


def _interrupted_agent_resume_origin() -> str:
    return resume_origin_for_interrupted_agent()


def _resume_candidate_from_segment(segment: dict[str, object]) -> dict[str, object]:
    return build_resume_segment_candidate(segment)


def _canonical_resume_candidate(
    candidate: dict[str, object],
    *,
    kind: str,
    origin: str,
    resume_pointer: str | None = None,
) -> dict[str, object]:
    return build_resume_candidate(
        candidate,
        kind=kind,
        origin=origin,
        resume_pointer=resume_pointer,
    )


def _has_candidate(
    segment_candidates: list[dict[str, object]],
    *,
    source: str,
    resume_file: str | None = None,
    agent_id: str | None = None,
) -> bool:
    for candidate in segment_candidates:
        if str(candidate.get("source") or "").strip() != source:
            continue
        if resume_file is not None and candidate.get("resume_file") != resume_file:
            continue
        if agent_id is not None and candidate.get("agent_id") != agent_id:
            continue
        return True
    return False


def _has_resume_candidate(
    resume_candidates: list[dict[str, object]],
    *,
    kind: str,
    resume_pointer: str | None = None,
    agent_id: str | None = None,
) -> bool:
    for candidate in resume_candidates:
        if str(candidate.get("kind") or "").strip() != kind:
            continue
        if resume_pointer is not None and candidate.get("resume_pointer") != resume_pointer:
            continue
        if agent_id is not None and candidate.get("agent_id") != agent_id:
            continue
        return True
    return False


def _build_legacy_resume_state(
    execution_context: dict[str, object],
    *,
    interrupted_agent_id: str | None,
    result_lookup_by_id: dict[str, dict[str, object]],
) -> dict[str, object]:
    segment_candidates: list[dict[str, object]] = []
    current_execution = execution_context.get("current_execution")
    active_bounded_segment = current_execution if execution_context.get("execution_resumable") and isinstance(current_execution, dict) else None
    resume_candidates: list[dict[str, object]] = []
    if isinstance(active_bounded_segment, dict):
        current_candidate = _resume_candidate_from_segment(active_bounded_segment)
        segment_candidates.append(current_candidate)
        resume_candidates.append(
            _canonical_resume_candidate(
                current_candidate,
                kind="bounded_segment",
                origin="compat.current_execution",
                resume_pointer=current_candidate.get("resume_file")
                if isinstance(current_candidate.get("resume_file"), str)
                else None,
            )
        )

    session_resume_file = execution_context.get("session_resume_file")
    if isinstance(session_resume_file, str) and session_resume_file:
        session_candidate = {
            "source": "session_resume_file",
            "status": "handoff",
            "resume_file": session_resume_file,
            "resumable": False,
        }
        if not any(
            candidate.get("resume_file") == session_candidate["resume_file"]
            for candidate in segment_candidates
        ):
            segment_candidates.append(session_candidate)
            resume_candidates.append(
                _canonical_resume_candidate(
                    session_candidate,
                    kind="continuity_handoff",
                    origin="compat.session_resume_file",
                    resume_pointer=session_resume_file,
                )
            )

    missing_session_resume_file = execution_context.get("missing_session_resume_file")
    if isinstance(missing_session_resume_file, str) and missing_session_resume_file:
        missing_session_candidate = {
            "source": "session_resume_file",
            "status": "missing",
            "resume_file": missing_session_resume_file,
            "resumable": False,
            "advisory": True,
        }
        if not any(
            candidate.get("resume_file") == missing_session_candidate["resume_file"]
            and candidate.get("source") == missing_session_candidate["source"]
            for candidate in segment_candidates
        ):
            segment_candidates.append(missing_session_candidate)
            resume_candidates.append(
                _canonical_resume_candidate(
                    missing_session_candidate,
                    kind="continuity_handoff",
                    origin="compat.session_resume_file",
                    resume_pointer=missing_session_resume_file,
                )
            )

    if interrupted_agent_id is not None:
        interrupted_candidate = {
            "source": "interrupted_agent",
            "status": "interrupted",
            "agent_id": interrupted_agent_id,
        }
        segment_candidates.append(interrupted_candidate)
        resume_candidates.append(
            _canonical_resume_candidate(
                interrupted_candidate,
                kind="interrupted_agent",
                origin="interrupted_agent_marker",
                resume_pointer=interrupted_agent_id,
            )
        )

    if execution_context.get("execution_resumable") and isinstance(current_execution, dict):
        resume_mode = "bounded_segment"
    elif interrupted_agent_id is not None:
        resume_mode = "interrupted_agent"
    else:
        resume_mode = None

    if execution_context.get("execution_resumable") and isinstance(current_execution, dict):
        active_resume_kind = "bounded_segment"
        active_resume_origin = "compat.current_execution"
        active_resume_pointer = current_execution.get("resume_file")
    elif isinstance(session_resume_file, str) and session_resume_file:
        active_resume_kind = "continuity_handoff"
        active_resume_origin = "compat.session_resume_file"
        active_resume_pointer = session_resume_file
    elif interrupted_agent_id is not None:
        active_resume_kind = "interrupted_agent"
        active_resume_origin = "interrupted_agent_marker"
        active_resume_pointer = interrupted_agent_id
    else:
        active_resume_kind = None
        active_resume_origin = None
        active_resume_pointer = None

    hydrated_resume_candidates = [_hydrate_resume_result(candidate, result_lookup_by_id) for candidate in resume_candidates]
    active_resume_candidate = _select_active_resume_candidate(
        hydrated_resume_candidates,
        active_resume_kind=active_resume_kind,
        active_resume_pointer=active_resume_pointer,
    )

    result = {
        "resume_surface_schema_version": _RESUME_SURFACE_SCHEMA_VERSION,
        "active_bounded_segment": active_bounded_segment if isinstance(active_bounded_segment, dict) else None,
        "derived_execution_head": current_execution if isinstance(current_execution, dict) else None,
        "continuity_handoff_file": session_resume_file if isinstance(session_resume_file, str) and session_resume_file else None,
        "recorded_continuity_handoff_file": (
            session_resume_file if isinstance(session_resume_file, str) and session_resume_file else missing_session_resume_file
        ),
        "missing_continuity_handoff_file": (
            missing_session_resume_file
            if isinstance(missing_session_resume_file, str) and missing_session_resume_file
            else None
        ),
        "has_continuity_handoff": bool(
            (isinstance(session_resume_file, str) and session_resume_file)
            or (isinstance(missing_session_resume_file, str) and missing_session_resume_file)
        ),
        "resume_candidates": hydrated_resume_candidates,
        "active_resume_kind": active_resume_kind,
        "active_resume_origin": active_resume_origin,
        "active_resume_pointer": active_resume_pointer,
        "active_execution_segment": current_execution if isinstance(current_execution, dict) else None,
        "segment_candidates": segment_candidates,
        "resume_mode": resume_mode,
        "has_interrupted_agent": interrupted_agent_id is not None,
        "interrupted_agent_id": interrupted_agent_id,
    }
    if isinstance(active_resume_candidate, dict):
        active_resume_result = active_resume_candidate.get("last_result")
        if isinstance(active_resume_result, Mapping):
            result["active_resume_result"] = dict(active_resume_result)
    result["compat_resume_surface"] = build_resume_compat_surface(result) or {}
    return result


def _build_resume_read_state(
    execution_context: dict[str, object],
    *,
    interrupted_agent_id: str | None,
    result_lookup_by_id: dict[str, dict[str, object]],
) -> dict[str, object]:
    resume_projection = execution_context.get("resume_projection")
    if hasattr(resume_projection, "continuation"):
        current_execution_raw = execution_context.get("current_execution")
        current_execution = current_execution_raw if isinstance(current_execution_raw, dict) else None
        bounded_segment = getattr(resume_projection.continuation, "bounded_segment", None)
        bounded_segment_origin = _bounded_segment_resume_origin(resume_projection)
        handoff_origin = _handoff_resume_origin(resume_projection)
        handoff_last_result_id = _handoff_last_result_id(resume_projection)
        active_execution_segment = None
        active_bounded_segment = None
        if bounded_segment is not None:
            active_bounded_segment = bounded_segment.model_dump(mode="json")
            active_execution_segment = active_bounded_segment
        elif current_execution is not None:
            active_execution_segment = current_execution

        segment_candidates: list[dict[str, object]] = []
        resume_candidates: list[dict[str, object]] = []
        if resume_projection.resumable and isinstance(active_execution_segment, dict):
            candidate_payload = dict(active_execution_segment)
            candidate_payload["resume_file"] = resume_projection.bounded_segment_resume_file
            candidate = _resume_candidate_from_segment(candidate_payload)
            segment_candidates.append(candidate)
            resume_candidates.append(
                _canonical_resume_candidate(
                    candidate,
                    kind="bounded_segment",
                    origin=bounded_segment_origin,
                    resume_pointer=resume_projection.bounded_segment_resume_file,
                )
            )

        if isinstance(resume_projection.handoff_resume_file, str) and resume_projection.handoff_resume_file:
            if not any(
                candidate.get("resume_file") == resume_projection.handoff_resume_file
                for candidate in segment_candidates
            ):
                candidate = {
                    "source": "session_resume_file",
                    "status": "handoff",
                    "resume_file": resume_projection.handoff_resume_file,
                    "resumable": False,
                }
                if handoff_last_result_id is not None:
                    candidate["last_result_id"] = handoff_last_result_id
                segment_candidates.append(candidate)
                resume_candidates.append(
                    _canonical_resume_candidate(
                        candidate,
                        kind="continuity_handoff",
                        origin=handoff_origin,
                        resume_pointer=resume_projection.handoff_resume_file,
                    )
                )

        if isinstance(resume_projection.missing_handoff_resume_file, str) and resume_projection.missing_handoff_resume_file:
            if not _has_candidate(
                segment_candidates,
                source="session_resume_file",
                resume_file=resume_projection.missing_handoff_resume_file,
            ):
                candidate = {
                    "source": "session_resume_file",
                    "status": "missing",
                    "resume_file": resume_projection.missing_handoff_resume_file,
                    "resumable": False,
                    "advisory": True,
                }
                if handoff_last_result_id is not None:
                    candidate["last_result_id"] = handoff_last_result_id
                segment_candidates.append(candidate)
                resume_candidates.append(
                    _canonical_resume_candidate(
                        candidate,
                        kind="continuity_handoff",
                        origin=handoff_origin,
                        resume_pointer=resume_projection.missing_handoff_resume_file,
                    )
                )

        if interrupted_agent_id is not None and not _has_candidate(
            segment_candidates,
            source="interrupted_agent",
            agent_id=interrupted_agent_id,
        ):
            candidate = {
                "source": "interrupted_agent",
                "status": "interrupted",
                "agent_id": interrupted_agent_id,
            }
            segment_candidates.append(candidate)
            if not _has_resume_candidate(
                resume_candidates,
                kind="interrupted_agent",
                agent_id=interrupted_agent_id,
            ):
                resume_candidates.append(
                    _canonical_resume_candidate(
                        candidate,
                        kind="interrupted_agent",
                        origin=_interrupted_agent_resume_origin(),
                        resume_pointer=interrupted_agent_id,
                    )
                )

        hydrated_resume_candidates = [_hydrate_resume_result(candidate, result_lookup_by_id) for candidate in resume_candidates]

        if resume_projection.resumable:
            resume_mode = "bounded_segment"
        elif interrupted_agent_id is not None:
            resume_mode = "interrupted_agent"
        else:
            resume_mode = None

        if resume_projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT:
            active_resume_kind = "bounded_segment"
            active_resume_origin = bounded_segment_origin
            active_resume_pointer = resume_projection.active_resume_file
        elif resume_projection.active_resume_source == ContinuationResumeSource.HANDOFF:
            active_resume_kind = "continuity_handoff"
            active_resume_origin = handoff_origin
            active_resume_pointer = resume_projection.active_resume_file
        elif interrupted_agent_id is not None:
            active_resume_kind = "interrupted_agent"
            active_resume_origin = _interrupted_agent_resume_origin()
            active_resume_pointer = interrupted_agent_id
        else:
            active_resume_kind = None
            active_resume_origin = None
            active_resume_pointer = None

        active_resume_candidate = _select_active_resume_candidate(
            hydrated_resume_candidates,
            active_resume_kind=active_resume_kind,
            active_resume_pointer=active_resume_pointer,
        )

        result = {
            "resume_surface_schema_version": _RESUME_SURFACE_SCHEMA_VERSION,
            "active_bounded_segment": active_bounded_segment,
            "derived_execution_head": current_execution,
            "continuity_handoff_file": resume_projection.handoff_resume_file,
            "recorded_continuity_handoff_file": resume_projection.recorded_handoff_resume_file,
            "missing_continuity_handoff_file": resume_projection.missing_handoff_resume_file,
            "has_continuity_handoff": resume_projection.recorded_handoff_resume_file is not None,
            "resume_candidates": hydrated_resume_candidates,
            "active_resume_kind": active_resume_kind,
            "active_resume_origin": active_resume_origin,
            "active_resume_pointer": active_resume_pointer,
            "active_execution_segment": active_execution_segment,
            "segment_candidates": segment_candidates,
            "resume_mode": resume_mode,
            "has_interrupted_agent": interrupted_agent_id is not None,
            "interrupted_agent_id": interrupted_agent_id,
        }
        if isinstance(active_resume_candidate, dict):
            active_resume_result = active_resume_candidate.get("last_result")
            if isinstance(active_resume_result, Mapping):
                result["active_resume_result"] = dict(active_resume_result)
        result["compat_resume_surface"] = build_resume_compat_surface(result) or {}
        return result

    try:
        return _build_legacy_resume_state(
            execution_context,
            interrupted_agent_id=interrupted_agent_id,
            result_lookup_by_id=result_lookup_by_id,
        )
    except Exception as exc:
        logger.warning(
            "Legacy resume synthesis failed; returning empty resume state: %s",
            exc,
        )
        result = {
            "resume_surface_schema_version": _RESUME_SURFACE_SCHEMA_VERSION,
            "active_bounded_segment": None,
            "derived_execution_head": execution_context.get("current_execution")
            if isinstance(execution_context.get("current_execution"), dict)
            else None,
            "continuity_handoff_file": None,
            "recorded_continuity_handoff_file": None,
            "missing_continuity_handoff_file": None,
            "has_continuity_handoff": False,
            "resume_candidates": [],
            "active_resume_kind": "interrupted_agent" if interrupted_agent_id is not None else None,
            "active_resume_origin": _interrupted_agent_resume_origin() if interrupted_agent_id is not None else None,
            "active_resume_pointer": interrupted_agent_id,
            "active_execution_segment": execution_context.get("current_execution")
            if isinstance(execution_context.get("current_execution"), dict)
            else None,
            "segment_candidates": [],
            "resume_mode": None,
            "has_interrupted_agent": interrupted_agent_id is not None,
            "interrupted_agent_id": interrupted_agent_id,
        }
        result["compat_resume_surface"] = build_resume_compat_surface(result) or {}
        return result


def _mapping_text(value: Mapping[str, object] | None, key: str) -> str | None:
    if not isinstance(value, Mapping):
        return None
    candidate = value.get(key)
    if not isinstance(candidate, str):
        return None
    stripped = candidate.strip()
    return stripped or None


def _promote_auto_selected_recent_bounded_segment(
    continuation_state: dict[str, object],
    *,
    reentry_metadata: Mapping[str, object],
) -> tuple[dict[str, object], bool]:
    """Promote a stronger auto-selected recent bounded segment over a same-pointer handoff."""

    selected_candidate = reentry_metadata.get("project_reentry_selected_candidate")
    if not isinstance(selected_candidate, Mapping):
        return continuation_state, False
    if not bool(reentry_metadata.get("project_root_auto_selected")):
        return continuation_state, False
    if _mapping_text(selected_candidate, "source") != "recent_project":
        return continuation_state, False
    if _mapping_text(selected_candidate, "resume_target_kind") != "bounded_segment":
        return continuation_state, False
    if not bool(selected_candidate.get("resumable", False)):
        return continuation_state, False

    resume_file = _mapping_text(selected_candidate, "resume_file")
    if resume_file is None:
        return continuation_state, False

    active_resume_kind = _mapping_text(continuation_state, "active_resume_kind")
    active_resume_pointer = _mapping_text(continuation_state, "active_resume_pointer")
    if active_resume_kind == "bounded_segment":
        return continuation_state, False
    if active_resume_kind not in {None, "continuity_handoff"}:
        return continuation_state, False
    if active_resume_pointer is not None and active_resume_pointer != resume_file:
        return continuation_state, False

    active_bounded_segment = continuation_state.get("active_bounded_segment")
    if isinstance(active_bounded_segment, dict) and _mapping_text(active_bounded_segment, "resume_file") not in {
        None,
        resume_file,
    }:
        return continuation_state, False

    recorded_by = _mapping_text(selected_candidate, "source_kind")
    bounded_segment = {
        "segment_status": "paused",
        "resume_file": resume_file,
        "phase": _mapping_text(selected_candidate, "recovery_phase"),
        "plan": _mapping_text(selected_candidate, "recovery_plan"),
        "segment_id": _mapping_text(selected_candidate, "source_segment_id"),
        "transition_id": _mapping_text(selected_candidate, "source_transition_id"),
        "updated_at": (
            _mapping_text(selected_candidate, "resume_target_recorded_at")
            or _mapping_text(selected_candidate, "source_recorded_at")
        ),
    }
    bounded_segment = {
        key: value
        for key, value in bounded_segment.items()
        if not isinstance(value, str) or value.strip()
    }

    raw_candidate = build_resume_segment_candidate(bounded_segment, source="recent_project")
    raw_candidate["resumable"] = True
    canonical_candidate = build_resume_candidate(
        raw_candidate,
        kind="bounded_segment",
        origin=resume_origin_for_bounded_segment(recorded_by=recorded_by),
        resume_pointer=resume_file,
    )

    def _replace_matching_candidate(
        candidates: object,
        replacement: dict[str, object],
        *,
        canonical: bool,
    ) -> list[dict[str, object]]:
        normalized = [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []
        updated: list[dict[str, object]] = []
        replaced = False
        for item in normalized:
            item_resume_file = _mapping_text(item, "resume_file")
            item_kind = _mapping_text(item, "kind") if canonical else None
            item_status = str(item.get("status") or "").strip() if not canonical else None
            if item_resume_file == resume_file and (
                item_kind in {None, "continuity_handoff"} if canonical else item_status in {"handoff", "missing"}
            ):
                if not replaced:
                    updated.append(dict(replacement))
                    replaced = True
                continue
            updated.append(item)
        if not replaced:
            updated.insert(0, dict(replacement))
        return updated

    promoted = dict(continuation_state)
    promoted["active_bounded_segment"] = bounded_segment
    promoted["active_execution_segment"] = bounded_segment
    promoted["active_resume_kind"] = "bounded_segment"
    promoted["active_resume_origin"] = resume_origin_for_bounded_segment(recorded_by=recorded_by)
    promoted["active_resume_pointer"] = resume_file
    promoted["resume_mode"] = "bounded_segment"
    promoted["resume_candidates"] = _replace_matching_candidate(
        promoted.get("resume_candidates"),
        canonical_candidate,
        canonical=True,
    )
    promoted["segment_candidates"] = _replace_matching_candidate(
        promoted.get("segment_candidates"),
        raw_candidate,
        canonical=False,
    )
    return promoted, True


# ─── Config Loader ────────────────────────────────────────────────────────────


def _config_to_dict(cfg: GPDProjectConfig) -> dict:
    """Convert a :class:`GPDProjectConfig` to the plain-dict format used by context callers.

    StrEnum values are converted to plain strings so that downstream template
    code (which does string comparisons) keeps working.
    """
    d: dict[str, object] = {
        "model_profile": str(cfg.model_profile.value),
        "autonomy": str(cfg.autonomy.value),
        "review_cadence": str(cfg.review_cadence.value),
        "research_mode": str(cfg.research_mode.value),
        "commit_docs": cfg.commit_docs,
        "branching_strategy": str(cfg.branching_strategy.value),
        "phase_branch_template": cfg.phase_branch_template,
        "milestone_branch_template": cfg.milestone_branch_template,
        "research": cfg.research,
        "plan_checker": cfg.plan_checker,
        "verifier": cfg.verifier,
        "parallelization": cfg.parallelization,
        "max_unattended_minutes_per_plan": cfg.max_unattended_minutes_per_plan,
        "max_unattended_minutes_per_wave": cfg.max_unattended_minutes_per_wave,
        "project_usd_budget": cfg.project_usd_budget,
        "session_usd_budget": cfg.session_usd_budget,
        "checkpoint_after_n_tasks": cfg.checkpoint_after_n_tasks,
        "checkpoint_after_first_load_bearing_result": cfg.checkpoint_after_first_load_bearing_result,
        "checkpoint_before_downstream_dependent_tasks": cfg.checkpoint_before_downstream_dependent_tasks,
    }
    if cfg.model_overrides:
        d["model_overrides"] = cfg.model_overrides
    return d


def load_config(cwd: Path) -> dict:
    """Load GPD/config.json with defaults.

    Delegates to :func:`gpd.core.config.load_config` (the canonical
    implementation) and converts the result to a plain dict for context
    assembly callers.

    Raises :class:`~gpd.core.errors.ConfigError` on malformed JSON.
    """
    cfg = _load_config_structured(cwd)
    return _config_to_dict(cfg)


# ─── Resolve Model ────────────────────────────────────────────────────────────

# Concrete model selection is runtime-scoped. When no override is configured
# for the active runtime, callers should omit the runtime model parameter and
# allow the platform to use its default model.


def _resolve_model(
    cwd: Path,
    agent_type: str,
    config: dict | None = None,
    runtime: str | None = None,
) -> str | None:
    """Resolve the runtime-specific model override for an agent type."""
    active_runtime = runtime
    if active_runtime is None:
        try:
            from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_runtime_for_gpd_use

            active_runtime = detect_runtime_for_gpd_use(cwd=cwd)
        except Exception:
            active_runtime = _detect_platform(cwd)
    else:
        RUNTIME_UNKNOWN = "unknown"
    if active_runtime == RUNTIME_UNKNOWN:
        active_runtime = _detect_platform(cwd)
    if active_runtime == RUNTIME_UNKNOWN:
        active_runtime = None

    return _resolve_model_canonical(cwd, agent_type, runtime=active_runtime)


# ─── Phase Info Helper ────────────────────────────────────────────────────────


def _try_find_phase(cwd: Path, phase: str) -> dict | None:
    """Attempt to find phase info. Returns a plain dict or None."""
    from gpd.core.phases import find_phase

    result = find_phase(cwd, phase)
    if result is None:
        return None
    return result.model_dump()


def _try_get_milestone_info(cwd: Path) -> dict:
    """Get milestone info from the canonical phases module."""
    from gpd.core.phases import get_milestone_info

    result = get_milestone_info(cwd)
    return result.model_dump()


# ─── Platform Detection ──────────────────────────────────────────────────────


def _detect_platform(cwd: Path | None = None) -> str:
    """Detect the active AI runtime, if any."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = Path.home()
    runtime_unknown = "unknown"
    try:
        from gpd.hooks.runtime_detect import (
            RUNTIME_UNKNOWN,
            detect_active_runtime,
            detect_runtime_for_gpd_use,
            detect_runtime_install_target,
        )
        runtime_unknown = RUNTIME_UNKNOWN

        active = detect_active_runtime(cwd=resolved_cwd, home=resolved_home)
        if active != runtime_unknown:
            return active

        detected = detect_runtime_for_gpd_use(cwd=resolved_cwd, home=resolved_home)
        if detected != runtime_unknown:
            return detected

        for descriptor in iter_runtime_descriptors():
            try:
                install_target = detect_runtime_install_target(
                    descriptor.runtime_name,
                    cwd=resolved_cwd,
                    home=resolved_home,
                )
            except Exception:
                continue
            if install_target is not None:
                return descriptor.runtime_name
    except Exception:
        pass

    return runtime_unknown


# ─── Context Assemblers ──────────────────────────────────────────────────────


def init_execute_phase(cwd: Path, phase: str | None, includes: set[str] | None = None) -> dict:
    """Assemble context for phase execution.

    Args:
        cwd: Project root directory.
        phase: Phase identifier (e.g. "3", "03", "3.1").
        includes: Optional set of file sections to embed (state, config, roadmap).
    """
    if not phase:
        raise ValidationError(
            "phase is required for init execute-phase. "
            "Provide a phase identifier such as '1', '03', or '3.1'."
        )

    includes = includes or set()
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)
    milestone = _try_get_milestone_info(cwd)

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
        "verifier_model": _resolve_model(cwd, "gpd-verifier", config),
        # Config flags
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "review_cadence": config["review_cadence"],
        "research_mode": config["research_mode"],
        "parallelization": config["parallelization"],
        "max_unattended_minutes_per_plan": config["max_unattended_minutes_per_plan"],
        "max_unattended_minutes_per_wave": config["max_unattended_minutes_per_wave"],
        "checkpoint_after_n_tasks": config["checkpoint_after_n_tasks"],
        "checkpoint_after_first_load_bearing_result": config["checkpoint_after_first_load_bearing_result"],
        "checkpoint_before_downstream_dependent_tasks": config["checkpoint_before_downstream_dependent_tasks"],
        "branching_strategy": config["branching_strategy"],
        "phase_branch_template": config["phase_branch_template"],
        "milestone_branch_template": config["milestone_branch_template"],
        "verifier_enabled": config["verifier"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        "phase_slug": phase_info.get("phase_slug") if phase_info else None,
        # Plan inventory
        "plans": phase_info["plans"] if phase_info else [],
        "summaries": phase_info.get("summaries", []) if phase_info else [],
        "incomplete_plans": phase_info.get("incomplete_plans", []) if phase_info else [],
        "plan_count": len(phase_info["plans"]) if phase_info else 0,
        "incomplete_count": len(phase_info.get("incomplete_plans", [])) if phase_info else 0,
        # Branch name
        "branch_name": _compute_branch_name(
            config,
            phase_info.get("phase_number") if phase_info else None,
            phase_info.get("phase_slug") if phase_info else None,
            milestone["version"],
            _generate_slug(milestone["name"]),
        ),
        # Milestone info
        "milestone_version": milestone["version"],
        "milestone_name": milestone["name"],
        "milestone_slug": _generate_slug(milestone["name"]),
        # File existence
        "state_exists": _state_exists(cwd),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "config_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{CONFIG_FILENAME}"),
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))
    result.update(_build_state_memory_runtime_context(cwd))
    result.update(_build_execution_runtime_context(cwd))

    # Include file contents if requested
    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
        result.update(_build_structured_state_runtime_context(cwd))
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / CONFIG_FILENAME)
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)

    return result


def init_plan_phase(cwd: Path, phase: str | None, includes: set[str] | None = None) -> dict:
    """Assemble context for phase planning.

    Args:
        cwd: Project root directory.
        phase: Phase identifier.
        includes: Optional set of file sections to embed
                  (state, roadmap, requirements, context, research, verification, validation).
    """
    if not phase:
        raise ValidationError(
            "phase is required for init plan-phase. "
            "Provide a phase identifier such as '1', '03', or '3.1'."
        )

    includes = includes or set()
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)

    result: dict[str, object] = {
        # Models
        "researcher_model": _resolve_model(cwd, "gpd-phase-researcher", config),
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
        "checker_model": _resolve_model(cwd, "gpd-plan-checker", config),
        # Workflow flags
        "research_enabled": config["research"],
        "plan_checker_enabled": config["plan_checker"],
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        "phase_slug": phase_info.get("phase_slug") if phase_info else None,
        "padded_phase": _normalize_phase_name(phase_info["phase_number"]) if phase_info else None,
        # Existing artifacts
        "has_research": phase_info.get("has_research", False) if phase_info else False,
        "has_context": phase_info.get("has_context", False) if phase_info else False,
        "has_plans": len(phase_info.get("plans", [])) > 0 if phase_info else False,
        "plan_count": len(phase_info.get("plans", [])) if phase_info else 0,
        # Environment
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))
    result.update(_build_state_memory_runtime_context(cwd))

    # Include file contents
    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
        result.update(_build_structured_state_runtime_context(cwd))
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)
    if "requirements" in includes:
        result["requirements_content"] = _safe_read_file_truncated(planning / REQUIREMENTS_FILENAME)
    if "context" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["context_content"] = _find_phase_artifact(phase_dir, CONTEXT_SUFFIX, STANDALONE_CONTEXT)
    if "research" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["research_content"] = _find_phase_artifact(phase_dir, RESEARCH_SUFFIX, STANDALONE_RESEARCH)
    if "verification" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["verification_content"] = _find_phase_artifact(phase_dir, VERIFICATION_SUFFIX)
    if "validation" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["validation_content"] = _find_phase_artifact(phase_dir, VALIDATION_SUFFIX, STANDALONE_VALIDATION)

    return result


def init_new_project(cwd: Path) -> dict:
    """Assemble context for new project creation."""
    config = load_config(cwd)

    # Detect existing research files (walk up to depth 3, max 5 files)
    has_research_files = False
    found_count = 0

    def _walk(directory: Path, depth: int) -> None:
        nonlocal has_research_files, found_count
        if depth > 3 or found_count >= 5:
            return
        try:
            entries = sorted(directory.iterdir())
        except (PermissionError, FileNotFoundError):
            return
        for entry in entries:
            if found_count >= 5:
                return
            if _should_skip_research_scan_entry(cwd, entry):
                continue
            if entry.is_dir():
                _walk(entry, depth + 1)
            elif entry.is_file() and entry.suffix in _RESEARCH_EXTENSIONS:
                found_count += 1
                has_research_files = True

    _walk(cwd, 0)

    has_project_manifest = (
        _path_exists(cwd, "requirements.txt")
        or _path_exists(cwd, "pyproject.toml")
        or _path_exists(cwd, "Makefile")
        or _path_exists(cwd, "main.tex")
    )

    return {
        # Models
        "researcher_model": _resolve_model(cwd, "gpd-project-researcher", config),
        "synthesizer_model": _resolve_model(cwd, "gpd-research-synthesizer", config),
        "roadmapper_model": _resolve_model(cwd, "gpd-roadmapper", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Existing state
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "has_research_map": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{RESEARCH_MAP_DIR_NAME}"),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        # Existing project detection
        "has_research_files": has_research_files,
        "has_project_manifest": has_project_manifest,
        "has_existing_project": has_research_files or has_project_manifest,
        "needs_research_map": (has_research_files or has_project_manifest)
        and not _path_exists(cwd, f"{PLANNING_DIR_NAME}/{RESEARCH_MAP_DIR_NAME}"),
        # Git state
        "has_git": _path_exists(cwd, ".git"),
        # Contract-backed context
        **_build_reference_runtime_context(cwd),
        # Platform
        "platform": _detect_platform(cwd),
    }


def init_new_milestone(cwd: Path) -> dict:
    """Assemble context for new milestone creation."""
    config = load_config(cwd)
    milestone = _try_get_milestone_info(cwd)
    result = {
        # Models
        "researcher_model": _resolve_model(cwd, "gpd-project-researcher", config),
        "synthesizer_model": _resolve_model(cwd, "gpd-research-synthesizer", config),
        "roadmapper_model": _resolve_model(cwd, "gpd-roadmapper", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "research_enabled": config["research"],
        # Current milestone
        "current_milestone": milestone["version"],
        "current_milestone_name": milestone["name"],
        # File existence
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(cwd),
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))
    result.update(_build_state_memory_runtime_context(cwd))
    return result


def init_quick(cwd: Path, description: str | None = None) -> dict:
    """Assemble context for quick task execution."""
    config = load_config(cwd)
    now = datetime.now(UTC)
    normalized_description = description.strip() if isinstance(description, str) else description
    slug = _generate_slug(normalized_description)
    if normalized_description and slug is None:
        slug = "task"
    if slug:
        slug = slug[:40]

    # Find next quick task number
    quick_dir = cwd / PLANNING_DIR_NAME / "quick"
    next_num = 1
    try:
        existing = []
        for entry in quick_dir.iterdir():
            match = re.match(r"^(\d+)-", entry.name)
            if match:
                existing.append(int(match.group(1)))
        if existing:
            next_num = max(existing) + 1
    except (FileNotFoundError, PermissionError):
        pass

    result = {
        # Models
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Quick task info
        "next_num": next_num,
        "slug": slug,
        "description": normalized_description,
        # Timestamps
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        # Paths
        "quick_dir": f"{PLANNING_DIR_NAME}/quick",
        "task_dir": f"{PLANNING_DIR_NAME}/quick/{next_num}-{slug}" if slug else None,
        # File existence
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))
    result.update(_build_state_memory_runtime_context(cwd))
    return result


def init_resume(cwd: Path, *, data_root: Path | None = None) -> dict:
    """Assemble context for resuming work."""
    requested_cwd = cwd.expanduser().resolve(strict=False)
    effective_cwd, reentry_metadata = _resolve_reentry_context(requested_cwd, data_root=data_root)
    config = load_config(effective_cwd)
    execution_context = _build_execution_runtime_context(effective_cwd)
    result_lookup_by_id = _build_resume_result_lookup(effective_cwd)

    # Check for interrupted agent
    interrupted_agent_id = None
    agent_id_file = effective_cwd / PLANNING_DIR_NAME / AGENT_ID_FILENAME
    try:
        interrupted_agent_id = agent_id_file.read_text(encoding="utf-8").strip() or None
    except (FileNotFoundError, OSError):
        pass

    continuation_state = _build_resume_read_state(
        execution_context,
        interrupted_agent_id=interrupted_agent_id,
        result_lookup_by_id=result_lookup_by_id,
    )
    continuation_state, recent_bounded_segment_promoted = _promote_auto_selected_recent_bounded_segment(
        continuation_state,
        reentry_metadata=reentry_metadata,
    )
    active_bounded_segment = continuation_state.get("active_bounded_segment")
    if not isinstance(active_bounded_segment, dict):
        active_bounded_segment = None
    has_interrupted_agent = bool(continuation_state.get("has_interrupted_agent"))
    normalized_interrupted_agent_id = continuation_state.get("interrupted_agent_id")
    if not isinstance(normalized_interrupted_agent_id, str) or not normalized_interrupted_agent_id.strip():
        normalized_interrupted_agent_id = interrupted_agent_id

    continuity_handoff_file = continuation_state.get("continuity_handoff_file")
    if not isinstance(continuity_handoff_file, str) or not continuity_handoff_file.strip():
        continuity_handoff_file = None
    recorded_continuity_handoff_file = continuation_state.get("recorded_continuity_handoff_file")
    if not isinstance(recorded_continuity_handoff_file, str) or not recorded_continuity_handoff_file.strip():
        recorded_continuity_handoff_file = None
    missing_continuity_handoff_file = continuation_state.get("missing_continuity_handoff_file")
    if not isinstance(missing_continuity_handoff_file, str) or not missing_continuity_handoff_file.strip():
        missing_continuity_handoff_file = None
    current_execution = continuation_state.get("active_execution_segment")
    segment_candidates = continuation_state.get("segment_candidates")
    if not isinstance(segment_candidates, list):
        segment_candidates = []
    derived_execution_head = continuation_state.get("derived_execution_head")
    if not isinstance(derived_execution_head, dict):
        derived_execution_head = execution_context.get("current_execution") if isinstance(execution_context.get("current_execution"), dict) else None
    resume_candidates = continuation_state.get("resume_candidates")
    if not isinstance(resume_candidates, list):
        resume_candidates = segment_candidates
    active_resume_kind = continuation_state.get("active_resume_kind")
    if not isinstance(active_resume_kind, str) or not active_resume_kind.strip():
        active_resume_kind = None
    active_resume_origin = continuation_state.get("active_resume_origin")
    if not isinstance(active_resume_origin, str) or not active_resume_origin.strip():
        active_resume_origin = None
    active_resume_pointer = continuation_state.get("active_resume_pointer")
    if not isinstance(active_resume_pointer, str) or not active_resume_pointer.strip():
        active_resume_pointer = None
    resume_mode = continuation_state.get("resume_mode")
    if not isinstance(resume_mode, str) or not resume_mode.strip():
        resume_mode = None
    active_resume_result = continuation_state.get("active_resume_result")
    if not isinstance(active_resume_result, dict):
        active_resume_result = None

    result = {
        "workspace_root": reentry_metadata["workspace_root"],
        "project_root": reentry_metadata["project_root"],
        "project_root_source": reentry_metadata["project_root_source"],
        "project_root_auto_selected": reentry_metadata["project_root_auto_selected"],
        "project_reentry_mode": reentry_metadata["project_reentry_mode"],
        "project_reentry_requires_selection": reentry_metadata["project_reentry_requires_selection"],
        "project_reentry_selected_candidate": reentry_metadata.get("project_reentry_selected_candidate"),
        "project_reentry_candidates": reentry_metadata["project_reentry_candidates"],
        # File existence
        "state_exists": _state_exists(effective_cwd),
        "roadmap_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "planning_exists": _path_exists(effective_cwd, PLANNING_DIR_NAME),
        # Agent state
        "has_interrupted_agent": has_interrupted_agent,
        "interrupted_agent_id": normalized_interrupted_agent_id,
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "review_cadence": config["review_cadence"],
        "research_mode": config["research_mode"],
        "resume_surface_schema_version": continuation_state.get(
            "resume_surface_schema_version",
            _RESUME_SURFACE_SCHEMA_VERSION,
        ),
        "active_bounded_segment": active_bounded_segment,
        "derived_execution_head": derived_execution_head,
        "derived_execution_head_resume_file": execution_context.get("current_execution_resume_file"),
        "continuity_handoff_file": continuity_handoff_file if isinstance(continuity_handoff_file, str) else None,
        "recorded_continuity_handoff_file": (
            recorded_continuity_handoff_file if isinstance(recorded_continuity_handoff_file, str) else None
        ),
        "missing_continuity_handoff_file": (
            missing_continuity_handoff_file if isinstance(missing_continuity_handoff_file, str) else None
        ),
        "has_continuity_handoff": bool(continuation_state.get("has_continuity_handoff")),
        "active_resume_kind": active_resume_kind,
        "active_resume_origin": active_resume_origin,
        "active_resume_pointer": active_resume_pointer,
        "active_resume_result": active_resume_result,
        "resume_candidates": resume_candidates,
        "active_execution_segment": current_execution,
        "segment_candidates": segment_candidates,
        "resume_mode": resume_mode,
        # Platform
        "platform": _detect_platform(effective_cwd),
    }
    result.update(_build_reference_runtime_context(effective_cwd))
    execution_public = {
        key: value for key, value in execution_context.items() if key != "resume_projection"
    }
    result.update(execution_public)
    if recent_bounded_segment_promoted and not bool(result.get("execution_resumable")):
        result["execution_resumable"] = True
    result["compat_resume_surface"] = build_resume_compat_surface(result, continuation_state, execution_context) or {}
    return canonicalize_resume_public_payload(result)


def init_verify_work(cwd: Path, phase: str | None) -> dict:
    """Assemble context for work verification."""
    if not phase:
        raise ValidationError(
            "phase is required for init verify-work. "
            "Provide a phase identifier such as '1', '03', or '3.1'."
        )

    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)

    result = {
        # Models
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
        "checker_model": _resolve_model(cwd, "gpd-plan-checker", config),
        "verifier_model": _resolve_model(cwd, "gpd-verifier", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        # Existing artifacts
        "has_verification": phase_info.get("has_verification", False) if phase_info else False,
        "has_validation": phase_info.get("has_validation", False) if phase_info else False,
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))
    return result


def init_phase_op(cwd: Path, phase: str | None = None, includes: set[str] | None = None) -> dict:
    """Assemble context for generic phase operations (parameter sweep, etc.)."""
    includes = includes or set()
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase) if phase else None

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
        "verifier_model": _resolve_model(cwd, "gpd-verifier", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "review_cadence": config["review_cadence"],
        "research_mode": config["research_mode"],
        "parallelization": config["parallelization"],
        "max_unattended_minutes_per_plan": config["max_unattended_minutes_per_plan"],
        "max_unattended_minutes_per_wave": config["max_unattended_minutes_per_wave"],
        "checkpoint_after_n_tasks": config["checkpoint_after_n_tasks"],
        "checkpoint_after_first_load_bearing_result": config["checkpoint_after_first_load_bearing_result"],
        "checkpoint_before_downstream_dependent_tasks": config["checkpoint_before_downstream_dependent_tasks"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        "phase_slug": phase_info.get("phase_slug") if phase_info else None,
        "padded_phase": _normalize_phase_name(phase_info["phase_number"]) if phase_info else None,
        # Existing artifacts
        "has_research": phase_info.get("has_research", False) if phase_info else False,
        "has_context": phase_info.get("has_context", False) if phase_info else False,
        "has_plans": len(phase_info.get("plans", [])) > 0 if phase_info else False,
        "has_verification": phase_info.get("has_verification", False) if phase_info else False,
        "has_validation": phase_info.get("has_validation", False) if phase_info else False,
        "plan_count": len(phase_info.get("plans", [])) if phase_info else 0,
        # File existence
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(cwd),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))
    result.update(_build_state_memory_runtime_context(cwd))
    result.update(_build_execution_runtime_context(cwd))

    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
        result.update(_build_structured_state_runtime_context(cwd))
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / CONFIG_FILENAME)
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)

    return result


def init_todos(cwd: Path, area: str | None = None) -> dict:
    """Assemble context for todo management."""
    config = load_config(cwd)
    now = datetime.now(UTC)

    pending_dir = cwd / PLANNING_DIR_NAME / TODOS_DIR_NAME / "pending"
    todos: list[dict[str, str]] = []

    try:
        for f in sorted(pending_dir.iterdir()):
            if not f.is_file() or not f.name.endswith(".md"):
                continue
            try:
                content = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
            title = _extract_frontmatter_field(content, "title") or "Untitled"
            todo_area = _extract_frontmatter_field(content, "area") or "general"
            created = _extract_frontmatter_field(content, "created") or "unknown"

            if area and todo_area != area:
                continue

            todos.append(
                {
                    "file": f.name,
                    "created": created,
                    "title": title,
                    "area": todo_area,
                    "path": f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}/pending/{f.name}",
                }
            )
    except (FileNotFoundError, PermissionError):
        pass

    return {
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Timestamps
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        # Todo inventory
        "todo_count": len(todos),
        "todos": todos,
        "pending_todos": todos,
        "area_filter": area,
        # Paths
        "pending_dir": f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}/pending",
        "done_dir": f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}/done",
        # File existence
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        "todos_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}"),
        "pending_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}/pending"),
        # Platform
        "platform": _detect_platform(cwd),
    }


def init_milestone_op(cwd: Path) -> dict:
    """Assemble context for milestone operations (complete, archive, etc.)."""
    config = load_config(cwd)
    milestone = _try_get_milestone_info(cwd)
    reference_runtime_context = _build_reference_runtime_context(cwd)

    milestone_snapshot = _milestone_completion_snapshot(cwd)

    # Check archived milestones
    milestones_dir = cwd / PLANNING_DIR_NAME / MILESTONES_DIR_NAME
    archived_milestones: list[str] = []
    try:
        archived_milestones = sorted(
            entry.name for entry in milestones_dir.iterdir() if entry.is_dir() or entry.is_file()
        )
    except FileNotFoundError:
        pass

    return {
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "branching_strategy": config["branching_strategy"],
        "phase_branch_template": config["phase_branch_template"],
        "milestone_branch_template": config["milestone_branch_template"],
        # Current milestone
        "milestone_version": milestone["version"],
        "milestone_name": milestone["name"],
        "milestone_slug": _generate_slug(milestone["name"]),
        # Phase counts
        "phase_count": milestone_snapshot.phase_count,
        "completed_phases": milestone_snapshot.completed_phases,
        "all_phases_complete": milestone_snapshot.all_phases_complete,
        # Archive
        "archived_milestones": archived_milestones,
        "archive_count": len(archived_milestones),
        # File existence
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(cwd),
        "milestones_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{MILESTONES_DIR_NAME}"),
        "phases_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}"),
        # Platform
        "platform": _detect_platform(cwd),
        **reference_runtime_context,
    }


def init_map_research(cwd: Path) -> dict:
    """Assemble context for research mapping."""
    config = load_config(cwd)

    # Check for existing research maps
    research_map_dir = cwd / PLANNING_DIR_NAME / RESEARCH_MAP_DIR_NAME
    existing_maps: list[str] = []
    try:
        existing_maps = sorted(f.name for f in research_map_dir.iterdir() if f.is_file() and f.name.endswith(".md"))
    except FileNotFoundError:
        pass

    result = {
        # Models
        "mapper_model": _resolve_model(cwd, "gpd-research-mapper", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "parallelization": config["parallelization"],
        # Paths
        "research_map_dir": f"{PLANNING_DIR_NAME}/{RESEARCH_MAP_DIR_NAME}",
        # Existing maps
        "existing_maps": existing_maps,
        "has_maps": len(existing_maps) > 0,
        # File existence
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        "research_map_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{RESEARCH_MAP_DIR_NAME}"),
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))
    return result


def init_progress(cwd: Path, includes: set[str] | None = None, *, data_root: Path | None = None) -> dict:
    """Assemble context for progress checking.

    Args:
        cwd: Project root directory.
        includes: Optional set of file sections to embed (state, roadmap, project, config).
    """
    includes = includes or set()
    requested_cwd = cwd.expanduser().resolve(strict=False)
    effective_cwd, reentry_metadata = _resolve_reentry_context(requested_cwd, data_root=data_root)
    config = load_config(effective_cwd)
    milestone = _try_get_milestone_info(effective_cwd)

    # Analyze phases
    layout = ProjectLayout(effective_cwd)
    phases_dir = layout.phases_dir
    phases: list[dict[str, object]] = []
    current_phase: dict[str, object] | None = None
    next_phase: dict[str, object] | None = None

    try:
        dirs = sorted(
            (d.name for d in phases_dir.iterdir() if d.is_dir()),
            key=_phase_sort_key,
        )
        for dir_name in dirs:
            dir_match = re.match(r"^(\d+(?:\.\d+)*)-?(.*)", dir_name)
            phase_number = dir_match.group(1) if dir_match else dir_name
            phase_name = dir_match.group(2) if dir_match and dir_match.group(2) else None

            phase_path = phases_dir / dir_name
            phase_files = [f.name for f in phase_path.iterdir() if f.is_file()]

            plans = [f for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
            summaries = [f for f in phase_files if layout.is_summary_file(f)]
            has_research = any(f.endswith(RESEARCH_SUFFIX) or f == STANDALONE_RESEARCH for f in phase_files)

            summary_count = _matching_phase_artifact_count(plans, summaries)

            if _is_phase_complete(len(plans), summary_count):
                status = "complete"
            elif plans:
                status = "in_progress"
            elif has_research:
                status = "researched"
            else:
                status = "pending"

            phase_entry: dict[str, object] = {
                "number": phase_number,
                "name": phase_name,
                "directory": f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}/{dir_name}",
                "status": status,
                "plan_count": len(plans),
                "summary_count": summary_count,
                "has_research": has_research,
            }
            phases.append(phase_entry)

            if current_phase is None and status in ("in_progress", "researched"):
                current_phase = phase_entry
            if next_phase is None and status == "pending":
                next_phase = phase_entry
    except FileNotFoundError:
        pass

    # Check for paused work
    paused_at: str | None = None
    state_content = _safe_read_file(effective_cwd / PLANNING_DIR_NAME / STATE_MD_FILENAME)
    if state_content:
        status_match = re.search(r"\*\*Status:\*\*\s*(.+)", state_content)
        if status_match and status_match.group(1).strip().lower() == "paused":
            stopped_match = re.search(r"\*\*Stopped at:\*\*\s*(.+)", state_content)
            paused_at = stopped_match.group(1).strip() if stopped_match else "true"

    result: dict[str, object] = {
        "workspace_root": reentry_metadata["workspace_root"],
        "project_root": reentry_metadata["project_root"],
        "project_root_source": reentry_metadata["project_root_source"],
        "project_root_auto_selected": reentry_metadata["project_root_auto_selected"],
        "project_reentry_mode": reentry_metadata["project_reentry_mode"],
        "project_reentry_requires_selection": reentry_metadata["project_reentry_requires_selection"],
        "project_reentry_selected_candidate": reentry_metadata.get("project_reentry_selected_candidate"),
        "project_reentry_candidates": reentry_metadata["project_reentry_candidates"],
        # Models
        "executor_model": _resolve_model(effective_cwd, "gpd-executor", config),
        "planner_model": _resolve_model(effective_cwd, "gpd-planner", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "review_cadence": config["review_cadence"],
        "research_mode": config["research_mode"],
        # Milestone
        "milestone_version": milestone["version"],
        "milestone_name": milestone["name"],
        # Phase overview
        "phases": phases,
        "phase_count": len(phases),
        "completed_count": sum(1 for p in phases if p["status"] == "complete"),
        "in_progress_count": sum(1 for p in phases if p["status"] == "in_progress"),
        # Current state
        "current_phase": current_phase,
        "next_phase": next_phase,
        "paused_at": paused_at,
        "has_work_in_progress": current_phase is not None,
        # File existence
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(effective_cwd),
        # Platform
        "platform": _detect_platform(effective_cwd),
    }
    result.update(_build_reference_runtime_context(effective_cwd))
    result.update(_build_state_memory_runtime_context(effective_cwd))
    result.update(_build_execution_runtime_context(effective_cwd))
    if result.get("execution_paused_at"):
        result["paused_at"] = result["execution_paused_at"]
    if result.get("current_execution") and result["current_phase"] is None:
        current_execution = result["current_execution"]
        if isinstance(current_execution, dict) and current_execution.get("phase"):
            result["current_phase"] = {
                "number": current_execution.get("phase"),
                "name": None,
                "directory": None,
                "status": "in_progress",
                "plan_count": None,
                "summary_count": None,
                "has_research": False,
            }
        result["has_work_in_progress"] = True

    # Include file contents
    planning = effective_cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
        result.update(_build_structured_state_runtime_context(effective_cwd))
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)
    if "project" in includes:
        result["project_content"] = _safe_read_file_truncated(planning / PROJECT_FILENAME)
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / CONFIG_FILENAME)

    return result
