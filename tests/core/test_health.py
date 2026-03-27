"""Tests for gpd.core.health — health check dashboard."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.core.constants import ProjectLayout
from gpd.core.contract_validation import validate_project_contract
from gpd.core.errors import ValidationError
from gpd.core.health import (
    CheckStatus,
    DoctorReport,
    HealthCheck,
    HealthReport,
    HealthSummary,
    check_checkpoint_tags,
    check_compaction_needed,
    check_config,
    check_convention_lock,
    check_environment,
    check_git_status,
    check_latest_return,
    check_orphans,
    check_plan_frontmatter,
    check_project_structure,
    check_roadmap_consistency,
    check_state_validity,
    check_storage_paths,
    extract_doctor_blockers,
    resolve_doctor_runtime_readiness,
    run_doctor,
    run_health,
)
from gpd.core.state import default_state_dict, generate_state_markdown, save_state_json
from gpd.core.storage_paths import ProjectStorageLayout

_PRIMARY_RUNTIME = iter_runtime_descriptors()[0].runtime_name

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _draft_invalid_project_contract() -> dict[str, object]:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["references"] = ["missing-ref"]
    return contract

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

    def test_extract_doctor_blockers_returns_only_failures(self):
        report = DoctorReport(
            overall=CheckStatus.FAIL,
            version="0.1.0",
            summary=HealthSummary(ok=1, warn=1, fail=2, total=4),
            checks=[
                HealthCheck(status=CheckStatus.OK, label="ok"),
                HealthCheck(status=CheckStatus.WARN, label="warn"),
                HealthCheck(status=CheckStatus.FAIL, label="fail-a"),
                HealthCheck(status=CheckStatus.FAIL, label="fail-b"),
            ],
        )

        blockers = extract_doctor_blockers(report)

        assert [check.label for check in blockers] == ["fail-a", "fail-b"]


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

        planning = tmp_path / "GPD"
        planning.mkdir()
        for f in REQUIRED_PLANNING_FILES:
            (planning / f).write_text("stub")
        for d in REQUIRED_PLANNING_DIRS:
            (planning / d).mkdir(parents=True, exist_ok=True)
        result = check_project_structure(tmp_path)
        assert result.status == CheckStatus.OK


class TestCheckStoragePaths:
    def test_clean_project_is_ok(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(ProjectStorageLayout, "project_root_is_temporary", lambda self: False)
        result = check_storage_paths(_bootstrap_health_project(tmp_path))

        assert result.status == CheckStatus.OK
        assert result.details["warning_count"] == 0

    def test_temp_root_project_warns_even_without_hidden_artifacts(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        temp_root = tmp_path / "runtime-temp"
        temp_root.mkdir()
        monkeypatch.setattr(ProjectStorageLayout, "temp_roots", lambda self: (temp_root.resolve(strict=False),))
        temp_project = temp_root / "project"
        temp_project.mkdir()

        result = check_storage_paths(_bootstrap_health_project(temp_project))

        assert result.status == CheckStatus.WARN
        assert result.details["temporary_project_root"] is True
        assert any("Project root is under a temporary directory" in warning for warning in result.warnings)

    def test_hidden_results_and_scratch_outputs_warn(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        hidden_results = cwd / "GPD" / "phases" / "01-setup" / "results"
        hidden_results.mkdir(parents=True)
        (hidden_results / "out.json").write_text("{}", encoding="utf-8")
        scratch_file = cwd / "GPD" / "tmp" / "final.csv"
        scratch_file.parent.mkdir(parents=True)
        scratch_file.write_text("x,y\n", encoding="utf-8")

        result = check_storage_paths(cwd)

        assert result.status == CheckStatus.WARN
        assert any("GPD/phases/01-setup/results/out.json" in warning for warning in result.warnings)
        assert any("GPD/tmp/final.csv" in warning for warning in result.warnings)

    def test_repo_gitignore_does_not_hide_checkpoint_outputs_under_gpd(self, tmp_path: Path) -> None:
        repo = _init_git_repo(tmp_path)

        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "-v",
                "--",
                "GPD/CHECKPOINTS.md",
                "GPD/phase-checkpoints/01-test-phase.md",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr == ""

    def test_git_status_reports_dirty_tracked_checkpoint_artifacts(self, tmp_path: Path) -> None:
        repo = _init_git_repo(tmp_path)
        checkpoint_dir = repo / "GPD" / "phase-checkpoints"
        checkpoint_dir.mkdir(parents=True)
        root_index = repo / "GPD" / "CHECKPOINTS.md"
        phase_checkpoint = checkpoint_dir / "01-test-phase.md"
        root_index.write_text("initial index\n", encoding="utf-8")
        phase_checkpoint.write_text("initial phase checkpoint\n", encoding="utf-8")

        subprocess.run(["git", "add", "-f", "GPD/CHECKPOINTS.md", "GPD/phase-checkpoints/01-test-phase.md"], cwd=repo, check=True, capture_output=True, text=True)

        root_index.write_text("dirty index\n", encoding="utf-8")
        phase_checkpoint.write_text("dirty phase checkpoint\n", encoding="utf-8")

        result = check_git_status(repo)

        assert result.label == "Git Status"
        assert result.status == CheckStatus.OK
        assert result.details["repo_detected"] is True
        assert result.details["uncommitted_files"] == 2


class TestCheckCompaction:
    def test_no_state_file(self, tmp_path: Path):
        result = check_compaction_needed(tmp_path)
        assert result.status == CheckStatus.OK
        assert result.details.get("reason") == "no_state_file"

    def test_small_state_ok(self, tmp_path: Path):
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "STATE.md").write_text("# State\nShort content\n")
        result = check_compaction_needed(tmp_path)
        assert result.status == CheckStatus.OK


class TestCheckOrphans:
    def test_no_phases_dir(self, tmp_path: Path):
        result = check_orphans(tmp_path)
        assert result.status == CheckStatus.OK

    def test_empty_phase_dir_warns(self, tmp_path: Path):
        phases = tmp_path / "GPD" / "phases"
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
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({"position": {}}))
        result = check_convention_lock(tmp_path)
        assert result.status == CheckStatus.WARN

    def test_convention_lock_non_dict_warns(self, tmp_path: Path):
        """A truthy non-dict convention_lock must not raise AttributeError."""
        fake_state = {"convention_lock": "not-a-dict"}
        with patch("gpd.core.health._peek_normalized_state_for_health", return_value=(fake_state, "state.json")):
            result = check_convention_lock(tmp_path)
        assert result.status == CheckStatus.WARN
        assert any("not a dict" in w for w in result.warnings)

    def test_empty_dict_falls_through_to_counting_loop(self, tmp_path: Path):
        """An empty dict {} is a valid convention_lock; should report counts, not 'No convention_lock'."""
        fake_state = {"convention_lock": {}}
        with patch("gpd.core.health._peek_normalized_state_for_health", return_value=(fake_state, "state.json")):
            result = check_convention_lock(tmp_path)
        assert "No convention_lock in state.json" not in result.warnings
        assert "set" in result.details
        assert "total" in result.details
        assert result.details["set"] == 0


class TestCheckConfig:
    def test_missing_config(self, tmp_path: Path):
        result = check_config(tmp_path)
        assert result.status == CheckStatus.WARN
        assert any("not found" in w for w in result.warnings)


class TestCheckGitStatus:
    def test_non_git_dir(self, tmp_path: Path):
        completed = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain", "GPD/"],
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


class TestCheckCheckpointTags:
    def test_non_git_dir(self, tmp_path: Path):
        completed = subprocess.CompletedProcess(
            args=["git", "tag", "-l", "gpd-checkpoint/*"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository (or any of the parent directories): .git",
        )
        with patch("gpd.core.health.subprocess.run", return_value=completed):
            result = check_checkpoint_tags(tmp_path)

        assert result.label == "Checkpoint Tags"
        assert result.status == CheckStatus.WARN
        assert result.details["repo_detected"] is False
        assert any("not a git repository" in warning for warning in result.warnings)

    def test_warns_on_stale_checkpoint_tags(self, tmp_path: Path):
        def _run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            if args[:3] == ["git", "tag", "-l"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="gpd-checkpoint/old\n", stderr="")
            if args[:4] == ["git", "log", "-1", "--format=%ct"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="0\n", stderr="")
            raise AssertionError(f"Unexpected args: {args}")

        with patch("gpd.core.health.subprocess.run", side_effect=_run):
            result = check_checkpoint_tags(tmp_path)

        assert result.status == CheckStatus.WARN
        assert result.details["stale_tags"] == ["gpd-checkpoint/old"]
        assert any("older than" in warning for warning in result.warnings)


class TestCheckRoadmapConsistency:
    def test_no_roadmap(self, tmp_path: Path):
        result = check_roadmap_consistency(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert any("not found" in i for i in result.issues)

    def test_roadmap_with_matching_phases(self, tmp_path: Path):
        planning = tmp_path / "GPD"
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

    def test_detects_plan_numbering_gap(self, tmp_path: Path):
        """Standard plan filenames like 01-PLAN.md must be parsed by the regex."""
        phases = tmp_path / "GPD" / "phases"
        phase_dir = phases / "01-intro"
        phase_dir.mkdir(parents=True)
        # Create plans with a gap: 01, 03 (missing 02)
        plan_content = _canonical_plan_frontmatter()
        (phase_dir / "01-PLAN.md").write_text(plan_content)
        (phase_dir / "03-PLAN.md").write_text(plan_content)
        result = check_plan_frontmatter(tmp_path)
        assert result.status == CheckStatus.WARN
        assert result.details["numbering_gaps"] >= 1
        assert any("Plan numbering gap" in w for w in result.warnings)

    def test_no_gap_with_consecutive_plans(self, tmp_path: Path):
        """Consecutive plan numbers should not produce warnings."""
        phases = tmp_path / "GPD" / "phases"
        phase_dir = phases / "01-intro"
        phase_dir.mkdir(parents=True)
        plan_content = _canonical_plan_frontmatter()
        (phase_dir / "01-PLAN.md").write_text(plan_content)
        (phase_dir / "02-PLAN.md").write_text(plan_content)
        (phase_dir / "03-PLAN.md").write_text(plan_content)
        result = check_plan_frontmatter(tmp_path)
        assert result.details["numbering_gaps"] == 0
        assert not any("Plan numbering gap" in w for w in result.warnings)

    def test_missing_contract_block_fails(self, tmp_path: Path):
        phases = tmp_path / "GPD" / "phases"
        phase_dir = phases / "01-intro"
        phase_dir.mkdir(parents=True)
        plan_content = (
            "---\n"
            "phase: 01-intro\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "---\n\n"
            "# Plan\n"
        )
        (phase_dir / "01-PLAN.md").write_text(plan_content)

        result = check_plan_frontmatter(tmp_path)

        assert result.status == CheckStatus.FAIL
        assert any("missing required frontmatter fields: contract" in issue for issue in result.issues)

    def test_invalid_contract_schema_fails(self, tmp_path: Path):
        phases = tmp_path / "GPD" / "phases"
        phase_dir = phases / "01-intro"
        phase_dir.mkdir(parents=True)
        plan_content = (
            "---\n"
            "phase: 01-intro\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "contract: []\n"
            "---\n\n"
            "# Plan\n"
        )
        (phase_dir / "01-PLAN.md").write_text(plan_content)

        result = check_plan_frontmatter(tmp_path)

        assert result.status == CheckStatus.FAIL
        assert any("contract: expected an object" in issue for issue in result.issues)


class TestCheckStateValidityProjectContract:
    def test_promotes_approval_blockers_to_issues(self, tmp_path: Path):
        cwd = _bootstrap_health_project(tmp_path)
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["context_intake"] = {
            "must_read_refs": [],
            "must_include_prior_outputs": [],
            "user_asserted_anchors": [],
            "known_good_baselines": [],
            "context_gaps": [],
            "crucial_inputs": [],
        }
        contract["references"][0]["role"] = "background"
        contract["references"][0]["must_surface"] = False
        contract["references"][0]["applies_to"] = []
        contract["references"][0]["required_actions"] = []

        state = {"project_contract": contract}
        (cwd / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")

        approval_validation = validate_project_contract(contract, mode="approved")
        fake_state_validation = SimpleNamespace(
            issues=[],
            warnings=[f"project_contract: {error}" for error in approval_validation.errors],
        )

        with patch("gpd.core.health.state_validate", return_value=fake_state_validation):
            result = check_state_validity(cwd)

        assert result.status == CheckStatus.FAIL
        assert approval_validation.errors
        assert any(issue.startswith("project_contract: ") for issue in result.issues)
        assert not any(warning in result.warnings for warning in fake_state_validation.warnings)

    def test_accepts_project_local_prior_artifact_grounding(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        artifact = cwd / "artifacts" / "benchmark" / "report.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"status": "ok"}\n', encoding="utf-8")

        contract["references"][0]["kind"] = "prior_artifact"
        contract["references"][0]["locator"] = "artifacts/benchmark/report.json"
        contract["references"][0]["role"] = "benchmark"
        contract["references"][0]["must_surface"] = True
        contract["references"][0]["applies_to"] = ["claim-benchmark"]
        contract["references"][0]["required_actions"] = ["compare"]

        state = default_state_dict()
        state["project_contract"] = contract
        save_state_json(cwd, state)
        (cwd / "GPD" / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

        result = check_state_validity(cwd)

        assert not any(issue.startswith("project_contract: ") for issue in result.issues)
        assert not any(warning.startswith("project_contract: ") for warning in result.warnings)

    def test_draft_invalid_project_contract_is_hidden_before_health_approval_checks(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        state = default_state_dict()
        state["project_contract"] = _draft_invalid_project_contract()
        layout = ProjectLayout(cwd)
        layout.state_json.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        layout.state_md.write_text(generate_state_markdown(state), encoding="utf-8")

        result = check_state_validity(cwd)

        assert not any("unknown reference missing-ref" in issue for issue in result.issues)
        assert any("project_contract: claim claim-benchmark references unknown reference missing-ref" in warning for warning in result.warnings)
        assert any(
            'schema normalization: dropped "project_contract" because contract failed draft scoping validation'
            in warning
            for warning in result.warnings
        )


class TestCheckStateValidity:
    def test_no_state_files(self, tmp_path: Path):
        result = check_state_validity(tmp_path)
        assert result.label == "State Validity"
        assert result.status == CheckStatus.FAIL
        assert result.issues

    def test_does_not_repair_state_json_while_inspecting(self, tmp_path: Path) -> None:
        state = default_state_dict()
        state["position"]["status"] = "Executing"
        save_state_json(tmp_path, state)
        layout = ProjectLayout(tmp_path)

        corrupt_state = "{bad json\n"
        backup_before = layout.state_json_backup.read_text(encoding="utf-8")
        layout.state_json.write_text(corrupt_state, encoding="utf-8")

        result = check_state_validity(tmp_path)

        assert result.status == CheckStatus.WARN
        assert layout.state_json.read_text(encoding="utf-8") == corrupt_state
        assert layout.state_json_backup.read_text(encoding="utf-8") == backup_before


# ─── run_health Integration ──────────────────────────────────────────────────


class TestRunHealth:
    def test_returns_report(self, tmp_path: Path):
        report = run_health(tmp_path)
        assert isinstance(report, HealthReport)
        assert report.summary.total >= 13
        assert report.overall in (CheckStatus.OK, CheckStatus.WARN, CheckStatus.FAIL)

    def test_fix_mode(self, tmp_path: Path):
        report = run_health(tmp_path, fix=True)
        assert isinstance(report.fixes_applied, list)

    def test_fixless_mode_does_not_rewrite_corrupt_state(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        layout = ProjectLayout(cwd)

        save_state_json(cwd, default_state_dict())
        primary_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
        primary_state["position"] = []
        layout.state_json.write_text(json.dumps(primary_state, indent=2) + "\n", encoding="utf-8")

        backup_state = default_state_dict()
        backup_state["position"]["current_phase"] = "12"
        backup_state["position"]["status"] = "Executing"
        layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

        before = layout.state_json.read_text(encoding="utf-8")
        report = run_health(cwd, fix=False)
        after = layout.state_json.read_text(encoding="utf-8")
        state_check = next(check for check in report.checks if check.label == "State Validity")

        assert before == after
        assert report.fixes_applied == []
        assert state_check.details["state_source"] == "state.json"

    def test_read_only_health_recovers_intent_marker_and_reports_current_state(
        self, tmp_path: Path
    ) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        layout = ProjectLayout(cwd)

        stale_state = default_state_dict()
        stale_state["position"]["current_phase"] = "01"
        recovered_state = default_state_dict()
        recovered_state["position"]["current_phase"] = "05"
        recovered_state["position"]["status"] = "Executing"
        _write_intent_recovery_state(cwd, stale_state=stale_state, recovered_state=recovered_state)

        before_state = layout.state_json.read_text(encoding="utf-8")
        before_md = layout.state_md.read_text(encoding="utf-8")

        report = run_health(cwd, fix=False)
        state_check = next(check for check in report.checks if check.label == "State Validity")

        assert layout.state_json.read_text(encoding="utf-8") != before_state
        assert layout.state_md.read_text(encoding="utf-8") != before_md
        assert not layout.state_intent.exists()
        assert json.loads(layout.state_json.read_text(encoding="utf-8"))["position"]["current_phase"] == "05"
        assert state_check.details["state_source"] == "state.json"

    def test_fix_mode_restores_backup_state_and_refreshes_report_details(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        layout = ProjectLayout(cwd)

        backup_state = default_state_dict()
        backup_state["position"]["status"] = "Executing"
        backup_state["position"]["current_phase"] = "12"
        backup_state["open_questions"] = ["Recovered from backup"]
        save_state_json(cwd, backup_state)
        backup_payload = json.loads(layout.state_json_backup.read_text(encoding="utf-8"))

        layout.state_json.unlink()
        layout.state_md.write_text("# State\nStale markdown that should not win.\n", encoding="utf-8")

        report = run_health(cwd, fix=True)

        restored_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
        state_check = next(check for check in report.checks if check.label == "State Validity")

        assert restored_state == backup_payload
        assert layout.state_json.exists()
        assert state_check.details["has_json"] is True
        assert state_check.details["has_md"] is True
        assert state_check.details["state_source"] == "state.json"
        assert not any("state.json not found" in issue for issue in state_check.issues)
        assert report.fixes_applied
        assert report.fixes_applied == ["Restored state.json from state.json.bak"]

    def test_fix_mode_regenerates_state_from_state_md_and_refreshes_report_details(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        layout = ProjectLayout(cwd)

        state = default_state_dict()
        state["position"]["status"] = "Executing"
        state["position"]["current_phase"] = "12"
        markdown = generate_state_markdown(state)
        layout.state_md.write_text(markdown, encoding="utf-8")

        layout.state_json.write_text("", encoding="utf-8")
        if layout.state_json_backup.exists():
            layout.state_json_backup.unlink()

        report = run_health(cwd, fix=True)
        state_check = next(check for check in report.checks if check.label == "State Validity")

        assert layout.state_json.exists()
        assert state_check.details["state_source"] == "state.json"
        assert report.fixes_applied == ["Regenerated state.json from STATE.md"]

    def test_fix_mode_restores_state_pair_coherently(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        layout = ProjectLayout(cwd)

        backup_state = default_state_dict()
        backup_state["position"]["status"] = "Executing"
        backup_state["position"]["current_phase"] = "12"
        backup_state["open_questions"] = ["Recovered from backup"]
        save_state_json(cwd, backup_state)
        backup_payload = json.loads(layout.state_json_backup.read_text(encoding="utf-8"))

        layout.state_json.unlink()
        layout.state_md.write_text("# State\nThis markdown is stale.\n", encoding="utf-8")

        report = run_health(cwd, fix=True)

        restored_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
        restored_md = layout.state_md.read_text(encoding="utf-8")

        assert restored_state == backup_payload
        assert "Recovered from backup" in restored_md
        assert "Restored state.json from state.json.bak" in report.fixes_applied

    def test_fix_mode_removes_stale_checkpoint_tags(self, tmp_path: Path):
        def _run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            if args == ["git", "--version"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="git version 2.45.0\n", stderr="")
            if args[:3] == ["git", "status", "--porcelain"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if args[:3] == ["git", "check-ignore", "--quiet"]:
                return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="")
            if args[:3] == ["git", "tag", "-l"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="gpd-checkpoint/old\n", stderr="")
            if args[:4] == ["git", "log", "-1", "--format=%ct"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="0\n", stderr="")
            if args[:3] == ["git", "tag", "-d"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Deleted tag\n", stderr="")
            raise AssertionError(f"Unexpected args: {args}")

        with patch("gpd.core.health.subprocess.run", side_effect=_run):
            report = run_health(tmp_path, fix=True)

        assert any("Removed 1 stale checkpoint tag" in fix for fix in report.fixes_applied)
        checkpoint_check = next(check for check in report.checks if check.label == "Checkpoint Tags")
        assert checkpoint_check.status == CheckStatus.OK
        assert checkpoint_check.details["stale_tags"] == []


class TestRunDoctor:
    def _make_specs_dir(self, tmp_path: Path, *, include_templates: bool = True) -> Path:
        specs = tmp_path / "specs"
        (specs / "references" / "shared").mkdir(parents=True)
        (specs / "references" / "verification" / "core").mkdir(parents=True)
        (specs / "references" / "verification" / "errors").mkdir(parents=True)
        (specs / "workflows").mkdir()
        if include_templates:
            (specs / "templates").mkdir()

        (specs / "references" / "shared" / "shared-protocols.md").write_text("shared\n", encoding="utf-8")
        (specs / "references" / "verification" / "core" / "verification-core.md").write_text(
            "verify\n", encoding="utf-8"
        )
        (specs / "references" / "verification" / "errors" / "llm-physics-errors.md").write_text(
            "errors\n", encoding="utf-8"
        )
        (specs / "workflows" / "plan-phase.md").write_text("plan\n", encoding="utf-8")
        if include_templates:
            (specs / "templates" / "phase-prompt.md").write_text("template\n", encoding="utf-8")

        return specs

    def test_reports_specs_structure(self, tmp_path: Path):
        report = run_doctor(specs_dir=self._make_specs_dir(tmp_path), version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Specs Structure"].status == CheckStatus.OK
        assert checks["Key References"].status == CheckStatus.OK
        assert report.mode == "installation"
        assert report.runtime is None

    def test_missing_required_specs_subdir_fails(self, tmp_path: Path):
        report = run_doctor(specs_dir=self._make_specs_dir(tmp_path, include_templates=False), version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Specs Structure"].status == CheckStatus.FAIL

    def test_missing_nested_key_reference_warns(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        missing_ref = specs_dir / "references" / "verification" / "errors" / "llm-physics-errors.md"
        missing_ref.unlink()

        report = run_doctor(specs_dir=specs_dir, version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Key References"].status == CheckStatus.WARN
        assert any(
            "references/verification/errors/llm-physics-errors.md" in warning
            for warning in checks["Key References"].warnings
        )

    def test_protocol_bundles_check_validates_existing_bundle_assets(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        bundles_dir = specs_dir / "bundles"
        bundles_dir.mkdir()
        (bundles_dir / "supporting-bundle.md").write_text(
            """---
