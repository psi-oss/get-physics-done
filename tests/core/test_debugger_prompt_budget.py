"""Prompt budget assertions for the `gpd-debugger` agent surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_gpd_debugger_prompt_stays_lightweight_and_keeps_the_return_contract_explicit() -> None:
    path = AGENTS_DIR / "gpd-debugger.md"
    source = path.read_text(encoding="utf-8")
    metrics = measure_prompt_surface(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)

    assert metrics.raw_include_count == 0
    assert metrics.expanded_line_count < 700
    assert metrics.expanded_char_count < 40_000
    assert "one-shot handoff" in source
    assert "session_file: GPD/debug/{slug}.md" in source
    assert "status: completed | checkpoint | blocked | failed" in source
    assert "@{GPD_INSTALL_DIR}/references/shared/shared-protocols.md" not in source
    assert "@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md" not in source
    assert "@{GPD_INSTALL_DIR}/references/verification/core/verification-core.md" not in source
