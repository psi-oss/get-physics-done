"""GPD configuration loading and model tier system.

Layer 1 code: stdlib + pydantic only.
"""

from __future__ import annotations

import copy
import json
import subprocess
from collections.abc import Callable
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from gpd.adapters.runtime_catalog import normalize_runtime_name
from gpd.core.constants import PLANNING_DIR_NAME, ProjectLayout
from gpd.core.errors import ConfigError
from gpd.core.observability import instrument_gpd_function

__all__ = [
    "AGENT_DEFAULT_TIERS",
    "ConfigError",
    "MODEL_PROFILES",
    "AutonomyMode",
    "BranchingStrategy",
    "ExecutionPreferences",
    "GPDProjectConfig",
    "ModelProfile",
    "ModelTier",
    "ReviewCadence",
    "ResearchMode",
    "canonical_config_key",
    "effective_config_value",
    "load_config",
    "resolve_agent_tier",
    "resolve_tier",
    "resolve_model",
    "supported_config_keys",
    "validate_agent_name",
]

# ─── Enums ──────────────────────────────────────────────────────────────────────


class AutonomyMode(StrEnum):
    """How much human oversight the system requires."""

    SUPERVISED = "supervised"
    BALANCED = "balanced"
    YOLO = "yolo"


class ReviewCadence(StrEnum):
    """How aggressively long-running execution injects review boundaries."""

    DENSE = "dense"
    ADAPTIVE = "adaptive"
    SPARSE = "sparse"


class ResearchMode(StrEnum):
    """Exploration vs exploitation tradeoff."""

    EXPLORE = "explore"
    BALANCED = "balanced"
    EXPLOIT = "exploit"
    ADAPTIVE = "adaptive"


class ModelProfile(StrEnum):
    """Research profile controlling model tier assignments."""

    DEEP_THEORY = "deep-theory"
    NUMERICAL = "numerical"
    EXPLORATORY = "exploratory"
    REVIEW = "review"
    PAPER_WRITING = "paper-writing"


class ModelTier(StrEnum):
    """Capability tier for model selection."""

    TIER_1 = "tier-1"
    TIER_2 = "tier-2"
    TIER_3 = "tier-3"


_VALID_MODEL_TIER_VALUES = frozenset(tier.value for tier in ModelTier)


@lru_cache(maxsize=1)
def _valid_runtime_names() -> frozenset[str]:
    from gpd.adapters.runtime_catalog import list_runtime_names

    try:
        return frozenset(list_runtime_names())
    except Exception as exc:
        raise RuntimeError("Unable to resolve supported runtimes") from exc


class BranchingStrategy(StrEnum):
    """Git branching strategy for phases."""

    NONE = "none"
    PER_PHASE = "per-phase"
    PER_MILESTONE = "per-milestone"


# ─── Model Profiles ─────────────────────────────────────────────────────────────

# Maps agent_name -> profile -> tier. Matches model-profiles.md reference exactly.
MODEL_PROFILES: dict[str, dict[str, ModelTier]] = {
    "gpd-planner": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-roadmapper": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-executor": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-phase-researcher": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-project-researcher": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_3,
    },
    "gpd-research-synthesizer": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-debugger": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-research-mapper": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_3,
        "exploratory": ModelTier.TIER_3,
        "review": ModelTier.TIER_3,
        "paper-writing": ModelTier.TIER_3,
    },
    "gpd-verifier": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-plan-checker": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-consistency-checker": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-paper-writer": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-literature-reviewer": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-bibliographer": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_3,
        "exploratory": ModelTier.TIER_3,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-explainer": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-review-reader": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-review-literature": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-review-math": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-check-proof": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-review-physics": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-review-significance": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-referee": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-experiment-designer": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_3,
    },
    "gpd-notation-coordinator": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_3,
        "exploratory": ModelTier.TIER_3,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_2,
    },
}

_MODEL_PROFILE_KEYS = frozenset(profile.value for profile in ModelProfile)


def _validate_model_profile_matrix() -> None:
    """Fail closed when an agent/profile tier mapping drifts."""
    for agent_name, profile_map in MODEL_PROFILES.items():
        missing = sorted(_MODEL_PROFILE_KEYS - set(profile_map))
        unknown = sorted(set(profile_map) - _MODEL_PROFILE_KEYS)
        if missing or unknown:
            parts: list[str] = []
            if missing:
                parts.append(f"missing profile(s): {', '.join(missing)}")
            if unknown:
                parts.append(f"unknown profile(s): {', '.join(unknown)}")
            raise ConfigError(f"MODEL_PROFILES[{agent_name!r}] is incomplete: {'; '.join(parts)}")
        for profile_name, tier in profile_map.items():
            if not isinstance(tier, ModelTier):
                raise ConfigError(f"MODEL_PROFILES[{agent_name!r}][{profile_name!r}] must be a ModelTier")


