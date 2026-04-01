"""Tests for shared hook current-task todo-resolution helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gpd.hooks.install_context import SelfOwnedInstallContext, ordered_todo_lookup_candidates
from gpd.hooks.runtime_detect import TodoCandidate
from tests.hooks.helpers import mark_complete_install as _mark_complete_install


def test_ordered_todo_lookup_candidates_uses_shared_todo_directory_constant_for_self_owned_install(
    tmp_path: Path,
) -> None:
    self_config_dir = tmp_path / "runtime"
    self_install = SelfOwnedInstallContext(config_dir=self_config_dir, runtime="codex", install_scope="local")

    with (
        patch("gpd.hooks.install_context.detect_self_owned_install", return_value=self_install),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="unknown"),
        patch("gpd.hooks.runtime_detect.get_todo_candidates", return_value=[]),
        patch("gpd.hooks.runtime_detect.should_consider_todo_candidate", return_value=True),
    ):
        candidates = ordered_todo_lookup_candidates(hook_file=__file__, cwd=str(tmp_path))

    assert [candidate.path for candidate in candidates] == [self_config_dir / "todos"]


def test_ordered_todo_lookup_candidates_uses_explicit_workspace_dir_for_local_install_lookup(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _mark_complete_install(workspace / ".codex", runtime="codex")

    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
    ):
        candidates = ordered_todo_lookup_candidates(hook_file=__file__, cwd=str(workspace))

    assert candidates[0].path == workspace / ".codex" / "todos"


def test_ordered_todo_lookup_candidates_ignores_runtime_less_explicit_target_hook_dir(
    tmp_path: Path,
) -> None:
    explicit_target = tmp_path / "custom-runtime-dir"
    hook_path = explicit_target / "hooks" / "statusline.py"
    hook_path.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(explicit_target)

    with patch("gpd.hooks.runtime_detect.get_todo_candidates", return_value=[]):
        candidates = ordered_todo_lookup_candidates(hook_file=hook_path, cwd=str(tmp_path))

    assert candidates == []


def test_ordered_todo_lookup_candidates_does_not_prepend_unrelated_self_install_over_workspace_install(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace_runtime_dir = workspace / ".codex"
    _mark_complete_install(workspace_runtime_dir, runtime="codex")
    workspace_candidate = TodoCandidate(
        workspace_runtime_dir / "todos",
        runtime="codex",
        scope="local",
    )

    unrelated_runtime_dir = tmp_path / "custom-runtime-dir"
    self_install = SelfOwnedInstallContext(
        config_dir=unrelated_runtime_dir,
        runtime="codex",
        install_scope="local",
    )

    with (
        patch("gpd.hooks.install_context.detect_self_owned_install", return_value=self_install),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="codex"),
        patch(
            "gpd.hooks.runtime_detect.detect_runtime_install_target",
            return_value=SimpleNamespace(config_dir=workspace_runtime_dir, install_scope="local"),
        ),
        patch("gpd.hooks.runtime_detect.get_todo_candidates", return_value=[workspace_candidate]),
        patch("gpd.hooks.runtime_detect.should_consider_todo_candidate", return_value=True),
    ):
        candidates = ordered_todo_lookup_candidates(hook_file=__file__, cwd=str(workspace))

    assert candidates == [workspace_candidate]


def test_ordered_todo_lookup_candidates_preserves_self_owned_candidate_when_workspace_runtime_differs(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace_runtime_dir = workspace / ".codex"
    workspace_runtime_dir.mkdir(parents=True)
    self_runtime_dir = tmp_path / ".claude"
    self_runtime_dir.mkdir(parents=True)

    self_install = SelfOwnedInstallContext(
        config_dir=self_runtime_dir,
        runtime="claude-code",
        install_scope="local",
    )
    workspace_candidate = TodoCandidate(
        workspace_runtime_dir / "todos",
        runtime="codex",
        scope="local",
    )
    self_candidate = TodoCandidate(
        self_runtime_dir / "todos",
        runtime="claude-code",
        scope="local",
    )

    with (
        patch("gpd.hooks.install_context.detect_self_owned_install", return_value=self_install),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="codex"),
        patch(
            "gpd.hooks.runtime_detect.detect_runtime_install_target",
            side_effect=lambda runtime, **_kwargs: (
                SimpleNamespace(config_dir=workspace_runtime_dir, install_scope="local")
                if runtime == "codex"
                else None
            ),
        ),
        patch("gpd.hooks.runtime_detect.get_todo_candidates", return_value=[workspace_candidate]),
        patch(
            "gpd.hooks.runtime_detect.should_consider_todo_candidate",
            side_effect=lambda candidate, **_kwargs: candidate.path == workspace_candidate.path,
        ),
    ):
        candidates = ordered_todo_lookup_candidates(
            hook_file=self_runtime_dir / "hooks" / "statusline.py",
            cwd=str(workspace),
        )

    assert candidates == [self_candidate, workspace_candidate]


def test_ordered_todo_lookup_candidates_uses_runtime_unknown_constant_not_literal(
    tmp_path: Path,
) -> None:
    runtime_unknown = "runtime-unknown"

    with (
        patch("gpd.hooks.install_context.detect_self_owned_install", return_value=None),
        patch("gpd.hooks.runtime_detect.RUNTIME_UNKNOWN", runtime_unknown),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value=runtime_unknown),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value=runtime_unknown),
        patch("gpd.hooks.runtime_detect.get_todo_candidates", return_value=[]),
        patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=AssertionError("unexpected lookup")),
    ):
        assert ordered_todo_lookup_candidates(hook_file=__file__, cwd=str(tmp_path)) == []


def test_ordered_todo_lookup_candidates_uses_non_project_cwd_for_runtime_preference_lookup(tmp_path: Path) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()

    with (
        patch("gpd.hooks.install_context.resolve_project_root", return_value=None),
        patch("gpd.hooks.install_context.detect_self_owned_install", return_value=None),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="codex") as mock_preferred,
        patch("gpd.hooks.runtime_detect.get_todo_candidates", return_value=[]),
        patch("gpd.hooks.runtime_detect.should_consider_todo_candidate", return_value=True),
    ):
        assert ordered_todo_lookup_candidates(hook_file=__file__, cwd=str(workspace)) == []

    assert mock_preferred.call_args.kwargs["cwd"] == workspace


def test_ordered_todo_lookup_candidates_prefers_nested_workspace_local_install_over_ancestor_project_root(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True)
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    _mark_complete_install(nested / ".codex", runtime="codex")

    with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
        candidates = ordered_todo_lookup_candidates(hook_file=__file__, cwd=str(nested))

    assert candidates[0].path == nested / ".codex" / "todos"


def test_ordered_todo_lookup_candidates_falls_back_to_ancestor_project_root_install_when_nested_cwd_has_none(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True)
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    _mark_complete_install(project / ".codex", runtime="codex")

    with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
        candidates = ordered_todo_lookup_candidates(hook_file=__file__, cwd=str(nested))

    assert candidates[0].path == project / ".codex" / "todos"


def test_ordered_todo_lookup_candidates_does_not_let_nested_other_runtime_hijack_active_runtime_lookup(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True)
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    _mark_complete_install(project / ".claude", runtime="claude-code")
    _mark_complete_install(nested / ".codex", runtime="codex")

    with (
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="claude-code"),
    ):
        candidates = ordered_todo_lookup_candidates(hook_file=__file__, cwd=str(nested))

    assert candidates[0].path == project / ".claude" / "todos"
