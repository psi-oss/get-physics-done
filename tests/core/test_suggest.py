"""Tests for gpd.core.suggest — next-action intelligence."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gpd.adapters import get_adapter, list_runtimes
from gpd.adapters.runtime_catalog import get_runtime_descriptor
from gpd.core import suggest as suggest_module
from gpd.core.constants import ENV_GPD_ACTIVE_RUNTIME
from gpd.core.proof_review import resolve_manuscript_proof_review_status
from gpd.core.reproducibility import compute_sha256
from gpd.core.runtime_command_surfaces import format_active_runtime_command
from gpd.core.suggest import (
    Recommendation,
    SuggestContext,
    SuggestResult,
    suggest_next,
)
from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN
from tests.manuscript_test_support import (
    CANONICAL_MANUSCRIPT_STEM,
    manuscript_path,
    manuscript_pdf_path,
    manuscript_relpath,
    write_proof_review_package,
)
from tests.runtime_install_helpers import seed_complete_runtime_install

_RUNTIME_NAMES = tuple(list_runtimes())
_SUPPORTED_RUNTIME_DESCRIPTORS = tuple(get_runtime_descriptor(runtime) for runtime in _RUNTIME_NAMES)
_RUNTIME_ENV_VARS_TO_CLEAR = {
    ENV_GPD_ACTIVE_RUNTIME,
    *(
        env_var
        for descriptor in _SUPPORTED_RUNTIME_DESCRIPTORS
        for env_var in (
            *descriptor.activation_env_vars,
            descriptor.global_config.env_var,
            descriptor.global_config.env_dir_var,
            descriptor.global_config.env_file_var,
            "XDG_CONFIG_HOME" if descriptor.global_config.strategy == "xdg_app" else None,
        )
        if env_var
    ),
}


def _runtime_pair_with_distinct_commands(action: str) -> tuple[str, str]:
    for runtime in _RUNTIME_NAMES:
        runtime_command = get_adapter(runtime).format_command(action)
        for other_runtime in _RUNTIME_NAMES:
            if other_runtime == runtime:
                continue
            if get_adapter(other_runtime).format_command(action) != runtime_command:
                return runtime, other_runtime
    raise AssertionError(f"Expected two supported runtimes with distinct command formatting for {action!r}")


@pytest.fixture(autouse=True)
def _isolate_runtime_detection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep suggest tests independent from the host machine's runtime installs."""
    for key in _RUNTIME_ENV_VARS_TO_CLEAR:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("gpd.hooks.runtime_detect.Path.home", lambda: tmp_path / "home")


