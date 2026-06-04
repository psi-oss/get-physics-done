"""Typer-free payload helpers for Research Persona CLI commands."""

from __future__ import annotations

import importlib
import inspect
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Protocol, runtime_checkable

from pydantic import ValidationError as PydanticValidationError

from gpd.core.research_persona import (
    RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS,
    ResearchPersona,
    ResearchPersonaAxis,
    ResearchPersonaCapsule,
    ResearchPersonaError,
    ResearchPersonaFact,
    ResearchPersonaHistoryEvent,
    ResearchPersonaPatch,
    ResearchPersonaPatchOperation,
    ResearchPersonaTombstone,
    append_research_persona_history,
    append_research_persona_tombstone,
    apply_research_persona_patch,
    build_research_persona_capsule,
    load_research_persona,
    parse_research_persona_data_strict,
    project_research_persona,
    research_persona_path,
    research_persona_root,
    save_research_persona,
    validate_research_persona,
)
from gpd.core.research_persona_audit import audit_research_persona_profile

__all__ = [
    "build_audit_payload",
    "build_apply_patch_payload",
    "build_doppelganger_payload",
    "build_diff_payload",
    "build_explain_plan_payload",
    "build_export_capsule_payload",
    "build_forget_payload",
    "build_ingest_source_payload",
    "build_show_payload",
    "build_taste_check_payload",
    "build_validate_payload",
    "parse_research_persona_patch_data_strict",
    "research_persona_audit_payload",
    "research_persona_apply_patch_payload",
    "research_persona_doppelganger_payload",
    "research_persona_diff_payload",
    "research_persona_explain_plan_payload",
    "research_persona_export_capsule_payload",
    "research_persona_forget_fact_payload",
    "research_persona_ingest_source_payload",
    "research_persona_show_payload",
    "research_persona_taste_check_payload",
    "research_persona_validate_payload",
    "summarize_research_persona_diff",
]

_INGESTION_MODULE = "gpd.core.research_persona_ingestion"
_APPLICATIONS_MODULE = "gpd.core.research_persona_applications"
_INGESTION_PAYLOAD_FUNCTIONS = (
    "build_research_persona_ingestion_payload",
    "build_research_persona_patch_from_sources",
    "build_research_persona_source_patch_payload",
    "build_research_persona_source_patch",
)
_DOPPELGANGER_PAYLOAD_FUNCTIONS = (
    "build_researcher_doppelganger_payload",
    "build_doppelganger_brief",
    "build_research_persona_doppelganger_payload",
)
_EXPLAIN_PLAN_PAYLOAD_FUNCTIONS = (
    "build_expertise_explanation_plan_payload",
    "build_expertise_explanation_plan",
    "build_research_persona_explain_plan_payload",
)
_TASTE_CHECK_PAYLOAD_FUNCTIONS = (
    "build_scientific_taste_check_payload",
    "build_scientific_taste_assessment",
    "build_research_persona_taste_check_payload",
)
_SOURCE_KIND_ALIASES = {
    "bib": "bibtex_import",
    "bibtex": "bibtex_import",
    "paper": "paper_import",
    "publication": "paper_import",
    "project": "project_scan",
    "repo": "repo_scan",
    "repository": "repo_scan",
    "user": "user_statement",
}


@runtime_checkable
class _ModelDumpable(Protocol):
    def model_dump(self, *, mode: str) -> object: ...


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_pydantic_errors(exc: PydanticValidationError) -> list[str]:
    messages: list[str] = []
    seen: set[str] = set()
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "value"
        message = str(error.get("msg", "validation failed")).strip() or "validation failed"
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        formatted = f"{location} {message}" if message.startswith("must ") else f"{location}: {message}"
        if formatted in seen:
            continue
        seen.add(formatted)
        messages.append(formatted)
    return messages or [str(exc)]


def _store_payload(data_root: Path | None) -> dict[str, object]:
    root = research_persona_root(data_root)
    path = research_persona_path(data_root)
    return {
        "root": str(root),
        "path": str(path),
        "exists": path.exists(),
    }


