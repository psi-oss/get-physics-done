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
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import gpd.cli as cli_module
from gpd.adapters.runtime_catalog import iter_runtime_descriptors, list_runtime_names
from gpd.cli import app
from gpd.core.recent_projects import record_recent_project
from gpd.core.reproducibility import compute_sha256
from gpd.core.state import StateUpdateResult, default_state_dict, generate_state_markdown
from tests.manuscript_test_support import (
    CANONICAL_MANUSCRIPT_STEM,
    write_proof_review_package,
)
from tests.manuscript_test_support import (
    manuscript_path as canonical_manuscript_path,
)
from tests.manuscript_test_support import (
    manuscript_pdf_path as canonical_manuscript_pdf_path,
)
from tests.manuscript_test_support import (
    manuscript_relpath as canonical_manuscript_relpath,
)


class _StableCliRunner(CliRunner):
    def invoke(self, *args, **kwargs):
        kwargs.setdefault("color", False)
        return super().invoke(*args, **kwargs)


runner = _StableCliRunner()
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _normalize_cli_output(text: str) -> str:
    return " ".join(_ANSI_ESCAPE_RE.sub("", text).split())


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "stage0"
_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()
_PRIMARY_RAW_RUNTIME_DESCRIPTOR = _RUNTIME_DESCRIPTORS[0]
_CANONICAL_MANUSCRIPT_REL = canonical_manuscript_relpath()
_CANONICAL_MANUSCRIPT_BASENAME = f"{CANONICAL_MANUSCRIPT_STEM}.tex"
_CANONICAL_MANUSCRIPT_PDF_BASENAME = f"{CANONICAL_MANUSCRIPT_STEM}.pdf"
_CANONICAL_MARKDOWN_BASENAME = f"{CANONICAL_MANUSCRIPT_STEM}.md"
_ALIASABLE_RUNTIME_DESCRIPTOR = next(
    descriptor
    for descriptor in _RUNTIME_DESCRIPTORS
    if any(alias != descriptor.runtime_name for alias in descriptor.selection_aliases)
)
_DOLLAR_COMMAND_DESCRIPTOR = next(
    descriptor for descriptor in _RUNTIME_DESCRIPTORS if descriptor.validated_command_surface == "public_runtime_dollar_command"
)
_SLASH_COMMAND_DESCRIPTOR = next(
    descriptor
    for descriptor in _RUNTIME_DESCRIPTORS
    if descriptor.validated_command_surface == "public_runtime_slash_command"
    and descriptor.runtime_name != _DOLLAR_COMMAND_DESCRIPTOR.runtime_name
)


@pytest.fixture()
def dollar_command_prefix(monkeypatch: pytest.MonkeyPatch) -> str:
    """Force the CLI preflight helpers to resolve the dollar-command runtime."""
    monkeypatch.setattr("gpd.cli.detect_runtime_for_gpd_use", lambda cwd=None: _DOLLAR_COMMAND_DESCRIPTOR.runtime_name)
    return _DOLLAR_COMMAND_DESCRIPTOR.public_command_surface_prefix


@pytest.fixture()
def slash_command_prefix(monkeypatch: pytest.MonkeyPatch) -> str:
    """Force the CLI preflight helpers to resolve the slash-command runtime."""
    monkeypatch.setattr("gpd.cli.detect_runtime_for_gpd_use", lambda cwd=None: _SLASH_COMMAND_DESCRIPTOR.runtime_name)
    return _SLASH_COMMAND_DESCRIPTOR.public_command_surface_prefix