bundle_id: supporting-bundle
bundle_version: 1
title: Supporting Bundle
summary: Supporting bundle referenced by the main doctor fixture.
trigger:
  any_terms:
    - supporting bundle
  min_term_matches: 1
  min_score: 3
---

# Supporting Bundle
""",
            encoding="utf-8",
        )
        (bundles_dir / "test-bundle.md").write_text(
            """---
bundle_id: test-bundle
bundle_version: 1
title: Test Bundle
summary: Minimal bundle used by doctor tests.
trigger:
  any_terms:
    - test bundle
  exclusive_with:
    - supporting-bundle
  min_term_matches: 1
  min_score: 3
assets:
  project_types:
    - path: templates/phase-prompt.md
      required: true
verifier_extensions:
  - name: convergence-audit
    rationale: Validate doctor check_id verification.
    check_ids:
      - "5.5"
---

# Test Bundle
""",
            encoding="utf-8",
        )

        report = run_doctor(specs_dir=specs_dir, version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Protocol Bundles"].status == CheckStatus.OK
        assert checks["Protocol Bundles"].details["bundle_count"] == 2
        assert checks["Protocol Bundles"].details["bundle_ids"] == ["supporting-bundle", "test-bundle"]

    def test_protocol_bundles_check_fails_when_required_asset_is_missing(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        bundles_dir = specs_dir / "bundles"
        bundles_dir.mkdir()
        (bundles_dir / "broken-bundle.md").write_text(
            """---
