"""Minimal JSON manipulation utilities (jq-lite for GPD workflows).

Each function reads JSON from *stdin_text* (a string) or from files,
and returns a plain Python object suitable for printing.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from gpd.core.errors import ValidationError
from gpd.core.utils import atomic_write

_MISSING = object()  # sentinel: key not found (distinct from JSON null)


def _resolve_path(data: object, key: str) -> object:
    """Walk a dot-path like ``.section``, ``.waves``, or ``.directories[-1]``.

    Leading dots are stripped.  Bracket notation for integer indices is
    supported (e.g. ``[-1]``, ``[0]``).

    Returns *_MISSING* when the path does not exist, preserving ``None``
    for actual JSON ``null`` values.
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
            # rest looks like '-1]' or '-1][2]' (multi-bracket)
            for bracket_match in re.finditer(r"\[([^\]]*)\]", "[" + rest):
                idx_str = bracket_match.group(1).strip('"').strip("'")
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
                return _MISSING
        elif isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return _MISSING
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return _MISSING
        else:
            return _MISSING
    return current


def json_get(stdin_text: str, key: str, default: str | None = None) -> str:
    """Extract a value at *key* from JSON on stdin.  Return as string."""
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError as err:
        if default is not None:
            return default
        raise ValidationError(f"Invalid JSON input: {stdin_text[:80]!r}") from err

    result = _resolve_path(data, key)
    if result is _MISSING:
        return default if default is not None else ""

    if result is None:
        return "null"
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
    if obj is _MISSING or obj is None:
        return ""
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
    if obj is _MISSING or obj is None:
        return ""
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
    if arr is _MISSING or not isinstance(arr, list):
        return ""

    values: list[str] = []
    for item in arr:
        if isinstance(item, dict) and field in item:
            v = item[field]
            values.append(str(v) if not isinstance(v, str) else v)
    return "\n".join(values)


def json_set(file_path: str, path: str, value: str) -> dict[str, object]:
    """Set a key in a JSON file (creates file if needed)."""
    fp = Path(file_path)
    corrupted = False
    if fp.exists():
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            data = {}
            corrupted = True
    else:
        data = {}

    working = copy.deepcopy(data)

    # Try to parse value as JSON, fall back to string
    try:
        parsed_value = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        parsed_value = value

    # Parse path into (key_or_index, is_index) steps
    steps: list[tuple[str | int, bool]] = []
    for segment in path.lstrip(".").split("."):
        if not segment:
            continue
        if "[" in segment:
            base, rest = segment.split("[", 1)
            if base:
                steps.append((base, False))
            for m in re.finditer(r"\[([^\]]*)\]", "[" + rest):
                idx_str = m.group(1).strip('"').strip("'")
                try:
                    steps.append((int(idx_str), True))
                except ValueError:
                    steps.append((idx_str, False))
        else:
            steps.append((segment, False))

    if not steps:
        return {"file": str(fp), "path": path, "updated": False, "error": "empty path"}

    # Traverse / create intermediate containers
    current: object = working
    traversal_complete = True
    for index, (step_key, is_idx) in enumerate(steps[:-1]):
        next_is_idx = steps[index + 1][1]
        if is_idx and isinstance(current, list):
            try:
                current = current[step_key]  # type: ignore[index]
            except (IndexError, TypeError):
                traversal_complete = False
                break
        elif isinstance(current, dict):
            if step_key not in current or not isinstance(current[step_key], (dict, list)):
                current[step_key] = [] if next_is_idx else {}  # type: ignore[index]
            current = current[step_key]  # type: ignore[index]
        else:
            traversal_complete = False
            break

    if not traversal_complete:
        return {"file": str(fp), "path": path, "updated": False, "error": "intermediate path not traversable"}

    # Set the final value
    updated = False
    final_key, final_is_idx = steps[-1]
    if final_is_idx and isinstance(current, list):
        try:
            current[final_key] = parsed_value  # type: ignore[index]
            updated = True
        except (IndexError, TypeError):
            pass
    elif not final_is_idx and isinstance(current, dict):
        current[final_key] = parsed_value  # type: ignore[index]
        updated = True

    if updated:
        fp.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(fp, json.dumps(working, indent=2) + "\n")
    result: dict[str, object] = {"file": str(fp), "path": path, "updated": updated}
    if corrupted:
        result["warning"] = "existing file had invalid JSON, reset to empty"
    if not updated:
        result["error"] = "type mismatch at final path element"
    return result


def json_merge_files(out_path: str, file_paths: list[str]) -> dict[str, object]:
    """Merge multiple JSON files into one (shallow dict merge)."""
    merged: dict[str, object] = {}
    skipped = 0
    for fp_str in file_paths:
        fp = Path(fp_str)
        if fp.exists():
            try:
                obj = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(obj, dict):
                    merged.update(obj)
                else:
                    skipped += 1
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                skipped += 1
        else:
            skipped += 1

    out = Path(out_path)
    atomic_write(out, json.dumps(merged, indent=2) + "\n")
    result: dict[str, object] = {"file": str(out), "merged": len(file_paths) - skipped, "keys": len(merged)}
    if skipped:
        result["skipped"] = skipped
    return result


def json_sum_lengths(stdin_text: str, keys: list[str]) -> str:
    """Sum the lengths of arrays at each given path in stdin JSON."""
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError:
        return "0"

    total = 0
    for key in keys:
        obj = _resolve_path(data, key)
        if obj is not _MISSING and isinstance(obj, (list, dict, str)):
            total += len(obj)
    return str(total)
