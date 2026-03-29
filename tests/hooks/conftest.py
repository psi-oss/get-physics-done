"""Shared runtime-env isolation for hook tests."""

from __future__ import annotations

import os

import pytest

from tests.hooks.helpers import runtime_env_prefixes, runtime_env_vars_to_clear


_RUNTIME_ENV_PREFIXES = runtime_env_prefixes()
_RUNTIME_ENV_VARS_TO_CLEAR = runtime_env_vars_to_clear()


@pytest.fixture(autouse=True)
def _reset_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep hook tests isolated from ambient runtime env drift."""
    for key in list(os.environ):
        if key.startswith(_RUNTIME_ENV_PREFIXES) or key in _RUNTIME_ENV_VARS_TO_CLEAR:
            monkeypatch.delenv(key, raising=False)
