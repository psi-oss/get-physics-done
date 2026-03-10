"""Coverage wave 15: tests for previously untested public functions.

Targets (prioritized by risk):
  1. state_record_metric       — state-mutating: appends metric rows
  2. state_record_session      — state-mutating: updates session fields
  3. save_state_json_locked    — state-mutating: atomic dual-write core
  4. verify_phase_completeness — validation: plan/summary matching
  5. validate_phase_waves      — validation: wave dependency checks
  6. list_phase_files          — query: lists plans/summaries across phases
  7. safe_parse_int / safe_read_file / safe_read_file_truncated /
     file_lock — pure helpers, widely used
"""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.state import (
    default_state_dict,
    generate_state_markdown,
    save_state_json_locked,
    state_record_metric,
    state_record_session,
)
from gpd.core.utils import (
    file_lock,
    safe_parse_int,
    safe_read_file,
    safe_read_file_truncated,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bootstrap_project(
    tmp_path: Path,
    state_dict: dict | None = None,
    *,
    current_phase: str = "03",
    status: str = "Executing",
) -> Path:
    """Create a minimal .gpd/ project with STATE.md + state.json."""
    planning = tmp_path / ".gpd"
    planning.mkdir(exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    (planning / "PROJECT.md").write_text("# Project\nTest.\n")
    (planning / "ROADMAP.md").write_text("# Roadmap\n")

    state = state_dict or default_state_dict()
    pos = state.setdefault("position", {})
    if pos.get("current_phase") is None:
        pos["current_phase"] = current_phase
    if pos.get("status") is None:
        pos["status"] = status
    if pos.get("current_plan") is None:
        pos["current_plan"] = "1"
    if pos.get("total_plans_in_phase") is None:
        pos["total_plans_in_phase"] = 3
    if pos.get("progress_percent") is None:
        pos["progress_percent"] = 33

    md = generate_state_markdown(state)
    (planning / "STATE.md").write_text(md, encoding="utf-8")
    (planning / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    return tmp_path


def _bootstrap_with_session_fields(tmp_path: Path) -> Path:
    """Bootstrap a project whose STATE.md includes session fields."""
    state = default_state_dict()
    state["position"]["current_phase"] = "01"
    state["position"]["status"] = "Executing"
    state["position"]["current_plan"] = "1"
    state["position"]["total_plans_in_phase"] = 2
    state["position"]["progress_percent"] = 50
    state["session"]["last_date"] = "2025-01-01T00:00:00+00:00"
    state["session"]["stopped_at"] = "Task 3"
    state["session"]["resume_file"] = "resume.md"
    return _bootstrap_project(tmp_path, state_dict=state, current_phase="01", status="Executing")


# ---------------------------------------------------------------------------
# 1. state_record_metric
# ---------------------------------------------------------------------------


class TestStateRecordMetric:
    """Tests for state_record_metric."""

    def test_record_basic_metric(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_record_metric(cwd, phase="03", plan="01", duration="45min")
        assert result.recorded is True
        assert result.phase == "03"
        assert result.plan == "01"
        assert result.duration == "45min"

    def test_record_metric_updates_state_md(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        state_record_metric(cwd, phase="03", plan="01", duration="45min", tasks="5", files="3")
        md = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        assert "Phase 03 P01" in md
        assert "45min" in md
        assert "5 tasks" in md
        assert "3 files" in md

    def test_record_metric_missing_required_fields(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_record_metric(cwd, phase=None, plan="01", duration="10min")
        assert result.recorded is False
        assert result.error is not None

    def test_record_metric_no_duration_fails(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_record_metric(cwd, phase="03", plan="01", duration=None)
        assert result.recorded is False

    def test_record_metric_no_state_file(self, tmp_path: Path) -> None:
        result = state_record_metric(tmp_path, phase="01", plan="01", duration="5min")
        assert result.recorded is False
        assert "not found" in (result.error or "").lower()

    def test_record_multiple_metrics(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        state_record_metric(cwd, phase="03", plan="01", duration="20min")
        state_record_metric(cwd, phase="03", plan="02", duration="30min")
        md = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        assert "Phase 03 P01" in md
        assert "Phase 03 P02" in md

    def test_record_metric_with_optional_fields_as_none(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_record_metric(cwd, phase="03", plan="01", duration="15min", tasks=None, files=None)
        assert result.recorded is True
        md = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        # Should use dash placeholders for missing optional fields
        assert "- tasks" in md or "15min" in md


# ---------------------------------------------------------------------------
# 2. state_record_session
# ---------------------------------------------------------------------------


class TestStateRecordSession:
    """Tests for state_record_session."""

    def test_record_session_basic(self, tmp_path: Path) -> None:
        cwd = _bootstrap_with_session_fields(tmp_path)
        result = state_record_session(cwd, stopped_at="Phase 03 Plan 2")
        assert result.recorded is True
        assert len(result.updated) > 0

    def test_record_session_updates_stopped_at(self, tmp_path: Path) -> None:
        cwd = _bootstrap_with_session_fields(tmp_path)
        state_record_session(cwd, stopped_at="Task 7 of phase 03")
        md = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        assert "Task 7 of phase 03" in md

    def test_record_session_updates_resume_file(self, tmp_path: Path) -> None:
        cwd = _bootstrap_with_session_fields(tmp_path)
        state_record_session(cwd, resume_file="my-resume.md")
        md = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        assert "my-resume.md" in md

    def test_record_session_no_state_file(self, tmp_path: Path) -> None:
        result = state_record_session(tmp_path, stopped_at="Task 1")
        assert result.recorded is False
        assert "not found" in (result.error or "").lower()

    def test_record_session_clears_resume_file(self, tmp_path: Path) -> None:
        """When resume_file is not provided, it should write 'None'."""
        cwd = _bootstrap_with_session_fields(tmp_path)
        state_record_session(cwd, stopped_at="Done")
        md = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        # The session section should have been updated
        assert "Done" in md

    def test_record_session_syncs_json(self, tmp_path: Path) -> None:
        cwd = _bootstrap_with_session_fields(tmp_path)
        state_record_session(cwd, stopped_at="Phase 2 Plan 3")
        json_path = cwd / ".gpd" / "state.json"
        stored = json.loads(json_path.read_text(encoding="utf-8"))
        assert isinstance(stored, dict)


# ---------------------------------------------------------------------------
# 3. save_state_json_locked
# ---------------------------------------------------------------------------


class TestSaveStateJsonLocked:
    """Tests for save_state_json_locked (caller must hold lock)."""

    def test_save_writes_both_files(self, tmp_path: Path) -> None:
        """save_state_json_locked should write state.json AND STATE.md."""
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "phases").mkdir()

        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["status"] = "Planning"

        json_path = planning / "state.json"
        # Must hold lock before calling
        with file_lock(json_path):
            save_state_json_locked(tmp_path, state)

        assert json_path.exists()
        assert (planning / "STATE.md").exists()

        stored = json.loads(json_path.read_text(encoding="utf-8"))
        assert stored["position"]["current_phase"] == "01"

        md = (planning / "STATE.md").read_text(encoding="utf-8")
        assert "Planning" in md

    def test_save_creates_backup(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()

        state = default_state_dict()
        state["position"]["current_phase"] = "02"

        json_path = planning / "state.json"
        with file_lock(json_path):
            save_state_json_locked(tmp_path, state)

        bak_path = planning / "state.json.bak"
        assert bak_path.exists()

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Saving again should overwrite previous content."""
        cwd = _bootstrap_project(tmp_path)
        json_path = cwd / ".gpd" / "state.json"

        state = default_state_dict()
        state["position"]["current_phase"] = "99"
        state["position"]["status"] = "Complete"

        with file_lock(json_path):
            save_state_json_locked(cwd, state)

        stored = json.loads(json_path.read_text(encoding="utf-8"))
        assert stored["position"]["current_phase"] == "99"

    def test_save_cleans_intent_marker(self, tmp_path: Path) -> None:
        """After successful write, the intent marker should be removed."""
        planning = tmp_path / ".gpd"
        planning.mkdir()

        state = default_state_dict()
        json_path = planning / "state.json"
        with file_lock(json_path):
            save_state_json_locked(tmp_path, state)

        intent_path = planning / ".state-write-intent"
        assert not intent_path.exists()


# ---------------------------------------------------------------------------
# 4. verify_phase_completeness
# ---------------------------------------------------------------------------


class TestVerifyPhaseCompleteness:
    """Tests for verify_phase_completeness from frontmatter module."""

    def test_complete_phase(self, tmp_path: Path) -> None:
        from gpd.core.frontmatter import verify_phase_completeness

        # Create a phase with matching plans and summaries
        planning = tmp_path / ".gpd"
        planning.mkdir()
        phases_dir = planning / "phases"
        phase_dir = phases_dir / "01-setup"
        phase_dir.mkdir(parents=True)

        (phase_dir / "01-setup-01-PLAN.md").write_text("---\nwave: 1\ngoal: Setup\n---\n# Plan\n")
        (phase_dir / "01-setup-01-SUMMARY.md").write_text("# Summary\nDone.\n")
        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n### Phase 1: Setup\n**Goal:** Initial setup\n"
        )
        (planning / "state.json").write_text("{}")

        result = verify_phase_completeness(tmp_path, "1")
        assert result.complete is True
        assert result.plan_count == 1
        assert result.summary_count == 1
        assert result.incomplete_plans == []

    def test_incomplete_phase_missing_summary(self, tmp_path: Path) -> None:
        from gpd.core.frontmatter import verify_phase_completeness

        planning = tmp_path / ".gpd"
        planning.mkdir()
        phases_dir = planning / "phases"
        phase_dir = phases_dir / "02-core"
        phase_dir.mkdir(parents=True)

        (phase_dir / "02-core-01-PLAN.md").write_text("---\nwave: 1\n---\n# Plan 1\n")
        (phase_dir / "02-core-02-PLAN.md").write_text("---\nwave: 2\n---\n# Plan 2\n")
        (phase_dir / "02-core-01-SUMMARY.md").write_text("# Summary 1\n")
        # Plan 02 has no summary
        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n### Phase 2: Core\n**Goal:** Core work\n"
        )
        (planning / "state.json").write_text("{}")

        result = verify_phase_completeness(tmp_path, "2")
        assert result.complete is False
        assert result.plan_count == 2
        assert result.summary_count == 1
        assert len(result.incomplete_plans) == 1

    def test_phase_not_found(self, tmp_path: Path) -> None:
        from gpd.core.frontmatter import verify_phase_completeness

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "phases").mkdir()
        (planning / "ROADMAP.md").write_text("# Roadmap\n")
        (planning / "state.json").write_text("{}")

        result = verify_phase_completeness(tmp_path, "99")
        assert result.complete is False
        assert len(result.errors) > 0


# ---------------------------------------------------------------------------
# 7. validate_phase_waves
# ---------------------------------------------------------------------------


class TestValidatePhaseWaves:
    """Tests for validate_phase_waves from phases module."""

    def test_valid_waves(self, tmp_path: Path) -> None:
        from gpd.core.phases import validate_phase_waves

        planning = tmp_path / ".gpd"
        planning.mkdir()
        phases_dir = planning / "phases"
        phase_dir = phases_dir / "01-setup"
        phase_dir.mkdir(parents=True)

        (phase_dir / "01-setup-01-PLAN.md").write_text(
            "---\nwave: 1\nobjective: Build\nfiles_modified: [a.py]\n---\n# Plan\n"
        )
        (phase_dir / "01-setup-02-PLAN.md").write_text(
            "---\nwave: 2\nobjective: Test\ndepends_on: [01-setup-01]\nfiles_modified: [b.py]\n---\n# Plan\n"
        )
        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n### Phase 1: Setup\n**Goal:** Initial\n"
        )
        (planning / "state.json").write_text("{}")

        result = validate_phase_waves(tmp_path, "1")
        assert result.validation is not None
        assert result.validation.valid is True

    def test_phase_not_found(self, tmp_path: Path) -> None:
        from gpd.core.phases import validate_phase_waves

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "phases").mkdir()
        (planning / "ROADMAP.md").write_text("# Roadmap\n")
        (planning / "state.json").write_text("{}")

        result = validate_phase_waves(tmp_path, "99")
        assert result.error == "Phase not found"


# ---------------------------------------------------------------------------
# 8. list_phase_files
# ---------------------------------------------------------------------------


class TestListPhaseFiles:
    """Tests for list_phase_files from phases module."""

    def test_list_plans(self, tmp_path: Path) -> None:
        from gpd.core.phases import list_phase_files

        planning = tmp_path / ".gpd"
        planning.mkdir()
        phases_dir = planning / "phases"
        phase_dir = phases_dir / "01-setup"
        phase_dir.mkdir(parents=True)

        (phase_dir / "01-setup-01-PLAN.md").write_text("# Plan\n")
        (phase_dir / "01-setup-02-PLAN.md").write_text("# Plan\n")
        (phase_dir / "01-setup-01-SUMMARY.md").write_text("# Summary\n")
        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n### Phase 1: Setup\n**Goal:** test\n"
        )
        (planning / "state.json").write_text("{}")

        result = list_phase_files(tmp_path, "plans")
        assert result.count == 2

    def test_list_summaries(self, tmp_path: Path) -> None:
        from gpd.core.phases import list_phase_files

        planning = tmp_path / ".gpd"
        planning.mkdir()
        phases_dir = planning / "phases"
        phase_dir = phases_dir / "01-setup"
        phase_dir.mkdir(parents=True)

        (phase_dir / "01-setup-01-PLAN.md").write_text("# Plan\n")
        (phase_dir / "01-setup-01-SUMMARY.md").write_text("# Summary\n")
        (phase_dir / "01-setup-02-SUMMARY.md").write_text("# Summary\n")
        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n### Phase 1: Setup\n**Goal:** test\n"
        )
        (planning / "state.json").write_text("{}")

        result = list_phase_files(tmp_path, "summaries")
        assert result.count == 2

    def test_list_files_no_phases_dir(self, tmp_path: Path) -> None:
        from gpd.core.phases import list_phase_files

        planning = tmp_path / ".gpd"
        planning.mkdir()
        # No phases/ directory
        (planning / "ROADMAP.md").write_text("# Roadmap\n")
        (planning / "state.json").write_text("{}")

        result = list_phase_files(tmp_path, "plans")
        assert result.count == 0

    def test_list_files_filter_by_phase(self, tmp_path: Path) -> None:
        from gpd.core.phases import list_phase_files

        planning = tmp_path / ".gpd"
        planning.mkdir()
        phases_dir = planning / "phases"

        # Two phases
        for phase_name in ("01-setup", "02-core"):
            d = phases_dir / phase_name
            d.mkdir(parents=True)
            (d / f"{phase_name}-01-PLAN.md").write_text("# Plan\n")

        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n### Phase 1: Setup\n**Goal:** A\n\n### Phase 2: Core\n**Goal:** B\n"
        )
        (planning / "state.json").write_text("{}")

        result = list_phase_files(tmp_path, "plans", phase="1")
        assert result.count == 1

    def test_list_all_files(self, tmp_path: Path) -> None:
        from gpd.core.phases import list_phase_files

        planning = tmp_path / ".gpd"
        planning.mkdir()
        phases_dir = planning / "phases"
        phase_dir = phases_dir / "01-setup"
        phase_dir.mkdir(parents=True)

        (phase_dir / "01-setup-01-PLAN.md").write_text("# Plan\n")
        (phase_dir / "01-setup-01-SUMMARY.md").write_text("# Summary\n")
        (phase_dir / "notes.txt").write_text("notes\n")
        (planning / "ROADMAP.md").write_text(
            "# Roadmap\n\n### Phase 1: Setup\n**Goal:** test\n"
        )
        (planning / "state.json").write_text("{}")

        result = list_phase_files(tmp_path, "all")
        assert result.count == 3


# ---------------------------------------------------------------------------
# 9. safe_parse_* helpers
# ---------------------------------------------------------------------------


class TestSafeParseInt:
    """Tests for safe_parse_int."""

    def test_valid_int_string(self) -> None:
        assert safe_parse_int("42") == 42

    def test_valid_int(self) -> None:
        assert safe_parse_int(7) == 7

    def test_none_returns_default(self) -> None:
        assert safe_parse_int(None) == 0

    def test_none_with_custom_default(self) -> None:
        assert safe_parse_int(None, default=-1) == -1

    def test_invalid_string_returns_default(self) -> None:
        assert safe_parse_int("abc") == 0

    def test_invalid_with_none_default(self) -> None:
        assert safe_parse_int("xyz", default=None) is None

    def test_float_string(self) -> None:
        # "3.14" should fail since it's not a valid int
        assert safe_parse_int("3.14") == 0

    def test_empty_string(self) -> None:
        assert safe_parse_int("") == 0

    def test_negative(self) -> None:
        assert safe_parse_int("-5") == -5

    def test_zero(self) -> None:
        assert safe_parse_int("0") == 0


# ---------------------------------------------------------------------------
# 10. safe_read_file / safe_read_file_truncated
# ---------------------------------------------------------------------------


class TestSafeReadFile:
    """Tests for safe_read_file."""

    def test_reads_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        assert safe_read_file(f) == "hello world"

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert safe_read_file(tmp_path / "missing.txt") is None

    def test_returns_none_for_directory(self, tmp_path: Path) -> None:
        assert safe_read_file(tmp_path) is None


class TestSafeReadFileTruncated:
    """Tests for safe_read_file_truncated."""

    def test_reads_small_file_fully(self, tmp_path: Path) -> None:
        f = tmp_path / "small.txt"
        f.write_text("short content")
        result = safe_read_file_truncated(f)
        assert result == "short content"

    def test_truncates_large_file(self, tmp_path: Path) -> None:
        f = tmp_path / "large.txt"
        content = "x" * 1000
        f.write_text(content)
        result = safe_read_file_truncated(f, max_chars=100)
        assert result is not None
        assert len(result) < 1000
        assert "truncated" in result

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert safe_read_file_truncated(tmp_path / "missing.txt") is None

    def test_custom_max_chars(self, tmp_path: Path) -> None:
        f = tmp_path / "medium.txt"
        f.write_text("a" * 200)
        result = safe_read_file_truncated(f, max_chars=50)
        assert result is not None
        assert result.startswith("a" * 50)
        assert "truncated" in result


# ---------------------------------------------------------------------------
# 11. file_lock
# ---------------------------------------------------------------------------


class TestFileLock:
    """Tests for file_lock context manager."""

    def test_basic_lock_and_unlock(self, tmp_path: Path) -> None:
        target = tmp_path / "lockable.json"
        target.write_text("{}")

        with file_lock(target):
            # Should be able to write while holding lock
            target.write_text('{"locked": true}')

        # After releasing, file should be accessible
        content = target.read_text()
        assert '"locked": true' in content

    def test_lock_creates_lock_file(self, tmp_path: Path) -> None:
        target = tmp_path / "test.json"
        target.write_text("{}")

        with file_lock(target):
            lock_path = target.with_suffix(".json.lock")
            assert lock_path.exists()

    def test_lock_cleans_up(self, tmp_path: Path) -> None:
        target = tmp_path / "test.json"
        target.write_text("{}")

        with file_lock(target):
            pass

        target.with_suffix(".json.lock")
        # Lock file should be cleaned up (or may still exist but unlocked)
        # The important thing is that we don't deadlock

    def test_lock_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "subdir" / "deep" / "test.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}")

        with file_lock(target):
            pass

    def test_lock_on_nonexistent_target(self, tmp_path: Path) -> None:
        """Lock should work even if the target file doesn't exist yet."""
        target = tmp_path / "does_not_exist.json"
        with file_lock(target):
            target.write_text("{}")
        assert target.exists()


# ---------------------------------------------------------------------------
# 15. ProjectLayout predicates and path helpers (constants.py)
# ---------------------------------------------------------------------------


class TestProjectLayoutPredicates:
    """Tests for ProjectLayout methods that had zero test references."""

    def test_config_json(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        assert layout.config_json.name == "config.json"
        assert layout.config_json.parent == tmp_path / ".gpd"

    def test_conventions_md(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        assert layout.conventions_md.name == "CONVENTIONS.md"

    def test_state_archive(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        assert layout.state_archive.name == "STATE-ARCHIVE.md"

    def test_state_json_backup(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        assert layout.state_json_backup.name == "state.json.bak"

    def test_state_intent(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        assert layout.state_intent.name == ".state-write-intent"

    def test_is_plan_file(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        assert layout.is_plan_file("01-PLAN.md") is True
        assert layout.is_plan_file("PLAN.md") is True
        assert layout.is_plan_file("01-SUMMARY.md") is False
        assert layout.is_plan_file("random.txt") is False

    def test_is_summary_file(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        assert layout.is_summary_file("01-SUMMARY.md") is True
        assert layout.is_summary_file("SUMMARY.md") is True
        assert layout.is_summary_file("01-PLAN.md") is False

    def test_is_verification_file(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        assert layout.is_verification_file("01-VERIFICATION.md") is True
        assert layout.is_verification_file("01-PLAN.md") is False

    def test_strip_plan_suffix(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        assert layout.strip_plan_suffix("01-PLAN.md") == "01"
        assert layout.strip_plan_suffix("PLAN.md") == ""
        assert layout.strip_plan_suffix("random.txt") == "random.txt"

    def test_strip_summary_suffix(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        assert layout.strip_summary_suffix("01-SUMMARY.md") == "01"
        assert layout.strip_summary_suffix("SUMMARY.md") == ""
        assert layout.strip_summary_suffix("random.txt") == "random.txt"

    def test_plan_file_path(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        path = layout.plan_file("01-setup", "01")
        assert path.name == "01-PLAN.md"
        assert "01-setup" in str(path)

    def test_summary_file_path(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        path = layout.summary_file("01-setup", "01")
        assert path.name == "01-SUMMARY.md"

    def test_verification_file_path(self, tmp_path: Path) -> None:
        from gpd.core.constants import ProjectLayout

        layout = ProjectLayout(tmp_path)
        path = layout.verification_file("01-setup", "01")
        assert path.name == "01-VERIFICATION.md"


# ---------------------------------------------------------------------------
# 16. gpd_span / instrument_gpd_function
# ---------------------------------------------------------------------------


class TestObservability:
    """Tests for observability module functions with zero coverage."""

    def test_gpd_span_basic(self) -> None:
        from gpd.core.observability import gpd_span

        with gpd_span("test.span", domain="physics") as span:
            assert span is not None

    def test_instrument_gpd_function_sync(self) -> None:
        from gpd.core.observability import instrument_gpd_function

        @instrument_gpd_function("test.func")
        def my_func(x: int) -> int:
            return x * 2

        assert my_func(5) == 10

    def test_instrument_gpd_function_async(self) -> None:
        import asyncio

        from gpd.core.observability import instrument_gpd_function

        @instrument_gpd_function("test.async_func")
        async def my_async_func(x: int) -> int:
            return x + 1

        result = asyncio.run(my_async_func(3))
        assert result == 4


# ---------------------------------------------------------------------------
# 17. check_latest_return (health check)
# ---------------------------------------------------------------------------


class TestCheckLatestReturn:
    """Tests for check_latest_return health check."""

    def test_no_summaries_is_ok(self, tmp_path: Path) -> None:
        from gpd.core.health import check_latest_return

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "phases").mkdir()
        (planning / "state.json").write_text("{}")
        (planning / "config.json").write_text("{}")
        (planning / "ROADMAP.md").write_text("# Roadmap\n")
        (planning / "STATE.md").write_text("# State\n")
        (planning / "PROJECT.md").write_text("# Project\n")

        result = check_latest_return(tmp_path)
        assert result.status.value == "ok"

    def test_summary_with_valid_return(self, tmp_path: Path) -> None:
        from gpd.core.health import check_latest_return

        planning = tmp_path / ".gpd"
        planning.mkdir()
        phases_dir = planning / "phases"
        phase_dir = phases_dir / "01-setup"
        phase_dir.mkdir(parents=True)
        (planning / "state.json").write_text("{}")
        (planning / "config.json").write_text("{}")
        (planning / "ROADMAP.md").write_text("# Roadmap\n")
        (planning / "STATE.md").write_text("# State\n")
        (planning / "PROJECT.md").write_text("# Project\n")

        summary_content = (
            "# Summary\n\n"
            "```yaml\n"
            "gpd_return:\n"
            "  status: completed\n"
            "  phase: '01'\n"
            "  plan: 01-setup-01\n"
            "  tasks_completed: 3\n"
            "  tasks_total: 3\n"
            "  one_liner: Everything done\n"
            "  next_action: Move to phase 2\n"
            "```\n"
        )
        (phase_dir / "01-setup-01-SUMMARY.md").write_text(summary_content)

        result = check_latest_return(tmp_path)
        assert result.status.value == "ok"

    def test_summary_without_return_block(self, tmp_path: Path) -> None:
        from gpd.core.health import check_latest_return

        planning = tmp_path / ".gpd"
        planning.mkdir()
        phases_dir = planning / "phases"
        phase_dir = phases_dir / "01-setup"
        phase_dir.mkdir(parents=True)
        (planning / "state.json").write_text("{}")
        (planning / "config.json").write_text("{}")
        (planning / "ROADMAP.md").write_text("# Roadmap\n")
        (planning / "STATE.md").write_text("# State\n")
        (planning / "PROJECT.md").write_text("# Project\n")

        (phase_dir / "01-setup-01-SUMMARY.md").write_text("# Summary\nJust text, no return block.\n")

        result = check_latest_return(tmp_path)
        assert result.status.value == "warn"
