"""Physics curator agent for blackboard write gating.

Implements the WriteGateProvider protocol from engine/blackboard_protocol.py
using a PydanticAI agent to evaluate whether proposed knowledge items should
be added to the shared solver blackboard.

The curator is the gatekeeper for global solver state — it prevents
branch-specific intermediates, unverified conjectures, and duplicates
from polluting the shared blackboard.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from psi_contracts.blackboard import BlackboardWriteRequest, CurationDecision
from pydantic import BaseModel, Field

from gpd.core.model_defaults import GPD_DEFAULT_FAST_MODEL
from gpd.specs import SPECS_DIR

logger = logging.getLogger(__name__)

# Default prompt path — loaded from specs/physics/agents/curator.md
_DEFAULT_PROMPT_PATH = SPECS_DIR / "physics" / "agents" / "curator.md"

_FALLBACK_PROMPT = (
    "You are a knowledge curator. Evaluate whether proposed entries should be "
    "added to a shared knowledge store. Approve verified, global, non-duplicate "
    "entries. Reject unverified conjectures, branch-specific intermediates, and duplicates."
)


# ---------------------------------------------------------------------------
# Structured output for batch evaluation
# ---------------------------------------------------------------------------


class CurationBatch(BaseModel):
    """Structured output from the curator agent for a batch of requests."""

    decisions: list[CurationDecision] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------


def _load_prompt(path: Path | None) -> str:
    """Load the curator system prompt from a markdown file.

    Raises FileNotFoundError if the specified path does not exist.
    Falls back to a minimal inline prompt only when no path is given
    and the default file is missing.
    """
    if path is not None:
        return path.read_text(encoding="utf-8")

    if _DEFAULT_PROMPT_PATH.is_file():
        return _DEFAULT_PROMPT_PATH.read_text(encoding="utf-8")

    logger.warning("curator_prompt_not_found: using fallback prompt (path=%s)", _DEFAULT_PROMPT_PATH)
    return _FALLBACK_PROMPT


# ---------------------------------------------------------------------------
# Agent factory (lazy creation)
# ---------------------------------------------------------------------------

_AGENT_CACHE: dict[str, object] = {}


def _get_curator_agent(model_id: str, prompt: str):
    """Lazily create (and cache) the PydanticAI curator agent."""
    cache_key = f"{model_id}:{hash(prompt)}"
    if cache_key in _AGENT_CACHE:
        return _AGENT_CACHE[cache_key]

    from pydantic_ai import Agent

    agent = Agent(
        model_id,
        output_type=CurationBatch,
        system_prompt=prompt,
        retries=2,
    )
    _AGENT_CACHE[cache_key] = agent
    return agent


# ---------------------------------------------------------------------------
# PhysicsCurator — WriteGateProvider implementation
# ---------------------------------------------------------------------------


class PhysicsCurator:
    """Curator agent that gates writes to the shared solver blackboard.

    Implements the WriteGateProvider protocol (structural subtyping):
        - evaluate(request, current_state) -> CurationDecision
        - evaluate_batch(requests, current_state) -> list[CurationDecision]

    Uses a PydanticAI Agent with haiku-tier model for fast, cheap evaluation.
    Thread-safe via asyncio.Lock.
    """

    def __init__(
        self,
        model_id: str = GPD_DEFAULT_FAST_MODEL,
        prompt_path: Path | None = None,
        max_batch_size: int = 10,
    ) -> None:
        self._model_id = model_id
        self._prompt = _load_prompt(prompt_path)
        self._max_batch_size = max_batch_size
        self._lock = asyncio.Lock()

    async def evaluate(
        self,
        request: BlackboardWriteRequest,
        current_state: dict[str, object],
    ) -> CurationDecision:
        """Evaluate a single blackboard write request.

        Returns a CurationDecision indicating whether the write is approved.
        """
        decisions = await self.evaluate_batch([request], current_state)
        return decisions[0]

    async def evaluate_batch(
        self,
        requests: list[BlackboardWriteRequest],
        current_state: dict[str, object],
    ) -> list[CurationDecision]:
        """Evaluate a batch of blackboard write requests.

        Splits into chunks of max_batch_size and processes sequentially
        under the lock to avoid concurrent agent calls.
        """
        if not requests:
            return []

        all_decisions: list[CurationDecision] = []
        async with self._lock:
            for i in range(0, len(requests), self._max_batch_size):
                chunk = requests[i : i + self._max_batch_size]
                decisions = await self._evaluate_chunk(chunk, current_state)
                all_decisions.extend(decisions)

        return all_decisions

    async def _evaluate_chunk(
        self,
        requests: list[BlackboardWriteRequest],
        current_state: dict[str, object],
    ) -> list[CurationDecision]:
        """Evaluate a single chunk of requests via the PydanticAI agent."""
        prompt = self._build_prompt(requests, current_state)
        agent = _get_curator_agent(self._model_id, self._prompt)
        result = await agent.run(prompt)

        decisions = result.output.decisions

        # Pad or truncate to match request count
        while len(decisions) < len(requests):
            decisions.append(
                CurationDecision(
                    approved=False,
                    reason="Curator did not return a decision for this request.",
                )
            )
        return decisions[: len(requests)]

    @staticmethod
    def _build_prompt(
        requests: list[BlackboardWriteRequest],
        current_state: dict[str, object],
    ) -> str:
        """Build the user prompt from requests and current blackboard state."""
        parts: list[str] = []

        # Current blackboard state summary
        if current_state:
            parts.append("## Current Blackboard State")
            for key, value in current_state.items():
                parts.append(f"- **{key}**: {value}")
            parts.append("")

        # Proposed writes
        parts.append("## Proposed Writes")
        for idx, req in enumerate(requests, 1):
            parts.append(f"### Request {idx}")
            parts.append(f"- **Kind**: {req.kind}")
            parts.append(f"- **Content**: {req.content}")
            if req.tags:
                parts.append(f"- **Tags**: {', '.join(req.tags)}")
            if req.source_branch:
                parts.append(f"- **Source branch**: {req.source_branch}")
            parts.append(f"- **Confidence**: {req.confidence}")
            evidence_ids = getattr(req, "evidence_ids", None)
            if evidence_ids:
                parts.append(f"- **Evidence IDs**: {', '.join(evidence_ids)}")
            parts.append("")

        parts.append(f"Evaluate each of the {len(requests)} proposed write(s) and return a CurationDecision for each.")
        return "\n".join(parts)
