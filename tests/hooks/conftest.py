"""Shared runtime-env isolation for hook tests."""

from __future__ import annotations

import pytest

from tests.hooks.helpers import clear_runtime_env


@pytest.fixture(autouse=True)
def _reset_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep hook tests isolated from ambient runtime env drift."""
    clear_runtime_env(monkeypatch)
