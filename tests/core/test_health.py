"""Tests for gpd.core.health — health check dashboard."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from gpd.core.health import (
    CheckStatus,
    HealthCheck,
    HealthReport,
    HealthSummary,
    check_compaction_needed,
    check_config,
    check_convention_lock,
    check_environment,
    check_git_status,
    check_orphans,
    check_plan_frontmatter,
    check_project_structure,
    check_roadmap_consistency,
    check_state_validity,
    run_health,
)

# ─── Model Tests ─────────────────────────────────────────────────────────────


class TestCheckStatus:
    def test_values(self):
        assert CheckStatus.OK == "ok"
        assert CheckStatus.WARN == "warn"
        assert CheckStatus.FAIL == "fail"


class TestHealthModels:
    def test_health_check_defaults(self):
        hc = HealthCheck(status=CheckStatus.OK, label="Test")
        assert hc.details == {}
        assert hc.issues == []
        assert hc.warnings == []

    def test_health_summary_defaults(self):
        hs = HealthSummary()
        assert hs.ok == 0
        assert hs.total == 0

    def test_health_report_roundtrip(self):
        report = HealthReport(
            overall=CheckStatus.OK,
            summary=HealthSummary(ok=3, warn=0, fail=0, total=3),
            checks=[HealthCheck(status=CheckStatus.OK, label="A")],
            fixes_applied=["fixed X"],
        )
        data = report.model_dump()
        restored = HealthReport.model_validate(data)
        assert restored.overall == CheckStatus.OK
        assert restored.fixes_applied == ["fixed X"]
        assert len(restored.checks) == 1


# ─── Individual Check Tests ──────────────────────────────────────────────────


class TestCheckEnvironment:
    def test_ok_on_current_python(self):
        result = check_environment()
        assert result.label == "Environment"
        assert result.status == CheckStatus.OK
        assert "python_version" in result.details


class TestCheckProjectStructure:
    def test_missing_planning_dir(self, tmp_path: Path):
        result = check_project_structure(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert len(result.issues) > 0

    def test_ok_with_full_structure(self, tmp_path: Path):
        from gpd.core.constants import REQUIRED_PLANNING_DIRS, REQUIRED_PLANNING_FILES

        planning = tmp_path / ".gpd"
        planning.mkdir()
        for f in REQUIRED_PLANNING_FILES:
            (planning / f).write_text("stub")
        for d in REQUIRED_PLANNING_DIRS:
            (planning / d).mkdir(parents=True, exist_ok=True)
        result = check_project_structure(tmp_path)
        assert result.status == CheckStatus.OK


class TestCheckCompaction:
    def test_no_state_file(self, tmp_path: Path):
        result = check_compaction_needed(tmp_path)
        assert result.status == CheckStatus.OK
        assert result.details.get("reason") == "no_state_file"

    def test_small_state_ok(self, tmp_path: Path):
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "STATE.md").write_text("# State\nShort content\n")
        result = check_compaction_needed(tmp_path)
        assert result.status == CheckStatus.OK


class TestCheckOrphans:
    def test_no_phases_dir(self, tmp_path: Path):
        result = check_orphans(tmp_path)
        assert result.status == CheckStatus.OK

    def test_empty_phase_dir_warns(self, tmp_path: Path):
        phases = tmp_path / ".gpd" / "phases"
        (phases / "01-intro").mkdir(parents=True)
        result = check_orphans(tmp_path)
        assert result.status == CheckStatus.WARN
        assert any("Empty phase" in w for w in result.warnings)


class TestCheckConventionLock:
    def test_no_state_json(self, tmp_path: Path):
        result = check_convention_lock(tmp_path)
        assert result.status == CheckStatus.WARN
        assert any("state.json" in w for w in result.warnings)

    def test_no_convention_lock_key(self, tmp_path: Path):
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({"position": {}}))
        result = check_convention_lock(tmp_path)
        assert result.status == CheckStatus.WARN


class TestCheckConfig:
    def test_missing_config(self, tmp_path: Path):
        result = check_config(tmp_path)
        assert result.status == CheckStatus.WARN
        assert any("not found" in w for w in result.warnings)


class TestCheckGitStatus:
    def test_non_git_dir(self, tmp_path: Path):
        completed = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain", ".gpd/"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository (or any of the parent directories): .git",
        )
        with patch("gpd.core.health.subprocess.run", return_value=completed):
            result = check_git_status(tmp_path)

        assert result.label == "Git Status"
        assert result.status == CheckStatus.WARN
        assert result.details["repo_detected"] is False
        assert any("not a git repository" in warning for warning in result.warnings)


class TestCheckRoadmapConsistency:
    def test_no_roadmap(self, tmp_path: Path):
        result = check_roadmap_consistency(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert any("not found" in i for i in result.issues)

    def test_roadmap_with_matching_phases(self, tmp_path: Path):
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text("## Phase 1: Intro\n## Phase 2: Method\n")
        phases = planning / "phases"
        (phases / "1-intro").mkdir(parents=True)
        (phases / "2-method").mkdir(parents=True)
        result = check_roadmap_consistency(tmp_path)
        assert result.status == CheckStatus.OK


class TestCheckPlanFrontmatter:
    def test_no_phases_dir(self, tmp_path: Path):
        result = check_plan_frontmatter(tmp_path)
        assert result.status == CheckStatus.OK
        assert result.details["plans_checked"] == 0


class TestCheckStateValidity:
    def test_no_state_files(self, tmp_path: Path):
        result = check_state_validity(tmp_path)
        assert result.label == "State Validity"


# ─── run_health Integration ──────────────────────────────────────────────────


class TestRunHealth:
    def test_returns_report(self, tmp_path: Path):
        report = run_health(tmp_path)
        assert isinstance(report, HealthReport)
        assert report.summary.total == 11
        assert report.overall in (CheckStatus.OK, CheckStatus.WARN, CheckStatus.FAIL)

    def test_fix_mode(self, tmp_path: Path):
        report = run_health(tmp_path, fix=True)
        assert isinstance(report.fixes_applied, list)
