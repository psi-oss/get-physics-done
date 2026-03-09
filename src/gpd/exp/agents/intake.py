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


_clarification_agent: Agent[None, ClarificationQuestion | ClarifiedSpec] | None = None
_feasibility_agent: Agent[None, FeasibilityResult] | None = None


def get_clarification_agent() -> Agent[None, ClarificationQuestion | ClarifiedSpec]:
    """Return the clarification agent, creating it on first call.

    Defers Agent construction so the module can be imported without
    an API key set in the environment.
    """
    global _clarification_agent
    if _clarification_agent is None:
        _clarification_agent = Agent(
            model=GPD_DEFAULT_MODEL,
            output_type=[ClarificationQuestion, ClarifiedSpec],  # type: ignore[arg-type]
            instructions=CLARIFICATION_SYSTEM_PROMPT,
            retries=2,
        )
    return _clarification_agent


def get_feasibility_agent() -> Agent[None, FeasibilityResult]:
    """Return the feasibility agent, creating it on first call.

    Defers Agent construction so the module can be imported without
    an API key set in the environment.
    """
    global _feasibility_agent
    if _feasibility_agent is None:
        _feasibility_agent = Agent(
            model=GPD_DEFAULT_MODEL,
            output_type=FeasibilityResult,
            instructions=FEASIBILITY_SYSTEM_PROMPT,
            retries=2,
        )
    return _feasibility_agent