# ─── Helpers ───────────────────────────────────────────────────────────────────


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project structure and return project root."""
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    (planning / "PROJECT.md").write_text("# My Project\n", encoding="utf-8")
    return tmp_path


def _create_roadmap(tmp_path: Path, content: str = "# Roadmap\n## Phase 1\n") -> None:
    """Write ROADMAP.md."""
    (tmp_path / "GPD" / "ROADMAP.md").write_text(content, encoding="utf-8")


def _create_state(tmp_path: Path, state: dict[str, object]) -> None:
    """Write state.json."""
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _create_phase(
    tmp_path: Path,
    name: str,
    *,
    plans: int = 0,
    summaries: int = 0,
    research: bool = False,
    verification: bool = False,
) -> Path:
    """Create a phase directory with specified artifacts."""
    phase_dir = tmp_path / "GPD" / "phases" / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, plans + 1):
        (phase_dir / f"{i:02d}-PLAN.md").write_text(f"Plan {i}\n", encoding="utf-8")
    for i in range(1, summaries + 1):
        (phase_dir / f"{i:02d}-SUMMARY.md").write_text(f"Summary {i}\n", encoding="utf-8")
    if research:
        (phase_dir / "RESEARCH.md").write_text("Research\n", encoding="utf-8")
    if verification:
        (phase_dir / "01-VERIFICATION.md").write_text("Verification\n", encoding="utf-8")
    return phase_dir


def _write_active_manuscript_entrypoint(
    project_root: Path,
    *,
    root_name: str = "paper",
    suffix: str = ".tex",
    body: str = "\\documentclass{article}\n",
) -> Path:
    manuscript_root = project_root / root_name
    manuscript_root.mkdir(parents=True, exist_ok=True)
    entrypoint = manuscript_root / f"{CANONICAL_MANUSCRIPT_STEM}{suffix}"
    entrypoint.write_text(body, encoding="utf-8")
    (manuscript_root / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "jhep",
                "created_at": "2026-03-10T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "manuscript",
                        "category": "tex",
                        "path": entrypoint.name,
                        "sha256": compute_sha256(entrypoint),
                        "produced_by": "tests.core.test_suggest",
                        "sources": [],
                        "metadata": {"role": "manuscript"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return entrypoint


def _write_reproducibility_manifest(project_root: Path, *, manuscript_pdf: Path) -> None:
    (project_root / "paper" / "reproducibility-manifest.json").write_text(
        json.dumps(
            {
                "paper_title": "Curvature Flow Bounds",
                "date": "2026-03-10",
                "contact": "research@example.com",
                "environment": {
                    "python_version": "3.12.1",
                    "package_manager": "uv",
                    "required_packages": [{"package": "numpy", "version": "1.26.4"}],
                    "lock_file": "pyproject.toml",
                },
                "execution_steps": [
                    {
                        "name": "run-analysis",
                        "command": "python scripts/run_analysis.py",
                        "outputs": ["results/out.json"],
                        "stochastic": False,
                    }
                ],
                "expected_results": [
                    {
                        "quantity": "x",
                        "expected_value": "1",
                        "tolerance": "0.1",
                        "script": "scripts/run_analysis.py",
                    }
                ],
                "output_files": [
                    {
                        "path": manuscript_pdf.name,
                        "checksum_sha256": compute_sha256(manuscript_pdf),
                    }
                ],
                "resource_requirements": [
                    {
                        "step": "run-analysis",
                        "cpu_cores": 1,
                        "memory_gb": 1.0,
                    }
                ],
                "minimum_viable": "1 core",
                "recommended": "2 cores",
                "random_seeds": [],
                "seeding_strategy": "",
                "known_platform_differences": [],
                "verification_steps": ["pipeline rerun", "numerical comparison", "artifact inspection"],
                "manifest_created": "2026-03-10T00:00:00+00:00",
                "last_verified": "2026-03-10T00:00:00+00:00",
                "last_verified_platform": "macOS-15-arm64",
            }
        ),
        encoding="utf-8",
    )


def _create_roadmap_with_phases(tmp_path: Path, phases: list[tuple[str, str]]) -> None:
    lines = ["# Roadmap", ""]
    for number, name in phases:
        lines.extend(
            [
                f"### Phase {number}: {name}",
                "**Goal:** planned",
                "",
            ]
        )
    _create_roadmap(tmp_path, "\n".join(lines).strip() + "\n")


def _create_todos(tmp_path: Path, count: int) -> None:
    """Create pending todo files."""
    pending = tmp_path / "GPD" / "todos" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (pending / f"todo-{i}.md").write_text(f"Todo {i}\n", encoding="utf-8")


def _write_submission_review_package(
    tmp_path: Path,
    *,
    theorem_bearing: bool,
    review_report: bool = False,
) -> Path:
    root = _setup_project(tmp_path)
    _create_state(
        root,
        {
            "convention_lock": {
                "metric_signature": "(-,+,+,+)",
                "natural_units": "c=1",
                "coordinate_system": "global chart",
            }
        },
    )
    package = write_proof_review_package(
        root,
        theorem_bearing=theorem_bearing,
        review_report=review_report,
    )
    resolve_manuscript_proof_review_status(root, package.manuscript_path, persist_manifest=True)
    if review_report:
        (root / "GPD" / "REFEREE-REPORT.md").write_text("Accepted after revision.\n", encoding="utf-8")
    _write_reproducibility_manifest(root, manuscript_pdf=package.manuscript_pdf_path)
    return root


# ─── No Project ────────────────────────────────────────────────────────────────


def test_no_project_suggests_new_project(tmp_path: Path) -> None:
    """Without PROJECT.md, only recommendation is new-project."""
    result = suggest_next(tmp_path)
    assert result.suggestion_count == 1
    assert result.top_action is not None
    assert result.top_action.action == "new-project"
    assert result.top_action.priority == 1


def test_no_project_uses_workspace_runtime_install_for_command_formatting(tmp_path: Path) -> None:
    """Installed runtime command formatting should follow the analyzed workspace, not the process cwd."""
    workspace_runtime, elsewhere_runtime = _runtime_pair_with_distinct_commands("new-project")
    workspace_adapter = get_adapter(workspace_runtime)
    elsewhere_adapter = get_adapter(elsewhere_runtime)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    seed_complete_runtime_install(workspace / workspace_adapter.local_config_dir_name, runtime=workspace_runtime)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    seed_complete_runtime_install(elsewhere / elsewhere_adapter.local_config_dir_name, runtime=elsewhere_runtime)

    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
    ):
        result = suggest_next(workspace)

    assert result.top_action is not None
    assert result.top_action.command == workspace_adapter.format_command("new-project")


def test_no_project_with_runtime_dir_but_no_install_uses_plain_gpd_command(tmp_path: Path) -> None:
    """Workflow bootstrap suggestions should fall back to the local init CLI when no runtime is installed."""
    workspace_runtime, elsewhere_runtime = _runtime_pair_with_distinct_commands("new-project")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / get_adapter(workspace_runtime).local_config_dir_name).mkdir()

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    seed_complete_runtime_install(
        elsewhere / get_adapter(elsewhere_runtime).local_config_dir_name,
        runtime=elsewhere_runtime,
    )

    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
    ):
        result = suggest_next(workspace)

    assert result.top_action is not None
    assert result.top_action.command == "gpd init new-project"


def test_format_command_matches_shared_runtime_surface_helper_for_suggest_next(tmp_path: Path) -> None:
    """Suggest formatting should match the shared active-runtime command helper."""
    workspace_runtime, _ = _runtime_pair_with_distinct_commands("suggest-next")
    adapter = get_adapter(workspace_runtime)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    seed_complete_runtime_install(workspace / adapter.local_config_dir_name, runtime=workspace_runtime)

    result = suggest_module._format_command("suggest-next", cwd=workspace)

    assert result == adapter.format_command("suggest-next")
    assert result == format_active_runtime_command("suggest-next", cwd=workspace, fallback=None)


def test_format_command_falls_back_to_local_cli_for_unknown_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown runtime detection should preserve the local CLI fallback surface."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", lambda cwd=None: RUNTIME_UNKNOWN)

    assert suggest_module._format_command("new-project", cwd=workspace) == "gpd init new-project"


@pytest.mark.parametrize("include_local_conflict", [False, True])
def test_no_project_uses_global_runtime_command_when_global_install_is_effective(
    tmp_path: Path, include_local_conflict: bool
) -> None:
    """A verified global install should surface adapter-formatted commands even with local clutter present."""
    runtime = _RUNTIME_NAMES[0]
    adapter = get_adapter(runtime)
    home_dir = tmp_path / "home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    seed_complete_runtime_install(
        adapter.resolve_global_config_dir(home=home_dir),
        runtime=runtime,
        install_scope="global",
        home=home_dir,
    )
    if include_local_conflict:
        (workspace / adapter.local_config_dir_name).mkdir(parents=True, exist_ok=True)

    result = suggest_next(workspace)

    assert result.top_action is not None
    assert result.top_action.command == adapter.format_command("new-project")
    assert result.top_action.command != "gpd init new-project"


# ─── Empty Project ─────────────────────────────────────────────────────────────


def test_empty_project_suggests_new_milestone(tmp_path: Path) -> None:
    """Project with no roadmap suggests creating one."""
    _setup_project(tmp_path)
    result = suggest_next(tmp_path)
    actions = [s.action for s in result.suggestions]
    assert "new-milestone" in actions


def test_roadmap_no_phases_suggests_plan_first(tmp_path: Path) -> None:
    """Roadmap with no phases suggests starting phase 1."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "plan-first-phase" in actions


