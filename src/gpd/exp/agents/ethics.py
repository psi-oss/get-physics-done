"""PydanticAI ethics screening agent for the experiment design pipeline.

Defines the ethics_agent that screens research protocols for ethical concerns.
This agent is a HARD GATE -- if ethics_passed=False, the pipeline stops.
There is no user override.
"""

from __future__ import annotations

from pydantic_ai import Agent

from gpd.core.model_defaults import GPD_DEFAULT_MODEL
from gpd.exp.agents.prompts import ETHICS_SYSTEM_PROMPT
from gpd.exp.contracts.feasibility import EthicsScreeningResult

_ethics_agent: Agent[None, EthicsScreeningResult] | None = None


def get_ethics_agent() -> Agent[None, EthicsScreeningResult]:
    """Return the ethics screening agent, creating it on first call.

    Defers Agent construction so the module can be imported without
    an API key set in the environment.
    """
    global _ethics_agent
    if _ethics_agent is None:
        _ethics_agent = Agent(
            model=GPD_DEFAULT_MODEL,
            output_type=EthicsScreeningResult,
            instructions=ETHICS_SYSTEM_PROMPT,
            retries=2,
        )
    return _ethics_agent