# Profile-independent view for public callers; resolution itself uses the full matrix.
AGENT_DEFAULT_TIERS: dict[str, ModelTier] = {
    agent_name: profile_map[ModelProfile.REVIEW.value]
    for agent_name, profile_map in MODEL_PROFILES.items()
}

# ─── Config Model ───────────────────────────────────────────────────────────────


class ExecutionPreferences(BaseModel):
    """Execution-surface preferences that override automatic orchestration.

    When ``strict_wait`` is true, the harness will not auto-interrupt workers
    at the ``max_unattended_minutes_*`` timeouts and will not return early
    ``status: checkpoint`` just to free user context — workers are allowed to
    run to natural completion. ``never_interrupt_running_workers`` and
    ``never_auto_close_child_agents`` are narrower knobs for callers who want
    only one of those guarantees.
    """

    strict_wait: bool = False
    never_interrupt_running_workers: bool = False
    never_auto_close_child_agents: bool = False


class GPDProjectConfig(BaseModel):
    """Configuration for a GPD project, loaded from GPD/config.json.

    Named GPDProjectConfig to distinguish it from other shared project
    contracts. This model controls project-level workflow settings
    (model profile, autonomy, git strategy, etc.).
    """

    model_profile: ModelProfile = ModelProfile.REVIEW
    autonomy: AutonomyMode = AutonomyMode.BALANCED
    review_cadence: ReviewCadence = ReviewCadence.ADAPTIVE
    research_mode: ResearchMode = ResearchMode.BALANCED

    # Workflow toggles
    commit_docs: bool = True
    research: bool = True
    plan_checker: bool = True
    verifier: bool = True
    parallelization: bool = True
    max_unattended_minutes_per_plan: int = Field(default=45, ge=1)
    max_unattended_minutes_per_wave: int = Field(default=90, ge=1)
    checkpoint_after_n_tasks: int = Field(default=3, ge=1)
    checkpoint_after_first_load_bearing_result: bool = True
    checkpoint_before_downstream_dependent_tasks: bool = True
    project_usd_budget: float | None = Field(default=None, gt=0)
    session_usd_budget: float | None = Field(default=None, gt=0)

    # Execution preferences (wait/interrupt semantics).
    execution_preferences: ExecutionPreferences = Field(default_factory=ExecutionPreferences)

    # Git settings
    branching_strategy: BranchingStrategy = BranchingStrategy.NONE
    phase_branch_template: str = "gpd/phase-{phase}-{slug}"
    milestone_branch_template: str = "gpd/{milestone}-{slug}"

    # Optional overrides
    model_overrides: dict[str, dict[str, str]] | None = Field(default=None)

    @field_validator("model_overrides")
    @classmethod
    def _validate_model_overrides(cls, value: dict[str, dict[str, str]] | None) -> dict[str, dict[str, str]] | None:
        """Validate runtime-scoped tier override mappings."""
        if value is None:
            return None

        normalized: dict[str, dict[str, str]] = {}
        normalized_runtime_sources: dict[str, str] = {}
        try:
            valid_runtime_names = _valid_runtime_names()
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc
        supported_runtimes = ", ".join(sorted(valid_runtime_names))
        supported_tiers = ", ".join(sorted(_VALID_MODEL_TIER_VALUES))

        for runtime, tier_map in value.items():
            normalized_runtime_name = normalize_runtime_name(runtime)
            if normalized_runtime_name not in valid_runtime_names:
                raise ValueError(
                    f"model_overrides contains unknown runtime {runtime!r}; "
                    f"expected one of: {supported_runtimes}"
                )
            if not isinstance(tier_map, dict):
                raise TypeError(f"model_overrides[{runtime!r}] must be an object mapping tiers to model ids")

            normalized_runtime: dict[str, str] = {}
            for tier, model in tier_map.items():
                if tier not in _VALID_MODEL_TIER_VALUES:
                    raise ValueError(
                        f"model_overrides[{runtime!r}] contains unknown tier {tier!r}; "
                        f"expected one of: {supported_tiers}"
                    )
                if not isinstance(model, str) or not model.strip():
                    raise ValueError(
                        f"model_overrides[{runtime!r}][{tier!r}] must be a non-empty string"
                    )
                normalized_runtime[tier] = model.strip()

            if normalized_runtime:
                previous_runtime = normalized_runtime_sources.get(normalized_runtime_name)
                if previous_runtime is not None:
                    raise ValueError(
                        f"model_overrides contains duplicate runtime entries for {normalized_runtime_name!r}: "
                        f"{previous_runtime!r} and {runtime!r} both target the same runtime"
                    )
                normalized_runtime_sources[normalized_runtime_name] = runtime
                normalized[normalized_runtime_name] = normalized_runtime

        return normalized or None


