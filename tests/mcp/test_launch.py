"""Regression tests for gpd.mcp.launch."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


class _DummyAdapter:
    def __init__(self, global_config_dir: Path) -> None:
        self.global_config_dir = global_config_dir


def test_detect_model_reads_codex_config_toml(tmp_path: Path) -> None:
    from gpd.mcp.launch import _detect_model, _detect_model_alias

    (tmp_path / "config.toml").write_text('model = "gpt-4"\n', encoding="utf-8")

    with (
        patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="codex"),
        patch("gpd.adapters.get_adapter", return_value=_DummyAdapter(tmp_path)),
    ):
        assert _detect_model() == "gpt-4"
        assert _detect_model_alias() == "opus"


def test_detect_model_reads_opencode_json(tmp_path: Path) -> None:
    from gpd.mcp.launch import _detect_model

    (tmp_path / "opencode.json").write_text(json.dumps({"model": "gpt-4o"}), encoding="utf-8")

    with (
        patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="opencode"),
        patch("gpd.adapters.get_adapter", return_value=_DummyAdapter(tmp_path)),
    ):
        assert _detect_model() == "gpt-4o"
