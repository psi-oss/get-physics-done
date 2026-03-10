"""Smoke tests for EVERY `gpd` CLI command.

Ensures every command can be invoked without crashing in a valid project
directory. This catches the class of bug where CLI functions pass a Path to
core functions that expect a domain object (e.g. convention_check receiving
a Path instead of ConventionLock).

Each test invokes the command with minimal valid arguments. If the command
exits 0, the type plumbing is correct. These are NOT functional tests —
they verify the CLI → core function argument wiring works.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.state import default_state_dict, generate_state_markdown

runner = CliRunner()


@pytest.fixture()
def gpd_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project with all files commands might touch."""
    planning = tmp_path / ".gpd"
    planning.mkdir()

    state = default_state_dict()
    state["position"].update(
        {
            "current_phase": "01",
            "current_phase_name": "Test Phase",
            "total_phases": 2,
            "status": "Planning",
        }
    )
    state["convention_lock"].update(
        {
            "metric_signature": "(-,+,+,+)",
            "coordinate_system": "Cartesian",
            "custom_conventions": {"my_custom": "value"},
        }
    )
    (planning / "state.json").write_text(json.dumps(state, indent=2))
    (planning / "STATE.md").write_text(generate_state_markdown(state))
    (planning / "PROJECT.md").write_text("# Test Project\n\n## Core Research Question\nWhat is physics?\n")
    (planning / "REQUIREMENTS.md").write_text("# Requirements\n\n- [ ] **REQ-01**: Do the thing\n")
    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## Phase 1: Test Phase\nGoal: Test\nRequirements: REQ-01\n"
        "\n## Phase 2: Phase Two\nGoal: More tests\nRequirements: REQ-01\n"
    )
    (planning / "CONVENTIONS.md").write_text("# Conventions\n\n- Metric: (-,+,+,+)\n- Coordinates: Cartesian\n")
    (planning / "config.json").write_text(
        json.dumps(
            {
                "autonomy": "yolo",
                "research_mode": "balanced",
                "parallelization": True,
                "commit_docs": True,
                "model_profile": "review",
                "workflow": {
                    "research": True,
                    "plan_checker": True,
                    "verifier": True,
                },
            }
        )
    )

    # Phase directories
    p1 = planning / "phases" / "01-test-phase"
    p1.mkdir(parents=True)
    (p1 / "README.md").write_text("# Phase 1: Test Phase\n")
    (p1 / "01-SUMMARY.md").write_text("# Summary\n\nExecuted plan summary.\n")
    (p1 / "01-VERIFICATION.md").write_text("# Verification\n\nVerified result.\n")
    p2 = planning / "phases" / "02-phase-two"
    p2.mkdir(parents=True)
    (p2 / "README.md").write_text("# Phase 2: Phase Two\n")

    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nTest manuscript.\n\\end{document}\n")
    (paper_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps({"version": 1, "paper_title": "Test", "journal": "prl", "created_at": "2026-03-10T00:00:00+00:00", "artifacts": []}),
        encoding="utf-8",
    )
    (paper_dir / "BIBLIOGRAPHY-AUDIT.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-10T00:00:00+00:00",
                "total_sources": 0,
                "resolved_sources": 0,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    (paper_dir / "reproducibility-manifest.json").write_text(
        json.dumps(
            {
                "paper_title": "Test",
                "date": "2026-03-10",
                "environment": {
                    "python_version": "3.12.1",
                    "package_manager": "uv",
                    "required_packages": [{"package": "numpy", "version": "1.26.4"}],
                    "lock_file": "pyproject.toml",
                    "system_requirements": {},
                },
                "execution_steps": [{"name": "run", "command": "python scripts/run.py"}],
                "expected_results": [{"quantity": "x", "expected_value": "1", "tolerance": "0.1", "script": "scripts/run.py"}],
                "output_files": [{"path": "results/out.json", "checksum_sha256": "a" * 64}],
                "resource_requirements": [{"step": "run", "cpu_cores": 1, "memory_gb": 1.0}],
                "verification_steps": ["rerun", "compare", "inspect"],
                "minimum_viable": "1 core",
                "recommended": "2 cores",
                "last_verified": "2026-03-10T00:00:00+00:00",
                "last_verified_platform": "macOS-15-arm64",
                "random_seeds": [],
                "seeding_strategy": "",
            }
        ),
        encoding="utf-8",
    )

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "referee-report.md").write_text("# Referee Report\n\n1. Clarify the derivation.\n")

    return tmp_path


