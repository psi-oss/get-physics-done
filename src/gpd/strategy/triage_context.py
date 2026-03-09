"""Physics triage context provider for the MCTS engine.

Implements the ``TriageContextProvider`` protocol from
``agentic_builder.engine.extension_protocols``, injecting GPD physics
intelligence into triage prompts: relevant protocols, convention status,
phase signals, recommended skills, and open research questions.

Layer 1 code: stdlib + gpd.strategy internals only.
"""

from __future__ import annotations

import logging

from gpd.core.conventions import KNOWN_CONVENTIONS, is_bogus_value
from gpd.core.observability import instrument_gpd_function
from gpd.strategy.bundle_loader import ActionSpec, BundleLoader
from gpd.strategy.router import ReferenceRouter

logger = logging.getLogger(__name__)


# ─── Phase Signal Computation ────────────────────────────────────────────────


def compute_phase_signal(dag_stats: dict[str, object]) -> dict[str, object]:
    """Compute the research phase signal from DAG statistics.

    Uses budget fraction remaining, average score, and visit depth to
    classify the current research phase:

    - ``"formulation"``: Early exploration (budget > 0.7, few results).
    - ``"derivation"``: Active computation (middle budget range).
    - ``"validation"``: Late-stage refinement (budget < 0.3 or high scores).

    Returns
    -------
    dict[str, object]
        Keys: ``phase``, ``budget_fraction``, ``exploration_pressure``.
    """
    budget_fraction = _safe_float(dag_stats.get("budget_fraction_remaining"), default=1.0)
    avg_score = _safe_float(dag_stats.get("avg_score"), default=0.0)
    total_visits = _safe_int(dag_stats.get("total_visits"), default=0)

    # Phase classification
    if budget_fraction > 0.7 and total_visits < 5:
        phase = "formulation"
        exploration_pressure = 0.9
    elif budget_fraction < 0.3 or avg_score > 70.0:
        phase = "validation"
        exploration_pressure = 0.2
    else:
        phase = "derivation"
        exploration_pressure = 0.5 + 0.3 * (budget_fraction - 0.3)

    return {
        "phase": phase,
        "budget_fraction": budget_fraction,
        "exploration_pressure": round(exploration_pressure, 3),
    }


# ─── Triage Context Provider ────────────────────────────────────────────────


