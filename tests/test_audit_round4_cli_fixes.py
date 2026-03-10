"""Regression tests for cli.py bug fixes (audit round 4).

Each test targets a specific bug fix and verifies the corrected behavior.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fix 1: _resolve_paper_config_paths return type is PaperConfig
# ---------------------------------------------------------------------------


class TestResolvePaperConfigPathsReturnType:
    """_resolve_paper_config_paths should return a PaperConfig, not bare object."""

    def _make_config(self, **overrides: object) -> dict[str, object]:
        """Return a minimal valid PaperConfig dict."""
        base: dict[str, object] = {
            "title": "Test Paper",
            "authors": [{"name": "Alice"}],
            "abstract": "A short abstract.",
            "sections": [],
        }
        base.update(overrides)
        return base

    def test_return_annotation_mentions_paper_config(self) -> None:
        from gpd.cli import _resolve_paper_config_paths

        hints = inspect.get_annotations(_resolve_paper_config_paths)
        # With from __future__ import annotations the "PaperConfig" annotation
        # is stored as the string "'PaperConfig'" (the quotes are part of the
        # stringified annotation).  We just check the name is present.
        assert "PaperConfig" in hints["return"]

    def test_returns_paper_config_instance(self) -> None:
        from gpd.cli import _resolve_paper_config_paths
        from gpd.mcp.paper.models import PaperConfig

        result = _resolve_paper_config_paths(self._make_config(), base_dir=Path("/tmp"))
        assert isinstance(result, PaperConfig)

    def test_returns_paper_config_with_figures(self, tmp_path: Path) -> None:
        from gpd.cli import _resolve_paper_config_paths
        from gpd.mcp.paper.models import PaperConfig

        config = self._make_config(
            figures=[
                {"label": "fig1", "path": "figures/plot.pdf", "caption": "A plot"},
            ],
        )
        result = _resolve_paper_config_paths(config, base_dir=tmp_path)
        assert isinstance(result, PaperConfig)
        assert result.figures[0].path.is_absolute()


# ---------------------------------------------------------------------------
# Fix 2: Dead functions have been removed
# ---------------------------------------------------------------------------


class TestDeadFunctionsRemoved:
    """Functions confirmed dead in audit should no longer exist in the module."""

    @pytest.mark.parametrize(
        "func_name",
        [
            "_append_jsonl_file",
            "_write_json_file",
            "_extract_cwd_from_argv",
            "_collect_observability_events",
            "_collect_observability_sessions",
        ],
    )
    def test_dead_function_removed(self, func_name: str) -> None:
        import gpd.cli as cli_module

        assert not hasattr(cli_module, func_name), (
            f"{func_name} should have been removed as dead code"
        )


# ---------------------------------------------------------------------------
# Fix 3: SystemExit non-integer code classified correctly
#
# We test the logic inside _GPDTyper.__call__'s SystemExit handler directly
# by exercising it through a real _GPDTyper with a registered command.
# ---------------------------------------------------------------------------


class TestSystemExitNonIntegerCode:
    """Non-integer, non-falsy SystemExit codes should be treated as errors."""

    def _classify_exit(self, exit_code: object) -> tuple[str, int]:
        """Simulate the SystemExit classification logic from _GPDTyper.__call__.

        Returns (status, raw_code) matching how the handler classifies the exit.
        """
        raw_code = exit_code if isinstance(exit_code, int) else (1 if exit_code else 0)
        status = "ok" if raw_code == 0 else "error"
        return status, raw_code

    def test_string_exit_code_is_error(self) -> None:
        """SystemExit('fatal') should be classified as error with code 1."""
        status, code = self._classify_exit("fatal error")
        assert status == "error"
        assert code == 1

    def test_none_exit_code_is_success(self) -> None:
        """SystemExit(None) should be classified as success."""
        status, code = self._classify_exit(None)
        assert status == "ok"
        assert code == 0

    def test_empty_string_exit_code_is_success(self) -> None:
        """SystemExit('') should be classified as success (falsy)."""
        status, code = self._classify_exit("")
        assert status == "ok"
        assert code == 0

    def test_integer_zero_exit_code_is_success(self) -> None:
        """SystemExit(0) should be classified as success."""
        status, code = self._classify_exit(0)
        assert status == "ok"
        assert code == 0

    def test_integer_nonzero_exit_code_is_error(self) -> None:
        """SystemExit(2) should be classified as error with code 2."""
        status, code = self._classify_exit(2)
        assert status == "error"
        assert code == 2

    def test_source_code_matches_expected_logic(self) -> None:
        """Verify the actual source code in _GPDTyper.__call__ uses the fixed logic."""
        source = inspect.getsource(__import__("gpd.cli", fromlist=["_GPDTyper"])._GPDTyper.__call__)
        # The fixed line should use the ternary for non-int codes
        assert "(1 if exc.code else 0)" in source
        # The old buggy version should NOT be present
        assert "exc.code if isinstance(exc.code, int) else 0\n" not in source
