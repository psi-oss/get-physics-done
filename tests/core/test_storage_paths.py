from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from gpd.core.constants import PLANNING_DIR_NAME
from gpd.core.storage_paths import (
    DurableOutputKind,
    ManagedOutputClass,
    ManagedOutputPolicy,
    ProjectStorageLayout,
    StorageClass,
    StoragePathError,
)


def _make_layout(tmp_path: Path, root_name: str = "project") -> ProjectStorageLayout:
    root = tmp_path / root_name
    root.mkdir()
    (root / PLANNING_DIR_NAME).mkdir()
    return ProjectStorageLayout(root)


def test_internal_and_scratch_roots_are_project_local(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)

    assert layout.internal_root == (layout.root / PLANNING_DIR_NAME).resolve(strict=False)
    assert layout.scratch_dir == layout.internal_root / "tmp"


@pytest.mark.parametrize(
    ("kind", "expected_name"),
    [
        (DurableOutputKind.ARTIFACTS, "artifacts"),
        (DurableOutputKind.CODE, "code"),
        (DurableOutputKind.DATA, "data"),
        (DurableOutputKind.DRAFT, "draft"),
        (DurableOutputKind.EXPORTS, "exports"),
        (DurableOutputKind.FIGURES, "figures"),
        (DurableOutputKind.MANUSCRIPT, "manuscript"),
        (DurableOutputKind.NOTEBOOKS, "notebooks"),
        (DurableOutputKind.PAPER, "paper"),
        (DurableOutputKind.REFERENCES, "references"),
        (DurableOutputKind.SIMULATIONS, "simulations"),
        (DurableOutputKind.SLIDES, "slides"),
    ],
)
def test_output_dir_maps_each_durable_kind(tmp_path: Path, kind: DurableOutputKind, expected_name: str) -> None:
    layout = _make_layout(tmp_path)

    assert layout.output_dir(kind) == layout.root / expected_name


@pytest.mark.parametrize("kind", list(DurableOutputKind))
def test_output_dirs_classify_as_user_durable(tmp_path: Path, kind: DurableOutputKind) -> None:
    layout = _make_layout(tmp_path)

    assert layout.classify(layout.output_dir(kind) / "artifact.txt") == StorageClass.USER_DURABLE


def test_phase_artifacts_dir_sanitizes_phase_name(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)

    assert layout.phase_artifacts_dir("03 derive beta(x)") == (
        layout.root / "artifacts" / "phases" / "03-derive-beta-x"
    )


def test_phase_operation_dir_nests_durable_phase_artifacts_under_operation_and_slug(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)

    assert layout.phase_operation_dir("03 derive beta(x)", "parameter sweeps", slug="mass scan v1") == (
        layout.root / "artifacts" / "phases" / "03-derive-beta-x" / "parameter-sweeps" / "mass-scan-v1"
    )


def test_classify_distinguishes_internal_scratch_user_project_and_external_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _make_layout(tmp_path)
    manuscript_stem = "curvature_flow_bounds"
    temp_root = tmp_path / "outside-temp"
    external_root = tmp_path / "outside"
    temp_root.mkdir()
    external_root.mkdir()
    controlled_temp_roots = (temp_root.resolve(strict=False),)
    monkeypatch.setattr(
        ProjectStorageLayout,
        "temp_roots",
        lambda self: controlled_temp_roots,
    )

    assert layout.classify(Path(PLANNING_DIR_NAME) / "STATE.md") == StorageClass.INTERNAL_DURABLE
    assert layout.classify(Path(PLANNING_DIR_NAME) / "tmp" / "cache" / "state.json") == StorageClass.SCRATCH
    assert layout.classify(f"paper/{manuscript_stem}.tex") == StorageClass.USER_DURABLE
    assert layout.classify(f"paper/{manuscript_stem}.tex.tmp") == StorageClass.USER_DURABLE
    assert layout.classify("notes/todo.md") == StorageClass.PROJECT_LOCAL_OTHER
    assert layout.classify(temp_root / "run.log") == StorageClass.TEMP_ROOT
    assert layout.classify(external_root / "artifact.txt") == StorageClass.EXTERNAL


def test_classify_absolute_user_output_path(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)
    output = layout.output_dir(DurableOutputKind.EXPORTS) / "report.json"

    assert layout.classify(output) == StorageClass.USER_DURABLE


def test_assess_output_path_matches_explicit_gpd_managed_policy(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)
    policy = ManagedOutputPolicy.gpd_subtree("paper")

    assessment = layout.assess_output_path(
        "GPD/paper/main.tex",
        managed_output_policies=(policy,),
    )

    assert assessment.classification == StorageClass.INTERNAL_DURABLE
    assert assessment.managed_output_class == ManagedOutputClass.GPD_MANAGED_DURABLE
    assert assessment.matched_policy == policy


