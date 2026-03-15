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
    run_doctor,
    run_health,
)
from gpd.core.storage_paths import ProjectStorageLayout

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
        hidden_results = cwd / ".gpd" / "phases" / "01-setup" / "results"
        hidden_results.mkdir(parents=True)
        (hidden_results / "out.json").write_text("{}", encoding="utf-8")
        scratch_file = cwd / ".gpd" / "tmp" / "final.csv"
        scratch_file.parent.mkdir(parents=True)
        scratch_file.write_text("x,y\n", encoding="utf-8")

        result = check_storage_paths(cwd)

        assert result.status == CheckStatus.WARN
        assert any(".gpd/phases/01-setup/results/out.json" in warning for warning in result.warnings)
        assert any(".gpd/tmp/final.csv" in warning for warning in result.warnings)


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

    def test_convention_lock_non_dict_warns(self, tmp_path: Path):
        """A truthy non-dict convention_lock must not raise AttributeError."""
        fake_state = {"convention_lock": "not-a-dict"}
        with patch("gpd.core.health.load_state_json", return_value=fake_state):
            result = check_convention_lock(tmp_path)
        assert result.status == CheckStatus.WARN
        assert any("not a dict" in w for w in result.warnings)

    def test_empty_dict_falls_through_to_counting_loop(self, tmp_path: Path):
        """An empty dict {} is a valid convention_lock; should report counts, not 'No convention_lock'."""
        fake_state = {"convention_lock": {}}
        with patch("gpd.core.health.load_state_json", return_value=fake_state):
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

    def test_detects_plan_numbering_gap(self, tmp_path: Path):
        """Standard plan filenames like 01-PLAN.md must be parsed by the regex."""
        phases = tmp_path / ".gpd" / "phases"
        phase_dir = phases / "01-intro"
        phase_dir.mkdir(parents=True)
        # Create plans with a gap: 01, 03 (missing 02)
        plan_content = "---\nwave: 1\n---\n# Plan\n"
        (phase_dir / "01-PLAN.md").write_text(plan_content)
        (phase_dir / "03-PLAN.md").write_text(plan_content)
        result = check_plan_frontmatter(tmp_path)
        assert result.status == CheckStatus.WARN
        assert result.details["numbering_gaps"] >= 1
        assert any("Plan numbering gap" in w for w in result.warnings)

    def test_no_gap_with_consecutive_plans(self, tmp_path: Path):
        """Consecutive plan numbers should not produce warnings."""
        phases = tmp_path / ".gpd" / "phases"
        phase_dir = phases / "01-intro"
        phase_dir.mkdir(parents=True)
        plan_content = "---\nwave: 1\n---\n# Plan\n"
        (phase_dir / "01-PLAN.md").write_text(plan_content)
        (phase_dir / "02-PLAN.md").write_text(plan_content)
        (phase_dir / "03-PLAN.md").write_text(plan_content)
        result = check_plan_frontmatter(tmp_path)
        assert result.details["numbering_gaps"] == 0
        assert not any("Plan numbering gap" in w for w in result.warnings)


class TestCheckStateValidity:
    def test_no_state_files(self, tmp_path: Path):
        result = check_state_validity(tmp_path)
        assert result.label == "State Validity"
        assert result.status == CheckStatus.FAIL
        assert result.issues


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

    def test_fix_mode_removes_stale_checkpoint_tags(self, tmp_path: Path):
        def _run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            if args == ["git", "--version"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="git version 2.45.0\n", stderr="")
            if args[:3] == ["git", "status", "--porcelain"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
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


def _bootstrap_health_project(tmp_path: Path) -> Path:
    planning = tmp_path / ".gpd"
    planning.mkdir()
    (planning / "phases").mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")
    (planning / "config.json").write_text("{}", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (planning / "STATE.md").write_text("# State\n", encoding="utf-8")
    (planning / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    return tmp_path


class TestCheckLatestReturn:
    def test_no_summaries_is_ok(self, tmp_path: Path) -> None:
        result = check_latest_return(_bootstrap_health_project(tmp_path))

        assert result.status == CheckStatus.OK
        assert result.details["reason"] == "no_summaries"

    def test_summary_with_valid_return_is_ok(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        phase_dir = cwd / ".gpd" / "phases" / "01-setup"
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
        phase_dir = cwd / ".gpd" / "phases" / "01-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "01-setup-01-SUMMARY.md").write_text(
            "# Summary\nJust text, no return block.\n",
            encoding="utf-8",
        )

        result = check_latest_return(cwd)

        assert result.status == CheckStatus.WARN
        assert result.warnings
