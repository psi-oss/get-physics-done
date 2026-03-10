"""Guardrails that keep prompt-authored CLI references aligned with the real CLI."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "src/gpd/cli.py"
PROMPT_ROOTS = (
    REPO_ROOT / "src/gpd/commands",
    REPO_ROOT / "src/gpd/agents",
    REPO_ROOT / "src/gpd/specs/agents",
    REPO_ROOT / "src/gpd/specs/skills",
    REPO_ROOT / "src/gpd/specs/workflows",
    REPO_ROOT / "src/gpd/specs/references",
    REPO_ROOT / "src/gpd/specs/templates",
)

INIT_COMMAND_RE = re.compile(r"@init_app\.command\(\"([a-z0-9-]+)\"\)")
INIT_USAGE_RE = re.compile(r"\bgpd init ([a-z0-9-]+)\b")


def _iter_prompt_sources() -> list[Path]:
    files: list[Path] = []
    for root in PROMPT_ROOTS:
        files.extend(sorted(root.rglob("*.md")))
    return files


def _declared_init_subcommands() -> set[str]:
    content = CLI_PATH.read_text(encoding="utf-8")
    return set(INIT_COMMAND_RE.findall(content))


def test_prompt_sources_use_only_real_gpd_init_subcommands() -> None:
    allowed = _declared_init_subcommands()
    invalid: list[str] = []

    for path in _iter_prompt_sources():
        content = path.read_text(encoding="utf-8")
        for match in INIT_USAGE_RE.finditer(content):
            subcommand = match.group(1)
            if subcommand not in allowed:
                invalid.append(f"{path.relative_to(REPO_ROOT)} -> {subcommand}")

    assert invalid == []
