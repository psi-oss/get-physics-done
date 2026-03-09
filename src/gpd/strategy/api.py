"""Public API surface for gpd.strategy consumers.

Import everything you need from here instead of reaching into internal modules.
This module consolidates the key classes, factories, and utilities that external
packages (primarily agentic-builder and pipeline) depend on.

Example::

    from gpd.strategy.api import (
        BundleLoader,
        PhysicsTriageContext,
        PhysicsRubricProvider,
        PhaseConfigProvider,
        get_loader,
        ReferenceRouter,
        create_gpd_invariant_checks,
    )
"""

from __future__ import annotations

from pathlib import Path

# ─── Errors (re-exported from gpd.core for convenience) ─────────────────────
from gpd.core.errors import BundleError, GPDError, LoaderError

# ─── Verification Checks (pure data, lives in core/) ────────────────────────
from gpd.core.verification_checks import VERIFICATION_CHECKS

# ─── Bundle Loading ──────────────────────────────────────────────────────────
from gpd.strategy.bundle_loader import (
    ActionSpec,
    ActorSpec,
    Bundle,
    BundleLoader,
    BundleManifest,
    MergedBundle,
    SkillEntry,
    get_bundle_loader,
    init_bundle_loader,
    load_bundle,
    merge_bundles,
    resolve_placeholders,
)

# ─── Physics Providers (engine extension protocols) ──────────────────────────
from gpd.strategy.commit_gate_hooks import create_gpd_invariant_checks
from gpd.strategy.curator import PhysicsCurator

# ─── Reference Loading & Routing ─────────────────────────────────────────────
from gpd.strategy.loader import ReferenceLoader, get_loader

# ─── MCTS Strategy ──────────────────────────────────────────────────────────
from gpd.strategy.mcts import GPDMCTSStrategy
from gpd.strategy.phase_config import PhaseConfig, PhaseConfigProvider, detect_phase, load_phase_configs

# ─── Routing ─────────────────────────────────────────────────────────────────
from gpd.strategy.router import ReferenceRouter, get_router
from gpd.strategy.rubric_provider import PhysicsRubricProvider
from gpd.strategy.triage_context import PhysicsTriageContext

# ─── Type Bridge ─────────────────────────────────────────────────────────────
from gpd.strategy.type_bridge import (
    BlackboardStoreAdapter,
    WriteGateAdapter,
    contract_decision_to_engine,
    contract_entry_to_engine,
    dict_to_engine_entry,
    engine_decision_to_contract,
    engine_entry_to_contract,
    engine_write_request_to_contract,
)


def get_infra_dir() -> Path:
    """Return path to the gpd infra/ directory containing MCP server configs."""
    # api.py is at src/gpd/strategy/api.py → parent×3 = packages/gpd/
    return Path(__file__).parent.parent.parent.parent / "infra"


__all__ = [
    # Bundle loading
    "ActionSpec",
    "ActorSpec",
    "Bundle",
    "BundleLoader",
    "BundleManifest",
    "MergedBundle",
    "SkillEntry",
    "get_bundle_loader",
    "init_bundle_loader",
    "load_bundle",
    "merge_bundles",
    "resolve_placeholders",
    # Reference loading & routing
    "ReferenceLoader",
    "get_loader",
    "ReferenceRouter",
    "get_router",
    # Physics providers
    "PhysicsTriageContext",
    "PhysicsRubricProvider",
    "PhaseConfigProvider",
    "PhaseConfig",
    "PhysicsCurator",
    "create_gpd_invariant_checks",
    "detect_phase",
    "load_phase_configs",
    # MCTS strategy
    "GPDMCTSStrategy",
    # Type bridge
    "BlackboardStoreAdapter",
    "WriteGateAdapter",
    "dict_to_engine_entry",
    "contract_entry_to_engine",
    "engine_entry_to_contract",
    "contract_decision_to_engine",
    "engine_decision_to_contract",
    "engine_write_request_to_contract",
    # Verification checks
    "VERIFICATION_CHECKS",
    # Errors
    "GPDError",
    "BundleError",
    "LoaderError",
    # Utilities
    "get_infra_dir",
]
