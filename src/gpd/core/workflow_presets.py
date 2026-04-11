"""Central workflow preset registry and doctor-facing readiness derivation.

Workflow presets are guidance over existing config knobs only. They do not
introduce any persisted schema; they package common settings and expose
doctor-backed readiness for the machine-local surface.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass

from gpd.core.config import (
    apply_config_update,
    canonical_config_key,
    effective_raw_config_value,
    supported_config_keys,
)
from gpd.core.small_utils import strict_bool_value as _strict_bool_value

__all__ = [
    "WorkflowPresetApplicationPreview",
    "WorkflowPresetConfigChange",
    "WorkflowPreset",
    "apply_workflow_preset_config",
    "get_workflow_preset",
    "get_workflow_preset_config_bundle",
    "list_workflow_presets",
    "preview_workflow_preset_application",
    "resolve_workflow_preset_readiness",
]

_GUIDANCE_ONLY_PRESET_KEYS = frozenset({"model_cost_posture"})
_LATEX_CAPABILITY_DEFAULTS: dict[str, object] = {
    "compiler": "pdflatex",
    "available": False,
    "compiler_available": False,
    "full_toolchain_available": False,
    "compiler_path": None,
    "distribution": None,
    "bibtex_available": None,
    "bibliography_support_available": False,
    "latexmk_available": None,
    "kpsewhich_available": None,
    "readiness_state": "blocked",
    "message": "",
    "warnings": [],
    "paper_build_ready": False,
    "arxiv_submission_ready": False,
}


@dataclass(frozen=True, slots=True)
class WorkflowPresetConfigChange:
    """A single key-level change applied by a workflow preset."""

    key: str
    before: object
    after: object


@dataclass(frozen=True, slots=True)
class WorkflowPresetApplicationPreview:
    """Shared preview/apply contract for one workflow preset."""

    preset_id: str
    label: str
    applied_keys: tuple[str, ...]
    ignored_guidance_only_keys: tuple[str, ...]
    changes: tuple[WorkflowPresetConfigChange, ...]
    unchanged_keys: tuple[str, ...]
    updated_config: dict[str, object]

    @property
    def changed_keys(self) -> tuple[str, ...]:
        """Return the keys whose effective values change under this preset."""

        return tuple(change.key for change in self.changes)


@dataclass(frozen=True, slots=True)
class WorkflowPreset:
    """A non-persisted guidance preset built from existing config knobs."""

    id: str
    label: str
    description: str
    summary: str
    recommended_config: dict[str, object]
    required_checks: tuple[str, ...] = ()
    ready_workflows: tuple[str, ...] = ()
    degraded_workflows: tuple[str, ...] = ()
    blocked_workflows: tuple[str, ...] = ()
    requires_extra_tooling: bool = False


def _capability_value(source: object, *keys: str) -> object | None:
    """Return the first non-``None`` capability field value from a mapping or object."""

    if isinstance(source, Mapping):
        for key in keys:
            if key in source:
                value = source[key]
                if value is not None:
                    return value
        return None
    for key in keys:
        if hasattr(source, key):
            value = getattr(source, key)
            if value is not None:
                return value
    return None


def _normalize_latex_capability(
    latex_capability: object | None = None,
) -> dict[str, object]:
    """Normalize structured LaTeX capability payloads into one contract."""

    if latex_capability is None:
        return {**_LATEX_CAPABILITY_DEFAULTS, "warnings": []}

    compiler_name = _capability_value(latex_capability, "compiler")
    if not isinstance(compiler_name, str) or not compiler_name.strip():
        compiler_name = "pdflatex"

    compiler_value = _capability_value(latex_capability, "compiler_available", "available")
    compiler_available = _strict_bool_value(compiler_value)
    if compiler_available is None:
        compiler_available = False

    bibtex_value = _capability_value(latex_capability, "bibtex_available", "bibtex", "bibliography_available")
    bibtex_available = _strict_bool_value(bibtex_value)

    latexmk_value = _capability_value(latex_capability, "latexmk_available", "latexmk")
    kpsewhich_value = _capability_value(latex_capability, "kpsewhich_available", "kpsewhich")
    full_toolchain_value = _capability_value(latex_capability, "full_toolchain_available", "full_toolchain_ready")
    full_toolchain_available = _strict_bool_value(full_toolchain_value)
    compiler_path = _capability_value(latex_capability, "compiler_path")
    distribution = _capability_value(latex_capability, "distribution")
    readiness_value = _capability_value(latex_capability, "readiness_state")
    message_value = _capability_value(latex_capability, "message")
    warnings_value = _capability_value(latex_capability, "warnings")
    if isinstance(warnings_value, str):
        warnings = [warnings_value]
    elif isinstance(warnings_value, (list, tuple)):
        warnings = list(warnings_value)
    else:
        warnings = []

    bibtex_ready = bibtex_available is True
    bibliography_support_available = compiler_available and bibtex_ready
    paper_build_ready = compiler_available
    arxiv_submission_ready = bibliography_support_available and kpsewhich_value is True
    if isinstance(readiness_value, str) and readiness_value in {"blocked", "degraded", "ready"}:
        readiness_state = readiness_value
    elif not compiler_available:
        readiness_state = "blocked"
    elif bibtex_ready:
        readiness_state = "ready"
    else:
        readiness_state = "degraded"

    if isinstance(message_value, str) and message_value.strip():
        message = message_value
    elif not compiler_available:
        message = f"No LaTeX compiler found for `{compiler_name}`."
    elif bibtex_ready:
        message = f"{compiler_name} found."
    else:
        message = f"{compiler_name} found, but BibTeX support is unavailable."

    normalized = {
        "compiler": compiler_name,
        "available": compiler_available,
        "compiler_available": compiler_available,
        "full_toolchain_available": (
            full_toolchain_available
            if full_toolchain_available is not None
            else compiler_available and bibtex_ready and latexmk_value is True and kpsewhich_value is True
        ),
        "compiler_path": compiler_path,
        "distribution": distribution,
        "bibtex_available": bibtex_available,
        "bibliography_support_available": bibliography_support_available,
        "latexmk_available": _strict_bool_value(latexmk_value),
        "kpsewhich_available": _strict_bool_value(kpsewhich_value),
        "readiness_state": readiness_state,
        "message": message,
        "warnings": warnings,
        "paper_build_ready": paper_build_ready,
        "arxiv_submission_ready": arxiv_submission_ready,
    }
    return normalized


WORKFLOW_PRESETS: tuple[WorkflowPreset, ...] = (
    WorkflowPreset(
        id="core-research",
        label="Core research",
        description="Best default for most physics projects. Uses only the base runtime-readiness contract.",
        summary="Balanced default workflow for planning, execution, and verification.",
        recommended_config={
            "autonomy": "balanced",
            "research_mode": "balanced",
            "model_profile": "review",
            "model_cost_posture": "balanced",
            "execution.review_cadence": "adaptive",
            "parallelization": True,
            "planning.commit_docs": True,
            "workflow.research": True,
            "workflow.plan_checker": True,
            "workflow.verifier": True,
        },
    ),
    WorkflowPreset(
        id="theory",
        label="Theory",
        description="Bias toward rigorous derivations and exact reasoning without claiming extra machine-tooling requirements.",
        summary="Derivation-heavy workflow using the base runtime-readiness contract only.",
        recommended_config={
            "autonomy": "balanced",
            "research_mode": "adaptive",
            "model_profile": "deep-theory",
            "model_cost_posture": "max-quality",
            "execution.review_cadence": "dense",
            "parallelization": True,
            "planning.commit_docs": True,
            "workflow.research": True,
            "workflow.plan_checker": True,
            "workflow.verifier": True,
        },
    ),
    WorkflowPreset(
        id="numerics",
        label="Numerics",
        description="Bias toward computational implementation and convergence work without claiming extra machine-tooling requirements beyond the base runtime.",
        summary="Computation-heavy workflow using the base runtime-readiness contract only.",
        recommended_config={
            "autonomy": "balanced",
            "research_mode": "balanced",
            "model_profile": "numerical",
            "model_cost_posture": "balanced",
            "execution.review_cadence": "adaptive",
            "parallelization": True,
            "planning.commit_docs": True,
            "workflow.research": True,
            "workflow.plan_checker": True,
            "workflow.verifier": True,
        },
    ),
    WorkflowPreset(
        id="publication-manuscript",
        label="Publication / manuscript",
        description="Drafting, review, build, and submission workflow for paper production.",
        summary="Paper-writing workflow; build and submission depend on LaTeX readiness.",
        recommended_config={
            "autonomy": "balanced",
            "research_mode": "exploit",
            "model_profile": "paper-writing",
            "model_cost_posture": "balanced",
            "execution.review_cadence": "dense",
            "parallelization": False,
            "planning.commit_docs": True,
            "workflow.research": True,
            "workflow.plan_checker": True,
            "workflow.verifier": True,
        },
        required_checks=("LaTeX Toolchain",),
        ready_workflows=("write-paper", "peer-review", "paper-build", "arxiv-submission"),
        degraded_workflows=("write-paper", "peer-review"),
        blocked_workflows=("paper-build", "arxiv-submission"),
        requires_extra_tooling=True,
    ),
    WorkflowPreset(
        id="full-research",
        label="Full research",
        description="Core research defaults plus publication/manuscript readiness awareness for projects expected to end in a paper.",
        summary="Core research workflow with publication readiness tracked alongside it.",
        recommended_config={
            "autonomy": "balanced",
            "research_mode": "adaptive",
            "model_profile": "review",
            "model_cost_posture": "balanced",
            "execution.review_cadence": "adaptive",
            "parallelization": True,
            "planning.commit_docs": True,
            "workflow.research": True,
            "workflow.plan_checker": True,
            "workflow.verifier": True,
        },
        required_checks=("LaTeX Toolchain",),
        ready_workflows=("write-paper", "peer-review", "paper-build", "arxiv-submission"),
        degraded_workflows=("write-paper", "peer-review"),
        blocked_workflows=("paper-build", "arxiv-submission"),
        requires_extra_tooling=True,
    ),
)

WORKFLOW_PRESET_INDEX: dict[str, WorkflowPreset] = {preset.id: preset for preset in WORKFLOW_PRESETS}


def _preset_actionable_config_bundle(preset: WorkflowPreset) -> dict[str, object]:
    """Return a config-only bundle for one preset.

    The bundle is limited to keys that already exist in the config schema.
    Guidance-only values remain in ``recommended_config`` for callers that want
    to display them, but they are not returned here because they are not
    persisted config keys.
    """

    bundle: dict[str, object] = {}
    supported_keys = set(supported_config_keys())
    for key, value in preset.recommended_config.items():
        if key in _GUIDANCE_ONLY_PRESET_KEYS:
            continue
        if canonical_config_key(key) is None or key not in supported_keys:
            supported = ", ".join(sorted(supported_keys))
            raise ValueError(
                f"Workflow preset {preset.id!r} contains unsupported config key {key!r}; "
                f"expected one of: {supported}"
            )
        bundle[key] = copy.deepcopy(value)
    return bundle


def _preset_effective_value(raw_config: dict[str, object], key: str) -> object:
    """Return the effective config value for one preset-controlled key."""

    found, value = effective_raw_config_value(raw_config, key)
    if not found:
        msg = f"Unsupported preset preview key {key!r}"
        raise ValueError(msg)
    return copy.deepcopy(value)


def get_workflow_preset_config_bundle(preset_id: str) -> dict[str, object] | None:
    """Return the actionable config bundle for one preset.

    The returned bundle is a detached copy that can be merged into a raw
    ``config.json`` payload without mutating the preset registry or the input
    config object.
    """

    preset = get_workflow_preset(preset_id)
    if preset is None:
        return None
    return _preset_actionable_config_bundle(preset)


def preview_workflow_preset_application(
    raw_config: dict[str, object],
    preset_id: str,
) -> WorkflowPresetApplicationPreview:
    """Preview one preset bundle against a raw config payload.

    The input payload is never mutated. The preset is expanded into the current
    config schema only, then validated once per key against the shared config
    model so callers can inspect the final payload or write it directly.
    """

    preset = get_workflow_preset(preset_id)
    if preset is None:
        supported = ", ".join(preset.id for preset in list_workflow_presets())
        raise ValueError(f"Unknown workflow preset {preset_id!r}. Supported: {supported}")

    supported_keys = set(supported_config_keys())
    updated = copy.deepcopy(raw_config)
    applied_keys: list[str] = []
    ignored_guidance_only_keys: list[str] = []
    changes: list[WorkflowPresetConfigChange] = []
    unchanged_keys: list[str] = []

    for key, value in preset.recommended_config.items():
        if key in _GUIDANCE_ONLY_PRESET_KEYS:
            ignored_guidance_only_keys.append(key)
            continue
        if canonical_config_key(key) is None or key not in supported_keys:
            supported = ", ".join(sorted(supported_keys))
            raise ValueError(
                f"Workflow preset {preset.id!r} contains unsupported config key {key!r}; "
                f"expected one of: {supported}"
            )

        before = _preset_effective_value(raw_config, key)
        updated, _ = apply_config_update(updated, key, value)
        after = _preset_effective_value(updated, key)
        applied_keys.append(key)
        if before == after:
            unchanged_keys.append(key)
        else:
            changes.append(
                WorkflowPresetConfigChange(
                    key=key,
                    before=before,
                    after=after,
                )
            )

    return WorkflowPresetApplicationPreview(
        preset_id=preset.id,
        label=preset.label,
        applied_keys=tuple(applied_keys),
        ignored_guidance_only_keys=tuple(ignored_guidance_only_keys),
        changes=tuple(changes),
        unchanged_keys=tuple(unchanged_keys),
        updated_config=updated,
    )


def apply_workflow_preset_config(raw_config: dict[str, object], preset_id: str) -> tuple[dict[str, object], str]:
    """Apply one preset bundle to a raw config payload atomically."""

    result = preview_workflow_preset_application(raw_config, preset_id)
    return result.updated_config, result.preset_id


def list_workflow_presets() -> tuple[WorkflowPreset, ...]:
    """Return the canonical workflow preset registry."""

    return WORKFLOW_PRESETS


def get_workflow_preset(preset_id: str) -> WorkflowPreset | None:
    """Resolve a workflow preset by identifier."""

    normalized = preset_id.strip().lower()
    if not normalized:
        return None
    return WORKFLOW_PRESET_INDEX.get(normalized)


def resolve_workflow_preset_readiness(
    *,
    base_ready: bool,
    latex_capability: object | None = None,
) -> dict[str, object]:
    """Return doctor-facing preset readiness derived from explicit tool checks."""

    capability = _normalize_latex_capability(latex_capability)
    compiler_ready = capability["compiler_available"] is True
    bibliography_support_ready = capability.get("bibliography_support_available") is True
    latexmk_available = capability.get("latexmk_available")
    kpsewhich_available = capability.get("kpsewhich_available")
    paper_build_ready = capability["paper_build_ready"] is True
    arxiv_submission_ready = capability["arxiv_submission_ready"] is True

    entries: list[dict[str, object]] = []
    ready = 0
    degraded = 0
    blocked = 0

    for preset in WORKFLOW_PRESETS:
        depends_on = list(preset.required_checks)
        if not base_ready:
            status = "blocked"
            usable = False
            summary = "blocked until base runtime-readiness issues are fixed"
            ready_workflows: list[str] = []
            degraded_workflows: list[str] = []
            blocked_workflows = list(preset.blocked_workflows or preset.ready_workflows)
            depends_on = ["Base runtime readiness", *depends_on]
        elif preset.requires_extra_tooling and not paper_build_ready:
            status = "degraded"
            usable = True
            summary = "degraded without a LaTeX compiler: draft/review remain usable, but build/submission stay blocked"
            ready_workflows = []
            degraded_workflows = list(preset.degraded_workflows)
            blocked_workflows = list(preset.blocked_workflows)
        elif preset.requires_extra_tooling and not bibliography_support_ready:
            status = "degraded"
            usable = True
            summary = (
                "degraded without bibliography tooling: draft/review remain usable, while paper-build and "
                "arxiv-submission may fail for manuscripts that require bibliography processing"
            )
            ready_workflows = list(preset.degraded_workflows)
            degraded_workflows = ["paper-build", "arxiv-submission"]
            blocked_workflows = []
        elif preset.requires_extra_tooling and not arxiv_submission_ready:
            status = "degraded"
            usable = True
            summary = "degraded without arxiv-submission support: paper-build remains usable, but arxiv-submission stays blocked"
            ready_workflows = [workflow for workflow in preset.ready_workflows if workflow != "arxiv-submission"]
            degraded_workflows = []
            blocked_workflows = ["arxiv-submission"]
        else:
            status = "ready"
            usable = True
            summary = "ready"
            ready_workflows = list(preset.ready_workflows)
            degraded_workflows = []
            blocked_workflows = []

        if status == "ready":
            ready += 1
        elif status == "degraded":
            degraded += 1
        else:
            blocked += 1

        warnings: list[str] = []
        if preset.requires_extra_tooling:
            if not compiler_ready:
                warnings.append(
                    "No LaTeX compiler detected: draft/review workflows remain usable, but build/submission stay blocked."
                )
            elif not bibliography_support_ready:
                warnings.append(
                    "BibTeX support is missing: bibliography-free manuscripts may still build, but citation-bearing builds and submission prep can fail outright."
                )
            elif not arxiv_submission_ready:
                warnings.append(
                    "kpsewhich is missing: paper-build remains usable, but arxiv-submission stays blocked."
                )
            if latexmk_available is False:
                warnings.append("latexmk is missing: paper builds will fall back to manual multipass compilation.")
            if kpsewhich_available is False:
                warnings.append("kpsewhich is missing: TeX resource checks are best-effort only.")

        entries.append(
            {
                "id": preset.id,
                "label": preset.label,
                "status": status,
                "usable": usable,
                "description": preset.description,
                "summary": summary,
                "requires_extra_tooling": preset.requires_extra_tooling,
                "depends_on": depends_on,
                "recommended_config": dict(preset.recommended_config),
                "ready_workflows": ready_workflows,
                "degraded_workflows": degraded_workflows,
                "blocked_workflows": blocked_workflows,
                "warnings": warnings,
                "latex_capability": dict(capability),
            }
        )

    return {
        "total": len(entries),
        "ready": ready,
        "degraded": degraded,
        "blocked": blocked,
        "latex_capability": dict(capability),
        "presets": entries,
    }