@pytest.mark.parametrize(
    ("subtree", "relative_output"),
    [
        (("analysis",), "GPD/analysis/discovery-curvature-flow-bounds.md"),
        (("comparisons",), "GPD/comparisons/benchmark-COMPARISON.md"),
        (("explanations",), "GPD/explanations/ward-identity.md"),
        (("knowledge",), "GPD/knowledge/K-curvature-flow-bounds.md"),
        (("knowledge", "reviews"), "GPD/knowledge/reviews/K-curvature-flow-bounds-REVIEW.md"),
        (("literature",), "GPD/literature/curvature-flow-bounds-REVIEW.md"),
    ],
)
def test_phase3_managed_output_policies_resolve_under_expected_gpd_roots(
    tmp_path: Path,
    subtree: tuple[str, ...],
    relative_output: str,
) -> None:
    layout = _make_layout(tmp_path)
    policy = ManagedOutputPolicy.gpd_subtree(*subtree)

    assert layout.managed_output_path(policy) == layout.internal_root.joinpath(*subtree)

    assessment = layout.assess_output_path(
        relative_output,
        managed_output_policies=(policy,),
    )

    assert assessment.classification == StorageClass.INTERNAL_DURABLE
    assert assessment.managed_output_class == ManagedOutputClass.GPD_MANAGED_DURABLE
    assert assessment.matched_policy == policy
    assert layout.validate_final_output(
        relative_output,
        managed_output_policies=(policy,),
    ) == (layout.internal_root / Path(relative_output).relative_to("GPD"))


def test_temp_roots_uses_environment_overrides_and_deduplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _make_layout(tmp_path)
    tmpdir = (tmp_path / "tmpdir").resolve(strict=False)
    other = (tmp_path / "other-temp").resolve(strict=False)
    tmpdir.mkdir()
    other.mkdir()
    monkeypatch.setenv("TMPDIR", str(tmpdir))
    monkeypatch.setenv("TEMP", str(tmpdir))
    monkeypatch.setenv("TMP", str(other))

    roots = layout.temp_roots()

    assert tmpdir in roots
    assert other in roots
    assert len(roots) == len(set(roots))
    assert all(path.is_absolute() for path in roots)
    assert roots[0] == Path(tempfile.gettempdir()).resolve(strict=False)


def test_project_root_is_temporary_detects_temp_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = tmp_path / "runtime-temp"
    temp_root.mkdir()
    controlled_temp_roots = (temp_root.resolve(strict=False),)
    monkeypatch.setattr(
        ProjectStorageLayout,
        "temp_roots",
        lambda self: controlled_temp_roots,
    )

    temp_project = temp_root / "project"
    temp_project.mkdir()
    (temp_project / PLANNING_DIR_NAME).mkdir()

    temp_layout = ProjectStorageLayout(temp_project)
    normal_layout = _make_layout(tmp_path, root_name="workspace-project")

    assert temp_layout.project_root_is_temporary() is True
    assert normal_layout.project_root_is_temporary() is False


def test_validate_internal_output_accepts_internal_paths_and_rejects_non_internal(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)

    internal = layout.validate_internal_output(Path(PLANNING_DIR_NAME) / "review" / "session.json")
    absolute_internal = layout.validate_internal_output(layout.internal_root / "traces" / "trace.jsonl")

    assert internal == layout.internal_root / "review" / "session.json"
    assert absolute_internal == layout.internal_root / "traces" / "trace.jsonl"

    with pytest.raises(StoragePathError, match="Internal durable outputs must stay under"):
        layout.validate_internal_output("paper/curvature_flow_bounds.tex")

    with pytest.raises(StoragePathError, match="Internal durable outputs must stay under"):
        layout.validate_internal_output(Path(PLANNING_DIR_NAME) / "tmp" / "cache.json")


def test_validate_user_output_accepts_durable_outputs_and_rejects_other_paths(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)

    validated = layout.validate_user_output("exports/final.json", kind=DurableOutputKind.EXPORTS)

    assert validated == layout.root / "exports" / "final.json"

    with pytest.raises(StoragePathError, match="stable project directory"):
        layout.validate_user_output("GPD/review/final.json")

    with pytest.raises(StoragePathError, match="stable project directory"):
        layout.validate_user_output("notes/final.json")

    with pytest.raises(StoragePathError, match="Expected a paper output"):
        layout.validate_user_output("exports/final.json", kind=DurableOutputKind.PAPER)