# ─── Config Loading ─────────────────────────────────────────────────────────────

_CONFIG_DEFAULTS = GPDProjectConfig()


def _normalize_config_key(key: str) -> str:
    """Normalize a user-facing config key path."""
    return key.strip()


def _enum_value(value: object) -> object:
    """Return the string value for enum-like config fields."""
    return value.value if isinstance(value, StrEnum) else value


_EFFECTIVE_CONFIG_LEAVES: dict[str, Callable[[GPDProjectConfig], object]] = {
    "autonomy": lambda config: _enum_value(config.autonomy),
    "branching_strategy": lambda config: _enum_value(config.branching_strategy),
    "checkpoint_after_first_load_bearing_result": (
        lambda config: config.checkpoint_after_first_load_bearing_result
    ),
    "checkpoint_after_n_tasks": lambda config: config.checkpoint_after_n_tasks,
    "checkpoint_before_downstream_dependent_tasks": (
        lambda config: config.checkpoint_before_downstream_dependent_tasks
    ),
    "commit_docs": lambda config: config.commit_docs,
    "max_unattended_minutes_per_plan": lambda config: config.max_unattended_minutes_per_plan,
    "max_unattended_minutes_per_wave": lambda config: config.max_unattended_minutes_per_wave,
    "milestone_branch_template": lambda config: config.milestone_branch_template,
    "model_overrides": lambda config: copy.deepcopy(config.model_overrides),
    "model_profile": lambda config: _enum_value(config.model_profile),
    "parallelization": lambda config: config.parallelization,
    "phase_branch_template": lambda config: config.phase_branch_template,
    "plan_checker": lambda config: config.plan_checker,
    "project_usd_budget": lambda config: config.project_usd_budget,
    "research": lambda config: config.research,
    "review_cadence": lambda config: _enum_value(config.review_cadence),
    "research_mode": lambda config: _enum_value(config.research_mode),
    "session_usd_budget": lambda config: config.session_usd_budget,
    "verifier": lambda config: config.verifier,
    "strict_wait": lambda config: config.execution_preferences.strict_wait,
    "never_interrupt_running_workers": (
        lambda config: config.execution_preferences.never_interrupt_running_workers
    ),
    "never_auto_close_child_agents": (
        lambda config: config.execution_preferences.never_auto_close_child_agents
    ),
}

_EFFECTIVE_CONFIG_SECTIONS: dict[str, Callable[[GPDProjectConfig], dict[str, object]]] = {
    "git": lambda config: {
        "branching_strategy": _enum_value(config.branching_strategy),
        "phase_branch_template": config.phase_branch_template,
        "milestone_branch_template": config.milestone_branch_template,
    },
    "planning": lambda config: {"commit_docs": config.commit_docs},
    "execution": lambda config: {
        "review_cadence": _enum_value(config.review_cadence),
        "max_unattended_minutes_per_plan": config.max_unattended_minutes_per_plan,
        "max_unattended_minutes_per_wave": config.max_unattended_minutes_per_wave,
        "checkpoint_after_n_tasks": config.checkpoint_after_n_tasks,
        "checkpoint_after_first_load_bearing_result": config.checkpoint_after_first_load_bearing_result,
        "checkpoint_before_downstream_dependent_tasks": config.checkpoint_before_downstream_dependent_tasks,
        "project_usd_budget": config.project_usd_budget,
        "session_usd_budget": config.session_usd_budget,
    },
    "workflow": lambda config: {
        "research": config.research,
        "plan_checker": config.plan_checker,
        "verifier": config.verifier,
    },
    "execution_preferences": lambda config: {
        "strict_wait": config.execution_preferences.strict_wait,
        "never_interrupt_running_workers": config.execution_preferences.never_interrupt_running_workers,
        "never_auto_close_child_agents": config.execution_preferences.never_auto_close_child_agents,
    },
}

