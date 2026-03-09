"""Regression tests for runtime platform detection in gpd.core.context."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

import gpd.core.context as context_module


def _clear_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove runtime detection env vars so each test controls the signal."""
    for key in list(os.environ):
        if key.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE")):
            monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize(
    ("env_var", "expected"),
    [
        ("CLAUDE_CODE_SESSION", "claude"),
        ("CODEX_SESSION", "codex"),
        ("GEMINI_CLI", "gemini"),
        ("OPENCODE_SESSION", "opencode"),
    ],
)
def test_init_context_uses_active_runtime_signal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env_var: str, expected: str
) -> None:
    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        runtime_env.setenv(env_var, "active")

        module = importlib.reload(context_module)
        ctx = module.init_new_project(tmp_path)
        assert ctx["platform"] == expected

    importlib.reload(context_module)
