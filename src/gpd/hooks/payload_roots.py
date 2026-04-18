"""Shared payload root resolution for runtime hook surfaces.

This keeps the raw runtime workspace path distinct from the resolved GPD
project root so hook consumers can use one source of truth for both.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from gpd.core.root_resolution import RootResolutionBasis, resolve_project_root, resolve_project_roots


@dataclass(frozen=True)
class PayloadRoots:
    workspace_dir: str
    project_root: str
    project_dir_present: bool = False
    project_dir_trusted: bool = False
    target_path: str | None = None
    target_root: str | None = None


def _object_value(value: object, key: str) -> object | None:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _first_string(value: object, *keys: str) -> str:
    for key in keys:
        candidate = _object_value(value, key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return ""


def _first_bool(value: object, *keys: str) -> bool | None:
    for key in keys:
        candidate = _object_value(value, key)
        if isinstance(candidate, bool):
            return candidate
    return None


def normalize_workspace_text(value: str | None) -> str:
    if not value:
        return str(Path.cwd().resolve(strict=False))
    path = Path(value).expanduser()
    try:
        return str(path.resolve(strict=False))
    except OSError:
        return str(path)


def normalize_optional_path_text(value: str | None, *, base_dir: str | None = None) -> str | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute() and base_dir:
        path = Path(base_dir).expanduser() / path
    try:
        return str(path.resolve(strict=False))
    except OSError:
        return str(path)


def _project_dir_from_payload(data: dict[str, object], *, hook_payload: object) -> str:
    workspace_value = data.get("workspace")
    return _first_string(workspace_value, *hook_payload.project_dir_keys) or _first_string(
        data,
        *hook_payload.project_dir_keys,
    )


def _target_path_from_payload(
    data: dict[str, object],
    *,
    hook_payload: object,
    workspace_dir: str,
) -> str | None:
    workspace_value = data.get("workspace")
    target_path_keys = tuple(getattr(hook_payload, "target_path_keys", ()) or ())
    return normalize_optional_path_text(
        _first_string(workspace_value, *target_path_keys) or _first_string(data, *target_path_keys),
        base_dir=workspace_dir,
    )


def _target_root_from_payload(
    data: dict[str, object],
    *,
    hook_payload: object,
    workspace_dir: str,
) -> str | None:
    workspace_value = data.get("workspace")
    target_root_keys = tuple(getattr(hook_payload, "target_root_keys", ()) or ())
    return normalize_optional_path_text(
        _first_string(workspace_value, *target_root_keys) or _first_string(data, *target_root_keys),
        base_dir=workspace_dir,
    )


def payload_uses_alias_only_workspace_mapping(
    data: dict[str, object],
    *,
    hook_payload: object,
) -> bool:
    """Return whether the payload used only non-primary workspace aliases.

    Hook payload root extraction accepts `project_dir` / `project_root` hints
    from either `data["workspace"]` or the top level. Keep the trust downgrade
    aligned with that same contract so alias-only workspace mappings cannot
    accidentally leave an unrelated top-level project hint authoritative.
    """

    workspace_keys = tuple(getattr(hook_payload, "workspace_keys", ()) or ())
    project_dir_keys = tuple(getattr(hook_payload, "project_dir_keys", ()) or ())
    if not workspace_keys or not project_dir_keys:
        return False

    workspace_value = data.get("workspace")
    if isinstance(workspace_value, dict):
        candidate_mapping: dict[str, object] = workspace_value
    elif workspace_value is None:
        candidate_mapping = data
    else:
        return False

    return bool(
        _first_string(candidate_mapping, *workspace_keys)
        and _project_dir_from_payload(data, hook_payload=hook_payload)
        and not _first_string(candidate_mapping, "cwd")
    )


def _workspace_is_within_project_dir(workspace_dir: str, project_dir: str) -> bool:
    if not workspace_dir or not project_dir:
        return False
    workspace_path = Path(workspace_dir).expanduser().resolve(strict=False)
    project_path = Path(project_dir).expanduser().resolve(strict=False)
    try:
        workspace_path.relative_to(project_path)
    except ValueError:
        return False
    return True


def _project_dir_is_trusted(workspace_dir: str, project_dir: str) -> bool:
    if not project_dir:
        return False
    if not _workspace_is_within_project_dir(workspace_dir, project_dir):
        return False
    resolution = resolve_project_roots(workspace_dir, project_dir=project_dir)
    return bool(
        resolution is not None
        and resolution.basis == RootResolutionBasis.PROJECT_DIR
        and resolution.has_project_layout
    )


def _authoritative_project_root(
    workspace_dir: str,
    candidate_project_root: str,
    *,
    project_dir_present: bool,
    project_dir_trusted: bool,
) -> str:
    normalized_workspace = normalize_workspace_text(workspace_dir)
    normalized_candidate = normalize_workspace_text(candidate_project_root)
    if not project_dir_present or project_dir_trusted:
        return normalized_candidate

    workspace_resolution = resolve_project_roots(normalized_workspace)
    if workspace_resolution is not None and workspace_resolution.has_project_layout:
        project_root = workspace_resolution.project_root
        if project_root is not None:
            return str(project_root)
    return normalized_workspace


def _policy_root_resolution_service(hook_payload: object) -> Callable[..., object] | None:
    for key in (
        "root_resolution_service",
        "payload_root_resolution_service",
        "resolve_payload_roots",
        "resolve_roots",
    ):
        candidate = getattr(hook_payload, key, None)
        if callable(candidate):
            return candidate
    return None


def _coerce_root_pair(
    value: object,
    *,
    fallback_workspace_dir: str,
) -> PayloadRoots | None:
    workspace_dir = ""
    project_root = ""
    project_dir_present = False
    project_dir_trusted = False
    target_path: str | None = None
    target_root: str | None = None

    if isinstance(value, str) and value:
        project_root = value
    elif isinstance(value, (tuple, list)) and len(value) >= 2:
        workspace_candidate, project_candidate = value[0], value[1]
        if isinstance(workspace_candidate, str) and workspace_candidate:
            workspace_dir = workspace_candidate
        if isinstance(project_candidate, str) and project_candidate:
            project_root = project_candidate
        if len(value) >= 3 and isinstance(value[2], str) and value[2]:
            target_path = value[2]
        if len(value) >= 4 and isinstance(value[3], str) and value[3]:
            target_root = value[3]
    else:
        workspace_dir = _first_string(
            value,
            "workspace_dir",
            "workspace_root",
            "cwd",
        )
        project_root = _first_string(
            value,
            "project_root",
            "project_dir",
            "root",
        )
        project_dir_present = bool(_first_bool(value, "project_dir_present"))
        project_dir_trusted = bool(_first_bool(value, "project_dir_trusted"))
        target_path = _first_string(value, "target_path") or None
        target_root = _first_string(value, "target_root") or None

    if not project_root:
        return None
    return PayloadRoots(
        workspace_dir=normalize_workspace_text(workspace_dir or fallback_workspace_dir),
        project_root=normalize_workspace_text(project_root),
        project_dir_present=project_dir_present,
        project_dir_trusted=project_dir_trusted,
        target_path=normalize_optional_path_text(target_path, base_dir=workspace_dir or fallback_workspace_dir),
        target_root=normalize_optional_path_text(target_root, base_dir=workspace_dir or fallback_workspace_dir),
    )


def _resolve_with_shared_service(
    data: dict[str, object],
    *,
    workspace_dir: str,
    project_dir: str,
    target_path: str | None = None,
    target_root: str | None = None,
    hook_payload: object,
    cwd: str | None = None,
) -> PayloadRoots | None:
    service = _policy_root_resolution_service(hook_payload)
    if service is None:
        return None

    attempts = (
        {
            "payload": data,
            "workspace_dir": workspace_dir,
            "project_dir": project_dir,
            "target_path": target_path,
            "target_root": target_root,
            "cwd": cwd,
        },
        {
            "data": data,
            "workspace_dir": workspace_dir,
            "project_dir": project_dir,
            "target_path": target_path,
            "target_root": target_root,
            "cwd": cwd,
        },
        {
            "workspace_dir": workspace_dir,
            "project_dir": project_dir,
            "target_path": target_path,
            "target_root": target_root,
            "cwd": cwd,
        },
        {
            "workspace_dir": workspace_dir,
            "project_dir": project_dir,
            "target_path": target_path,
            "target_root": target_root,
        },
        {"cwd": workspace_dir, "project_dir": project_dir, "target_path": target_path, "target_root": target_root},
        {"cwd": workspace_dir},
    )
    for kwargs in attempts:
        try:
            resolved = service(**kwargs)
        except TypeError:
            continue
        except Exception as exc:
            raise RuntimeError("shared root resolution service failed") from exc
        return _coerce_root_pair(
            resolved,
            fallback_workspace_dir=workspace_dir,
        )
    return None


def workspace_dir_from_payload(
    data: dict[str, object],
    *,
    policy_getter: Callable[[str | None], object],
    cwd: str | None = None,
) -> str:
    hook_payload = policy_getter(cwd)
    workspace_value = data.get("workspace")
    raw_workspace = (
        workspace_value
        if isinstance(workspace_value, str) and workspace_value
        else _first_string(workspace_value, *hook_payload.workspace_keys)
        or _first_string(data, *hook_payload.workspace_keys)
        or cwd
        or os.getcwd()
    )
    return normalize_workspace_text(raw_workspace)


def project_root_from_payload(
    data: dict[str, object],
    workspace_dir: str,
    *,
    policy_getter: Callable[[str | None], object],
    cwd: str | None = None,
) -> str:
    hook_payload = policy_getter(cwd or workspace_dir)
    project_dir = _project_dir_from_payload(
        data,
        hook_payload=hook_payload,
    )
    target_path = _target_path_from_payload(
        data,
        hook_payload=hook_payload,
        workspace_dir=workspace_dir,
    )
    target_root = _target_root_from_payload(
        data,
        hook_payload=hook_payload,
        workspace_dir=workspace_dir,
    )
    project_dir_present = bool(project_dir)
    project_dir_trusted = _project_dir_is_trusted(workspace_dir, project_dir)
    resolved_roots = _resolve_with_shared_service(
        data,
        workspace_dir=workspace_dir,
        project_dir=project_dir,
        target_path=target_path,
        target_root=target_root,
        hook_payload=hook_payload,
        cwd=cwd,
    )
    if resolved_roots is not None:
        shared_project_dir_present = resolved_roots.project_dir_present or project_dir_present
        shared_project_dir_trusted = resolved_roots.project_dir_trusted or project_dir_trusted
        if shared_project_dir_trusted and not _workspace_is_within_project_dir(
            resolved_roots.workspace_dir,
            resolved_roots.project_root,
        ):
            shared_project_dir_trusted = False
        return _authoritative_project_root(
            workspace_dir=resolved_roots.workspace_dir,
            candidate_project_root=resolved_roots.project_root,
            project_dir_present=shared_project_dir_present,
            project_dir_trusted=shared_project_dir_trusted,
        )
    resolved_root = resolve_project_root(workspace_dir, project_dir=project_dir)
    candidate_project_root = str(resolved_root) if resolved_root is not None else workspace_dir
    return _authoritative_project_root(
        workspace_dir=workspace_dir,
        candidate_project_root=candidate_project_root,
        project_dir_present=project_dir_present,
        project_dir_trusted=project_dir_trusted,
    )


def resolve_payload_roots(
    data: dict[str, object],
    *,
    policy_getter: Callable[[str | None], object],
    cwd: str | None = None,
) -> PayloadRoots:
    workspace_dir = workspace_dir_from_payload(data, policy_getter=policy_getter, cwd=cwd)
    hook_payload = policy_getter(cwd or workspace_dir)
    project_dir = _project_dir_from_payload(
        data,
        hook_payload=hook_payload,
    )
    target_path = _target_path_from_payload(
        data,
        hook_payload=hook_payload,
        workspace_dir=workspace_dir,
    )
    target_root = _target_root_from_payload(
        data,
        hook_payload=hook_payload,
        workspace_dir=workspace_dir,
    )
    project_dir_present = bool(project_dir)
    project_dir_trusted = _project_dir_is_trusted(workspace_dir, project_dir)
    resolved_roots = _resolve_with_shared_service(
        data,
        workspace_dir=workspace_dir,
        project_dir=project_dir,
        target_path=target_path,
        target_root=target_root,
        hook_payload=hook_payload,
        cwd=cwd,
    )
    if resolved_roots is not None:
        shared_project_dir_present = resolved_roots.project_dir_present or project_dir_present
        shared_project_dir_trusted = resolved_roots.project_dir_trusted or project_dir_trusted
        if shared_project_dir_trusted and not _workspace_is_within_project_dir(
            resolved_roots.workspace_dir,
            resolved_roots.project_root,
        ):
            shared_project_dir_trusted = False
        authoritative_project_root = _authoritative_project_root(
            workspace_dir=resolved_roots.workspace_dir,
            candidate_project_root=resolved_roots.project_root,
            project_dir_present=shared_project_dir_present,
            project_dir_trusted=shared_project_dir_trusted,
        )
        if shared_project_dir_present or shared_project_dir_trusted:
            return PayloadRoots(
                workspace_dir=resolved_roots.workspace_dir,
                project_root=authoritative_project_root,
                project_dir_present=shared_project_dir_present,
                project_dir_trusted=shared_project_dir_trusted,
                target_path=resolved_roots.target_path or target_path,
                target_root=resolved_roots.target_root or target_root,
            )
        return PayloadRoots(
            workspace_dir=resolved_roots.workspace_dir,
            project_root=authoritative_project_root,
            project_dir_present=project_dir_present,
            project_dir_trusted=project_dir_trusted,
            target_path=resolved_roots.target_path or target_path,
            target_root=resolved_roots.target_root or target_root,
        )
    project_root = project_root_from_payload(
        data,
        workspace_dir,
        policy_getter=policy_getter,
        cwd=cwd,
    )
    return PayloadRoots(
        workspace_dir=workspace_dir,
        project_root=project_root,
        project_dir_present=project_dir_present,
        project_dir_trusted=project_dir_trusted,
        target_path=target_path,
        target_root=target_root,
    )
