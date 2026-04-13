#!/usr/bin/env python3
"""Render the runtime catalog table used by the onboarding docs."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "src" / "gpd" / "adapters" / "runtime_catalog.json"


def load_runtime_catalog() -> list[dict[str, object]]:
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _runtime_aliases(entry: dict[str, object]) -> list[str]:
    seen: list[str] = []
    for alias in entry.get("selection_aliases", []) or []:
        if alias not in seen:
            seen.append(alias)
    return seen


def _selector_flags(entry: dict[str, object]) -> list[str]:
    seen: list[str] = []
    for flag in entry.get("selection_flags", []) or []:
        if flag not in seen:
            seen.append(flag)
    return seen


def render_table() -> str:
    catalog = sorted(load_runtime_catalog(), key=lambda entry: entry.get("priority", 0))
    rows = []
    for entry in catalog:
        display_name = entry.get("display_name", entry.get("runtime_name", ""))
        install_flag = entry.get("install_flag", "<missing>")
        launch_command = entry.get("launch_command", "<missing>")
        command_prefix = entry.get("command_prefix") or "<none>"
        aliases = _runtime_aliases(entry)
        selector_flags = _selector_flags(entry)
        alias_cell = ", ".join(f"`{alias}`" for alias in aliases) if aliases else "`<none>`"
        selector_flag_cell = ", ".join(f"`{flag}`" for flag in selector_flags) if selector_flags else "`<none>`"
        rows.append(
            f"| {display_name} | `{install_flag}` | `{launch_command}` | `{command_prefix}` | {alias_cell} | {selector_flag_cell} |"
        )
    header = "| Runtime | `npx` flag | Launch command | Command prefix | Runtime aliases | Extra selector flags |"
    separator = "|---------|------------|----------------|----------------|-----------------|----------------------|"
    return "\n".join([header, separator, *rows])


if __name__ == "__main__":
    print(render_table())
