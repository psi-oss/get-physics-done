"""Shared utility functions for GPD.

Layer 1 code: stdlib + pathlib + json + re only.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from gpd.core.constants import DEFAULT_MAX_INCLUDE_CHARS, ENV_MAX_INCLUDE_CHARS

__all__ = [
    "MAX_INCLUDE_CHARS",
    "atomic_write",
    "compare_phase_numbers",
    "file_lock",
    "format_progress_bar",
    "generate_slug",
    "is_phase_complete",
    "phase_normalize",
    "phase_sort_key",
    "phase_top_level",
    "phase_unpad",
    "safe_parse_int",
    "safe_parse_json",
    "safe_parse_yaml",
    "safe_read_file",
    "safe_read_file_truncated",
    "walk_for_nan",
]

# ─── Phase Utilities ────────────────────────────────────────────────────────────


def phase_normalize(name: str) -> str:
    """Normalize a phase name by padding the top-level segment to 2 digits.

    Sub-levels are NOT padded: "3.1.2" -> "03.1.2", "12" -> "12".
    Non-numeric prefixes are returned as-is.
    """
    match = re.match(r"^(\d+(?:\.\d+)*)", name)
    if not match:
        return name
    parts = match.group(1).split(".")
    normalized = []
    for i, part in enumerate(parts):
        try:
            v = int(part)
            normalized.append(str(v).zfill(2) if i == 0 else str(v))
        except ValueError:
            normalized.append(part)
    return ".".join(normalized)


def phase_unpad(name: str) -> str:
    """Strip leading zeros from each segment of a phase number.

    Returns the "display" form: "08.1.1" -> "8.1.1".
    Preserves all decimal levels.
    """
    match = re.match(r"^(\d+(?:\.\d+)*)", name)
    if not match:
        return name
    parts = match.group(1).split(".")
    unpadded = []
    for part in parts:
        try:
            unpadded.append(str(int(part)))
        except ValueError:
            unpadded.append(part)
    return ".".join(unpadded)


def phase_top_level(phase: str) -> int | None:
    """Extract the top-level phase number from a phase string.

    "2.1.1" -> 2, "abc" -> None.
    """
    match = re.match(r"^(\d+)", phase)
    if not match:
        return None
    return int(match.group(1))


def compare_phase_numbers(a: str, b: str) -> int:
    """Compare two phase number strings segment-by-segment.

    Handles multi-level decimals: "2.1.2" < "2.1.10".
    Returns negative if a < b, 0 if equal, positive if a > b.
    """
    a_match = re.match(r"^(\d+(?:\.\d+)*)", a)
    b_match = re.match(r"^(\d+(?:\.\d+)*)", b)
    a_parts = (a_match.group(1) if a_match else "0").split(".")
    b_parts = (b_match.group(1) if b_match else "0").split(".")
    length = max(len(a_parts), len(b_parts))
    for i in range(length):
        a_val = int(a_parts[i]) if i < len(a_parts) else 0
        b_val = int(b_parts[i]) if i < len(b_parts) else 0
        if a_val != b_val:
            return a_val - b_val
    # Fall back to lexicographic for non-numeric suffixes
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def is_phase_complete(plan_count: int, summary_count: int) -> bool:
    """A phase is complete when it has at least one plan and every plan has a summary."""
    return plan_count > 0 and summary_count >= plan_count


def phase_sort_key(name: str) -> list[int]:
    """Sort key for phase directory names by numeric segments.

    "03-setup" -> [3], "2.1-derive" -> [2, 1].
    """
    match = re.match(r"^(\d+(?:\.\d+)*)", name)
    if not match:
        return [999999]
    return [int(s) for s in match.group(1).split(".")]


# ─── Text Utilities ─────────────────────────────────────────────────────────────


def generate_slug(text: str) -> str | None:
    """Generate a URL-safe slug from text.

    "Hello World!" -> "hello-world", "" -> None.
    """
    if not text:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return slug.strip("-") or None


def format_progress_bar(percent: float, width: int = 40) -> str:
    """Render a text progress bar.

    format_progress_bar(0.75) -> "[==============================          ] 75%"
    """
    clamped = max(0.0, min(1.0, percent))
    filled = int(clamped * width)
    bar = "=" * filled + " " * (width - filled)
    return f"[{bar}] {int(clamped * 100)}%"


# ─── Safe Parsing ───────────────────────────────────────────────────────────────


def safe_parse_int(value: object, default: int | None = 0) -> int | None:
    """Parse an integer safely, returning *default* if invalid.

    Unlike int(), never raises on bad input.  When *default* is ``None``
    the caller can distinguish "not a number" from a real zero.
    """
    if value is None:
        return default
    try:
        return int(str(value))
    except (ValueError, TypeError):
        return default


def safe_parse_json(text: str) -> dict | None:
    """Parse JSON text, returning None on failure."""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def safe_parse_yaml(text: str) -> dict | None:
    """Parse YAML frontmatter text, returning None on failure.

    Expects the content between --- delimiters (without the delimiters).
    Returns None for non-dict results or YAML parse errors.
    """
    import yaml

    try:
        result = yaml.safe_load(text)
        if isinstance(result, dict):
            return result
        return None
    except yaml.YAMLError:
        return None


# ─── NaN / Integrity Checking ──────────────────────────────────────────────────


def walk_for_nan(obj: object, prefix: str) -> list[str]:
    """Walk an object tree and collect paths to any float('nan') values.

    Returns dot-notation paths like "state.position.phase".
    """
    found: list[str] = []
    _walk_nan(obj, prefix, found)
    return found


def _walk_nan(obj: object, prefix: str, found: list[str]) -> None:
    if obj is None or not isinstance(obj, (dict, list)):
        return
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            path = f"{prefix}[{i}]"
            if isinstance(v, float) and v != v:  # NaN check
                found.append(path)
            elif isinstance(v, (dict, list)):
                _walk_nan(v, path, found)
    else:
        for k, v in obj.items():
            path = f"{prefix}.{k}"
            if isinstance(v, float) and v != v:  # NaN check
                found.append(path)
            elif isinstance(v, (dict, list)):
                _walk_nan(v, path, found)


# ─── File Helpers ───────────────────────────────────────────────────────────────

# Maximum characters to include when reading files for context
MAX_INCLUDE_CHARS = int(os.environ.get(ENV_MAX_INCLUDE_CHARS, str(DEFAULT_MAX_INCLUDE_CHARS)))


def safe_read_file(path: Path) -> str | None:
    """Read a file, returning None if it doesn't exist, is a directory, or can't be read."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return None