# ─── Paused Work ───────────────────────────────────────────────────────────────


def test_paused_work_highest_priority(tmp_path: Path) -> None:
    """Paused work should be the first recommendation."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"position": {"paused_at": "2026-01-15T10:00:00Z", "status": "Paused"}})
    result = suggest_next(root)
    assert result.top_action is not None
    assert result.top_action.action == "resume"
    assert result.top_action.command == "gpd resume"
    assert result.top_action.priority == 1
    assert "2026-01-15" in result.top_action.reason


def test_paused_status_without_timestamp(tmp_path: Path) -> None:
    """Paused status detected even without paused_at timestamp."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"position": {"status": "Paused"}})
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "resume" in actions


# ─── Blockers ──────────────────────────────────────────────────────────────────


def test_blockers_suggest_debug(tmp_path: Path) -> None:
    """Unresolved blockers suggest debugging."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"blockers": ["Need GPU access", "Missing dataset"]})
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "resolve-blockers" in actions
    blocker_rec = next(s for s in result.suggestions if s.action == "resolve-blockers")
    assert "2 unresolved blocker(s)" in blocker_rec.reason
    assert result.context.active_blockers == 2


def test_resolved_blockers_ignored(tmp_path: Path) -> None:
    """Resolved blockers should not trigger suggestion."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"blockers": [{"text": "Old issue", "resolved": True}]})
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "resolve-blockers" not in actions


# ─── Phase Scanning ────────────────────────────────────────────────────────────


def test_in_progress_phase_suggests_execute(tmp_path: Path) -> None:
    """Phase with plans but no summaries suggests execution."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=3, summaries=1)
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "execute-phase" in actions
    exec_rec = next(s for s in result.suggestions if s.action == "execute-phase")
    assert exec_rec.command == "gpd init execute-phase 01"
    assert "2 incomplete plan(s)" in exec_rec.reason
    assert exec_rec.phase == "01"


def test_numbered_plans_are_not_completed_by_bare_summary(tmp_path: Path) -> None:
    """A bare SUMMARY.md must not complete numbered plan files."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    phase_dir = _create_phase(root, "01-setup", plans=1, summaries=0)
    (phase_dir / "SUMMARY.md").write_text("Summary\n", encoding="utf-8")

    result = suggest_next(root)

    assert result.context.phase_count == 1
    assert result.context.completed_phases == 0
    assert any(s.action == "execute-phase" for s in result.suggestions)


def test_standalone_plan_and_summary_count_as_phase_completion(tmp_path: Path) -> None:
    """Standalone PLAN.md and SUMMARY.md should remain a valid completion pair."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    phase_dir = _create_phase(root, "01-setup", plans=0, summaries=0)
    (phase_dir / "PLAN.md").write_text("Plan\n", encoding="utf-8")
    (phase_dir / "SUMMARY.md").write_text("Summary\n", encoding="utf-8")

    result = suggest_next(root)

    assert result.context.phase_count == 1
    assert result.context.completed_phases == 1
    assert all(s.action != "execute-phase" for s in result.suggestions)


def test_complete_unverified_suggests_verify(tmp_path: Path) -> None:
    """Complete phase without verification suggests verification."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=2, summaries=2)
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "verify-work" in actions


