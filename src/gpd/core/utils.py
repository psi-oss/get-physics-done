"""Shared utility functions for GPD.

Layer 1 code: stdlib + pathlib + re only.
"""

from __future__ import annotations

import os
import re
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from gpd.core.constants import DEFAULT_MAX_INCLUDE_CHARS, ENV_MAX_INCLUDE_CHARS

try:
    import fcntl
except ModuleNotFoundError:  # pragma: no cover - exercised on Windows
    fcntl = None

try:
    import msvcrt
except ModuleNotFoundError:  # pragma: no cover - exercised on POSIX
    msvcrt = None

__all__ = [
    "MAX_INCLUDE_CHARS",
    "atomic_write",
    "compare_phase_numbers",
    "file_lock",
    "generate_slug",
    "is_phase_complete",
    "phase_normalize",
    "phase_sort_key",
    "phase_unpad",
    "safe_parse_int",
    "safe_read_file",
    "safe_read_file_truncated",
]

# ─── Phase Utilities ────────────────────────────────────────────────────────────


def phase_normalize(name: str) -> str:
    """Normalize a phase name by padding the top-level segment to 2 digits.

    Sub-levels are NOT padded: "3.1.2" -> "03.1.2", "12" -> "12".
    Non-numeric prefixes are returned as-is.
    """
    if name is None:
        return ""
    match = re.match(r"^(\d+(?:\.\d+)*)(.*)", name)
    if not match:
        return name
    numeric, suffix = match.group(1), match.group(2)
    parts = numeric.split(".")
    normalized = []
    for i, part in enumerate(parts):
        try:
            v = int(part)
            normalized.append(str(v).zfill(2) if i == 0 else str(v))
        except ValueError:
            normalized.append(part)
    return ".".join(normalized) + suffix


def phase_unpad(name: str) -> str:
    """Strip leading zeros from each segment of a phase number.

    Returns the "display" form: "08.1.1" -> "8.1.1".
    Preserves all decimal levels.
    """
    if name is None:
        return ""
    match = re.match(r"^(\d+(?:\.\d+)*)(.*)", name)
    if not match:
        return name
    numeric, suffix = match.group(1), match.group(2)
    parts = numeric.split(".")
    unpadded = []
    for part in parts:
        try:
            unpadded.append(str(int(part)))
        except ValueError:
            unpadded.append(part)
    return ".".join(unpadded) + suffix


def compare_phase_numbers(a: str, b: str) -> int:
    """Compare two phase number strings segment-by-segment.

    Handles multi-level decimals: "2.1.2" < "2.1.10".
    Returns negative if a < b, 0 if equal, positive if a > b.
    """
    if a is None:
        a = ""
    if b is None:
        b = ""
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
    # Fall back to lexicographic comparison of non-numeric suffixes only
    a_suffix = a[a_match.end():] if a_match else a
    b_suffix = b[b_match.end():] if b_match else b
    if a_suffix < b_suffix:
        return -1
    if a_suffix > b_suffix:
        return 1
    return 0


def is_phase_complete(plan_count: int, summary_count: int) -> bool:
    """A phase is complete when it has at least one plan and every plan has a summary."""
    return plan_count > 0 and summary_count >= plan_count


def phase_sort_key(name: str) -> list[int]:
    """Sort key for phase directory names by numeric segments.

    "03-setup" -> [3], "2.1-derive" -> [2, 1].
    """
    if name is None:
        return [999999]
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


def safe_parse_int(value: object, default: int | None = 0) -> int | None:
    """Parse an integer safely, returning *default* if invalid.

    Unlike int(), never raises on bad input.  When *default* is ``None``
    the caller can distinguish "not a number" from a real zero.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value))
    except (ValueError, TypeError):
        return default



# ─── File Helpers ───────────────────────────────────────────────────────────────


def _max_include_chars_from_env() -> int:
    """Return a valid include limit from the environment or the default."""
    parsed = safe_parse_int(os.environ.get(ENV_MAX_INCLUDE_CHARS), DEFAULT_MAX_INCLUDE_CHARS)
    if parsed is None or parsed <= 0:
        return DEFAULT_MAX_INCLUDE_CHARS
    return parsed


# Maximum characters to include when reading files for context
MAX_INCLUDE_CHARS = _max_include_chars_from_env()


def safe_read_file(path: Path) -> str | None:
    """Read a file, returning None if it doesn't exist, is a directory, or can't be read."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, PermissionError, UnicodeDecodeError, OSError):
        return None


def safe_read_file_truncated(path: Path, max_chars: int | None = None) -> str | None:
    """Read a file, truncating if it exceeds max_chars."""
    content = safe_read_file(path)
    if content is None:
        return None
    limit = max_chars if max_chars is not None else MAX_INCLUDE_CHARS
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
        os.replace(tmp_path, filepath)
        tmp_path = None
    finally:
        if fd is not None:
            fd.close()
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _ensure_windows_lock_region(lock_fd: object) -> None:
    """Guarantee a 1-byte region exists for msvcrt byte-range locking."""
    if msvcrt is None:
        return
    lock_fd.seek(0, os.SEEK_END)
    if lock_fd.tell() == 0:
        lock_fd.write(b"\0")
        lock_fd.flush()
    lock_fd.seek(0)


def _acquire_file_lock_nonblocking(lock_fd: object) -> None:
    """Acquire an exclusive non-blocking lock using the active platform backend."""
    if fcntl is not None:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    if msvcrt is not None:
        _ensure_windows_lock_region(lock_fd)
        msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        return
    raise RuntimeError("No supported file-locking backend is available on this platform")


def _release_file_lock(lock_fd: object) -> None:
    """Release a lock using the active platform backend."""
    if fcntl is not None:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        return
    if msvcrt is not None:
        _ensure_windows_lock_region(lock_fd)
        msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
        return
    raise RuntimeError("No supported file-locking backend is available on this platform")


@contextmanager
def file_lock(path: Path, timeout: float = 5.0) -> Iterator[None]:
    """Context manager for cross-platform exclusive file locking.

    Usage:
        with file_lock(some_path):
            # exclusive access to some_path
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = None
    try:
        lock_fd = open(lock_path, "a+b")  # noqa: SIM115
        deadline = time.monotonic() + timeout
        while True:
            try:
                _acquire_file_lock_nonblocking(lock_fd)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timeout acquiring lock on {path}") from None
                time.sleep(0.05)
        yield
    finally:
        if lock_fd is not None:
            try:
                _release_file_lock(lock_fd)
            except OSError:
                pass
            lock_fd.close()
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
