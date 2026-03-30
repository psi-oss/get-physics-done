"""Shared payload root resolution for runtime hook surfaces.

This keeps the raw runtime workspace path distinct from the resolved GPD
project root so hook consumers can use one source of truth for both.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from gpd.core.root_resolution import resolve_project_root


@dataclass(frozen=True)
class PayloadRoots:
    workspace_dir: str
    project_root: str

    @property
    def raw_workspace_dir(self) -> str:
        """Compatibility alias for the un-resolved workspace path."""
        return self.workspace_dir

    @property
    def resolved_project_root(self) -> str:
        """Compatibility alias for the resolved project root."""
        return self.project_root


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


def normalize_workspace_text(value: str | None) -> str:
    if not value:
        return str(Path.cwd().resolve(strict=False))
    path = Path(value).expanduser()
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

    if isinstance(value, PayloadRoots):
        return value
    if isinstance(value, str) and value:
        project_root = value
    elif isinstance(value, (tuple, list)) and len(value) >= 2:
        workspace_candidate, project_candidate = value[0], value[1]
        if isinstance(workspace_candidate, str) and workspace_candidate:
            workspace_dir = workspace_candidate
        if isinstance(project_candidate, str) and project_candidate:
            project_root = project_candidate
    else:
        workspace_dir = _first_string(
            value,
            "raw_workspace_dir",
            "workspace_dir",
            "workspace_root",
            "cwd",
        )
        project_root = _first_string(
            value,
            "resolved_project_root",
            "project_root",
            "project_dir",
            "root",
        )

    if not project_root:
        return None
    return PayloadRoots(
        workspace_dir=normalize_workspace_text(workspace_dir or fallback_workspace_dir),
        project_root=normalize_workspace_text(project_root),
    )


def _resolve_with_shared_service(
    data: dict[str, object],
    *,
    workspace_dir: str,
    project_dir: str,
    hook_payload: object,
    cwd: str | None = None,
) -> PayloadRoots | None:
    service = _policy_root_resolution_service(hook_payload)
    if service is None:
        return None

    attempts = (
        {"payload": data, "workspace_dir": workspace_dir, "project_dir": project_dir, "cwd": cwd},
        {"data": data, "workspace_dir": workspace_dir, "project_dir": project_dir, "cwd": cwd},
        {"workspace_dir": workspace_dir, "project_dir": project_dir, "cwd": cwd},
        {"workspace_dir": workspace_dir, "project_dir": project_dir},
        {"cwd": workspace_dir, "project_dir": project_dir},
        {"cwd": workspace_dir},
    )
    for kwargs in attempts:
        try:
            resolved = service(**kwargs)
        except TypeError:
            continue
        except Exception:
            return None
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
    resolved_roots = _resolve_with_shared_service(
        data,
        workspace_dir=workspace_dir,
        project_dir=project_dir,
        hook_payload=hook_payload,
        cwd=cwd,
    )
    if resolved_roots is not None:
        return resolved_roots.project_root
    resolved_root = resolve_project_root(workspace_dir, project_dir=project_dir)
    return str(resolved_root) if resolved_root is not None else workspace_dir


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
    resolved_roots = _resolve_with_shared_service(
        data,
        workspace_dir=workspace_dir,
        project_dir=project_dir,
        hook_payload=hook_payload,
        cwd=cwd,
    )
    if resolved_roots is not None:
        return resolved_roots
    project_root = project_root_from_payload(
        data,
        workspace_dir,
        policy_getter=policy_getter,
        cwd=cwd,
    )
    return PayloadRoots(workspace_dir=workspace_dir, project_root=project_root)
