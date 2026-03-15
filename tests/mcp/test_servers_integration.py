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

See: .gpd/PROJECT.md

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


@pytest.fixture()
def gpd_project(tmp_path: Path) -> Path:
    """Create a realistic GPD project directory tree.

    Layout::
        <tmp>/
          .gpd/
            STATE.md
            state.json
            phases/
              01-setup/
                plan-01.md
                plan-02.md
                plan-03.md
                summary-01.md
    """
    planning = tmp_path / ".gpd"
    planning.mkdir()

    # Write state files
    (planning / "state.json").write_text(json.dumps(_STATE_JSON, indent=2))
    (planning / "STATE.md").write_text(_STATE_MD)

    # Create phase directory with plans and one summary
    phase_dir = planning / "phases" / "01-setup"
    phase_dir.mkdir(parents=True)
    for i in range(1, 4):
        (phase_dir / f"plan-{i:02d}.md").write_text(f"# Plan {i}\nDo step {i}.")
    (phase_dir / "summary-01.md").write_text("# Summary 1\nCompleted step 1.")

    return tmp_path


# ===========================================================================
# 1. Conventions Server
# ===========================================================================


class TestConventionsServerIntegration:
    """Integration tests for conventions_server tools with real state files."""

    def test_convention_set_stores_value(self, gpd_project: Path):
        from gpd.mcp.servers.conventions_server import convention_set

        result = convention_set(str(gpd_project), "regularization_scheme", "dim-reg")

        assert result["status"] == "set"
        assert result["key"] == "regularization_scheme"
        assert result["value"] == "dim-reg"
        assert result["type"] == "standard"

        # Verify the value persisted in state.json
        state = json.loads((gpd_project / ".gpd" / "state.json").read_text())
        assert state["convention_lock"]["regularization_scheme"] == "dim-reg"

    def test_convention_set_already_set_rejects_overwrite(self, gpd_project: Path):
        from gpd.mcp.servers.conventions_server import convention_set

        # metric_signature is already "(+,-,-,-)" in the fixture
        result = convention_set(str(gpd_project), "metric_signature", "(-,+,+,+)")

        assert result["status"] == "already_set"
        assert result["current_value"] == "(+,-,-,-)"
        assert result["requested_value"] == "mostly-plus"

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

    def test_advance_plan_increments(self, gpd_project: Path):
        from gpd.mcp.servers.state_server import advance_plan

        result = advance_plan(str(gpd_project))

        assert isinstance(result, dict)
        # Plan 1 -> 2, should succeed
        assert result["advanced"] is True
        assert result.get("new_plan") == 2 or result.get("current_plan") == 2

        # Verify STATE.md was updated
        md = (gpd_project / ".gpd" / "STATE.md").read_text()
        assert "**Current Plan:** 2" in md

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

    def test_run_check_flags_missing_hbar(self):
        from gpd.mcp.servers.verification_server import run_check

        artifact = "Compute the quantum commutator [x, p] for a particle."
        result = run_check("5.1", "qft", artifact)

        assert any("hbar" in issue for issue in result["automated_issues"])

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

    def test_symmetry_check_with_real_symmetries(self):
        from gpd.mcp.servers.verification_server import symmetry_check

        result = symmetry_check(
            "M(s,t) = -i g^2 (delta_{ab} / (s - m^2))",
            ["Lorentz invariance", "gauge invariance", "CPT"],
        )

        assert result["symmetries_checked"] == 3
        for entry in result["results"]:
            assert entry["matched_type"] is not None
            assert entry["strategy"] is not None

    def test_run_contract_check_fit_family_with_partial_metadata(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"declared_family": "power_law", "allowed_families": ["power_law", "scaling_form"]},
                "observed": {"selected_family": "power_law", "competing_family_checked": False},
            }
        )

        assert result["check_id"] == "5.18"
        assert result["status"] == "warning"
        assert "competing_family_checked" in result["metrics"]


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

    def test_list_error_classes_filter_by_domain(self):
        from gpd.mcp.servers.errors_mcp import list_error_classes

        result = list_error_classes(domain="core")

        assert isinstance(result, dict)
        assert result["count"] > 0
        for ec in result["error_classes"]:
            assert ec["domain"] == "core"

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

    def test_get_error_class_not_found(self):
        from gpd.mcp.servers.errors_mcp import get_error_class

        result = get_error_class(9999)

        assert "error" in result


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

    def test_list_protocols_filter_by_domain(self):
        from gpd.mcp.servers.protocols_server import list_protocols

        result = list_protocols(domain="core_derivation")

        assert isinstance(result, dict)
        assert result["count"] >= 1
        for proto in result["protocols"]:
            assert proto["domain"] == "core_derivation"

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

    def test_get_protocol_not_found(self):
        from gpd.mcp.servers.protocols_server import get_protocol

        result = get_protocol("nonexistent-protocol-xyz")

        assert "error" in result
        assert "available" in result
        assert len(result["available"]) > 0

    def test_route_protocol_finds_perturbation(self):
        from gpd.mcp.servers.protocols_server import route_protocol

        result = route_protocol("perturbative QCD one-loop calculation")

        assert isinstance(result, dict)
        assert result["match_count"] >= 1
        names = [p["name"] for p in result["protocols"]]
        assert "perturbation-theory" in names

    def test_route_protocol_finds_algebraic_qft(self):
        from gpd.mcp.servers.protocols_server import route_protocol

        result = route_protocol("Haag-Kastler net modular theory type III local algebras")

        assert isinstance(result, dict)
        assert result["match_count"] >= 1
        names = [p["name"] for p in result["protocols"]]
        assert "algebraic-qft" in names

    def test_route_protocol_finds_string_field_theory(self):
        from gpd.mcp.servers.protocols_server import route_protocol

        result = route_protocol("open superstring field theory tachyon condensation")

        assert isinstance(result, dict)
        assert result["match_count"] >= 1
        names = [p["name"] for p in result["protocols"]]
        assert "string-field-theory" in names


