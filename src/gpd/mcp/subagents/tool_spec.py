"""Collaborative tool specification protocol.

GPD+ drafts an initial tool specification using a PydanticAI agent,
then converts it to a ToolCreateRequest for MCP Builder to build.
The MCP Builder prompt includes instructions to refine the spec if needed.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel
from pydantic_ai import Agent

from gpd.core.model_defaults import GPD_DEFAULT_MODEL, resolve_model_and_settings
from gpd.mcp.subagents.models import ToolCreateRequest

logger = logging.getLogger(__name__)

SPEC_DRAFTING_PROMPT: str = (
    "You are a physics simulation tool architect. Given a capability gap "
    "description and research context, draft a precise tool specification. "
    "Focus on: what physics the tool simulates, what inputs it needs "
    "(parameters, initial conditions), what outputs it produces (fields, "
    "scalars, time series), and what existing tools are similar."
)


class ToolSpec(BaseModel):
    """Specification for a new physics simulation tool."""

    name: str
    """Proposed tool name (snake_case)."""

    domain: str
    """Physics domain (should match a PhysicsCategory name)."""

    description: str
    """What the tool does."""

    inputs: list[dict[str, str]]
    """List of {"name": ..., "type": ..., "description": ...}."""

    outputs: list[dict[str, str]]
    """List of {"name": ..., "type": ..., "description": ...}."""

    expected_behavior: str
    """How the tool should behave."""

    similar_tools: list[str] = []
    """Existing tools for reference."""

    constraints: list[str] = []
    """Constraints (e.g., "must run on Modal", "must support batch")."""


class ToolSpecDrafter:
    """Drafts tool specifications using PydanticAI Agent."""

    def __init__(self, model: str = GPD_DEFAULT_MODEL) -> None:
        base_model, self._model_settings = resolve_model_and_settings(model)
        self._agent: Agent[None, ToolSpec] = Agent(
            base_model,
            output_type=ToolSpec,
            system_prompt=SPEC_DRAFTING_PROMPT,
            retries=2,
        )

    async def draft(
        self,
        capability_gap: str,
        research_context: str,
        available_tools: list[str],
    ) -> ToolSpec:
        """Draft a tool specification from a capability gap description."""
        tools_str = ", ".join(available_tools) if available_tools else "none"
        user_prompt = (
            f"## Capability Gap\n{capability_gap}\n\n"
            f"## Research Context\n{research_context}\n\n"
            f"## Available Tools (for reference)\n{tools_str}"
        )
        result = await self._agent.run(user_prompt, model_settings=self._model_settings)
        return result.output


def spec_to_create_request(spec: ToolSpec, research_context: str) -> ToolCreateRequest:
    """Convert a ToolSpec into a ToolCreateRequest for the orchestrator."""
    return ToolCreateRequest(
        name=spec.name,
        domain=spec.domain,
        description=spec.description,
        inputs=spec.inputs,
        outputs=spec.outputs,
        similar_tools=spec.similar_tools,
        research_context=research_context,
    )
