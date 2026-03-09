"""Thin wrapper around claude-agent-sdk for subagent spawning.

Isolates all SDK coupling to this single module. Handles lazy imports,
timeout management, macOS AF_UNIX path workarounds, and status callbacks.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from gpd.mcp.subagents.models import SubagentResult, SubagentStatus

logger = logging.getLogger(__name__)

# Track symlinks for cleanup
_SYMLINK_CLEANUP: list[str] = []


def _cleanup_symlinks() -> None:
    """Remove temporary symlinks created for AF_UNIX path workaround."""
    for link in _SYMLINK_CLEANUP:
        try:
            os.unlink(link)
        except OSError:
            pass


atexit.register(_cleanup_symlinks)


def _get_short_cwd(cwd: str) -> str:
    """Return cwd directly if short enough, or create a /tmp symlink.

    macOS AF_UNIX socket paths are limited to 104 bytes. Long paths cause
    OSError from the SDK's Unix socket creation. Workaround: create a short
    symlink in /tmp pointing to the actual working directory.
    """
    if len(cwd) <= 80:
        return cwd

    link_dir = tempfile.mkdtemp(prefix="gpdplus-")
    link_path = str(Path(link_dir) / "w")
    os.symlink(cwd, link_path)
    _SYMLINK_CLEANUP.append(link_path)
    _SYMLINK_CLEANUP.append(link_dir)
    logger.debug("Created short symlink %s -> %s for AF_UNIX workaround", link_path, cwd)
    return link_path


class SubagentSDK:
    """Thin wrapper around claude-agent-sdk for spawning subagents.

    All SDK imports are lazy to avoid import-time failures when
    claude-agent-sdk is not installed.
    """

    async def spawn(
        self,
        prompt: str,
        agents: dict[str, object],
        allowed_tools: list[str],
        cwd: str,
        max_turns: int = 50,
        max_budget_usd: float = 5.0,
        timeout_seconds: int = 300,
        on_status: Callable[[SubagentStatus], None] | None = None,
    ) -> SubagentResult:
        """Spawn a subagent and wait for its result.

        Args:
            prompt: The prompt to send to the subagent.
            agents: Dict of agent name -> AgentDefinition.
            allowed_tools: Tools the parent agent can use.
            cwd: Working directory for the subagent.
            max_turns: Maximum conversation turns.
            max_budget_usd: Maximum spend limit.
            timeout_seconds: Timeout with 50% buffer applied internally.
            on_status: Optional callback for status updates.

        Returns:
            SubagentResult with success/failure and result text.

        Raises:
            RuntimeError: If claude-agent-sdk is not installed.
        """
        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeAgentOptions,
                ResultMessage,
                TextBlock,
                ToolUseBlock,
                query,
            )
        except ImportError:
            raise RuntimeError("claude-agent-sdk not installed. Run: pip install claude-agent-sdk") from None

        short_cwd = _get_short_cwd(cwd)

        options = ClaudeAgentOptions(
            allowed_tools=allowed_tools,
            agents=agents,
            permission_mode="bypassPermissions",
            cwd=short_cwd,
            max_turns=max_turns,
            max_budget_usd=max_budget_usd,
        )

        # Apply 50% buffer to timeout (per research pitfall 5)
        buffered_timeout = timeout_seconds * 1.5

        try:
            result = SubagentResult(success=False, result_text="No result received")

            async def _run() -> SubagentResult:
                nonlocal result
                async for message in query(prompt=prompt, options=options):
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock) and on_status:
                                first_line = block.text.split("\n")[0][:100]
                                on_status(
                                    SubagentStatus(
                                        agent_name="subagent",
                                        message=first_line,
                                        is_subagent_message=False,
                                    )
                                )
                            elif isinstance(block, ToolUseBlock) and on_status:
                                on_status(
                                    SubagentStatus(
                                        agent_name=block.name,
                                        message=f"Using tool: {block.name}",
                                        is_subagent_message=True,
                                    )
                                )
                    elif isinstance(message, ResultMessage):
                        result = SubagentResult(
                            success=not message.is_error,
                            result_text=message.result or "",
                            cost_usd=message.total_cost_usd or 0.0,
                            session_id=message.session_id,
                            duration_seconds=message.duration_ms / 1000.0,
                        )
                return result

            return await asyncio.wait_for(_run(), timeout=buffered_timeout)

        except TimeoutError:
            logger.warning("Subagent timed out after %.0f seconds", buffered_timeout)
            return SubagentResult(
                success=False,
                result_text="Subagent timed out",
            )
