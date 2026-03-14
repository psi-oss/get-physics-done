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
        "allowed-tools:\n  - file_read\n  - shell\ncolor: cyan\n---\n"
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
        "surface: internal\nrole_family: verification\n"
        "tools: file_read, file_write, shell, search_files, find_files, web_search, web_fetch\ncolor: green\n---\n"
        "Verifier body with {GPD_INSTALL_DIR}/data.\n"
        "Config dir: {GPD_CONFIG_DIR}\n"
        "Runtime flag: {GPD_RUNTIME_FLAG}\n"
        "Use the file_read tool to check files.\n",
        encoding="utf-8",
    )
    (agents / "gpd-executor.md").write_text(
        "---\nname: gpd-executor\ndescription: Executes research plans\n"
        "surface: public\nrole_family: worker\n"
        "allowed-tools:\n  - file_read\n  - file_write\n  - file_edit\n  - shell\n"
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
        name = f"{subdir[:3]}.md"
        if subdir == "references":
            content = (
                "# References\n"
                "Path: {GPD_INSTALL_DIR}/test\n"
                "Home: ~/.claude/test\n"
                "Search with web_search and web_fetch.\n"
            )
        elif subdir == "workflows":
            content = (
                "# Workflows\n"
                'Use ask_user([{"label": "Yes"}])\n'
                'Launch task(prompt="Run it")\n'
                "Run /gpd:plan-phase 1 next.\n"
            )
        else:
            content = "# Templates\nPath: {GPD_INSTALL_DIR}/test\nHome: ~/.claude/test\n"

        (d / name).write_text(content, encoding="utf-8")

    return root