def test_researched_phase_suggests_plan(tmp_path: Path) -> None:
    """Phase with research but no plans suggests planning."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=2, summaries=2, verification=True)
    _create_phase(root, "02-core", research=True)
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "plan-phase" in actions
    plan_rec = next(s for s in result.suggestions if s.action == "plan-phase")
    assert plan_rec.command == "gpd init plan-phase 02"
    assert plan_rec.phase == "02"


def test_pending_phase_suggests_discuss(tmp_path: Path) -> None:
    """Pending phase with nothing suggests discussion."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=2, summaries=2, verification=True)
    _create_phase(root, "02-core")  # empty phase
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "discuss-phase" in actions


def test_all_complete_suggests_audit(tmp_path: Path) -> None:
    """All phases complete suggests milestone audit."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=1, summaries=1, verification=True)
    _create_phase(root, "02-core", plans=2, summaries=2, verification=True)
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "audit-milestone" in actions
    assert "write-paper" in actions  # all verified too


def test_roadmap_only_phase_blocks_milestone_audit(tmp_path: Path) -> None:
    """Roadmap phases without matching disk work must keep the milestone open."""
    root = _setup_project(tmp_path)
    _create_roadmap_with_phases(root, [("1", "Setup"), ("2", "Build")])
    _create_phase(root, "01-setup", plans=1, summaries=1, verification=True)

    result = suggest_next(root)

    assert result.context.phase_count == 2
    assert result.context.completed_phases == 1
    assert all(s.action != "audit-milestone" for s in result.suggestions)
    assert all(s.action != "write-paper" for s in result.suggestions)


# ─── Unverified Results ────────────────────────────────────────────────────────


def test_unverified_results_suggest_verification(tmp_path: Path) -> None:
    """Unverified intermediate results suggest verification."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=1, summaries=1)
    _create_state(
        root,
        {
            "intermediate_results": [
                {"id": "result-1", "phase": "1", "verified": False},
                {"id": "result-2", "phase": "1", "verified": True},
            ]
        },
    )
    result = suggest_next(root)
    verify_results = next((s for s in result.suggestions if s.action == "verify-results"), None)
    assert verify_results is not None
    assert verify_results.command == "gpd init verify-work 01"
    assert verify_results.phase == "01"
    assert result.context.unverified_results == 1


def test_unverified_results_with_verification_records_do_not_trigger_verify_results(tmp_path: Path) -> None:
    """verification_records should count as verification evidence for suggestions."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=1, summaries=1)
    _create_state(
        root,
        {
            "intermediate_results": [
                {
                    "id": "result-1",
                    "phase": "1",
                    "verified": False,
                    "verification_records": [{"verifier": "auditor", "method": "manual", "confidence": "low"}],
                }
            ]
        },
    )

    result = suggest_next(root)

    assert all(s.action != "verify-results" for s in result.suggestions)
    assert result.context.unverified_results == 0


def test_unverified_results_without_resolvable_phase_are_suppressed(tmp_path: Path) -> None:
    """verify-results should not emit an unusable phase-less verify-work command."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"intermediate_results": [{"id": "result-1", "verified": False}]})

    result = suggest_next(root)

    assert all(s.action != "verify-results" for s in result.suggestions)
    assert result.context.unverified_results == 1


# ─── Open Questions ────────────────────────────────────────────────────────────


def test_open_questions_suggest_address(tmp_path: Path) -> None:
    """Open questions suggest addressing them."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"open_questions": ["What is the coupling constant?"]})
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "address-questions" in actions
    assert result.context.open_questions == 1


# ─── Active Calculations ──────────────────────────────────────────────────────


def test_active_calculations_suggest_continue(tmp_path: Path) -> None:
    """Active calculations suggest checking status."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"active_calculations": ["RG flow computation"]})
    result = suggest_next(root)
    continue_calculations = next((s for s in result.suggestions if s.action == "continue-calculations"), None)

    assert continue_calculations is not None
    assert continue_calculations.command == "gpd progress"
    assert result.context.active_calculations == 1


# ─── Pending Todos ─────────────────────────────────────────────────────────────


def test_pending_todos_suggest_review(tmp_path: Path) -> None:
    """Pending todo items suggest review."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_todos(root, 3)
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "review-todos" in actions
    assert result.context.pending_todos == 3


# ─── Convention Gaps ───────────────────────────────────────────────────────────


def test_missing_conventions_suggest_set(tmp_path: Path) -> None:
    """Missing core conventions suggest setting them."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"convention_lock": {"metric_signature": "(-,+,+,+)"}})
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "set-conventions" in actions
    assert "natural_units" in result.context.missing_conventions
    assert "coordinate_system" in result.context.missing_conventions


# ─── Paper Pipeline ────────────────────────────────────────────────────────────