@pytest.fixture(autouse=True)
def _chdir(gpd_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """All tests run from the project directory."""
    monkeypatch.chdir(gpd_project)


def _invoke(*args: str, expect_ok: bool = True) -> None:
    """Invoke a gpd CLI command and assert it doesn't crash."""
    result = runner.invoke(app, list(args), catch_exceptions=False)
    if expect_ok:
        assert result.exit_code == 0, f"gpd {' '.join(args)} failed:\n{result.output}"


# ═══════════════════════════════════════════════════════════════════════════
# Convention commands — the original bug class
# ═══════════════════════════════════════════════════════════════════════════


class TestConventionCommands:
    def test_check(self) -> None:
        _invoke("convention", "check")

    def test_list(self) -> None:
        _invoke("convention", "list")

    def test_set(self) -> None:
        _invoke("convention", "set", "natural_units", "SI")

    def test_set_force(self) -> None:
        _invoke("convention", "set", "metric_signature", "(+,-,-,-)", "--force")

    def test_check_empty_state(self, gpd_project: Path) -> None:
        (gpd_project / ".gpd" / "state.json").write_text("{}")
        _invoke("convention", "check")

    def test_check_no_state_file(self, gpd_project: Path) -> None:
        (gpd_project / ".gpd" / "state.json").unlink()
        _invoke("convention", "check")

    def test_set_persists(self, gpd_project: Path) -> None:
        _invoke("convention", "set", "fourier_convention", "physics")
        state = json.loads((gpd_project / ".gpd" / "state.json").read_text())
        assert state["convention_lock"]["fourier_convention"] == "physics"


# ═══════════════════════════════════════════════════════════════════════════
# State commands
# ═══════════════════════════════════════════════════════════════════════════


class TestStateCommands:
    def test_load(self) -> None:
        _invoke("state", "load")

    def test_get(self) -> None:
        _invoke("state", "get")

    def test_get_section(self) -> None:
        _invoke("state", "get", "current_phase")

    def test_validate(self) -> None:
        # May exit 1 if issues found, but must not crash
        result = runner.invoke(app, ["state", "validate"], catch_exceptions=False)
        assert result.exit_code in (0, 1)

    def test_snapshot(self) -> None:
        _invoke("state", "snapshot")

    def test_compact(self) -> None:
        _invoke("state", "compact")

    def test_add_decision(self) -> None:
        _invoke("state", "add-decision", "--summary", "Use SI units", "--rationale", "Standard")

    def test_add_blocker(self) -> None:
        _invoke("state", "add-blocker", "--text", "Need reference data")


# ═══════════════════════════════════════════════════════════════════════════
# Init commands
# ═══════════════════════════════════════════════════════════════════════════


class TestInitCommands:
    def test_new_project(self) -> None:
        _invoke("init", "new-project")

    def test_plan_phase(self) -> None:
        _invoke("init", "plan-phase", "1")

    def test_execute_phase(self) -> None:
        _invoke("init", "execute-phase", "1")


# ═══════════════════════════════════════════════════════════════════════════
# Phase commands
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseCommands:
    def test_list(self) -> None:
        _invoke("phase", "list")

    def test_index(self) -> None:
        _invoke("phase", "index", "1")


# ═══════════════════════════════════════════════════════════════════════════
# Roadmap commands
# ═══════════════════════════════════════════════════════════════════════════


class TestRoadmapCommands:
    def test_get_phase(self) -> None:
        _invoke("roadmap", "get-phase", "1")

    def test_analyze(self) -> None:
        _invoke("roadmap", "analyze")


# ═══════════════════════════════════════════════════════════════════════════
# Progress command
# ═══════════════════════════════════════════════════════════════════════════


class TestProgressCommand:
    def test_progress(self) -> None:
        _invoke("progress")


# ═══════════════════════════════════════════════════════════════════════════
# Verify commands
# ═══════════════════════════════════════════════════════════════════════════


class TestVerifyCommands:
    def test_phase(self) -> None:
        _invoke("verify", "phase", "1")


# ═══════════════════════════════════════════════════════════════════════════
# Result commands
# ═══════════════════════════════════════════════════════════════════════════


class TestResultCommands:
    def test_list(self) -> None:
        _invoke("result", "list")


# ═══════════════════════════════════════════════════════════════════════════
# Approximation commands
# ═══════════════════════════════════════════════════════════════════════════


class TestApproximationCommands:
    def test_list(self) -> None:
        _invoke("approximation", "list")

    def test_add(self) -> None:
        _invoke("approximation", "add", "Born approx", "--validity-range", "x << 1")

    def test_add_minimal(self) -> None:
        """Add with only the name — optional params must not pass None to core."""
        _invoke("approximation", "add", "WKB approx")

    def test_check(self) -> None:
        _invoke("approximation", "check")


# ═══════════════════════════════════════════════════════════════════════════
# Uncertainty commands
# ═══════════════════════════════════════════════════════════════════════════


class TestUncertaintyCommands:
    def test_list(self) -> None:
        _invoke("uncertainty", "list")

    def test_add(self) -> None:
        _invoke("uncertainty", "add", "mass", "--value", "1.0", "--uncertainty", "0.1")

    def test_add_minimal(self) -> None:
        """Add with only the quantity — optional params must not pass None to core."""
        _invoke("uncertainty", "add", "charge")


# ═══════════════════════════════════════════════════════════════════════════
# Question commands
# ═══════════════════════════════════════════════════════════════════════════


class TestQuestionCommands:
    def test_list(self) -> None:
        _invoke("question", "list")

    def test_add(self) -> None:
        _invoke("question", "add", "What is the coupling constant?")

    def test_resolve(self) -> None:
        _invoke("question", "add", "What is the coupling constant?")
        _invoke("question", "resolve", "coupling constant")


# ═══════════════════════════════════════════════════════════════════════════
# Calculation commands
# ═══════════════════════════════════════════════════════════════════════════


class TestCalculationCommands:
    def test_list(self) -> None:
        _invoke("calculation", "list")

    def test_add(self) -> None:
        _invoke("calculation", "add", "Loop integral computation")

    def test_complete(self) -> None:
        _invoke("calculation", "add", "Loop integral computation")
        _invoke("calculation", "complete", "Loop integral")


# ═══════════════════════════════════════════════════════════════════════════
# Utility commands
# ═══════════════════════════════════════════════════════════════════════════


class TestUtilityCommands:
    def test_timestamp(self) -> None:
        _invoke("timestamp")

    def test_slug(self) -> None:
        _invoke("slug", "Hello World Test")


class TestReviewValidationCommands:
    def test_review_contract_uses_typed_registry_surface(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-contract", "write-paper"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:write-paper"
        assert payload["review_contract"]["review_mode"] == "publication"
        assert ".gpd/REFEREE-REPORT.tex" in payload["review_contract"]["required_outputs"]
        assert "artifact manifest" in payload["review_contract"]["required_evidence"]

    def test_review_contract_peer_review_uses_typed_registry_surface(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-contract", "peer-review"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:peer-review"
        assert payload["review_contract"]["review_mode"] == "publication"
        assert ".gpd/REFEREE-REPORT.md" in payload["review_contract"]["required_outputs"]
        assert ".gpd/REFEREE-REPORT.tex" in payload["review_contract"]["required_outputs"]
        assert ".gpd/review/CLAIMS.json" in payload["review_contract"]["required_outputs"]
        assert ".gpd/review/STAGE-interestingness.json" in payload["review_contract"]["required_outputs"]
        assert ".gpd/review/REFEREE-DECISION.json" in payload["review_contract"]["required_outputs"]
        assert payload["review_contract"]["preflight_checks"] == [
            "project_state",
            "roadmap",
            "conventions",
            "research_artifacts",
            "manuscript",
        ]
        assert "artifact manifest" in payload["review_contract"]["required_evidence"]
        assert payload["review_contract"]["stage_ids"] == [
            "reader",
            "literature",
            "math",
            "physics",
            "interestingness",
            "meta",
        ]
        assert payload["review_contract"]["stage_artifacts"] == [
            ".gpd/review/CLAIMS.json",
            ".gpd/review/STAGE-reader.json",
            ".gpd/review/STAGE-literature.json",
            ".gpd/review/STAGE-math.json",
            ".gpd/review/STAGE-physics.json",
            ".gpd/review/STAGE-interestingness.json",
            ".gpd/review/REVIEW-LEDGER.json",
            ".gpd/review/REFEREE-DECISION.json",
        ]
        assert payload["review_contract"]["final_decision_output"] == ".gpd/review/REFEREE-DECISION.json"
        assert payload["review_contract"]["requires_fresh_context_per_stage"] is True

    def test_review_preflight_write_paper_strict(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:write-paper"
        assert payload["passed"] is True
        check_names = {check["name"] for check in payload["checks"]}
        assert {
            "project_state",
            "state_integrity",
            "roadmap",
            "conventions",
            "research_artifacts",
            "verification_reports",
        } <= check_names

    def test_review_preflight_peer_review_strict(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:peer-review"
        assert payload["passed"] is True
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["project_state"]["passed"] is True
        assert checks["state_integrity"]["passed"] is True
        assert checks["roadmap"]["passed"] is True
        assert checks["research_artifacts"]["passed"] is True
        assert checks["verification_reports"]["passed"] is True
        assert checks["manuscript"]["passed"] is True
        assert checks["conventions"]["passed"] is True
        assert checks["artifact_manifest"]["passed"] is True
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["bibliography_audit_clean"]["passed"] is True
        assert checks["reproducibility_manifest"]["passed"] is True
        assert checks["reproducibility_ready"]["passed"] is True

    def test_review_preflight_strict_blocks_review_integrity_failures(self, gpd_project: Path) -> None:
        planning = gpd_project / ".gpd"
        state = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        state["intermediate_results"] = [
            {"id": "R-01", "description": "Unbacked claim", "depends_on": [], "verified": True, "verification_records": []}
        ]
        (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["state_integrity"]["passed"] is False

    def test_review_preflight_verify_work_for_phase(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "verify-work", "1"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:verify-work"
        assert payload["passed"] is True
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["phase_lookup"]["passed"] is True
        assert checks["phase_summaries"]["passed"] is True

    def test_review_preflight_respond_to_referees_checks_report_path(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "respond-to-referees", "reports/referee-report.md"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:respond-to-referees"
        assert payload["passed"] is True
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert checks["referee_report_source"]["passed"] is True

    def test_review_preflight_peer_review_fails_without_manuscript(self, gpd_project: Path) -> None:
        (gpd_project / "paper" / "main.tex").unlink()

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:peer-review"
        assert payload["passed"] is False
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False

    def test_review_preflight_fails_without_manuscript(self, gpd_project: Path) -> None:
        (gpd_project / "paper" / "main.tex").unlink()

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "respond-to-referees", "reports/referee-report.md"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:respond-to-referees"
        assert payload["passed"] is False
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False


    def test_review_preflight_peer_review_strict_requires_artifact_audits(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / "ARTIFACT-MANIFEST.json").unlink()

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["artifact_manifest"]["passed"] is False

    def test_review_preflight_peer_review_accepts_explicit_manuscript_path(self, gpd_project: Path) -> None:
        (gpd_project / "paper" / "main.tex").unlink()

        paper_dir = gpd_project / "paper"
        review_dir = gpd_project / "submission"
        review_dir.mkdir()
        (review_dir / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\nSubmission manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )
        for artifact_name in ("ARTIFACT-MANIFEST.json", "BIBLIOGRAPHY-AUDIT.json", "reproducibility-manifest.json"):
            (review_dir / artifact_name).write_text((paper_dir / artifact_name).read_text(encoding="utf-8"), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "submission/main.tex", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:peer-review"
        assert payload["passed"] is True
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert "submission/main.tex" in checks["manuscript"]["detail"]

    def test_review_preflight_peer_review_accepts_explicit_manuscript_directory(self, gpd_project: Path) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert "resolved to" in checks["manuscript"]["detail"]

    def test_review_preflight_peer_review_directory_uses_lexicographic_fallback_without_main_file(
        self,
        gpd_project: Path,
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / "main.tex").unlink()
        (paper_dir / "z-notes.tex").write_text("\\section{Notes}\n", encoding="utf-8")
        (paper_dir / "a-appendix.md").write_text("# Appendix\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert "a-appendix.md" in checks["manuscript"]["detail"]

    def test_review_preflight_peer_review_strict_blocks_dirty_bibliography_audit(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / "BIBLIOGRAPHY-AUDIT.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-03-10T00:00:00+00:00",
                    "total_sources": 2,
                    "resolved_sources": 1,
                    "partial_sources": 1,
                    "unverified_sources": 0,
                    "failed_sources": 0,
                    "entries": [],
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["bibliography_audit_clean"]["passed"] is False

    def test_review_preflight_peer_review_strict_blocks_non_ready_reproducibility_manifest(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        manifest = json.loads((paper_dir / "reproducibility-manifest.json").read_text(encoding="utf-8"))
        manifest["last_verified"] = ""
        manifest["last_verified_platform"] = ""
        (paper_dir / "reproducibility-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["reproducibility_manifest"]["passed"] is True
        assert checks["reproducibility_ready"]["passed"] is False

    def test_review_preflight_arxiv_submission_strict_requires_artifact_audits(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / "ARTIFACT-MANIFEST.json").unlink()
        (paper_dir / "BIBLIOGRAPHY-AUDIT.json").unlink()

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["artifact_manifest"]["passed"] is False
        assert checks["bibliography_audit"]["passed"] is False

    def test_validate_paper_quality_command(self, gpd_project: Path) -> None:
        quality_path = gpd_project / "paper-quality.json"
        quality_path.write_text(
            json.dumps(
                {
                    "title": "Review-grade paper",
                    "journal": "prd",
                    "equations": {
                        "labeled": {"satisfied": 4, "total": 4},
                        "symbols_defined": {"satisfied": 4, "total": 4},
                        "dimensionally_verified": {"satisfied": 4, "total": 4},
                        "limiting_cases_verified": {"satisfied": 4, "total": 4},
                    },
                    "figures": {
                        "axes_labeled_with_units": {"satisfied": 2, "total": 2},
                        "error_bars_present": {"satisfied": 2, "total": 2},
                        "referenced_in_text": {"satisfied": 2, "total": 2},
                        "captions_self_contained": {"satisfied": 2, "total": 2},
                        "colorblind_safe": {"satisfied": 2, "total": 2},
                    },
                    "citations": {
                        "citation_keys_resolve": {"satisfied": 5, "total": 5},
                        "missing_placeholders": {"passed": True},
                        "key_prior_work_cited": {"passed": True},
                        "hallucination_free": {"passed": True},
                    },
                    "conventions": {
                        "convention_lock_complete": {"passed": True},
                        "assert_convention_coverage": {"satisfied": 3, "total": 3},
                        "notation_consistent": {"passed": True},
                    },
                    "verification": {
                        "report_passed": {"passed": True},
                        "must_haves_verified": {"satisfied": 3, "total": 3},
                        "key_result_confidences": ["INDEPENDENTLY CONFIRMED"],
                    },
                    "completeness": {
                        "abstract_written_last": {"passed": True},
                        "required_sections_present": {"satisfied": 4, "total": 4},
                        "placeholders_cleared": {"passed": True},
                        "supplemental_cross_referenced": {"passed": True},
                    },
                    "results": {
                        "uncertainties_present": {"satisfied": 3, "total": 3},
                        "comparison_with_prior_work_present": {"passed": True},
                        "physical_interpretation_present": {"passed": True},
                    },
                    "journal_extra_checks": {"convergence_three_points": True},
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(app, ["--raw", "validate", "paper-quality", str(quality_path)], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["ready_for_submission"] is True
        assert payload["journal"] == "prd"

    def test_validate_paper_quality_command_fails_on_blockers(self, gpd_project: Path) -> None:
        quality_path = gpd_project / "paper-quality-blocked.json"
        quality_path.write_text(
            json.dumps(
                {
                    "title": "Blocked paper",
                    "journal": "jhep",
                    "citations": {
                        "citation_keys_resolve": {"satisfied": 1, "total": 2},
                        "missing_placeholders": {"passed": False},
                        "key_prior_work_cited": {"passed": False},
                        "hallucination_free": {"passed": False},
                    },
                    "verification": {
                        "report_passed": {"passed": False},
                        "must_haves_verified": {"satisfied": 0, "total": 2},
                        "key_result_confidences": ["UNRELIABLE"],
                    },
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "paper-quality", str(quality_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["ready_for_submission"] is False

    def test_validate_referee_decision_command_accepts_consistent_major_revision(self, gpd_project: Path) -> None:
        decision_path = gpd_project / "referee-decision.json"
        decision_path.write_text(
            json.dumps(
                {
                    "manuscript_path": "paper/main.tex",
                    "target_journal": "jhep",
                    "final_recommendation": "major_revision",
                    "stage_artifacts": [
                        ".gpd/review/STAGE-reader.json",
                        ".gpd/review/STAGE-literature.json",
                        ".gpd/review/STAGE-math.json",
                        ".gpd/review/STAGE-physics.json",
                        ".gpd/review/STAGE-interestingness.json",
                    ],
                    "claim_scope_proportionate_to_evidence": False,
                    "reframing_possible_without_new_results": True,
                    "novelty": "adequate",
                    "significance": "weak",
                    "venue_fit": "adequate",
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "referee-decision", str(decision_path), "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is True
        assert payload["most_positive_allowed_recommendation"] == "major_revision"

    def test_validate_referee_decision_command_blocks_overly_positive_prl_decision(self, gpd_project: Path) -> None:
        decision_path = gpd_project / "referee-decision-prl.json"
        decision_path.write_text(
            json.dumps(
                {
                    "manuscript_path": "paper/main.tex",
                    "target_journal": "prl",
                    "final_recommendation": "minor_revision",
                    "stage_artifacts": [
                        ".gpd/review/STAGE-reader.json",
                        ".gpd/review/STAGE-literature.json",
                        ".gpd/review/STAGE-math.json",
                        ".gpd/review/STAGE-physics.json",
                        ".gpd/review/STAGE-interestingness.json",
                    ],
                    "novelty": "adequate",
                    "significance": "weak",
                    "venue_fit": "weak",
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "referee-decision", str(decision_path), "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert payload["most_positive_allowed_recommendation"] == "reject"

    def test_validate_reproducibility_manifest_strict_command(self, gpd_project: Path) -> None:
        manifest_path = gpd_project / "reproducibility-ready.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "paper_title": "Reproducible Paper",
                    "date": "2026-03-10",
                    "environment": {
                        "python_version": "3.12.1",
                        "package_manager": "uv",
                        "required_packages": [{"package": "numpy", "version": "1.26.4"}],
                        "lock_file": "uv.lock",
                        "system_requirements": {},
                    },
                    "input_data": [
                        {
                            "name": "benchmark",
                            "source": "NIST",
                            "version_or_date": "2026-03-01",
                            "checksum_sha256": "a" * 64,
                        }
                    ],
                    "generated_data": [{"name": "spectrum", "script": "scripts/run.py", "checksum_sha256": "b" * 64}],
                    "execution_steps": [
                        {"name": "prepare", "command": "python scripts/prepare.py"},
                        {"name": "sample", "command": "python scripts/run.py", "stochastic": True},
                    ],
                    "expected_results": [{"quantity": "x", "expected_value": "1", "tolerance": "0.1", "script": "scripts/run.py"}],
                    "output_files": [{"path": "results/out.json", "checksum_sha256": "c" * 64}],
                    "resource_requirements": [
                        {"step": "prepare", "cpu_cores": 1, "memory_gb": 1.0},
                        {"step": "sample", "cpu_cores": 2, "memory_gb": 2.0},
                    ],
                    "random_seeds": [{"computation": "sample", "seed": "42"}],
                    "seeding_strategy": "Fixed seed per stochastic step",
                    "verification_steps": ["rerun pipeline", "compare numbers", "inspect artifacts"],
                    "minimum_viable": "1 core",
                    "recommended": "2 cores",
                    "last_verified": "2026-03-10",
                    "last_verified_platform": "macOS 14 arm64",
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "reproducibility-manifest", str(manifest_path), "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is True
        assert payload["ready_for_review"] is True

    def test_validate_reproducibility_manifest_stdin_strict_fails_when_not_review_ready(self) -> None:
        manifest = {
            "paper_title": "Needs more metadata",
            "date": "2026-03-10",
            "environment": {
                "python_version": "3.12.1",
                "package_manager": "uv",
                "required_packages": [{"package": "numpy", "version": "1.26.4"}],
                "lock_file": "uv.lock",
                "system_requirements": {},
            },
            "execution_steps": [{"name": "run", "command": "python scripts/run.py"}],
            "expected_results": [{"quantity": "x", "expected_value": "1", "tolerance": "0.1", "script": "scripts/run.py"}],
            "output_files": [{"path": "results/out.json", "checksum_sha256": "a" * 64}],
            "resource_requirements": [],
            "verification_steps": ["rerun"],
            "minimum_viable": "",
            "recommended": "",
            "last_verified": "",
            "last_verified_platform": "",
        }

        result = runner.invoke(
            app,
            ["--raw", "validate", "reproducibility-manifest", "-", "--strict"],
            input=json.dumps(manifest),
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is True
        assert payload["ready_for_review"] is False


class TestNoDuplicateTestMethods:
    """Regression: duplicate method names hide tests in Python."""

    def test_no_duplicate_test_method_in_review_validation(self) -> None:
        import ast

        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "TestReviewValidationCommands":
                method_names = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                duplicates = [name for name in method_names if method_names.count(name) > 1]
                assert duplicates == [], f"Duplicate test methods in TestReviewValidationCommands: {set(duplicates)}"
                break