def _persona_counts_from_payload(payload: dict[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field_name in ("facts", "axes", *RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS):
        value = payload.get(field_name)
        counts[field_name] = len(value) if isinstance(value, list) else 0
    return counts


def _normalize_projection_for_cli(projection: str) -> str:
    return projection.strip().replace("-", "_")


def _input_path_payload(input_path: str | None, *, cwd: Path | None = None) -> tuple[str | None, bool | None]:
    if input_path is None:
        return None, None
    if input_path == "-":
        return "stdin", False
    target = Path(input_path)
    if not target.is_absolute() and cwd is not None:
        target = cwd / target
    return str(target), target.exists()


def _resolve_cli_output_path(output_path: str | None, *, cwd: Path | None = None) -> Path | None:
    if output_path is None:
        return None
    if output_path == "-":
        raise ResearchPersonaError("output path must be a file path, not stdin")
    target = Path(output_path).expanduser()
    if not target.is_absolute() and cwd is not None:
        target = cwd / target
    return target


def _write_json_artifact(path: Path, payload: object) -> Path:
    if path.exists() and path.is_dir():
        raise ResearchPersonaError(f"output path is a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path


def _jsonable_value(value: object) -> object:
    if isinstance(value, _ModelDumpable):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable_value(item) for item in value]
    return value


def _jsonable_mapping(value: object, *, context: str) -> dict[str, object]:
    data = _jsonable_value(value)
    if not isinstance(data, dict):
        raise ResearchPersonaError(f"{context} must return a JSON object")
    return data


def _import_persona_extension(module_name: str) -> ModuleType:
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise ResearchPersonaError(
                f"research persona support module is unavailable: missing {module_name}"
            ) from exc
        raise


def _call_with_supported_kwargs(handler: Callable[..., object], /, **kwargs: object) -> object:
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        return handler(**kwargs)

    parameters = signature.parameters
    accepts_kwargs = any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    if accepts_kwargs:
        return handler(**kwargs)

    supported_kwargs = {key: value for key, value in kwargs.items() if key in parameters and value is not None}
    return handler(**supported_kwargs)


def _call_persona_extension(module_name: str, function_names: tuple[str, ...], /, **kwargs: object) -> object:
    module = _import_persona_extension(module_name)
    for function_name in function_names:
        handler = getattr(module, function_name, None)
        if callable(handler):
            return _call_with_supported_kwargs(handler, **kwargs)
    joined = ", ".join(function_names)
    raise ResearchPersonaError(f"research persona support module {module_name} is missing one of: {joined}")


def _normalize_patch_payload(patch_data: object) -> dict[str, object]:
    patch = parse_research_persona_patch_data_strict(_jsonable_value(patch_data))
    return patch.model_dump(mode="json")


def _extract_candidate_patch(payload: dict[str, object]) -> dict[str, object]:
    raw_patch = payload.get("patch")
    if raw_patch is None:
        raw_patch = payload.get("candidate_patch")
    if raw_patch is None and "schema_version" in payload and "operations" in payload:
        raw_patch = payload
    if raw_patch is None:
        raise ResearchPersonaError("ingestion payload must include a candidate research persona patch")
    return _normalize_patch_payload(raw_patch)


def _source_kind_counts(patch: dict[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    source_kind = patch.get("source_kind")
    if isinstance(source_kind, str):
        counts[source_kind] = counts.get(source_kind, 0) + 1
    evidence = patch.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue
            item_source_kind = item.get("source_kind")
            if isinstance(item_source_kind, str):
                counts[item_source_kind] = counts.get(item_source_kind, 0) + 1
    return counts


def _default_evidence_summary(patch: dict[str, object]) -> dict[str, object]:
    operations = patch.get("operations")
    tombstones = patch.get("tombstones")
    evidence = patch.get("evidence")
    return {
        "operation_count": len(operations) if isinstance(operations, list) else 0,
        "tombstone_count": len(tombstones) if isinstance(tombstones, list) else 0,
        "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
        "source_kind_counts": _source_kind_counts(patch),
    }


def _review_route(*, output_path: str | None = None) -> dict[str, object]:
    patch_target = output_path or "<candidate-patch.json>"
    return {
        "kind": "candidate_patch",
        "approval_required": True,
        "diff_command": f"gpd research-persona diff {patch_target}",
        "apply_command": f"gpd research-persona apply-patch {patch_target}",
    }


def _capsule_descriptor(capsule: dict[str, object]) -> dict[str, object]:
    counts: dict[str, int] = {}
    for field_name in (
        "facts",
        "axes",
        "standing_preferences",
        "negative_preferences",
        "tools",
        "research_areas",
        "expertise",
        "workstyle",
        "scientific_taste",
    ):
        value = capsule.get(field_name)
        counts[field_name] = len(value) if isinstance(value, list) else 0
    return {
        "source": "research_persona_capsule",
        "role": capsule.get("role"),
        "purpose": capsule.get("purpose"),
        "counts": counts,
    }


def _ensure_positive_int(value: int, *, name: str) -> int:
    if value < 1:
        raise ResearchPersonaError(f"{name} must be at least 1")
    return value


def _source_documents_from_input(source_document: object, *, privacy_default: str) -> list[object]:
    if isinstance(source_document, Mapping):
        for key in ("sources", "documents"):
            documents = source_document.get(key)
            if not isinstance(documents, list):
                continue
            return [_source_document_with_privacy(document, privacy_default=privacy_default) for document in documents]
        return [_source_document_with_privacy(source_document, privacy_default=privacy_default)]
    if isinstance(source_document, list):
        return [
            _source_document_with_privacy(document, privacy_default=privacy_default) for document in source_document
        ]
    raise ResearchPersonaError("source JSON must be an object, a list of source objects, or an object with documents")


def _source_document_with_privacy(document: object, *, privacy_default: str) -> object:
    if not isinstance(document, Mapping):
        return document
    normalized = dict(document)
    if normalized.get("source_kind") is None and normalized.get("kind") is not None:
        raw_kind = str(normalized["kind"]).strip().casefold()
        normalized["source_kind"] = _SOURCE_KIND_ALIASES.get(raw_kind, raw_kind)
    normalized.pop("kind", None)
    if normalized.get("text") is None and normalized.get("summary") is not None:
        normalized["text"] = normalized["summary"]
    normalized.pop("summary", None)
    if normalized.get("privacy") is None and privacy_default != "private_local":
        normalized["privacy"] = privacy_default
    return normalized


def _compact_cli_text(value: object, *, limit: int = 240) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _document_summary(document: object, *, fallback: str | None = None) -> str | None:
    if isinstance(document, Mapping):
        for key in (
            "topic",
            "question",
            "project_summary",
            "summary",
            "title",
            "claim",
            "description",
            "task",
        ):
            text = _compact_cli_text(document.get(key))
            if text:
                return text
        steps = document.get("steps")
        if isinstance(steps, list):
            text = _compact_cli_text("; ".join(str(item) for item in steps[:3]))
            if text:
                return text
    if isinstance(document, list):
        text = _compact_cli_text("; ".join(str(item) for item in document[:3]))
        if text:
            return text
    return _compact_cli_text(fallback)


def _persona_counts(persona: ResearchPersona) -> dict[str, int]:
    return _persona_counts_from_payload(persona.model_dump(mode="json"))


def _projection_counts(projection: dict[str, object]) -> dict[str, int]:
    return _persona_counts_from_payload(projection)


def _fact_descriptor(fact: ResearchPersonaFact) -> dict[str, object]:
    return {
        "id": fact.id,
        "category": fact.category,
        "privacy": fact.privacy,
        "confidence": fact.confidence,
    }


def _axis_descriptor(axis: ResearchPersonaAxis) -> dict[str, object]:
    return {
        "id": axis.id,
        "privacy": axis.privacy,
        "confidence": axis.confidence,
        "fact_ids_count": len(axis.fact_ids),
        "has_name": axis.name is not None,
        "has_value": axis.value is not None,
    }


def _changed_fields(before: dict[str, object], after: dict[str, object]) -> list[str]:
    ignored = {"id"}
    return sorted(
        field_name
        for field_name in set(before) | set(after)
        if field_name not in ignored and before.get(field_name) != after.get(field_name)
    )


def _summarize_fact_diff(before: ResearchPersona, after: ResearchPersona) -> dict[str, object]:
    before_by_id = {fact.id: fact for fact in before.facts}
    after_by_id = {fact.id: fact for fact in after.facts}
    added_ids = sorted(set(after_by_id) - set(before_by_id))
    removed_ids = sorted(set(before_by_id) - set(after_by_id))
    changed: list[dict[str, object]] = []
    for fact_id in sorted(set(before_by_id) & set(after_by_id)):
        before_payload = before_by_id[fact_id].model_dump(mode="json")
        after_payload = after_by_id[fact_id].model_dump(mode="json")
        fields = _changed_fields(before_payload, after_payload)
        if not fields:
            continue
        changed.append(
            {
                "id": fact_id,
                "before": _fact_descriptor(before_by_id[fact_id]),
                "after": _fact_descriptor(after_by_id[fact_id]),
                "changed_fields": fields,
            }
        )
    return {
        "added": [_fact_descriptor(after_by_id[fact_id]) for fact_id in added_ids],
        "removed": [_fact_descriptor(before_by_id[fact_id]) for fact_id in removed_ids],
        "changed": changed,
    }


def _summarize_axis_diff(before: ResearchPersona, after: ResearchPersona) -> dict[str, object]:
    before_by_id = {axis.id: axis for axis in before.axes}
    after_by_id = {axis.id: axis for axis in after.axes}
    added_ids = sorted(set(after_by_id) - set(before_by_id))
    removed_ids = sorted(set(before_by_id) - set(after_by_id))
    changed: list[dict[str, object]] = []
    for axis_id in sorted(set(before_by_id) & set(after_by_id)):
        before_payload = before_by_id[axis_id].model_dump(mode="json")
        after_payload = after_by_id[axis_id].model_dump(mode="json")
        fields = _changed_fields(before_payload, after_payload)
        if not fields:
            continue
        changed.append(
            {
                "id": axis_id,
                "before": _axis_descriptor(before_by_id[axis_id]),
                "after": _axis_descriptor(after_by_id[axis_id]),
                "changed_fields": fields,
            }
        )
    return {
        "added": [_axis_descriptor(after_by_id[axis_id]) for axis_id in added_ids],
        "removed": [_axis_descriptor(before_by_id[axis_id]) for axis_id in removed_ids],
        "changed": changed,
    }


def _summarize_list_diff(before: ResearchPersona, after: ResearchPersona) -> dict[str, object]:
    fields: dict[str, object] = {}
    for field_name in RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS:
        before_values = list(getattr(before, field_name))
        after_values = list(getattr(after, field_name))
        before_set = set(before_values)
        after_set = set(after_values)
        fields[field_name] = {
            "before_count": len(before_values),
            "after_count": len(after_values),
            "added_count": len(after_set - before_set),
            "removed_count": len(before_set - after_set),
            "changed": before_values != after_values,
        }
    return fields


def _would_history_path(data_root: Path | None) -> Path:
    return research_persona_root(data_root) / "history" / "events.jsonl"


def _would_tombstone_path(data_root: Path | None) -> Path:
    return research_persona_root(data_root) / "tombstones" / "events.jsonl"


def _patch_tombstones(patch: ResearchPersonaPatch, *, created_at: str) -> list[ResearchPersonaTombstone]:
    tombstones: list[ResearchPersonaTombstone] = []
    seen: set[str] = set()
    for tombstone in patch.tombstones:
        if tombstone.fact_id in seen:
            continue
        seen.add(tombstone.fact_id)
        tombstones.append(tombstone)
    for operation in patch.operations:
        if operation.tombstone is not None:
            tombstone = operation.tombstone
        elif operation.op == "tombstone_fact" and operation.fact_id is not None:
            tombstone = ResearchPersonaTombstone(
                fact_id=operation.fact_id,
                reason=operation.reason or patch.reason,
                source_kind=patch.source_kind,
                created_at=created_at,
            )
        else:
            continue
        if tombstone.fact_id in seen:
            continue
        seen.add(tombstone.fact_id)
        tombstones.append(tombstone)
    return tombstones


def parse_research_persona_patch_data_strict(data: object) -> ResearchPersonaPatch:
    """Parse strict patch data for future CLI wrappers."""

    if isinstance(data, ResearchPersonaPatch):
        return data
    if not isinstance(data, dict):
        raise ResearchPersonaError("research persona patch must be a JSON object")
    try:
        return ResearchPersonaPatch.model_validate(data)
    except PydanticValidationError as exc:
        raise ResearchPersonaError("; ".join(_format_pydantic_errors(exc))) from exc


def summarize_research_persona_diff(before: ResearchPersona, after: ResearchPersona) -> dict[str, object]:
    """Return a value-redacted before/after summary."""

    if not isinstance(before, ResearchPersona) or not isinstance(after, ResearchPersona):
        raise ResearchPersonaError("research persona diff requires ResearchPersona instances")
    counts_before = _persona_counts(before)
    counts_after = _persona_counts(after)
    return {
        "updated": before.model_dump(mode="json") != after.model_dump(mode="json"),
        "counts": {
            "before": counts_before,
            "after": counts_after,
            "delta": {field_name: counts_after[field_name] - counts_before[field_name] for field_name in counts_before},
        },
        "facts": _summarize_fact_diff(before, after),
        "axes": _summarize_axis_diff(before, after),
        "lists": _summarize_list_diff(before, after),
    }


def research_persona_show_payload(
    *,
    data_root: Path | None = None,
    projection: str = "local",
    strict: bool = True,
) -> dict[str, object]:
    """Return path, existence, count, and projection data without writing files."""

    persona = load_research_persona(data_root, strict=strict)
    projected = project_research_persona(persona, purpose=_normalize_projection_for_cli(projection))
    return {
        **_store_payload(data_root),
        "counts": _persona_counts(persona),
        "projection_counts": _projection_counts(projected),
        "projection": projected,
    }


def research_persona_validate_payload(
    data: object,
    *,
    path: str | Path | None = None,
    exists: bool | None = None,
) -> dict[str, object]:
    """Validate arbitrary research-persona JSON data for CLI output."""

    result = validate_research_persona(data)
    payload: dict[str, object] = result.model_dump(mode="json")
    if path is not None:
        payload["path"] = str(path)
    if exists is not None:
        payload["exists"] = exists
    if result.valid:
        persona = parse_research_persona_data_strict(data)
        payload["counts"] = _persona_counts(persona)
    return payload


def research_persona_diff_payload(
    patch_data: object,
    *,
    data_root: Path | None = None,
) -> dict[str, object]:
    """Return the value-redacted diff a patch would produce without writing files."""

    patch = parse_research_persona_patch_data_strict(patch_data)
    before = load_research_persona(data_root, strict=True)
    after = apply_research_persona_patch(before, patch)
    diff = summarize_research_persona_diff(before, after)
    return {
        **_store_payload(data_root),
        "would_update": diff["updated"],
        "diff": diff,
    }


def research_persona_apply_patch_payload(
    patch_data: object,
    *,
    data_root: Path | None = None,
    dry_run: bool = False,
    actor: str | None = None,
    summary: str | None = None,
    event_type: str = "patch_applied",
    now: str | None = None,
) -> dict[str, object]:
    """Strict-load, apply, and optionally persist a research-persona patch."""

    patch = parse_research_persona_patch_data_strict(patch_data)
    before = load_research_persona(data_root, strict=True)
    after = apply_research_persona_patch(before, patch)
    diff = summarize_research_persona_diff(before, after)
    created_at = now or _utc_now()
    tombstones = _patch_tombstones(patch, created_at=created_at)
    payload: dict[str, object] = {
        **_store_payload(data_root),
        "updated": diff["updated"],
        "dry_run": dry_run,
        "diff": diff,
        "history_path": str(_would_history_path(data_root)),
        "tombstone_path": str(_would_tombstone_path(data_root)),
        "tombstones": {
            "count": len(tombstones),
            "fact_ids": sorted(tombstone.fact_id for tombstone in tombstones),
        },
    }
    if dry_run:
        return payload

    saved_path = save_research_persona(after, data_root)
    event = ResearchPersonaHistoryEvent(
        event_type=event_type,
        summary=summary or patch.reason or "Applied research persona patch.",
        source_kind=patch.source_kind,
        created_at=created_at,
        actor=actor,
        patch=patch,
    )
    history_path = append_research_persona_history(event, data_root)
    tombstone_path = _would_tombstone_path(data_root)
    for tombstone in tombstones:
        tombstone_path = append_research_persona_tombstone(tombstone, data_root)

    payload.update(
        {
            "path": str(saved_path),
            "exists": saved_path.exists(),
            "history_path": str(history_path),
            "tombstone_path": str(tombstone_path),
        }
    )
    return payload


def research_persona_forget_fact_payload(
    fact_id: str,
    *,
    data_root: Path | None = None,
    reason: str | None = None,
    dry_run: bool = False,
    actor: str | None = None,
    now: str | None = None,
) -> dict[str, object]:
    """Forget a fact through a tombstone patch and return the apply payload."""

    fact_id = fact_id.strip()
    if not fact_id:
        raise ResearchPersonaError("fact_id must not be blank")
    created_at = now or _utc_now()
    tombstone = ResearchPersonaTombstone(
        fact_id=fact_id,
        reason=reason,
        source_kind="manual_patch",
        created_at=created_at,
    )
    patch = ResearchPersonaPatch(
        tombstones=[tombstone],
        operations=[
            ResearchPersonaPatchOperation(
                op="tombstone_fact",
                fact_id=fact_id,
                reason=reason,
            )
        ],
        source_kind="manual_patch",
        reason=reason or "Forgot research persona fact.",
    )
    payload = research_persona_apply_patch_payload(
        patch,
        data_root=data_root,
        dry_run=dry_run,
        actor=actor,
        summary=reason or f"Forgot research persona fact {fact_id}.",
        event_type="fact_forgotten",
        now=created_at,
    )
    payload["forgot_fact_id"] = fact_id
    return payload


def research_persona_export_capsule_payload(
    *,
    role: str,
    data_root: Path | None = None,
) -> dict[str, object]:
    """Return a prompt-safe capsule payload from the strict local profile."""

    persona = load_research_persona(data_root, strict=True)
    capsule: ResearchPersonaCapsule = build_research_persona_capsule(persona, role=role)
    return capsule.model_dump(mode="json")


def research_persona_audit_payload(
    data: object,
    *,
    path: str | Path | None = None,
    exists: bool | None = None,
    now: str | None = None,
    stale_after_days: int = 180,
    include_info: bool = True,
) -> dict[str, object]:
    """Return a strict read-only research persona audit payload."""

    report = audit_research_persona_profile(
        data,
        now=now,
        stale_after_days=stale_after_days,
        include_info=include_info,
    )
    payload = report.model_dump(mode="json")
    if path is not None:
        payload["path"] = str(path)
    if exists is not None:
        payload["exists"] = exists
    payload["review_route"] = _review_route()
    return payload


def research_persona_ingest_source_payload(
    source_document: object,
    *,
    cwd: Path | None = None,
    source_path: str | None = None,
    output_path: str | None = None,
    dry_run: bool = False,
    privacy_default: str = "private_local",
) -> dict[str, object]:
    """Build a candidate persona patch from explicit source data without touching the persona store."""

    sources = _source_documents_from_input(source_document, privacy_default=privacy_default)
    core_result = _call_persona_extension(
        _INGESTION_MODULE,
        _INGESTION_PAYLOAD_FUNCTIONS,
        sources=sources,
        source_document=source_document,
        document=source_document,
        source_path=source_path,
        cwd=cwd,
        privacy_default=privacy_default,
        privacy_defaults={
            "fact_privacy": privacy_default,
            "source_document_privacy": "private_local",
            "requires_user_review": True,
        },
    )
    payload = _jsonable_mapping(core_result, context="research persona ingestion")
    core_returned_patch = payload.get("patch") is None and payload.get("candidate_patch") is None
    core_returned_patch = core_returned_patch and "schema_version" in payload and "operations" in payload
    patch = _extract_candidate_patch(payload)
    if core_returned_patch:
        payload = {}
    payload["patch"] = patch
    payload.pop("candidate_patch", None)
    payload.setdefault("evidence_summary", _default_evidence_summary(patch))
    payload.setdefault(
        "privacy_defaults",
        {
            "fact_privacy": privacy_default,
            "source_document_privacy": "private_local",
            "requires_user_review": True,
        },
    )

    target = _resolve_cli_output_path(output_path, cwd=cwd)
    output_written = False
    if target is not None and not dry_run:
        _write_json_artifact(target, patch)
        output_written = True
    output_path_text = str(target) if target is not None else None
    payload["review_route"] = _review_route(output_path=output_path_text)
    payload["source"] = {"path": source_path, "explicit_document": True}
    payload["dry_run"] = dry_run
    payload["writes_persona_storage"] = False
    payload["output"] = {
        "path": output_path_text,
        "written": output_written,
        "artifact_kind": "candidate_patch",
    }
    return payload


def _research_persona_application_payload(
    *,
    application: str,
    capsule_role: str,
    function_names: tuple[str, ...],
    data_root: Path | None = None,
    task: str | None = None,
    plan_document: object | None = None,
    candidate_document: object | None = None,
    focus: str | None = None,
    audience: str | None = None,
    max_items: int = 8,
) -> dict[str, object]:
    max_items = _ensure_positive_int(max_items, name="max_items")
    capsule = research_persona_export_capsule_payload(role=capsule_role, data_root=data_root)
    capsule_model = ResearchPersonaCapsule.model_validate(capsule)
    project_summary = _document_summary(plan_document) or _document_summary(candidate_document) or focus
    topic = _compact_cli_text(task) or _compact_cli_text(focus) or project_summary or "research work"
    question = _compact_cli_text(task) or _document_summary(plan_document) or "How should this plan be explained?"
    taste_summary = (
        _document_summary(candidate_document)
        or _compact_cli_text(task)
        or _compact_cli_text(focus)
        or "candidate research direction"
    )
    core_result = _call_persona_extension(
        _APPLICATIONS_MODULE,
        function_names,
        persona_or_capsule=capsule_model,
        capsule=capsule,
        persona_capsule=capsule,
        task=task,
        topic=topic,
        question=question,
        project_summary=taste_summary if application == "taste_check" else project_summary,
        plan=plan_document,
        plan_document=plan_document,
        candidate=candidate_document,
        candidate_document=candidate_document,
        focus=focus,
        audience=audience,
        max_items=max_items,
    )
    payload = _jsonable_mapping(core_result, context=f"research persona {application}")
    payload.setdefault("application", application)
    payload.setdefault("mode", "advisory_preview")
    payload.setdefault("prompt_safe", True)
    payload.setdefault("raw_profile_exposed", False)
    payload.setdefault("persona_capsule", _capsule_descriptor(capsule))
    payload.setdefault("inputs", {})
    if isinstance(payload["inputs"], dict):
        payload["inputs"].setdefault("task", task)
        payload["inputs"].setdefault("has_plan_document", plan_document is not None)
        payload["inputs"].setdefault("has_candidate_document", candidate_document is not None)
        payload["inputs"].setdefault("focus", focus)
        payload["inputs"].setdefault("audience", audience)
        payload["inputs"].setdefault("max_items", max_items)
    return payload


def research_persona_doppelganger_payload(
    *,
    data_root: Path | None = None,
    task: str | None = None,
    focus: str | None = None,
    max_items: int = 8,
) -> dict[str, object]:
    """Return a prompt-safe Researcher Doppelganger advisory preview."""

    return _research_persona_application_payload(
        application="doppelganger",
        capsule_role="doppelganger",
        function_names=_DOPPELGANGER_PAYLOAD_FUNCTIONS,
        data_root=data_root,
        task=task,
        focus=focus,
        max_items=max_items,
    )


def research_persona_explain_plan_payload(
    *,
    data_root: Path | None = None,
    plan_document: object | None = None,
    task: str | None = None,
    audience: str | None = None,
    max_items: int = 8,
) -> dict[str, object]:
    """Return a prompt-safe Expertise-Aware Explanations plan preview."""

    return _research_persona_application_payload(
        application="explain_plan",
        capsule_role="explainer",
        function_names=_EXPLAIN_PLAN_PAYLOAD_FUNCTIONS,
        data_root=data_root,
        task=task,
        plan_document=plan_document,
        audience=audience,
        max_items=max_items,
    )


def research_persona_taste_check_payload(
    *,
    data_root: Path | None = None,
    candidate_document: object | None = None,
    task: str | None = None,
    focus: str | None = None,
    max_items: int = 8,
) -> dict[str, object]:
    """Return a prompt-safe Scientific Taste Model advisory preview."""

    return _research_persona_application_payload(
        application="taste_check",
        capsule_role="taste",
        function_names=_TASTE_CHECK_PAYLOAD_FUNCTIONS,
        data_root=data_root,
        task=task,
        candidate_document=candidate_document,
        focus=focus,
        max_items=max_items,
    )


def build_show_payload(*, cwd: Path | None = None, projection: str = "local") -> dict[str, object]:
    """CLI wrapper for the stored-profile show command."""

    return research_persona_show_payload(projection=projection)


def build_validate_payload(
    *,
    cwd: Path | None = None,
    document: object | None = None,
    input_path: str | None = None,
) -> dict[str, object]:
    """CLI wrapper for validating a stored profile, JSON file, or stdin."""

    path_text, exists = _input_path_payload(input_path, cwd=cwd)
    if document is not None:
        return research_persona_validate_payload(document, path=path_text, exists=exists)

    stored_path = research_persona_path()
    persona = load_research_persona(strict=True)
    return research_persona_validate_payload(
        persona.model_dump(mode="json"),
        path=str(stored_path),
        exists=stored_path.exists(),
    )


def build_audit_payload(
    *,
    cwd: Path | None = None,
    document: object | None = None,
    input_path: str | None = None,
    now: str | None = None,
    stale_after_days: int = 180,
    include_info: bool = True,
) -> dict[str, object]:
    """CLI wrapper for read-only stored-profile or input-document audit."""

    path_text, exists = _input_path_payload(input_path, cwd=cwd)
    if document is not None:
        return research_persona_audit_payload(
            document,
            path=path_text,
            exists=exists,
            now=now,
            stale_after_days=stale_after_days,
            include_info=include_info,
        )

    stored_path = research_persona_path()
    if stored_path.exists():
        try:
            stored_document: object = json.loads(stored_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            stored_document = {"schema_version": None, "facts": [{"id": "profile-json", "value": str(exc)}]}
    else:
        stored_document = ResearchPersona().model_dump(mode="json")
    return research_persona_audit_payload(
        stored_document,
        path=str(stored_path),
        exists=stored_path.exists(),
        now=now,
        stale_after_days=stale_after_days,
        include_info=include_info,
    )


def build_diff_payload(
    *,
    cwd: Path | None = None,
    patch_document: object,
    patch_path: str | None = None,
) -> dict[str, object]:
    """CLI wrapper for a read-only patch diff."""

    payload = research_persona_diff_payload(patch_document)
    path_text, exists = _input_path_payload(patch_path, cwd=cwd)
    if path_text is not None:
        payload["patch_path"] = path_text
        payload["patch_exists"] = exists
    return payload


def build_apply_patch_payload(
    *,
    cwd: Path | None = None,
    patch_document: object,
    patch_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """CLI wrapper for applying a governed patch."""

    payload = research_persona_apply_patch_payload(patch_document, dry_run=dry_run, actor="gpd-cli")
    path_text, exists = _input_path_payload(patch_path, cwd=cwd)
    if path_text is not None:
        payload["patch_path"] = path_text
        payload["patch_exists"] = exists
    return payload


def build_forget_payload(
    *,
    cwd: Path | None = None,
    fact_id: str,
    reason: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """CLI wrapper for tombstoning one fact by id."""

    return research_persona_forget_fact_payload(
        fact_id,
        reason=reason,
        dry_run=dry_run,
        actor="gpd-cli",
    )


def build_export_capsule_payload(*, cwd: Path | None = None, role: str) -> dict[str, object]:
    """CLI wrapper for a prompt-safe role capsule."""

    return research_persona_export_capsule_payload(role=role)


def build_ingest_source_payload(
    *,
    cwd: Path | None = None,
    source_document: object,
    source_path: str | None = None,
    output_path: str | None = None,
    dry_run: bool = False,
    privacy_default: str = "private_local",
) -> dict[str, object]:
    """CLI wrapper for source ingestion candidate-patch generation."""

    payload = research_persona_ingest_source_payload(
        source_document,
        cwd=cwd,
        source_path=source_path,
        output_path=output_path,
        dry_run=dry_run,
        privacy_default=privacy_default,
    )
    path_text, exists = _input_path_payload(source_path, cwd=cwd)
    payload["source_path"] = path_text
    payload["source_exists"] = exists
    return payload


def build_doppelganger_payload(
    *,
    cwd: Path | None = None,
    task: str | None = None,
    focus: str | None = None,
    max_items: int = 8,
) -> dict[str, object]:
    """CLI wrapper for the Researcher Doppelganger preview."""

    return research_persona_doppelganger_payload(task=task, focus=focus, max_items=max_items)


def build_explain_plan_payload(
    *,
    cwd: Path | None = None,
    plan_document: object | None = None,
    plan_path: str | None = None,
    task: str | None = None,
    audience: str | None = None,
    max_items: int = 8,
) -> dict[str, object]:
    """CLI wrapper for the expertise-aware explanation preview."""

    payload = research_persona_explain_plan_payload(
        plan_document=plan_document,
        task=task,
        audience=audience,
        max_items=max_items,
    )
    path_text, exists = _input_path_payload(plan_path, cwd=cwd)
    if path_text is not None:
        payload["plan_path"] = path_text
        payload["plan_exists"] = exists
    return payload


def build_taste_check_payload(
    *,
    cwd: Path | None = None,
    candidate_document: object | None = None,
    candidate_path: str | None = None,
    task: str | None = None,
    focus: str | None = None,
    max_items: int = 8,
) -> dict[str, object]:
    """CLI wrapper for the scientific taste advisory preview."""

    payload = research_persona_taste_check_payload(
        candidate_document=candidate_document,
        task=task,
        focus=focus,
        max_items=max_items,
    )
    path_text, exists = _input_path_payload(candidate_path, cwd=cwd)
    if path_text is not None:
        payload["candidate_path"] = path_text
        payload["candidate_exists"] = exists
    return payload
