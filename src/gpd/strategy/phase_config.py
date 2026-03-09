"""Phase-aware MCTS config provider for dynamic parameter adjustment.

Detects the current research phase (formulation / derivation / validation)
from live DAG statistics and returns PUCT override parameters. The
controller calls ``get_overrides(dag_stats)`` each step; the provider
returns ``None`` when the phase hasn't changed to avoid unnecessary
reconfiguration.

Phase detection is purely arithmetic (budget fraction, score, depth) ---
no LLM calls.

Default phase configs ship in ``specs/physics/config/phase_defaults.yaml``
and can be overridden per-project via a YAML file at
``.planning/phase_config.yaml``.

Layer 1 code: stdlib + pydantic + pyyaml only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase names
# ---------------------------------------------------------------------------

PHASE_FORMULATION = "formulation"
PHASE_DERIVATION = "derivation"
PHASE_VALIDATION = "validation"

_VALID_PHASES = frozenset({PHASE_FORMULATION, PHASE_DERIVATION, PHASE_VALIDATION})

# ---------------------------------------------------------------------------
# PhaseConfig (frozen dataclass)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhaseConfig:
    """Immutable config for a single research phase."""

    c_puct: float = 1.2
    prior_multipliers: dict[str, float] = field(default_factory=dict)
    bundle_period: int = 10
    verification_threshold: float = 0.5
    compaction_enabled: bool = False


# ---------------------------------------------------------------------------
# Default configs (code constants, overridable via YAML)
# ---------------------------------------------------------------------------

DEFAULT_PHASE_CONFIGS: dict[str, PhaseConfig] = {
    PHASE_FORMULATION: PhaseConfig(
        c_puct=2.0,
        prior_multipliers={"Plan": 1.5, "Strategize": 1.5, "Ground": 2.0, "Work": 0.5},
        bundle_period=5,
        verification_threshold=0.3,
        compaction_enabled=False,
    ),
    PHASE_DERIVATION: PhaseConfig(
        c_puct=1.2,
        prior_multipliers={"Work": 1.5, "Ground": 0.8},
        bundle_period=10,
        verification_threshold=0.5,
        compaction_enabled=False,
    ),
    PHASE_VALIDATION: PhaseConfig(
        c_puct=0.6,
        prior_multipliers={"CritiqueImprove": 1.5, "SolveImprove": 1.5, "Work": 0.5},
        bundle_period=20,
        verification_threshold=0.7,
        compaction_enabled=True,
    ),
}

# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

# Path to the shipped defaults
_SHIPPED_DEFAULTS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "specs" / "physics" / "config" / "phase_defaults.yaml"
)


def _parse_phase_config(raw: dict[str, object]) -> PhaseConfig:
    """Parse a single phase config entry from a YAML dict."""
    multipliers_raw = raw.get("prior_multipliers")
    multipliers: dict[str, float] = {}
    if isinstance(multipliers_raw, dict):
        multipliers = {str(k): float(v) for k, v in multipliers_raw.items()}

    return PhaseConfig(
        c_puct=float(raw.get("c_puct", 1.2)),
        prior_multipliers=multipliers,
        bundle_period=int(raw.get("bundle_period", 10)),
        verification_threshold=float(raw.get("verification_threshold", 0.5)),
        compaction_enabled=bool(raw.get("compaction_enabled", False)),
    )


def load_phase_configs_from_yaml(path: Path) -> dict[str, PhaseConfig]:
    """Load phase configs from a YAML file.

    Each top-level key must be a valid phase name. Unknown phases are
    silently skipped to allow forward compatibility.

    Raises:
        FileNotFoundError: If *path* does not exist.
        yaml.YAMLError: If the file is malformed YAML.
        ValueError: If the top-level value is not a mapping.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected YAML mapping at top level, got {type(raw).__name__}")

    configs: dict[str, PhaseConfig] = {}
    for phase_name, phase_raw in raw.items():
        if phase_name not in _VALID_PHASES:
            logger.warning("unknown_phase_in_yaml", extra={"phase": phase_name, "path": str(path)})
            continue
        if not isinstance(phase_raw, dict):
            logger.warning("invalid_phase_entry", extra={"phase": phase_name, "path": str(path)})
            continue
        configs[phase_name] = _parse_phase_config(phase_raw)

    return configs


