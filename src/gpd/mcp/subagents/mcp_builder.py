"""MCP Builder AgentDefinition factory and prompt construction.

Defines the MCP Builder subagent identity, system prompt, and prompt
formatting for fix and create workflows. Parses structured JSON results
from raw subagent output.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from gpd.mcp.subagents.models import (
    SubagentResult,
    ToolCreateRequest,
    ToolCreateResult,
    ToolFixRequest,
    ToolFixResult,
)

logger = logging.getLogger(__name__)

MCP_BUILDER_SYSTEM_PROMPT: str = """You are MCP Builder, an autonomous MCP server construction agent.

You have access to the MCP Builder construction pipeline at:
  psi/apps/mcp-builder/construction/

Your capabilities:
1. CREATE new MCP servers: run_construction_pipeline(question, capability_gap)
2. EDIT existing servers: run_edit_pipeline(mcp_name, tool_description=..., patch_description=...)
3. DIAGNOSE errors: diagnose_error(error_id) from mcp_error_db
4. DEBUG sessions: run_debug_session(mcp_name, user_message, error_id=...)

When asked to fix a tool failure:
1. Read the error details (error_id, stack trace, tool name)
2. Load the server source code
3. Diagnose the root cause
4. Apply the fix via run_edit_pipeline with patch_description
5. Return: {"success": true/false, "mcp_name": "...", "version_hash": "..."}

When asked to create a new tool:
1. Review the tool specification (inputs, outputs, physics domain)
2. Refine the spec if needed
3. Run the construction pipeline
4. Return: {"success": true/false, "mcp_name": "...", "deploy_url": "..."}

Always return structured JSON results. Never ask for user approval -- work autonomously."""

MCP_BUILDER_TOOLS: list[str] = ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
"""Tools available to MCP Builder subagent. Explicitly excludes 'Task' (subagents cannot spawn subagents)."""


def get_mcp_builder_cwd() -> str:
    """Return the absolute path to psi/apps/mcp-builder/.

    Resolves relative to this file: walk up from gpd.mcp package to psi root,
    then down to apps/mcp-builder.
    """
    # __file__ is .../psi/packages/gpd/src/gpd/mcp/subagents/mcp_builder.py
    # Walk up to psi root: subagents -> mcp -> gpd -> src -> gpd -> packages -> psi
    psi_root = Path(__file__).resolve().parents[6]
    mcp_builder_dir = psi_root / "apps" / "mcp-builder"
    if mcp_builder_dir.is_dir():
        return str(mcp_builder_dir)
    # Fallback: try relative from cwd
    fallback = Path.cwd() / "psi" / "apps" / "mcp-builder"
    if fallback.is_dir():
        return str(fallback)
    return str(mcp_builder_dir)


def create_mcp_builder_definition() -> object:
    """Create the MCP Builder AgentDefinition for subagent spawning.

    Returns an AgentDefinition (from claude_agent_sdk) with the MCP Builder
    system prompt, tools, and model configuration.

    Raises:
        RuntimeError: If claude-agent-sdk is not installed.
    """
    try:
        from claude_agent_sdk import AgentDefinition
    except ImportError:
        raise RuntimeError("claude-agent-sdk not installed. Run: pip install claude-agent-sdk") from None

    return AgentDefinition(
        description=(
            "MCP Builder specialist. Use when: (1) a tool fails and needs fixing, "
            "(2) no existing tool covers a needed capability, or (3) an existing "
            "tool needs a new feature added. Builds, tests, and deploys MCP servers."
        ),
        prompt=MCP_BUILDER_SYSTEM_PROMPT,
        tools=MCP_BUILDER_TOOLS,
        model="sonnet",
    )


def build_fix_prompt(request: ToolFixRequest) -> str:
    """Format a prompt for fixing a broken tool via MCP Builder."""
    return f"""A tool failure occurred during research.

MCP: {request.mcp_name}
Error ID: {request.error_id}
Error Summary: {request.error_summary}
Error Type: {request.error_type}
Fix Complexity: {request.fix_complexity}