def safe_read_file_truncated(path: Path, max_chars: int | None = None) -> str | None:
    """Read a file, truncating if it exceeds max_chars."""
    content = safe_read_file(path)
    if content is None:
        return None
    limit = max_chars or MAX_INCLUDE_CHARS
    if len(content) <= limit:
        return content
    return content[:limit] + f"\n\n...truncated ({len(content)} chars total, showing first {limit})."


def atomic_write(filepath: Path, content: str) -> None:
    """Write a file atomically via temp file + fsync + rename.

    Ensures the file is either fully written or not modified at all.
    """
    parent = filepath.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd = None
    tmp_path = None
    try:
        fd_int, tmp_path = tempfile.mkstemp(dir=parent, prefix=".tmp_", suffix=".tmp")
        fd = os.fdopen(fd_int, "w", encoding="utf-8")
        fd.write(content)
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        fd = None
        os.rename(tmp_path, filepath)
        tmp_path = None
    finally:
        if fd is not None:
            fd.close()
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@contextmanager
def file_lock(path: Path, timeout: float = 5.0) -> Iterator[None]:
    """Context manager for advisory file locking using fcntl.flock().

    Usage:
        with file_lock(some_path):
            # exclusive access to some_path
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = None
    try:
        lock_fd = open(lock_path, "w", encoding="utf-8")  # noqa: SIM115
        # Use non-blocking first, retry with timeout
        import time

        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timeout acquiring lock on {path}") from None
                time.sleep(0.05)
        yield
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            lock_fd.close()
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
