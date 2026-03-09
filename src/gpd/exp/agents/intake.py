"""PydanticAI agent definitions for the question intake pipeline.

Defines the clarification agent (multi-turn dialog to refine research questions)
and the feasibility agent (classifies questions into rejection categories).
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent

from gpd.core.model_defaults import GPD_DEFAULT_MODEL
from gpd.exp.agents.prompts import CLARIFICATION_SYSTEM_PROMPT, FEASIBILITY_SYSTEM_PROMPT
from gpd.exp.contracts.feasibility import FeasibilityResult


class ClarificationQuestion(BaseModel):
    """Agent output requesting more information from the user.

    Returned when the research question needs clarification before
    a full ClarifiedSpec can be built.
    """

    question: str
    reason: str


class ClarifiedSpec(BaseModel):
    """Agent output when the research question is sufficiently clarified.

    Contains the refined question and all extracted or estimated constraints
    needed to construct an ExperimentSpec.
    """

    question: str
    budget_cap_cents: int = 0
    deadline_hours: int | None = None
    domain: str
    constraints: list[str]


clarification_agent: Agent[None, ClarificationQuestion | ClarifiedSpec] = Agent(
    model=GPD_DEFAULT_MODEL,
    output_type=[ClarificationQuestion, ClarifiedSpec],  # type: ignore[arg-type]
    instructions=CLARIFICATION_SYSTEM_PROMPT,
    retries=2,
)

feasibility_agent: Agent[None, FeasibilityResult] = Agent(
    model=GPD_DEFAULT_MODEL,
    output_type=FeasibilityResult,
    instructions=FEASIBILITY_SYSTEM_PROMPT,
    retries=2,
)
