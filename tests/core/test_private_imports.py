from __future__ import annotations

import ast
from pathlib import Path

CLI_IMPORT_PATH = Path("src/gpd/cli.py")
CONVENTIONS_SERVER_PATH = Path("src/gpd/mcp/servers/conventions_server.py")
TARGETS = (CLI_IMPORT_PATH, CONVENTIONS_SERVER_PATH)
TARGET_MODULE_PREFIXES = ("gpd.core.state", "gpd.core.context")


def _find_private_gpd_core_imports(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in TARGET_MODULE_PREFIXES
            ):
                for alias in node.names:
                    if alias.name.startswith("_"):
                        findings.append(f"{path}: from {module} import {alias.name}")
    return findings


def test_cli_and_conventions_server_avoid_private_core_imports() -> None:
    findings: list[str] = []
    for path in TARGETS:
        findings.extend(_find_private_gpd_core_imports(path))
    if findings:
        raise AssertionError(
            "Private gpd.core imports are disallowed in CLI/MCP servers:\n" + "\n".join(findings)
        )
