from __future__ import annotations

from pathlib import Path

from gpd.core.frontmatter import verify_phase_completeness
from gpd.core.phases import list_phase_files, validate_phase_waves


def _create_phase_dir(cwd: Path, name: str) -> Path:
    phase_dir = cwd / ".gpd" / "phases" / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir


def _write_roadmap(cwd: Path, content: str) -> None:
    (cwd / ".gpd" / "ROADMAP.md").write_text(content, encoding="utf-8")


class TestVerifyPhaseCompleteness:
    def test_complete_phase(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path, current_phase="01", status="Planning")
        phase_dir = _create_phase_dir(cwd, "01-setup")
        (phase_dir / "01-setup-01-PLAN.md").write_text("---\nwave: 1\ngoal: Setup\n---\n# Plan\n", encoding="utf-8")
        (phase_dir / "01-setup-01-SUMMARY.md").write_text("# Summary\nDone.\n", encoding="utf-8")
        _write_roadmap(cwd, "# Roadmap\n\n### Phase 1: Setup\n**Goal:** Initial setup\n")

        result = verify_phase_completeness(cwd, "1")

        assert result.complete is True
        assert result.plan_count == 1
        assert result.summary_count == 1
        assert result.incomplete_plans == []

    def test_incomplete_phase_reports_missing_summaries(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path, current_phase="02", status="Planning")
        phase_dir = _create_phase_dir(cwd, "02-core")
        (phase_dir / "02-core-01-PLAN.md").write_text("---\nwave: 1\n---\n# Plan 1\n", encoding="utf-8")
        (phase_dir / "02-core-02-PLAN.md").write_text("---\nwave: 2\n---\n# Plan 2\n", encoding="utf-8")
        (phase_dir / "02-core-01-SUMMARY.md").write_text("# Summary 1\n", encoding="utf-8")
        _write_roadmap(cwd, "# Roadmap\n\n### Phase 2: Core\n**Goal:** Core work\n")

        result = verify_phase_completeness(cwd, "2")

        assert result.complete is False
        assert result.plan_count == 2
        assert result.summary_count == 1
        assert result.incomplete_plans == ["02-core-02"]

    def test_phase_not_found(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path)

        result = verify_phase_completeness(cwd, "99")

        assert result.complete is False
        assert result.errors


class TestValidatePhaseWaves:
    def test_valid_waves(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path, current_phase="01", status="Planning")
        phase_dir = _create_phase_dir(cwd, "01-setup")
        (phase_dir / "01-setup-01-PLAN.md").write_text(
            "---\nwave: 1\nobjective: Build\nfiles_modified: [a.py]\n---\n# Plan\n",
            encoding="utf-8",
        )
        (phase_dir / "01-setup-02-PLAN.md").write_text(
            "---\nwave: 2\nobjective: Test\ndepends_on: [01-setup-01]\nfiles_modified: [b.py]\n---\n# Plan\n",
            encoding="utf-8",
        )
        _write_roadmap(cwd, "# Roadmap\n\n### Phase 1: Setup\n**Goal:** Initial\n")

        result = validate_phase_waves(cwd, "1")

        assert result.validation is not None
        assert result.validation.valid is True

    def test_phase_not_found(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path)

        result = validate_phase_waves(cwd, "99")

        assert result.error == "Phase not found"


class TestListPhaseFiles:
    def test_lists_plan_files(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path, current_phase="01", status="Planning")
        phase_dir = _create_phase_dir(cwd, "01-setup")
        (phase_dir / "01-setup-01-PLAN.md").write_text("# Plan\n", encoding="utf-8")
        (phase_dir / "01-setup-02-PLAN.md").write_text("# Plan\n", encoding="utf-8")
        (phase_dir / "01-setup-01-SUMMARY.md").write_text("# Summary\n", encoding="utf-8")
        _write_roadmap(cwd, "# Roadmap\n\n### Phase 1: Setup\n**Goal:** test\n")

        result = list_phase_files(cwd, "plans")

        assert result.count == 2
        assert result.files == ["01-setup-01-PLAN.md", "01-setup-02-PLAN.md"]

    def test_lists_summary_files(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path, current_phase="01", status="Planning")
        phase_dir = _create_phase_dir(cwd, "01-setup")
        (phase_dir / "01-setup-01-PLAN.md").write_text("# Plan\n", encoding="utf-8")
        (phase_dir / "01-setup-01-SUMMARY.md").write_text("# Summary\n", encoding="utf-8")
        (phase_dir / "01-setup-02-SUMMARY.md").write_text("# Summary\n", encoding="utf-8")
        _write_roadmap(cwd, "# Roadmap\n\n### Phase 1: Setup\n**Goal:** test\n")

        result = list_phase_files(cwd, "summaries")

        assert result.count == 2
        assert result.files == ["01-setup-01-SUMMARY.md", "01-setup-02-SUMMARY.md"]

    def test_returns_zero_when_phases_directory_is_missing(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (planning / "state.json").write_text("{}", encoding="utf-8")

        result = list_phase_files(tmp_path, "plans")

        assert result.count == 0

    def test_filters_by_phase(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path, current_phase="01", status="Planning")

        for phase_name in ("01-setup", "02-core"):
            phase_dir = _create_phase_dir(cwd, phase_name)
            (phase_dir / f"{phase_name}-01-PLAN.md").write_text("# Plan\n", encoding="utf-8")

        _write_roadmap(
            cwd,
            "# Roadmap\n\n### Phase 1: Setup\n**Goal:** A\n\n### Phase 2: Core\n**Goal:** B\n",
        )

        result = list_phase_files(cwd, "plans", phase="1")

        assert result.count == 1
        assert result.phase_dir == "setup"
        assert result.files == ["01-setup-01-PLAN.md"]

    def test_lists_all_files(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path, current_phase="01", status="Planning")
        phase_dir = _create_phase_dir(cwd, "01-setup")
        (phase_dir / "01-setup-01-PLAN.md").write_text("# Plan\n", encoding="utf-8")
        (phase_dir / "01-setup-01-SUMMARY.md").write_text("# Summary\n", encoding="utf-8")
        (phase_dir / "notes.txt").write_text("notes\n", encoding="utf-8")
        _write_roadmap(cwd, "# Roadmap\n\n### Phase 1: Setup\n**Goal:** test\n")

        result = list_phase_files(cwd, "all")

        assert result.count == 3
