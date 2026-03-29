"""Shared payload root resolution for runtime hook surfaces.

This keeps the raw runtime workspace path distinct from the resolved GPD
project root so hook consumers can use one source of truth for both.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from gpd.core.observability import resolve_project_root


@dataclass(frozen=True)
class PayloadRoots:
    workspace_dir: str
    project_root: str


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _first_string(value: object, *keys: str) -> str:
    mapping = _mapping(value)
    for key in keys:
        candidate = mapping.get(key)
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
    workspace_value = data.get("workspace")
    project_dir = _first_string(workspace_value, *hook_payload.project_dir_keys) or _first_string(
        data,
        *hook_payload.project_dir_keys,
    )
    resolved_root = resolve_project_root(workspace_dir, project_dir=project_dir)
    return str(resolved_root) if resolved_root is not None else workspace_dir


def resolve_payload_roots(
    data: dict[str, object],
    *,
    policy_getter: Callable[[str | None], object],
    cwd: str | None = None,
) -> PayloadRoots:
    workspace_dir = workspace_dir_from_payload(data, policy_getter=policy_getter, cwd=cwd)
    project_root = project_root_from_payload(
        data,
        workspace_dir,
        policy_getter=policy_getter,
        cwd=cwd,
    )
    return PayloadRoots(workspace_dir=workspace_dir, project_root=project_root)