# ===========================================================================
# 6. Patterns Server
# ===========================================================================


class TestPatternsServerIntegration:
    """Integration tests for patterns_server with real seed data."""

    def test_seed_patterns_idempotent(self, tmp_path: Path):
        from gpd.core.patterns import pattern_seed

        # Seed into a temp location
        result1 = pattern_seed(root=tmp_path / "patterns")
        result2 = pattern_seed(root=tmp_path / "patterns")

        assert result1.added > 0
        assert result2.skipped == result1.added  # idempotent
        assert result2.added == 0

    def test_seed_patterns_via_mcp_tool(self, tmp_path: Path, monkeypatch):
        from gpd.mcp.servers import patterns_server

        monkeypatch.setattr(patterns_server, "_DEFAULT_PATTERNS_ROOT", tmp_path / "patterns")
        result = patterns_server.seed_patterns()

        assert isinstance(result, dict)
        assert result["seeded"] is True
        assert result["added"] > 0

    def test_lookup_pattern_after_seed(self, tmp_path: Path, monkeypatch):
        from gpd.mcp.servers import patterns_server

        lib_root = tmp_path / "patterns"
        monkeypatch.setattr(patterns_server, "_DEFAULT_PATTERNS_ROOT", lib_root)

        # Seed first
        patterns_server.seed_patterns()

        # Search by keyword
        result = patterns_server.lookup_pattern(keywords="sign error")

        assert isinstance(result, dict)
        assert result["count"] >= 1
        assert len(result["patterns"]) >= 1

    def test_lookup_pattern_by_domain_after_seed(self, tmp_path: Path, monkeypatch):
        from gpd.mcp.servers import patterns_server

        lib_root = tmp_path / "patterns"
        monkeypatch.setattr(patterns_server, "_DEFAULT_PATTERNS_ROOT", lib_root)

        patterns_server.seed_patterns()

        result = patterns_server.lookup_pattern(domain="qft")

        assert isinstance(result, dict)
        assert result["library_exists"] is True
        # The bootstrap seeds include qft patterns
        assert result["count"] >= 1

    def test_list_domains_returns_real_data(self):
        from gpd.mcp.servers.patterns_server import list_domains

        result = list_domains()

        assert isinstance(result, dict)
        assert len(result["domains"]) > 5
        assert "qft" in result["domains"]
        assert len(result["categories"]) > 3
        assert "sign-error" in result["categories"]
        assert len(result["severities"]) >= 3


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

    def test_list_skills_filter_by_category(self):
        from gpd.mcp.servers.skills_server import list_skills

        result = list_skills(category="verification")

        assert isinstance(result, dict)
        assert result["count"] >= 1
        for skill in result["skills"]:
            assert skill["category"] == "verification"

    def test_get_skill_real_agent_backed_canonical_skill(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-debugger")

        assert isinstance(result, dict)
        assert "error" not in result, f"gpd-debugger skill not found: {result}"
        assert result["name"] == "gpd-debugger"
        assert result["file_count"] >= 1
        assert len(result["content"]) > 0

    def test_get_skill_uses_canonical_command_content(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-help")

        assert isinstance(result, dict)
        assert "error" not in result
        assert result["name"] == "gpd-help"
        assert "gpd command reference" in result["content"].lower()
        assert result["file_count"] == 1

    def test_get_skill_resolves_package_spec_paths(self):
        from gpd.mcp.servers.skills_server import get_skill
        from gpd.registry import SPECS_DIR

        result = get_skill("gpd-plan-phase")

        assert "error" not in result
        assert "{GPD_INSTALL_DIR}" not in result["content"]
        assert f"@{SPECS_DIR.resolve().as_posix()}/workflows/plan-phase.md" in result["content"]

    def test_get_skill_peer_review_surfaces_transitive_schema_refs_and_typed_contract(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-peer-review")

        assert "error" not in result
        assert any(path.endswith("review-ledger-schema.md") for path in result["schema_references"])
        assert any(path.endswith("referee-decision-schema.md") for path in result["schema_references"])
        assert result["review_contract"] is not None
        assert result["review_contract"]["review_mode"] == "publication"
        assert result["context_mode"] == "project-required"

    def test_get_skill_not_found(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-nonexistent-skill-xyz")

        assert isinstance(result, dict)
        assert "error" in result
        assert "available" in result

    def test_route_skill_selects_execution(self):
        from gpd.mcp.servers.skills_server import route_skill

        result = route_skill("execute the current phase")

        assert isinstance(result, dict)
        assert result["suggestion"] == "gpd-execute-phase"
        assert result["confidence"] > 0

    def test_route_skill_selects_peer_review(self):
        from gpd.mcp.servers.skills_server import route_skill

        result = route_skill("peer review this manuscript like a referee")

        assert isinstance(result, dict)
        assert result["suggestion"] == "gpd-peer-review"
        assert result["confidence"] > 0

    def test_get_skill_index_complete(self):
        from gpd.mcp.servers.skills_server import get_skill_index

        result = get_skill_index()

        assert isinstance(result, dict)
        assert result["total_skills"] > 10
        assert "index_text" in result
        assert "/gpd:" in result["index_text"]
        assert "/gpd:peer-review" in result["index_text"]
        assert "gpd-debugger" in result["index_text"]
        assert "/gpd:debugger" not in result["index_text"]
        assert len(result["categories"]) > 3
