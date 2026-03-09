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

ethics_agent: Agent[None, EthicsScreeningResult] = Agent(
    model=GPD_DEFAULT_MODEL,
    output_type=EthicsScreeningResult,
    instructions=ETHICS_SYSTEM_PROMPT,
    retries=2,
)