_CONFIG_KEY_ALIASES: dict[str, str] = {
    "autonomy": "autonomy",
    "branching_strategy": "branching_strategy",
    "checkpoint_after_first_load_bearing_result": "checkpoint_after_first_load_bearing_result",
    "checkpoint_after_n_tasks": "checkpoint_after_n_tasks",
    "checkpoint_before_downstream_dependent_tasks": "checkpoint_before_downstream_dependent_tasks",
    "commit_docs": "commit_docs",
    "execution.checkpoint_after_first_load_bearing_result": "checkpoint_after_first_load_bearing_result",
    "execution.checkpoint_after_n_tasks": "checkpoint_after_n_tasks",
    "execution.checkpoint_before_downstream_dependent_tasks": "checkpoint_before_downstream_dependent_tasks",
    "execution.max_unattended_minutes_per_plan": "max_unattended_minutes_per_plan",
    "execution.max_unattended_minutes_per_wave": "max_unattended_minutes_per_wave",
    "execution.review_cadence": "review_cadence",
    "git.branching_strategy": "branching_strategy",
    "git.milestone_branch_template": "milestone_branch_template",
    "git.phase_branch_template": "phase_branch_template",
    "max_unattended_minutes_per_plan": "max_unattended_minutes_per_plan",
    "max_unattended_minutes_per_wave": "max_unattended_minutes_per_wave",
    "milestone_branch_template": "milestone_branch_template",
    "model_overrides": "model_overrides",
    "model_profile": "model_profile",
    "parallelization": "parallelization",
    "phase_branch_template": "phase_branch_template",
    "plan_checker": "plan_checker",
    "planning.commit_docs": "commit_docs",
    "project_usd_budget": "project_usd_budget",
    "research": "research",
    "review_cadence": "review_cadence",
    "research_mode": "research_mode",
    "session_usd_budget": "session_usd_budget",
    "verifier": "verifier",
    "execution.project_usd_budget": "project_usd_budget",
    "execution.session_usd_budget": "session_usd_budget",
    "workflow.plan_checker": "plan_checker",
    "workflow.research": "research",
    "workflow.verifier": "verifier",
    "strict_wait": "strict_wait",
    "never_interrupt_running_workers": "never_interrupt_running_workers",
    "never_auto_close_child_agents": "never_auto_close_child_agents",
    "execution_preferences.strict_wait": "strict_wait",
    "execution_preferences.never_interrupt_running_workers": "never_interrupt_running_workers",
    "execution_preferences.never_auto_close_child_agents": "never_auto_close_child_agents",
}

_CANONICAL_CONFIG_STORAGE_PATHS: dict[str, tuple[str, ...]] = {
    canonical_key: (canonical_key,) for canonical_key in _EFFECTIVE_CONFIG_LEAVES
}
_CANONICAL_CONFIG_STORAGE_PATHS.update(
    {
        "review_cadence": ("execution", "review_cadence"),
        "max_unattended_minutes_per_plan": ("execution", "max_unattended_minutes_per_plan"),
        "max_unattended_minutes_per_wave": ("execution", "max_unattended_minutes_per_wave"),
        "checkpoint_after_n_tasks": ("execution", "checkpoint_after_n_tasks"),
        "checkpoint_after_first_load_bearing_result": (
            "execution",
            "checkpoint_after_first_load_bearing_result",
        ),
        "checkpoint_before_downstream_dependent_tasks": (
            "execution",
            "checkpoint_before_downstream_dependent_tasks",
        ),
        "project_usd_budget": ("execution", "project_usd_budget"),
        "session_usd_budget": ("execution", "session_usd_budget"),
        "strict_wait": ("execution_preferences", "strict_wait"),
        "never_interrupt_running_workers": (
            "execution_preferences",
            "never_interrupt_running_workers",
        ),
        "never_auto_close_child_agents": (
            "execution_preferences",
            "never_auto_close_child_agents",
        ),
    }
)

_ALIASES_BY_CANONICAL_KEY: dict[str, tuple[str, ...]] = {}
for _alias, _canonical_key in _CONFIG_KEY_ALIASES.items():
    _ALIASES_BY_CANONICAL_KEY.setdefault(_canonical_key, []).append(_alias)
_ALIASES_BY_CANONICAL_KEY = {
    canonical_key: tuple(sorted(set(aliases)))
    for canonical_key, aliases in _ALIASES_BY_CANONICAL_KEY.items()
}


