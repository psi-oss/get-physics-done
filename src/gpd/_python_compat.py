"""Python-runtime compatibility helpers for import-time surfaces."""

from __future__ import annotations

import sys

MIN_SUPPORTED_PYTHON = (3, 11)
MIN_SUPPORTED_PYTHON_LABEL = ".".join(str(part) for part in MIN_SUPPORTED_PYTHON)


def unsupported_python_message(*, version_info: tuple[int, ...] | None = None) -> str:
    """Return the canonical error for unsupported Python interpreters."""

    version = version_info if version_info is not None else sys.version_info
    major = int(version[0]) if len(version) > 0 else 0
    minor = int(version[1]) if len(version) > 1 else 0
    return (
        "get-physics-done requires Python "
        f"{MIN_SUPPORTED_PYTHON_LABEL}+; current interpreter is Python {major}.{minor}. "
        f"Use `uv run ...` or a Python {MIN_SUPPORTED_PYTHON_LABEL}+ environment."
    )


def require_supported_python(*, version_info: tuple[int, ...] | None = None) -> None:
    """Raise a stable error when the active interpreter is too old."""

    version = version_info if version_info is not None else sys.version_info
    if tuple(version[:2]) < MIN_SUPPORTED_PYTHON:
        raise RuntimeError(unsupported_python_message(version_info=tuple(version)))