def test_validate_user_output_rejects_scratch_temp_and_external_absolute_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _make_layout(tmp_path)
    temp_root = (tmp_path / "outside-temp").resolve(strict=False)
    external_root = (tmp_path / "outside").resolve(strict=False)
    temp_root.mkdir()
    external_root.mkdir()
    monkeypatch.setenv("TMPDIR", str(temp_root))
    monkeypatch.setenv("TEMP", str(temp_root))
    monkeypatch.setenv("TMP", str(temp_root / "fallback"))

    with pytest.raises(StoragePathError, match="stable project directory"):
        layout.validate_user_output(layout.scratch_dir / "final.json")

    with pytest.raises(StoragePathError, match="stable project directory"):
        layout.validate_user_output(temp_root / "final.json")

    with pytest.raises(StoragePathError, match="stable project directory"):
        layout.validate_user_output(external_root / "final.json")


def test_validate_final_output_accepts_user_durable_and_custom_stable_project_dirs(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)

    assert layout.validate_final_output("paper/curvature_flow_bounds.tex") == (
        layout.root / "paper" / "curvature_flow_bounds.tex"
    )
    assert layout.validate_final_output("release-paper/curvature_flow_bounds.tex") == (
        layout.root / "release-paper" / "curvature_flow_bounds.tex"
    )


def test_validate_final_output_rejects_internal_project_scratch_temp_and_external_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _make_layout(tmp_path)
    temp_root = (tmp_path / "outside-temp").resolve(strict=False)
    external_root = (tmp_path / "outside").resolve(strict=False)
    temp_root.mkdir()
    external_root.mkdir()
    monkeypatch.setattr(ProjectStorageLayout, "temp_roots", lambda self: (temp_root,))

    with pytest.raises(StoragePathError, match="GPD/"):
        layout.validate_final_output("GPD/paper/main.tex")

    with pytest.raises(StoragePathError, match="scratch directories"):
        layout.validate_final_output(layout.scratch_dir / "final.json")

    with pytest.raises(StoragePathError, match="scratch directories"):
        layout.validate_final_output("tmp/final.json")

    with pytest.raises(StoragePathError, match="OS temp root"):
        layout.validate_final_output(temp_root / "final.json")

    with pytest.raises(StoragePathError, match="inside the project root"):
        layout.validate_final_output(external_root / "final.json")


def test_validate_final_output_accepts_policy_owned_gpd_managed_paths(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)
    policy = ManagedOutputPolicy.gpd_subtree("paper")

    assert layout.validate_final_output(
        "GPD/paper/main.tex",
        managed_output_policies=(policy,),
    ) == (layout.internal_root / "paper" / "main.tex")
    assert layout.validate_managed_output("GPD/paper/main.tex", policy=policy) == (
        layout.internal_root / "paper" / "main.tex"
    )


def test_validate_commit_target_allows_internal_docs_but_rejects_internal_artifacts_and_scratch_paths(
    tmp_path: Path,
) -> None:
    layout = _make_layout(tmp_path)

    assert layout.validate_commit_target("GPD/STATE.md") == layout.internal_root / "STATE.md"

    hidden_results = layout.internal_root / "phases" / "01-setup" / "results" / "out.json"
    hidden_results.parent.mkdir(parents=True)
    hidden_results.write_text("{}", encoding="utf-8")
    with pytest.raises(StoragePathError, match=r"Suspicious durable-artifact path under .*GPD"):
        layout.validate_commit_target(hidden_results)

    artifact_like = layout.internal_root / "paper" / "curvature_flow_bounds.tex"
    artifact_like.parent.mkdir(parents=True)
    artifact_like.write_text("\\documentclass{article}\n", encoding="utf-8")
    with pytest.raises(StoragePathError, match="Artifact-like file stored under internal metadata directories"):
        layout.validate_commit_target(artifact_like)

    with pytest.raises(StoragePathError, match="scratch directories"):
        layout.validate_commit_target("tmp/final.csv")


def test_validate_commit_target_allows_policy_owned_gpd_managed_artifacts(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)
    target = layout.internal_root / "paper" / "main.tex"
    target.parent.mkdir(parents=True)
    target.write_text("\\documentclass{article}\n", encoding="utf-8")
    policy = ManagedOutputPolicy.gpd_subtree("paper")

    assert (
        layout.validate_commit_target(
            target,
            managed_output_policies=(policy,),
        )
        == target
    )


