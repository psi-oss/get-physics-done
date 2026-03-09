"""Shared Pydantic models for subagent communication.

Defines request/result types for tool fixing, tool creation, and status updates
used across the subagent spawning infrastructure.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field


class SubagentResult(BaseModel):
    """Generic result wrapper for any subagent call."""

    success: bool
    result_text: str
    cost_usd: float = 0.0
    session_id: str | None = None
    duration_seconds: float = 0.0


class ToolFixRequest(BaseModel):
    """Request to fix a broken tool via MCP Builder subagent."""

    mcp_name: str
    error_id: int
    error_summary: str
    error_type: str
    fix_complexity: str
    timeout_seconds: int


class ToolFixResult(BaseModel):
    """Result from fixing a tool."""

    success: bool
    mcp_name: str
    version_hash: str | None = None
    cost_usd: float = 0.0
    error_message: str | None = None


class ToolCreateContext(BaseModel):
    """Structured context for MCP Builder when creating a new tool.

    Per MCP-05 locked decision: rich typed context including research question,
    domain, expected I/O, similar tools, and requesting milestone details.
    Replaces the flat string approach in ToolCreateRequest.research_context.
    """

    research_question: str
    """The full research question driving this tool creation."""

    domain: str
    """Physics domain (e.g., 'cfd', 'quantum', 'md')."""

    expected_inputs: list[dict[str, str]] = Field(default_factory=list)
    """Expected input parameters with name and type/description."""

    expected_outputs: list[dict[str, str]] = Field(default_factory=list)
    """Expected output fields with name and type/description."""

    similar_tools: list[str] = Field(default_factory=list)
    """Names of existing tools in the catalog that are similar."""

    requesting_milestone_id: str = ""
    """ID of the milestone that needs this tool."""

    requesting_milestone_description: str = ""
    """Description of what the milestone is trying to accomplish."""


class ToolCreateRequest(BaseModel):
    """Request to create a new tool via MCP Builder subagent."""

    name: str
    domain: str
    description: str
    inputs: list[dict[str, str]]
    outputs: list[dict[str, str]]
    similar_tools: list[str] = []
    research_context: str

    context: ToolCreateContext | None = None
    """Structured context for richer MCP Builder input. When present, takes priority over flat research_context field."""


class ToolCreateResult(BaseModel):
    """Result from creating a tool."""

    success: bool
    mcp_name: str | None = None
    deploy_url: str | None = None
    cost_usd: float = 0.0
    error_message: str | None = None


class SubagentStatus(BaseModel):
    """Status update for display layer."""

    agent_name: str
    message: str
    is_subagent_message: bool = False
    timestamp: float = 0.0

    def __init__(self, **data: object) -> None:
        if "timestamp" not in data or data["timestamp"] == 0.0:
            data["timestamp"] = time.time()
        super().__init__(**data)