@pytest.fixture()
def gpd_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project with all files commands might touch."""
    planning = tmp_path / "GPD"
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
    (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    (planning / "PROJECT.md").write_text("# Test Project\n\n## Core Research Question\nWhat is physics?\n", encoding="utf-8")
    (planning / "REQUIREMENTS.md").write_text("# Requirements\n\n- [ ] **REQ-01**: Do the thing\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## Phase 1: Test Phase\nGoal: Test\nRequirements: REQ-01\n"
        "\n## Phase 2: Phase Two\nGoal: More tests\nRequirements: REQ-01\n", encoding="utf-8"
    )
    (planning / "CONVENTIONS.md").write_text("# Conventions\n\n- Metric: (-,+,+,+)\n- Coordinates: Cartesian\n", encoding="utf-8")
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
        ), encoding="utf-8"
    )

    # Phase directories
    p1 = planning / "phases" / "01-test-phase"
    p1.mkdir(parents=True)
    (p1 / "README.md").write_text("# Phase 1: Test Phase\n", encoding="utf-8")
    (p1 / "01-SUMMARY.md").write_text(
        "---\n"
        "phase: 01-test-phase\n"
        "plan: 01\n"
        "depth: full\n"
        "provides: [executed plan summary]\n"
        "completed: 2026-03-10\n"
        "---\n\n"
        "# Summary\n\nExecuted plan summary.\n", encoding="utf-8"
    )
    (p1 / "01-VERIFICATION.md").write_text(
        "---\n"
        "phase: 01-test-phase\n"
        "verified: 2026-03-10T00:00:00Z\n"
        "status: passed\n"
        "score: 1/1 checks passed\n"
        "---\n\n"
        "# Verification\n\nVerified result.\n", encoding="utf-8"
    )
    p2 = planning / "phases" / "02-phase-two"
    p2.mkdir(parents=True)
    (p2 / "README.md").write_text("# Phase 2: Phase Two\n", encoding="utf-8")

    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    manuscript = canonical_manuscript_path(tmp_path)
    manuscript.write_text(
        "\\documentclass{article}\n\\begin{document}\nTest manuscript.\n\\end{document}\n",
        encoding="utf-8",
    )
    compiled_manuscript = canonical_manuscript_pdf_path(tmp_path)
    compiled_manuscript.write_bytes(b"%PDF-1.4\n% fake arxiv submission pdf\n")
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Curvature Flow Bounds",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Introduction", "content": "Test manuscript."}],
            }
        ),
        encoding="utf-8",
    )
    (paper_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Test",
                "journal": "prl",
                "created_at": "2026-03-10T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "manuscript",
                        "category": "tex",
                        "path": _CANONICAL_MANUSCRIPT_BASENAME,
                        "sha256": compute_sha256(manuscript),
                        "produced_by": "tests.test_cli_commands",
                        "sources": [],
                        "metadata": {"role": "manuscript"},
                    },
                    {
                        "artifact_id": "compiled-manuscript",
                        "category": "pdf",
                        "path": _CANONICAL_MANUSCRIPT_PDF_BASENAME,
                        "sha256": compute_sha256(compiled_manuscript),
                        "produced_by": "tests.test_cli_commands",
                        "sources": [{"path": _CANONICAL_MANUSCRIPT_BASENAME, "role": "compiled_from"}],
                        "metadata": {"role": "compiled_manuscript"},
                    },
                ],
            }
        ),
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
    (reports_dir / "referee-report.md").write_text("# Referee Report\n\n1. Clarify the derivation.\n", encoding="utf-8")

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


def _manuscript_entrypoint_path(
    project_root: Path,
    *,
    root_name: str = "paper",
    suffix: str = ".tex",
) -> Path:
    return project_root / root_name / f"{CANONICAL_MANUSCRIPT_STEM}{suffix}"


def _manuscript_entrypoint_relpath(
    *,
    root_name: str = "paper",
    suffix: str = ".tex",
) -> str:
    return f"{root_name}/{CANONICAL_MANUSCRIPT_STEM}{suffix}"


def _write_review_stage_artifacts(
    project_root: Path,
    artifact_names: tuple[str, ...] | None = None,
    *,
    manuscript_path: str = _CANONICAL_MANUSCRIPT_REL,
    proof_bearing: bool = False,
    write_proof_redteam: bool = False,
    proof_redteam_status: str = "passed",
) -> None:
    review_dir = project_root / "GPD" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    manuscript_abspath = (project_root / manuscript_path).resolve(strict=False)
    manuscript_sha256 = compute_sha256(manuscript_abspath) if manuscript_abspath.exists() else "a" * 64
    written_claim_indexes: set[str] = set()
    for artifact_name in artifact_names or (
        "STAGE-reader.json",
        "STAGE-literature.json",
        "STAGE-math.json",
        "STAGE-physics.json",
        "STAGE-interestingness.json",
    ):
        artifact_path = review_dir / artifact_name
        if not artifact_name.startswith("STAGE-") or not artifact_name.endswith(".json"):
            artifact_path.write_text("{}", encoding="utf-8")
            continue

        artifact_stem = artifact_name[len("STAGE-") : -len(".json")]
        if "-R" in artifact_stem:
            stage_id, round_text = artifact_stem.rsplit("-R", 1)
            if not round_text.isdigit():
                artifact_path.write_text("{}", encoding="utf-8")
                continue
            round_number = int(round_text)
            round_suffix = f"-R{round_number}"
        else:
            stage_id = artifact_stem
            round_number = 1
            round_suffix = ""

        if stage_id not in {"reader", "literature", "math", "physics", "interestingness"}:
            artifact_path.write_text("{}", encoding="utf-8")
            continue

        if round_suffix not in written_claim_indexes:
            (review_dir / f"CLAIMS{round_suffix}.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "manuscript_path": manuscript_path,
                        "manuscript_sha256": manuscript_sha256,
                        "claims": [
                            {
                                "claim_id": "CLM-001",
                                "claim_type": "main_result",
                                "text": (
                                    "For every r_0 > 0, the orbit intersects the target annulus."
                                    if proof_bearing
                                    else "The manuscript makes a test claim."
                                ),
                                "artifact_path": manuscript_path,
                                "section": "Conclusion",
                                "equation_refs": [],
                                "figure_refs": [],
                                "supporting_artifacts": [],
                                "theorem_assumptions": ["chi > 0"] if proof_bearing else [],
                                "theorem_parameters": ["r_0"] if proof_bearing else [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            written_claim_indexes.add(round_suffix)

        artifact_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": round_number,
                    "stage_id": stage_id,
                    "stage_kind": stage_id,
                    "manuscript_path": manuscript_path,
                    "manuscript_sha256": manuscript_sha256,
                    "claims_reviewed": ["CLM-001"],
                    "summary": f"{stage_id} review summary.",
                    "strengths": ["Structured review artifact emitted."],
                    "findings": [
                        {
                            "issue_id": "REF-001",
                            "claim_ids": ["CLM-001"],
                            "severity": "minor",
                            "summary": "Minor concern.",
                            "rationale": "",
                            "evidence_refs": [f"{manuscript_path}#Conclusion"],
                            "manuscript_locations": [],
                            "support_status": "unclear",
                            "blocking": False,
                            "required_action": "",
                        }
                    ],
                    "proof_audits": (
                        [
                            {
                                "claim_id": "CLM-001",
                                "theorem_assumptions_checked": ["chi > 0"],
                                "theorem_parameters_checked": ["r_0"],
                                "proof_locations": [f"{manuscript_path}:1"],
                                "uncovered_assumptions": [],
                                "uncovered_parameters": [],
                                "coverage_gaps": [],
                                "alignment_status": "aligned",
                                "notes": "Reviewed against theorem inventory.",
                            }
                        ]
                        if proof_bearing and stage_id == "math"
                        else []
                    ),
                    "confidence": "medium",
                    "recommendation_ceiling": "major_revision",
                }
            ),
            encoding="utf-8",
        )

    if write_proof_redteam:
        for round_suffix in written_claim_indexes:
            (review_dir / f"PROOF-REDTEAM{round_suffix}.md").write_text(
                (
                    "---\n"
                    f"status: {proof_redteam_status}\n"
                    "reviewer: gpd-check-proof\n"
                    "claim_ids:\n"
                    "  - CLM-001\n"
                    "proof_artifact_paths:\n"
                    f"  - {manuscript_path}\n"
                    f"manuscript_path: {manuscript_path}\n"
                    f"manuscript_sha256: {manuscript_sha256}\n"
                    f"round: {1 if not round_suffix else int(round_suffix.removeprefix('-R'))}\n"
                    "missing_parameter_symbols: []\n"
                    "missing_hypothesis_ids: []\n"
                    "coverage_gaps: []\n"
                    "scope_status: matched\n"
                    "quantifier_status: matched\n"
                    "counterexample_status: none_found\n"
                    "---\n\n"
                    "# Proof Redteam\n"
                    "## Proof Inventory\n"
                    "- Exact claim / theorem text: For every r_0 > 0, the orbit intersects the target annulus.\n"
                    "- Claim / theorem target: Annulus intersection for every target radius.\n"
                    "- Named parameters:\n"
                    "  - `r_0`: target radius\n"
                    "- Hypotheses:\n"
                    "  - `H1`: chi > 0\n"
                    "- Quantifier / domain obligations:\n"
                    "  - for every r_0 > 0\n"
                    "- Conclusion clauses:\n"
                    "  - annulus intersection holds\n"
                    "## Coverage Ledger\n"
                    "### Named-Parameter Coverage\n"
                    "| Parameter | Role / Domain | Proof Location | Status | Notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| `r_0` | target radius | {manuscript_path}:1 | covered | Tracked explicitly. |\n"
                    "### Hypothesis Coverage\n"
                    "| Hypothesis | Proof Location | Status | Notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| `H1` | {manuscript_path}:1 | covered | Used in the proof. |\n"
                    "### Quantifier / Domain Coverage\n"
                    "| Obligation | Proof Location | Status | Notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| `for every r_0 > 0` | {manuscript_path}:1 | covered | No narrowing introduced. |\n"
                    "### Conclusion-Clause Coverage\n"
                    "| Clause | Proof Location | Status | Notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| annulus intersection holds | {manuscript_path}:1 | covered | Final theorem statement matches. |\n"
                    "## Adversarial Probe\n"
                    "- Probe type: dropped-parameter test\n"
                    "- Result: The proof still references r_0, so the full claim survives.\n"
                    "## Verdict\n"
                    "- Scope status: `matched`\n"
                    "- Quantifier status: `matched`\n"
                    "- Counterexample status: `none_found`\n"
                    "- Blocking gaps:\n"
                    "  - None.\n"
                    "## Required Follow-Up\n"
                    "- None.\n"
                ),
                encoding="utf-8",
            )


def _write_legacy_publication_artifacts(project_root: Path, artifact_names: tuple[str, ...]) -> None:
    """Mirror publication review artifacts into the removed legacy internal location."""
    legacy_dir = project_root / "GPD" / "paper"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    paper_dir = project_root / "paper"
    for artifact_name in artifact_names:
        source = paper_dir / artifact_name
        (legacy_dir / artifact_name).write_bytes(source.read_bytes())


def _write_secondary_manuscript_root(project_root: Path, *, root_name: str = "manuscript") -> Path:
    manuscript_dir = project_root / root_name
    manuscript_dir.mkdir(parents=True, exist_ok=True)
    manuscript = manuscript_dir / _CANONICAL_MANUSCRIPT_BASENAME
    manuscript.write_text(
        "\\documentclass{article}\n\\begin{document}\nSecondary manuscript.\n\\end{document}\n",
        encoding="utf-8",
    )
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-03-10T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": f"manuscript-{root_name}",
                        "category": "tex",
                        "path": _CANONICAL_MANUSCRIPT_BASENAME,
                        "sha256": compute_sha256(manuscript),
                        "produced_by": "tests.test_cli_commands",
                        "sources": [],
                        "metadata": {"role": "manuscript"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manuscript


def _write_publication_review_outcome(
    project_root: Path,
    *,
    final_recommendation: str = "accept",
    round_number: int = 1,
    blocking_issue_ids: list[str] | None = None,
    manuscript_path: str = _CANONICAL_MANUSCRIPT_REL,
    proof_bearing: bool = False,
    write_proof_redteam: bool = False,
    proof_redteam_status: str = "passed",
) -> None:
    review_dir = project_root / "GPD" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    round_suffix = "" if round_number <= 1 else f"-R{round_number}"
    _write_review_stage_artifacts(
        project_root,
        artifact_names=(
            f"STAGE-reader{round_suffix}.json",
            f"STAGE-literature{round_suffix}.json",
            f"STAGE-math{round_suffix}.json",
            f"STAGE-physics{round_suffix}.json",
            f"STAGE-interestingness{round_suffix}.json",
        ),
        manuscript_path=manuscript_path,
        proof_bearing=proof_bearing,
        write_proof_redteam=write_proof_redteam,
        proof_redteam_status=proof_redteam_status,
    )
    unresolved_blocking_issue_ids = blocking_issue_ids or []
    (review_dir / f"REVIEW-LEDGER{round_suffix}.json").write_text(
        json.dumps(
            {
                "version": 1,
                "round": round_number,
                "manuscript_path": manuscript_path,
                "issues": [
                    {
                        "issue_id": issue_id,
                        "opened_by_stage": "reader",
                        "severity": "major",
                        "blocking": True,
                        "claim_ids": ["CLM-001"],
                        "summary": "Blocking review issue.",
                        "rationale": "",
                        "evidence_refs": [],
                        "required_action": "Revise the manuscript.",
                        "status": "open",
                    }
                    for issue_id in unresolved_blocking_issue_ids
                ],
            }
        ),
        encoding="utf-8",
    )
    (review_dir / f"REFEREE-DECISION{round_suffix}.json").write_text(
        json.dumps(
            {
                "manuscript_path": manuscript_path,
                "target_journal": "jhep",
                "final_recommendation": final_recommendation,
                "final_confidence": "medium",
                "stage_artifacts": [
                    f"GPD/review/STAGE-reader{round_suffix}.json",
                    f"GPD/review/STAGE-literature{round_suffix}.json",
                    f"GPD/review/STAGE-math{round_suffix}.json",
                    f"GPD/review/STAGE-physics{round_suffix}.json",
                    f"GPD/review/STAGE-interestingness{round_suffix}.json",
                ],
                "central_claims_supported": True,
                "claim_scope_proportionate_to_evidence": True,
                "physical_assumptions_justified": True,
                "unsupported_claims_are_central": False,
                "reframing_possible_without_new_results": True,
                "proof_audit_coverage_complete": True,
                "theorem_proof_alignment_adequate": True,
                "mathematical_correctness": "adequate",
                "novelty": "adequate",
                "significance": "adequate",
                "venue_fit": "adequate",
                "literature_positioning": "adequate",
                "unresolved_major_issues": len(unresolved_blocking_issue_ids),
                "unresolved_minor_issues": 0,
                "blocking_issue_ids": unresolved_blocking_issue_ids,
            }
        ),
        encoding="utf-8",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Convention commands — the original bug class
# ═══════════════════════════════════════════════════════════════════════════


class TestConventionCommands:
    def test_set_persists(self, gpd_project: Path) -> None:
        _invoke("convention", "set", "fourier_convention", "physics")
        state = json.loads((gpd_project / "GPD" / "state.json").read_text())
        assert state["convention_lock"]["fourier_convention"] == "physics"


# ═══════════════════════════════════════════════════════════════════════════
# State commands
# ═══════════════════════════════════════════════════════════════════════════


class TestStateCommands:
    def test_validate(self) -> None:
        # May exit 1 if issues found, but must not crash
        result = runner.invoke(app, ["state", "validate"], catch_exceptions=False)
        assert result.exit_code in (0, 1)

    def test_set_project_contract(self, gpd_project: Path) -> None:
        contract_path = gpd_project / "contract.json"
        contract_path.write_text(
            (FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        _invoke("state", "set-project-contract", str(contract_path))
        state = json.loads((gpd_project / "GPD" / "state.json").read_text(encoding="utf-8"))
        assert state["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"

    def test_set_project_contract_raw_surfaces_warnings_on_success(self, gpd_project: Path) -> None:
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["references"][0]["must_surface"] = False
        contract_path = gpd_project / "warning-contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--cwd", str(gpd_project), "--raw", "state", "set-project-contract", str(contract_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["updated"] is True
        assert any("references must include at least one must_surface=true anchor" in warning for warning in payload["warnings"])

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

    def test_set_project_contract_rejects_singleton_list_drift_at_write_boundary(self, gpd_project: Path) -> None:
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["context_intake"]["must_read_refs"] = "ref-benchmark"
        contract_path = gpd_project / "invalid-contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "state", "set-project-contract", str(contract_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["updated"] is False
        assert (
            payload["reason"]
            == "Invalid project contract schema: context_intake.must_read_refs must be a list, not str"
        )
        assert payload["warnings"] == []
        assert payload["schema_reference"] == "templates/project-contract-schema.md"
        state = json.loads((gpd_project / "GPD" / "state.json").read_text(encoding="utf-8"))
        assert state["project_contract"] is None

    def test_set_project_contract_exits_nonzero_on_hard_backend_rejection(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        contract_path = gpd_project / "contract.json"
        contract_path.write_text(
            (FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        def _reject_contract(cwd: Path, contract_data: object) -> StateUpdateResult:
            return StateUpdateResult(
                updated=False,
                reason="Backend rejected project contract: missing required anchor",
            )

        monkeypatch.setattr("gpd.core.state.state_set_project_contract", _reject_contract)

        result = runner.invoke(
            app,
            ["--cwd", str(gpd_project), "--raw", "state", "set-project-contract", str(contract_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["updated"] is False
        assert payload["reason"] == "Backend rejected project contract: missing required anchor"

    def test_set_project_contract_keeps_benign_noop_exit_zero(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        contract_path = gpd_project / "contract.json"
        contract_path.write_text(
            (FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        def _noop_contract(cwd: Path, contract_data: object) -> StateUpdateResult:
            return StateUpdateResult(
                updated=False,
                unchanged=True,
                reason="Project contract already matches requested value",
            )

        monkeypatch.setattr("gpd.core.state.state_set_project_contract", _noop_contract)

        result = runner.invoke(
            app,
            ["--cwd", str(gpd_project), "--raw", "state", "set-project-contract", str(contract_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["updated"] is False
        assert payload["reason"] == "Project contract already matches requested value"

    def test_set_project_contract_raw_rejects_schema_valid_contract_with_approval_blockers(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["context_intake"] = {
            "must_read_refs": [],
            "must_include_prior_outputs": [],
            "user_asserted_anchors": [],
            "known_good_baselines": [],
            "context_gaps": ["Need a concrete must-surface anchor before approval."],
            "crucial_inputs": [],
        }
        contract["references"][0]["role"] = "background"
        contract["references"][0]["must_surface"] = False
        contract_path = gpd_project / "draft-contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        def _unexpected_backend_call(*args, **kwargs) -> object:
            raise AssertionError("backend persistence must not run after approved-mode preflight failure")

        monkeypatch.setattr("gpd.core.state.state_set_project_contract", _unexpected_backend_call)

        result = runner.invoke(
            app,
            ["--cwd", str(gpd_project), "--raw", "state", "set-project-contract", str(contract_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert payload["mode"] == "approved"
        assert any("approved project contract requires" in error for error in payload["errors"])
        state = json.loads((gpd_project / "GPD" / "state.json").read_text(encoding="utf-8"))
        assert state["project_contract"] is None


# ═══════════════════════════════════════════════════════════════════════════
# Regression check commands
# ═══════════════════════════════════════════════════════════════════════════


class TestRegressionCheckCommands:
    def test_default_scope(self, gpd_project: Path) -> None:
        _invoke("regression-check")


class TestInitCommands:
    def test_progress_include_rejects_unknown_values(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "init", "progress", "--include", "state, bogus"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["error"] == (
            "Unknown --include value(s) for gpd init progress: bogus. "
            "Allowed values: config, project, roadmap, state."
        )

    def test_init_resume_resolves_ancestor_project_root_from_nested_workspace(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        nested = gpd_project / "workspace" / "notes"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(nested), "init", "resume"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["planning_exists"] is True
        assert payload["project_exists"] is True
        assert payload["roadmap_exists"] is True
        assert payload["state_exists"] is True

    def test_init_progress_resolves_ancestor_project_root_from_nested_workspace(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        nested = gpd_project / "workspace" / "notes"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(nested), "init", "progress"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["project_exists"] is True
        assert payload["roadmap_exists"] is True
        assert payload["state_exists"] is True

    def test_init_progress_can_skip_recent_project_reentry_for_projectless_config_bootstrap(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workspace = tmp_path / "workspace"
        candidate = tmp_path / "recoverable-project"
        data_root = tmp_path / "data"

        (workspace / "GPD" / "phases").mkdir(parents=True)
        (workspace / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "autonomy": "balanced",
                    "review_cadence": "adaptive",
                    "research_mode": "balanced",
                }
            ),
            encoding="utf-8",
        )

        gpd_dir = candidate / "GPD"
        gpd_dir.mkdir(parents=True)
        (gpd_dir / "STATE.md").write_text("# Research State\n", encoding="utf-8")
        (gpd_dir / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (gpd_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
        resume_file = gpd_dir / "phases" / "01" / ".continue-here.md"
        resume_file.parent.mkdir(parents=True, exist_ok=True)
        resume_file.write_text("resume\n", encoding="utf-8")
        monkeypatch.setenv("GPD_DATA_DIR", str(data_root))
        record_recent_project(
            candidate,
            session_data={
                "last_date": "2026-03-29T12:00:00+00:00",
                "stopped_at": "Phase 01",
                "resume_file": "GPD/phases/01/.continue-here.md",
            },
            store_root=data_root,
        )

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(workspace), "init", "progress", "--include", "config", "--no-project-reentry"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["workspace_root"] == str(workspace.resolve())
        assert payload["project_root"] == str(workspace.resolve())
        assert payload["project_root_source"] == "workspace"
        assert payload["project_root_auto_selected"] is False
        assert payload["config_content"] is not None
        assert payload["project_exists"] is False
        assert "project_reentry_mode" not in payload
        assert "project_reentry_candidates" not in payload
        assert "project_reentry_selected_candidate" not in payload

    def test_plan_phase_surfaces_artifact_derived_reference_context(self, gpd_project: Path) -> None:
        literature_dir = gpd_project / "GPD" / "literature"
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
        map_dir = gpd_project / "GPD" / "research-map"
        map_dir.mkdir(parents=True)
        (map_dir / "REFERENCES.md").write_text(
            """# Reference and Anchor Map

## Active Anchor Registry