def test_check_user_output_reports_warning_without_raising_for_off_policy_but_project_local_paths(
    tmp_path: Path,
) -> None:
    layout = _make_layout(tmp_path)

    check = layout.check_user_output("release-paper", kind=DurableOutputKind.PAPER)

    assert check.ok is False
    assert check.classification == StorageClass.PROJECT_LOCAL_OTHER
    assert any("custom project directory" in warning for warning in check.warnings)


def test_check_user_output_warns_for_project_local_temp_dir(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)

    check = layout.check_user_output("tmp/final.json", kind=DurableOutputKind.EXPORTS)

    assert check.ok is False
    assert check.classification == StorageClass.PROJECT_LOCAL_OTHER
    assert any("tmp/temp/scratch" in warning for warning in check.warnings)


def test_check_user_output_warns_when_project_root_is_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    temp_root = tmp_path / "runtime-temp"
    temp_root.mkdir()
    controlled_temp_roots = (temp_root.resolve(strict=False),)
    monkeypatch.setattr(ProjectStorageLayout, "temp_roots", lambda self: controlled_temp_roots)

    temp_project = temp_root / "project"
    temp_project.mkdir()
    (temp_project / PLANNING_DIR_NAME).mkdir()
    layout = ProjectStorageLayout(temp_project)

    check = layout.check_user_output("paper/curvature_flow_bounds.tex", kind=DurableOutputKind.PAPER)

    assert check.classification == StorageClass.USER_DURABLE
    assert any("Project root is under a temporary directory" in warning for warning in check.warnings)


def test_audit_storage_warnings_flags_hidden_results_and_scratch_outputs(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)
    hidden_results = layout.internal_root / "phases" / "01-setup" / "results"
    hidden_results.mkdir(parents=True)
    (hidden_results / "out.json").write_text("{}", encoding="utf-8")
    artifact_like = layout.internal_root / "paper" / "curvature_flow_bounds.tex"
    artifact_like.parent.mkdir(parents=True)
    artifact_like.write_text("\\documentclass{article}\n", encoding="utf-8")
    scratch_output = layout.scratch_dir / "final.csv"
    scratch_output.parent.mkdir(parents=True, exist_ok=True)
    scratch_output.write_text("x,y\n", encoding="utf-8")
    project_scratch_output = layout.root / "tmp" / "final.csv"
    project_scratch_output.parent.mkdir(parents=True, exist_ok=True)
    project_scratch_output.write_text("x,y\n", encoding="utf-8")
    nested_project_scratch_output = layout.root / "notes" / "tmp" / "final.csv"
    nested_project_scratch_output.parent.mkdir(parents=True, exist_ok=True)
    nested_project_scratch_output.write_text("x,y\n", encoding="utf-8")
    user_durable_scratch_output = layout.root / "artifacts" / "tmp" / "final.csv"
    user_durable_scratch_output.parent.mkdir(parents=True, exist_ok=True)
    user_durable_scratch_output.write_text("x,y\n", encoding="utf-8")

    warnings = layout.audit_storage_warnings()

    assert any("GPD/phases/01-setup/results/out.json" in warning for warning in warnings)
    assert any("GPD/paper/curvature_flow_bounds.tex" in warning for warning in warnings)
    assert any("GPD/tmp/final.csv" in warning for warning in warnings)
    assert any("tmp/final.csv" in warning for warning in warnings)
    assert any("notes/tmp/final.csv" in warning for warning in warnings)
    assert any("artifacts/tmp/final.csv" in warning for warning in warnings)


def test_audit_storage_warnings_respects_explicit_managed_output_policy(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)
    paper_output = layout.internal_root / "paper" / "main.tex"
    paper_output.parent.mkdir(parents=True, exist_ok=True)
    paper_output.write_text("\\documentclass{article}\n", encoding="utf-8")
    scratch_output = layout.scratch_dir / "final.csv"
    scratch_output.parent.mkdir(parents=True, exist_ok=True)
    scratch_output.write_text("x,y\n", encoding="utf-8")
    policy = ManagedOutputPolicy.gpd_subtree("paper")

    warnings = layout.audit_storage_warnings(managed_output_policies=(policy,))

    assert not any("GPD/paper/main.tex" in warning for warning in warnings)
    assert any("GPD/tmp/final.csv" in warning for warning in warnings)


def test_resolve_anchors_relative_paths_at_project_root(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)

    assert layout.resolve("paper/curvature_flow_bounds.tex") == (
        layout.root / "paper" / "curvature_flow_bounds.tex"
    ).resolve(strict=False)
    assert layout.resolve(layout.root / "paper" / "curvature_flow_bounds.tex") == (
        layout.root / "paper" / "curvature_flow_bounds.tex"
    ).resolve(strict=False)