def supported_config_keys() -> tuple[str, ...]:
    """Return the supported writable CLI-facing config keys."""
    return tuple(sorted(_CONFIG_KEY_ALIASES))


def canonical_config_key(key: str) -> str | None:
    """Resolve a CLI-facing config key to its canonical leaf key."""
    return _CONFIG_KEY_ALIASES.get(_normalize_config_key(key))


def effective_config_value(config: GPDProjectConfig, key: str) -> tuple[bool, object]:
    """Return a CLI-facing effective config value for a supported key."""
    normalized_key = _normalize_config_key(key)
    if normalized_key in _EFFECTIVE_CONFIG_SECTIONS:
        return True, _EFFECTIVE_CONFIG_SECTIONS[normalized_key](config)

    canonical_key = canonical_config_key(normalized_key)
    if canonical_key is None:
        return False, None
    return True, _EFFECTIVE_CONFIG_LEAVES[canonical_key](config)


def effective_raw_config_value(raw: dict[str, object], key: str) -> tuple[bool, object]:
    """Return a CLI-facing effective config value directly from a raw payload."""

    return effective_config_value(_model_from_parsed_config(raw), key)


def _set_dict_path(target: dict[str, object], path: tuple[str, ...], value: object) -> None:
    """Set a dotted path inside a nested dict, creating parents as needed."""
    current = target
    for segment in path[:-1]:
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            next_value = {}
            current[segment] = next_value
        current = next_value
    current[path[-1]] = value


def _delete_dict_path(target: dict[str, object], path: tuple[str, ...]) -> None:
    """Delete a dotted path from a nested dict and prune empty containers."""
    if not path:
        return

    trail: list[tuple[dict[str, object], str]] = []
    current: object = target
    for segment in path[:-1]:
        if not isinstance(current, dict):
            return
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            return
        trail.append((current, segment))
        current = next_value

    if not isinstance(current, dict):
        return
    current.pop(path[-1], None)

    for parent, segment in reversed(trail):
        child = parent.get(segment)
        if isinstance(child, dict) and not child:
            parent.pop(segment, None)
        else:
            break


def apply_config_update(raw: dict[str, object], key: str, value: object) -> tuple[dict[str, object], str]:
    """Apply a validated config update and normalize shadow aliases away."""
    if not isinstance(raw, dict):
        raise ConfigError("config.json must be a JSON object")

    canonical_key = canonical_config_key(key)
    if canonical_key is None:
        supported = ", ".join(supported_config_keys())
        raise ConfigError(f"Unsupported config key {key!r}. Supported keys: {supported}")

    updated = copy.deepcopy(raw)
    storage_path = _CANONICAL_CONFIG_STORAGE_PATHS[canonical_key]
    _set_dict_path(updated, storage_path, value)
    for alias in _ALIASES_BY_CANONICAL_KEY.get(canonical_key, ()):
        alias_path = tuple(alias.split("."))
        if alias_path != storage_path:
            _delete_dict_path(updated, alias_path)

    _model_from_parsed_config(updated)
    return updated, canonical_key


def _known_agent_names() -> frozenset[str]:
    """Return the known agent names from registry metadata and tier maps."""
    known = set(MODEL_PROFILES) | set(AGENT_DEFAULT_TIERS)
    try:
        from gpd import registry as content_registry
    except (ImportError, ModuleNotFoundError):
        return frozenset(known)

    try:
        known.update(content_registry.list_agents())
    except AttributeError:
        return frozenset(known)
    except Exception as exc:
        raise ConfigError("Unable to resolve known agent names from registry") from exc
    return frozenset(known)


def validate_agent_name(agent_name: str) -> None:
    """Raise when an agent name is not part of the known registry surface."""
    normalized = agent_name.strip()
    if not normalized:
        raise ConfigError("Agent name must be a non-empty string")
    if normalized not in _known_agent_names():
        raise ConfigError(f"Unknown agent {agent_name!r}")


def _get_nested(parsed: dict, key: str, section: str | None = None, field: str | None = None) -> object:
    """Get a config value with optional nested section fallback."""
    if key in parsed:
        return parsed[key]
    if section and field and section in parsed and isinstance(parsed[section], dict):
        if field in parsed[section]:
            return parsed[section][field]
    return None


