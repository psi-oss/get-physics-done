"""Integration tests for all 7 GPD MCP servers.

Calls @mcp.tool() decorated functions with **real** project data on disk
(not mocks).  Each test creates a realistic GPD project fixture with
phases, conventions, and results, then exercises the tool functions
against actual file I/O, parsing, and lookup logic.

Covers:
    conventions_server   — convention_set + convention_check
    state_server         — get_state + advance_plan
    verification_server  — run_check + dimensional_check
    errors_mcp           — list_error_classes + get_error_class
    protocols_server      — list_protocols + get_protocol
    patterns_server       — seed_patterns + lookup_pattern
    skills_server         — list_skills + get_skill
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.state import default_state_dict, generate_state_markdown

# ---------------------------------------------------------------------------
# Shared realistic-project fixture
# ---------------------------------------------------------------------------

_STATE_JSON = {
    "project_reference": {
        "core_research_question": "One-loop vacuum polarization in QED",
        "current_focus": "Compute photon self-energy at NLO",
    },
    "position": {
        "current_phase": "01",
        "current_phase_name": "Setup",
        "total_phases": 3,
        "current_plan": 1,
        "total_plans_in_phase": 3,
        "status": "Executing",
        "last_activity": "2025-06-01",
        "progress_percent": 10,
    },
    "convention_lock": {
        "metric_signature": "(+,-,-,-)",
        "fourier_convention": "physics",
        "natural_units": "natural",
    },
    "decisions": [
        {
            "summary": "Use dim-reg for UV divergences",
            "phase": "01",
            "rationale": "Standard in QFT literature",
        }
    ],
    "intermediate_results": [
        {
            "id": "R1",
            "description": "Leading-order propagator",
            "equation": "D_F(p) = i/(p^2 - m^2 + i*epsilon)",
            "phase": "01",
            "verified": True,
        }
    ],
    "active_calculations": ["Photon self-energy at one loop"],
    "open_questions": ["Correct treatment of gamma_5 in d dimensions?"],
    "blockers": [],
    "approximations": [],
    "propagated_uncertainties": [],
    "pending_todos": [],
    "session": {},
    "performance_metrics": {},
}


_STATE_MD = """\
# Research State

## Project Reference

See: GPD/PROJECT.md

**Core research question:** One-loop vacuum polarization in QED
**Current focus:** Compute photon self-energy at NLO

## Current Position

**Current Phase:** 01
**Current Phase Name:** Setup
**Total Phases:** 3
**Current Plan:** 1
**Total Plans in Phase:** 3
**Status:** Executing
**Last Activity:** 2025-06-01

**Progress:** [\u2588\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591] 10%

## Active Calculations

- Photon self-energy at one loop

## Intermediate Results

- [R1] Leading-order propagator: `D_F(p) = i/(p^2 - m^2 + i*epsilon)` (phase 01, \u2713)

## Open Questions

- Correct treatment of gamma_5 in d dimensions?

## Decisions

- Use dim-reg for UV divergences (phase 01) \u2014 Standard in QFT literature

## Convention Lock

- **metric_signature:** (+,-,-,-)
- **fourier_convention:** physics
- **natural_units:** natural

## Blockers

None yet.

## Pending TODOs

