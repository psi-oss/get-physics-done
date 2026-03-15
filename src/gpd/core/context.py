"""Context assembly for AI agent commands.

Each function gathers project state and produces a structured dict consumed by agent prompts.

Delegates to :mod:`gpd.core.config` for configuration loading and model-tier
resolution so that defaults and model profiles are defined in exactly one place.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from gpd.adapters import iter_adapters
from gpd.adapters.install_utils import AGENTS_DIR_NAME, FLAT_COMMANDS_DIR_NAME, GPD_INSTALL_DIR_NAME, HOOKS_DIR_NAME
from gpd.contracts import ResearchContract, contract_from_data
from gpd.core.config import GPDProjectConfig, resolve_agent_tier
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
    STANDALONE_SUMMARY,
    STANDALONE_VALIDATION,
    STANDALONE_VERIFICATION,
    STATE_MD_FILENAME,
    SUMMARY_SUFFIX,
    TODOS_DIR_NAME,
    VALIDATION_SUFFIX,
    VERIFICATION_SUFFIX,
)
from gpd.core.errors import ValidationError
from gpd.core.protocol_bundles import render_protocol_bundle_context, select_protocol_bundles
from gpd.core.reference_ingestion import ingest_reference_artifacts
from gpd.core.state import load_state_json as _load_state_json
from gpd.core.utils import (
    generate_slug as _generate_slug_impl,
)
from gpd.core.utils import is_phase_complete as _is_phase_complete
from gpd.core.utils import phase_normalize as _phase_normalize_impl
from gpd.core.utils import phase_sort_key as _phase_sort_key
from gpd.core.utils import safe_read_file as _safe_read_file
from gpd.core.utils import safe_read_file_truncated as _safe_read_file_truncated

logger = logging.getLogger(__name__)


# Research file extensions for project detection.
_RESEARCH_EXTENSIONS = frozenset({".tex", ".ipynb", ".py", ".jl", ".f90"})
_RUNTIME_CONFIG_DIRS = frozenset(adapter.local_config_dir_name for adapter in iter_adapters())
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

# Directories to skip when scanning for research files.
_IGNORE_DIRS = frozenset(
    {
        ".git",
        PLANNING_DIR_NAME,
        *_RUNTIME_CONFIG_DIRS,
        ".config",
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
    return _load_state_json(cwd) is not None


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



def _find_phase_artifact(phase_dir: Path, suffix: str, standalone: str) -> str | None:
    """Find file content matching a suffix pattern in a phase directory (truncated)."""
    if not phase_dir.is_dir():
        return None
    for f in sorted(phase_dir.iterdir()):
        if f.is_file() and (f.name.endswith(suffix) or f.name == standalone):
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


def _load_project_contract(cwd: Path) -> ResearchContract | None:
    """Load the canonical project contract from state.json when available."""
    state = _load_state_json(cwd)
    if not isinstance(state, dict):
        return None
    return contract_from_data(state.get("project_contract"))


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
) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    """Return active-reference lookup tables by ID and canonicalizable token."""
    by_id: dict[str, dict[str, object]] = {}
    token_to_id: dict[str, str] = {}
    for ref in active_references:
        ref_id = str(ref.get("id") or "").strip()
        locator = str(ref.get("locator") or "").strip()
        if ref_id:
            by_id[ref_id] = ref
            token_to_id.setdefault(ref_id.casefold(), ref_id)
        if ref_id and locator:
            token_to_id.setdefault(locator.casefold(), ref_id)
        for alias in ref.get("aliases", []):
            alias_text = str(alias).strip()
            if alias_text and ref_id:
                token_to_id.setdefault(alias_text.casefold(), ref_id)
    return by_id, token_to_id


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
    _, token_to_id = _build_active_reference_lookup(active_references)
    if contract is not None:
        intake = contract.context_intake.model_dump(mode="json")
        for key in merged:
            _append_unique_strings(merged[key], list(intake.get(key) or []))
    for key in merged:
        _append_unique_strings(merged[key], list(derived_intake.get(key) or []))
    canonical_must_read_refs: list[str] = []
    for token in merged["must_read_refs"]:
        resolved = token_to_id.get(token.casefold(), token)
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

    intake = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    contract_intake = contract.context_intake.model_dump(mode="json")
    for key in intake:
        _append_unique_strings(intake[key], list(contract_intake.get(key) or []))
        _append_unique_strings(intake[key], list(effective_reference_intake.get(key) or []))
    _, token_to_id = _build_active_reference_lookup(active_references)
    canonical_must_read_refs: list[str] = []
    for token in list(intake.get("must_read_refs") or []):
        resolved = token_to_id.get(str(token).casefold(), str(token))
        _append_unique_strings(canonical_must_read_refs, [resolved])
    intake["must_read_refs"] = canonical_must_read_refs
    return intake


def _canonicalize_project_contract(
    contract: ResearchContract | None,
    *,
    active_references: list[dict[str, object]],
    effective_reference_intake: dict[str, list[str]],
) -> ResearchContract | None:
    """Return the canonical contract after merging durable anchor context."""

    if contract is None:
        return None

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
    seen_ids: set[str] = set()
    seen_locators: set[str] = set()
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
        if ref_id:
            seen_ids.add(ref_id)
        if locator_key:
            seen_locators.add(locator_key)
    for derived in canonical_refs:
        ref_id = str(derived.get("id") or "").strip()
        locator_key = str(derived.get("locator") or "").strip().casefold()
        if ref_id in seen_ids or (locator_key and locator_key in seen_locators):
            continue
        merged_references.append(derived)
    payload["references"] = merged_references
    try:
        return ResearchContract.model_validate(payload)
    except Exception:
        return contract


def _render_active_reference_context(
    active_references: list[dict[str, object]],
    effective_intake: dict[str, list[str]],
    literature_review_files: list[str],
    research_map_reference_files: list[str],
) -> str:
    """Render a compact text block of anchors and carry-forward inputs."""
    lines: list[str] = ["## Active Reference Registry"]
    refs_by_id, _ = _build_active_reference_lookup(active_references)

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
    contract = _load_project_contract(cwd)
    artifact_payload = _reference_artifact_payload(cwd)
    artifact_ingestion = ingest_reference_artifacts(
        cwd,
        literature_review_files=list(artifact_payload["literature_review_files"]),
        research_map_reference_files=list(artifact_payload["research_map_reference_files"]),
    )
    derived_references = [ref.to_context_dict() for ref in artifact_ingestion.references]
    active_references = _merge_active_references(_serialize_active_references(contract), derived_references)
    effective_reference_intake = _merge_reference_intake(
        contract,
        artifact_ingestion.intake.to_dict(),
        active_references,
    )
    canonical_contract = _canonicalize_project_contract(
        contract,
        active_references=active_references,
        effective_reference_intake=effective_reference_intake,
    )
    project_text = _safe_read_file(cwd / PLANNING_DIR_NAME / PROJECT_FILENAME)
    selected_protocol_bundles = select_protocol_bundles(project_text, canonical_contract)

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
        "project_contract": canonical_contract.model_dump(mode="json") if canonical_contract is not None else None,
        "contract_intake": canonical_contract.context_intake.model_dump(mode="json") if canonical_contract is not None else None,
        "effective_reference_intake": effective_reference_intake,
        "derived_active_references": derived_references,
        "derived_active_reference_count": len(derived_references),
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
        ),
        **artifact_payload,
    }


def _build_execution_runtime_context(cwd: Path) -> dict[str, object]:
    """Build shared live execution-state context for orchestration surfaces."""
    from gpd.core.observability import get_current_execution

    snapshot = get_current_execution(cwd)
    state = _load_state_json(cwd)
    position = state.get("position") if isinstance(state, dict) else {}
    session = state.get("session") if isinstance(state, dict) else {}

    paused_states = {"paused", "awaiting_user", "ready_to_continue", "waiting_review", "blocked"}
    segment_status = (snapshot.segment_status or "").lower() if snapshot is not None else ""
    is_resumable = bool(snapshot and segment_status in paused_states)
    paused_at = (
        snapshot.updated_at
        if snapshot is not None and segment_status in paused_states
        else (position.get("paused_at") if isinstance(position, dict) else None)
    )
    resume_file = (
        snapshot.resume_file
        if snapshot is not None and snapshot.resume_file
        else (session.get("resume_file") if isinstance(session, dict) else None)
    )

    return {
        "current_execution": snapshot.model_dump(mode="json") if snapshot is not None else None,
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
        "execution_resume_file": resume_file,
    }


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
        "checkpoint_after_n_tasks": cfg.checkpoint_after_n_tasks,
        "checkpoint_after_first_load_bearing_result": cfg.checkpoint_after_first_load_bearing_result,
        "checkpoint_before_downstream_dependent_tasks": cfg.checkpoint_before_downstream_dependent_tasks,
    }
    if cfg.model_overrides:
        d["model_overrides"] = cfg.model_overrides
    return d


def load_config(cwd: Path) -> dict:
    """Load .gpd/config.json with defaults.

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
            from gpd.hooks.runtime_detect import detect_runtime_for_gpd_use

            active_runtime = detect_runtime_for_gpd_use(cwd=cwd)
        except Exception:
            active_runtime = _detect_platform(cwd)
    if active_runtime == "unknown":
        active_runtime = None

    if config is None:
        return _resolve_model_canonical(cwd, agent_type, runtime=active_runtime)

    if not active_runtime:
        return None

    profile = config.get("model_profile", str(GPDProjectConfig.model_fields["model_profile"].default.value))
    tier = resolve_agent_tier(agent_type, profile).value
    runtime_overrides = config.get("model_overrides")
    if not isinstance(runtime_overrides, dict):
        return None
    runtime_map = runtime_overrides.get(active_runtime)
    if not isinstance(runtime_map, dict):
        return None
    value = runtime_map.get(tier)
    return value if isinstance(value, str) and value else None


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
    try:
        from gpd.hooks.runtime_detect import detect_runtime_for_gpd_use

        return detect_runtime_for_gpd_use(cwd=cwd)
    except Exception:
        return "unknown"


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
    result.update(_build_execution_runtime_context(cwd))

    # Include file contents if requested
    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
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

    # Include file contents
    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
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
        result["verification_content"] = _find_phase_artifact(phase_dir, VERIFICATION_SUFFIX, STANDALONE_VERIFICATION)
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
            if entry.name in _IGNORE_DIRS:
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
    return result


