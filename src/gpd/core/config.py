"""GPD configuration loading and model tier system.

Layer 1 code: stdlib + pydantic only.
"""

from __future__ import annotations

import json
import logging
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.constants import PLANNING_DIR_NAME, ProjectLayout
from gpd.core.errors import ConfigError
from gpd.core.observability import instrument_gpd_function

logger = logging.getLogger(__name__)

__all__ = [
    "AGENT_DEFAULT_TIERS",
    "DEFAULT_COST_PER_MILLION",
    "MODEL_PROFILES",
    "AutonomyMode",
    "BranchingStrategy",
    "GPDProjectConfig",
    "ModelProfile",
    "ModelTier",
    "ResearchMode",
    "TierCost",
    "get_cost_per_million",
    "load_config",
    "resolve_agent_tier",
    "resolve_model",
]

# ─── Enums ──────────────────────────────────────────────────────────────────────


class AutonomyMode(StrEnum):
    """How much human oversight the system requires."""

    SUPERVISED = "supervised"
    GUIDED = "guided"
    AUTONOMOUS = "autonomous"
    YOLO = "yolo"


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
    "gpd-theory-mapper": {
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

# Default tier per agent (profile-independent fallback)
AGENT_DEFAULT_TIERS: dict[str, ModelTier] = {
    "gpd-planner": ModelTier.TIER_1,
    "gpd-roadmapper": ModelTier.TIER_1,
    "gpd-executor": ModelTier.TIER_2,
    "gpd-phase-researcher": ModelTier.TIER_2,
    "gpd-project-researcher": ModelTier.TIER_2,
    "gpd-research-synthesizer": ModelTier.TIER_2,
    "gpd-debugger": ModelTier.TIER_1,
    "gpd-theory-mapper": ModelTier.TIER_3,
    "gpd-verifier": ModelTier.TIER_1,
    "gpd-plan-checker": ModelTier.TIER_1,
    "gpd-consistency-checker": ModelTier.TIER_1,
    "gpd-paper-writer": ModelTier.TIER_2,
    "gpd-literature-reviewer": ModelTier.TIER_2,
    "gpd-bibliographer": ModelTier.TIER_2,
    "gpd-referee": ModelTier.TIER_1,
    "gpd-experiment-designer": ModelTier.TIER_2,
    "gpd-notation-coordinator": ModelTier.TIER_2,
}

# ─── Cost Defaults ──────────────────────────────────────────────────────────────


class TierCost(BaseModel):
    """Cost per million tokens for a single tier."""

    model_config = ConfigDict(frozen=True)

    input: float
    output: float


# Default pricing per million tokens (provider-agnostic tier defaults)
DEFAULT_COST_PER_MILLION: dict[str, TierCost] = {
    "tier-1": TierCost(input=15.0, output=75.0),
    "tier-2": TierCost(input=3.0, output=15.0),
    "tier-3": TierCost(input=0.25, output=1.25),
}

# ─── Config Model ───────────────────────────────────────────────────────────────


class GPDProjectConfig(BaseModel):
    """Configuration for a GPD project, loaded from .gpd/config.json.

    Named GPDProjectConfig to distinguish it from other shared project
    contracts. This model controls project-level workflow settings
    (model profile, autonomy, git strategy, etc.).
    """

    model_profile: ModelProfile = ModelProfile.REVIEW
    autonomy: AutonomyMode = AutonomyMode.GUIDED
    research_mode: ResearchMode = ResearchMode.BALANCED

    # Workflow toggles
    commit_docs: bool = True
    search_gitignored: bool = False
    research: bool = True
    plan_checker: bool = True
    verifier: bool = True
    parallelization: bool = True
    brave_search: bool = False

    # Git settings
    branching_strategy: BranchingStrategy = BranchingStrategy.NONE
    phase_branch_template: str = "gpd/phase-{phase}-{slug}"
    milestone_branch_template: str = "gpd/{milestone}-{slug}"

    # Optional overrides
    model_map: dict[str, str] | None = Field(default=None)
    cost_per_million: dict[str, TierCost] | None = Field(default=None)


# ─── Config Loading ─────────────────────────────────────────────────────────────

_CONFIG_DEFAULTS = GPDProjectConfig()


def _get_nested(parsed: dict, key: str, section: str | None = None, field: str | None = None) -> object:
    """Get a config value with optional nested section fallback."""
    if key in parsed:
        return parsed[key]
    if section and field and section in parsed and isinstance(parsed[section], dict):
        if field in parsed[section]:
            return parsed[section][field]
    return None


def _resolve_autonomy(parsed: dict) -> AutonomyMode:
    """Resolve autonomy with backward compatibility for old 'mode' field."""
    val = _get_nested(parsed, "autonomy")
    if val is not None:
        return AutonomyMode(val)
    # Backward compat: map old "mode" field
    mode = _get_nested(parsed, "mode")
    if isinstance(mode, str):
        mode = mode.strip().lower()
    if mode == "yolo":
        return AutonomyMode.YOLO
    if mode == "interactive":
        return AutonomyMode.SUPERVISED
    return _CONFIG_DEFAULTS.autonomy


def _resolve_parallelization(parsed: dict) -> bool:
    """Resolve parallelization from bool or object with 'enabled' key."""
    val = _get_nested(parsed, "parallelization")
    if isinstance(val, bool):
        return val
    if isinstance(val, dict) and "enabled" in val:
        return bool(val["enabled"])
    return _CONFIG_DEFAULTS.parallelization


@instrument_gpd_function("config.load")
def load_config(project_dir: Path) -> GPDProjectConfig:
    """Load GPD config from .gpd/config.json with defaults.

    Raises on malformed JSON. Returns defaults if file doesn't exist.
    """
    config_path = ProjectLayout(project_dir).config_json
    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return GPDProjectConfig()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Malformed config.json: {e}. Fix or delete {PLANNING_DIR_NAME}/config.json") from e

    if not isinstance(parsed, dict):
        raise ConfigError("config.json must be a JSON object")

    try:
        return GPDProjectConfig(
            model_profile=_get_nested(parsed, "model_profile") or _CONFIG_DEFAULTS.model_profile,
            autonomy=_resolve_autonomy(parsed),
            research_mode=_get_nested(parsed, "research_mode") or _CONFIG_DEFAULTS.research_mode,
            commit_docs=_coalesce(
                _get_nested(parsed, "commit_docs", section="planning", field="commit_docs"),
                _CONFIG_DEFAULTS.commit_docs,
            ),
            search_gitignored=_coalesce(
                _get_nested(parsed, "search_gitignored", section="planning", field="search_gitignored"),
                _CONFIG_DEFAULTS.search_gitignored,
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
            plan_checker=_resolve_plan_checker(parsed),
            verifier=_coalesce(
                _get_nested(parsed, "verifier", section="workflow", field="verifier"),
                _CONFIG_DEFAULTS.verifier,
            ),
            parallelization=_resolve_parallelization(parsed),
            brave_search=_coalesce(
                _get_nested(parsed, "brave_search"),
                _CONFIG_DEFAULTS.brave_search,
            ),
            model_map=_get_nested(parsed, "model_map") or None,
            cost_per_million=_parse_cost_per_million(parsed),
        )
    except (ValueError, TypeError) as e:
        raise ConfigError(
            f"Invalid config.json values: {e}. Fix or delete {PLANNING_DIR_NAME}/config.json"
        ) from e


def _coalesce(value: object, default: object) -> object:
    """Return value if not None, else default."""
    return value if value is not None else default


def _resolve_plan_checker(parsed: dict) -> bool:
    """Resolve plan_checker with backward compat for workflow.plan_check."""
    val = _get_nested(parsed, "plan_checker", section="workflow", field="plan_checker")
    if val is not None:
        return bool(val)
    # backward compat: old configs used workflow.plan_check
    if "workflow" in parsed and isinstance(parsed["workflow"], dict):
        old_val = parsed["workflow"].get("plan_check")
        if old_val is not None:
            return bool(old_val)
    return _CONFIG_DEFAULTS.plan_checker


def _parse_cost_per_million(parsed: dict) -> dict[str, TierCost] | None:
    """Parse cost_per_million override from config."""
    raw = _get_nested(parsed, "cost_per_million")
    if not raw or not isinstance(raw, dict):
        return None
    result: dict[str, TierCost] = {}
    for tier, costs in raw.items():
        if isinstance(costs, dict):
            try:
                result[tier] = TierCost.model_validate(costs)
            except ValueError:
                continue
    return result if result else None


# ─── Model Resolution ───────────────────────────────────────────────────────────


@instrument_gpd_function("config.resolve_tier")
def resolve_agent_tier(agent_name: str, profile: ModelProfile | str) -> ModelTier:
    """Resolve the model tier for an agent given a model profile.

    Falls back to the agent's default tier, then to TIER_2.
    """
    profile_str = profile.value if isinstance(profile, ModelProfile) else profile
    agent_profiles = MODEL_PROFILES.get(agent_name)
    if agent_profiles:
        tier = agent_profiles.get(profile_str)
        if tier:
            return tier
        # Try "review" as fallback profile
        tier = agent_profiles.get("review")
        if tier:
            return tier
    return AGENT_DEFAULT_TIERS.get(agent_name, ModelTier.TIER_2)


@instrument_gpd_function("config.resolve_model")
def resolve_model(project_dir: Path, agent_name: str) -> str:
    """Resolve the model identifier for an agent in a project.

    Loads config, resolves tier via profile, then applies model_map override.
    Returns the tier string (e.g., "tier-1") or mapped model name.
    """
    config = load_config(project_dir)
    tier = resolve_agent_tier(agent_name, config.model_profile)
    if config.model_map and tier.value in config.model_map:
        return config.model_map[tier.value]
    return tier.value


@instrument_gpd_function("config.cost_per_million")
def get_cost_per_million(project_dir: Path | None = None) -> dict[str, TierCost]:
    """Get cost per million tokens, with optional project override."""
    if project_dir is not None:
        config = load_config(project_dir)
        if config.cost_per_million:
            merged = dict(DEFAULT_COST_PER_MILLION)
            merged.update(config.cost_per_million)
            return merged
    return dict(DEFAULT_COST_PER_MILLION)
