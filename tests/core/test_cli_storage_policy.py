from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.storage_paths import ProjectStorageLayout

runner = CliRunner()


def _write_basic_paper_config(project_root: Path) -> Path:
    paper_dir = project_root / "paper"
    paper_dir.mkdir()
    config_path = paper_dir / "PAPER-CONFIG.json"
    config_path.write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _build_result(output_dir: Path) -> MagicMock:
    result = MagicMock()
    result.manifest_path = output_dir / "ARTIFACT-MANIFEST.json"
    result.bibliography_audit_path = None
    result.pdf_path = output_dir / "main.pdf"
    result.success = True
    result.errors = []
    return result


def _bootstrap_health_project(project_root: Path) -> None:
    planning = project_root / ".gpd"
    planning.mkdir()
    (planning / "phases").mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")
    (planning / "config.json").write_text("{}", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (planning / "STATE.md").write_text("# State\n", encoding="utf-8")
    (planning / "PROJECT.md").write_text("# Project\n", encoding="utf-8")


def test_paper_build_default_paper_output_has_no_storage_warnings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ProjectStorageLayout, "project_root_is_temporary", lambda self: False)
    _write_basic_paper_config(tmp_path)
    paper_dir = tmp_path / "paper"

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=_build_result(paper_dir))):
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["output_dir"] == "./paper"
    assert payload["warnings"] == []


def test_paper_build_explicit_nonstandard_output_dir_warns_but_builds(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ProjectStorageLayout, "project_root_is_temporary", lambda self: False)
    _write_basic_paper_config(tmp_path)
    output_dir = tmp_path / "release-paper"
    output_dir.mkdir()

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=_build_result(output_dir))) as mock_build:
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(tmp_path), "paper-build", "--output-dir", str(output_dir)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["output_dir"] == "./release-paper"
    assert any("stable project directory" in warning for warning in payload["warnings"])
    assert mock_build.await_args.args[1] == output_dir.resolve(strict=False)


def test_paper_build_warns_when_project_root_is_temporary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ProjectStorageLayout, "project_root_is_temporary", lambda self: True)
    _write_basic_paper_config(tmp_path)
    paper_dir = tmp_path / "paper"

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=_build_result(paper_dir))):
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert any("Project root is under a temporary directory" in warning for warning in payload["warnings"])


def test_health_cli_raw_reports_storage_path_warnings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ProjectStorageLayout, "project_root_is_temporary", lambda self: False)
    _bootstrap_health_project(tmp_path)
    hidden_results = tmp_path / ".gpd" / "phases" / "01-setup" / "results"
    hidden_results.mkdir(parents=True)
    (hidden_results / "out.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "health"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    storage_check = next(check for check in payload["checks"] if check["label"] == "Storage Paths")
    assert storage_check["status"] == "warn"
    assert any(".gpd/phases/01-setup/results/out.json" in warning for warning in storage_check["warnings"])
