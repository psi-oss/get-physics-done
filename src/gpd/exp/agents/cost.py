"""PydanticAI cost estimation agent for the experiment pipeline.

Estimates the base bounty price per task for an experimental protocol.
The cost domain (domain/cost_estimation.py) uses this unit price to compute
the full experiment cost with retries and confidence range.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from gpd.core.model_defaults import GPD_DEFAULT_MODEL
from gpd.exp.agents.prompts import COST_ESTIMATION_SYSTEM_PROMPT


class CostAgentOutput(BaseModel):
    """Output from the cost estimation agent.

    base_bounty_price_cents: Unit price per human task in integer US cents.
        Must be >= 100 (absolute floor for any task).
    reasoning: Explanation of the pricing decision.
    """

    base_bounty_price_cents: int = Field(ge=100)
    reasoning: str


cost_agent: Agent[None, CostAgentOutput] = Agent(
    model=GPD_DEFAULT_MODEL,
    output_type=CostAgentOutput,
    instructions=COST_ESTIMATION_SYSTEM_PROMPT,
    retries=2,
)