| Anchor | Type | Source / Locator | What It Constrains | Required Action | Carry Forward To |
| ------ | ---- | ---------------- | ------------------ | --------------- | ---------------- |
| prior-baseline | prior artifact | `GPD/phases/01-test-phase/01-SUMMARY.md` | Baseline summary for later comparisons | use | planning/execution |
""",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["--raw", "init", "plan-phase", "1"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)

        assert payload["project_contract"] is None
        assert payload["derived_active_reference_count"] >= 2
        assert "Benchmark Ref 2024" in payload["active_reference_context"]
        assert "GPD/phases/01-test-phase/01-SUMMARY.md" in payload["active_reference_context"]
        assert "GPD/phases/01-test-phase/01-SUMMARY.md" in payload["effective_reference_intake"]["must_include_prior_outputs"]

    def test_new_milestone_surfaces_contract_and_effective_reference_context(self, gpd_project: Path) -> None:
        (gpd_project / "GPD" / "ROADMAP.md").write_text(
            "# Roadmap\n\n## Milestone v1.1: Scaling Study\n",
            encoding="utf-8",
        )
        state = json.loads((gpd_project / "GPD" / "state.json").read_text(encoding="utf-8"))
        state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        (gpd_project / "GPD" / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

        literature_dir = gpd_project / "GPD" / "literature"
        literature_dir.mkdir(parents=True)
        (literature_dir / "benchmark-REVIEW.md").write_text(
            "## Active Anchor Registry\n\n"
            "| Anchor | Type | Why It Matters | Required Action | Downstream Use |\n"
            "| ------ | ---- | -------------- | --------------- | -------------- |\n"
            "| Benchmark Ref 2024 | benchmark | Published benchmark curve for the decisive observable | read/compare/cite | planning/execution |\n",
            encoding="utf-8",
        )
        map_dir = gpd_project / "GPD" / "research-map"
        map_dir.mkdir(parents=True)
        (map_dir / "CONCERNS.md").write_text(
            "## Prior Outputs\n\n"
            "- `GPD/phases/01-test-phase/01-SUMMARY.md`\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["--raw", "init", "new-milestone"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)

        assert payload["current_milestone"] == "v1.1"
        assert payload["project_contract"]["references"][0]["id"] == "ref-benchmark"
        assert "Benchmark Ref 2024" in payload["active_reference_context"]
        assert "GPD/phases/01-test-phase/01-SUMMARY.md" in payload["effective_reference_intake"]["must_include_prior_outputs"]
        assert "GPD/research-map/CONCERNS.md" in payload["research_map_reference_files"]

    def test_new_milestone_surfaces_contract_load_and_validation_gates(self, gpd_project: Path) -> None:
        (gpd_project / "GPD" / "ROADMAP.md").write_text(
            "# Roadmap\n\n## Milestone v1.1: Scaling Study\n",
            encoding="utf-8",
        )
        state = json.loads((gpd_project / "GPD" / "state.json").read_text(encoding="utf-8"))
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["context_intake"] = {
            "must_read_refs": [],
            "must_include_prior_outputs": [],
            "user_asserted_anchors": [],
            "known_good_baselines": [],
            "context_gaps": ["Need a concrete must-surface anchor before approval."],
            "crucial_inputs": [],
        }
        contract["references"][0]["role"] = "background"
        contract["references"][0]["must_surface"] = False
        state["project_contract"] = contract
        (gpd_project / "GPD" / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

        result = runner.invoke(app, ["--raw", "init", "new-milestone"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)

        assert payload["project_contract"] is not None
        assert payload["project_contract"]["references"][0]["must_surface"] is False
        assert payload["contract_intake"]["context_gaps"] == ["Need a concrete must-surface anchor before approval."]
        assert payload["project_contract_load_info"]["status"] == "loaded_with_approval_blockers"
        assert payload["project_contract_validation"]["valid"] is False
        assert "project_contract_load_info" in payload
        assert "project_contract_validation" in payload

    def test_phase_op_surfaces_contract_load_and_validation_gates(self, gpd_project: Path) -> None:
        state = json.loads((gpd_project / "GPD" / "state.json").read_text(encoding="utf-8"))
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["context_intake"] = {
            "must_read_refs": [],
            "must_include_prior_outputs": [],
            "user_asserted_anchors": [],
            "known_good_baselines": [],
            "context_gaps": ["Need a concrete must-surface anchor before approval."],
            "crucial_inputs": [],
        }
        contract["references"][0]["role"] = "background"
        contract["references"][0]["must_surface"] = False
        state["project_contract"] = contract
        (gpd_project / "GPD" / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

        result = runner.invoke(app, ["--raw", "init", "phase-op"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)

        assert payload["project_contract"] is not None
        assert payload["project_contract"]["references"][0]["must_surface"] is False
        assert payload["contract_intake"]["context_gaps"] == ["Need a concrete must-surface anchor before approval."]
        assert payload["project_contract_load_info"]["status"] == "loaded_with_approval_blockers"
        assert payload["project_contract_validation"]["valid"] is False
        assert "project_contract_load_info" in payload
        assert "project_contract_validation" in payload


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
        assert "${PAPER_DIR}/ARTIFACT-MANIFEST.json" in payload["review_contract"]["required_outputs"]
        assert "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json" in payload["review_contract"]["required_outputs"]
        assert "${PAPER_DIR}/reproducibility-manifest.json" in payload["review_contract"]["required_outputs"]
        assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in payload["review_contract"]["required_outputs"]
        assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in payload["review_contract"]["required_outputs"]
        assert "GPD/REFEREE-REPORT{round_suffix}.md" in payload["review_contract"]["required_outputs"]
        assert "GPD/REFEREE-REPORT{round_suffix}.tex" in payload["review_contract"]["required_outputs"]
        assert payload["review_contract"]["preflight_checks"] == [
            "command_context",
            "project_state",
            "roadmap",
            "conventions",
            "research_artifacts",
            "verification_reports",
            "manuscript",
            "artifact_manifest",
            "bibliography_audit",
            "bibliography_audit_clean",
            "reproducibility_manifest",
            "reproducibility_ready",
            "manuscript_proof_review",
        ]
        assert payload["review_contract"]["stage_artifacts"] == [
            "GPD/review/CLAIMS{round_suffix}.json",
            "GPD/review/STAGE-reader{round_suffix}.json",
            "GPD/review/STAGE-literature{round_suffix}.json",
            "GPD/review/STAGE-math{round_suffix}.json",
            "GPD/review/STAGE-physics{round_suffix}.json",
            "GPD/review/STAGE-interestingness{round_suffix}.json",
            "GPD/review/REVIEW-LEDGER{round_suffix}.json",
            "GPD/review/REFEREE-DECISION{round_suffix}.json",
        ]
        assert payload["review_contract"]["conditional_requirements"] == [
            {
                "when": "theorem-bearing claims are present",
                "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                "required_evidence": [],
                "blocking_conditions": [],
                "blocking_preflight_checks": [],
                "stage_artifacts": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            }
        ]
        assert "manuscript scaffold target (existing draft or bootstrap target)" in payload["review_contract"]["required_evidence"]
        assert "phase summaries or milestone digest" in payload["review_contract"]["required_evidence"]
        assert "verification reports" in payload["review_contract"]["required_evidence"]
        assert "manuscript-root bibliography audit" in payload["review_contract"]["required_evidence"]
        assert "manuscript-root artifact manifest" in payload["review_contract"]["required_evidence"]
        assert "manuscript-root reproducibility manifest" in payload["review_contract"]["required_evidence"]

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
        assert "GPD/REFEREE-REPORT{round_suffix}.md" in payload["review_contract"]["required_outputs"]
        assert "GPD/REFEREE-REPORT{round_suffix}.tex" in payload["review_contract"]["required_outputs"]
        assert "GPD/review/CLAIMS{round_suffix}.json" in payload["review_contract"]["required_outputs"]
        assert "GPD/review/STAGE-interestingness{round_suffix}.json" in payload["review_contract"]["required_outputs"]
        assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in payload["review_contract"]["required_outputs"]
        assert "GPD/CONSISTENCY-REPORT.md" not in payload["review_contract"]["required_outputs"]
        assert payload["review_contract"]["preflight_checks"] == [
            "command_context",
            "project_state",
            "roadmap",
            "conventions",
            "research_artifacts",
            "verification_reports",
            "manuscript",
            "artifact_manifest",
            "bibliography_audit",
            "bibliography_audit_clean",
            "reproducibility_manifest",
            "reproducibility_ready",
            "manuscript_proof_review",
        ]
        assert "existing manuscript" in payload["review_contract"]["required_evidence"]
        assert "phase summaries or milestone digest" in payload["review_contract"]["required_evidence"]
        assert "verification reports" in payload["review_contract"]["required_evidence"]
        assert "manuscript-root bibliography audit" in payload["review_contract"]["required_evidence"]
        assert "manuscript-root artifact manifest" in payload["review_contract"]["required_evidence"]
        assert "manuscript-root reproducibility manifest" in payload["review_contract"]["required_evidence"]
        assert "manuscript-root publication artifacts" in payload["review_contract"]["required_evidence"]
        assert payload["review_contract"]["stage_artifacts"] == [
            "GPD/review/CLAIMS{round_suffix}.json",
            "GPD/review/STAGE-reader{round_suffix}.json",
            "GPD/review/STAGE-literature{round_suffix}.json",
            "GPD/review/STAGE-math{round_suffix}.json",
            "GPD/review/STAGE-physics{round_suffix}.json",
            "GPD/review/STAGE-interestingness{round_suffix}.json",
            "GPD/review/REVIEW-LEDGER{round_suffix}.json",
            "GPD/review/REFEREE-DECISION{round_suffix}.json",
        ]
        assert payload["review_contract"]["conditional_requirements"] == [
            {
                "when": "theorem-bearing claims are present",
                "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                "required_evidence": [],
                "blocking_conditions": [],
                "blocking_preflight_checks": [],
                "stage_artifacts": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            }
        ]
        assert "stage_ids" not in payload["review_contract"]
        assert "final_decision_output" not in payload["review_contract"]
        assert "requires_fresh_context_per_stage" not in payload["review_contract"]
        assert "max_review_rounds" not in payload["review_contract"]

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
        assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in payload["review_contract"]["required_outputs"]
        assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in payload["review_contract"]["required_outputs"]
        assert "existing manuscript" in payload["review_contract"]["required_evidence"]
        assert "referee report source when provided as a path" in payload["review_contract"]["required_evidence"]
        assert "missing referee report source when provided as a path" in payload["review_contract"]["blocking_conditions"]
        assert "command_context" in payload["review_contract"]["preflight_checks"]
        assert "referee_report_source" in payload["review_contract"]["preflight_checks"]

    def test_review_contract_arxiv_submission_surfaces_latest_review_outcome_gate(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-contract", "arxiv-submission"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:arxiv-submission"
        assert "manuscript-root artifact manifest" in payload["review_contract"]["required_evidence"]
        assert "manuscript-root bibliography audit" in payload["review_contract"]["required_evidence"]
        assert "latest peer-review review ledger" in payload["review_contract"]["required_evidence"]
        assert "latest peer-review referee decision" in payload["review_contract"]["required_evidence"]
        assert "missing manuscript-root artifact manifest" in payload["review_contract"]["blocking_conditions"]
        assert "missing manuscript-root bibliography audit" in payload["review_contract"]["blocking_conditions"]
        assert "missing compiled manuscript" in payload["review_contract"]["blocking_conditions"]
        assert "missing latest staged peer-review decision evidence" in payload["review_contract"]["blocking_conditions"]
        assert "latest staged peer-review recommendation blocks submission packaging" in payload["review_contract"]["blocking_conditions"]
        assert payload["review_contract"]["preflight_checks"] == [
            "command_context",
            "project_state",
            "manuscript",
            "artifact_manifest",
            "bibliography_audit",
            "bibliography_audit_clean",
            "compiled_manuscript",
            "conventions",
            "publication_blockers",
            "review_ledger",
            "review_ledger_valid",
            "referee_decision",
            "referee_decision_valid",
            "publication_review_outcome",
            "manuscript_proof_review",
        ]
        assert payload["review_contract"]["conditional_requirements"] == [
            {
                "when": "theorem-bearing manuscripts are present",
                "required_outputs": [],
                "required_evidence": ["cleared manuscript proof review for theorem-bearing manuscripts"],
                "blocking_conditions": ["missing or stale manuscript proof review for theorem-bearing manuscripts"],
                "blocking_preflight_checks": ["manuscript_proof_review"],
                "stage_artifacts": [],
            }
        ]

    def test_command_context_project_required_fails_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dollar_command_prefix: str
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside"
        outside_dir.mkdir()
        monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "progress"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:progress"
        assert payload["context_mode"] == "project-required"
        assert payload["passed"] is False
        assert payload["guidance"] == (
            "This command requires a recoverable GPD workspace. "
            "Open the right project, use `gpd resume --recent` to rediscover it, or initialize a new project with "
            f"`{dollar_command_prefix}new-project` in the runtime surface or `gpd init new-project` in the local CLI."
        )

    def test_command_context_progress_resolves_ancestor_project_root_for_nested_workspace(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        nested = gpd_project / "workspace" / "notes"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(nested), "validate", "command-context", "progress"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:progress"
        assert payload["context_mode"] == "project-required"
        assert payload["passed"] is True
        assert payload["project_exists"] is True
        assert checks["project_exists"]["passed"] is True
        assert "GPD/PROJECT.md" in checks["project_exists"]["detail"]

    def test_command_context_resume_work_resolves_ancestor_project_root_for_nested_workspace(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        nested = gpd_project / "workspace" / "notes"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(nested), "validate", "command-context", "resume-work"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:resume-work"
        assert payload["context_mode"] == "project-required"
        assert payload["passed"] is True
        assert checks["project_exists"]["passed"] is True

    def test_command_context_resume_work_requires_literal_files_in_project_root(self, gpd_project: Path) -> None:
        (gpd_project / "GPD" / "ROADMAP.md").unlink()

        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", "resume-work"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:resume-work"
        assert payload["context_mode"] == "project-required"
        assert payload["passed"] is False
        assert checks["project_exists"]["passed"] is True

    def test_command_context_recovery_surfaces_accept_partial_recoverable_workspace(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project = tmp_path / "recoverable-project"
        nested = project / "workspace" / "notes"
        gpd_dir = project / "GPD"
        nested.mkdir(parents=True)
        gpd_dir.mkdir()
        (gpd_dir / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (gpd_dir / "STATE.md").write_text("# Research State\n", encoding="utf-8")
        monkeypatch.chdir(nested)

        for command_name in ("progress", "resume-work"):
            result = runner.invoke(
                app,
                ["--raw", "--cwd", str(nested), "validate", "command-context", command_name],
                catch_exceptions=False,
            )

            assert result.exit_code == (0 if command_name == "resume-work" else 1), result.output
            payload = json.loads(result.output)
            checks = {check["name"]: check for check in payload["checks"]}
            assert payload["passed"] is (command_name == "resume-work")
            assert payload["project_exists"] is False
            assert checks["state_exists"]["passed"] is True
            assert checks["roadmap_exists"]["passed"] is True
            assert checks["project_exists"]["passed"] is False
            assert checks["required_files"]["passed"] is (command_name == "resume-work")

    def test_command_context_plan_milestone_gaps_requires_globbed_files_in_project_root(
        self, gpd_project: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", "plan-milestone-gaps"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:plan-milestone-gaps"
        assert payload["context_mode"] == "project-required"
        assert payload["passed"] is False
        assert checks["project_exists"]["passed"] is True

    def test_command_context_plan_milestone_gaps_resolves_ancestor_project_root_for_nested_workspace(
        self,
        gpd_project: Path,
    ) -> None:
        nested = gpd_project / "workspace" / "notes"
        nested.mkdir(parents=True)
        (gpd_project / "GPD" / "v1-MILESTONE-AUDIT.md").write_text("# Audit\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(nested), "validate", "command-context", "plan-milestone-gaps"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:plan-milestone-gaps"
        assert payload["context_mode"] == "project-required"
        assert payload["passed"] is True
        assert checks["project_exists"]["passed"] is True

    def test_command_context_progress_auto_selects_unique_recoverable_recent_project(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workspace = tmp_path.parent / f"{tmp_path.name}-outside-unique"
        workspace.mkdir()
        project = tmp_path / "recoverable-project"
        gpd_dir = project / "GPD"
        gpd_dir.mkdir(parents=True)
        (gpd_dir / "STATE.md").write_text("# Research State\n", encoding="utf-8")
        (gpd_dir / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (gpd_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
        resume_file = gpd_dir / "phases" / "01" / ".continue-here.md"
        resume_file.parent.mkdir(parents=True, exist_ok=True)
        resume_file.write_text("resume\n", encoding="utf-8")
        data_root = tmp_path / "data"
        monkeypatch.setenv("GPD_DATA_DIR", str(data_root))
        record_recent_project(
            project,
            session_data={
                "last_date": "2026-03-29T12:00:00+00:00",
                "stopped_at": "Phase 01",
                "resume_file": "GPD/phases/01/.continue-here.md",
            },
            store_root=data_root,
        )

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(workspace), "validate", "command-context", "progress"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["passed"] is True
        assert checks["project_reentry"]["passed"] is True
        assert "auto-selected recoverable recent project" in checks["project_reentry"]["detail"]

    def test_command_context_resume_work_auto_selects_unique_recoverable_recent_project(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workspace = tmp_path.parent / f"{tmp_path.name}-outside-unique-resume"
        workspace.mkdir()
        project = tmp_path / "recoverable-resume-project"
        gpd_dir = project / "GPD"
        gpd_dir.mkdir(parents=True)
        (gpd_dir / "STATE.md").write_text("# Research State\n", encoding="utf-8")
        (gpd_dir / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (gpd_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
        resume_file = gpd_dir / "phases" / "02" / ".continue-here.md"
        resume_file.parent.mkdir(parents=True, exist_ok=True)
        resume_file.write_text("resume\n", encoding="utf-8")
        data_root = tmp_path / "data"
        monkeypatch.setenv("GPD_DATA_DIR", str(data_root))
        record_recent_project(
            project,
            session_data={
                "last_date": "2026-03-29T12:00:00+00:00",
                "stopped_at": "Phase 02",
                "resume_file": "GPD/phases/02/.continue-here.md",
            },
            store_root=data_root,
        )

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(workspace), "validate", "command-context", "resume-work"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["passed"] is True
        assert checks["project_reentry"]["passed"] is True
        assert "auto-selected recoverable recent project" in checks["project_reentry"]["detail"]

    def test_command_context_resume_work_requires_explicit_selection_when_recent_projects_are_ambiguous(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workspace = tmp_path.parent / f"{tmp_path.name}-outside-ambiguous"
        workspace.mkdir()
        data_root = tmp_path / "data"
        monkeypatch.setenv("GPD_DATA_DIR", str(data_root))

        for name, stopped_at in (("project-a", "Phase 01"), ("project-b", "Phase 02")):
            project = tmp_path / name
            gpd_dir = project / "GPD"
            gpd_dir.mkdir(parents=True)
            (gpd_dir / "STATE.md").write_text("# Research State\n", encoding="utf-8")
            (gpd_dir / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
            (gpd_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
            phase_number = stopped_at.removeprefix("Phase ").strip() or "01"
            resume_file = gpd_dir / "phases" / phase_number / ".continue-here.md"
            resume_file.parent.mkdir(parents=True, exist_ok=True)
            resume_file.write_text("resume\n", encoding="utf-8")
            record_recent_project(
                project,
                session_data={
                    "last_date": "2026-03-29T12:00:00+00:00",
                    "stopped_at": stopped_at,
                    "resume_file": f"GPD/phases/{phase_number}/.continue-here.md",
                },
                store_root=data_root,
            )

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(workspace), "validate", "command-context", "resume-work"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["passed"] is False
        assert checks["project_reentry"]["passed"] is False
        assert "multiple recoverable recent GPD projects" in payload["guidance"]

    def test_command_context_projectless_passes_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dollar_command_prefix: str
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
        assert payload["public_runtime_command_prefix"] == dollar_command_prefix
        assert f"public command surface rooted at `{dollar_command_prefix}`" in payload["dispatch_note"]

    def test_command_context_start_passes_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dollar_command_prefix: str
    ) -> None:
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", "start"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:start"
        assert payload["context_mode"] == "projectless"
        assert payload["passed"] is True
        assert payload["public_runtime_command_prefix"] == dollar_command_prefix
        assert f"public command surface rooted at `{dollar_command_prefix}`" in payload["dispatch_note"]

    def test_command_context_tour_passes_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dollar_command_prefix: str
    ) -> None:
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", "tour"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:tour"
        assert payload["context_mode"] == "projectless"
        assert payload["passed"] is True
        assert payload["public_runtime_command_prefix"] == dollar_command_prefix
        assert f"public command surface rooted at `{dollar_command_prefix}`" in payload["dispatch_note"]

    @pytest.mark.parametrize("command_name", ["health", "suggest-next"])
    def test_command_context_projectless_recovery_commands_pass_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command_name: str
    ) -> None:
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", command_name],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == f"gpd:{command_name}"
        assert payload["context_mode"] == "projectless"
        assert payload["passed"] is True

    @pytest.mark.parametrize("command_name", ["gpd:settings", "gpd:set-tier-models"])
    def test_command_context_surfaces_runtime_command_dispatch_note(
        self, dollar_command_prefix: str, command_name: str
    ) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", command_name],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == command_name
        assert payload["validated_surface"] == "public_runtime_dollar_command"
        assert payload["public_runtime_command_prefix"] == dollar_command_prefix
        assert payload["local_cli_equivalence_guaranteed"] is False
        assert f"public command surface rooted at `{dollar_command_prefix}`" in payload["dispatch_note"]
        assert "same-name local `gpd` subcommand" in payload["dispatch_note"]

    @pytest.mark.parametrize("command_name", ["gpd:settings", "gpd:set-tier-models"])
    def test_command_context_surfaces_slash_runtime_dispatch_note(
        self, slash_command_prefix: str, monkeypatch: pytest.MonkeyPatch, command_name: str
    ) -> None:
        monkeypatch.setattr("gpd.cli.detect_runtime_for_gpd_use", lambda cwd=None: _SLASH_COMMAND_DESCRIPTOR.runtime_name)

        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", command_name],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == command_name
        assert payload["validated_surface"] == "public_runtime_slash_command"
        assert payload["public_runtime_command_prefix"] == slash_command_prefix
        assert payload["local_cli_equivalence_guaranteed"] is False
        assert f"public command surface rooted at `{slash_command_prefix}`" in payload["dispatch_note"]
        assert "same-name local `gpd` subcommand" in payload["dispatch_note"]

    @pytest.mark.parametrize("command_name", ["gpd:settings", "gpd:set-tier-models"])
    def test_command_context_falls_back_when_runtime_resolution_fails(
        self, monkeypatch: pytest.MonkeyPatch, command_name: str
    ) -> None:
        monkeypatch.setattr("gpd.cli.detect_runtime_for_gpd_use", lambda cwd=None: None)

        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", command_name],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == command_name
        assert payload["validated_surface"] == "public_runtime_command_surface"
        assert payload["public_runtime_command_prefix"] == ""
        assert payload["local_cli_equivalence_guaranteed"] is False
        assert "the active runtime command surface" in payload["dispatch_note"]
        assert "same-name local `gpd` subcommand" in payload["dispatch_note"]

    def test_config_set_autonomy_guided_path_uses_runtime_command_helper(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dollar_command_prefix: str
    ) -> None:
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(
            app,
            ["--raw", "config", "set", "autonomy", '"balanced"'],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["guided_path"] == (
            f"Use `{dollar_command_prefix}settings` inside the runtime for guided autonomy changes."
        )

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
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dollar_command_prefix: str
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-aware"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "discover"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:discover"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is False
        assert payload["explicit_inputs"] == ["phase number or standalone topic"]
        assert payload["guidance"] == (
            "Either provide phase number or standalone topic explicitly, or initialize a project with "
            f"`{dollar_command_prefix}new-project` in the runtime surface or `gpd init new-project` in the local CLI."
        )

    def test_review_preflight_propagates_runtime_surface_metadata(self, dollar_command_prefix: str) -> None:
        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["validated_surface"] == "public_runtime_dollar_command"
        assert payload["public_runtime_command_prefix"] == dollar_command_prefix
        assert payload["local_cli_equivalence_guaranteed"] is False
        assert f"public command surface rooted at `{dollar_command_prefix}`" in payload["dispatch_note"]
        assert payload["conditional_requirements"] == [
            {
                "when": "theorem-bearing claims are present",
                "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                "required_evidence": [],
                "blocking_conditions": [],
                "blocking_preflight_checks": [],
                "stage_artifacts": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            }
        ]
        checks = {check["name"]: check for check in payload["checks"]}
        assert "same-name local `gpd` subcommand" in checks["command_context"]["detail"]
        assert checks["artifact_manifest"]["passed"] is True
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["reproducibility_manifest"]["passed"] is True
        assert checks["manuscript_proof_review"]["passed"] is True

    def test_review_contract_preflight_helpers_only_follow_explicit_checks(self) -> None:
        contract = SimpleNamespace(
            preflight_checks=["artifact_manifest"],
            required_evidence=[
                "verification reports",
                "manuscript-root artifact manifest",
                "manuscript-root bibliography audit",
            ],
            blocking_conditions=[
                "missing compiled manuscript",
                "missing latest staged peer-review decision evidence",
            ],
        )

        assert cli_module._review_contract_requests_check(contract, "artifact_manifest") is True
        assert cli_module._review_preflight_check_is_blocking(contract, "artifact_manifest") is True
        assert cli_module._review_contract_requests_check(contract, "verification_reports") is False
        assert cli_module._review_preflight_check_is_blocking(contract, "verification_reports") is False
        assert cli_module._review_contract_requests_check(contract, "compiled_manuscript") is False
        assert cli_module._review_preflight_check_is_blocking(contract, "compiled_manuscript") is False
        assert cli_module._review_contract_requests_check(contract, "review_ledger") is False
        assert cli_module._review_preflight_check_is_blocking(contract, "review_ledger") is False
        assert (
            cli_module._review_preflight_check_is_blocking(
                contract,
                "manuscript_proof_review",
                conditional_blocking_preflight_checks={"manuscript_proof_review"},
            )
            is True
        )

    def test_validate_review_preflight_help_mentions_manuscript_and_referee_subjects(self) -> None:
        result = runner.invoke(
            app,
            ["validate", "review-preflight", "--help"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        assert "Optional phase number, manuscript target" in result.output
        assert "referee report source" in result.output

    def test_command_required_files_override_detail_uses_contract_metadata_not_command_name(self, tmp_path: Path) -> None:
        manuscript = canonical_manuscript_path(tmp_path)
        manuscript.parent.mkdir(parents=True, exist_ok=True)
        manuscript.write_text(
            "\\documentclass{article}\n\\begin{document}\nDraft.\n\\end{document}\n",
            encoding="utf-8",
        )
        command = SimpleNamespace(
            name="gpd:custom-review",
            requires={"files": ["paper/*.tex"]},
            review_contract=SimpleNamespace(preflight_checks=["manuscript", "compiled_manuscript"]),
        )

        detail = cli_module._command_required_files_override_detail(
            tmp_path,
            command,
            str(manuscript.relative_to(tmp_path)),
            workspace_cwd=tmp_path,
        )

        assert detail is not None
        assert "explicit manuscript target satisfies command context" in detail

    def test_command_required_files_override_detail_skips_referee_source_commands(self, tmp_path: Path) -> None:
        manuscript = canonical_manuscript_path(tmp_path)
        manuscript.parent.mkdir(parents=True, exist_ok=True)
        manuscript.write_text(
            "\\documentclass{article}\n\\begin{document}\nDraft.\n\\end{document}\n",
            encoding="utf-8",
        )
        command = SimpleNamespace(
            name="gpd:custom-referees",
            requires={"files": ["paper/*.tex"]},
            review_contract=SimpleNamespace(preflight_checks=["manuscript", "referee_report_source"]),
        )

        detail = cli_module._command_required_files_override_detail(
            tmp_path,
            command,
            str(manuscript.relative_to(tmp_path)),
            workspace_cwd=tmp_path,
        )

        assert detail is None

    def test_command_context_manuscript_check_allows_bootstrap_from_contract_metadata(self, tmp_path: Path) -> None:
        isolated_root = tmp_path / "bootstrap-context"
        isolated_root.mkdir(parents=True, exist_ok=True)
        command = SimpleNamespace(
            name="gpd:custom-write",
            requires={},
            review_contract=SimpleNamespace(preflight_checks=["manuscript"]),
        )

        result = cli_module._command_context_manuscript_check(
            isolated_root,
            command,
            arguments=None,
            workspace_cwd=isolated_root,
        )

        assert result is not None
        passed, detail = result
        assert passed is True
        assert "fresh bootstrap is allowed" in detail

    def test_review_preflight_falls_back_when_runtime_resolution_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("gpd.cli.detect_runtime_for_gpd_use", lambda cwd=None: None)

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["validated_surface"] == "public_runtime_command_surface"
        assert payload["public_runtime_command_prefix"] == ""
        assert payload["local_cli_equivalence_guaranteed"] is False
        assert "the active runtime command surface" in payload["dispatch_note"]

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
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-aware-short"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "discover", "-d", "deep"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:discover"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is False

    def test_command_context_explain_requires_explicit_inputs_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dollar_command_prefix: str
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-explain"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "explain"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:explain"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is False
        assert payload["explicit_inputs"] == ["concept, result, method, notation, or paper"]
        assert payload["guidance"] == (
            "Either provide concept, result, method, notation, or paper explicitly, or initialize a project with "
            f"`{dollar_command_prefix}new-project` in the runtime surface or `gpd init new-project` in the local CLI."
        )

    def test_command_context_compare_results_requires_explicit_inputs_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dollar_command_prefix: str
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-compare"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "compare-results"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:compare-results"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is False
        assert payload["explicit_inputs"] == ["phase, artifact, or comparison target"]
        assert payload["guidance"] == (
            "Either provide phase, artifact, or comparison target explicitly, or initialize a project with "
            f"`{dollar_command_prefix}new-project` in the runtime surface or `gpd init new-project` in the local CLI."
        )

    def test_command_context_digest_knowledge_requires_explicit_inputs_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-digest-knowledge"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "digest-knowledge"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:digest-knowledge"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is False
        assert checks["project_exists"]["passed"] is False
        assert checks["explicit_inputs"]["passed"] is False

    def test_command_context_digest_knowledge_accepts_explicit_topic_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-digest-knowledge-topic"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            [
                "--raw",
                "--cwd",
                str(outside_dir),
                "validate",
                "command-context",
                "digest-knowledge",
                "renormalization group fixed points",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:digest-knowledge"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is True
        assert checks["project_exists"]["passed"] is False
        assert checks["explicit_inputs"]["passed"] is True

    def test_command_context_digest_knowledge_accepts_explicit_file_path_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-digest-knowledge-file"
        outside_dir.mkdir()
        knowledge_dir = outside_dir / "GPD" / "knowledge"
        knowledge_dir.mkdir(parents=True)
        knowledge_file = knowledge_dir / "K-renormalization-group-fixed-points.md"
        knowledge_file.write_text("knowledge doc\n", encoding="utf-8")
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            [
                "--raw",
                "--cwd",
                str(outside_dir),
                "validate",
                "command-context",
                "digest-knowledge",
                str(knowledge_file.relative_to(outside_dir)),
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:digest-knowledge"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is True
        assert checks["project_exists"]["passed"] is False
        assert checks["explicit_inputs"]["passed"] is True

    def test_command_context_digest_knowledge_accepts_explicit_modern_arxiv_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-digest-knowledge-arxiv"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "digest-knowledge", "2401.12345v2"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:digest-knowledge"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is True
        assert checks["project_exists"]["passed"] is False
        assert checks["explicit_inputs"]["passed"] is True

    def test_command_context_digest_knowledge_accepts_explicit_legacy_arxiv_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-digest-knowledge-legacy-arxiv"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "digest-knowledge", "hep-th/9901001"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:digest-knowledge"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is True
        assert checks["project_exists"]["passed"] is False
        assert checks["explicit_inputs"]["passed"] is True

    def test_command_context_review_knowledge_requires_explicit_inputs_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-review-knowledge"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "review-knowledge"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:review-knowledge"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is False
        assert checks["project_exists"]["passed"] is False
        assert checks["explicit_inputs"]["passed"] is False

    def test_command_context_review_knowledge_accepts_explicit_knowledge_path_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-review-knowledge-path"
        outside_dir.mkdir()
        knowledge_dir = outside_dir / "GPD" / "knowledge"
        knowledge_dir.mkdir(parents=True)
        knowledge_file = knowledge_dir / "K-renormalization-group-fixed-points.md"
        knowledge_file.write_text("knowledge doc\n", encoding="utf-8")
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            [
                "--raw",
                "--cwd",
                str(outside_dir),
                "validate",
                "command-context",
                "review-knowledge",
                str(knowledge_file.relative_to(outside_dir)),
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:review-knowledge"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is True
        assert checks["project_exists"]["passed"] is False
        assert checks["explicit_inputs"]["passed"] is True

    def test_command_context_review_knowledge_accepts_explicit_knowledge_id_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-review-knowledge-id"
        outside_dir.mkdir()
        knowledge_dir = outside_dir / "GPD" / "knowledge"
        knowledge_dir.mkdir(parents=True)
        knowledge_file = knowledge_dir / "K-renormalization-group-fixed-points.md"
        knowledge_file.write_text("knowledge doc\n", encoding="utf-8")
        monkeypatch.chdir(outside_dir)

        result = runner.invoke(
            app,
            [
                "--raw",
                "--cwd",
                str(outside_dir),
                "validate",
                "command-context",
                "review-knowledge",
                "K-renormalization-group-fixed-points",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:review-knowledge"
        assert payload["context_mode"] == "project-aware"
        assert payload["passed"] is True
        assert checks["project_exists"]["passed"] is False
        assert checks["explicit_inputs"]["passed"] is True

    def test_review_preflight_write_paper_strict(self) -> None:
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(gpd_project), "validate", "review-preflight", "write-paper", "--strict"],
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
        } <= check_names
        assert checks["reproducibility_manifest"]["passed"] is True
        assert checks["reproducibility_ready"]["passed"] is True

    def test_review_preflight_write_paper_bootstraps_manuscript_proof_review_manifest(
        self,
        gpd_project: Path,
    ) -> None:
        _write_review_stage_artifacts(gpd_project, artifact_names=("STAGE-math.json",))

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is True
        assert (gpd_project / "paper" / "PROOF-REVIEW-MANIFEST.json").exists()

    def test_review_preflight_write_paper_reports_theorem_bearing_proof_review_without_blocking(
        self,
        gpd_project: Path,
    ) -> None:
        write_proof_review_package(gpd_project, theorem_bearing=True, review_report=False)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(gpd_project), "validate", "review-preflight", "write-paper"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is False
        assert "PROOF-REDTEAM.md" in checks["manuscript_proof_review"]["detail"]
        assert "write-paper will run its own staged proof-review loop" in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_peer_review_surfaces_active_conditional_requirements_for_theorem_bearing_manuscript(
        self,
        gpd_project: Path,
    ) -> None:
        write_proof_review_package(gpd_project, theorem_bearing=True, review_report=False)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(gpd_project), "validate", "review-preflight", "peer-review"],
            catch_exceptions=False,
        )

        payload = json.loads(result.output)
        assert payload["active_conditional_requirements"] == payload["conditional_requirements"]
        assert payload["active_conditional_requirements"] == [
            {
                "when": "theorem-bearing claims are present",
                "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                "required_evidence": [],
                "blocking_conditions": [],
                "blocking_preflight_checks": [],
                "stage_artifacts": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            }
        ]

    def test_review_preflight_write_paper_reports_theorem_bearing_claim_inventory_without_blocking(
        self,
        gpd_project: Path,
    ) -> None:
        _write_review_stage_artifacts(
            gpd_project,
            artifact_names=("STAGE-reader.json",),
            proof_bearing=True,
            write_proof_redteam=False,
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is False
        assert "no prior staged math review artifact matches the active manuscript" in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_write_paper_reports_theorem_bearing_manuscript_text_without_blocking(
        self,
        gpd_project: Path,
    ) -> None:
        _manuscript_entrypoint_path(gpd_project).write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\begin{theorem}For every r_0 > 0, the orbit intersects the target annulus.\\end{theorem}\n"
            "\\begin{proof}The proof is omitted.\\end{proof}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is False
        assert "no prior staged math review artifact matches the active manuscript" in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_write_paper_reports_theorem_bearing_nested_section_text_without_blocking(
        self,
        gpd_project: Path,
    ) -> None:
        manuscript_path = _manuscript_entrypoint_path(gpd_project)
        manuscript_path.write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\input{sections/results}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        section_path = manuscript_path.parent / "sections" / "results.tex"
        section_path.parent.mkdir(parents=True, exist_ok=True)
        section_path.write_text(
            "\\begin{claim}For every r_0 > 0, the orbit intersects the target annulus.\\end{claim}\n"
            "\\begin{proof}The proof is omitted.\\end{proof}\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is False
        assert "no prior staged math review artifact matches the active manuscript" in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_write_paper_reports_stale_manuscript_proof_review_without_blocking(
        self,
        gpd_project: Path,
    ) -> None:
        _write_review_stage_artifacts(gpd_project, artifact_names=("STAGE-math.json",))

        initial = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )
        assert initial.exit_code == 0, initial.output

        manuscript = canonical_manuscript_path(gpd_project)
        manuscript.write_text(
            "\\documentclass{article}\n\\begin{document}\nRevised theorem statement.\n\\end{document}\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is False
        assert "stale" in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_write_paper_reports_missing_proof_redteam_for_proof_bearing_manuscript_without_blocking(
        self,
        gpd_project: Path,
    ) -> None:
        _write_review_stage_artifacts(
            gpd_project,
            artifact_names=("STAGE-math.json",),
            proof_bearing=True,
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is False
        assert "PROOF-REDTEAM.md" in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_write_paper_accepts_passed_proof_redteam_for_proof_bearing_manuscript(
        self,
        gpd_project: Path,
    ) -> None:
        _write_review_stage_artifacts(
            gpd_project,
            artifact_names=("STAGE-math.json",),
            proof_bearing=True,
            write_proof_redteam=True,
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is True

    def test_review_preflight_peer_review_reports_stale_manuscript_proof_review_without_blocking(
        self,
        gpd_project: Path,
    ) -> None:
        _write_review_stage_artifacts(gpd_project, artifact_names=("STAGE-math.json",))

        initial = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )
        assert initial.exit_code == 0, initial.output

        manuscript = canonical_manuscript_path(gpd_project)
        manuscript.write_text(
            "\\documentclass{article}\n\\begin{document}\nPeer review should refresh this proof.\n\\end{document}\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is False
        assert payload["passed"] is True

    def test_review_preflight_write_paper_strict_allows_fresh_bootstrap_without_manuscript(self, gpd_project: Path) -> None:
        canonical_manuscript_path(gpd_project).unlink()

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:write-paper"
        assert payload["passed"] is True
        assert payload["active_conditional_requirements"] == []
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert "fresh bootstrap is allowed" in checks["manuscript"]["detail"]
        assert "reproducibility_manifest" not in checks
        assert "reproducibility_ready" not in checks

    @pytest.mark.parametrize(
        ("command", "extra_args"),
        [
            ("write-paper", []),
            ("respond-to-referees", ["reports/referee-report.md"]),
            ("peer-review", []),
            ("arxiv-submission", []),
        ],
    )
    def test_review_preflight_fails_closed_on_ambiguous_manuscript_state(
        self,
        gpd_project: Path,
        command: str,
        extra_args: list[str],
    ) -> None:
        _write_secondary_manuscript_root(gpd_project)

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", command, *extra_args, "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["passed"] is False
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert "ambiguous or inconsistent manuscript roots" in checks["manuscript"]["detail"]
        if command == "write-paper":
            assert "reproducibility_manifest" not in checks
            assert "reproducibility_ready" not in checks

    @pytest.mark.parametrize(
        ("command", "extra_args"),
        [
            ("write-paper", []),
            ("respond-to-referees", ["reports/referee-report.md"]),
            ("peer-review", []),
            ("arxiv-submission", []),
        ],
    )
    def test_review_preflight_fails_closed_on_inconsistent_manuscript_state(
        self,
        gpd_project: Path,
        command: str,
        extra_args: list[str],
    ) -> None:
        paper_dir = gpd_project / "paper"
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

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", command, *extra_args, "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["passed"] is False
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert "ambiguous or inconsistent manuscript roots" in checks["manuscript"]["detail"]

    def test_review_preflight_write_paper_strict_recognizes_markdown_resume_directory(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()
        (paper_dir / _CANONICAL_MARKDOWN_BASENAME).write_text("# Markdown manuscript\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert f"paper/{_CANONICAL_MARKDOWN_BASENAME}" in checks["manuscript"]["detail"]
        assert checks["artifact_manifest"]["passed"] is True
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["reproducibility_manifest"]["passed"] is True

    @pytest.mark.parametrize("resume_dir_name", ["manuscript", "draft"])
    def test_review_preflight_write_paper_strict_uses_resolved_resume_directory(
        self,
        gpd_project: Path,
        resume_dir_name: str,
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()

        resume_dir = gpd_project / resume_dir_name
        resume_dir.mkdir()
        (resume_dir / _CANONICAL_MANUSCRIPT_BASENAME).write_text(
            "\\documentclass{article}\n\\begin{document}\nResume manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )
        for artifact_name in (
            "PAPER-CONFIG.json",
            "ARTIFACT-MANIFEST.json",
            "BIBLIOGRAPHY-AUDIT.json",
            "reproducibility-manifest.json",
        ):
            (resume_dir / artifact_name).write_text((paper_dir / artifact_name).read_text(encoding="utf-8"), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert f"{resume_dir_name}/{_CANONICAL_MANUSCRIPT_BASENAME}" in checks["manuscript"]["detail"]
        assert checks["artifact_manifest"]["passed"] is True
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["reproducibility_manifest"]["passed"] is True
        assert checks["reproducibility_ready"]["passed"] is True

    def test_review_preflight_write_paper_strict_does_not_fall_back_to_legacy_gpd_paper_artifacts(
        self,
        gpd_project: Path,
    ) -> None:
        canonical_manuscript_path(gpd_project).unlink()

        resume_dir = gpd_project / "manuscript"
        resume_dir.mkdir()
        (resume_dir / _CANONICAL_MANUSCRIPT_BASENAME).write_text(
            "\\documentclass{article}\n\\begin{document}\nResume manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )
        _write_legacy_publication_artifacts(
            gpd_project,
            ("PAPER-CONFIG.json", "ARTIFACT-MANIFEST.json", "BIBLIOGRAPHY-AUDIT.json", "reproducibility-manifest.json"),
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "write-paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert "fresh bootstrap is allowed" in checks["manuscript"]["detail"]
        assert "artifact_manifest" not in checks
        assert "bibliography_audit" not in checks
        assert "reproducibility_manifest" not in checks

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

    def test_command_context_start_command_passes_without_project(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "start"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:start"
        assert payload["context_mode"] == "projectless"
        assert payload["passed"] is True
        assert checks["project_context"]["passed"] is True

    def test_command_context_tour_command_passes_without_project(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        empty_dir = tmp_path / "empty-context"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(empty_dir), "validate", "command-context", "tour"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:tour"
        assert payload["context_mode"] == "projectless"
        assert payload["passed"] is True
        assert checks["project_context"]["passed"] is True

    def test_command_context_project_aware_command_accepts_explicit_inputs(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-aware-explicit"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "discover", "7"],
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
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-required"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(outside_dir), "validate", "command-context", "quick"],
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
        assert checks["manuscript"]["passed"] is True
        assert checks["conventions"]["passed"] is True
        assert checks["artifact_manifest"]["passed"] is True
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["bibliography_audit_clean"]["passed"] is True
        assert checks["reproducibility_manifest"]["passed"] is True
        assert checks["reproducibility_ready"]["passed"] is True

    def test_review_preflight_peer_review_without_subject_accepts_markdown_entrypoint(
        self, gpd_project: Path
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()
        (paper_dir / _CANONICAL_MARKDOWN_BASENAME).write_text("# Markdown manuscript\n", encoding="utf-8")

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
        assert checks["manuscript"]["passed"] is True
        assert f"paper/{_CANONICAL_MARKDOWN_BASENAME}" in checks["manuscript"]["detail"]
        assert checks["artifact_manifest"]["passed"] is True
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["reproducibility_manifest"]["passed"] is True

    def test_review_preflight_strict_blocks_review_integrity_failures(self, gpd_project: Path) -> None:
        planning = gpd_project / "GPD"
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
        planning = gpd_project / "GPD"
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
        planning = gpd_project / "GPD"
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
        planning = gpd_project / "GPD"
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
        planning = gpd_project / "GPD"
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
        assert "artifact_manifest" not in checks
        assert "bibliography_audit" not in checks

    def test_review_preflight_respond_to_referees_accepts_markdown_manuscript(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()
        (paper_dir / _CANONICAL_MARKDOWN_BASENAME).write_text("# Markdown manuscript\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "respond-to-referees", "reports/referee-report.md"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert f"paper/{_CANONICAL_MARKDOWN_BASENAME}" in checks["manuscript"]["detail"]

    def test_review_preflight_peer_review_fails_without_manuscript(self, gpd_project: Path) -> None:
        canonical_manuscript_path(gpd_project).unlink()

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
        canonical_manuscript_path(gpd_project).unlink()

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
        assert checks["command_context"]["passed"] is False
        assert checks["referee_report_source"]["passed"] is True
        assert checks["manuscript"]["passed"] is False
        assert "no manuscript entrypoint found under paper/, manuscript/, or draft/" in checks["command_context"]["detail"]

    def test_review_preflight_peer_review_resolves_ancestor_project_root_for_nested_workspace(
        self,
        gpd_project: Path,
    ) -> None:
        nested = gpd_project / "workspace" / "notes"
        nested.mkdir(parents=True)

        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(nested), "validate", "review-preflight", "peer-review", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert payload["command"] == "gpd:peer-review"
        assert payload["passed"] is True
        assert checks["manuscript"]["passed"] is True
        assert _CANONICAL_MANUSCRIPT_REL in checks["manuscript"]["detail"]


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

    def test_review_preflight_peer_review_strict_rejects_invalid_artifact_manifest(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / "ARTIFACT-MANIFEST.json").write_text("{not json", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["artifact_manifest"]["passed"] is False
        assert "could not parse artifact manifest" in checks["artifact_manifest"]["detail"]

    def test_review_preflight_peer_review_strict_rejects_blank_artifact_manifest_title(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        manifest = json.loads((paper_dir / "ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
        manifest["paper_title"] = "   "
        (paper_dir / "ARTIFACT-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["artifact_manifest"]["passed"] is False
        assert "artifact manifest is invalid" in checks["artifact_manifest"]["detail"]
        assert "artifact_manifest.paper_title" in checks["artifact_manifest"]["detail"]

    def test_review_preflight_peer_review_rejects_explicit_manuscript_path_outside_supported_roots(
        self,
        gpd_project: Path,
    ) -> None:
        canonical_manuscript_path(gpd_project).unlink()

        paper_dir = gpd_project / "paper"
        review_dir = gpd_project / "submission"
        review_dir.mkdir()
        (_manuscript_entrypoint_path(gpd_project, root_name="submission")).write_text(
            "\\documentclass{article}\n\\begin{document}\nSubmission manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )
        for artifact_name in (
            "PAPER-CONFIG.json",
            "ARTIFACT-MANIFEST.json",
            "BIBLIOGRAPHY-AUDIT.json",
            "reproducibility-manifest.json",
        ):
            (review_dir / artifact_name).write_text((paper_dir / artifact_name).read_text(encoding="utf-8"), encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "--raw",
                "validate",
                "review-preflight",
                "peer-review",
                _manuscript_entrypoint_relpath(root_name="submission"),
                "--strict",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["command"] == "gpd:peer-review"
        assert payload["passed"] is False
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert checks["manuscript"]["detail"] == (
            "explicit manuscript target must stay under `paper/`, `manuscript/`, or `draft/` inside the current project"
        )

    def test_review_preflight_peer_review_strict_does_not_fall_back_to_gpd_paper_for_explicit_manuscript(
        self,
        gpd_project: Path,
    ) -> None:
        review_dir = gpd_project / "submission"
        review_dir.mkdir()
        (_manuscript_entrypoint_path(gpd_project, root_name="submission")).write_text(
            "\\documentclass{article}\n\\begin{document}\nSubmission manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "--raw",
                "validate",
                "review-preflight",
                "peer-review",
                _manuscript_entrypoint_relpath(root_name="submission"),
                "--strict",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert checks["manuscript"]["detail"] == (
            "explicit manuscript target must stay under `paper/`, `manuscript/`, or `draft/` inside the current project"
        )

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

    @pytest.mark.parametrize(("command", "extra_args"), [("peer-review", ["paper"]), ("arxiv-submission", ["paper"])])
    def test_review_preflight_explicit_manuscript_path_disambiguates_supported_root(
        self,
        gpd_project: Path,
        command: str,
        extra_args: list[str],
    ) -> None:
        _write_secondary_manuscript_root(gpd_project)

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", command, *extra_args, "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == (1 if command == "arxiv-submission" else 0), result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert "resolved to ./paper/curvature_flow_bounds.tex" in checks["manuscript"]["detail"]

    def test_review_preflight_peer_review_directory_rejects_missing_main_entrypoint(
        self,
        gpd_project: Path,
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()
        (paper_dir / "z-notes.tex").write_text("\\section{Notes}\n", encoding="utf-8")
        (paper_dir / "a-appendix.md").write_text("# Appendix\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "peer-review", "paper", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert "no manuscript entry point found under ./paper" == checks["manuscript"]["detail"]

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

    def test_review_preflight_peer_review_strict_rejects_invalid_bibliography_audit_shape(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / "BIBLIOGRAPHY-AUDIT.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-03-10T00:00:00+00:00",
                    "total_sources": "oops",
                    "resolved_sources": 1,
                    "partial_sources": 0,
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
        assert "bibliography audit is invalid" in checks["bibliography_audit_clean"]["detail"]

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

    def test_review_preflight_peer_review_strict_does_not_swallow_reproducibility_validator_bugs(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import gpd.core.reproducibility as reproducibility_module

        def _raise_validator_bug(payload: object):
            raise RuntimeError("validator bug")

        monkeypatch.setattr(reproducibility_module, "validate_reproducibility_manifest", _raise_validator_bug)

        with pytest.raises(RuntimeError, match="validator bug"):
            runner.invoke(
                app,
                ["--raw", "validate", "review-preflight", "peer-review", "--strict"],
                catch_exceptions=False,
            )

    def test_review_preflight_arxiv_submission_strict_requires_artifact_audits(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / "ARTIFACT-MANIFEST.json").unlink()

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["artifact_manifest"]["passed"] is False
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["compiled_manuscript"]["passed"] is True

    def test_review_preflight_arxiv_submission_strict_requires_bibliography_audit(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / "BIBLIOGRAPHY-AUDIT.json").unlink()

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["artifact_manifest"]["passed"] is True
        assert checks["bibliography_audit"]["passed"] is False
        assert checks["compiled_manuscript"]["passed"] is True

    def test_review_preflight_arxiv_submission_enforces_theorem_bearing_proof_review_without_strict(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(
            gpd_project,
            final_recommendation="accept",
            proof_bearing=True,
            write_proof_redteam=False,
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["artifact_manifest"]["passed"] is True
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["review_ledger"]["passed"] is True
        assert checks["referee_decision"]["passed"] is True
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is True
        assert "PROOF-REDTEAM.md" in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_arxiv_submission_bypasses_auxiliary_proof_review_for_non_theorem_manuscripts(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(
            gpd_project,
            final_recommendation="accept",
            proof_bearing=False,
            write_proof_redteam=False,
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is True
        assert checks["manuscript_proof_review"]["blocking"] is False
        assert "PROOF-REDTEAM" not in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_arxiv_submission_uses_theorem_bearing_claim_inventory_when_math_anchor_is_not_theorem_bearing(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(
            gpd_project,
            final_recommendation="accept",
            proof_bearing=False,
            write_proof_redteam=False,
        )
        claims_path = gpd_project / "GPD" / "review" / "CLAIMS.json"
        claims_payload = json.loads(claims_path.read_text(encoding="utf-8"))
        claims_payload["claims"][0]["claim_kind"] = "theorem"
        claims_payload["claims"][0]["text"] = "For every r_0 > 0, the orbit intersects the target annulus."
        claims_payload["claims"][0]["theorem_assumptions"] = ["chi > 0"]
        claims_payload["claims"][0]["theorem_parameters"] = ["r_0"]
        claims_path.write_text(json.dumps(claims_payload), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["review_ledger"]["passed"] is True
        assert checks["referee_decision"]["passed"] is True
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is True
        assert "not required" not in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_arxiv_submission_detects_theorem_bearing_manuscript_text_without_theorem_claim_inventory(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(
            gpd_project,
            final_recommendation="accept",
            proof_bearing=False,
            write_proof_redteam=False,
        )
        _manuscript_entrypoint_path(gpd_project).write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\begin{lemma}For every r_0 > 0, the orbit intersects the target annulus.\\end{lemma}\n"
            "\\begin{proof}The proof is omitted.\\end{proof}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is True
        assert "not required" not in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_arxiv_submission_rejects_theorem_claim_inventory_omitted_from_math_review(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(
            gpd_project,
            final_recommendation="accept",
            proof_bearing=False,
            write_proof_redteam=False,
        )
        claims_path = gpd_project / "GPD" / "review" / "CLAIMS.json"
        claims_payload = json.loads(claims_path.read_text(encoding="utf-8"))
        claims_payload["claims"][0]["claim_kind"] = "theorem"
        claims_payload["claims"][0]["text"] = "For every r_0 > 0, the orbit intersects the target annulus."
        claims_payload["claims"][0]["theorem_assumptions"] = ["chi > 0"]
        claims_payload["claims"][0]["theorem_parameters"] = ["r_0"]
        claims_path.write_text(json.dumps(claims_payload), encoding="utf-8")
        math_stage_path = gpd_project / "GPD" / "review" / "STAGE-math.json"
        math_stage_payload = json.loads(math_stage_path.read_text(encoding="utf-8"))
        math_stage_payload["claims_reviewed"] = []
        math_stage_payload["proof_audits"] = []
        math_stage_path.write_text(json.dumps(math_stage_payload), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is True
        assert "claims_reviewed" in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_arxiv_submission_uses_latest_round_specific_theorem_proof_review(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(
            gpd_project,
            final_recommendation="accept",
            round_number=1,
            proof_bearing=True,
            write_proof_redteam=True,
        )
        _write_publication_review_outcome(
            gpd_project,
            final_recommendation="accept",
            round_number=2,
            proof_bearing=True,
            write_proof_redteam=False,
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert "round 2" in checks["review_ledger"]["detail"]
        assert "round 2" in checks["referee_decision"]["detail"]
        assert checks["manuscript_proof_review"]["passed"] is False
        assert checks["manuscript_proof_review"]["blocking"] is True
        assert "PROOF-REDTEAM-R2.md" in checks["manuscript_proof_review"]["detail"]

    def test_review_preflight_arxiv_submission_rejects_accepted_review_after_manuscript_edit(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(
            gpd_project,
            final_recommendation="accept",
            proof_bearing=False,
        )
        manuscript_path = canonical_manuscript_path(gpd_project)
        manuscript_path.write_text(
            "\\documentclass{article}\n\\begin{document}\nEdited after review.\n\\end{document}\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["referee_decision_valid"]["passed"] is False
        assert "manuscript_sha256 does not match the active manuscript snapshot" in checks["referee_decision_valid"]["detail"]

    def test_review_preflight_arxiv_submission_strict_blocks_semantically_dirty_bibliography_audit(
        self,
        gpd_project: Path,
    ) -> None:
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
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["bibliography_audit"]["passed"] is True
        assert checks["bibliography_audit_clean"]["passed"] is False
        assert "bibliography audit still has unresolved" in checks["bibliography_audit_clean"]["detail"]

    def test_review_preflight_arxiv_submission_strict_blocks_publication_blockers(self, gpd_project: Path) -> None:
        planning = gpd_project / "GPD"
        state = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        state["blockers"] = ["Publication blocker: unresolved venue fit"]
        (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["compiled_manuscript"]["passed"] is True
        assert checks["publication_blockers"]["passed"] is False
        assert checks["publication_blockers"]["blocking"] is True

    def test_review_preflight_arxiv_submission_strict_blocks_latest_major_revision_decision(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(gpd_project, final_recommendation="major_revision")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["review_ledger"]["passed"] is True
        assert checks["referee_decision"]["passed"] is True
        assert checks["review_ledger_valid"]["passed"] is True
        assert checks["referee_decision_valid"]["passed"] is True
        assert checks["publication_review_outcome"]["passed"] is False
        assert checks["publication_review_outcome"]["blocking"] is True

    def test_review_preflight_arxiv_submission_strict_blocks_latest_open_blocking_review_issues(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(
            gpd_project,
            final_recommendation="minor_revision",
            blocking_issue_ids=["REF-001"],
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["review_ledger_valid"]["passed"] is True
        assert checks["referee_decision_valid"]["passed"] is False
        assert "publication_review_outcome" not in checks

    def test_review_preflight_arxiv_submission_strict_uses_latest_review_round_when_review_artifacts_exist(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(gpd_project, final_recommendation="accept", round_number=1)
        _write_publication_review_outcome(gpd_project, final_recommendation="major_revision", round_number=2)

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert "round 2" in checks["review_ledger"]["detail"]
        assert "round 2" in checks["referee_decision"]["detail"]
        assert checks["publication_review_outcome"]["passed"] is False

    def test_review_preflight_arxiv_submission_strict_requires_matching_latest_review_pair(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(gpd_project, final_recommendation="accept", round_number=1)
        _write_publication_review_outcome(gpd_project, final_recommendation="accept", round_number=2)
        (gpd_project / "GPD" / "review" / "REVIEW-LEDGER-R2.json").unlink()

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["review_ledger"]["passed"] is False
        assert "round 2" in checks["review_ledger"]["detail"]

    def test_review_preflight_arxiv_submission_strict_rejects_stale_review_artifact_manuscript_paths(
        self,
        gpd_project: Path,
    ) -> None:
        _write_publication_review_outcome(
            gpd_project,
            final_recommendation="accept",
            manuscript_path=_manuscript_entrypoint_relpath(root_name="submission"),
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["review_ledger_valid"]["passed"] is False
        assert checks["referee_decision_valid"]["passed"] is False

    def test_review_preflight_arxiv_submission_ignores_generic_non_publication_blockers(self, gpd_project: Path) -> None:
        planning = gpd_project / "GPD"
        state = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        state["blockers"] = ["IR divergence in loop integral"]
        (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["publication_blockers"]["passed"] is True
        assert checks["review_ledger"]["passed"] is False
        assert checks["referee_decision"]["passed"] is False

    def test_review_preflight_arxiv_submission_rejects_explicit_non_default_paper_directory(
        self,
        gpd_project: Path,
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()

        submission_dir = gpd_project / "submission"
        submission_dir.mkdir()
        (submission_dir / _CANONICAL_MANUSCRIPT_BASENAME).write_text(
            "\\documentclass{article}\n\\begin{document}\nSubmission manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )
        (submission_dir / _CANONICAL_MANUSCRIPT_PDF_BASENAME).write_bytes(b"%PDF-1.4\n% fake arxiv submission pdf\n")
        for artifact_name in ("PAPER-CONFIG.json", "ARTIFACT-MANIFEST.json", "BIBLIOGRAPHY-AUDIT.json"):
            (submission_dir / artifact_name).write_text(
                (paper_dir / artifact_name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert "must stay under `paper/`, `manuscript/`, or `draft/`" in checks["manuscript"]["detail"]

    def test_review_preflight_arxiv_submission_rejects_explicit_manuscript_file(self, gpd_project: Path) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()

        submission_dir = gpd_project / "submission"
        submission_dir.mkdir()
        (submission_dir / _CANONICAL_MANUSCRIPT_BASENAME).write_text(
            "\\documentclass{article}\n\\begin{document}\nSubmission manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )
        (submission_dir / _CANONICAL_MANUSCRIPT_PDF_BASENAME).write_bytes(b"%PDF-1.4\n% fake arxiv submission pdf\n")
        for artifact_name in ("PAPER-CONFIG.json", "ARTIFACT-MANIFEST.json", "BIBLIOGRAPHY-AUDIT.json"):
            (submission_dir / artifact_name).write_text(
                (paper_dir / artifact_name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        result = runner.invoke(
            app,
            [
                "--raw",
                "validate",
                "review-preflight",
                "arxiv-submission",
                _manuscript_entrypoint_relpath(root_name="submission"),
                "--strict",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert "must stay under `paper/`, `manuscript/`, or `draft/`" in checks["manuscript"]["detail"]

    def test_command_context_arxiv_submission_rejects_explicit_target_outside_supported_roots(
        self,
        gpd_project: Path,
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()
        submission_dir = gpd_project / "submission"
        submission_dir.mkdir()
        (submission_dir / _CANONICAL_MANUSCRIPT_BASENAME).write_text(
            "\\documentclass{article}\n\\begin{document}\nSubmission manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )
        (submission_dir / "ARTIFACT-MANIFEST.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "paper_title": "Submission Manuscript",
                    "journal": "jhep",
                    "created_at": "2026-03-10T00:00:00+00:00",
                    "artifacts": [
                        {
                            "artifact_id": "manuscript",
                            "category": "tex",
                            "path": _CANONICAL_MANUSCRIPT_BASENAME,
                            "sha256": compute_sha256(submission_dir / _CANONICAL_MANUSCRIPT_BASENAME),
                            "produced_by": "tests.test_cli_commands",
                            "sources": [],
                            "metadata": {"role": "manuscript"},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "command-context", "arxiv-submission", "submission"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["required_files"]["passed"] is False
        assert "explicit manuscript target satisfies command context" not in checks["required_files"]["detail"]

    def test_command_context_peer_review_resolves_relative_manuscript_from_nested_workspace(
        self,
        gpd_project: Path,
    ) -> None:
        nested = gpd_project / "notes"
        nested.mkdir()

        result = runner.invoke(
            app,
            [
                "--raw",
                "--cwd",
                str(nested),
                "validate",
                "command-context",
                "peer-review",
                f"../paper/{_CANONICAL_MANUSCRIPT_BASENAME}",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is True
        assert checks["required_files"]["passed"] is True
        assert "../paper/" not in checks["manuscript"]["detail"]

    def test_command_context_peer_review_rejects_explicit_manuscript_outside_supported_roots(
        self,
        gpd_project: Path,
    ) -> None:
        submission_dir = gpd_project / "submission"
        submission_dir.mkdir()
        (_manuscript_entrypoint_path(gpd_project, root_name="submission")).write_text(
            "\\documentclass{article}\n\\begin{document}\nSubmission manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "--raw",
                "validate",
                "command-context",
                "peer-review",
                _manuscript_entrypoint_relpath(root_name="submission"),
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert checks["manuscript"]["detail"] == (
            "explicit manuscript target must stay under `paper/`, `manuscript/`, or `draft/` inside the current project"
        )

    def test_review_preflight_arxiv_submission_strict_does_not_fall_back_to_legacy_gpd_paper_artifacts(
        self,
        gpd_project: Path,
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()

        submission_dir = gpd_project / "submission"
        submission_dir.mkdir()
        (submission_dir / _CANONICAL_MANUSCRIPT_BASENAME).write_text(
            "\\documentclass{article}\n\\begin{document}\nSubmission manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )
        (submission_dir / _CANONICAL_MANUSCRIPT_PDF_BASENAME).write_bytes(b"%PDF-1.4\n% fake arxiv submission pdf\n")
        _write_legacy_publication_artifacts(
            gpd_project,
            ("PAPER-CONFIG.json", "ARTIFACT-MANIFEST.json", "BIBLIOGRAPHY-AUDIT.json"),
        )

        result = runner.invoke(
            app,
            [
                "--raw",
                "validate",
                "review-preflight",
                "arxiv-submission",
                _manuscript_entrypoint_relpath(root_name="submission"),
                "--strict",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert "must stay under `paper/`, `manuscript/`, or `draft/`" in checks["manuscript"]["detail"]

    def test_review_preflight_arxiv_submission_rejects_explicit_markdown_manuscript_file(
        self,
        gpd_project: Path,
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()

        submission_dir = gpd_project / "submission"
        submission_dir.mkdir()
        (submission_dir / _CANONICAL_MARKDOWN_BASENAME).write_text("# Markdown manuscript\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "--raw",
                "validate",
                "review-preflight",
                "arxiv-submission",
                _manuscript_entrypoint_relpath(root_name="submission", suffix=".md"),
                "--strict",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert "must stay under `paper/`, `manuscript/`, or `draft/`" in checks["manuscript"]["detail"]

    def test_review_preflight_arxiv_submission_rejects_directory_with_markdown_entrypoint(
        self,
        gpd_project: Path,
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()

        submission_dir = gpd_project / "submission"
        submission_dir.mkdir()
        (submission_dir / _CANONICAL_MARKDOWN_BASENAME).write_text("# Markdown manuscript\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert "must stay under `paper/`, `manuscript/`, or `draft/`" in checks["manuscript"]["detail"]

    def test_review_preflight_arxiv_submission_rejects_explicit_directory_without_main_entrypoint(
        self,
        gpd_project: Path,
    ) -> None:
        paper_dir = gpd_project / "paper"
        submission_dir = gpd_project / "submission"
        submission_dir.mkdir()
        (submission_dir / "alt.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\nSubmission manuscript.\n\\end{document}\n",
            encoding="utf-8",
        )
        (submission_dir / "alt.pdf").write_bytes(b"%PDF-1.4\n% fake arxiv submission pdf\n")
        for artifact_name in ("PAPER-CONFIG.json", "ARTIFACT-MANIFEST.json", "BIBLIOGRAPHY-AUDIT.json"):
            (submission_dir / artifact_name).write_text(
                (paper_dir / artifact_name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert "must stay under `paper/`, `manuscript/`, or `draft/`" in checks["manuscript"]["detail"]

    def test_review_preflight_arxiv_submission_default_markdown_only_project_fails_manuscript_check(
        self,
        gpd_project: Path,
    ) -> None:
        paper_dir = gpd_project / "paper"
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).unlink()
        (paper_dir / _CANONICAL_MARKDOWN_BASENAME).write_text("# Markdown manuscript\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--raw", "validate", "review-preflight", "arxiv-submission", "--strict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        checks = {check["name"]: check for check in payload["checks"]}
        assert checks["manuscript"]["passed"] is False
        assert "no LaTeX manuscript entrypoint found under paper/, manuscript/, or draft/" in checks["manuscript"]["detail"]

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

    def test_validate_paper_quality_command_blocks_invalid_ledger_integrity_flags(self, gpd_project: Path) -> None:
        quality_path = gpd_project / "paper-quality-ledger-blocked.json"
        quality_path.write_text(
            json.dumps(
                {
                    "title": "Ledger blocked paper",
                    "journal": "generic",
                    "verification": {
                        "report_passed": {"passed": True},
                        "contract_targets_verified": {"satisfied": 1, "total": 1},
                        "key_result_confidences": ["INDEPENDENTLY CONFIRMED"],
                    },
                    "journal_extra_checks": {
                        "contract_results_parse_ok": False,
                        "contract_results_alignment_ok": False,
                        "comparison_verdicts_valid": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(app, ["--raw", "validate", "paper-quality", str(quality_path)], catch_exceptions=False)

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        blocker_checks = {issue["check"] for issue in payload["blocking_issues"]}
        assert "contract_results_parse_ok" in blocker_checks
        assert "contract_results_alignment_ok" in blocker_checks
        assert "comparison_verdicts_valid" in blocker_checks

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
        (paper_dir / _CANONICAL_MANUSCRIPT_BASENAME).write_text(
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
        (paper_dir / "PAPER-CONFIG.json").write_text(
            json.dumps(
                {
                    "title": "Benchmark Paper",
                    "journal": "jhep",
                    "output_filename": CANONICAL_MANUSCRIPT_STEM,
                    "authors": [{"name": "A. Researcher"}],
                    "abstract": "Benchmark abstract.",
                    "sections": [{"heading": "Introduction", "content": "Intro."}],
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
        tracker_dir = gpd_project / "paper"
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
            "      - GPD/comparisons/benchmark-COMPARISON.md\n"
            "---\n\n"
            "# Figure Tracker\n",
            encoding="utf-8",
        )
        comparison_dir = gpd_project / "GPD" / "comparisons"
        comparison_dir.mkdir(parents=True, exist_ok=True)
        (comparison_dir / "benchmark-COMPARISON.md").write_text(
            "---\n"
            "comparison_kind: benchmark\n"
            "comparison_sources:\n"
            "  - label: theory\n"
            "    kind: summary\n"
            "    path: GPD/phases/01-benchmark/01-SUMMARY.md\n"
            "  - label: benchmark\n"
            "    kind: verification\n"
            "    path: GPD/phases/01-benchmark/01-VERIFICATION.md\n"
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
        phase_dir = gpd_project / "GPD" / "phases" / "01-benchmark"
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
        assert payload["journal"] == "jhep"
        assert payload["categories"]["verification"]["checks"]["contract_targets_verified"] > 0
        assert payload["categories"]["results"]["checks"]["comparison_with_prior_work_present"] > 0

    def test_validate_referee_decision_command_accepts_consistent_major_revision(self, gpd_project: Path) -> None:
        _write_review_stage_artifacts(gpd_project)
        decision_path = gpd_project / "referee-decision.json"
        decision_path.write_text(
            json.dumps(
                {
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
                    "target_journal": "jhep",
                    "final_recommendation": "major_revision",
                    "final_confidence": "high",
                    "stage_artifacts": [
                        "GPD/review/STAGE-reader.json",
                        "GPD/review/STAGE-literature.json",
                        "GPD/review/STAGE-math.json",
                        "GPD/review/STAGE-physics.json",
                        "GPD/review/STAGE-interestingness.json",
                    ],
                    "central_claims_supported": True,
                    "claim_scope_proportionate_to_evidence": False,
                    "physical_assumptions_justified": True,
                    "proof_audit_coverage_complete": True,
                    "theorem_proof_alignment_adequate": True,
                    "unsupported_claims_are_central": False,
                    "reframing_possible_without_new_results": True,
                    "mathematical_correctness": "adequate",
                    "novelty": "adequate",
                    "significance": "weak",
                    "venue_fit": "adequate",
                    "literature_positioning": "adequate",
                    "unresolved_major_issues": 0,
                    "unresolved_minor_issues": 0,
                    "blocking_issue_ids": [],
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
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
                    "issues": [],
                }
            ),
            encoding="utf-8",
        )
        ledger_path = gpd_project / "review-ledger-extra-artifact.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
                    "issues": [],
                }
            ),
            encoding="utf-8",
        )
        ledger_path = gpd_project / "review-ledger-extra-artifact.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
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

    def test_validate_referee_decision_help_surfaces_strict_policy_semantics(self) -> None:
        result = runner.invoke(app, ["validate", "referee-decision", "--help"], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "Require staged peer-review artifact coverage" in result.output
        assert "recommendation-floor consistency" in result.output
        assert "policy-driving inputs" in result.output
        assert "all journals" in result.output

    def test_validate_referee_decision_strict_requires_matching_ledger(self, gpd_project: Path) -> None:
        _write_review_stage_artifacts(gpd_project)
        decision_path = gpd_project / "referee-decision-strict-no-ledger.json"
        decision_path.write_text(
            json.dumps(
                {
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
                    "target_journal": "jhep",
                    "final_recommendation": "major_revision",
                    "stage_artifacts": [
                        "GPD/review/STAGE-reader.json",
                        "GPD/review/STAGE-literature.json",
                        "GPD/review/STAGE-math.json",
                        "GPD/review/STAGE-physics.json",
                        "GPD/review/STAGE-interestingness.json",
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
        assert "Strict referee-decision validation requires --ledger" in payload["error"]

    def test_validate_referee_decision_command_accepts_round_suffixed_stage_artifacts(self, gpd_project: Path) -> None:
        _write_review_stage_artifacts(
            gpd_project,
            artifact_names=(
                "STAGE-reader-R2.json",
                "STAGE-literature-R2.json",
                "STAGE-math-R2.json",
                "STAGE-physics-R2.json",
                "STAGE-interestingness-R2.json",
            ),
            manuscript_path=_manuscript_entrypoint_relpath(root_name="submission"),
        )
        decision_path = gpd_project / "referee-decision-r2.json"
        decision_path.write_text(
            json.dumps(
                {
                    "manuscript_path": _manuscript_entrypoint_relpath(root_name="submission"),
                    "target_journal": "jhep",
                    "final_recommendation": "major_revision",
                    "final_confidence": "high",
                    "stage_artifacts": [
                        "GPD/review/STAGE-reader-R2.json",
                        "GPD/review/STAGE-literature-R2.json",
                        "GPD/review/STAGE-math-R2.json",
                        "GPD/review/STAGE-physics-R2.json",
                        "GPD/review/STAGE-interestingness-R2.json",
                    ],
                    "central_claims_supported": True,
                    "claim_scope_proportionate_to_evidence": True,
                    "physical_assumptions_justified": True,
                    "proof_audit_coverage_complete": True,
                    "theorem_proof_alignment_adequate": True,
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
        ledger_path = gpd_project / "review-ledger-r2.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 2,
                    "manuscript_path": _manuscript_entrypoint_relpath(root_name="submission"),
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

    def test_validate_referee_decision_command_rejects_wrong_existing_artifact_set(self, gpd_project: Path) -> None:
        _write_review_stage_artifacts(
            gpd_project,
            artifact_names=(
                "CLAIMS.json",
                "REVIEW-LEDGER.json",
                "REFEREE-DECISION.json",
                "STAGE-meta.json",
                "STAGE-summary.json",
            ),
        )
        decision_path = gpd_project / "referee-decision-wrong-artifacts.json"
        decision_path.write_text(
            json.dumps(
                {
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
                    "target_journal": "jhep",
                    "final_recommendation": "major_revision",
                    "stage_artifacts": [
                        "GPD/review/CLAIMS.json",
                        "GPD/review/REVIEW-LEDGER.json",
                        "GPD/review/REFEREE-DECISION.json",
                        "GPD/review/STAGE-meta.json",
                        "GPD/review/STAGE-summary.json",
                    ],
                }
            ),
            encoding="utf-8",
        )
        ledger_path = gpd_project / "review-ledger-extra-artifact.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
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

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert any("canonical five specialist stage artifacts" in reason for reason in payload["reasons"])

    def test_validate_referee_decision_command_rejects_extra_noncanonical_stage_artifact(self, gpd_project: Path) -> None:
        _write_review_stage_artifacts(gpd_project)
        decision_path = gpd_project / "referee-decision-extra-artifact.json"
        decision_path.write_text(
            json.dumps(
                {
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
                    "target_journal": "jhep",
                    "final_recommendation": "major_revision",
                    "stage_artifacts": [
                        "GPD/review/STAGE-reader.json",
                        "GPD/review/STAGE-literature.json",
                        "GPD/review/STAGE-math.json",
                        "GPD/review/STAGE-physics.json",
                        "GPD/review/STAGE-interestingness.json",
                        "GPD/review/STAGE-meta.json",
                    ],
                }
            ),
            encoding="utf-8",
        )
        ledger_path = gpd_project / "review-ledger-extra-artifact.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
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

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert any("rejects noncanonical stage artifacts" in reason for reason in payload["reasons"])
        assert any("STAGE-meta.json" in reason for reason in payload["reasons"])

    def test_validate_referee_decision_command_blocks_overly_positive_prl_decision(self, gpd_project: Path) -> None:
        _write_review_stage_artifacts(gpd_project)
        decision_path = gpd_project / "referee-decision-prl.json"
        decision_path.write_text(
            json.dumps(
                {
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
                    "target_journal": "prl",
                    "final_recommendation": "minor_revision",
                    "stage_artifacts": [
                        "GPD/review/STAGE-reader.json",
                        "GPD/review/STAGE-literature.json",
                        "GPD/review/STAGE-math.json",
                        "GPD/review/STAGE-physics.json",
                        "GPD/review/STAGE-interestingness.json",
                    ],
                    "novelty": "adequate",
                    "significance": "weak",
                    "venue_fit": "weak",
                }
            ),
            encoding="utf-8",
        )
        ledger_path = gpd_project / "review-ledger-prl.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
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

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert payload["most_positive_allowed_recommendation"] == "reject"

    def test_validate_referee_decision_command_rejects_missing_stage_artifacts(self, gpd_project: Path) -> None:
        decision_path = gpd_project / "referee-decision-missing-artifacts.json"
        decision_path.write_text(
            json.dumps(
                {
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
                    "target_journal": "jhep",
                    "final_recommendation": "major_revision",
                    "stage_artifacts": [
                        "GPD/review/STAGE-reader.json",
                        "GPD/review/STAGE-literature.json",
                        "GPD/review/STAGE-math.json",
                        "GPD/review/STAGE-physics.json",
                        "GPD/review/STAGE-interestingness.json",
                    ],
                }
            ),
            encoding="utf-8",
        )
        ledger_path = gpd_project / "review-ledger-missing-artifacts.json"
        ledger_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "round": 1,
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
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
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
                    "target_journal": "jhep",
                    "final_recommendation": "major_revision",
                    "stage_artifacts": [
                        "GPD/review/STAGE-reader.json",
                        "GPD/review/STAGE-literature.json",
                        "GPD/review/STAGE-math.json",
                        "GPD/review/STAGE-physics.json",
                        "GPD/review/STAGE-interestingness.json",
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
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
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
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
                    "target_journal": "jhep",
                    "final_recommendation": "major_revision",
                    "stage_artifacts": [
                        "GPD/review/STAGE-reader.json",
                        "GPD/review/STAGE-literature.json",
                        "GPD/review/STAGE-math.json",
                        "GPD/review/STAGE-physics.json",
                        "GPD/review/STAGE-interestingness.json",
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
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
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
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
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
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
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
                    "manuscript_path": _CANONICAL_MANUSCRIPT_REL,
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
        phase_dir = gpd_project / "GPD" / "phases" / "01-benchmark"
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

    def test_validate_plan_contract_command_rejects_ambiguous_contract_target_ids(self, gpd_project: Path) -> None:
        phase_dir = gpd_project / "GPD" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True, exist_ok=True)
        plan_path = phase_dir / "01-01-PLAN.md"
        plan_path.write_text(
            (FIXTURES_DIR / "plan_with_contract.md")
            .read_text(encoding="utf-8")
            .replace("deliverables: [deliv-figure]", "deliverables: [claim-benchmark]", 1)
            .replace("    - id: deliv-figure", "    - id: claim-benchmark", 1)
            .replace(
                "      evidence_required: [deliv-figure, ref-benchmark]",
                "      evidence_required: [claim-benchmark, ref-benchmark]",
                1,
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["--raw", "validate", "plan-contract", str(plan_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert any(
            "contract: contract id claim-benchmark is reused across claim, deliverable; "
            "target resolution is ambiguous" in error
            for error in payload["errors"]
        )

    def test_validate_plan_preflight_command_blocks_missing_required_wolfram(self, gpd_project: Path, monkeypatch) -> None:
        phase_dir = gpd_project / "GPD" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True, exist_ok=True)
        plan_path = phase_dir / "01-01-PLAN.md"
        plan_path.write_text(
            (FIXTURES_DIR / "plan_with_contract.md")
            .read_text(encoding="utf-8")
            .replace(
                "interactive: false\n",
                "interactive: false\n"
                "tool_requirements:\n"
                "  - id: wolfram-cas\n"
                "    tool: wolfram\n"
                "    purpose: Symbolic tensor reduction\n",
                1,
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda binary: None)

        result = runner.invoke(
            app,
            ["--raw", "validate", "plan-preflight", str(plan_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["validation_passed"] is True
        assert payload["passed"] is False
        assert payload["requirements"][0]["tool"] == "wolfram"
        assert payload["requirements"][0]["blocking"] is True

    def test_validate_plan_preflight_command_allows_missing_optional_wolfram_with_fallback(
        self,
        gpd_project: Path,
        monkeypatch,
    ) -> None:
        phase_dir = gpd_project / "GPD" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True, exist_ok=True)
        plan_path = phase_dir / "01-01-PLAN.md"
        plan_path.write_text(
            (FIXTURES_DIR / "plan_with_contract.md")
            .read_text(encoding="utf-8")
            .replace(
                "interactive: false\n",
                "interactive: false\n"
                "tool_requirements:\n"
                "  - id: wolfram-cas\n"
                "    tool: mathematica\n"
                "    purpose: Symbolic tensor reduction\n"
                "    required: false\n"
                "    fallback: Use SymPy instead\n",
                1,
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda binary: None)

        result = runner.invoke(
            app,
            ["--raw", "validate", "plan-preflight", str(plan_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["validation_passed"] is True
        assert payload["passed"] is True
        assert payload["requirements"][0]["tool"] == "wolfram"
        assert payload["requirements"][0]["blocking"] is False
        assert "license state are not proven" in payload["warnings"][0]

    @pytest.mark.parametrize(("command_args"), [("integrations", "status", "wolfram")])
    def test_integrations_surface_smoke(self, command_args: tuple[str, ...]) -> None:
        _invoke(*command_args)

    def test_validate_summary_contract_command_rejects_unknown_contract_ids(self, gpd_project: Path) -> None:
        phase_dir = gpd_project / "GPD" / "phases" / "01-benchmark"
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
        phase_dir = gpd_project / "GPD" / "phases" / "01-benchmark"
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
        phase_dir = gpd_project / "GPD" / "phases" / "01-benchmark"
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
            "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract\n"
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
        assert payload["reproducibility_ready"] is True
        assert "ready_for_review" not in payload

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
        assert payload["schema_reference"].endswith("paper/reproducibility-manifest.md")
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
        assert payload["reproducibility_ready"] is False
        assert payload["schema_reference"].endswith("paper/reproducibility-manifest.md")
        assert "ready_for_review" not in payload

    def test_validate_reproducibility_manifest_can_emit_kernel_verdict(self, gpd_project: Path) -> None:
        manifest_path = gpd_project / "reproducibility-kernel.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "paper_title": "Kernel Ready",
                    "date": "2026-03-10",
                    "environment": {
                        "python_version": "3.12.1",
                        "package_manager": "uv",
                        "required_packages": [{"package": "numpy", "version": "1.26.4"}],
                        "lock_file": "uv.lock",
                        "system_requirements": {},
                    },
                    "execution_steps": [{"name": "run", "command": "python scripts/run.py", "stochastic": True}],
                    "expected_results": [{"quantity": "x", "expected_value": "1", "tolerance": "0.1", "script": "scripts/run.py"}],
                    "output_files": [{"path": "results/out.json", "checksum_sha256": "a" * 64}],
                    "resource_requirements": [{"step": "run", "cpu_cores": 1, "memory_gb": 1.0}],
                    "random_seeds": [{"computation": "run", "seed": "42"}],
                    "seeding_strategy": "Fixed seed",
                    "verification_steps": ["rerun pipeline", "compare outputs", "inspect artifacts"],
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
            ["--raw", "validate", "reproducibility-manifest", str(manifest_path), "--kernel-verdict"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["validation"]["valid"] is True
        assert payload["validation"]["reproducibility_ready"] is True
        assert "ready_for_review" not in payload["validation"]
        assert payload["kernel_verdict"]["overall"] == "PASS"
        assert payload["kernel_verdict"]["verdict_hash"].startswith("sha256:")


def test_cli_import_and_help_lookup_failure_paths(monkeypatch: pytest.MonkeyPatch) -> None:
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

    def _raise_programmer_error() -> list[str]:
        raise TypeError("catalog bug")

    original_cli = sys.modules.get("gpd.cli")
    monkeypatch.setattr(adapters_module, "list_runtimes", _raise_programmer_error)
    sys.modules.pop("gpd.cli", None)

    try:
        with pytest.raises(TypeError, match="catalog bug"):
            importlib.import_module("gpd.cli")
    finally:
        if original_cli is not None:
            sys.modules["gpd.cli"] = original_cli
            gpd_package.cli = original_cli


def test_install_command_smoke_error_paths_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    gpd_project: Path,
) -> None:
    import gpd.adapters as adapters_module

    def _raise_runtime_catalog() -> list[str]:
        raise RuntimeError("catalog offline")

    monkeypatch.setattr(adapters_module, "list_runtimes", _raise_runtime_catalog)

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(gpd_project), "install", "--all"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error"] == "Runtime catalog unavailable during install: catalog offline"
    assert "Traceback" not in result.output

    def assert_raw_install_error(argv: list[str], expected_error: str, setup=None) -> None:
        if setup is not None:
            setup()
        result = runner.invoke(app, ["--raw", "--cwd", str(gpd_project), *argv], catch_exceptions=False)
        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["error"] == expected_error
        assert "Traceback" not in result.output

    assert_raw_install_error(
        ["install"],
        "Raw install requires one or more runtimes or --all",
    )
    assert_raw_install_error(
        ["install", _PRIMARY_RAW_RUNTIME_DESCRIPTOR.runtime_name],
        "Raw install requires --local, --global, or --target-dir",
        setup=lambda: (
            monkeypatch.setattr(adapters_module, "list_runtimes", lambda: [_PRIMARY_RAW_RUNTIME_DESCRIPTOR.runtime_name]),
            monkeypatch.setattr(adapters_module, "get_adapter", lambda runtime_name: object()),
        ),
    )
    assert_raw_install_error(
        ["uninstall", "--all", "--global"],
        "Runtime catalog unavailable during uninstall: catalog offline",
        setup=lambda: monkeypatch.setattr(adapters_module, "list_runtimes", _raise_runtime_catalog),
    )


def test_cli_uninstall_and_resolution_paths(monkeypatch: pytest.MonkeyPatch, gpd_project: Path, tmp_path: Path) -> None:
    import gpd.adapters as adapters_module
    import gpd.cli as cli_module
    import gpd.core.config as config_module

    monkeypatch.setattr(adapters_module, "list_runtimes", lambda: [_PRIMARY_RAW_RUNTIME_DESCRIPTOR.runtime_name])
    monkeypatch.setattr(adapters_module, "get_adapter", lambda runtime_name: object())

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(gpd_project), "uninstall", _PRIMARY_RAW_RUNTIME_DESCRIPTOR.runtime_name],
        catch_exceptions=False,
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error"] == "Raw uninstall requires --local, --global, or --target-dir"
    assert "Traceback" not in result.output

    monkeypatch.setattr(
        adapters_module,
        "get_adapter",
        lambda runtime_name: (_ for _ in ()).throw(RuntimeError("adapter offline")),
    )
    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(gpd_project),
            "uninstall",
            _PRIMARY_RAW_RUNTIME_DESCRIPTOR.runtime_name,
            "--target-dir",
            str(gpd_project / _PRIMARY_RAW_RUNTIME_DESCRIPTOR.config_dir_name),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert (
        payload["error"]
        == f"Runtime adapter unavailable for '{_PRIMARY_RAW_RUNTIME_DESCRIPTOR.runtime_name}' during uninstall: adapter offline"
    )
    assert "Traceback" not in result.output

    alias = next(
        value for value in _ALIASABLE_RUNTIME_DESCRIPTOR.selection_aliases if value != _ALIASABLE_RUNTIME_DESCRIPTOR.runtime_name
    )
    monkeypatch.setattr(cli_module, "_supported_runtime_names", list_runtime_names)
    monkeypatch.setattr(config_module, "validate_agent_name", lambda agent_name: None)
    monkeypatch.setattr(config_module, "resolve_model", lambda cwd, agent_name, runtime=None: runtime)
    result = runner.invoke(app, ["resolve-model", "gpd-executor", "--runtime", alias], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert _ALIASABLE_RUNTIME_DESCRIPTOR.runtime_name in result.output

    cwd = tmp_path / "workspace"
    cwd.mkdir()
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    canonical_target = global_dir / _PRIMARY_RAW_RUNTIME_DESCRIPTOR.config_dir_name
    canonical_target.mkdir()
    tricky_target = global_dir / "nested" / ".." / _PRIMARY_RAW_RUNTIME_DESCRIPTOR.config_dir_name

    class _FakeAdapter:
        def resolve_target_dir(self, is_global: bool, cwd: Path | None = None) -> Path:
            del cwd
            return canonical_target if is_global else tmp_path / "workspace" / _PRIMARY_RAW_RUNTIME_DESCRIPTOR.config_dir_name

    monkeypatch.setattr(cli_module, "_get_cwd", lambda: cwd)
    monkeypatch.setattr(cli_module, "_get_adapter_or_error", lambda runtime_name, action: _FakeAdapter())
    assert cli_module._target_dir_matches_global(_PRIMARY_RAW_RUNTIME_DESCRIPTOR.runtime_name, str(tricky_target), action="install") is True


def test_init_new_project_help_surfaces_stage_option() -> None:
    result = runner.invoke(app, ["init", "new-project", "--help"])
    output = _normalize_cli_output(result.output)

    assert result.exit_code == 0
    assert "--stage" in output
    assert "Load the staged new-project context for a specific" in output
    assert "stage id." in output


def test_init_verify_work_help_surfaces_stage_option() -> None:
    result = runner.invoke(app, ["init", "verify-work", "--help"])
    output = _normalize_cli_output(result.output)

    assert result.exit_code == 0
    assert "--stage" in output
    assert "Load the staged verify-work context for a specific" in output
    assert "stage id." in output


def test_init_plan_phase_help_surfaces_stage_option() -> None:
    result = runner.invoke(app, ["init", "plan-phase", "--help"])
    output = _normalize_cli_output(result.output)

    assert result.exit_code == 0
    assert "--stage" in output
    assert "Load the staged plan-phase context for a specific" in output
    assert "stage id." in output


def test_init_execute_phase_help_surfaces_stage_option() -> None:
    result = runner.invoke(app, ["init", "execute-phase", "--help"])
    output = _normalize_cli_output(result.output)

    assert result.exit_code == 0
    assert "--stage" in output
    assert "Load the staged execute-phase context for a specific" in output
    assert "stage id." in output


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
