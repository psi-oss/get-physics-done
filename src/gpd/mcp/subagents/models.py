"""Shared Pydantic models for subagent communication."""

from __future__ import annotations

from enum import StrEnum
import time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubagentResult(BaseModel):
    """Generic result wrapper for any subagent call."""

    success: bool
    result_text: str
    cost_usd: float = 0.0
    session_id: str | None = None
    duration_seconds: float = 0.0


class SubagentStatusKind(StrEnum):
    """Kinds of status updates emitted during a subagent run."""

    UPDATE = "update"
    TOOL = "tool"


class SubagentStatus(BaseModel):
    """Status update for display and logging layers.

    Legacy ``agent_name`` / ``is_subagent_message`` inputs are still accepted
    so older callers keep working while the clearer ``source`` / ``kind``
    surface takes over.
    """

    model_config = ConfigDict(populate_by_name=True)

    source: str = "subagent"
    message: str
    kind: SubagentStatusKind = SubagentStatusKind.UPDATE
    timestamp: float = Field(default_factory=time.time)

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_fields(cls, data: object) -> object:
        """Accept legacy field names from pre-cleanup callers."""
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        if "source" not in payload and "agent_name" in payload:
            payload["source"] = payload.pop("agent_name")
        if "kind" not in payload and "is_subagent_message" in payload:
            payload["kind"] = (
                SubagentStatusKind.TOOL if bool(payload.pop("is_subagent_message")) else SubagentStatusKind.UPDATE
            )
        return payload

    @property
    def agent_name(self) -> str:
        """Backward-compatible alias for the status source."""
        return self.source

    @property
    def is_subagent_message(self) -> bool:
        """Backward-compatible alias for tool-use events."""
        return self.kind == SubagentStatusKind.TOOL