def test_markdown_manuscript_is_not_treated_as_new_project(tmp_path: Path) -> None:
    """A markdown manuscript should be recognized without PROJECT.md."""
    _write_active_manuscript_entrypoint(tmp_path, suffix=".md", body="# Markdown manuscript\n")

    result = suggest_next(tmp_path)
    actions = [s.action for s in result.suggestions]

    assert "new-project" not in actions
    assert "new-milestone" in actions
    assert "peer-review" in actions
    assert "arxiv-submission" not in actions
    assert result.context.has_paper is True


def test_paper_exists_suggests_peer_review_before_submission(tmp_path: Path) -> None:
    """Paper draft suggests peer review and does not suggest arXiv before review clears."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _write_active_manuscript_entrypoint(root)
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "peer-review" in actions
    assert "arxiv-submission" not in actions
    assert result.context.has_paper is True


def test_ambiguous_manuscript_state_blocks_write_paper_and_arxiv_submission(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=1, summaries=1, verification=True)
    write_proof_review_package(root, theorem_bearing=False, review_report=True)
    _write_active_manuscript_entrypoint(root, root_name="manuscript")

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "write-paper" not in actions
    assert "arxiv-submission" not in actions
    assert result.context.has_paper is False


def test_inconsistent_manuscript_state_blocks_write_paper_and_arxiv_submission(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=1, summaries=1, verification=True)
    write_proof_review_package(root, theorem_bearing=False, review_report=True)
    paper_dir = root / "paper"
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Alternate Title",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        ),
        encoding="utf-8",
    )

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "write-paper" not in actions
    assert "arxiv-submission" not in actions
    assert result.context.has_paper is False


def test_referee_report_in_planning_root_suggests_response(tmp_path: Path) -> None:
    """Referee report in GPD suggests responding to referees."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _write_active_manuscript_entrypoint(root)
    (root / "GPD" / "REFEREE-REPORT.md").write_text("Major revision needed.\n", encoding="utf-8")
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "respond-to-referees" in actions
    assert "peer-review" not in actions
    assert "arxiv-submission" not in actions  # referee response takes precedence