_ALLOWED_CONFIG_ROOT_KEYS = frozenset(
    {
        "autonomy",
        "branching_strategy",
        "checkpoint_after_first_load_bearing_result",
        "checkpoint_after_n_tasks",
        "checkpoint_before_downstream_dependent_tasks",
        "project_usd_budget",
        "session_usd_budget",
        "commit_docs",
        "execution",
        "execution_preferences",
        "git",
        "max_unattended_minutes_per_plan",
        "max_unattended_minutes_per_wave",
        "milestone_branch_template",
        "model_overrides",
        "model_profile",
        "never_auto_close_child_agents",
        "never_interrupt_running_workers",
        "parallelization",
        "phase_branch_template",
        "plan_checker",
        "planning",
        "research",
        "review_cadence",
        "research_mode",
        "strict_wait",
        "verifier",
        "workflow",
    }
)

_ALLOWED_CONFIG_SECTION_KEYS = {
    "git": frozenset({"branching_strategy", "milestone_branch_template", "phase_branch_template"}),
    "execution": frozenset(
        {
            "review_cadence",
            "max_unattended_minutes_per_plan",
            "max_unattended_minutes_per_wave",
            "checkpoint_after_n_tasks",
            "checkpoint_after_first_load_bearing_result",
            "checkpoint_before_downstream_dependent_tasks",
            "project_usd_budget",
            "session_usd_budget",
        }
    ),
    "execution_preferences": frozenset(
        {
            "strict_wait",
            "never_interrupt_running_workers",
            "never_auto_close_child_agents",
        }
    ),
    "planning": frozenset({"commit_docs"}),
    "workflow": frozenset({"plan_checker", "research", "verifier"}),
}


def _unsupported_config_keys(parsed: dict[str, object]) -> list[str]:
    """Return unsupported config.json keys using the current schema only."""
    unsupported: list[str] = []

    for key, value in parsed.items():
        if key not in _ALLOWED_CONFIG_ROOT_KEYS:
            unsupported.append(key)
            continue

        if key == "parallelization" and isinstance(value, dict):
            if value:
                unsupported.extend(f"parallelization.{nested_key}" for nested_key in value)
            else:
                unsupported.append("parallelization")
            continue

        allowed_nested = _ALLOWED_CONFIG_SECTION_KEYS.get(key)
        if allowed_nested is None or not isinstance(value, dict):
            continue

        unsupported.extend(
            f"{key}.{nested_key}"
            for nested_key in value
            if nested_key not in allowed_nested
        )

    return sorted(unsupported)


def _lookup_config_path(parsed: dict[str, object], alias: str) -> tuple[bool, object]:
    segments = alias.split(".")
    current: object = parsed
    for segment in segments:
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _conflicting_duplicate_config_aliases(parsed: dict[str, object]) -> list[str]:
    """Return root/nested alias conflicts for the same canonical config key."""
    conflicts: list[str] = []
    for canonical_key, aliases in sorted(_ALIASES_BY_CANONICAL_KEY.items()):
        present: list[tuple[str, object]] = []
        for alias in aliases:
            found, value = _lookup_config_path(parsed, alias)
            if found:
                present.append((alias, value))
        if len(present) < 2:
            continue

        first_alias, first_value = present[0]
        conflicting_aliases = [alias for alias, value in present[1:] if value != first_value]
        if conflicting_aliases:
            conflicts.append(
                f"`{canonical_key}` has conflicting aliases: "
                + ", ".join(f"`{alias}`" for alias in (first_alias, *conflicting_aliases))
            )
    return conflicts


