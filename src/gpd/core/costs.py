"""Machine-local usage ledger and read-only cost summary helpers.

The cost ledger is advisory telemetry only. It never guesses provider billing
from model profiles alone. Usage is recorded only when a runtime payload
surfaces token or cost metadata explicitly.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.adapters.runtime_catalog import get_hook_payload_policy, get_runtime_capabilities
from gpd.core.constants import (
    COST_LEDGER_DIR_NAME,
    COST_LEDGER_RECORDS_FILENAME,
    COST_PRICING_SNAPSHOT_FILENAME,
    ENV_DATA_DIR,
    HOME_DATA_DIR_NAME,
)
from gpd.core.observability import get_current_session_id, resolve_project_root
from gpd.core.utils import atomic_write, file_lock, safe_read_file

__all__ = [
    "CostProjectSummary",
    "CostSessionSummary",
    "CostSummary",
    "PricingSnapshot",
    "UsageRecord",
    "build_cost_summary",
    "cost_data_root",
    "list_usage_records",
    "load_pricing_snapshot",
    "pricing_snapshot_path",
    "record_usage_from_runtime_payload",
    "usage_ledger_path",
]

_RECENT_SESSION_DEFAULT = 5
_DEDUP_WINDOW_SECONDS = 10.0


class UsageRecord(BaseModel):
    """One machine-local usage/cost ledger entry."""

    model_config = ConfigDict(frozen=True)

    record_id: str
    recorded_at: str
    runtime: str | None = None
    provider: str | None = None
    model: str | None = None
    session_id: str | None = None
    workspace_root: str | None = None
    project_root: str | None = None
    source: str = "runtime-hook"
    event_type: str | None = None
    usage_status: str = "measured"
    cost_status: str = "unavailable"
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_input_tokens: int | None = None
    cost_usd: float | None = None
    cost_source: str | None = None
    pricing_snapshot_source: str | None = None
    pricing_snapshot_as_of: str | None = None
    fingerprint: str | None = None


class PricingEntry(BaseModel):
    """One exact-match price row for conservative USD estimation."""

    model_config = ConfigDict(frozen=True)

    runtime: str
    model: str
    provider: str | None = None
    input_per_million_usd: float | None = None
    output_per_million_usd: float | None = None
    cached_input_per_million_usd: float | None = None
    cache_write_input_per_million_usd: float | None = None


class PricingSnapshot(BaseModel):
    """Machine-local pricing snapshot used for cost estimates."""

    model_config = ConfigDict(frozen=True)

    source: str | None = None
    as_of: str | None = None
    currency: str = "USD"
    entries: list[PricingEntry] = Field(default_factory=list)


class CostRollup(BaseModel):
    """Aggregated usage/cost totals for a project or session."""

    model_config = ConfigDict(frozen=True)

    record_count: int = 0
    usage_status: str = "unavailable"
    cost_status: str = "unavailable"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    cost_usd: float | None = None
    last_recorded_at: str | None = None
    runtimes: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)


class CostSessionSummary(CostRollup):
    """Compact per-session usage/cost summary."""

    session_id: str
    project_root: str | None = None


class CostProjectSummary(CostRollup):
    """Current-project usage/cost rollup."""

    project_root: str | None = None


class CostSummary(BaseModel):
    """Read-only cost summary for the local CLI."""

    model_config = ConfigDict(frozen=True)

    workspace_root: str
    active_runtime: str | None = None
    active_runtime_capabilities: dict[str, str] = Field(default_factory=dict)
    model_profile: str | None = None
    runtime_model_selection: str | None = None
    current_session_id: str | None = None
    project: CostProjectSummary
    current_session: CostSessionSummary | None = None
    recent_sessions: list[CostSessionSummary] = Field(default_factory=list)
    pricing_snapshot_configured: bool = False
    pricing_snapshot_source: str | None = None
    pricing_snapshot_as_of: str | None = None
    guidance: list[str] = Field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _first_string(value: object, *keys: str) -> str | None:
    mapping = _mapping(value)
    for key in keys:
        candidate = mapping.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _first_number(value: object, *keys: str) -> int | float | None:
    mapping = _mapping(value)
    for key in keys:
        if key not in mapping:
            continue
        candidate = mapping.get(key)
        if isinstance(candidate, bool):
            continue
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, float):
            return candidate if candidate == candidate else None
        if isinstance(candidate, str):
            stripped = candidate.strip()
            if not stripped:
                continue
            try:
                number = float(stripped)
            except ValueError:
                continue
            if number.is_integer():
                return int(number)
            return number
    return None


def _normalized_runtime(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    return normalized or None


def _runtime_capability_payload(runtime: str | None) -> dict[str, str]:
    normalized_runtime = _normalized_runtime(runtime)
    if not normalized_runtime:
        return {}
    try:
        capability = get_runtime_capabilities(normalized_runtime)
    except KeyError:
        return {}
    return {
        "permissions_surface": capability.permissions_surface,
        "statusline_surface": capability.statusline_surface,
        "notify_surface": capability.notify_surface,
        "telemetry_source": capability.telemetry_source,
        "telemetry_completeness": capability.telemetry_completeness,
    }


def _usage_container(payload: dict[str, object], usage_keys: tuple[str, ...]) -> dict[str, object]:
    for key in usage_keys:
        candidate = _mapping(payload.get(key))
        if candidate:
            return candidate
    return {}


def _cost_root(explicit_data_dir: Path | None = None) -> Path:
    if explicit_data_dir is not None:
        return explicit_data_dir.expanduser() / COST_LEDGER_DIR_NAME
    data_dir = os.environ.get(ENV_DATA_DIR, "").strip()
    if data_dir:
        return Path(data_dir).expanduser() / COST_LEDGER_DIR_NAME
    return Path.home() / HOME_DATA_DIR_NAME / COST_LEDGER_DIR_NAME


def cost_data_root(explicit_data_dir: Path | None = None) -> Path:
    """Return the resolved machine-local cost data root."""
    return _cost_root(explicit_data_dir)


def usage_ledger_path(data_root: Path | None = None) -> Path:
    """Return the append-only machine-local usage ledger path."""
    return _cost_root(data_root) / COST_LEDGER_RECORDS_FILENAME


def pricing_snapshot_path(data_root: Path | None = None) -> Path:
    """Return the optional machine-local pricing snapshot path."""
    return _cost_root(data_root) / COST_PRICING_SNAPSHOT_FILENAME


def load_pricing_snapshot(data_root: Path | None = None) -> PricingSnapshot:
    """Load the optional machine-local pricing snapshot, or return an empty one."""
    content = safe_read_file(pricing_snapshot_path(data_root))
    if content is None:
        return PricingSnapshot()
    try:
        return PricingSnapshot.model_validate_json(content)
    except ValueError:
        return PricingSnapshot()


def _load_usage_records(data_root: Path | None = None) -> list[UsageRecord]:
    ledger_path = usage_ledger_path(data_root)
    content = safe_read_file(ledger_path)
    if content is None:
        return []

    rows: list[UsageRecord] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rows.append(UsageRecord.model_validate_json(stripped))
        except ValueError:
            continue
    return rows


def list_usage_records(
    data_root: Path | None = None,
    *,
    project_root: Path | None = None,
    session_id: str | None = None,
    last: int | None = None,
) -> list[UsageRecord]:
    """Return usage records newest-first with optional project/session filters."""
    records = _load_usage_records(data_root)
    filtered: list[UsageRecord] = []
    normalized_project = project_root.expanduser().resolve(strict=False).as_posix() if project_root is not None else None
    for record in records:
        if normalized_project is not None and record.project_root != normalized_project:
            continue
        if session_id is not None and record.session_id != session_id:
            continue
        filtered.append(record)

    filtered.sort(key=lambda row: (row.recorded_at, row.record_id), reverse=True)
    if last is not None and last > 0:
        return filtered[:last]
    return filtered


def _append_record(record: UsageRecord, *, data_root: Path | None = None) -> UsageRecord:
    ledger_path = usage_ledger_path(data_root)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(ledger_path):
        existing = _load_usage_records(data_root)
        if record.fingerprint:
            for prior in reversed(existing[-25:]):
                if prior.fingerprint != record.fingerprint:
                    continue
                try:
                    current_time = datetime.fromisoformat(record.recorded_at.replace("Z", "+00:00"))
                    prior_time = datetime.fromisoformat(prior.recorded_at.replace("Z", "+00:00"))
                except ValueError:
                    break
                if abs((current_time - prior_time).total_seconds()) <= _DEDUP_WINDOW_SECONDS:
                    return prior
                break
        lines = [row.model_dump_json() for row in existing]
        lines.append(record.model_dump_json())
        atomic_write(ledger_path, "\n".join(lines) + "\n")
    return record


def _match_pricing_entry(snapshot: PricingSnapshot, *, runtime: str | None, provider: str | None, model: str | None) -> PricingEntry | None:
    if runtime is None or model is None:
        return None
    runtime_key = runtime.casefold()
    model_key = model.casefold()
    provider_key = provider.casefold() if provider else None
    for entry in snapshot.entries:
        if entry.runtime.casefold() != runtime_key:
            continue
        if entry.model.casefold() != model_key:
            continue
        if entry.provider is not None and provider_key is not None and entry.provider.casefold() != provider_key:
            continue
        if entry.provider is not None and provider_key is None:
            continue
        return entry
    return None


def _estimated_cost_from_pricing(
    snapshot: PricingSnapshot,
    *,
    runtime: str | None,
    provider: str | None,
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_input_tokens: int | None,
    cache_write_input_tokens: int | None,
) -> tuple[float | None, str | None]:
    entry = _match_pricing_entry(snapshot, runtime=runtime, provider=provider, model=model)
    if entry is None:
        return None, None

    total = 0.0
    matched = False
    for token_count, rate in (
        (input_tokens, entry.input_per_million_usd),
        (output_tokens, entry.output_per_million_usd),
        (cached_input_tokens, entry.cached_input_per_million_usd),
        (cache_write_input_tokens, entry.cache_write_input_per_million_usd),
    ):
        if token_count is None or rate is None:
            continue
        matched = True
        total += (float(token_count) / 1_000_000.0) * float(rate)
    if not matched:
        return None, None
    return round(total, 6), entry.model


def _fingerprint_from_payload(
    *,
    runtime: str | None,
    project_root: str | None,
    session_id: str | None,
    event_type: str | None,
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
    cached_input_tokens: int | None,
    cache_write_input_tokens: int | None,
    cost_usd: float | None,
) -> str:
    raw = json.dumps(
        {
            "runtime": runtime,
            "project_root": project_root,
            "session_id": session_id,
            "event_type": event_type,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cached_input_tokens": cached_input_tokens,
            "cache_write_input_tokens": cache_write_input_tokens,
            "cost_usd": cost_usd,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return raw


def record_usage_from_runtime_payload(
    payload: dict[str, object],
    *,
    runtime: str | None,
    cwd: Path | None,
    data_root: Path | None = None,
) -> UsageRecord | None:
    """Record one measured usage payload when the runtime exposes token/cost telemetry."""
    capability_payload = _runtime_capability_payload(runtime)
    if capability_payload.get("telemetry_completeness") == "none":
        return None
    if capability_payload.get("telemetry_source") not in {"notify-hook"}:
        return None

    policy = get_hook_payload_policy(runtime)
    usage = _usage_container(payload, policy.usage_keys)
    model_value = payload.get("model")
    model = (
        _normalize_optional_text(model_value)
        if isinstance(model_value, str)
        else _first_string(model_value, *policy.model_keys)
    ) or _first_string(payload, *policy.model_keys)
    provider = _first_string(model_value, *policy.provider_keys) or _first_string(payload, *policy.provider_keys)

    input_tokens_raw = _first_number(usage, *policy.input_tokens_keys)
    output_tokens_raw = _first_number(usage, *policy.output_tokens_keys)
    total_tokens_raw = _first_number(usage, *policy.total_tokens_keys)
    cached_tokens_raw = _first_number(usage, *policy.cached_input_tokens_keys)
    cache_write_tokens_raw = _first_number(usage, *policy.cache_write_input_tokens_keys)
    cost_usd_raw = _first_number(usage, *policy.cost_usd_keys)

    if input_tokens_raw is None:
        input_tokens_raw = _first_number(payload, *policy.input_tokens_keys)
    if output_tokens_raw is None:
        output_tokens_raw = _first_number(payload, *policy.output_tokens_keys)
    if total_tokens_raw is None:
        total_tokens_raw = _first_number(payload, *policy.total_tokens_keys)
    if cached_tokens_raw is None:
        cached_tokens_raw = _first_number(payload, *policy.cached_input_tokens_keys)
    if cache_write_tokens_raw is None:
        cache_write_tokens_raw = _first_number(payload, *policy.cache_write_input_tokens_keys)
    if cost_usd_raw is None:
        cost_usd_raw = _first_number(payload, *policy.cost_usd_keys)

    input_tokens = int(input_tokens_raw) if isinstance(input_tokens_raw, (int, float)) else None
    output_tokens = int(output_tokens_raw) if isinstance(output_tokens_raw, (int, float)) else None
    cached_input_tokens = int(cached_tokens_raw) if isinstance(cached_tokens_raw, (int, float)) else None
    cache_write_input_tokens = int(cache_write_tokens_raw) if isinstance(cache_write_tokens_raw, (int, float)) else None
    total_tokens = int(total_tokens_raw) if isinstance(total_tokens_raw, (int, float)) else None
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = int(input_tokens or 0) + int(output_tokens or 0)

    cost_usd = float(cost_usd_raw) if isinstance(cost_usd_raw, (int, float)) else None
    has_usage_signal = any(
        value is not None
        for value in (
            input_tokens,
            output_tokens,
            total_tokens,
            cached_input_tokens,
            cache_write_input_tokens,
            cost_usd,
        )
    )
    if not has_usage_signal:
        return None

    workspace_root = resolve_project_root(cwd) if cwd is not None else None
    if workspace_root is None and cwd is not None:
        workspace_root = cwd.expanduser().resolve(strict=False)
    workspace_text = workspace_root.as_posix() if workspace_root is not None else None
    session_id = get_current_session_id(workspace_root) if workspace_root is not None else None
    event_type = _normalize_optional_text(payload.get("type"))

    pricing_snapshot = load_pricing_snapshot(data_root)
    estimated_cost_usd, _matched_model = _estimated_cost_from_pricing(
        pricing_snapshot,
        runtime=runtime,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_write_input_tokens=cache_write_input_tokens,
    )

    cost_status = "unavailable"
    cost_source: str | None = None
    pricing_source: str | None = None
    pricing_as_of: str | None = None
    if cost_usd is not None:
        cost_status = "measured"
        cost_source = "runtime-payload"
    elif estimated_cost_usd is not None:
        cost_usd = estimated_cost_usd
        cost_status = "estimated"
        cost_source = "pricing-snapshot"
        pricing_source = pricing_snapshot.source
        pricing_as_of = pricing_snapshot.as_of

    record = UsageRecord(
        record_id=f"usage-{int(datetime.now(UTC).timestamp() * 1000)}-{secrets.token_hex(3)}",
        recorded_at=_now_iso(),
        runtime=_normalized_runtime(runtime),
        provider=provider,
        model=model,
        session_id=session_id,
        workspace_root=workspace_text,
        project_root=workspace_text,
        event_type=event_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_write_input_tokens=cache_write_input_tokens,
        cost_usd=cost_usd,
        cost_status=cost_status,
        cost_source=cost_source,
        pricing_snapshot_source=pricing_source,
        pricing_snapshot_as_of=pricing_as_of,
        fingerprint=_fingerprint_from_payload(
            runtime=runtime,
            project_root=workspace_text,
            session_id=session_id,
            event_type=event_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_input_tokens=cache_write_input_tokens,
            cost_usd=cost_usd,
        ),
    )
    return _append_record(record, data_root=data_root)


def _rollup(records: list[UsageRecord]) -> CostRollup:
    if not records:
        return CostRollup()

    runtime_values = sorted({value for record in records if (value := _normalize_optional_text(record.runtime))})
    model_values = sorted({value for record in records if (value := _normalize_optional_text(record.model))})
    measured_costs = [record.cost_usd for record in records if record.cost_status == "measured" and record.cost_usd is not None]
    estimated_costs = [record.cost_usd for record in records if record.cost_status == "estimated" and record.cost_usd is not None]
    usage_status = (
        "measured"
        if any(
            value is not None
            for record in records
            for value in (
                record.input_tokens,
                record.output_tokens,
                record.total_tokens,
                record.cached_input_tokens,
                record.cache_write_input_tokens,
            )
        )
        else "unavailable"
    )
    if measured_costs and estimated_costs:
        cost_status = "mixed"
        cost_total = round(sum(measured_costs) + sum(estimated_costs), 6)
    elif measured_costs:
        cost_status = "measured"
        cost_total = round(sum(measured_costs), 6)
    elif estimated_costs:
        cost_status = "estimated"
        cost_total = round(sum(estimated_costs), 6)
    else:
        cost_status = "unavailable"
        cost_total = None

    return CostRollup(
        record_count=len(records),
        usage_status=usage_status,
        cost_status=cost_status,
        input_tokens=sum(record.input_tokens or 0 for record in records),
        output_tokens=sum(record.output_tokens or 0 for record in records),
        total_tokens=sum(record.total_tokens or 0 for record in records),
        cached_input_tokens=sum(record.cached_input_tokens or 0 for record in records),
        cache_write_input_tokens=sum(record.cache_write_input_tokens or 0 for record in records),
        cost_usd=cost_total,
        last_recorded_at=max((record.recorded_at for record in records), default=None),
        runtimes=runtime_values,
        models=model_values,
    )


def _session_rows(records: list[UsageRecord], *, last: int) -> list[CostSessionSummary]:
    grouped: dict[str, list[UsageRecord]] = {}
    for record in records:
        if not record.session_id:
            continue
        grouped.setdefault(record.session_id, []).append(record)

    rows: list[CostSessionSummary] = []
    for session_id, group in grouped.items():
        rollup = _rollup(group)
        rows.append(
            CostSessionSummary(
                session_id=session_id,
                project_root=next((record.project_root for record in group if record.project_root), None),
                **rollup.model_dump(),
            )
        )
    rows.sort(key=lambda row: (row.last_recorded_at or "", row.session_id), reverse=True)
    return rows[:last] if last > 0 else rows


def build_cost_summary(cwd: Path | None = None, *, data_root: Path | None = None, last_sessions: int = _RECENT_SESSION_DEFAULT) -> CostSummary:
    """Build a read-only usage/cost summary for the current workspace and recent sessions."""
    resolved_workspace = resolve_project_root(cwd) if cwd is not None else None
    if resolved_workspace is None:
        resolved_workspace = cwd.expanduser().resolve(strict=False) if cwd is not None else Path.cwd().resolve(strict=False)

    records = list_usage_records(data_root)
    project_records = [record for record in records if record.project_root == resolved_workspace.as_posix()]
    current_session_id = get_current_session_id(resolved_workspace)
    current_session_records = [record for record in project_records if current_session_id and record.session_id == current_session_id]
    pricing_snapshot = load_pricing_snapshot(data_root)

    active_runtime: str | None = None
    active_runtime_capabilities: dict[str, str] = {}
    model_profile: str | None = None
    runtime_model_selection: str | None = None
    try:
        from gpd.core.config import load_config
        from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_runtime_for_gpd_use

        config = load_config(resolved_workspace)
        model_profile = getattr(config.model_profile, "value", None) or str(config.model_profile)
        detected_runtime = detect_runtime_for_gpd_use(cwd=resolved_workspace)
        if detected_runtime != RUNTIME_UNKNOWN:
            active_runtime = detected_runtime
            active_runtime_capabilities = _runtime_capability_payload(detected_runtime)
            overrides = sorted(((config.model_overrides or {}).get(detected_runtime) or {}).keys())
            if overrides:
                runtime_model_selection = f"explicit overrides pinned for {', '.join(overrides)}"
            else:
                runtime_model_selection = "runtime defaults"
    except Exception:
        pass

    guidance: list[str] = []
    project_rollup = _rollup(project_records)
    current_session_rollup = _rollup(current_session_records) if current_session_records else None

    if not project_records:
        if active_runtime_capabilities.get("telemetry_completeness") == "none" and active_runtime:
            guidance.append(
                f"{active_runtime} does not currently expose a GPD-managed usage telemetry collection path, so `gpd cost` may remain empty even when work runs."
            )
        elif active_runtime_capabilities.get("telemetry_completeness") == "best-effort" and active_runtime:
            guidance.append(
                f"{active_runtime} only exposes best-effort usage telemetry through {active_runtime_capabilities.get('telemetry_source') or 'its runtime hook'}, so missing turns remain unavailable instead of being guessed."
            )
        else:
            guidance.append(
                "No measured usage telemetry is recorded for this workspace yet. GPD records usage only when the runtime emits token or cost payloads."
            )
    elif project_rollup.usage_status == "measured" and project_rollup.cost_status == "unavailable":
        if pricing_snapshot.entries:
            guidance.append(
                "Measured tokens are available, but no pricing snapshot entry matched the recorded runtime/provider/model combination, so USD cost is unavailable."
            )
        else:
            guidance.append(
                "Measured tokens are available, but no pricing snapshot is configured at the machine-local cost root, so USD cost is unavailable."
            )
    elif project_rollup.cost_status == "mixed":
        guidance.append(
            "USD cost mixes measured runtime telemetry with pricing-snapshot estimates. Treat the total as advisory rather than invoice-level billing truth."
        )

    if active_runtime and runtime_model_selection == "runtime defaults":
        guidance.append(
            f"Current model posture: profile `{model_profile or 'unknown'}` with {active_runtime} runtime defaults. Use the runtime `settings` command only if you want explicit tier-model overrides."
        )

    return CostSummary(
        workspace_root=resolved_workspace.as_posix(),
        active_runtime=active_runtime,
        active_runtime_capabilities=active_runtime_capabilities,
        model_profile=model_profile,
        runtime_model_selection=runtime_model_selection,
        current_session_id=current_session_id,
        project=CostProjectSummary(project_root=resolved_workspace.as_posix(), **project_rollup.model_dump()),
        current_session=(
            CostSessionSummary(
                session_id=current_session_id,
                project_root=resolved_workspace.as_posix(),
                **current_session_rollup.model_dump(),
            )
            if current_session_id and current_session_rollup is not None
            else None
        ),
        recent_sessions=_session_rows(records, last=max(last_sessions, 0)),
        pricing_snapshot_configured=bool(pricing_snapshot.entries),
        pricing_snapshot_source=pricing_snapshot.source,
        pricing_snapshot_as_of=pricing_snapshot.as_of,
        guidance=guidance,
    )
