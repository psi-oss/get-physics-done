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

import importlib
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.state import default_state_dict, generate_state_markdown

runner = CliRunner()
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "stage0"


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
    (p1 / "01-SUMMARY.md").write_text(
        "---\n"
        "phase: 01-test-phase\n"
        "plan: 01\n"
        "depth: full\n"
        "provides: [executed plan summary]\n"
        "completed: 2026-03-10\n"
        "---\n\n"
        "# Summary\n\nExecuted plan summary.\n"
    )
    (p1 / "01-VERIFICATION.md").write_text(
        "---\n"
        "phase: 01-test-phase\n"
        "verified: 2026-03-10T00:00:00Z\n"
        "status: passed\n"
        "score: 1/1 checks passed\n"
        "---\n\n"
        "# Verification\n\nVerified result.\n"
    )
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


def _write_review_stage_artifacts(project_root: Path, artifact_names: tuple[str, ...] | None = None) -> None:
    review_dir = project_root / ".gpd" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    for artifact_name in artifact_names or (
        "STAGE-reader.json",
        "STAGE-literature.json",
        "STAGE-math.json",
        "STAGE-physics.json",
        "STAGE-interestingness.json",
    ):
        (review_dir / artifact_name).write_text("{}", encoding="utf-8")


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

    def test_set_project_contract(self, gpd_project: Path) -> None:
        contract_path = gpd_project / "contract.json"
        contract_path.write_text(
            (FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        _invoke("state", "set-project-contract", str(contract_path))
        state = json.loads((gpd_project / ".gpd" / "state.json").read_text(encoding="utf-8"))
        assert state["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"

    def test_set_project_contract_resolves_relative_path_against_cwd(self, gpd_project: Path) -> None:
        contract_path = gpd_project / "contract.json"
        contract_path.write_text(
            (FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--cwd", str(gpd_project), "state", "set-project-contract", "contract.json"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        state = json.loads((gpd_project / ".gpd" / "state.json").read_text(encoding="utf-8"))
        assert state["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"

    def test_set_project_contract_accepts_stdin(self, gpd_project: Path) -> None:
        contract_text = (FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8")

        result = runner.invoke(
            app,
            ["--cwd", str(gpd_project), "state", "set-project-contract", "-"],
            input=contract_text,
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        state = json.loads((gpd_project / ".gpd" / "state.json").read_text(encoding="utf-8"))
        assert state["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"

    def test_set_project_contract_rejects_semantically_invalid_contract(self, gpd_project: Path) -> None:
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["uncertainty_markers"]["weakest_anchors"] = []
        contract["uncertainty_markers"]["disconfirming_observations"] = []
        contract_path = gpd_project / "invalid-contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "state", "set-project-contract", str(contract_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert any("weakest_anchors" in error for error in payload["errors"])


# ═══════════════════════════════════════════════════════════════════════════
# Init commands
# ═══════════════════════════════════════════════════════════════════════════


class TestInitCommands:
    def test_new_project(self) -> None:
        _invoke("init", "new-project")

    def test_map_research(self) -> None:
        _invoke("init", "map-research")

    def test_plan_phase(self) -> None:
        _invoke("init", "plan-phase", "1")

    def test_execute_phase(self) -> None:
        _invoke("init", "execute-phase", "1")

    def test_plan_phase_surfaces_artifact_derived_reference_context(self, gpd_project: Path) -> None:
        literature_dir = gpd_project / ".gpd" / "literature"
        literature_dir.mkdir(parents=True)
        (literature_dir / "benchmark-REVIEW.md").write_text(
            """# Literature Review: Benchmark Survey

## Active Anchor Registry

| Anchor | Type | Why It Matters | Required Action | Downstream Use |
| ------ | ---- | -------------- | --------------- | -------------- |
| Benchmark Ref 2024 | benchmark | Published benchmark curve for the decisive observable | read/compare/cite | planning/execution |

```yaml
---
review_summary:
  benchmark_values:
    - quantity: "critical slope"
      value: "1.23 +/- 0.04"
      source: "Benchmark Ref 2024"
  active_anchors:
    - anchor: "Benchmark Ref 2024"
      type: "benchmark"
      why_it_matters: "Published benchmark curve for the decisive observable"
      required_action: "read/compare/cite"
      downstream_use: "planning/execution"
---
```
""",
            encoding="utf-8",
        )
        map_dir = gpd_project / ".gpd" / "research-map"
        map_dir.mkdir(parents=True)
        (map_dir / "REFERENCES.md").write_text(
            """# Reference and Anchor Map

## Active Anchor Registry

| Anchor | Type | Source / Locator | What It Constrains | Required Action | Carry Forward To |
| ------ | ---- | ---------------- | ------------------ | --------------- | ---------------- |
| prior-baseline | prior artifact | `.gpd/phases/01-test-phase/01-SUMMARY.md` | Baseline summary for later comparisons | use | planning/execution |
""",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["--raw", "init", "plan-phase", "1"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)

        assert payload["project_contract"] is None
        assert payload["derived_active_reference_count"] >= 2
        assert "Benchmark Ref 2024" in payload["active_reference_context"]
        assert ".gpd/phases/01-test-phase/01-SUMMARY.md" in payload["active_reference_context"]
        assert ".gpd/phases/01-test-phase/01-SUMMARY.md" in payload["effective_reference_intake"]["must_include_prior_outputs"]

    def test_new_milestone_surfaces_contract_and_effective_reference_context(self, gpd_project: Path) -> None:
        (gpd_project / ".gpd" / "ROADMAP.md").write_text(
            "# Roadmap\n\n## Milestone v1.1: Scaling Study\n",
            encoding="utf-8",
        )
        state = json.loads((gpd_project / ".gpd" / "state.json").read_text(encoding="utf-8"))
        state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        (gpd_project / ".gpd" / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

        literature_dir = gpd_project / ".gpd" / "literature"
        literature_dir.mkdir(parents=True)
        (literature_dir / "benchmark-REVIEW.md").write_text(
            "## Active Anchor Registry\n\n"
            "| Anchor | Type | Why It Matters | Required Action | Downstream Use |\n"
            "| ------ | ---- | -------------- | --------------- | -------------- |\n"
            "| Benchmark Ref 2024 | benchmark | Published benchmark curve for the decisive observable | read/compare/cite | planning/execution |\n",
            encoding="utf-8",
        )
        map_dir = gpd_project / ".gpd" / "research-map"
        map_dir.mkdir(parents=True)
        (map_dir / "CONCERNS.md").write_text(
            "## Prior Outputs\n\n"
            "- `.gpd/phases/01-test-phase/01-SUMMARY.md`\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["--raw", "init", "new-milestone"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)

        assert payload["current_milestone"] == "v1.1"
        assert payload["project_contract"]["references"][0]["id"] == "ref-benchmark"
        assert "Benchmark Ref 2024" in payload["active_reference_context"]
        assert ".gpd/phases/01-test-phase/01-SUMMARY.md" in payload["effective_reference_intake"]["must_include_prior_outputs"]
        assert ".gpd/research-map/CONCERNS.md" in payload["research_map_reference_files"]


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
        assert payload["context_mode"] == "project-required"
        assert payload["review_contract"]["review_mode"] == "publication"
        assert ".gpd/REFEREE-REPORT.tex" in payload["review_contract"]["required_outputs"]
        assert payload["review_contract"]["preflight_checks"] == [
            "project_state",
            "roadmap",
            "conventions",
            "research_artifacts",
            "manuscript",
        ]
        assert "existing manuscript" in payload["review_contract"]["required_evidence"]
        assert "phase summaries or milestone digest" in payload["review_contract"]["required_evidence"]
        assert "verification reports" in payload["review_contract"]["required_evidence"]
        assert "bibliography audit" in payload["review_contract"]["required_evidence"]
        assert "artifact manifest" in payload["review_contract"]["required_evidence"]
        assert "reproducibility manifest" in payload["review_contract"]["required_evidence"]

    def test_review_contract_peer_review_uses_typed_registry_surface(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-contract", "peer-review"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:peer-review"
        assert payload["context_mode"] == "project-required"
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
        assert "existing manuscript" in payload["review_contract"]["required_evidence"]
        assert "phase summaries or milestone digest" in payload["review_contract"]["required_evidence"]
        assert "verification reports" in payload["review_contract"]["required_evidence"]
        assert "bibliography audit" in payload["review_contract"]["required_evidence"]
        assert "artifact manifest" in payload["review_contract"]["required_evidence"]
        assert "reproducibility manifest" in payload["review_contract"]["required_evidence"]
        assert "stage review artifacts" in payload["review_contract"]["required_evidence"]
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

    def test_review_contract_accepts_public_command_label(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-contract", "/gpd:peer-review"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:peer-review"
        assert payload["review_contract"]["review_mode"] == "publication"

    def test_review_contract_respond_to_referees_uses_typed_registry_surface(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-contract", "respond-to-referees"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:respond-to-referees"
        assert payload["context_mode"] == "project-required"
        assert payload["review_contract"]["review_mode"] == "publication"
        assert ".gpd/paper/REFEREE_RESPONSE.md" in payload["review_contract"]["required_outputs"]
        assert ".gpd/AUTHOR-RESPONSE.md" in payload["review_contract"]["required_outputs"]
        assert "existing manuscript" in payload["review_contract"]["required_evidence"]
        assert "structured referee issues" in payload["review_contract"]["required_evidence"]
        assert "peer-review review ledger when available" in payload["review_contract"]["required_evidence"]
        assert "peer-review decision artifacts when available" in payload["review_contract"]["required_evidence"]
        assert "revision verification evidence" in payload["review_contract"]["required_evidence"]

    def test_command_context_project_required_fails_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "progress"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:progress"
        assert payload["context_mode"] == "project-required"
        assert payload["passed"] is False
        assert payload["guidance"] == (
            "This command requires an initialized GPD project. Run `gpd init new-project`."
        )

    def test_command_context_projectless_passes_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", "map-research"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:map-research"
        assert payload["context_mode"] == "projectless"
        assert payload["passed"] is True

    def test_command_context_slides_passes_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "slides"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:slides"
        assert payload["context_mode"] == "projectless"
        assert payload["passed"] is True

    def test_command_context_project_aware_requires_explicit_inputs_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "discover"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:discover"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is False
        assert payload["explicit_inputs"] == ["phase number or standalone topic"]
        assert payload["guidance"] == (
            "Either provide phase number or standalone topic explicitly, or run `gpd init new-project`."
        )

    def test_command_context_project_aware_accepts_explicit_inputs_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", "discover", "finite-temperature RG flow --depth deep"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:discover"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is True

    def test_command_context_project_aware_rejects_short_flag_without_topic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", "discover", "-d", "deep"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:discover"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is False

    def test_command_context_explain_requires_explicit_inputs_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "explain"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:explain"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is False
        assert payload["explicit_inputs"] == ["concept, result, method, notation, or paper"]
        assert payload["guidance"] == (
            "Either provide concept, result, method, notation, or paper explicitly, or run `gpd init new-project`."
        )

    def test_command_context_compare_results_requires_explicit_inputs_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "compare-results"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:compare-results"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is False
        assert payload["explicit_inputs"] == ["phase, artifact, or comparison target"]
        assert payload["guidance"] == (
            "Either provide phase, artifact, or comparison target explicitly, or run `gpd init new-project`."
        )

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
        checks = {check["name"]: check for check in payload["checks"]}
        check_names = set(checks)
        assert {
            "project_state",
            "state_integrity",
            "roadmap",
            "conventions",
            "research_artifacts",
            "verification_reports",
        } <= check_names
        assert checks["reproducibility_manifest"]["passed"] is True
        assert checks["reproducibility_ready"]["passed"] is True

    def test_command_context_global_command_passes_without_project(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "help"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:help"
        assert payload["context_mode"] == "global"
        assert payload["passed"] is True
        assert checks["project_context"]["passed"] is True

    def test_command_context_projectless_command_passes_without_project(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "new-project"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:new-project"
        assert payload["context_mode"] == "projectless"
        assert payload["passed"] is True
        assert checks["project_context"]["passed"] is True

    def test_command_context_project_aware_command_accepts_explicit_inputs(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "discover", "7"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:discover"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is True
        assert checks["project_exists"]["passed"] is False
        assert checks["explicit_inputs"]["passed"] is True

    def test_command_context_project_required_command_fails_without_project(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "quick"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:quick"
        assert payload["context_mode"] == "project-required"
        assert payload["passed"] is False
        assert checks["project_exists"]["passed"] is False

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

    def test_review_preflight_strict_blocks_semantically_invalid_project_contract(self, gpd_project: Path) -> None:
        planning = gpd_project / ".gpd"
        state = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["uncertainty_markers"]["weakest_anchors"] = []
        contract["uncertainty_markers"]["disconfirming_observations"] = []
        state["project_contract"] = contract
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
        assert "project_contract:" in checks["state_integrity"]["detail"]

    def test_review_preflight_strict_blocks_invalid_phase_artifact_frontmatter(self, gpd_project: Path) -> None:
        planning = gpd_project / ".gpd"
        phase_dir = planning / "phases" / "01-test-phase"
        (phase_dir / "01-SUMMARY.md").write_text("# Summary\n\nMissing frontmatter.\n", encoding="utf-8")
        (phase_dir / "01-VERIFICATION.md").write_text("# Verification\n\nMissing frontmatter.\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["summary_frontmatter"]["passed"] is False
        assert checks["verification_frontmatter"]["passed"] is False

    def test_review_preflight_verify_work_for_phase(self, gpd_project: Path) -> None:
        planning = gpd_project / ".gpd"
        state = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        state["position"]["status"] = "Phase complete — ready for verification"
        (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

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
        assert checks["required_state"]["passed"] is True

    def test_review_preflight_verify_work_fails_from_planning_state(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "verify-work", "1"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:verify-work"
        assert payload["passed"] is False
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["phase_lookup"]["passed"] is True
        assert checks["phase_summaries"]["passed"] is True
        assert checks["required_state"]["passed"] is False
        assert checks["required_state"]["blocking"] is True
        assert 'found "Planning"' in checks["required_state"]["detail"]

    def test_review_preflight_verify_work_without_subject_uses_current_phase_artifacts(self, gpd_project: Path) -> None:
        planning = gpd_project / ".gpd"
        state = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        state["position"]["current_phase"] = "02"
        state["position"]["status"] = "Phase complete — ready for verification"
        (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "verify-work"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:verify-work"
        assert payload["passed"] is False
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["phase_summaries"]["passed"] is False
        assert 'current phase "02" has no SUMMARY artifacts' in checks["phase_summaries"]["detail"]
        assert checks["required_state"]["passed"] is True

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

    def test_review_preflight_arxiv_submission_accepts_explicit_non_default_paper_directory(
        self,
        gpd_project: Path,
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / "main.tex").unlink()

        submission_dir = gpd_project / "submission"
        submission_dir.mkdir()
        (submission_dir / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\nSubmission manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )
        for artifact_name in ("ARTIFACT-MANIFEST.json", "BIBLIOGRAPHY-AUDIT.json"):
            (submission_dir / artifact_name).write_text(
                (paper_dir / artifact_name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:arxiv-submission"
        assert payload["passed"] is True
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert "submission" in checks["manuscript"]["detail"]
        assert checks["artifact_manifest"]["passed"] is True
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["reproducibility_manifest"]["passed"] is False
        assert checks["reproducibility_manifest"]["blocking"] is False

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
                        "contract_targets_verified": {"satisfied": 3, "total": 3},
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
                        "contract_targets_verified": {"satisfied": 0, "total": 2},
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

    def test_validate_paper_quality_command_blocks_missing_decisive_verdicts(self, gpd_project: Path) -> None:
        quality_path = gpd_project / "paper-quality-decisive-blocked.json"
        quality_path.write_text(
            json.dumps(
                {
                    "title": "Decisive blocker",
                    "journal": "generic",
                    "verification": {
                        "report_passed": {"passed": True},
                        "contract_targets_verified": {"satisfied": 1, "total": 1},
                        "key_result_confidences": ["INDEPENDENTLY CONFIRMED"],
                    },
                    "results": {
                        "uncertainties_present": {"satisfied": 1, "total": 1},
                        "comparison_with_prior_work_present": {"passed": True},
                        "physical_interpretation_present": {"passed": True},
                        "decisive_artifacts_with_explicit_verdicts": {"satisfied": 0, "total": 1},
                        "decisive_artifacts_benchmark_anchored": {"satisfied": 1, "total": 1},
                        "decisive_comparison_failures_scoped": {"passed": True},
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
        blocker_checks = {issue["check"] for issue in payload["blocking_issues"]}
        assert "decisive_artifacts_with_explicit_verdicts" in blocker_checks

    def test_validate_paper_quality_command_from_project_artifacts(self, gpd_project: Path) -> None:
        stage4_dir = Path(__file__).resolve().parent / "fixtures" / "stage4"
        paper_dir = gpd_project / "paper"
        (paper_dir / "main.tex").write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\begin{abstract}Benchmark result with explicit comparison.\\end{abstract}\n"
            "\\section{Introduction}See Fig.~\\ref{fig:benchmark} and \\cite{bench2026}.\n"
            "\\section{Conclusion}Recovered the benchmark within tolerance.\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        (paper_dir / "ARTIFACT-MANIFEST.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "paper_title": "Benchmark Paper",
                    "journal": "prd",
                    "created_at": "2026-03-13T00:00:00+00:00",
                    "artifacts": [],
                }
            ),
            encoding="utf-8",
        )
        (paper_dir / "BIBLIOGRAPHY-AUDIT.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-03-13T00:00:00+00:00",
                    "total_sources": 1,
                    "resolved_sources": 1,
                    "partial_sources": 0,
                    "unverified_sources": 0,
                    "failed_sources": 0,
                    "entries": [],
                }
            ),
            encoding="utf-8",
        )
        tracker_dir = gpd_project / ".gpd" / "paper"
        tracker_dir.mkdir(parents=True, exist_ok=True)
        (tracker_dir / "FIGURE_TRACKER.md").write_text(
            "---\n"
            "figure_registry:\n"
            "  - id: fig-benchmark\n"
            '    label: "Fig. 1"\n'
            "    kind: figure\n"
            "    role: benchmark\n"
            "    path: paper/figures/benchmark.pdf\n"
            "    contract_ids: [claim-benchmark, deliv-figure]\n"
            "    decisive: true\n"
            "    has_units: true\n"
            "    has_uncertainty: true\n"
            "    referenced_in_text: true\n"
            "    caption_self_contained: true\n"
            "    colorblind_safe: true\n"
            "    comparison_sources:\n"
            "      - .gpd/comparisons/benchmark-COMPARISON.md\n"
            "---\n\n"
            "# Figure Tracker\n",
            encoding="utf-8",
        )
        comparison_dir = gpd_project / ".gpd" / "comparisons"
        comparison_dir.mkdir(parents=True, exist_ok=True)
        (comparison_dir / "benchmark-COMPARISON.md").write_text(
            "---\n"
            "comparison_kind: benchmark\n"
            "comparison_sources:\n"
            "  - label: theory\n"
            "    kind: summary\n"
            "    path: .gpd/phases/01-benchmark/01-SUMMARY.md\n"
            "  - label: benchmark\n"
            "    kind: verification\n"
            "    path: .gpd/phases/01-benchmark/01-VERIFICATION.md\n"
            "comparison_verdicts:\n"
            "  - subject_id: claim-benchmark\n"
            "    subject_kind: claim\n"
            "    subject_role: decisive\n"
            "    reference_id: ref-benchmark\n"
            "    comparison_kind: benchmark\n"
            "    metric: relative_error\n"
            '    threshold: "<= 0.01"\n'
            "    verdict: pass\n"
            "    recommended_action: Keep benchmark figure in manuscript\n"
            "---\n\n"
            "# Internal Comparison\n",
            encoding="utf-8",
        )
        phase_dir = gpd_project / ".gpd" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True, exist_ok=True)
        (phase_dir / "01-SUMMARY.md").write_text(
            (stage4_dir / "summary_with_contract_results.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (phase_dir / "01-VERIFICATION.md").write_text(
            (stage4_dir / "verification_with_contract_results.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "paper-quality", "--from-project", str(gpd_project)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["journal"] == "prd"
        assert payload["categories"]["verification"]["checks"]["contract_targets_verified"] > 0
        assert payload["categories"]["results"]["checks"]["comparison_with_prior_work_present"] > 0

    def test_validate_referee_decision_command_accepts_consistent_major_revision(self, gpd_project: Path) -> None:
        _write_review_stage_artifacts(gpd_project)
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
        ledger_path = gpd_project / "review-ledger-consistent.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": "paper/main.tex",
                    "issues": [],
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "referee-decision", str(decision_path), "--strict", "--ledger", str(ledger_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is True
        assert payload["most_positive_allowed_recommendation"] == "major_revision"

    def test_validate_referee_decision_command_blocks_overly_positive_prl_decision(self, gpd_project: Path) -> None:
        _write_review_stage_artifacts(gpd_project)
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

    def test_validate_referee_decision_command_rejects_missing_stage_artifacts(self, gpd_project: Path) -> None:
        decision_path = gpd_project / "referee-decision-missing-artifacts.json"
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
        assert any("listed staged review artifacts do not exist" in reason for reason in payload["reasons"])

    def test_validate_referee_decision_command_rejects_unknown_blocking_issue_ids_when_ledger_given(
        self, gpd_project: Path
    ) -> None:
        _write_review_stage_artifacts(gpd_project)
        decision_path = gpd_project / "referee-decision-ledger-mismatch.json"
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
                    "blocking_issue_ids": ["REF-999"],
                }
            ),
            encoding="utf-8",
        )
        ledger_path = gpd_project / "review-ledger.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": "paper/main.tex",
                    "issues": [
                        {
                            "issue_id": "REF-001",
                            "opened_by_stage": "physics",
                            "severity": "major",
                            "blocking": True,
                            "summary": "Evidence is incomplete.",
                            "required_action": "Add the missing benchmark comparison.",
                            "status": "open",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "--raw",
                "validate",
                "referee-decision",
                str(decision_path),
                "--strict",
                "--ledger",
                str(ledger_path),
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert any("blocking_issue_ids not found in review ledger" in reason for reason in payload["reasons"])

    def test_validate_referee_decision_command_rejects_dual_stdin_inputs(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "referee-decision", "-", "--ledger", "-"],
            input="{}\n",
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert "Cannot read both referee-decision and review-ledger from stdin" in payload["error"]

    def test_validate_referee_decision_command_rejects_omitted_unresolved_blocking_ledger_issues(
        self, gpd_project: Path
    ) -> None:
        _write_review_stage_artifacts(gpd_project)
        decision_path = gpd_project / "referee-decision-omits-blocker.json"
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
                }
            ),
            encoding="utf-8",
        )
        ledger_path = gpd_project / "review-ledger-open-blocker.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": "paper/main.tex",
                    "issues": [
                        {
                            "issue_id": "REF-001",
                            "opened_by_stage": "physics",
                            "severity": "major",
                            "blocking": True,
                            "summary": "Evidence is incomplete.",
                            "required_action": "Add the missing benchmark comparison.",
                            "status": "open",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "--raw",
                "validate",
                "referee-decision",
                str(decision_path),
                "--strict",
                "--ledger",
                str(ledger_path),
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert any(
            "unresolved blocking review-ledger issues missing from blocking_issue_ids" in reason
            for reason in payload["reasons"]
        )

    def test_validate_paper_quality_command_reports_shape_errors_without_traceback(self, gpd_project: Path) -> None:
        input_path = gpd_project / "paper-quality-invalid.json"
        input_path.write_text(
            json.dumps(
                {
                    "title": "Bad Input",
                    "journal": "prd",
                    "equations": "broken",
                    "figures": {},
                    "citations": {},
                    "conventions": {},
                    "verification": {},
                    "completeness": {},
                    "results": {},
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "paper-quality", str(input_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert "paper-quality input.equations must be an object, not str" in payload["error"]

    def test_validate_paper_quality_command_rejects_unknown_fields_without_traceback(self, gpd_project: Path) -> None:
        input_path = gpd_project / "paper-quality-unknown-field.json"
        input_path.write_text(
            json.dumps(
                {
                    "title": "Bad Input",
                    "journal": "prd",
                    "equations": {},
                    "figures": {},
                    "citations": {},
                    "conventions": {},
                    "verification": {"report_exists": {"passed": True}},
                    "completeness": {},
                    "results": {},
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "paper-quality", str(input_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert "paper-quality input.verification.report_exists: Extra inputs are not permitted" in payload["error"]
        assert "templates/paper/paper-quality-input-schema.md" in payload["error"]

    def test_validate_referee_decision_command_reports_shape_errors_without_traceback(self, gpd_project: Path) -> None:
        decision_path = gpd_project / "referee-decision-invalid.json"
        decision_path.write_text(
            json.dumps(
                {
                    "manuscript_path": "paper/main.tex",
                    "target_journal": "jhep",
                    "final_recommendation": "major_revision",
                    "stage_artifacts": "not-a-list",
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "referee-decision", str(decision_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert "referee-decision.stage_artifacts must be an array, not str" in payload["error"]

    def test_validate_review_ledger_command_accepts_valid_ledger(self, gpd_project: Path) -> None:
        ledger_path = gpd_project / "review-ledger.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": "paper/main.tex",
                    "issues": [
                        {
                            "issue_id": "REF-001",
                            "opened_by_stage": "physics",
                            "severity": "major",
                            "blocking": True,
                            "claim_ids": ["CLM-001"],
                            "summary": "Evidence is incomplete.",
                            "required_action": "Add the missing benchmark comparison.",
                            "status": "open",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-ledger", str(ledger_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["issues"][0]["issue_id"] == "REF-001"

    def test_validate_review_ledger_command_reports_shape_errors_without_traceback(self, gpd_project: Path) -> None:
        ledger_path = gpd_project / "review-ledger-invalid.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": "paper/main.tex",
                    "issues": "not-a-list",
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-ledger", str(ledger_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert "review-ledger.issues must be an array, not str" in payload["error"]

    def test_validate_plan_contract_command_accepts_valid_plan(self, gpd_project: Path) -> None:
        phase_dir = gpd_project / ".gpd" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True, exist_ok=True)
        plan_path = phase_dir / "01-01-PLAN.md"
        plan_path.write_text(
            (FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "plan-contract", str(plan_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is True

    def test_validate_summary_contract_command_rejects_unknown_contract_ids(self, gpd_project: Path) -> None:
        phase_dir = gpd_project / ".gpd" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True, exist_ok=True)
        (phase_dir / "01-01-PLAN.md").write_text(
            (FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        summary_path = phase_dir / "01-SUMMARY.md"
        summary_path.write_text(
            (FIXTURES_DIR.parent / "stage4" / "summary_with_contract_results.md")
            .read_text(encoding="utf-8")
            .replace("claim-benchmark:", "claim-unknown:", 1),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "summary-contract", str(summary_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert any("Unknown claim contract_results entry: claim-unknown" in error for error in payload["errors"])

    def test_validate_summary_contract_command_reports_unresolved_plan_contract_ref(self, gpd_project: Path) -> None:
        phase_dir = gpd_project / ".gpd" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True, exist_ok=True)
        summary_path = phase_dir / "01-SUMMARY.md"
        summary_path.write_text(
            (FIXTURES_DIR.parent / "stage4" / "summary_with_contract_results.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "summary-contract", str(summary_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert "plan_contract_ref: could not resolve matching plan contract" in payload["errors"]

    def test_validate_verification_contract_command_requires_contract_results(self, gpd_project: Path) -> None:
        phase_dir = gpd_project / ".gpd" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True, exist_ok=True)
        (phase_dir / "01-01-PLAN.md").write_text(
            (FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        verification_path = phase_dir / "01-VERIFICATION.md"
        verification_path.write_text(
            "---\n"
            "phase: 01-benchmark\n"
            "verified: 2026-03-13T00:00:00Z\n"
            "status: passed\n"
            "score: 1/1 contract targets verified\n"
            "plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract\n"
            "---\n\n"
            "# Verification\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "verification-contract", str(verification_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert "contract_results: required for contract-backed plan" in payload["errors"]

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

    def test_validate_reproducibility_manifest_reports_shape_errors_without_traceback(self, gpd_project: Path) -> None:
        manifest_path = gpd_project / "reproducibility-invalid.json"
        manifest_path.write_text(
            json.dumps({"paper_title": "Bad Input", "environment": []}),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "reproducibility-manifest", str(manifest_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert any(issue["field"] == "environment" and "object" in issue["message"].lower() for issue in payload["issues"])

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


def test_cli_import_survives_runtime_help_lookup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import gpd as gpd_package
    import gpd.adapters as adapters_module

    def _raise_runtime_catalog() -> list[str]:
        raise RuntimeError("catalog offline")

    original_cli = sys.modules.get("gpd.cli")
    monkeypatch.setattr(adapters_module, "list_runtimes", _raise_runtime_catalog)
    sys.modules.pop("gpd.cli", None)

    try:
        reloaded = importlib.import_module("gpd.cli")
        assert reloaded._runtime_override_help() == "Runtime name override"
    finally:
        if original_cli is not None:
            sys.modules["gpd.cli"] = original_cli
            gpd_package.cli = original_cli


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
