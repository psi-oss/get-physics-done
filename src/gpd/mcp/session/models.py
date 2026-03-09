"""Pydantic data models for GPD session state."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class MilestoneState(BaseModel):
    """State of a single milestone within a session."""

    name: str
    status: str = "pending"  # pending | in_progress | complete | blocked
    progress_pct: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    description: str = ""


class SessionState(BaseModel):
    """Full session state persisted as JSON.

    This is the source of truth for a GPD session. The schema_version
    field enables forward-compatible schema migrations.
    """

    schema_version: int = 1

    # Identity
    session_id: str
    project_name: str
    project_root: str = ""
    session_name: str

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Status
    status: str = "active"  # active | paused | completed | interrupted
    elapsed_seconds: float = 0.0

    # Progress tracking
    current_phase: int = 0
    current_plan: int = 0
    milestones: list[MilestoneState] = Field(default_factory=list)

    # MCP tool usage
    mcp_count: int = 0
    mcp_tools_used: list[str] = Field(default_factory=list)
    mcp_last_refreshed: datetime | None = None

    # Research artifacts
    research_findings: list[str] = Field(default_factory=list)
    tool_outputs: list[str] = Field(default_factory=list)
    error_messages: list[str] = Field(default_factory=list)

    # Metadata
    tags: list[str] = Field(default_factory=list)
    checkpoint_data: dict[str, object] = Field(default_factory=dict)
    last_checkpoint_at: datetime | None = None

    @classmethod
    def new(
        cls,
        session_id: str,
        project_name: str,
        session_name: str,
        project_root: str = "",
        tags: list[str] | None = None,
    ) -> SessionState:
        """Create a new active session with current timestamps."""
        now = datetime.now(tz=UTC)
        return cls(
            session_id=session_id,
            project_name=project_name,
            project_root=project_root,
            session_name=session_name,
            created_at=now,
            updated_at=now,
            status="active",
            tags=tags or [],
        )