Use the mcp-builder agent to diagnose and fix this error.
The agent should:
1. Run diagnose_error({request.error_id}) to get structured diagnosis
2. Apply the fix via run_edit_pipeline("{request.mcp_name}", patch_description=<diagnosis fix>)
3. Return the result as JSON: {{"success": bool, "mcp_name": str, "version_hash": str}}
"""


def build_create_prompt(request: ToolCreateRequest) -> str:
    """Format a prompt for creating a new tool via MCP Builder.

    When request.context (ToolCreateContext) is present, formats the prompt
    with structured sections for richer MCP Builder input. Falls back to
    flat research_context formatting when context is not provided.
    """
    similar = ", ".join(request.similar_tools) if request.similar_tools else "none"
    inputs_str = json.dumps(request.inputs, indent=2)
    outputs_str = json.dumps(request.outputs, indent=2)

    # Use structured ToolCreateContext when available
    if request.context is not None:
        ctx = request.context
        ctx_inputs = "\n".join(f"  - {inp.get('name', '?')}: {inp.get('type', '?')}" for inp in ctx.expected_inputs)
        ctx_outputs = "\n".join(f"  - {out.get('name', '?')}: {out.get('type', '?')}" for out in ctx.expected_outputs)
        ctx_similar = ", ".join(ctx.similar_tools) if ctx.similar_tools else "none"

        context_block = f"""RESEARCH QUESTION: {ctx.research_question}
PHYSICS DOMAIN: {ctx.domain}
EXPECTED INPUTS:
{ctx_inputs or "  (none specified)"}
EXPECTED OUTPUTS:
{ctx_outputs or "  (none specified)"}
SIMILAR EXISTING TOOLS: {ctx_similar}
REQUESTING MILESTONE: {ctx.requesting_milestone_id} - {ctx.requesting_milestone_description}"""
    else:
        context_block = f"Research Context: {request.research_context}"

    return f"""Create a new MCP tool based on this specification:

Tool Name: {request.name}
Physics Domain: {request.domain}
Description: {request.description}
Required Inputs: {inputs_str}
Expected Outputs: {outputs_str}
Similar Existing Tools: {similar}

{context_block}

Use the mcp-builder agent to build, test, and deploy this tool.
The agent should use run_construction_pipeline() with appropriate parameters.
Refine the spec if needed before building.
Return JSON: {{"success": bool, "mcp_name": str, "deploy_url": str}}
"""


def parse_subagent_result(raw: SubagentResult) -> ToolFixResult | ToolCreateResult:
    """Parse raw subagent result text into a typed result model.

    Extracts JSON from the result text using json.loads with regex fallback
    to find JSON objects embedded in natural language text.
    """
    text = raw.result_text

    # Try direct JSON parse first
    try:
        data = json.loads(text)
        return _build_typed_result(data, raw.cost_usd)
    except (json.JSONDecodeError, ValueError):
        pass

    # Regex fallback: find JSON object in text
    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return _build_typed_result(data, raw.cost_usd)
        except (json.JSONDecodeError, ValueError):
            pass

    # Could not parse -- return failure
    return ToolFixResult(
        success=False,
        mcp_name="unknown",
        error_message=f"Could not parse subagent result: {text[:200]}",
        cost_usd=raw.cost_usd,
    )


def _build_typed_result(data: dict[str, object], cost_usd: float) -> ToolFixResult | ToolCreateResult:
    """Build the appropriate typed result from parsed JSON data."""
    success = bool(data.get("success", False))

    # If it has deploy_url, it's a create result
    if "deploy_url" in data:
        return ToolCreateResult(
            success=success,
            mcp_name=str(data.get("mcp_name")) if data.get("mcp_name") else None,
            deploy_url=str(data.get("deploy_url")) if data.get("deploy_url") else None,
            cost_usd=cost_usd,
            error_message=str(data.get("error_message")) if data.get("error_message") else None,
        )

    # Otherwise it's a fix result
    return ToolFixResult(
        success=success,
        mcp_name=str(data.get("mcp_name", "unknown")),
        version_hash=str(data.get("version_hash")) if data.get("version_hash") else None,
        cost_usd=cost_usd,
        error_message=str(data.get("error_message")) if data.get("error_message") else None,
    )