class PhysicsTriageContext:
    """Builds physics-aware context for MCTS triage prompts.

    Satisfies the ``TriageContextProvider`` protocol defined in
    ``agentic_builder.engine.extension_protocols``.

    Parameters
    ----------
    bundle_loader:
        Loaded BundleLoader with merged base + physics bundles.
    reference_router:
        Router for mapping computation types to protocols.
    domain:
        Physics domain string (e.g. ``"qft"``, ``"condensed matter"``).
        ``None`` for domain-agnostic context.
    """

    def __init__(
        self,
        bundle_loader: BundleLoader,
        reference_router: ReferenceRouter,
        domain: str | None = None,
    ) -> None:
        self._loader = bundle_loader
        self._router = reference_router
        self._domain = domain

    @instrument_gpd_function("triage_context.build")
    def build_context(
        self,
        state: dict[str, object],
        node_id: str,
        dag_stats: dict[str, object],
    ) -> dict[str, object]:
        """Build physics-enriched context for triage prompt injection.

        Returns a dict with keys:

        - ``mode_descriptions``: Available action modes with triage guidance.
        - ``relevant_protocols``: Protocol names relevant to the domain.
        - ``recommended_skills``: Skill names from merged bundles.
        - ``convention_summary``: Human-readable convention lock status.
        - ``phase_signal``: Current research phase and exploration pressure.
        - ``gpd_phase``: Typed phase metadata carried in the payload overlay.
        - ``open_questions``: Unresolved research questions from state.
        - ``verification_focus``: Verification checks the branch should prioritize.
        - ``required_tools``: Tools the branch expects to rely on.
        - ``shared_claims``: Cross-branch claims worth reusing or verifying.
        """
        payload_state = self._payload_state(state)
        return {
            "mode_descriptions": self._build_mode_descriptions(),
            "relevant_protocols": self._build_relevant_protocols(),
            "recommended_skills": self._build_recommended_skills(),
            "convention_summary": self._build_convention_summary(payload_state),
            "phase_signal": compute_phase_signal(dag_stats),
            "gpd_phase": self._extract_gpd_phase(payload_state),
            "open_questions": self._extract_open_questions(payload_state),
            "verification_focus": self._extract_verification_focus(payload_state),
            "required_tools": self._extract_required_tools(payload_state),
            "shared_claims": self._extract_shared_claims(payload_state),
        }

    # ─── Private Helpers ─────────────────────────────────────────────────────

    def _build_mode_descriptions(self) -> list[dict[str, object]]:
        """Extract action mode descriptions from loaded bundle specs.

        Each entry contains the action_id and a list of mode objects
        with ``mode_id``, ``summary``, and ``triage_guidance``.
        """
        merged = self._loader.merged
        if merged is None:
            return []

        descriptions: list[dict[str, object]] = []
        for action_id in sorted(merged.actions):
            action = merged.actions[action_id]
            modes = _extract_action_modes(action)
            if modes:
                descriptions.append({"action_id": action_id, "modes": modes})

        return descriptions

    def _build_relevant_protocols(self) -> list[str]:
        """Find protocols relevant to the physics domain via the router."""
        if not self._domain:
            return []

        protocol = self._router.route_protocol(self._domain)
        if protocol is None:
            return []
        return [protocol]

    def _build_recommended_skills(self) -> list[str]:
        """Return skill names from the merged bundle."""
        return self._loader.get_skill_names()

    def _build_convention_summary(self, state: dict[str, object]) -> str:
        """Build a human-readable convention lock summary.

        Reads ``convention_lock`` from state and counts how many of
        the 18 canonical fields are set.
        """
        lock_data = state.get("convention_lock")
        if not isinstance(lock_data, dict):
            return f"0/{len(KNOWN_CONVENTIONS)} conventions locked"

        set_count = 0
        for key in KNOWN_CONVENTIONS:
            val = lock_data.get(key)
            if not is_bogus_value(val):
                set_count += 1

        return f"{set_count}/{len(KNOWN_CONVENTIONS)} conventions locked"

    def _payload_state(self, state: dict[str, object]) -> dict[str, object]:
        payload = state.get("payload")
        if isinstance(payload, dict):
            return payload
        return state

    def _extract_gpd(self, state: dict[str, object]) -> dict[str, object]:
        raw = state.get("gpd")
        if not isinstance(raw, dict):
            return {}
        return raw

    def _extract_gpd_phase(self, state: dict[str, object]) -> dict[str, object]:
        gpd = self._extract_gpd(state)
        raw = gpd.get("phase")
        if not isinstance(raw, dict):
            return {}
        phase_id = raw.get("id")
        phase_name = raw.get("name")
        status = raw.get("status")
        result: dict[str, object] = {}
        if isinstance(phase_id, str) and phase_id.strip():
            result["id"] = phase_id.strip()
        if isinstance(phase_name, str) and phase_name.strip():
            result["name"] = phase_name.strip()
        if isinstance(status, str) and status.strip():
            result["status"] = status.strip()
        return result

    def _extract_open_questions(self, state: dict[str, object]) -> list[str]:
        """Extract open questions from state."""
        gpd = self._extract_gpd(state)
        raw = gpd.get("open_questions")
        if not isinstance(raw, list):
            raw = state.get("open_questions")
        if not isinstance(raw, list):
            return []

        questions: list[str] = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                questions.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text") or item.get("question") or item.get("description", "")
                if isinstance(text, str) and text.strip():
                    questions.append(text.strip())
        return questions

    def _extract_verification_focus(self, state: dict[str, object]) -> list[dict[str, str]]:
        gpd = self._extract_gpd(state)
        raw = gpd.get("verification_focus")
        if not isinstance(raw, list):
            return []

        result: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            check_id = item.get("id")
            check = item.get("check")
            if not (isinstance(check_id, str) and check_id.strip() and isinstance(check, str) and check.strip()):
                continue
            row = {"id": check_id.strip(), "check": check.strip()}
            priority = item.get("priority")
            rationale = item.get("rationale")
            if isinstance(priority, str) and priority.strip():
                row["priority"] = priority.strip()
            if isinstance(rationale, str) and rationale.strip():
                row["rationale"] = rationale.strip()
            result.append(row)
        return result

    def _extract_required_tools(self, state: dict[str, object]) -> list[dict[str, object]]:
        gpd = self._extract_gpd(state)
        raw = gpd.get("required_tools")
        if not isinstance(raw, list):
            return []

        result: list[dict[str, object]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            purpose = item.get("purpose")
            if not (isinstance(name, str) and name.strip() and isinstance(purpose, str) and purpose.strip()):
                continue
            row: dict[str, object] = {"name": name.strip(), "purpose": purpose.strip()}
            if "required" in item:
                row["required"] = bool(item.get("required"))
            result.append(row)
        return result

    def _extract_shared_claims(self, state: dict[str, object]) -> list[dict[str, object]]:
        gpd = self._extract_gpd(state)
        raw = gpd.get("shared_claims")
        if not isinstance(raw, list):
            return []

        result: list[dict[str, object]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            claim_id = item.get("id")
            claim = item.get("claim")
            if not (isinstance(claim_id, str) and claim_id.strip() and isinstance(claim, str) and claim.strip()):
                continue
            row: dict[str, object] = {"id": claim_id.strip(), "claim": claim.strip()}
            status = item.get("status")
            if isinstance(status, str) and status.strip():
                row["status"] = status.strip()
            confidence = item.get("confidence")
            if isinstance(confidence, (int, float)):
                row["confidence"] = float(confidence)
            result.append(row)
        return result


# ─── Internal Helpers ────────────────────────────────────────────────────────


def _extract_action_modes(action: ActionSpec) -> list[dict[str, str]]:
    """Extract mode descriptions from an ActionSpec.

    Modes may be defined in the ``extra`` dict under the ``modes`` key,
    or inferred from the action's own triage_guidance if no explicit
    modes exist.
    """
    modes_raw = action.extra.get("modes") if action.extra else None
    if isinstance(modes_raw, list):
        result: list[dict[str, str]] = []
        for m in modes_raw:
            if isinstance(m, dict) and "mode_id" in m:
                result.append(
                    {
                        "mode_id": str(m["mode_id"]),
                        "summary": str(m.get("summary", "")),
                        "triage_guidance": str(m.get("triage_guidance", "")),
                    }
                )
        return result

    # No explicit modes — synthesize a default-mode entry from triage_guidance
    if action.triage_guidance:
        return [
            {
                "mode_id": "default",
                "summary": action.summary or action.title,
                "triage_guidance": action.triage_guidance,
            }
        ]

    return []


def _safe_float(value: object, *, default: float) -> float:
    """Convert a value to float, returning default on failure."""
    if value is None:
        return default
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, *, default: int) -> int:
    """Convert a value to int, returning default on failure."""
    if value is None:
        return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
