"""GPDMCTSStrategy — MCTS strategy with GPD physics intelligence.

Wraps the base MCTSStrategy with convention lock enforcement,
CommitGate invariant checks, GPD-specific MCP tool injection,
and physics provider instantiation (triage context, rubric, curator,
phase config).

Registered as a pipeline strategy entry point:
    [project.entry-points."psi.strategies"]
    gpd_mcts = "gpd.strategy.mcts:GPDMCTSStrategy"
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import logfire
from psi_contracts.campaign import CampaignConfig
from psi_contracts.formalization import FormalProblem, Verifier
from gpd.contracts import ConventionLock, ErrorClass
from psi_contracts.solving import Run

from gpd.core.errors import LoaderError
from gpd.core.observability import gpd_span
from gpd.strategy.commit_gate_hooks import create_gpd_invariant_checks
from gpd.strategy.loader import ReferenceLoader, get_loader
from gpd.strategy.router import ReferenceRouter

if TYPE_CHECKING:
    from pipeline.capabilities import CapabilityRegistry

    from gpd.strategy.curator import PhysicsCurator
    from gpd.strategy.phase_config import PhaseConfigProvider
    from gpd.strategy.rubric_provider import PhysicsRubricProvider
    from gpd.strategy.triage_context import PhysicsTriageContext

from pipeline.strategies.base import AgenticStrategy, EventEmitter, MemoryStore, PauseCheck
from pipeline.strategies.mcts import MCTSStrategy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Convention lock extraction
# ---------------------------------------------------------------------------


def _extract_convention_lock(problem: FormalProblem) -> ConventionLock:
    """Extract convention lock from problem metadata or return empty lock.

    Checks FormalProblem.hard_constraints and problem_statement for
    ASSERT_CONVENTION directives.
    """
    from gpd.core.conventions import parse_assert_conventions

    lock = ConventionLock()

    # Parse from problem statement
    text = problem.problem_statement or problem.objective or ""
    for constraint in problem.hard_constraints:
        text += "\n" + constraint

    assertions = parse_assert_conventions(text)
    for key, value in assertions:
        if hasattr(lock, key) and key != "custom_conventions":
            setattr(lock, key, value)
        else:
            lock.custom_conventions[key] = value

    return lock


def convention_lock_consistency_check(
    problem: FormalProblem,
    config_lock: dict[str, str] | None = None,
) -> ConventionLock:
    """Reconcile convention locks from FormalProblem (primary) and YAML config (override).

    FormalProblem is the authoritative source (closest to user intent).
    YAML config values override when both sources set the same field.
    Conflicts are logged as WARNING to surface 3-source-of-truth drift
    (BUG A: builder path, strategy path, and MCP server path can diverge).

    Returns the merged ConventionLock for use by both CommitGate and strategy.
    """
    from gpd.core.conventions import KNOWN_CONVENTIONS, normalize_key, normalize_value

    problem_lock = _extract_convention_lock(problem)

    if not config_lock:
        return problem_lock

    merged = problem_lock.model_copy()

    for raw_key, raw_value in config_lock.items():
        key = normalize_key(raw_key)
        value = str(raw_value).strip()
        if not value:
            continue

        if key in KNOWN_CONVENTIONS:
            problem_value = getattr(merged, key, None)
            if problem_value is not None:
                norm_problem = normalize_value(key, problem_value)
                norm_config = normalize_value(key, value)
                if norm_problem != norm_config:
                    logger.warning(
                        "convention_lock_conflict",
                        extra={
                            "key": key,
                            "problem_value": problem_value,
                            "config_value": value,
                            "resolution": "config_override",
                        },
                    )
            setattr(merged, key, value)
        else:
            problem_custom = merged.custom_conventions.get(key)
            if problem_custom is not None and problem_custom != value:
                logger.warning(
                    "convention_lock_conflict",
                    extra={
                        "key": key,
                        "problem_value": problem_custom,
                        "config_value": value,
                        "resolution": "config_override",
                    },
                )
            merged.custom_conventions[key] = value

    return merged


def _load_error_catalog(loader: ReferenceLoader, domain: str | None) -> list[ErrorClass]:
    """Load error catalog entries relevant to the physics domain.

    Uses the router to find relevant error catalog files, loads them via
    the ReferenceLoader, and parses ErrorClass entries from markdown tables.
    """
    router = ReferenceRouter(loader)
    if not domain:
        return []

    # route_errors_to_catalogs returns catalog file names (e.g. ["llm-errors-core"])
    catalog_names = router.route_errors_to_catalogs(domain)
    catalog: list[ErrorClass] = []
    for catalog_name in catalog_names:
        content = loader.load_error_catalog(catalog_name)
        if content:
            catalog.extend(_parse_error_classes_from_markdown(content))

    return catalog


def _parse_error_classes_from_markdown(content: str) -> list[ErrorClass]:
    """Parse ErrorClass entries from markdown table rows.

    Expected format (from llm-physics-errors.md):
    | ID | Name | Description | Detection Strategy | Example | Domains |
    """
    import re

    errors: list[ErrorClass] = []
    # Match markdown table rows: | id | name | desc | strategy | example | domains |
    row_pattern = re.compile(
        r"^\|\s*(\d+)\s*\|"  # id
        r"\s*([^|]+?)\s*\|"  # name
        r"\s*([^|]+?)\s*\|"  # description
        r"\s*([^|]+?)\s*\|"  # detection_strategy
        r"\s*([^|]*?)\s*\|"  # example (may be empty)
        r"\s*([^|]*?)\s*\|",  # domains (may be empty)
        re.MULTILINE,
    )
    for match in row_pattern.finditer(content):
        raw_id, name, desc, strategy, example, domains_str = match.groups()
        domain_list = [d.strip() for d in domains_str.split(",") if d.strip()]
        errors.append(
            ErrorClass(
                id=int(raw_id),
                name=name.strip(),
                description=desc.strip(),
                detection_strategy=strategy.strip(),
                example=example.strip(),
                domains=domain_list or ["general"],
            )
        )
    return errors


def _resolve_gpd_mcp_tools(params: object, existing_tools: list[str]) -> list[str]:
    """Resolve GPD MCP tools using the canonical tool_manifest resolver.

    Delegates to ``agentic_builder.tools.manifest.resolve_gpd_tools`` which
    derives MCP tool names from GPD feature flags.  Deduplicates against
    tools already present in strategy params.
    """
    from agentic_builder.tools.manifest import resolve_gpd_tools

    gpd_tools = resolve_gpd_tools(params)
    existing = set(existing_tools)
    return [t for t in gpd_tools if t not in existing]


def _infer_domain(problem: FormalProblem) -> str | None:
    """Infer the physics domain string from FormalProblem.

    Maps from the contracts PhysicsDomain enum (from TaskAgent) to
    the GPD domain string used by reference routing.
    """
    if problem.domain is None:
        return None
    return str(problem.domain.value)


# ---------------------------------------------------------------------------
# Overlay resolution
# ---------------------------------------------------------------------------

_DEFAULT_OVERLAYS = ["physics"]
_ENV_OVERLAY_KEY = "GPD_BUNDLE_OVERLAYS"


def _resolve_overlay_names(gpd_cfg: object | None) -> list[str]:
    """Resolve bundle overlay names from GPDConfig, env var, or default.

    Precedence: GPDConfig.bundle_overlays > GPD_BUNDLE_OVERLAYS env var > ["physics"].
    The env var is a comma-separated string (e.g. "physics,astro").
    """
    import os

    # 1. GPDConfig field (if present and non-default)
    if gpd_cfg is not None and hasattr(gpd_cfg, "bundle_overlays"):
        overlays = gpd_cfg.bundle_overlays  # type: ignore[union-attr]
        if overlays is not None:
            return list(overlays)

    # 2. Environment variable
    env_val = os.environ.get(_ENV_OVERLAY_KEY)
    if env_val:
        return [s.strip() for s in env_val.split(",") if s.strip()]

    # 3. Default
    return list(_DEFAULT_OVERLAYS)


# ---------------------------------------------------------------------------
# Provider factories
# ---------------------------------------------------------------------------


def _create_triage_context(
    domain: str | None,
    overlay_names: list[str] | None = None,
) -> PhysicsTriageContext | None:
    """Create a PhysicsTriageContext with a loaded BundleLoader and router.

    Returns None if the bundle or reference loader cannot be initialized.
    ``get_loader()`` may raise ``RuntimeError`` when the reference directory
    is misconfigured — this is a known API behavior, not an unexpected error.
    """
    from gpd.strategy.bundle_loader import BundleLoader
    from gpd.strategy.triage_context import PhysicsTriageContext

    try:
        loader = BundleLoader()
        overlays = overlay_names if domain else None
        loader.load(base_name="base", overlay_names=overlays)
    except (LoaderError, OSError) as exc:
        logger.info("gpd_triage_context_skipped", extra={"reason": str(exc)})
        return None

    try:
        ref_loader = get_loader()
    except (LoaderError, OSError, RuntimeError) as exc:
        logger.info("gpd_triage_context_skipped", extra={"reason": str(exc)})
        return None

    if ref_loader is None:
        logger.info("gpd_triage_context_skipped: no reference loader available")
        return None
    router = ReferenceRouter(ref_loader)

    return PhysicsTriageContext(bundle_loader=loader, reference_router=router, domain=domain)


def _create_rubric_provider() -> PhysicsRubricProvider:
    """Create a PhysicsRubricProvider (always succeeds — no I/O)."""
    from gpd.strategy.rubric_provider import PhysicsRubricProvider

    return PhysicsRubricProvider()


def _create_curator(model_id: str) -> PhysicsCurator:
    """Create a PhysicsCurator with the specified model.

    Uses haiku-tier by default for fast, cheap curation calls.
    """
    from gpd.strategy.curator import PhysicsCurator

    return PhysicsCurator(model_id=model_id)


def _create_phase_config_provider(project_dir: Path | None = None) -> PhaseConfigProvider:
    """Create a PhaseConfigProvider with merged phase configs."""
    from gpd.strategy.phase_config import PhaseConfigProvider

    return PhaseConfigProvider(project_dir=project_dir)


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


class GPDMCTSStrategy(AgenticStrategy):
    """MCTS strategy enhanced with GPD physics intelligence.

    When ``strategy_params.gpd_enabled`` is True:
    1. Extracts convention lock from problem metadata
    2. Loads domain-relevant error catalog from bundles
    3. Injects GPD MCP tools into the solver's tool list
    4. Creates CommitGate invariant check hooks
    5. Instantiates physics providers (triage context, rubric, curator, phase config)
    6. Creates campaign-scoped blackboard store
    7. Builds provider dict for SystemBuilder pass-through
    8. Delegates to MCTSStrategy with enriched config and providers
    9. Runs GPD invariant checks on yielded Runs

    When ``gpd_enabled`` is False, delegates directly to MCTSStrategy
    with no overhead.
    """

    async def solve(
        self,
        problem: FormalProblem,
        verifier: Verifier,
        capabilities: CapabilityRegistry,
        config: CampaignConfig,
        memory: MemoryStore,
        events: EventEmitter,
        ctx: object = None,
        campaign_id: UUID | None = None,
        pause_event: asyncio.Event | None = None,
        sequence_offset: int = 0,
        providers: dict[str, object] | None = None,
        pause_check: PauseCheck | None = None,
    ) -> AsyncIterator[Run]:
        """Yield scored runs from GPD-enhanced MCTS search."""
        params = config.strategy_params

        if not params.gpd_enabled:
            # Fast path: delegate directly to base MCTS
            async for run in MCTSStrategy().solve(
                problem=problem,
                verifier=verifier,
                capabilities=capabilities,
                config=config,
                memory=memory,
                events=events,
                ctx=ctx,
                campaign_id=campaign_id,
                pause_event=pause_event,
                sequence_offset=sequence_offset,
                providers=providers,
                pause_check=pause_check,
            ):
                yield run
            return

        with gpd_span("strategy.gpd_mcts_solve", bundle=params.gpd_bundle) as span:
            domain = _infer_domain(problem)
            span.set_attribute("gpd.domain", domain or "unknown")

            await events.emit(
                "gpd_strategy_started",
                {
                    "domain": domain,
                    "gpd_conventions": params.gpd_conventions,
                    "gpd_verification": params.gpd_verification,
                    "gpd_protocols": params.gpd_protocols,
                    "gpd_errors": params.gpd_errors,
                    "gpd_bundle": params.gpd_bundle,
                },
            )

            # 1. Merge convention lock from FormalProblem + YAML config
            gpd_cfg = config.gpd_config
            convention_lock = convention_lock_consistency_check(problem, config_lock=None)
            logger.info(
                "gpd_convention_lock_loaded",
                extra={"domain": domain, "has_metric": convention_lock.metric_signature is not None},
            )

            # 2. Load error catalog
            error_catalog: list[ErrorClass] = []
            if params.gpd_errors:
                error_catalog = _load_error_catalog_optional(domain)

            # 3. Create CommitGate invariant checks
            invariant_checks = create_gpd_invariant_checks(convention_lock, error_catalog)
            if invariant_checks:
                await events.emit(
                    "gpd_invariant_checks_configured",
                    {"count": len(invariant_checks)},
                )

            # 4. Inject GPD MCP tools into strategy params
            gpd_tools = _resolve_gpd_mcp_tools(params, list(params.mcp_tools))
            if gpd_tools:
                enriched_mcp_tools = list(params.mcp_tools) + gpd_tools
                params = params.model_copy(update={"mcp_tools": enriched_mcp_tools})
                config = config.model_copy(update={"strategy_params": params})
                logger.info("gpd_mcp_tools_injected", extra={"tools": gpd_tools})

            # 5. Instantiate physics providers
            #    Resolve overlay names: GPDConfig > env var > default ["physics"]
            overlay_names = _resolve_overlay_names(gpd_cfg)
            triage_ctx = _create_triage_context(domain, overlay_names=overlay_names)
            rubric_provider = _create_rubric_provider()
            phase_config = _create_phase_config_provider()

            # Curator model: use haiku for cheap curation gating
            from gpd.core.model_defaults import GPD_DEFAULT_FAST_MODEL

            curator_model = GPD_DEFAULT_FAST_MODEL
            curator = _create_curator(curator_model)

            # Bridge curator (contract types) to engine WriteGateProvider protocol
            from gpd.strategy.type_bridge import WriteGateAdapter

            write_gate = WriteGateAdapter(curator)

            provider_summary = {
                "triage_context": triage_ctx is not None,
                "rubric_provider": True,
                "curator": True,
                "write_gate": True,
                "phase_config": True,
                # Blackboard is owned by agentic-builder when RunConfig.gpd.enabled is set.
                # This strategy does NOT provide its own blackboard store to avoid
                # diverging DB paths between in-process access and the gpd-blackboard MCP server.
                "blackboard": False,
            }
            logger.info("gpd_providers_created", extra=provider_summary)
            span.set_attribute("gpd.providers", str(provider_summary))

            await events.emit("gpd_providers_configured", provider_summary)

            # 6. Store convention lock, invariant checks, and provider refs
            #    in memory for downstream consumption by engine
            await memory.record_hypothesis(
                {
                    "type": "gpd_convention_lock",
                    "convention_lock": convention_lock.model_dump(),
                    "error_catalog_size": len(error_catalog),
                    "invariant_check_count": len(invariant_checks),
                    "providers": provider_summary,
                }
            )

            # 7. Load V2 payload schema overlay from first overlay that has one
            from gpd.specs import SPECS_DIR as _specs_dir

            payload_overlay = None
            for _ovl_name in overlay_names:
                overlay_path = _specs_dir / _ovl_name / "schemas" / "payload_overlay.json"
                if overlay_path.exists():
                    import json as _json

                    payload_overlay = _json.loads(overlay_path.read_text())
                    logger.info("gpd_payload_overlay_loaded", path=str(overlay_path))
                    break

            # 7b. Load skill manifest from bundle skill directories
            skill_manifest = None
            try:
                from agentic_builder.tools.skill_executor import load_skill_manifest

                skill_dirs = [_specs_dir / "skills"] + [_specs_dir / n / "skills" for n in overlay_names]
                skill_dirs = [d for d in skill_dirs if d.is_dir()]
                if skill_dirs:
                    skill_manifest = load_skill_manifest(skill_dirs)
                    logger.info("gpd_skill_manifest_loaded", skill_count=len(skill_manifest))
            except ImportError:
                logger.debug("skill_executor not available, skipping skill manifest")

            # 8. Build provider dict for SystemBuilder pass-through
            #    Keys must match SystemBuilder.__init__ kwargs.
            #    Only include non-None optional providers — the builder
            #    uses its own defaults when a key is absent.
            builder_providers: dict[str, object] = {
                "rubric_provider": rubric_provider,
                "phase_config_provider": phase_config,
                "write_gate_provider": write_gate,
            }
            if triage_ctx is not None:
                builder_providers["triage_context_provider"] = triage_ctx
            if skill_manifest:
                builder_providers["skill_manifest"] = skill_manifest
            if payload_overlay is not None:
                builder_providers["payload_schema_overlay"] = payload_overlay

            # 9. Delegate to MCTSStrategy with providers flowing through
            #    MCTSStrategy → solve_mcts_streaming → SystemBuilder → ControllerContext
            run_count = 0
            async for run in MCTSStrategy().solve(
                problem=problem,
                verifier=verifier,
                capabilities=capabilities,
                config=config,
                memory=memory,
                events=events,
                ctx=ctx,
                campaign_id=campaign_id,
                pause_event=pause_event,
                sequence_offset=sequence_offset,
                providers=builder_providers,
                pause_check=pause_check,
            ):
                run_count += 1

                # 10. Run GPD invariant checks on solution text
                if invariant_checks and run.solution and run.solution.code:
                    violations = _run_invariant_checks(invariant_checks, run.solution.code)
                    if violations:
                        await events.emit(
                            "gpd_invariant_violations",
                            {
                                "run_id": str(run.id),
                                "violations": violations,
                                "score": run.score.value,
                            },
                        )
                        logfire.info(
                            "gpd_violations_detected",
                            run_id=str(run.id),
                            violation_count=len(violations),
                        )

                yield run

            span.set_attribute("gpd.total_runs", run_count)
            await events.emit(
                "gpd_strategy_completed",
                {"total_runs": run_count, "domain": domain},
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_error_catalog_optional(domain: str | None) -> list[ErrorClass]:
    """Load error catalog, returning empty list when unavailable.

    The error catalog is a purely optional strategy enhancement — it enriches
    CommitGate invariant checks but is never required.  Loader initialization
    or reference file issues result in an empty catalog, not a crash.
    """
    try:
        loader = get_loader()
    except (LoaderError, OSError, RuntimeError) as exc:
        logger.info("gpd_error_catalog_skipped", extra={"reason": str(exc)})
        return []
    if loader is None:
        logger.info("gpd_error_catalog_skipped: no loader available")
        return []
    try:
        return _load_error_catalog(loader, domain)
    except LoaderError as exc:
        logger.info("gpd_error_catalog_load_skipped", extra={"reason": str(exc)})
        return []


def _run_invariant_checks(
    checks: list[object],
    solution_text: str,
) -> list[str]:
    """Run GPD invariant checks against a solution's text content.

    Returns combined list of violation strings from all checks.
    """
    payload: dict[str, object] = {"solution": {"text": solution_text}}
    ctx: dict[str, object] = {}
    violations: list[str] = []

    for check_fn in checks:
        result = check_fn(payload, ctx)
        if isinstance(result, list):
            violations.extend(result)

    return violations
