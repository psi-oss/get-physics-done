"""Thin wrapper around claude-agent-sdk for subagent spawning.

Isolates all SDK coupling to this single module. Handles lazy imports,
timeout management, macOS AF_UNIX path workarounds, and status callbacks.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from gpd.mcp.subagents.models import SubagentResult, SubagentStatus, SubagentStatusKind

logger = logging.getLogger(__name__)

TIMEOUT_BUFFER_MULTIPLIER: float = 1.5

SDK_INSTALL_HINT = "claude-agent-sdk not installed. Run: pip install claude-agent-sdk"
DEFAULT_EMPTY_RESULT_TEXT = "Subagent finished without a result message."

_SYMLINK_CLEANUP: list[str] = []
_TEMP_DIR_CLEANUP: list[str] = []


def _cleanup_symlinks() -> None:
    """Remove temporary symlinks created for AF_UNIX path workaround."""
    for link in _SYMLINK_CLEANUP:
        try:
            if os.path.lexists(link):
                os.unlink(link)
        except OSError:
            pass
    _SYMLINK_CLEANUP.clear()

    for link_dir in _TEMP_DIR_CLEANUP:
        shutil.rmtree(link_dir, ignore_errors=True)
    _TEMP_DIR_CLEANUP.clear()


atexit.register(_cleanup_symlinks)


def _get_short_cwd(cwd: str) -> str:
    """Return cwd directly if short enough, or create a /tmp symlink.

    macOS AF_UNIX socket paths are limited to 104 bytes. Long paths cause
    OSError from the SDK's Unix socket creation. Workaround: create a short
    symlink in /tmp pointing to the actual working directory.
    """
    if len(cwd) <= 80:
        return cwd

    link_dir = tempfile.mkdtemp(prefix="gpd-session-")
    link_path = str(Path(link_dir) / "w")
    os.symlink(cwd, link_path)
    _SYMLINK_CLEANUP.append(link_path)
    _TEMP_DIR_CLEANUP.append(link_dir)
    logger.debug("Created short symlink %s -> %s for AF_UNIX workaround", link_path, cwd)
    return link_path


def _emit_status(
    on_status: Callable[[SubagentStatus], None] | None,
    *,
    source: str,
    message: str,
    kind: SubagentStatusKind = SubagentStatusKind.UPDATE,
) -> None:
    """Send a status event if a callback is registered."""
    if on_status is None:
        return

    trimmed = message.strip()
    if not trimmed:
        return

    on_status(SubagentStatus(source=source, message=trimmed, kind=kind))


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
        timeout_seconds: float = 300.0,
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
            raise RuntimeError(SDK_INSTALL_HINT) from None

        short_cwd = _get_short_cwd(cwd)

        options = ClaudeAgentOptions(
            allowed_tools=allowed_tools,
            agents=agents,
            permission_mode="bypassPermissions",
            cwd=short_cwd,
            max_turns=max_turns,
            max_budget_usd=max_budget_usd,
        )

        # Apply timeout buffer (per research pitfall 5)
        buffered_timeout = timeout_seconds * TIMEOUT_BUFFER_MULTIPLIER

        try:
            result = SubagentResult(success=False, result_text=DEFAULT_EMPTY_RESULT_TEXT)

            async def _run() -> SubagentResult:
                nonlocal result
                async for message in query(prompt=prompt, options=options):
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                first_line = block.text.strip().splitlines()[0] if block.text.strip() else ""
                                _emit_status(on_status, source="subagent", message=first_line)
                            elif isinstance(block, ToolUseBlock):
                                _emit_status(
                                    on_status,
                                    source=block.name,
                                    message="Tool call started",
                                    kind=SubagentStatusKind.TOOL,
                                )
                    elif isinstance(message, ResultMessage):
                        result = SubagentResult(
                            success=not message.is_error,
                            result_text=message.result or "",
                            cost_usd=message.total_cost_usd or 0.0,
                            session_id=message.session_id,
                            duration_seconds=(message.duration_ms or 0) / 1000.0,
                        )
                return result

            return await asyncio.wait_for(_run(), timeout=buffered_timeout)

        except TimeoutError:
            logger.warning(
                "Subagent timed out after %.1f buffered seconds (configured %.1f seconds)",
                buffered_timeout,
                timeout_seconds,
            )
            return SubagentResult(
                success=False,
                result_text=(
                    f"Subagent timed out after {buffered_timeout:.1f}s "
                    f"(configured timeout {timeout_seconds:.1f}s)."
                ),
            )
