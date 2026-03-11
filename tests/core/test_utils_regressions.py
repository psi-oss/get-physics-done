from __future__ import annotations

import importlib
import os

import gpd.core.utils as utils
from gpd.core.constants import DEFAULT_MAX_INCLUDE_CHARS, ENV_MAX_INCLUDE_CHARS


def test_max_include_chars_invalid_env_falls_back_to_default(monkeypatch) -> None:
    original = os.environ.get(ENV_MAX_INCLUDE_CHARS)
    monkeypatch.setenv(ENV_MAX_INCLUDE_CHARS, "not-an-int")

    try:
        importlib.reload(utils)
        assert utils.MAX_INCLUDE_CHARS == DEFAULT_MAX_INCLUDE_CHARS
    finally:
        if original is None:
            monkeypatch.delenv(ENV_MAX_INCLUDE_CHARS, raising=False)
        else:
            monkeypatch.setenv(ENV_MAX_INCLUDE_CHARS, original)
        importlib.reload(utils)
