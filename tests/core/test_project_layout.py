from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.constants import ProjectLayout


@pytest.mark.parametrize(
    ("attribute", "filename"),
    [
        ("config_json", "config.json"),
        ("conventions_md", "CONVENTIONS.md"),
        ("state_archive", "STATE-ARCHIVE.md"),
        ("state_json_backup", "state.json.bak"),
        ("state_intent", ".state-write-intent"),
    ],
)
def test_project_layout_file_properties(attribute: str, filename: str, tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    path = getattr(layout, attribute)

    assert path.name == filename
    assert path.parent == tmp_path / ".gpd"


@pytest.mark.parametrize(
    ("attribute", "dirname"),
    [
        ("analysis_dir", "analysis"),
        ("phases_dir", "phases"),
        ("literature_dir", "literature"),
        ("research_map_dir", "research-map"),
        ("scratch_dir", "tmp"),
    ],
)
def test_project_layout_directory_properties(attribute: str, dirname: str, tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    path = getattr(layout, attribute)

    assert path.name == dirname
    assert path.parent == tmp_path / ".gpd"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("01-PLAN.md", True),
        ("PLAN.md", True),
        ("01-SUMMARY.md", False),
        ("random.txt", False),
    ],
)
def test_project_layout_is_plan_file(filename: str, expected: bool, tmp_path: Path) -> None:
    assert ProjectLayout(tmp_path).is_plan_file(filename) is expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("01-SUMMARY.md", True),
        ("SUMMARY.md", True),
        ("01-PLAN.md", False),
        ("random.txt", False),
    ],
)
def test_project_layout_is_summary_file(filename: str, expected: bool, tmp_path: Path) -> None:
    assert ProjectLayout(tmp_path).is_summary_file(filename) is expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("01-VERIFICATION.md", True),
        ("01-PLAN.md", False),
    ],
)
def test_project_layout_is_verification_file(filename: str, expected: bool, tmp_path: Path) -> None:
    assert ProjectLayout(tmp_path).is_verification_file(filename) is expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("01-PLAN.md", "01"),
        ("PLAN.md", ""),
        ("random.txt", "random.txt"),
    ],
)
def test_project_layout_strip_plan_suffix(filename: str, expected: str, tmp_path: Path) -> None:
    assert ProjectLayout(tmp_path).strip_plan_suffix(filename) == expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("01-SUMMARY.md", "01"),
        ("SUMMARY.md", ""),
        ("random.txt", "random.txt"),
    ],
)
def test_project_layout_strip_summary_suffix(filename: str, expected: str, tmp_path: Path) -> None:
    assert ProjectLayout(tmp_path).strip_summary_suffix(filename) == expected


@pytest.mark.parametrize(
    ("method_name", "expected_name"),
    [
        ("plan_file", "01-PLAN.md"),
        ("summary_file", "01-SUMMARY.md"),
        ("verification_file", "01-VERIFICATION.md"),
    ],
)
def test_project_layout_phase_artifact_paths(
    method_name: str, expected_name: str, tmp_path: Path
) -> None:
    layout = ProjectLayout(tmp_path)
    path = getattr(layout, method_name)("01-setup", "01")

    assert path.name == expected_name
    assert path.parent == tmp_path / ".gpd" / "phases" / "01-setup"