bundle_id: broken-bundle
bundle_version: 1
title: Broken Bundle
summary: Bundle with a missing required asset.
trigger:
  any_terms:
    - broken bundle
  min_term_matches: 1
  min_score: 3
assets:
  project_types:
    - path: templates/missing-template.md
      required: true
---

# Broken Bundle
""",
            encoding="utf-8",
        )

        report = run_doctor(specs_dir=specs_dir, version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Protocol Bundles"].status == CheckStatus.FAIL
        assert any("templates/missing-template.md" in issue for issue in checks["Protocol Bundles"].issues)

    def test_protocol_bundles_check_fails_when_asset_path_escapes_specs_dir(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        bundles_dir = specs_dir / "bundles"
        bundles_dir.mkdir()
        (bundles_dir / "path-escape-bundle.md").write_text(
            """---
bundle_id: path-escape-bundle
bundle_version: 1
title: Path Escape Bundle
summary: Bundle with an invalid asset path.
trigger:
  any_terms:
    - path escape bundle
  min_term_matches: 1
  min_score: 3
assets:
  project_types:
    - path: ../outside.md
      required: true
---

# Path Escape Bundle
""",
            encoding="utf-8",
        )

        report = run_doctor(specs_dir=specs_dir, version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Protocol Bundles"].status == CheckStatus.FAIL
        assert any("path must stay within specs dir" in issue for issue in checks["Protocol Bundles"].issues)

    def test_protocol_bundles_check_fails_when_bundle_file_is_not_utf8(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        bundles_dir = specs_dir / "bundles"
        bundles_dir.mkdir()
        (bundles_dir / "invalid-encoding.md").write_bytes(b"\xff\xfe\x80")

        report = run_doctor(specs_dir=specs_dir, version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Protocol Bundles"].status == CheckStatus.FAIL
        assert any("unreadable bundle" in issue for issue in checks["Protocol Bundles"].issues)

    def test_protocol_bundles_check_fails_when_verifier_extension_check_id_is_unknown(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        bundles_dir = specs_dir / "bundles"
        bundles_dir.mkdir()
        (bundles_dir / "bad-check-bundle.md").write_text(
            """---
