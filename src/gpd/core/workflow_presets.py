"""Central workflow preset registry and doctor-facing readiness derivation.

Workflow presets are guidance over existing config knobs only. They do not
introduce any persisted schema; they package common settings and expose
doctor-backed readiness for the machine-local surface.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from gpd.core.config import apply_config_update, canonical_config_key, supported_config_keys

__all__ = [
    "WorkflowPreset",
    "apply_workflow_preset_config",
    "get_workflow_preset",
    "get_workflow_preset_config_bundle",
    "list_workflow_presets",
    "resolve_workflow_preset_readiness",
]

_GUIDANCE_ONLY_PRESET_KEYS = frozenset({"model_cost_posture"})


@dataclass(frozen=True, slots=True)
class WorkflowPreset:
    """A non-persisted guidance preset built from existing config knobs."""

    id: str
    label: str
    description: str
    summary: str
    recommended_config: dict[str, Any]
    required_checks: tuple[str, ...] = ()
    ready_workflows: tuple[str, ...] = ()
    degraded_workflows: tuple[str, ...] = ()
    blocked_workflows: tuple[str, ...] = ()
    requires_extra_tooling: bool = False


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


def _preset_actionable_config_bundle(preset: WorkflowPreset) -> dict[str, Any]:
    """Return a config-only bundle for one preset.

    The bundle is limited to keys that already exist in the config schema.
    Guidance-only values remain in ``recommended_config`` for callers that want
    to display them, but they are not returned here because they are not
    persisted config keys.
    """

    bundle: dict[str, Any] = {}
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


def get_workflow_preset_config_bundle(preset_id: str) -> dict[str, Any] | None:
    """Return the actionable config bundle for one preset.

    The returned bundle is a detached copy that can be merged into a raw
    ``config.json`` payload without mutating the preset registry or the input
    config object.
    """

    preset = get_workflow_preset(preset_id)
    if preset is None:
        return None
    return _preset_actionable_config_bundle(preset)


def apply_workflow_preset_config(raw_config: dict[str, object], preset_id: str) -> tuple[dict[str, object], str]:
    """Apply one preset bundle to a raw config payload atomically.

    The input payload is never mutated. The preset is expanded into the current
    config schema only, then validated once per key against the shared config
    model so callers can write the returned payload directly.
    """

    preset = get_workflow_preset(preset_id)
    if preset is None:
        supported = ", ".join(preset.id for preset in list_workflow_presets())
        raise ValueError(f"Unknown workflow preset {preset_id!r}. Supported: {supported}")

    updated = copy.deepcopy(raw_config)
    for key, value in _preset_actionable_config_bundle(preset).items():
        updated, _ = apply_config_update(updated, key, value)
    return updated, preset.id


def list_workflow_presets() -> tuple[WorkflowPreset, ...]:
    """Return the canonical workflow preset registry."""

    return WORKFLOW_PRESETS


def get_workflow_preset(preset_id: str) -> WorkflowPreset | None:
    """Resolve a workflow preset by identifier."""

    normalized = preset_id.strip().lower()
    if not normalized:
        return None
    return WORKFLOW_PRESET_INDEX.get(normalized)


def resolve_workflow_preset_readiness(*, base_ready: bool, latex_available: bool | None) -> dict[str, object]:
    """Return doctor-facing preset readiness derived from explicit tool checks."""

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
        elif preset.requires_extra_tooling and latex_available is False:
            status = "degraded"
            usable = True
            summary = "degraded without LaTeX: draft/review remain usable, but build/submission stay blocked"
            ready_workflows = []
            degraded_workflows = list(preset.degraded_workflows)
            blocked_workflows = list(preset.blocked_workflows)
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
            }
        )

    return {
        "total": len(entries),
        "ready": ready,
        "degraded": degraded,
        "blocked": blocked,
        "presets": entries,
    }
