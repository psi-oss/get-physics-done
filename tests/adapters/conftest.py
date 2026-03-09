"""Shared fixtures for adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def gpd_root(tmp_path: Path) -> Path:
    """Create a minimal GPD package data directory (mirrors real layout).

    Layout:
      commands/help.md          — simple command
      commands/sub/deep.md      — nested command (tests flattening)
      agents/gpd-verifier.md    — agent with tools list
      agents/gpd-executor.md    — agent with allowed-tools array
      hooks/statusline.py       — hook script
      hooks/check_update.py     — hook script
      specs/references/ref.md   — GPD content reference
      specs/templates/tpl.md    — GPD content template
      specs/workflows/wf.md     — GPD content workflow
    """
    root = tmp_path / "gpd_root"

    # commands/
    cmds = root / "commands"
    cmds.mkdir(parents=True)
    (cmds / "help.md").write_text(
        "---\nname: gpd:help\ndescription: Show GPD help\n"
        "allowed-tools:\n  - Read\n  - Bash\ncolor: cyan\n---\n"
        "Help body with {GPD_INSTALL_DIR}/ref and ~/.claude/agents path.\n",
        encoding="utf-8",
    )
    sub = cmds / "sub"
    sub.mkdir()
    (sub / "deep.md").write_text(
        "---\nname: gpd:sub-deep\ndescription: Deep command\n---\nDeep body.\n",
        encoding="utf-8",
    )

    # agents/
    agents = root / "agents"
    agents.mkdir()
    (agents / "gpd-verifier.md").write_text(
        "---\nname: gpd-verifier\ndescription: Verifies physics results\n"
        "tools: Read, Write, Bash, Grep, Glob, WebSearch, WebFetch\ncolor: green\n---\n"
        "Verifier body with {GPD_INSTALL_DIR}/data.\n"
        "Use the Read tool to check files.\n",
        encoding="utf-8",
    )
    (agents / "gpd-executor.md").write_text(
        "---\nname: gpd-executor\ndescription: Executes research plans\n"
        "allowed-tools:\n  - Read\n  - Write\n  - Edit\n  - Bash\n"
        "  - mcp__physics_server\ncolor: blue\n---\n"
        "Executor body.\n",
        encoding="utf-8",
    )

    # hooks/
    hooks = root / "hooks"
    hooks.mkdir()
    (hooks / "statusline.py").write_text("#!/usr/bin/env python3\nprint('status')\n", encoding="utf-8")
    (hooks / "check_update.py").write_text("#!/usr/bin/env python3\nprint('update')\n", encoding="utf-8")

    # specs/ (GPD content directories)
    for subdir in ("references", "templates", "workflows"):
        d = root / "specs" / subdir
        d.mkdir(parents=True)
        (d / f"{subdir[:3]}.md").write_text(
            f"# {subdir.title()}\nPath: {{GPD_INSTALL_DIR}}/test\nHome: ~/.claude/test\n",
            encoding="utf-8",
        )

    return root