def load_phase_configs(project_dir: Path | None = None) -> dict[str, PhaseConfig]:
    """Load phase configs with override precedence.

    Resolution order:
        1. Project-level ``.planning/phase_config.yaml`` (highest priority)
        2. Shipped defaults at ``specs/physics/config/phase_defaults.yaml``
        3. Hard-coded ``DEFAULT_PHASE_CONFIGS`` (lowest)

    Returns the merged config dict.
    """
    # Start from hard-coded defaults
    merged = dict(DEFAULT_PHASE_CONFIGS)

    # Layer shipped YAML defaults
    if _SHIPPED_DEFAULTS_PATH.is_file():
        try:
            shipped = load_phase_configs_from_yaml(_SHIPPED_DEFAULTS_PATH)
            merged.update(shipped)
        except (yaml.YAMLError, ValueError, OSError) as exc:
            logger.warning("shipped_phase_defaults_load_failed", extra={"error": str(exc)})

    # Layer project overrides
    if project_dir is not None:
        project_yaml = project_dir / ".planning" / "phase_config.yaml"
        if project_yaml.is_file():
            try:
                project_configs = load_phase_configs_from_yaml(project_yaml)
                merged.update(project_configs)
            except (yaml.YAMLError, ValueError, OSError) as exc:
                logger.warning("project_phase_config_load_failed", extra={"error": str(exc)})

    return merged


# ---------------------------------------------------------------------------
# Phase detection
# ---------------------------------------------------------------------------


def detect_phase(dag_stats: dict[str, object]) -> str:
    """Detect the current research phase from DAG statistics.

    Args:
        dag_stats: Dictionary with keys:
            - budget_fraction_remaining (float): fraction of node budget left (0..1)
            - avg_score (float): rolling average verifier score (0..1)
            - score_trend (float): score derivative (positive = improving)
            - node_count (int): total nodes in the DAG
            - max_depth (int): deepest node depth

    Returns:
        One of ``"formulation"``, ``"derivation"``, or ``"validation"``.
    """
    budget = float(dag_stats.get("budget_fraction_remaining", 1.0))
    avg_score = float(dag_stats.get("avg_score", 0.0))
    node_count = int(dag_stats.get("node_count", 0))

    # Early stage: lots of budget left and few nodes explored
    if budget > 0.7 and node_count < 10:
        return PHASE_FORMULATION

    # Late stage: low budget or strong scores
    if budget < 0.3 or avg_score > 0.6:
        return PHASE_VALIDATION

    # Mid stage: budget consumed but scores still moderate
    if budget > 0.3 and avg_score < 0.5:
        return PHASE_DERIVATION

    # Fallback
    return PHASE_DERIVATION


# ---------------------------------------------------------------------------
# PhaseConfigProvider
# ---------------------------------------------------------------------------


class PhaseConfigProvider:
    """Provides dynamic MCTS parameter overrides based on detected phase.

    Implements the ``PhaseConfigProvider`` protocol from
    ``agentic_builder.engine.extension_protocols``.

    Usage::

        provider = PhaseConfigProvider()
        overrides = provider.get_overrides(dag_stats)
        if overrides is not None:
            controller.reconfigure(**overrides)
    """

    def __init__(
        self,
        phase_configs: dict[str, PhaseConfig] | None = None,
        project_dir: Path | None = None,
    ) -> None:
        if phase_configs is not None:
            self._configs = dict(phase_configs)
        else:
            self._configs = load_phase_configs(project_dir)
        self._last_phase: str | None = None

    @property
    def configs(self) -> dict[str, PhaseConfig]:
        """Current phase config mapping (read-only snapshot)."""
        return dict(self._configs)

    @property
    def last_phase(self) -> str | None:
        """The last detected phase, or None if never called."""
        return self._last_phase

    def get_overrides(self, dag_stats: dict[str, object]) -> dict[str, object] | None:
        """Return PUCT overrides for the current phase, or None if unchanged.

        The returned dict has keys matching what ``Controller.reconfigure()``
        accepts (currently ``c_puct`` and ``prior_multipliers``).
        """
        phase = detect_phase(dag_stats)

        if phase == self._last_phase:
            return None

        self._last_phase = phase
        config = self._configs.get(phase)
        if config is None:
            logger.warning("no_config_for_phase", extra={"phase": phase})
            return None

        logger.info(
            "phase_transition",
            extra={
                "from_phase": self._last_phase,
                "to_phase": phase,
                "c_puct": config.c_puct,
                "bundle_period": config.bundle_period,
            },
        )

        return {
            "c_puct": config.c_puct,
            "prior_multipliers": dict(config.prior_multipliers),
        }