def init_resume(cwd: Path) -> dict:
    """Assemble context for resuming work."""
    config = load_config(cwd)
    execution_context = _build_execution_runtime_context(cwd)

    # Check for interrupted agent
    interrupted_agent_id = None
    agent_id_file = cwd / PLANNING_DIR_NAME / AGENT_ID_FILENAME
    try:
        interrupted_agent_id = agent_id_file.read_text(encoding="utf-8").strip() or None
    except (FileNotFoundError, OSError):
        pass

    segment_candidates: list[dict[str, object]] = []
    current_execution = execution_context.get("current_execution")
    if execution_context.get("execution_resumable") and isinstance(current_execution, dict):
        segment_candidates.append(
            {
                "source": "current_execution",
                "status": current_execution.get("segment_status"),
                "phase": current_execution.get("phase"),
                "plan": current_execution.get("plan"),
                "segment_id": current_execution.get("segment_id"),
                "resume_file": current_execution.get("resume_file"),
                "checkpoint_reason": current_execution.get("checkpoint_reason"),
                "first_result_gate_pending": current_execution.get("first_result_gate_pending"),
                "pre_fanout_review_pending": current_execution.get("pre_fanout_review_pending"),
                "pre_fanout_review_cleared": current_execution.get("pre_fanout_review_cleared"),
                "skeptical_requestioning_required": current_execution.get("skeptical_requestioning_required"),
                "skeptical_requestioning_summary": current_execution.get("skeptical_requestioning_summary"),
                "weakest_unchecked_anchor": current_execution.get("weakest_unchecked_anchor"),
                "disconfirming_observation": current_execution.get("disconfirming_observation"),
                "downstream_locked": current_execution.get("downstream_locked"),
                "waiting_reason": current_execution.get("waiting_reason"),
                "blocked_reason": current_execution.get("blocked_reason"),
                "last_result_label": current_execution.get("last_result_label"),
                "updated_at": current_execution.get("updated_at"),
            }
        )
    if interrupted_agent_id is not None:
        segment_candidates.append(
            {
                "source": "interrupted_agent",
                "status": "interrupted",
                "agent_id": interrupted_agent_id,
            }
        )
    if execution_context.get("execution_resumable") and isinstance(current_execution, dict):
        resume_mode = "bounded_segment"
    elif interrupted_agent_id is not None:
        resume_mode = "interrupted_agent"
    else:
        resume_mode = None

    result = {
        # File existence
        "state_exists": _state_exists(cwd),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        # Agent state
        "has_interrupted_agent": interrupted_agent_id is not None,
        "interrupted_agent_id": interrupted_agent_id,
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "review_cadence": config["review_cadence"],
        "research_mode": config["research_mode"],
        "active_execution_segment": current_execution,
        "segment_candidates": segment_candidates,
        "resume_mode": resume_mode,
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))
    result.update(execution_context)
    return result


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
    result.update(_build_execution_runtime_context(cwd))

    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
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

    # Count phases
    phases_dir = cwd / PLANNING_DIR_NAME / PHASES_DIR_NAME
    phase_count = 0
    completed_phases = 0
    try:
        for d in sorted(phases_dir.iterdir()):
            if not d.is_dir():
                continue
            phase_count += 1
            phase_files = [f.name for f in d.iterdir() if f.is_file()]
            plans = [f for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
            summaries = [f for f in phase_files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY]
            if _is_phase_complete(len(plans), len(summaries)):
                completed_phases += 1
    except FileNotFoundError:
        pass

    # Check archived milestones
    milestones_dir = cwd / PLANNING_DIR_NAME / MILESTONES_DIR_NAME
    archived_milestones: list[str] = []
    try:
        archived_milestones = sorted(d.name for d in milestones_dir.iterdir() if d.is_dir())
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
        "phase_count": phase_count,
        "completed_phases": completed_phases,
        "all_phases_complete": phase_count > 0 and phase_count == completed_phases,
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


def init_progress(cwd: Path, includes: set[str] | None = None) -> dict:
    """Assemble context for progress checking.

    Args:
        cwd: Project root directory.
        includes: Optional set of file sections to embed (state, roadmap, project, config).
    """
    includes = includes or set()
    config = load_config(cwd)
    milestone = _try_get_milestone_info(cwd)

    # Analyze phases
    phases_dir = cwd / PLANNING_DIR_NAME / PHASES_DIR_NAME
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
            summaries = [f for f in phase_files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY]
            has_research = any(f.endswith(RESEARCH_SUFFIX) or f == STANDALONE_RESEARCH for f in phase_files)

            if _is_phase_complete(len(plans), len(summaries)):
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
                "summary_count": len(summaries),
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
    state_content = _safe_read_file(cwd / PLANNING_DIR_NAME / STATE_MD_FILENAME)
    if state_content:
        status_match = re.search(r"\*\*Status:\*\*\s*(.+)", state_content)
        if status_match and status_match.group(1).strip().lower() == "paused":
            stopped_match = re.search(r"\*\*Stopped at:\*\*\s*(.+)", state_content)
            paused_at = stopped_match.group(1).strip() if stopped_match else "true"

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
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
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(cwd),
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))
    result.update(_build_execution_runtime_context(cwd))
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
    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)
    if "project" in includes:
        result["project_content"] = _safe_read_file_truncated(planning / PROJECT_FILENAME)
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / CONFIG_FILENAME)

    return result
