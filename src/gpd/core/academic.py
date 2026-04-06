"""Academic platform experiment support for GPD.

Provides credit-aware execution guards, enhanced artifact capture for
academic deployments, and session-level usage logging.

When ``platform_mode`` is ``academic`` in GPD/config.json:
- Every agent invocation is logged with credit metadata
- Artifact capture is enhanced with provenance and reproducibility fields
- Credit budget checks gate expensive operations before they start

Public API
----------
log_academic_event  -- record an academic-mode event with credit metadata
capture_artifact    -- persist an artifact with academic provenance metadata
check_budget_guard  -- pre-flight check that raises when budget is exhausted
academic_session_summary -- summarize credit usage for current session
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.core.config import GPDProjectConfig, PlatformMode, check_credit_budget, is_academic_mode
from gpd.core.constants import ProjectLayout
from gpd.core.errors import ConfigError
from gpd.core.observability import gpd_span, instrument_gpd_function
from gpd.core.utils import atomic_write, file_lock, safe_read_file

logger = logging.getLogger(__name__)

__all__ = [
    "AcademicArtifact",
    "AcademicEvent",
    "AcademicSessionSummary",
    "academic_session_summary",
    "capture_artifact",
    "check_budget_guard",
    "log_academic_event",
]


# ─── Models ──────────────────────────────────────────────────────────────────


class AcademicEvent(BaseModel):
    """A single academic-mode event with credit metadata."""

    timestamp: str
    event_type: str
    agent: str | None = None
    credit_cost: int = Field(default=0, ge=0)
    credit_remaining: int | None = None
    session_id: str | None = None
    phase: str | None = None
    plan: str | None = None
    data: dict[str, object] = Field(default_factory=dict)


class AcademicArtifact(BaseModel):
    """An artifact captured with academic provenance metadata."""

    timestamp: str
    artifact_type: str
    path: str
    phase: str | None = None
    plan: str | None = None
    agent: str | None = None
    description: str = ""
    provenance: dict[str, object] = Field(default_factory=dict)
    reproducibility: dict[str, object] = Field(default_factory=dict)


class AcademicSessionSummary(BaseModel):
    """Summary of academic credit usage for a session."""

    session_id: str | None = None
    platform_mode: str = "academic"
    credit_budget: int | None = None
    credit_used: int = 0
    credit_remaining: int | None = None
    event_count: int = 0
    artifact_count: int = 0
    events_by_type: dict[str, int] = Field(default_factory=dict)


# ─── Path Helpers ─────────────────────────────────────────────────────────────


def _academic_dir(cwd: Path) -> Path:
    return ProjectLayout(cwd).gpd / "academic"


def _academic_log_path(cwd: Path) -> Path:
    return _academic_dir(cwd) / "events.jsonl"


def _academic_artifacts_path(cwd: Path) -> Path:
    return _academic_dir(cwd) / "artifacts.jsonl"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ─── Public API ───────────────────────────────────────────────────────────────


@instrument_gpd_function("academic.check_budget")
def check_budget_guard(config: GPDProjectConfig) -> None:
    """Raise :class:`ConfigError` when the academic credit budget is exhausted.

    No-op when platform_mode is not academic or credit_budget is None.
    """
    if not is_academic_mode(config):
        return
    has_budget, remaining = check_credit_budget(config)
    if not has_budget:
        raise ConfigError(
            f"Academic credit budget exhausted (budget={config.credit_budget}, "
            f"used={config.credit_used}). Increase credit_budget or switch to "
            "standard platform_mode."
        )


@instrument_gpd_function("academic.log_event")
def log_academic_event(
    cwd: Path,
    config: GPDProjectConfig,
    *,
    event_type: str,
    agent: str | None = None,
    credit_cost: int = 0,
    session_id: str | None = None,
    phase: str | None = None,
    plan: str | None = None,
    data: dict[str, object] | None = None,
) -> AcademicEvent | None:
    """Record an academic-mode event with credit metadata.

    Returns None when not in academic mode.
    """
    if not is_academic_mode(config):
        return None

    _, remaining = check_credit_budget(config)

    event = AcademicEvent(
        timestamp=_now_iso(),
        event_type=event_type,
        agent=agent,
        credit_cost=credit_cost,
        credit_remaining=remaining,
        session_id=session_id,
        phase=phase,
        plan=plan,
        data=data or {},
    )

    log_path = _academic_log_path(cwd)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    line = event.model_dump_json()
    with file_lock(log_path):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    with gpd_span("academic.event", **{"gpd.academic_event_type": event_type}):
        logger.info("academic_event", extra={"event_type": event_type, "agent": agent, "credit_cost": credit_cost})

    return event


@instrument_gpd_function("academic.capture_artifact")
def capture_artifact(
    cwd: Path,
    config: GPDProjectConfig,
    *,
    artifact_type: str,
    path: str,
    phase: str | None = None,
    plan: str | None = None,
    agent: str | None = None,
    description: str = "",
    provenance: dict[str, object] | None = None,
    reproducibility: dict[str, object] | None = None,
) -> AcademicArtifact | None:
    """Persist an artifact record with academic provenance metadata.

    Captures provenance (who created it, from what inputs) and
    reproducibility hints (parameters, seeds, versions) for each artifact.

    Returns None when not in academic mode or artifact_capture is disabled.
    """
    if not is_academic_mode(config):
        return None
    if not config.artifact_capture:
        return None

    artifact = AcademicArtifact(
        timestamp=_now_iso(),
        artifact_type=artifact_type,
        path=path,
        phase=phase,
        plan=plan,
        agent=agent,
        description=description,
        provenance=provenance or {},
        reproducibility=reproducibility or {},
    )

    artifacts_path = _academic_artifacts_path(cwd)
    artifacts_path.parent.mkdir(parents=True, exist_ok=True)

    line = artifact.model_dump_json()
    with file_lock(artifacts_path):
        with open(artifacts_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    with gpd_span("academic.artifact", **{"gpd.artifact_type": artifact_type}):
        logger.info(
            "academic_artifact_captured",
            extra={"artifact_type": artifact_type, "path": path, "agent": agent},
        )

    return artifact


@instrument_gpd_function("academic.session_summary")
def academic_session_summary(
    cwd: Path,
    config: GPDProjectConfig,
    *,
    session_id: str | None = None,
) -> AcademicSessionSummary | None:
    """Summarize credit usage and artifact capture for the current session.

    Returns None when not in academic mode.
    """
    if not is_academic_mode(config):
        return None

    _, remaining = check_credit_budget(config)

    # Count events
    event_count = 0
    events_by_type: dict[str, int] = {}
    log_path = _academic_log_path(cwd)
    content = safe_read_file(log_path)
    if content:
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
                if session_id and evt.get("session_id") != session_id:
                    continue
                event_count += 1
                et = evt.get("event_type", "unknown")
                events_by_type[et] = events_by_type.get(et, 0) + 1
            except (json.JSONDecodeError, ValueError):
                continue

    # Count artifacts
    artifact_count = 0
    artifacts_path = _academic_artifacts_path(cwd)
    art_content = safe_read_file(artifacts_path)
    if art_content:
        for line in art_content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                art = json.loads(line)
                if session_id and art.get("session_id") != session_id:
                    continue
                artifact_count += 1
            except (json.JSONDecodeError, ValueError):
                continue

    return AcademicSessionSummary(
        session_id=session_id,
        credit_budget=config.credit_budget,
        credit_used=config.credit_used,
        credit_remaining=remaining,
        event_count=event_count,
        artifact_count=artifact_count,
        events_by_type=events_by_type,
    )
