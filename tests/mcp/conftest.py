"""Shared fixtures for MCP server tests."""

from __future__ import annotations

import os

import pytest

FAKE_PROJECT_DIR = r"C:\fake\project" if os.name == "nt" else "/tmp/fake"
"""Module-level constant for use in ``@pytest.mark.parametrize`` decorators."""


@pytest.fixture
def fake_project_dir() -> str:
    """Platform-appropriate absolute path for test project directories.

    On Windows, POSIX-style ``/fake/project`` is not detected as absolute by
    ``Path.is_absolute()``.  This fixture returns a path that passes the
    ``resolve_absolute_project_dir`` gate on every platform.
    """
    if os.name == "nt":
        return r"C:\fake\project"
    return "/fake/project"
