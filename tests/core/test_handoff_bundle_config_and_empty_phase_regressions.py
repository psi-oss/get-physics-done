from __future__ import annotations

import shutil
from pathlib import Path

from gpd.core.config import load_config as load_structured_config
from gpd.core.context import init_progress
from gpd.core.context import load_config as load_context_config
from gpd.core.phases import progress_render

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


def _copy_fixture_workspace(tmp_path: Path, fixture_relpath: str) -> Path:
    source = FIXTURES_DIR / fixture_relpath / "workspace"
    destination = tmp_path / fixture_relpath.replace("/", "-")
    shutil.copytree(source, destination)
    return destination


def test_config_readback_workspace_round_trips_through_config_loaders_and_init_progress(
    tmp_path: Path,
) -> None:
    workspace = _copy_fixture_workspace(tmp_path, "config-readback/positive")
    config_path = workspace / "GPD" / "config.json"
    config_text = config_path.read_text(encoding="utf-8")

    structured_config = load_structured_config(workspace)
    context_config = load_context_config(workspace)
    ctx = init_progress(workspace, includes={"config"}, include_project_reentry=False)

    assert structured_config.model_profile.value == "review"
    assert structured_config.autonomy.value == "balanced"
    assert structured_config.review_cadence.value == "adaptive"
    assert structured_config.research_mode.value == "balanced"
    assert structured_config.commit_docs is False
    assert structured_config.branching_strategy.value == "none"
    assert structured_config.parallelization is True

    assert context_config["model_profile"] == "review"
    assert context_config["autonomy"] == "balanced"
    assert context_config["review_cadence"] == "adaptive"
    assert context_config["research_mode"] == "balanced"
    assert context_config["commit_docs"] is False
    assert context_config["branching_strategy"] == "none"
    assert context_config["parallelization"] is True

    assert ctx["project_root_source"] == "workspace"
    assert ctx["project_root"] == workspace.resolve(strict=False).as_posix()
    assert ctx["config_content"] == config_text


def test_empty_phase_workspace_keeps_progress_and_init_progress_at_zero(
    tmp_path: Path,
) -> None:
    workspace = _copy_fixture_workspace(tmp_path, "empty-phase/positive")

    ctx = init_progress(workspace, includes={"state"}, include_project_reentry=False)
    progress = progress_render(workspace, "json")

    assert ctx["project_root_source"] == "workspace"
    assert ctx["project_root"] == workspace.resolve(strict=False).as_posix()
    assert ctx["state_exists"] is True
    assert ctx["roadmap_exists"] is True
    assert ctx["project_exists"] is True
    assert ctx["phase_count"] == 0
    assert ctx["phases"] == []
    assert ctx["current_phase"] is None
    assert ctx["next_phase"] is None
    assert ctx["has_work_in_progress"] is False
    assert ctx["state_content"] is not None
    assert "**Current Phase:** 01" in ctx["state_content"]

    assert progress.total_plans == 0
    assert progress.total_summaries == 0
    assert progress.percent == 0
