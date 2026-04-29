from __future__ import annotations

import re

from typer.testing import CliRunner

from gpd.cli import app

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _normalize_cli_output(text: str) -> str:
    return " ".join(_ANSI_ESCAPE_RE.sub("", text).split())


_LOCAL_BRIDGE_HEADLINE_FRAGMENTS = frozenset(
    {
        "GPD local bridge",
        "local install",
        "readiness",
        "validation",
        "permissions",
        "observability",
        "recovery",
        "cost",
        "presets",
        "diagnostics",
        "shared Wolfram integration CLI",
    }
)


def test_top_level_help_headline_tracks_local_bridge_contract() -> None:
    result = CliRunner().invoke(app, ["--help"], color=False)

    assert result.exit_code == 0
    output = _normalize_cli_output(result.output)
    missing = {fragment for fragment in _LOCAL_BRIDGE_HEADLINE_FRAGMENTS if fragment not in output}
    assert missing == set()
