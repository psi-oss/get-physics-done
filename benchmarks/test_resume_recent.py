"""Explicit benchmark for the ``resume --recent`` hot path.

The timed region covers recent-project loading, row annotation, and the forced
recent-project recovery advice path. Fixture copying, index materialization, and
workspace bootstrap stay outside the measurement loop.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from statistics import median
from time import perf_counter_ns

import pytest

import gpd.cli as cli_module
from gpd.core.context import init_resume
from gpd.core.recovery_advice import build_recovery_advice

try:
    from tests.phase16_projection_oracle_helpers import HANDOFF_BUNDLE_ROOT, copy_fixture_workspace
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[1]
    helper_path = REPO_ROOT / "tests" / "phase16_projection_oracle_helpers.py"
    helper_spec = importlib.util.spec_from_file_location("phase16_projection_oracle_helpers", helper_path)
    if helper_spec is not None and helper_spec.loader is not None:
        helper_module = importlib.util.module_from_spec(helper_spec)
        sys.modules[helper_spec.name] = helper_module
        helper_spec.loader.exec_module(helper_module)
        HANDOFF_BUNDLE_ROOT = helper_module.HANDOFF_BUNDLE_ROOT
        copy_fixture_workspace = helper_module.copy_fixture_workspace
    else:
        HANDOFF_BUNDLE_ROOT = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"

        def copy_fixture_workspace(tmp_path: Path, fixture_slug: str, variant: str) -> Path:
            source = HANDOFF_BUNDLE_ROOT / fixture_slug / variant / "workspace"
            destination = tmp_path / f"{fixture_slug}-{variant}"
            shutil.copytree(source, destination)
            return destination


try:
    from benchmarks.phase17_benchmark_helpers import measure_ns as _measure_ns
except ImportError:

    def _measure_ns(fn, *, warmup: int = 3, samples: int = 11) -> list[int]:
        for _ in range(warmup):
            fn()

        durations: list[int] = []
        for _ in range(samples):
            start_ns = perf_counter_ns()
            fn()
            durations.append(perf_counter_ns() - start_ns)
        return durations


FIXTURE_SLUG = "resume-recent-noise"
FIXTURE_VARIANT = "mutation"
RECENT_PROJECTS_FIXTURE = (
    HANDOFF_BUNDLE_ROOT / FIXTURE_SLUG / FIXTURE_VARIANT / "machine-local" / "recent-projects.json"
)


def _resume_recent_noise_rows() -> list[dict[str, object]]:
    payload = json.loads(RECENT_PROJECTS_FIXTURE.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for entry in payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        project_root = entry.get("path")
        if not isinstance(project_root, str) or not project_root.strip():
            continue
        rows.append(
            {
                "project_root": project_root,
                "available": False,
                "resumable": False,
                "resume_file": None,
                "resume_file_available": False,
                "resume_target_kind": None,
                "resume_target_recorded_at": None,
                "source_kind": "recent_project_noise",
                "source_recorded_at": None,
            }
        )
    return rows


def _write_recent_projects_index(data_root: Path, rows: list[dict[str, object]]) -> None:
    index_path = data_root / "recent-projects" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps({"rows": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prepare_resume_recent_fixture(tmp_path: Path) -> tuple[Path, Path, int]:
    workspace_root = copy_fixture_workspace(tmp_path, FIXTURE_SLUG, FIXTURE_VARIANT)
    data_root = tmp_path / "data"
    noise_rows = _resume_recent_noise_rows()
    _write_recent_projects_index(data_root, noise_rows)
    return workspace_root, data_root, len(noise_rows)


def test_resume_recent_hot_path_tracks_noise_count_and_hot_path_latency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root, data_root, noise_count = _prepare_resume_recent_fixture(tmp_path)
    monkeypatch.setenv("GPD_DATA_DIR", str(data_root))

    resume_payload = init_resume(workspace_root, data_root=data_root)

    def _hot_path() -> tuple[int, int, str]:
        rows = cli_module._load_recent_projects_rows(last=20)
        annotated_rows = cli_module._annotate_recent_project_rows(rows)
        advice = build_recovery_advice(
            workspace_root,
            recent_rows=annotated_rows,
            resume_payload=resume_payload,
            force_recent=True,
        )
        return len(annotated_rows), advice.recent_projects_count, advice.decision_source

    first_count, first_noise_count, first_decision_source = _hot_path()
    assert first_count == noise_count == 3
    assert first_noise_count == noise_count
    assert first_decision_source == "forced-recent-projects"

    samples = _measure_ns(_hot_path)
    assert len(samples) >= 3
    assert all(sample > 0 for sample in samples)
    assert int(median(samples)) > 0
    assert first_noise_count == noise_count