None yet.
"""


def _write_state_with_project_contract(
    tmp_path: Path,
    contract: dict[str, object],
    *,
    current_phase: str = "01",
    status: str = "Executing",
) -> Path:
    project_root = tmp_path / "project"
    gpd_dir = project_root / "GPD"
    gpd_dir.mkdir(parents=True, exist_ok=True)
    state = default_state_dict()
    state["position"]["current_phase"] = current_phase
    state["position"]["status"] = status
    state["project_contract"] = contract
    (gpd_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (gpd_dir / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    return project_root


@pytest.fixture()
def gpd_project(tmp_path: Path) -> Path:
    """Create a realistic GPD project directory tree.

    Layout::
        <tmp>/
          GPD/
            STATE.md
            state.json
            phases/
              01-setup/
                plan-01.md
                plan-02.md
                plan-03.md
                summary-01.md
    """
    planning = tmp_path / "GPD"
    planning.mkdir()

    # Write state files
    (planning / "state.json").write_text(json.dumps(_STATE_JSON, indent=2), encoding="utf-8")
    (planning / "STATE.md").write_text(_STATE_MD, encoding="utf-8")

    # Create phase directory with plans and one summary
    phase_dir = planning / "phases" / "01-setup"
    phase_dir.mkdir(parents=True)
    for i in range(1, 4):
        (phase_dir / f"plan-{i:02d}.md").write_text(f"# Plan {i}\nDo step {i}.", encoding="utf-8")
    (phase_dir / "summary-01.md").write_text("# Summary 1\nCompleted step 1.", encoding="utf-8")

    return tmp_path


# ===========================================================================
# 1. Conventions Server
# ===========================================================================


class TestConventionsServerIntegration:
    """Integration tests for conventions_server tools with real state files."""

    def test_convention_check_real_lock(self, gpd_project: Path):
        from gpd.mcp.servers.conventions_server import convention_check

        lock = _STATE_JSON["convention_lock"]
        result = convention_check(lock)

        assert isinstance(result, dict)
        assert result["valid"] is True
        assert result["missing_critical"] == []
        assert "metric_signature" in result["set_fields"]
        assert result["completeness_percent"] > 0
        assert result["total_standard_fields"] > 0


# ===========================================================================
# 2. State Server
# ===========================================================================


class TestStateServerIntegration:
    """Integration tests for state_server tools with real STATE.md / state.json."""

    def test_get_state_returns_structured_data(self, gpd_project: Path):
        from gpd.mcp.servers.state_server import get_state

        result = get_state(str(gpd_project))

        assert isinstance(result, dict)
        # Should return structured state, not raw markdown
        assert "position" in result
        assert "decisions" in result or "blockers" in result

    def test_get_state_surfaces_canonical_project_contract_metadata(self, tmp_path: Path) -> None:
        from gpd.mcp.servers.state_server import get_state

        contract = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "stage0" / "project_contract.json").read_text(encoding="utf-8"))
        project_root = _write_state_with_project_contract(tmp_path, contract)

        result = get_state(str(project_root))

        assert result["position"]["current_phase"] == "01"
        assert "session" not in result
        assert result["project_contract"]["scope"]["question"] == contract["scope"]["question"]
        assert result["project_contract_load_info"]["status"] == "loaded"
        assert result["project_contract_validation"]["valid"] is True
        assert result["project_contract_gate"]["authoritative"] is True
        assert result["project_contract_gate"]["visible"] is True
        assert result["project_contract_gate"]["repair_required"] is False

    def test_validate_state_on_realistic_project(self, gpd_project: Path):
        from gpd.mcp.servers.state_server import validate_state

        result = validate_state(str(gpd_project))

        assert isinstance(result, dict)
        assert "valid" in result
        assert isinstance(result["issues"], list)


# ===========================================================================
# 3. Verification Server
# ===========================================================================


class TestVerificationServerIntegration:
    """Integration tests for verification_server tools (pure functions)."""

    def test_run_check_dimensional_on_qft_artifact(self):
        from gpd.mcp.servers.verification_server import run_check

        artifact = (
            "The vacuum polarization tensor is "
            "\\Pi^{\\mu\\nu}(q) = (g^{\\mu\\nu} q^2 - q^\\mu q^\\nu) \\Pi(q^2). "
            "Using dimensional regularization with \\hbar = c = 1."
        )
        result = run_check("5.1", "qft", artifact)

        assert result["schema_version"] == 1
        assert result["check_id"] == "5.1"
        assert result["check_name"] == "Dimensional analysis"
        assert result["domain"] == "qft"
        assert result["tier"] >= 1
        assert result["evidence_kind"] == "computational"
        assert isinstance(result["catches"], str)
        # hbar is present -> no automated issue about missing hbar
        assert not any("hbar" in issue for issue in result["automated_issues"])

    def test_dimensional_check_consistent_energy(self):
        from gpd.mcp.servers.verification_server import dimensional_check

        result = dimensional_check(["[M][L]^2[T]^-2 = [M][L]^2[T]^-2"])

        assert result["schema_version"] == 1
        assert result["all_consistent"] is True
        assert result["checked_count"] == 1
        assert result["results"][0]["valid"] is True

    def test_dimensional_check_catches_mismatch(self):
        from gpd.mcp.servers.verification_server import dimensional_check

        # Energy vs momentum: [M][L]^2[T]^-2  !=  [M][L][T]^-1
        result = dimensional_check(["[M][L]^2[T]^-2 = [M][L][T]^-1"])

        assert result["all_consistent"] is False
        mismatches = result["results"][0]["mismatches"]
        assert "L" in mismatches
        assert "T" in mismatches


# ===========================================================================
# 4. Errors MCP Server
# ===========================================================================


class TestErrorsMcpIntegration:
    """Integration tests for errors_mcp using real catalog files on disk."""

    def test_list_error_classes_returns_real_data(self):
        # Force fresh store (reset singleton)
        import gpd.mcp.servers.errors_mcp as _mod
        from gpd.mcp.servers.errors_mcp import list_error_classes

        _mod._store = None

        result = list_error_classes()

        assert isinstance(result, dict)
        assert result["count"] > 0
        assert result["total_classes"] > 0
        assert len(result["error_classes"]) > 0
        # Check that every entry has the expected keys
        entry = result["error_classes"][0]
        assert "id" in entry
        assert "name" in entry
        assert "domain" in entry

    def test_get_error_class_real_entry(self):
        from gpd.mcp.servers.errors_mcp import get_error_class

        # Error class #1 should exist in the core catalog
        result = get_error_class(1)

        assert isinstance(result, dict)
        assert "error" not in result  # no error key means it was found
        assert result["id"] == 1
        assert isinstance(result["name"], str)
        assert len(result["name"]) > 0
        assert "detection_strategy" in result
        assert result["domain"] == "core"


# ===========================================================================
# 5. Protocols Server
# ===========================================================================


class TestProtocolsServerIntegration:
    """Integration tests for protocols_server using real protocol .md files."""

    def test_list_protocols_real_files(self):
        # Force fresh store (reset singleton)
        import gpd.mcp.servers.protocols_server as _mod
        from gpd.mcp.servers.protocols_server import list_protocols

        _mod._store = None

        result = list_protocols()

        assert isinstance(result, dict)
        assert result["count"] > 10  # we saw 47 protocol files
        assert len(result["protocols"]) > 10
        assert len(result["available_domains"]) > 1

        # Each protocol entry must have required keys
        proto = result["protocols"][0]
        for key in ("name", "title", "domain", "tier", "context_cost"):
            assert key in proto, f"Missing key '{key}' in protocol entry"

    def test_get_protocol_perturbation_theory(self):
        from gpd.mcp.servers.protocols_server import get_protocol

        result = get_protocol("perturbation-theory")

        assert isinstance(result, dict)
        assert "error" not in result
        assert result["name"] == "perturbation-theory"
        assert isinstance(result["title"], str)
        assert len(result["title"]) > 0
        assert result["domain"] == "core_derivation"
        assert isinstance(result["steps"], list)
        assert isinstance(result["checkpoints"], list)
        assert isinstance(result["content"], str)
        assert len(result["content"]) > 100

    def test_route_protocol_finds_perturbation(self):
        from gpd.mcp.servers.protocols_server import route_protocol

        result = route_protocol("perturbative QCD one-loop calculation")

        assert isinstance(result, dict)
        assert result["match_count"] >= 1
        names = [p["name"] for p in result["protocols"]]
        assert "perturbation-theory" in names


# ===========================================================================
# 6. Patterns Server
# ===========================================================================


class TestPatternsServerIntegration:
    """Integration tests for patterns_server with real seed data."""

    def test_lookup_pattern_after_seed(self, tmp_path: Path, monkeypatch):
        from gpd.mcp.servers import patterns_server

        lib_root = tmp_path / "patterns"
        monkeypatch.setattr(patterns_server, "_DEFAULT_PATTERNS_ROOT", lib_root)

        patterns_server.seed_patterns()

        result = patterns_server.lookup_pattern(keywords="sign error")

        assert isinstance(result, dict)
        assert result["count"] >= 1
        assert len(result["patterns"]) >= 1


# ===========================================================================
# 7. Skills Server
# ===========================================================================


class TestSkillsServerIntegration:
    """Integration tests for skills_server using real skills on disk."""

    @pytest.fixture(autouse=True)
    def _reset_cache(self):
        """Clear the shared registry cache so each test loads current disk state."""
        from gpd.registry import invalidate_cache

        invalidate_cache()
        yield
        invalidate_cache()

    def test_list_skills_returns_real_canonical_skill_index(self):
        from gpd.mcp.servers.skills_server import list_skills

        result = list_skills()

        assert isinstance(result, dict)
        assert result["count"] > 10  # we saw many gpd-* dirs
        names = {s["name"] for s in result["skills"]}
        # Spot-check known canonical command and agent-backed skills.
        assert "gpd-debug" in names or "gpd-debugger" in names
        assert "gpd-discover" in names
        assert "gpd-peer-review" in names

        # Each skill has expected shape
        for skill in result["skills"]:
            assert "name" in skill
            assert "category" in skill
            assert skill["name"].startswith("gpd-")

    def test_list_skills_by_category_keeps_consistency_checker_visible(self):
        from gpd.mcp.servers.skills_server import list_skills

        result = list_skills(category="verification")

        assert result["count"] > 0
        names = {skill["name"] for skill in result["skills"]}
        assert {"gpd-consistency-checker", "gpd-plan-checker", "gpd-verifier"}.issubset(names)
        assert all(skill["category"] == "verification" for skill in result["skills"])

    def test_debug_command_and_debugger_agent_surfaces_remain_available(self):
        from gpd.mcp.servers.skills_server import get_skill, list_skills

        result = list_skills()
        names = {s["name"] for s in result["skills"]}
        assert {"gpd-debug", "gpd-debugger"}.issubset(names)

        debug_skill = get_skill("gpd-debug")
        debugger_skill = get_skill("gpd-debugger")

        assert debug_skill["allowed_tools_surface"] == "command.allowed-tools"
        assert debug_skill["schema_references"] == []
        assert debug_skill["contract_references"] == []
        assert debug_skill["schema_documents"] == []
        assert debug_skill["contract_documents"] == []
        assert "gpd-debugger" in debug_skill["content"]

        assert debugger_skill["allowed_tools_surface"] == "agent.tools"
        assert debugger_skill["schema_references"] == []
        assert debugger_skill["contract_references"] == []
        assert debugger_skill["schema_documents"] == []
        assert debugger_skill["contract_documents"] == []
        assert debugger_skill["transitive_schema_references"] == []
        assert debugger_skill["transitive_schema_documents"] == []

    def test_get_skill_uses_canonical_command_content(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-help")

        assert isinstance(result, dict)
        assert "error" not in result
        assert result["name"] == "gpd-help"
        assert "Display GPD help by delegating to the workflow-owned help surface." in result["content"]
        assert "/gpd:" not in result["content"]
        assert "gpd-help" in result["content"]
        assert "## Command Requirements" in result["content"]
        assert "Quick Start Extract" in result["content"]
        assert "## Contextual Help" in result["content"]
        assert result["file_count"] == 1
        assert result["allowed_tools_surface"] == "command.allowed-tools"

    def test_get_skill_peer_review_surfaces_transitive_schema_refs_and_typed_contract(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-peer-review")

        assert "error" not in result
        assert any(path.endswith("review-ledger-schema.md") for path in result["schema_references"])
        assert any(path.endswith("referee-decision-schema.md") for path in result["schema_references"])
        assert result["review_contract"] is not None
        assert result["review_contract"]["review_mode"] == "publication"
        assert "required_state" not in result["review_contract"]
        assert result["review_contract"]["conditional_requirements"] == [
            {
                "when": "theorem-bearing claims are present",
                "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                "required_evidence": [],
                "blocking_conditions": [],
                "blocking_preflight_checks": [],
                "stage_artifacts": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            }
        ]
        assert result["context_mode"] == "project-required"
        assert result["project_reentry_capable"] is False
        assert "## Review Contract" in result["content"]
        assert "review_contract:" in result["content"]
        assert "review-contract:" not in result["content"]
        assert "Treat `content` as the wrapper/context surface." in result["loading_hint"]
        assert "Load `schema_documents` and `contract_documents` too when present" in result["loading_hint"]
        assert "It already embeds the model-visible `Command Requirements` section." in result["loading_hint"]

    def test_get_skill_check_proof_surfaces_dedicated_proof_redteam_schema_and_contract_docs(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-check-proof")
        direct_paths = {entry["path"] for entry in result["referenced_files"]}
        schema_documents = {Path(entry["path"]).name: entry for entry in result["schema_documents"]}
        contract_documents = {Path(entry["path"]).name: entry for entry in result["contract_documents"]}

        assert "error" not in result
        assert result["reference_count"] == len(direct_paths)
        assert any(path.endswith("proof-redteam-schema.md") for path in direct_paths)
        assert any(path.endswith("proof-redteam-protocol.md") for path in direct_paths)
        assert any(path.endswith("proof-redteam-schema.md") for path in result["schema_references"])
        assert any(path.endswith("proof-redteam-protocol.md") for path in result["contract_references"])
        assert "proof-redteam-schema.md" in schema_documents
        assert "Proof Redteam" in schema_documents["proof-redteam-schema.md"]["body"]
        assert "proof-redteam-protocol.md" in contract_documents
        assert "Proof Redteam Protocol" in contract_documents["proof-redteam-protocol.md"]["body"]
        assert any(path.endswith("peer-review-panel.md") for path in result["contract_references"])
        assert "Treat `content` as the wrapper/context surface." in result["loading_hint"]
        assert "Load `schema_documents` and `contract_documents` too when present" in result["loading_hint"]

    def test_get_skill_surfaces_template_backed_schema_documents_for_writing_and_resume(self):
        from gpd.mcp.servers.skills_server import get_skill

        write_paper = get_skill("gpd-write-paper")
        pause_work = get_skill("gpd-pause-work")

        write_schema_documents = {Path(entry["path"]).name: entry for entry in write_paper["schema_documents"]}
        pause_schema_documents = {Path(entry["path"]).name: entry for entry in pause_work["schema_documents"]}

        assert "error" not in write_paper
        assert any(path.endswith("figure-tracker.md") for path in write_paper["schema_references"])
        assert any(path.endswith("author-response.md") for path in write_paper["schema_references"])
        assert "figure-tracker.md" in write_schema_documents
        assert "author-response.md" in write_schema_documents
        assert "figure_registry" in write_schema_documents["figure-tracker.md"]["body"]
        assert "Issue ID" in write_schema_documents["author-response.md"]["body"]

        assert "error" not in pause_work
        assert any(path.endswith("continue-here.md") for path in pause_work["schema_references"])
        assert "continue-here.md" in pause_schema_documents
        assert "<persistent_state>" in pause_schema_documents["continue-here.md"]["body"]

    def test_get_skill_surfaces_lightweight_paper_writer_reference_paths_and_transitive_metadata(self):
        from gpd.mcp.servers.skills_server import get_skill

        paper_writer = get_skill("gpd-paper-writer")
        paper_writer_referenced_paths = {entry["path"] for entry in paper_writer["referenced_files"]}
        paper_writer_transitive_paths = {entry["path"] for entry in paper_writer["transitive_referenced_files"]}
        paper_writer_template_references = set(paper_writer["template_references"])

        assert "error" not in paper_writer
        assert paper_writer["reference_count"] == len(paper_writer_referenced_paths)
        assert paper_writer["transitive_reference_count"] > paper_writer["reference_count"]
        assert paper_writer_referenced_paths.issuperset(
            {
                "@{GPD_INSTALL_DIR}/references/shared/shared-protocols.md",
                "@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md",
                "@{GPD_INSTALL_DIR}/references/publication/paper-writer-cookbook.md",
                "@{GPD_INSTALL_DIR}/templates/notation-glossary.md",
                "@{GPD_INSTALL_DIR}/templates/latex-preamble.md",
                "@{GPD_INSTALL_DIR}/references/publication/figure-generation-templates.md",
                "@{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md",
                "@{GPD_INSTALL_DIR}/templates/paper/author-response.md",
            }
        )
        assert paper_writer_template_references == {
            "@{GPD_INSTALL_DIR}/templates/notation-glossary.md",
            "@{GPD_INSTALL_DIR}/templates/latex-preamble.md",
            "@{GPD_INSTALL_DIR}/templates/paper/author-response.md",
        }
        assert paper_writer["schema_references"] == ["@{GPD_INSTALL_DIR}/templates/paper/author-response.md"]
        assert paper_writer["schema_documents"]
        assert any(path.endswith("verification-core.md") for path in paper_writer_transitive_paths)

    def test_get_skill_surfaces_lightweight_bibliographer_reference_paths_and_transitive_metadata(self):
        from gpd.mcp.servers.skills_server import get_skill

        bibliographer = get_skill("gpd-bibliographer")
        bibliographer_referenced_paths = {entry["path"] for entry in bibliographer["referenced_files"]}
        bibliographer_template_references = set(bibliographer["template_references"])
        bibliographer_transitive_paths = {entry["path"] for entry in bibliographer["transitive_referenced_files"]}

        assert "error" not in bibliographer
        assert bibliographer["reference_count"] == len(bibliographer_referenced_paths)
        assert bibliographer["transitive_reference_count"] > bibliographer["reference_count"]
        assert bibliographer_referenced_paths == {
            "@{GPD_INSTALL_DIR}/references/shared/shared-protocols.md",
            "@{GPD_INSTALL_DIR}/references/physics-subfields.md",
            "@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md",
            "@{GPD_INSTALL_DIR}/templates/notation-glossary.md",
            "@{GPD_INSTALL_DIR}/references/publication/bibtex-standards.md",
            "@{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md",
            "@{GPD_INSTALL_DIR}/references/publication/bibliography-advanced-search.md",
        }
        assert bibliographer_template_references == {
            "@{GPD_INSTALL_DIR}/templates/notation-glossary.md",
        }
        assert bibliographer["schema_references"] == []
        assert bibliographer["schema_documents"] == []
        assert any(path.endswith("verification-core.md") for path in bibliographer_transitive_paths)

    def test_get_skill_index_complete(self):
        from gpd.mcp.servers.skills_server import get_skill_index

        result = get_skill_index()

        assert isinstance(result, dict)
        assert result["total_skills"] > 10
        assert "index_text" in result
        assert "gpd-execute-phase" in result["index_text"]
        assert "gpd-peer-review" in result["index_text"]
        assert "gpd-debugger" in result["index_text"]
        assert "/gpd:debugger" not in result["index_text"]
        assert len(result["categories"]) > 3
