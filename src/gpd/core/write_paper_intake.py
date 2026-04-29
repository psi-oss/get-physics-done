"""Shared resolution helpers for ``write-paper --intake`` launch payloads."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError as PydanticValidationError

from gpd.core.constants import ProjectLayout
from gpd.core.utils import normalize_ascii_slug

if TYPE_CHECKING:
    from gpd.mcp.paper.models import WritePaperAuthoringInput


@dataclass(frozen=True, slots=True)
class WritePaperExternalAuthoringIntakeResolution:
    """Validated external-authoring intake details for bounded ``write-paper`` bootstrap."""

    status: str
    intake_path: Path | None
    manuscript_root: Path | None
    intake_root: Path | None
    subject_slug: str | None
    manifest: WritePaperAuthoringInput | None = None
    detail: str = ""


def split_write_paper_launch_arguments(arguments: str | None) -> list[str]:
    """Split a raw write-paper launch argument string into shell-like tokens."""

    if not arguments:
        return []
    try:
        return shlex.split(arguments)
    except ValueError:
        return arguments.split()


def flag_values(arguments: str | None, *flags: str) -> list[str]:
    """Return non-empty values supplied to one or more long flags."""

    tokens = split_write_paper_launch_arguments(arguments)
    values: list[str] = []
    skip_next = False
    flag_set = set(flags)

    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            break
        if token in flag_set:
            skip_next = True
            if index + 1 >= len(tokens):
                continue
            next_token = tokens[index + 1].strip()
            if next_token and not next_token.startswith("-"):
                values.append(next_token)
            continue
        matched_flag = next((flag for flag in flags if token.startswith(f"{flag}=")), None)
        if matched_flag is None:
            continue
        value = token.partition("=")[2].strip()
        if value:
            values.append(value)

    return values


def write_paper_external_authoring_intake_argument(arguments: str | None) -> str | None:
    """Return the explicit ``--intake`` manifest path supplied to ``write-paper``."""

    flagged = flag_values(arguments, "--intake")
    return flagged[-1] if flagged else None


def has_write_paper_external_authoring_intake(arguments: str | None) -> bool:
    """Return whether ``write-paper`` received an explicit ``--intake`` flag."""

    return write_paper_external_authoring_intake_argument(arguments) is not None


def write_paper_external_authoring_subject_slug(manifest: WritePaperAuthoringInput) -> str:
    """Return the managed publication subject slug for one external-authoring intake."""

    explicit_slug = str(getattr(manifest, "subject_slug", "") or "").strip()
    if explicit_slug:
        return explicit_slug
    derived_slug = normalize_ascii_slug(str(getattr(manifest, "title", "") or "")) or "paper"
    return derived_slug[:48].rstrip("-") or "paper"


def _format_display_path(target: str | Path | None) -> str:
    if target is None:
        return ""
    return Path(target).expanduser().resolve(strict=False).as_posix()


def _format_pydantic_schema_error(error: dict[str, object], *, root_label: str) -> str:
    """Return a concise schema error matching the CLI's public error shape."""

    location = ".".join(str(part) for part in error.get("loc", ()) if str(part))
    label = f"{root_label}.{location}" if location else root_label
    message = str(error.get("msg", "validation failed")).strip() or "validation failed"
    input_value = error.get("input")

    if message == "Field required":
        return f"{label} is required"
    if "valid dictionary" in message.lower():
        return f"{label} must be an object, not {type(input_value).__name__}"
    if "valid list" in message.lower():
        return f"{label} must be an array, not {type(input_value).__name__}"
    return f"{label}: {message}"


def _resolve_subject_path(subject: str | None, *, base: Path) -> Path | None:
    if not isinstance(subject, str) or not subject.strip():
        return None
    target = Path(subject)
    if not target.is_absolute():
        target = base / target
    return target.resolve(strict=False)


def _load_json_document(input_path: Path) -> object:
    source = _format_display_path(input_path)
    try:
        raw = input_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"JSON input not found: {source}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError(f"JSON input is not valid UTF-8: {source}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Failed to read JSON input from {source}: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from {source}: {exc}") from exc


def resolve_write_paper_external_authoring_intake(
    project_root: Path,
    arguments: str | None,
    *,
    workspace_cwd: Path | None = None,
) -> WritePaperExternalAuthoringIntakeResolution | None:
    """Validate the bounded external-authoring intake manifest for ``write-paper``."""

    from gpd.mcp.paper.models import WritePaperAuthoringInput

    intake_argument = write_paper_external_authoring_intake_argument(arguments)
    if intake_argument is None:
        return None

    resolved_project_root = Path(project_root).resolve(strict=False)
    workspace_root = (workspace_cwd or resolved_project_root).resolve(strict=False)
    intake_path = (
        _resolve_subject_path(intake_argument, base=workspace_root) or (workspace_root / intake_argument)
    ).resolve(strict=False)
    if intake_path.suffix.lower() != ".json":
        return WritePaperExternalAuthoringIntakeResolution(
            status="invalid",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"write-paper `--intake` must point to a JSON file: {_format_display_path(intake_path)}",
        )
    if not intake_path.exists():
        return WritePaperExternalAuthoringIntakeResolution(
            status="missing",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"missing write-paper intake manifest {_format_display_path(intake_path)}",
        )
    if intake_path.is_dir():
        return WritePaperExternalAuthoringIntakeResolution(
            status="invalid",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"write-paper `--intake` must point to a JSON file, not a directory: {_format_display_path(intake_path)}",
        )

    try:
        payload = _load_json_document(intake_path)
    except ValueError as exc:
        return WritePaperExternalAuthoringIntakeResolution(
            status="invalid",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"could not load write-paper intake manifest: {exc}",
        )
    if not isinstance(payload, dict):
        return WritePaperExternalAuthoringIntakeResolution(
            status="invalid",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"write-paper intake manifest must be a JSON object: {_format_display_path(intake_path)}",
        )

    try:
        manifest = WritePaperAuthoringInput.model_validate(payload)
    except PydanticValidationError as exc:
        details = "; ".join(
            _format_pydantic_schema_error(error, root_label="write_paper_authoring_input")
            for error in exc.errors()[:3]
        )
        return WritePaperExternalAuthoringIntakeResolution(
            status="invalid",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"write-paper intake manifest is invalid: {details}",
        )

    subject_slug = write_paper_external_authoring_subject_slug(manifest)
    layout = ProjectLayout(resolved_project_root)
    manuscript_root = layout.publication_manuscript_dir(subject_slug)
    intake_root = layout.publication_intake_dir(subject_slug)
    return WritePaperExternalAuthoringIntakeResolution(
        status="resolved",
        intake_path=intake_path,
        manuscript_root=manuscript_root,
        intake_root=intake_root,
        subject_slug=subject_slug,
        manifest=manifest,
        detail=(
            f"validated external authoring intake {_format_display_path(intake_path)}; "
            f"managed manuscript bootstrap will use {_format_display_path(manuscript_root)}"
        ),
    )


def reject_write_paper_intake_inside_project_detail() -> str:
    """Return the explicit fail-closed detail for project-backed ``--intake`` launches."""

    return (
        "write-paper `--intake` is only allowed from a workspace without an initialized GPD project; "
        "omit `--intake` for project-backed write-paper or launch from a projectless external-authoring workspace"
    )