def test_referee_report_in_canonical_gpd_root_suggests_response(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _write_active_manuscript_entrypoint(root)
    (root / "GPD" / "REFEREE-REPORT.md").write_text("Major revision needed.\n", encoding="utf-8")

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "respond-to-referees" in actions
    assert "peer-review" not in actions


def test_markdown_referee_report_suggests_response_without_arxiv_submission(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _write_active_manuscript_entrypoint(root, suffix=".md", body="# Markdown manuscript\n")
    (root / "GPD" / "REFEREE-REPORT.md").write_text("Major revision needed.\n", encoding="utf-8")

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "respond-to-referees" in actions
    assert "peer-review" not in actions
    assert "arxiv-submission" not in actions


def test_author_response_and_accepted_decision_clear_referee_response_suggestion(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=False, review_report=True)
    _create_roadmap(root)
    (root / "GPD" / "AUTHOR-RESPONSE.md").write_text("Responses incorporated.\n", encoding="utf-8")

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "respond-to-referees" not in actions
    assert "peer-review" not in actions
    assert "arxiv-submission" in actions


def test_blocking_accepted_decision_does_not_suggest_arxiv_submission(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=False, review_report=True)
    _create_roadmap(root)
    (root / "GPD" / "AUTHOR-RESPONSE.md").write_text("Responses incorporated.\n", encoding="utf-8")
    (root / "GPD" / "review" / "REFEREE-DECISION.json").write_text(
        json.dumps(
            {
                "manuscript_path": manuscript_relpath(),
                "target_journal": "jhep",
                "final_recommendation": "accept",
                "final_confidence": "high",
                "stage_artifacts": [f"GPD/review/STAGE-{stage}.json" for stage in ("reader", "literature", "math", "physics", "interestingness")],
                "central_claims_supported": True,
                "claim_scope_proportionate_to_evidence": True,
                "physical_assumptions_justified": True,
                "proof_audit_coverage_complete": True,
                "theorem_proof_alignment_adequate": False,
                "unsupported_claims_are_central": False,
                "reframing_possible_without_new_results": True,
                "mathematical_correctness": "adequate",
                "novelty": "adequate",
                "significance": "adequate",
                "venue_fit": "adequate",
                "literature_positioning": "adequate",
                "unresolved_major_issues": 0,
                "unresolved_minor_issues": 0,
                "blocking_issue_ids": ["REF-001"],
            }
        ),
        encoding="utf-8",
    )

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions


def test_accepted_review_decision_overrides_referee_response_with_submission(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=False, review_report=True)
    _create_roadmap(root)

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "respond-to-referees" not in actions
    assert "peer-review" not in actions
    assert "arxiv-submission" in actions


def test_stale_non_theorem_review_snapshot_does_not_suggest_arxiv_submission(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=False, review_report=True)
    _create_roadmap(root)
    manuscript_path(root).write_text(
        "\\documentclass{article}\n\\begin{document}\nEdited after accepted review.\n\\end{document}\n",
        encoding="utf-8",
    )

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions


def test_review_package_for_different_active_manuscript_does_not_suggest_arxiv_submission(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=False, review_report=True)
    _create_roadmap(root)
    manuscript_path(root).unlink()
    _write_active_manuscript_entrypoint(
        root,
        root_name="manuscript",
        body="\\documentclass{article}\n\\begin{document}\nOther draft.\n\\end{document}\n",
    )

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions


def test_missing_submission_support_artifacts_do_not_suggest_arxiv_submission(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=False, review_report=True)
    _create_roadmap(root)
    for artifact_path in (
        root / "paper" / "ARTIFACT-MANIFEST.json",
        root / "paper" / "BIBLIOGRAPHY-AUDIT.json",
        manuscript_pdf_path(root),
    ):
        artifact_path.unlink()

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions


def test_missing_reproducibility_manifest_blocks_arxiv_submission(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=False, review_report=True)
    _create_roadmap(root)
    (root / "paper" / "reproducibility-manifest.json").unlink()

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions


def test_publication_blockers_block_arxiv_submission_suggestion(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=False, review_report=True)
    _create_roadmap(root)
    _create_state(root, {"blockers": ["Venue fit still unresolved"]})

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions


def test_missing_conventions_block_arxiv_submission_suggestion(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    write_proof_review_package(root, theorem_bearing=False, review_report=True)
    _create_roadmap(root)
    _create_state(root, {"convention_lock": {"metric_signature": "(-,+,+,+)"}})

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions
    assert "set-conventions" in actions
    assert "natural_units" in result.context.missing_conventions


def test_accepted_review_decision_without_review_ledger_does_not_suggest_arxiv_submission(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _write_active_manuscript_entrypoint(root)
    review_dir = root / "GPD" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "REFEREE-DECISION.json").write_text(
        json.dumps(
            {
                "manuscript_path": manuscript_relpath(),
                "target_journal": "jhep",
                "final_recommendation": "accept",
                "final_confidence": "high",
                "stage_artifacts": [],
                "central_claims_supported": True,
                "claim_scope_proportionate_to_evidence": True,
                "physical_assumptions_justified": True,
                "proof_audit_coverage_complete": True,
                "theorem_proof_alignment_adequate": False,
                "unsupported_claims_are_central": False,
                "reframing_possible_without_new_results": True,
                "mathematical_correctness": "adequate",
                "novelty": "adequate",
                "significance": "adequate",
                "venue_fit": "adequate",
                "literature_positioning": "adequate",
                "unresolved_major_issues": 0,
                "unresolved_minor_issues": 0,
                "blocking_issue_ids": [],
            }
        ),
        encoding="utf-8",
    )

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions


def test_theorem_bearing_stale_manuscript_proof_review_blocks_arxiv_submission(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=True, review_report=True)
    _create_roadmap(root)
    (root / "GPD" / "AUTHOR-RESPONSE.md").write_text("Responses incorporated.\n", encoding="utf-8")
    manuscript = manuscript_path(root)
    manuscript.write_text(
        "\\documentclass{article}\n\\begin{document}\nRevised theorem statement.\n\\end{document}\n",
        encoding="utf-8",
    )

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions


def test_theorem_bearing_claim_inventory_without_math_coverage_blocks_arxiv_submission(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=False, review_report=True)
    _create_roadmap(root)
    claims_path = root / "GPD" / "review" / "CLAIMS.json"
    claims_payload = json.loads(claims_path.read_text(encoding="utf-8"))
    claims_payload["claims"][0]["claim_kind"] = "theorem"
    claims_payload["claims"][0]["text"] = "For every r_0 > 0, the orbit intersects the target annulus."
    claims_payload["claims"][0]["theorem_assumptions"] = ["chi > 0"]
    claims_payload["claims"][0]["theorem_parameters"] = ["r_0"]
    claims_path.write_text(json.dumps(claims_payload), encoding="utf-8")
    math_stage_path = root / "GPD" / "review" / "STAGE-math.json"
    math_stage_payload = json.loads(math_stage_path.read_text(encoding="utf-8"))
    math_stage_payload["claims_reviewed"] = []
    math_stage_payload["proof_audits"] = []
    math_stage_path.write_text(json.dumps(math_stage_payload), encoding="utf-8")

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions


def test_theorem_bearing_nested_section_text_blocks_arxiv_submission_without_claim_inventory(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=False, review_report=True)
    _create_roadmap(root)
    manuscript = _write_active_manuscript_entrypoint(
        root,
        body="\\documentclass{article}\n\\begin{document}\n\\input{sections/results}\n\\end{document}\n",
    )
    section_path = manuscript.parent / "sections" / "results.tex"
    section_path.parent.mkdir(parents=True, exist_ok=True)
    section_path.write_text(
        "\\begin{theorem}For every r_0 > 0, the orbit intersects the target annulus.\\end{theorem}\n"
        "\\begin{proof}Nested theorem proof.\\end{proof}\n",
        encoding="utf-8",
    )

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" not in actions


def test_theorem_bearing_fresh_manuscript_proof_review_allows_arxiv_submission(tmp_path: Path) -> None:
    root = _write_submission_review_package(tmp_path, theorem_bearing=True, review_report=True)
    _create_roadmap(root)

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "arxiv-submission" in actions


def test_milestone_referee_report_namespace_does_not_trigger_response(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _write_active_manuscript_entrypoint(root)
    (root / "GPD" / "v1-MILESTONE-REFEREE-REPORT.md").write_text("Milestone review only.\n", encoding="utf-8")

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "respond-to-referees" not in actions
    assert "peer-review" in actions


def test_legacy_lowercase_referee_report_locations_no_longer_trigger_response(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    paper_dir = root / "GPD" / "paper"
    paper_dir.mkdir(parents=True)
    _write_active_manuscript_entrypoint(root)
    (paper_dir / "referee-report-1.md").write_text("Major revision needed.\n", encoding="utf-8")

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "respond-to-referees" not in actions
    assert "peer-review" in actions


def test_non_markdown_referee_report_does_not_trigger_response(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    reports_dir = root / "paper" / "referee-reports"
    reports_dir.mkdir(parents=True)
    _write_active_manuscript_entrypoint(root)
    (reports_dir / "REFEREE-REPORT-1.txt").write_text("Major revision needed.\n", encoding="utf-8")

    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]

    assert "respond-to-referees" not in actions
    assert "peer-review" in actions


def test_literature_review_suggested_when_all_complete(tmp_path: Path) -> None:
    """All complete + no literature review suggests one."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=1, summaries=1, verification=True)
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "literature-review" in actions


# ─── Priority & Limit ─────────────────────────────────────────────────────────


def test_suggestions_sorted_by_priority(tmp_path: Path) -> None:
    """Suggestions should be sorted ascending by priority."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"position": {"paused_at": "2026-01-15"}, "blockers": ["Bug"]})
    _create_phase(root, "01-setup", plans=2, summaries=0)
    _create_todos(root, 5)
    result = suggest_next(root)
    priorities = [s.priority for s in result.suggestions]
    assert priorities == sorted(priorities)


def test_limit_caps_output(tmp_path: Path) -> None:
    """Limit parameter caps the number of suggestions."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(
        root,
        {"position": {"paused_at": "2026-01-15"}, "blockers": ["B1"], "open_questions": ["Q1"]},
    )
    _create_phase(root, "01-setup", plans=2, summaries=0)
    _create_phase(root, "02-core", research=True)
    _create_todos(root, 3)
    result = suggest_next(root, limit=2)
    assert result.suggestion_count <= 2
    assert result.total_suggestions > 2


# ─── Mode-Aware Adjustments ───────────────────────────────────────────────────


def test_explore_mode_boosts_discussion(tmp_path: Path) -> None:
    """Explore mode should lower priority (boost) discuss-phase."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    (root / "GPD" / "config.json").write_text(json.dumps({"research_mode": "explore"}), encoding="utf-8")
    _create_phase(root, "01-setup", plans=2, summaries=0)
    _create_phase(root, "02-core")  # pending
    result = suggest_next(root)
    discuss = next((s for s in result.suggestions if s.action == "discuss-phase"), None)
    assert discuss is not None
    assert discuss.priority <= 5  # boosted from 6


def test_exploit_mode_boosts_execution(tmp_path: Path) -> None:
    """Exploit mode should lower priority (boost) execute-phase."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    (root / "GPD" / "config.json").write_text(json.dumps({"research_mode": "exploit"}), encoding="utf-8")
    _create_phase(root, "01-setup", plans=2, summaries=0)
    result = suggest_next(root)
    execute = next((s for s in result.suggestions if s.action == "execute-phase"), None)
    assert execute is not None
    assert execute.priority <= 3  # boosted from 3 → 2


def test_supervised_mode_penalizes_execution(tmp_path: Path) -> None:
    """Supervised autonomy mode should increase execution priority (penalize)."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    (root / "GPD" / "config.json").write_text(json.dumps({"autonomy": "supervised"}), encoding="utf-8")
    _create_phase(root, "01-setup", plans=2, summaries=0)
    result = suggest_next(root)
    execute = next((s for s in result.suggestions if s.action == "execute-phase"), None)
    assert execute is not None
    assert execute.priority >= 4  # penalized from 3 → 4


def test_yolo_mode_boosts_execution(tmp_path: Path) -> None:
    """YOLO mode should lower execution priority (boost)."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    (root / "GPD" / "config.json").write_text(json.dumps({"autonomy": "yolo"}), encoding="utf-8")
    _create_phase(root, "01-setup", plans=2, summaries=0)
    result = suggest_next(root)
    execute = next((s for s in result.suggestions if s.action == "execute-phase"), None)
    assert execute is not None
    assert execute.priority <= 3  # boosted from 3 → 2


# ─── Phase Sorting ─────────────────────────────────────────────────────────────


def test_decimal_phases_sorted_correctly(tmp_path: Path) -> None:
    """Decimal sub-phases should be sorted numerically (2.1 < 2.10)."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "02.10-late", plans=1, summaries=1, verification=True)
    _create_phase(root, "02.1-early")
    _create_phase(root, "01-base", plans=1, summaries=1, verification=True)
    result = suggest_next(root)
    # 02.1-early is pending, should suggest discuss-phase for it
    discuss = next((s for s in result.suggestions if s.action == "discuss-phase"), None)
    assert discuss is not None
    assert discuss.phase == "02.1"


# ─── Data Model Tests ─────────────────────────────────────────────────────────


def test_recommendation_is_frozen() -> None:
    """Recommendation should be immutable."""
    rec = Recommendation(action="test", priority=1, reason="reason", command="/gpd:test")
    with pytest.raises(AttributeError):
        rec.action = "changed"  # type: ignore[misc]


def test_suggest_context_defaults() -> None:
    """SuggestContext should have sensible defaults."""
    ctx = SuggestContext()
    assert ctx.current_phase is None
    assert ctx.progress_percent == 0.0
    assert ctx.phase_count == 0
    assert ctx.autonomy == "balanced"
    assert ctx.research_mode == "balanced"


def test_suggest_result_fields(tmp_path: Path) -> None:
    """SuggestResult should expose all expected fields."""
    result = suggest_next(tmp_path)
    assert isinstance(result, SuggestResult)
    assert isinstance(result.suggestions, list)
    assert isinstance(result.total_suggestions, int)
    assert isinstance(result.suggestion_count, int)
    assert isinstance(result.context, SuggestContext)


# ─── Adaptive Mode ─────────────────────────────────────────────────────────────


def test_adaptive_mode_without_lock_signal_boosts_discussion(tmp_path: Path) -> None:
    """Adaptive mode should stay discussion-heavy until the method is locked by evidence."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    (root / "GPD" / "config.json").write_text(json.dumps({"research_mode": "adaptive"}), encoding="utf-8")
    _create_phase(root, "01-setup", plans=2, summaries=0)
    _create_phase(root, "02-core")
    result = suggest_next(root)
    discuss = next((s for s in result.suggestions if s.action == "discuss-phase"), None)
    assert discuss is not None
    assert discuss.priority <= 6  # should be boosted
    assert result.context.adaptive_approach_locked is False


def test_adaptive_mode_with_decisive_evidence_boosts_execution_and_verification(tmp_path: Path) -> None:
    """Adaptive mode should narrow only once decisive evidence or an explicit lock exists."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    (root / "GPD" / "config.json").write_text(json.dumps({"research_mode": "adaptive"}), encoding="utf-8")
    locked_phase = _create_phase(root, "00-scan", summaries=1)
    (locked_phase / "01-SUMMARY.md").write_text(
        """---
status: passed
comparison_verdicts:
  - subject_id: claim-benchmark
    subject_kind: claim
    subject_role: decisive
    verdict: pass
---

# Summary
""",
        encoding="utf-8",
    )
    _create_phase(root, "01-setup", plans=2, summaries=0)
    result = suggest_next(root)
    execute = next((s for s in result.suggestions if s.action == "execute-phase"), None)
    assert execute is not None
    assert execute.priority <= 3  # boosted from 3 → 2
    assert result.context.adaptive_approach_locked is True


def test_format_local_cli_command_falls_back_to_canonical_command_surface_for_unmapped_actions() -> None:
    assert suggest_module._format_local_cli_command("discuss-phase") == "gpd:discuss-phase"


# ─── Issue 3: current_phase int coercion ─────────────────────────────────────


def test_int_current_phase_coerced_to_str(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Integer current_phase from state.json must be coerced to str.

    The state module's validated loader normalizes ints before they reach
    suggest_next, so we mock the internal loader to simulate the fallback
    path (direct JSON read) which can return raw int values.
    """
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_phase(root, "01-setup", plans=1, summaries=0)

    raw_state = {"position": {"current_phase": 3, "status": "active"}}
    monkeypatch.setattr(
        "gpd.core.suggest._load_state_json_safe",
        lambda _cwd: raw_state,
    )
    result = suggest_next(root)
    assert result.context.current_phase == "3"
    assert isinstance(result.context.current_phase, str)


def test_none_current_phase_stays_none(tmp_path: Path) -> None:
    """None current_phase should remain None, not become 'None'."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"position": {"status": "active"}})
    result = suggest_next(root)
    assert result.context.current_phase is None


# ─── Issue 4: progress_percent 0 is not swallowed ────────────────────────────


def test_progress_percent_zero_preserved(tmp_path: Path) -> None:
    """progress_percent=0 must stay 0, not be coerced by 'or 0'."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"position": {"progress_percent": 0}})
    result = suggest_next(root)
    assert result.context.progress_percent == 0.0


def test_progress_percent_missing_defaults_to_zero(tmp_path: Path) -> None:
    """Missing progress_percent should default to 0."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"position": {}})
    result = suggest_next(root)
    assert result.context.progress_percent == 0.0


def test_progress_percent_null_defaults_to_zero(tmp_path: Path) -> None:
    """progress_percent: null in JSON must not raise TypeError."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    _create_state(root, {"position": {"progress_percent": None}})
    result = suggest_next(root)
    assert result.context.progress_percent == 0.0