def _model_from_parsed_config(parsed: dict[str, object]) -> GPDProjectConfig:
    """Build the canonical config model from a parsed config payload."""
    if not isinstance(parsed, dict):
        raise ConfigError("config.json must be a JSON object")

    unsupported_keys = _unsupported_config_keys(parsed)
    if unsupported_keys:
        raise ConfigError(
            "Unsupported config.json keys: "
            + ", ".join(f"`{key}`" for key in unsupported_keys)
            + f". Update {PLANNING_DIR_NAME}/config.json to the current schema."
        )

    duplicate_alias_conflicts = _conflicting_duplicate_config_aliases(parsed)
    if duplicate_alias_conflicts:
        raise ConfigError(
            "Conflicting duplicate config aliases: "
            + "; ".join(duplicate_alias_conflicts)
            + f". Keep only one spelling in {PLANNING_DIR_NAME}/config.json."
        )

    try:
        return GPDProjectConfig(
            model_profile=_coalesce(
                _get_nested(parsed, "model_profile"),
                _CONFIG_DEFAULTS.model_profile,
            ),
            autonomy=_coalesce(
                _get_nested(parsed, "autonomy"),
                _CONFIG_DEFAULTS.autonomy,
            ),
            review_cadence=_coalesce(
                _get_nested(parsed, "review_cadence", section="execution", field="review_cadence"),
                _CONFIG_DEFAULTS.review_cadence,
            ),
            research_mode=_coalesce(
                _get_nested(parsed, "research_mode"),
                _CONFIG_DEFAULTS.research_mode,
            ),
            commit_docs=_coalesce(
                _get_nested(parsed, "commit_docs", section="planning", field="commit_docs"),
                _CONFIG_DEFAULTS.commit_docs,
            ),
            branching_strategy=_coalesce(
                _get_nested(parsed, "branching_strategy", section="git", field="branching_strategy"),
                _CONFIG_DEFAULTS.branching_strategy,
            ),
            phase_branch_template=_coalesce(
                _get_nested(parsed, "phase_branch_template", section="git", field="phase_branch_template"),
                _CONFIG_DEFAULTS.phase_branch_template,
            ),
            milestone_branch_template=_coalesce(
                _get_nested(parsed, "milestone_branch_template", section="git", field="milestone_branch_template"),
                _CONFIG_DEFAULTS.milestone_branch_template,
            ),
            research=_coalesce(
                _get_nested(parsed, "research", section="workflow", field="research"),
                _CONFIG_DEFAULTS.research,
            ),
            plan_checker=_coalesce(
                _get_nested(parsed, "plan_checker", section="workflow", field="plan_checker"),
                _CONFIG_DEFAULTS.plan_checker,
            ),
            verifier=_coalesce(
                _get_nested(parsed, "verifier", section="workflow", field="verifier"),
                _CONFIG_DEFAULTS.verifier,
            ),
            parallelization=_coalesce(
                _get_nested(parsed, "parallelization"),
                _CONFIG_DEFAULTS.parallelization,
            ),
            max_unattended_minutes_per_plan=_coalesce(
                _get_nested(
                    parsed,
                    "max_unattended_minutes_per_plan",
                    section="execution",
                    field="max_unattended_minutes_per_plan",
                ),
                _CONFIG_DEFAULTS.max_unattended_minutes_per_plan,
            ),
            max_unattended_minutes_per_wave=_coalesce(
                _get_nested(
                    parsed,
                    "max_unattended_minutes_per_wave",
                    section="execution",
                    field="max_unattended_minutes_per_wave",
                ),
                _CONFIG_DEFAULTS.max_unattended_minutes_per_wave,
            ),
            checkpoint_after_n_tasks=_coalesce(
                _get_nested(
                    parsed,
                    "checkpoint_after_n_tasks",
                    section="execution",
                    field="checkpoint_after_n_tasks",
                ),
                _CONFIG_DEFAULTS.checkpoint_after_n_tasks,
            ),
            checkpoint_after_first_load_bearing_result=_coalesce(
                _get_nested(
                    parsed,
                    "checkpoint_after_first_load_bearing_result",
                    section="execution",
                    field="checkpoint_after_first_load_bearing_result",
                ),
                _CONFIG_DEFAULTS.checkpoint_after_first_load_bearing_result,
            ),
            checkpoint_before_downstream_dependent_tasks=_coalesce(
                _get_nested(
                    parsed,
                    "checkpoint_before_downstream_dependent_tasks",
                    section="execution",
                    field="checkpoint_before_downstream_dependent_tasks",
                ),
                _CONFIG_DEFAULTS.checkpoint_before_downstream_dependent_tasks,
            ),
            project_usd_budget=_coalesce(
                _get_nested(parsed, "project_usd_budget", section="execution", field="project_usd_budget"),
                _CONFIG_DEFAULTS.project_usd_budget,
            ),
            session_usd_budget=_coalesce(
                _get_nested(parsed, "session_usd_budget", section="execution", field="session_usd_budget"),
                _CONFIG_DEFAULTS.session_usd_budget,
            ),
            model_overrides=_coalesce(
                _get_nested(parsed, "model_overrides"),
                None,
            ),
            execution_preferences=ExecutionPreferences(
                strict_wait=bool(
                    _coalesce(
                        _get_nested(
                            parsed,
                            "strict_wait",
                            section="execution_preferences",
                            field="strict_wait",
                        ),
                        _CONFIG_DEFAULTS.execution_preferences.strict_wait,
                    )
                ),
                never_interrupt_running_workers=bool(
                    _coalesce(
                        _get_nested(
                            parsed,
                            "never_interrupt_running_workers",
                            section="execution_preferences",
                            field="never_interrupt_running_workers",
                        ),
                        _CONFIG_DEFAULTS.execution_preferences.never_interrupt_running_workers,
                    )
                ),
                never_auto_close_child_agents=bool(
                    _coalesce(
                        _get_nested(
                            parsed,
                            "never_auto_close_child_agents",
                            section="execution_preferences",
                            field="never_auto_close_child_agents",
                        ),
                        _CONFIG_DEFAULTS.execution_preferences.never_auto_close_child_agents,
                    )
                ),
            ),
        )
    except (ValueError, TypeError) as e:
        raise ConfigError(
            f"Invalid config.json values: {e}. Fix or delete {PLANNING_DIR_NAME}/config.json"
        ) from e


