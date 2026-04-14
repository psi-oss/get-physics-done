"""Verify that the npm dry-run package includes required runtime artifacts."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from scripts.release_workflow import validate_npm_pack_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_npm_pack_dry_run_json() -> list[dict[str, object]]:
    cache_dir = REPO_ROOT / "tmp" / "npm-pack-test-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["npm_config_cache"] = str(cache_dir)
    env["npm_config_audit"] = "false"
    env["npm_config_fund"] = "false"
    env["npm_config_update_notifier"] = "false"

    result = subprocess.run(
        ["npm", "pack", "--dry-run", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError("npm pack --dry-run --json did not emit valid JSON") from exc


def test_npm_pack_dry_run_includes_catalog_and_contract() -> None:
    entries = _run_npm_pack_dry_run_json()
    validate_npm_pack_manifest(entries)
