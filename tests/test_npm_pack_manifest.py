"""Verify that the npm dry-run package includes required runtime artifacts."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.release_workflow import main, validate_npm_pack_manifest

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


def test_verify_npm_pack_cli_rejects_malformed_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "npm-pack-dry-run.json"
    input_path.write_text("{not valid json", encoding="utf-8")

    exit_code = main(["verify-npm-pack", "--repo", str(REPO_ROOT), "--input", str(input_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "ERROR: Could not parse npm pack manifest JSON.\n"
    assert "Traceback" not in captured.err


def test_verify_npm_pack_cli_rejects_non_list_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "npm-pack-dry-run.json"
    input_path.write_text(json.dumps({"files": []}), encoding="utf-8")

    exit_code = main(["verify-npm-pack", "--repo", str(REPO_ROOT), "--input", str(input_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "ERROR: npm pack output root must be a list.\n"
    assert "Traceback" not in captured.err