bundle_id: bad-check-bundle
bundle_version: 1
title: Bad Check Bundle
summary: Bundle with an invalid verifier check id.
trigger:
  any_terms:
    - bad check bundle
  min_term_matches: 1
  min_score: 3
verifier_extensions:
  - name: invalid-audit
    rationale: Uses an invalid check id.
    check_ids:
      - "5.99"
---

# Bad Check Bundle
""",
            encoding="utf-8",
        )

        report = run_doctor(specs_dir=specs_dir, version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Protocol Bundles"].status == CheckStatus.FAIL
        assert any("unknown check_id '5.99'" in issue for issue in checks["Protocol Bundles"].issues)

    def test_protocol_bundles_check_fails_when_exclusive_with_bundle_is_unknown(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        bundles_dir = specs_dir / "bundles"
        bundles_dir.mkdir()
        (bundles_dir / "bad-exclusive-bundle.md").write_text(
            """---
bundle_id: bad-exclusive-bundle
bundle_version: 1
title: Bad Exclusive Bundle
summary: Bundle with an unknown exclusive_with target.
trigger:
  any_terms:
    - bad exclusive bundle
  exclusive_with:
    - missing-bundle
  min_term_matches: 1
  min_score: 3
---

# Bad Exclusive Bundle
""",
            encoding="utf-8",
        )

        report = run_doctor(specs_dir=specs_dir, version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Protocol Bundles"].status == CheckStatus.FAIL
        assert any("unknown exclusive_with bundle missing-bundle" in issue for issue in checks["Protocol Bundles"].issues)

    def test_default_mode_excludes_runtime_readiness_checks(self, tmp_path: Path):
        report = run_doctor(specs_dir=self._make_specs_dir(tmp_path), version="0.1.0")
        labels = {check.label for check in report.checks}

        assert report.mode == "installation"
        assert report.runtime is None
        assert report.install_scope is None
        assert report.target is None
        assert "Runtime Launcher" not in labels
        assert "Runtime Config Target" not in labels
        assert "Bootstrap Network Access" not in labels
        assert "Provider/Auth Guidance" not in labels
        assert "LaTeX Toolchain" not in labels
        assert "Optional Workflow Add-ons" not in labels

    def test_runtime_mode_records_virtualenv_state_without_blocking(self, tmp_path: Path):
        target_dir = tmp_path / ".codex"
        specs_dir = self._make_specs_dir(tmp_path)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=False),
            patch("gpd.core.health.shutil.which", return_value="/usr/bin/codex"),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=HealthCheck(status=CheckStatus.OK, label="LaTeX Toolchain"),
            ),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime="codex",
                install_scope="global",
                target_dir=target_dir,
            )

        checks = {check.label: check for check in report.checks}

        assert report.mode == "runtime-readiness"
        assert report.runtime == "codex"
        assert report.install_scope == "global"
        assert report.target == str(target_dir.resolve(strict=False))
        assert checks["Python Runtime"].status in {CheckStatus.OK, CheckStatus.WARN}
        assert checks["Python Runtime"].details["active_virtualenv"] is False
        assert not checks["Python Runtime"].issues
        assert checks["Runtime Launcher"].status == CheckStatus.OK
        assert checks["Runtime Config Target"].status == CheckStatus.OK
        assert checks["Optional Workflow Add-ons"].status == CheckStatus.OK
        assert checks["Optional Workflow Add-ons"].details["ready"] == 1
        assert checks["Optional Workflow Add-ons"].details["missing"] == 0
        assert checks["Optional Workflow Add-ons"].details["degraded"] == 0
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["summary"] == "ready"
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["status"] == "ready"
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["ready_workflows"] == [
            "write-paper",
            "peer-review",
            "paper-build",
            "arxiv-submission",
        ]
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["degraded_workflows"] == []
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["blocked_workflows"] == []
        assert checks["Optional Workflow Add-ons"].warnings == []

    def test_runtime_mode_fails_when_runtime_launcher_is_missing(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health.shutil.which", return_value=None),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=HealthCheck(status=CheckStatus.OK, label="LaTeX Toolchain"),
            ),
        ):
            report = run_doctor(specs_dir=specs_dir, version="0.1.0", runtime=_PRIMARY_RUNTIME, install_scope="global")

        launcher_check = next(check for check in report.checks if check.label == "Runtime Launcher")
        assert launcher_check.status == CheckStatus.FAIL
        assert any("not found on PATH" in issue for issue in launcher_check.issues)

    def test_runtime_mode_fails_when_target_parent_is_not_writable(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        blocked_parent = tmp_path / "blocked"
        blocked_parent.mkdir()
        target_dir = blocked_parent / ".codex"
        blocked_parent_resolved = blocked_parent.resolve(strict=False)

        def _access(path: str | Path, mode: int) -> bool:
            candidate = Path(path).resolve(strict=False)
            if candidate == blocked_parent_resolved:
                return False
            return True

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health.shutil.which", return_value="/usr/bin/codex"),
            patch("gpd.core.health.os.access", side_effect=_access),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=HealthCheck(status=CheckStatus.OK, label="LaTeX Toolchain"),
            ),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime="codex",
                install_scope="global",
                target_dir=target_dir,
            )

        target_check = next(check for check in report.checks if check.label == "Runtime Config Target")
        assert target_check.status == CheckStatus.FAIL
        assert any(str(blocked_parent_resolved) in issue for issue in target_check.issues)

    def test_runtime_advisories_are_non_blocking(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health.shutil.which", return_value="/usr/bin/codex"),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(
                    status=CheckStatus.WARN,
                    label="Bootstrap Network Access",
                    warnings=["registry unavailable"],
                ),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(
                    status=CheckStatus.OK,
                    label="Provider/Auth Guidance",
                    warnings=["manual verification required"],
                ),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=HealthCheck(
                    status=CheckStatus.WARN,
                    label="LaTeX Toolchain",
                    warnings=["latex not installed"],
                ),
            ),
        ):
            report = run_doctor(specs_dir=specs_dir, version="0.1.0", runtime="codex", install_scope="global")

        checks = {check.label: check for check in report.checks}

        assert report.overall == CheckStatus.WARN
        assert checks["Bootstrap Network Access"].status == CheckStatus.WARN
        assert checks["Provider/Auth Guidance"].status == CheckStatus.OK
        assert checks["LaTeX Toolchain"].status == CheckStatus.WARN
        assert checks["Optional Workflow Add-ons"].status == CheckStatus.WARN
        assert checks["Optional Workflow Add-ons"].details["ready"] == 0
        assert checks["Optional Workflow Add-ons"].details["degraded"] == 1
        assert checks["Optional Workflow Add-ons"].details["missing"] == 0
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["status"] == "degraded"
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["usable"] is True
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["summary"] == (
            "degraded (draft/review usable; build/submission require LaTeX)"
        )
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["ready_workflows"] == []
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["degraded_workflows"] == [
            "write-paper",
            "peer-review",
        ]
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["blocked_workflows"] == [
            "paper-build",
            "arxiv-submission",
        ]
        assert checks["Optional Workflow Add-ons"].warnings == [
            "Paper/manuscript workflows are degraded without LaTeX: `write-paper` and `peer-review` remain usable, "
            "but `paper-build` and `arxiv-submission` require a LaTeX toolchain."
        ]
        assert all(
            checks[label].status != CheckStatus.FAIL
            for label in (
                "Bootstrap Network Access",
                "Provider/Auth Guidance",
                "LaTeX Toolchain",
                "Optional Workflow Add-ons",
            )
        )

    def test_runtime_mode_with_explicit_target_does_not_invent_scope(self, tmp_path: Path):
        target_dir = tmp_path / ".runtime-config"
        specs_dir = self._make_specs_dir(tmp_path)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health.shutil.which", return_value="/usr/bin/runtime"),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=HealthCheck(status=CheckStatus.OK, label="LaTeX Toolchain"),
            ),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime=_PRIMARY_RUNTIME,
                target_dir=target_dir,
            )

        assert report.mode == "runtime-readiness"
        assert report.runtime == _PRIMARY_RUNTIME
        assert report.install_scope is None
        assert report.target == str(target_dir.resolve(strict=False))

    def test_runtime_resolution_preserves_explicit_local_scope_and_target(self, tmp_path: Path):
        target_dir = tmp_path / ".runtime-config"

        context = resolve_doctor_runtime_readiness(
            _PRIMARY_RUNTIME,
            install_scope="local",
            target_dir=target_dir,
            cwd=tmp_path,
        )

        assert context.runtime == _PRIMARY_RUNTIME
        assert context.install_scope == "local"
        assert context.target == target_dir.resolve(strict=False)

    def test_runtime_resolution_anchors_relative_target_to_supplied_cwd(self, tmp_path: Path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        context = resolve_doctor_runtime_readiness(
            _PRIMARY_RUNTIME,
            install_scope="local",
            target_dir="relative-target",
            cwd=workspace,
        )

        assert context.runtime == _PRIMARY_RUNTIME
        assert context.install_scope == "local"
        assert context.target == (workspace / "relative-target").resolve(strict=False)

    def test_runtime_mode_with_explicit_local_scope_and_target_keeps_both(self, tmp_path: Path):
        target_dir = tmp_path / ".runtime-config"
        specs_dir = self._make_specs_dir(tmp_path)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health.shutil.which", return_value="/usr/bin/runtime"),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=HealthCheck(status=CheckStatus.OK, label="LaTeX Toolchain"),
            ),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime=_PRIMARY_RUNTIME,
                install_scope="local",
                target_dir=target_dir,
                cwd=tmp_path,
            )

        checks = {check.label: check for check in report.checks}
        assert report.install_scope == "local"
        assert report.target == str(target_dir.resolve(strict=False))
        assert checks["Runtime Config Target"].details["target"] == str(target_dir.resolve(strict=False))

    def test_runtime_mode_with_relative_target_dir_resolves_against_supplied_cwd(self, tmp_path: Path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        specs_dir = self._make_specs_dir(tmp_path)
        expected_target = (workspace / "relative-target").resolve(strict=False)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health.shutil.which", return_value="/usr/bin/runtime"),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=HealthCheck(status=CheckStatus.OK, label="LaTeX Toolchain"),
            ),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime=_PRIMARY_RUNTIME,
                install_scope="local",
                target_dir="relative-target",
                cwd=workspace,
            )

        checks = {check.label: check for check in report.checks}
        assert report.install_scope == "local"
        assert report.target == str(expected_target)
        assert checks["Runtime Config Target"].details["target"] == str(expected_target)

    def test_runtime_mode_rejects_scope_without_runtime(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)

        with pytest.raises(ValidationError, match="install_scope and target_dir require runtime"):
            run_doctor(specs_dir=specs_dir, version="0.1.0", install_scope="local")

    def test_runtime_readiness_mode_adds_selected_runtime_checks(self, tmp_path: Path, monkeypatch):
        specs_dir = self._make_specs_dir(tmp_path)
        monkeypatch.setattr("gpd.core.health.shutil.which", lambda *_args: "/usr/bin/runtime")
        monkeypatch.setattr("gpd.core.health.os.access", lambda *_args: True)
        monkeypatch.setattr(
            "gpd.core.health._doctor_check_bootstrap_network_access",
            lambda: HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
        )
        monkeypatch.setattr(
            "gpd.core.health._doctor_check_latex_toolchain",
            lambda: HealthCheck(status=CheckStatus.WARN, label="LaTeX Toolchain", warnings=["optional"]),
        )

        report = run_doctor(
            specs_dir=specs_dir,
            version="0.1.0",
            runtime=_PRIMARY_RUNTIME,
            install_scope="local",
            cwd=tmp_path,
        )

        checks = {check.label: check for check in report.checks}
        assert report.mode == "runtime-readiness"
        assert report.runtime == _PRIMARY_RUNTIME
        assert report.install_scope == "local"
        assert report.target is not None
        for label in (
            "Runtime Launcher",
            "Runtime Config Target",
            "Bootstrap Network Access",
            "Provider/Auth Guidance",
            "LaTeX Toolchain",
            "Optional Workflow Add-ons",
        ):
            assert label in checks
        assert checks["Runtime Launcher"].status == CheckStatus.OK
        assert checks["Runtime Config Target"].status == CheckStatus.OK
        assert checks["LaTeX Toolchain"].status == CheckStatus.WARN
        assert checks["Optional Workflow Add-ons"].status == CheckStatus.WARN
        assert checks["Optional Workflow Add-ons"].details["add_ons"][0]["label"] == "Paper/manuscript workflows"

    def test_runtime_readiness_fails_when_launcher_missing(self, tmp_path: Path, monkeypatch):
        specs_dir = self._make_specs_dir(tmp_path)
        monkeypatch.setattr("gpd.core.health.shutil.which", lambda *_args: None)
        monkeypatch.setattr("gpd.core.health.os.access", lambda *_args: True)
        monkeypatch.setattr(
            "gpd.core.health._doctor_check_bootstrap_network_access",
            lambda: HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
        )
        monkeypatch.setattr(
            "gpd.core.health._doctor_check_latex_toolchain",
            lambda: HealthCheck(status=CheckStatus.OK, label="LaTeX Toolchain"),
        )

        report = run_doctor(
            specs_dir=specs_dir,
            version="0.1.0",
            runtime=_PRIMARY_RUNTIME,
            install_scope="local",
            cwd=tmp_path,
        )

        checks = {check.label: check for check in report.checks}
        assert report.overall == CheckStatus.FAIL
        assert checks["Runtime Launcher"].status == CheckStatus.FAIL
        assert any("not found on PATH" in issue for issue in checks["Runtime Launcher"].issues)

    def test_runtime_readiness_fails_when_target_is_not_writable(self, tmp_path: Path, monkeypatch):
        specs_dir = self._make_specs_dir(tmp_path)
        monkeypatch.setattr("gpd.core.health.shutil.which", lambda *_args: "/usr/bin/runtime")
        monkeypatch.setattr("gpd.core.health.os.access", lambda *_args: False)
        monkeypatch.setattr(
            "gpd.core.health._doctor_check_bootstrap_network_access",
            lambda: HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
        )
        monkeypatch.setattr(
            "gpd.core.health._doctor_check_latex_toolchain",
            lambda: HealthCheck(status=CheckStatus.OK, label="LaTeX Toolchain"),
        )

        report = run_doctor(
            specs_dir=specs_dir,
            version="0.1.0",
            runtime=_PRIMARY_RUNTIME,
            install_scope="local",
            cwd=tmp_path,
        )

        checks = {check.label: check for check in report.checks}
        assert report.overall == CheckStatus.FAIL
        assert checks["Runtime Config Target"].status == CheckStatus.FAIL
        assert any("not writable" in issue for issue in checks["Runtime Config Target"].issues)


def _bootstrap_health_project(tmp_path: Path) -> Path:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")
    (planning / "config.json").write_text("{}", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (planning / "STATE.md").write_text("# State\n", encoding="utf-8")
    (planning / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    return tmp_path


def _write_intent_recovery_state(
    cwd: Path,
    *,
    stale_state: dict[str, object],
    recovered_state: dict[str, object],
) -> None:
    save_state_json(cwd, stale_state)
    layout = ProjectLayout(cwd)
    json_tmp = layout.gpd / ".state-json-tmp"
    md_tmp = layout.gpd / ".state-md-tmp"
    json_tmp.write_text(json.dumps(recovered_state, indent=2) + "\n", encoding="utf-8")
    md_tmp.write_text(generate_state_markdown(recovered_state), encoding="utf-8")
    layout.state_intent.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")


def _init_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    repo_root = Path(__file__).resolve().parents[2]
    (tmp_path / ".gitignore").write_text((repo_root / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def _canonical_plan_frontmatter() -> str:
    return (FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8")


class TestCheckLatestReturn:
    def test_no_summaries_is_ok(self, tmp_path: Path) -> None:
        result = check_latest_return(_bootstrap_health_project(tmp_path))

        assert result.status == CheckStatus.OK
        assert result.details["reason"] == "no_summaries"

    def test_summary_with_valid_return_is_ok(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        phase_dir = cwd / "GPD" / "phases" / "01-setup"
        phase_dir.mkdir(parents=True)
        summary_content = (
            "# Summary\n\n"
            "```yaml\n"
            "gpd_return:\n"
            "  status: completed\n"
            "  files_written: [src/main.py]\n"
            "  issues: []\n"
            "  next_actions: [/gpd:verify-work 02]\n"
            "```\n"
        )
        (phase_dir / "01-setup-01-SUMMARY.md").write_text(summary_content, encoding="utf-8")

        result = check_latest_return(cwd)

        assert result.status == CheckStatus.OK
        assert result.label == "Latest Return Envelope"

    def test_summary_without_return_block_warns(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        phase_dir = cwd / "GPD" / "phases" / "01-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "01-setup-01-SUMMARY.md").write_text(
            "# Summary\nJust text, no return block.\n",
            encoding="utf-8",
        )

        result = check_latest_return(cwd)

        assert result.status == CheckStatus.WARN
        assert result.warnings