@instrument_gpd_function("config.load")
def load_config(project_dir: Path) -> GPDProjectConfig:
    """Load GPD config from GPD/config.json with defaults.

    Raises on malformed JSON. Returns defaults if file doesn't exist.
    """
    config_path = ProjectLayout(project_dir).config_json
    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _apply_gitignore_commit_docs(project_dir, GPDProjectConfig())
    except (PermissionError, UnicodeDecodeError, OSError) as exc:
        raise ConfigError(f"Cannot read config file {config_path}: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Malformed config.json: {e}. Fix or delete {PLANNING_DIR_NAME}/config.json") from e
    return _apply_gitignore_commit_docs(project_dir, _model_from_parsed_config(parsed))


def _apply_gitignore_commit_docs(project_dir: Path, config: GPDProjectConfig) -> GPDProjectConfig:
    """Force commit_docs off when the planning directory is gitignored."""
    if _planning_dir_is_gitignored(project_dir):
        return config.model_copy(update={"commit_docs": False})
    return config


def _planning_dir_is_gitignored(project_dir: Path) -> bool:
    """Return True when the planning directory is ignored by git."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", f"{PLANNING_DIR_NAME}/"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False

    return result.returncode == 0


def _coalesce(value: object, default: object) -> object:
    """Return value if not None, else default."""
    return value if value is not None else default


# ─── Model Resolution ───────────────────────────────────────────────────────────


@instrument_gpd_function("config.resolve_tier")
def resolve_agent_tier(agent_name: str, profile: ModelProfile | str) -> ModelTier:
    """Resolve the model tier for an agent given a model profile.

    Raises when the profile matrix is incomplete instead of silently
    downgrading to a default tier.
    """
    validate_agent_name(agent_name)
    _validate_model_profile_matrix()
    profile_str = profile.value if isinstance(profile, ModelProfile) else profile
    if profile_str not in _MODEL_PROFILE_KEYS:
        supported = ", ".join(sorted(_MODEL_PROFILE_KEYS))
        raise ConfigError(f"Unknown model profile {profile_str!r}. Supported profiles: {supported}")
    agent_profiles = MODEL_PROFILES.get(agent_name)
    if agent_profiles is None:
        raise ConfigError(f"No model tier mapping configured for agent {agent_name!r}")
    tier = agent_profiles.get(profile_str)
    if tier is None:
        raise ConfigError(f"No model tier mapping configured for agent {agent_name!r} and profile {profile_str!r}")
    return tier


@instrument_gpd_function("config.resolve_project_tier")
def resolve_tier(project_dir: Path, agent_name: str) -> ModelTier:
    """Resolve the abstract model tier for an agent in a project."""
    config = load_config(project_dir)
    return resolve_agent_tier(agent_name, config.model_profile)


@instrument_gpd_function("config.resolve_model")
def resolve_model(project_dir: Path, agent_name: str, runtime: str | None = None) -> str | None:
    """Resolve the runtime-specific model override for an agent in a project.

    Returns the concrete model name when the current runtime has an explicit
    override for the agent's resolved tier. Returns ``None`` when no override is
    configured so the caller can omit the runtime model parameter and let the
    platform use its own default model.
    """
    validate_agent_name(agent_name)
    if not runtime:
        return None

    config = load_config(project_dir)
    tier = resolve_agent_tier(agent_name, config.model_profile).value
    normalized_runtime = normalize_runtime_name(runtime)
    if normalized_runtime is None:
        supported = ", ".join(sorted(_valid_runtime_names()))
        raise ConfigError(f"Unknown runtime {runtime!r}. Supported runtimes: {supported}")
    runtime_overrides = (config.model_overrides or {}).get(normalized_runtime)
    if not runtime_overrides:
        return None
    return runtime_overrides.get(tier)
