"""Minimal JSON manipulation utilities (jq-lite for GPD workflows).

Each function reads JSON from *stdin_text* (a string) or from files,
and returns a plain Python object suitable for printing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gpd.core.utils import atomic_write


def _resolve_path(data: Any, key: str) -> Any:
    """Walk a dot-path like ``.section``, ``.waves``, or ``.directories[-1]``.

    Leading dots are stripped.  Bracket notation for integer indices is
    supported (e.g. ``[-1]``, ``[0]``).
    """
    parts: list[str] = []
    raw = key.lstrip(".")
    if not raw:
        return data

    # Split on '.' but keep bracket expressions attached
    for segment in raw.split("."):
        if not segment:
            continue
        # Handle e.g. "directories[-1]" → ("directories", "-1")
        if "[" in segment:
            base, rest = segment.split("[", 1)
            if base:
                parts.append(base)
            # rest looks like '-1]' or '\"key\"]'
            idx_str = rest.rstrip("]").strip('"').strip("'")
            parts.append(f"[{idx_str}]")
        else:
            parts.append(segment)

    current = data
    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            idx_inner = part[1:-1]
            try:
                idx = int(idx_inner)
                current = current[idx]
            except (ValueError, TypeError, IndexError, KeyError):
                return None
        elif isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return None
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def json_get(stdin_text: str, key: str, default: str | None = None) -> str:
    """Extract a value at *key* from JSON on stdin.  Return as string."""
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError:
        if default is not None:
            return default
        raise ValueError(f"Invalid JSON input: {stdin_text[:80]!r}")

    result = _resolve_path(data, key)
    if result is None:
        return default if default is not None else ""

    if isinstance(result, str):
        return result
    return json.dumps(result, separators=(",", ":"))


def json_keys(stdin_text: str, key: str) -> str:
    """Return newline-separated top-level keys of the object at *key*."""
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError:
        return ""

    obj = _resolve_path(data, key)
    if isinstance(obj, dict):
        return "\n".join(str(k) for k in obj)
    return ""


def json_list(stdin_text: str, key: str) -> str:
    """Return newline-separated items from the array/object at *key*."""
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError:
        return ""

    obj = _resolve_path(data, key)
    if isinstance(obj, list):
        return "\n".join(str(item) for item in obj)
    if isinstance(obj, dict):
        return "\n".join(str(k) for k in obj)
    return ""


def json_pluck(stdin_text: str, key: str, field: str) -> str:
    """Extract *field* from each object in the array at *key*.

    Returns newline-separated values.
    """
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError:
        return ""

    arr = _resolve_path(data, key)
    if not isinstance(arr, list):
        return ""

    values: list[str] = []
    for item in arr:
        if isinstance(item, dict) and field in item:
            v = item[field]
            values.append(str(v) if not isinstance(v, str) else v)
    return "\n".join(values)


def json_set(file_path: str, path: str, value: str) -> dict[str, Any]:
    """Set a key in a JSON file (creates file if needed)."""
    fp = Path(file_path)
    if fp.exists():
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        fp.parent.mkdir(parents=True, exist_ok=True)
        data = {}

    # Try to parse value as JSON, fall back to string
    try:
        parsed_value = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        parsed_value = value

    # Set in the data dict at the given path
    parts = path.lstrip(".").split(".")
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = parsed_value

    fp.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(fp, json.dumps(data, indent=2) + "\n")
    return {"file": str(fp), "path": path, "updated": True}


def json_merge_files(out_path: str, file_paths: list[str]) -> dict[str, Any]:
    """Merge multiple JSON files into one (shallow dict merge)."""
    merged: dict[str, Any] = {}
    for fp_str in file_paths:
        fp = Path(fp_str)
        if fp.exists():
            try:
                obj = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(obj, dict):
                    merged.update(obj)
            except json.JSONDecodeError:
                pass

    out = Path(out_path)
    atomic_write(out, json.dumps(merged, indent=2) + "\n")
    return {"file": str(out), "merged": len(file_paths), "keys": len(merged)}


def json_sum_lengths(stdin_text: str, keys: list[str]) -> str:
    """Sum the lengths of arrays at each given path in stdin JSON."""
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError:
        return "0"

    total = 0
    for key in keys:
        obj = _resolve_path(data, key)
        if isinstance(obj, (list, dict, str)):
            total += len(obj)
    return str(total)
