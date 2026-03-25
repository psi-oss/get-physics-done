"""Tests for gpd.core.suggest — next-action intelligence."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gpd.adapters import get_adapter, list_runtimes
from gpd.adapters.install_utils import GPD_INSTALL_DIR_NAME, MANIFEST_NAME
from gpd.adapters.runtime_catalog import get_runtime_descriptor
from gpd.core.constants import ENV_GPD_ACTIVE_RUNTIME
from gpd.core.suggest import (
    Recommendation,
    SuggestContext,
    SuggestResult,
    suggest_next,
)

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
    (planning / "PROJECT.md").write_text("# My Project\n")
    return tmp_path


def _create_roadmap(tmp_path: Path, content: str = "# Roadmap\n## Phase 1\n") -> None:
    """Write ROADMAP.md."""
    (tmp_path / "GPD" / "ROADMAP.md").write_text(content)


def _create_state(tmp_path: Path, state: dict[str, object]) -> None:
    """Write state.json."""
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state))


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
        (phase_dir / f"{i:02d}-PLAN.md").write_text(f"Plan {i}\n")
    for i in range(1, summaries + 1):
        (phase_dir / f"{i:02d}-SUMMARY.md").write_text(f"Summary {i}\n")
    if research:
        (phase_dir / "RESEARCH.md").write_text("Research\n")
    if verification:
        (phase_dir / "01-VERIFICATION.md").write_text("Verification\n")
    return phase_dir


def _create_todos(tmp_path: Path, count: int) -> None:
    """Create pending todo files."""
    pending = tmp_path / "GPD" / "todos" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (pending / f"todo-{i}.md").write_text(f"Todo {i}\n")


def _mark_complete_runtime_install(config_dir: Path, *, runtime: str, install_scope: str = "local") -> None:
    """Create the concrete install markers real runtime installs write."""
    (config_dir / GPD_INSTALL_DIR_NAME).mkdir(parents=True, exist_ok=True)
    (config_dir / MANIFEST_NAME).write_text(
        json.dumps({"runtime": runtime, "install_scope": install_scope}),
        encoding="utf-8",
    )


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
    _mark_complete_runtime_install(workspace / workspace_adapter.local_config_dir_name, runtime=workspace_runtime)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _mark_complete_runtime_install(elsewhere / elsewhere_adapter.local_config_dir_name, runtime=elsewhere_runtime)

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
    _mark_complete_runtime_install(elsewhere / get_adapter(elsewhere_runtime).local_config_dir_name, runtime=elsewhere_runtime)

    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
    ):
        result = suggest_next(workspace)

    assert result.top_action is not None
    assert result.top_action.command == "gpd init new-project"


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
    assert result.top_action.command == "gpd init resume"
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
    actions = [s.action for s in result.suggestions]
    assert "continue-calculations" in actions
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


def test_paper_exists_suggests_peer_review_before_submission(tmp_path: Path) -> None:
    """Paper draft suggests peer review before arXiv submission."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    (root / "paper").mkdir()
    (root / "paper" / "main.tex").write_text("\\documentclass{article}\n")
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "peer-review" in actions
    assert "arxiv-submission" in actions
    peer_review = next(s for s in result.suggestions if s.action == "peer-review")
    arxiv_submission = next(s for s in result.suggestions if s.action == "arxiv-submission")
    assert peer_review.priority < arxiv_submission.priority
    assert result.context.has_paper is True


def test_referee_report_in_planning_root_suggests_response(tmp_path: Path) -> None:
    """Referee report in GPD suggests responding to referees."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    (root / "paper").mkdir()
    (root / "paper" / "main.tex").write_text("\\documentclass{article}\n")
    (root / "GPD" / "REFEREE-REPORT.md").write_text("Major revision needed.\n")
    result = suggest_next(root)
    actions = [s.action for s in result.suggestions]
    assert "respond-to-referees" in actions
    assert "peer-review" not in actions
    assert "arxiv-submission" not in actions  # referee response takes precedence


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
    (root / "GPD" / "config.json").write_text(json.dumps({"research_mode": "explore"}))
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
    (root / "GPD" / "config.json").write_text(json.dumps({"research_mode": "exploit"}))
    _create_phase(root, "01-setup", plans=2, summaries=0)
    result = suggest_next(root)
    execute = next((s for s in result.suggestions if s.action == "execute-phase"), None)
    assert execute is not None
    assert execute.priority <= 3  # boosted from 3 → 2


def test_supervised_mode_penalizes_execution(tmp_path: Path) -> None:
    """Supervised autonomy mode should increase execution priority (penalize)."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    (root / "GPD" / "config.json").write_text(json.dumps({"autonomy": "supervised"}))
    _create_phase(root, "01-setup", plans=2, summaries=0)
    result = suggest_next(root)
    execute = next((s for s in result.suggestions if s.action == "execute-phase"), None)
    assert execute is not None
    assert execute.priority >= 4  # penalized from 3 → 4


def test_yolo_mode_boosts_execution(tmp_path: Path) -> None:
    """YOLO mode should lower execution priority (boost)."""
    root = _setup_project(tmp_path)
    _create_roadmap(root)
    (root / "GPD" / "config.json").write_text(json.dumps({"autonomy": "yolo"}))
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
    (root / "GPD" / "config.json").write_text(json.dumps({"research_mode": "adaptive"}))
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
    (root / "GPD" / "config.json").write_text(json.dumps({"research_mode": "adaptive"}))
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
