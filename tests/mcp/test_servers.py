"""Tests for all 7 GPD MCP servers.

Calls @mcp.tool() decorated functions directly with mock backends.
Covers: conventions, errors, patterns, protocols, skills, state, verification.
"""

from __future__ import annotations

import json
from unittest.mock import ANY, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. Conventions server
# ---------------------------------------------------------------------------


class TestConventionsServer:
    """Tests for gpd.mcp.servers.conventions_server tool functions."""

    def test_convention_check_empty_lock(self):
        from gpd.mcp.servers.conventions_server import convention_check

        result = convention_check({})
        assert result["completeness_percent"] == 0.0
        assert len(result["missing_critical"]) > 0

    def test_convention_check_with_critical_fields(self):
        from gpd.mcp.servers.conventions_server import convention_check

        lock = {
            "metric_signature": "(+,-,-,-)",
            "fourier_convention": "physics",
            "natural_units": "natural",
        }
        result = convention_check(lock)
        assert result["valid"] is True
        assert result["missing_critical"] == []

    def test_convention_check_consistency_issues(self):
        from gpd.mcp.servers.conventions_server import convention_check

        lock = {"renormalization_scheme": "MS-bar"}
        result = convention_check(lock)
        assert any("Renormalization scheme" in i for i in result["issues"])

    def test_convention_check_euclidean_qft_warning(self):
        from gpd.mcp.servers.conventions_server import convention_check

        lock = {
            "metric_signature": "Euclidean (+,+,+,+)",
            "fourier_convention": "QFT",
            "natural_units": "natural",
        }
        result = convention_check(lock)
        assert any("Euclidean" in i for i in result["issues"])

    def test_convention_diff_identical(self):
        from gpd.mcp.servers.conventions_server import convention_diff

        lock = {"metric_signature": "(+,-,-,-)", "natural_units": "natural"}
        result = convention_diff(lock, lock)
        assert result["identical"] is True
        assert result["diff_count"] == 0

    def test_convention_diff_changed(self):
        from gpd.mcp.servers.conventions_server import convention_diff

        lock_a = {"metric_signature": "(+,-,-,-)", "natural_units": "natural"}
        lock_b = {"metric_signature": "(-,+,+,+)", "natural_units": "natural"}
        result = convention_diff(lock_a, lock_b)
        assert result["identical"] is False
        assert len(result["critical_diffs"]) == 1
        assert result["critical_diffs"][0]["field"] == "metric_signature"

    def test_convention_diff_added_field(self):
        from gpd.mcp.servers.conventions_server import convention_diff

        lock_a = {"natural_units": "natural"}
        lock_b = {"natural_units": "natural", "metric_signature": "(+,-,-,-)"}
        result = convention_diff(lock_a, lock_b)
        assert result["diff_count"] == 1

    def test_assert_convention_validate_matching(self):
        from gpd.mcp.servers.conventions_server import assert_convention_validate

        content = "% ASSERT_CONVENTION: metric_signature=(+,-,-,-)"
        lock = {"metric_signature": "(+,-,-,-)"}
        result = assert_convention_validate(content, lock)
        assert result["valid"] is True
        assert result["assertions_found"] >= 1

    def test_assert_convention_validate_mismatch(self):
        from gpd.mcp.servers.conventions_server import assert_convention_validate

        content = "% ASSERT_CONVENTION: metric_signature=(-,+,+,+)"
        lock = {"metric_signature": "(+,-,-,-)"}
        result = assert_convention_validate(content, lock)
        assert result["valid"] is False
        assert len(result["mismatches"]) == 1

    def test_assert_convention_validate_no_assertions(self):
        from gpd.mcp.servers.conventions_server import assert_convention_validate

        result = assert_convention_validate("No assertions here", {})
        assert result["valid"] is False
        assert result["assertions_found"] == 0

    def test_subfield_defaults_qft(self):
        from gpd.mcp.servers.conventions_server import subfield_defaults

        result = subfield_defaults("qft")
        assert result["found"] is True
        assert "natural_units" in result["defaults"]
        assert result["defaults"]["natural_units"] == "natural"

    def test_subfield_defaults_algebraic_qft(self):
        from gpd.mcp.servers.conventions_server import subfield_defaults

        result = subfield_defaults("algebraic_qft")
        assert result["found"] is True
        assert result["defaults"]["natural_units"] == "natural"
        assert result["defaults"]["state_normalization"] == "relativistic"

    def test_subfield_defaults_string_field_theory(self):
        from gpd.mcp.servers.conventions_server import subfield_defaults

        result = subfield_defaults("string_field_theory")
        assert result["found"] is True
        assert result["defaults"]["natural_units"] == "natural"
        assert result["defaults"]["creation_annihilation_order"] == "normal"

    def test_subfield_defaults_unknown(self):
        from gpd.mcp.servers.conventions_server import subfield_defaults

        result = subfield_defaults("unknown_domain")
        assert result["found"] is False
        assert "available_domains" in result

    def test_subfield_defaults_all_domains_valid(self):
        from gpd.mcp.servers.conventions_server import SUBFIELD_DEFAULTS, subfield_defaults

        for domain in SUBFIELD_DEFAULTS:
            result = subfield_defaults(domain)
            assert result["found"] is True, f"Domain {domain} should be found"

    def test_convention_lock_status(self, tmp_path):
        from gpd.mcp.servers.conventions_server import convention_lock_status

        planning = tmp_path / ".gpd"
        planning.mkdir()
        state = {
            "convention_lock": {
                "metric_signature": "(+,-,-,-)",
                "natural_units": "natural",
            }
        }
        (planning / "state.json").write_text(json.dumps(state))
        result = convention_lock_status(str(tmp_path))
        assert result["set_count"] >= 2
        assert "metric_signature" in result["set_fields"]

    def test_convention_lock_status_empty_project(self, tmp_path):
        from gpd.mcp.servers.conventions_server import convention_lock_status

        planning = tmp_path / ".gpd"
        planning.mkdir()
        result = convention_lock_status(str(tmp_path))
        assert result["set_count"] == 0

    def test_convention_set(self, tmp_path):
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({}))

        result = convention_set(str(tmp_path), "metric_signature", "(+,-,-,-)")
        assert result["status"] == "set"
        assert result["key"] == "metric_signature"

    def test_convention_set_already_set(self, tmp_path):
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / ".gpd"
        planning.mkdir()
        state = {"convention_lock": {"metric_signature": "(+,-,-,-)"}}
        (planning / "state.json").write_text(json.dumps(state))

        result = convention_set(str(tmp_path), "metric_signature", "(-,+,+,+)")
        assert result["status"] == "already_set"

    def test_convention_set_custom_key(self, tmp_path):
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({}))

        result = convention_set(str(tmp_path), "custom:my_convention", "my_value")
        assert result["status"] == "set"
        assert result["type"] == "custom"


    def test_load_lock_non_dict_state_json(self, tmp_path):
        """If state.json contains a non-dict (e.g. a list), return empty lock."""
        from gpd.mcp.servers.conventions_server import _load_lock_from_project

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps([1, 2, 3]))
        lock = _load_lock_from_project(str(tmp_path))
        assert lock.metric_signature is None

    def test_load_lock_string_state_json(self, tmp_path):
        """If state.json contains a bare string, return empty lock."""
        from gpd.mcp.servers.conventions_server import _load_lock_from_project

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps("just a string"))
        lock = _load_lock_from_project(str(tmp_path))
        assert lock.metric_signature is None

    def test_update_lock_non_dict_state_json(self, tmp_path):
        """If state.json contains a non-dict, _update_lock_in_project resets raw to {}."""
        from gpd.mcp.servers.conventions_server import _update_lock_in_project

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps([1, 2, 3]))
        lock, result = _update_lock_in_project(
            str(tmp_path), lambda lk: lk.metric_signature
        )
        assert lock.metric_signature is None
        assert result is None

# ---------------------------------------------------------------------------
# 2. Errors MCP server
# ---------------------------------------------------------------------------


class TestErrorsMcp:
    """Tests for gpd.mcp.servers.errors_mcp tool functions."""

    @pytest.fixture(autouse=True)
    def _mock_store(self):
        """Inject a mock ErrorStore."""
        mock = MagicMock()
        mock.get.return_value = {
            "id": 1,
            "name": "Wrong CG coefficients",
            "description": "Incorrect Clebsch-Gordan coefficients",
            "detection_strategy": "Verify with angular momentum algebra",
            "example": "3j-symbol errors",
            "domain": "core",
            "source_file": "llm-errors-core.md",
        }
        mock.get_traceability.return_value = {"Dimensional Analysis": "✓", "Symmetry": "✓"}
        mock.list_all.return_value = [
            {"id": 1, "name": "Wrong CG coefficients", "domain": "core"},
            {"id": 2, "name": "N-particle symmetrization", "domain": "core"},
        ]
        mock.check_relevant.return_value = [
            {"id": 1, "name": "Wrong CG coefficients", "domain": "core", "relevance_score": 10}
        ]
        mock.domains = ["core", "field_theory"]
        mock.count = 104
        self.store = mock
        with patch("gpd.mcp.servers.errors_mcp._get_store", return_value=mock):
            yield

    def test_catalog_files_live_under_verification_errors_subtree(self):
        from gpd.mcp.servers.errors_mcp import ERROR_CATALOG_FILES, REFERENCES_DIR, TRACEABILITY_FILE

        assert ERROR_CATALOG_FILES == [
            "verification/errors/llm-errors-core.md",
            "verification/errors/llm-errors-field-theory.md",
            "verification/errors/llm-errors-extended.md",
            "verification/errors/llm-errors-deep.md",
        ]
        assert TRACEABILITY_FILE == "verification/errors/llm-errors-traceability.md"

        for rel_path in [*ERROR_CATALOG_FILES, TRACEABILITY_FILE]:
            assert (REFERENCES_DIR / rel_path).is_file(), rel_path

    def test_real_error_store_uses_new_catalog_paths_and_stable_basenames(self):
        from gpd.mcp.servers.errors_mcp import ErrorStore, REFERENCES_DIR

        store = ErrorStore(REFERENCES_DIR)
        error = store.get(1)

        assert error is not None
        assert error["source_file"] == "llm-errors-core.md"
        assert store.get_traceability(1) is not None

    def test_get_error_class_found(self):
        from gpd.mcp.servers.errors_mcp import get_error_class

        result = get_error_class(1)
        assert result["name"] == "Wrong CG coefficients"

    def test_get_error_class_not_found(self):
        from gpd.mcp.servers.errors_mcp import get_error_class

        self.store.get.return_value = None
        result = get_error_class(999)
        assert "error" in result

    def test_check_error_classes(self):
        from gpd.mcp.servers.errors_mcp import check_error_classes

        result = check_error_classes("angular momentum coupling calculation")
        assert result["match_count"] >= 1

    def test_get_detection_strategy(self):
        from gpd.mcp.servers.errors_mcp import get_detection_strategy

        result = get_detection_strategy(1)
        assert "detection_strategy" in result
        assert result["name"] == "Wrong CG coefficients"

    def test_get_detection_strategy_not_found(self):
        from gpd.mcp.servers.errors_mcp import get_detection_strategy

        self.store.get.return_value = None
        result = get_detection_strategy(999)
        assert "error" in result

    def test_get_traceability(self):
        from gpd.mcp.servers.errors_mcp import get_traceability

        result = get_traceability(1)
        assert "verification_checks" in result
        assert len(result["covered_by"]) == 2

    def test_get_traceability_no_data(self):
        from gpd.mcp.servers.errors_mcp import get_traceability

        self.store.get_traceability.return_value = None
        result = get_traceability(1)
        assert "note" in result

    def test_list_error_classes(self):
        from gpd.mcp.servers.errors_mcp import list_error_classes

        result = list_error_classes()
        assert result["count"] == 2
        assert result["total_classes"] == 104

    def test_list_error_classes_by_domain(self):
        from gpd.mcp.servers.errors_mcp import list_error_classes

        self.store.list_all.return_value = [{"id": 1, "name": "Wrong CG coefficients", "domain": "core"}]
        result = list_error_classes(domain="core")
        self.store.list_all.assert_called_with("core")
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# 3. Patterns server
# ---------------------------------------------------------------------------


class TestPatternsServer:
    """Tests for gpd.mcp.servers.patterns_server tool functions."""

    def test_lookup_pattern_by_keywords(self):
        from gpd.mcp.servers.patterns_server import lookup_pattern

        mock_result = MagicMock()
        mock_result.count = 1
        mock_result.matches = [MagicMock()]
        mock_result.matches[0].model_dump.return_value = {"id": "p1", "title": "Sign error"}
        mock_result.query = "sign error"

        with patch("gpd.mcp.servers.patterns_server.pattern_search", return_value=mock_result):
            result = lookup_pattern(keywords="sign error")
        assert result["count"] == 1

    def test_lookup_pattern_by_domain(self):
        from gpd.mcp.servers.patterns_server import lookup_pattern

        mock_result = MagicMock()
        mock_result.count = 2
        mock_result.patterns = [MagicMock(), MagicMock()]
        for p in mock_result.patterns:
            p.model_dump.return_value = {"id": "p1", "domain": "qft"}
        mock_result.library_exists = True

        with patch("gpd.mcp.servers.patterns_server.pattern_list", return_value=mock_result):
            result = lookup_pattern(domain="qft")
        assert result["count"] == 2
        assert result["library_exists"] is True

    def test_add_pattern(self):
        from gpd.mcp.servers.patterns_server import add_pattern

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "added": True,
            "id": "qft-sign-error-test",
            "severity": "high",
        }

        with patch("gpd.mcp.servers.patterns_server.pattern_add", return_value=mock_result):
            result = add_pattern(
                domain="qft",
                title="Test sign error",
                category="sign-error",
                severity="high",
                description="A test pattern",
            )
        assert result["added"] is True

    def test_promote_pattern(self):
        from gpd.mcp.servers.patterns_server import promote_pattern

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "promoted": True,
            "id": "p1",
            "from_level": "single_observation",
            "to_level": "confirmed",
        }

        with patch("gpd.mcp.servers.patterns_server.pattern_promote", return_value=mock_result):
            result = promote_pattern("p1")
        assert result["promoted"] is True

    def test_seed_patterns(self):
        from gpd.mcp.servers.patterns_server import seed_patterns

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"seeded": True, "added": 8, "skipped": 0, "total": 8}

        with patch("gpd.mcp.servers.patterns_server.pattern_seed", return_value=mock_result):
            result = seed_patterns()
        assert result["seeded"] is True
        assert result["added"] == 8

    def test_list_domains(self):
        from gpd.mcp.servers.patterns_server import list_domains

        result = list_domains()
        assert "domains" in result
        assert "categories" in result
        assert "severities" in result
        assert len(result["domains"]) > 0


# ---------------------------------------------------------------------------
# 4. Protocols server
# ---------------------------------------------------------------------------


class TestProtocolsServer:
    """Tests for gpd.mcp.servers.protocols_server tool functions."""

    @pytest.fixture(autouse=True)
    def _mock_store(self):
        mock = MagicMock()
        mock.get.return_value = {
            "name": "perturbation-theory",
            "title": "Perturbation Theory Protocol",
            "domain": "core_derivation",
            "tier": 1,
            "context_cost": "high",
            "load_when": ["perturbation", "loop", "expansion"],
            "steps": ["Identify small parameter", "Expand to desired order"],
            "checkpoints": ["Check convergence radius", "Verify limiting cases"],
            "body": "# Perturbation Theory Protocol\n...",
        }
        mock.list_all.return_value = [
            {
                "name": "perturbation-theory",
                "title": "Perturbation Theory Protocol",
                "domain": "core_derivation",
                "tier": 1,
                "context_cost": "high",
                "load_when": ["perturbation"],
            },
        ]
        mock.route.return_value = [
            {
                "name": "perturbation-theory",
                "title": "Perturbation Theory Protocol",
                "domain": "core_derivation",
                "tier": 1,
                "context_cost": "high",
                "relevance_score": 15,
            },
        ]
        mock.domains = ["core_derivation", "computational_methods"]
        self.store = mock
        with patch("gpd.mcp.servers.protocols_server._get_store", return_value=mock):
            yield

    def test_get_protocol_found(self):
        from gpd.mcp.servers.protocols_server import get_protocol

        result = get_protocol("perturbation-theory")
        assert result["name"] == "perturbation-theory"
        assert len(result["steps"]) == 2
        assert len(result["checkpoints"]) == 2

    def test_get_protocol_not_found(self):
        from gpd.mcp.servers.protocols_server import get_protocol

        self.store.get.return_value = None
        result = get_protocol("nonexistent")
        assert "error" in result
        assert "available" in result

    def test_list_protocols(self):
        from gpd.mcp.servers.protocols_server import list_protocols

        result = list_protocols()
        assert result["count"] == 1
        assert set(result["available_domains"]) == {"computational_methods", "core_derivation"}

    def test_list_protocols_by_domain(self):
        from gpd.mcp.servers.protocols_server import list_protocols

        list_protocols(domain="core_derivation")
        self.store.list_all.assert_called_with("core_derivation")

    def test_route_protocol(self):
        from gpd.mcp.servers.protocols_server import route_protocol

        result = route_protocol("perturbative QCD one-loop calculation")
        assert result["match_count"] >= 1

    def test_get_protocol_checkpoints_found(self):
        from gpd.mcp.servers.protocols_server import get_protocol_checkpoints

        result = get_protocol_checkpoints("perturbation-theory")
        assert result["checkpoint_count"] == 2

    def test_get_protocol_checkpoints_not_found(self):
        from gpd.mcp.servers.protocols_server import get_protocol_checkpoints

        self.store.get.return_value = None
        result = get_protocol_checkpoints("nonexistent")
        assert "error" in result


# ---------------------------------------------------------------------------
# 5. Skills server
# ---------------------------------------------------------------------------


class TestSkillsServer:
    """Tests for gpd.mcp.servers.skills_server tool functions."""

    @pytest.fixture(autouse=True)
    def _mock_skill_registry(self, tmp_path):
        """Create fake commands/agents for MCP skill tests."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        (commands_dir / "execute-phase.md").write_text(
            "---\n"
            "name: gpd:execute-phase\n"
            "description: Execute all plans in a phase.\n"
            "---\n"
            "\n"
            "Canonical execute command.\n",
            encoding="utf-8",
        )
        (commands_dir / "plan-phase.md").write_text(
            "---\n"
            "name: gpd:plan-phase\n"
            "description: Create detailed execution plan.\n"
            "---\n"
            "\n"
            "Canonical plan command.\n"
            "Read @{GPD_INSTALL_DIR}/workflows/plan-phase.md and {GPD_AGENTS_DIR}/gpd-planner.md.\n",
            encoding="utf-8",
        )
        (commands_dir / "help.md").write_text(
            "---\n"
            "name: gpd:help\n"
            "description: Show available GPD commands and usage guide.\n"
            "---\n"
            "\n"
            "Canonical help command.\n",
            encoding="utf-8",
        )
        (commands_dir / "peer-review.md").write_text(
            "---\n"
            "name: gpd:peer-review\n"
            "description: Conduct standalone peer review.\n"
            "---\n"
            "\n"
            "Canonical peer review command.\n",
            encoding="utf-8",
        )
        (agents_dir / "gpd-debugger.md").write_text(
            "---\n"
            "name: gpd-debugger\n"
            "description: Canonical debugger agent.\n"
            "---\n"
            "\n"
            "Primary debugger agent.\n",
            encoding="utf-8",
        )

        with (
            patch("gpd.registry.COMMANDS_DIR", commands_dir),
            patch("gpd.registry.AGENTS_DIR", agents_dir),
        ):
            from gpd.registry import invalidate_cache

            invalidate_cache()
            yield
            invalidate_cache()

    def test_list_skills(self):
        from gpd.mcp.servers.skills_server import list_skills

        result = list_skills()
        assert result["count"] == 5
        names = {s["name"] for s in result["skills"]}
        assert "gpd-execute-phase" in names
        assert "gpd-plan-phase" in names
        assert "gpd-peer-review" in names
        assert "gpd-debugger" in names
        assert "gpd-help" in names

    def test_list_skills_by_category(self):
        from gpd.mcp.servers.skills_server import list_skills

        result = list_skills(category="execution")
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "gpd-execute-phase"

    def test_list_skills_empty_category(self):
        from gpd.mcp.servers.skills_server import list_skills

        result = list_skills(category="nonexistent")
        assert result["count"] == 0

    def test_get_skill_found(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-execute-phase")
        assert result["name"] == "gpd-execute-phase"
        assert "Canonical execute command" in result["content"]
        assert result["file_count"] == 1

    def test_get_skill_agent_uses_primary_agent_content(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-debugger")
        assert result["name"] == "gpd-debugger"
        assert "Primary debugger agent" in result["content"]

    def test_get_skill_resolves_install_and_agents_placeholders(self):
        from gpd.mcp.servers.skills_server import get_skill
        from gpd.registry import AGENTS_DIR, SPECS_DIR

        result = get_skill("gpd-plan-phase")

        assert "{GPD_INSTALL_DIR}" not in result["content"]
        assert "{GPD_AGENTS_DIR}" not in result["content"]
        assert f"@{SPECS_DIR.resolve().as_posix()}/workflows/plan-phase.md" in result["content"]
        assert f"{AGENTS_DIR.resolve().as_posix()}/gpd-planner.md" in result["content"]

    def test_get_skill_not_found(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-nonexistent")
        assert "error" in result

    def test_route_skill_execute(self):
        from gpd.mcp.servers.skills_server import route_skill

        result = route_skill("execute the phase implementation")
        assert result["suggestion"] == "gpd-execute-phase"
        assert result["confidence"] > 0

    def test_route_skill_plan(self):
        from gpd.mcp.servers.skills_server import route_skill

        result = route_skill("plan the next phase design strategy")
        assert result["suggestion"] == "gpd-plan-phase"

    def test_route_skill_peer_review(self):
        from gpd.mcp.servers.skills_server import route_skill

        result = route_skill("peer review this manuscript like a referee")
        assert result["suggestion"] == "gpd-peer-review"

    def test_route_skill_no_match(self):
        from gpd.mcp.servers.skills_server import route_skill

        result = route_skill("zzz yyy xxx")
        assert result["suggestion"] == "gpd-help"
        assert result["confidence"] <= 0.1

    def test_route_skill_no_match_without_help_falls_back_to_first_skill(self):
        from gpd.mcp.servers.skills_server import route_skill
        from gpd.registry import SkillDef

        with patch(
            "gpd.mcp.servers.skills_server._load_skill_index",
            return_value=[
                SkillDef(
                    name="gpd-debugger",
                    description="Debugger",
                    content="Primary debugger agent.",
                    category="debugging",
                    path="/tmp/gpd-debugger.md",
                    source_kind="agent",
                    registry_name="gpd-debugger",
                )
            ],
        ):
            result = route_skill("zzz yyy xxx")

        assert result["suggestion"] == "gpd-debugger"
        assert result["confidence"] <= 0.1

    def test_get_skill_index(self):
        from gpd.mcp.servers.skills_server import get_skill_index

        result = get_skill_index()
        assert result["total_skills"] == 5
        assert "index_text" in result
        assert "/gpd:execute-phase" in result["index_text"]
        assert "/gpd:peer-review" in result["index_text"]

    def test_get_skill_accepts_command_style_name(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd:execute-phase")
        assert result["name"] == "gpd-execute-phase"
        assert "Canonical execute command" in result["content"]


# ---------------------------------------------------------------------------
# 6. State server
# ---------------------------------------------------------------------------


class TestStateServer:
    """Tests for gpd.mcp.servers.state_server tool functions."""

    def test_get_state(self):
        from gpd.mcp.servers.state_server import get_state

        mock_state = {"position": {"current_phase": "01"}, "decisions": [], "blockers": []}

        with patch("gpd.mcp.servers.state_server.load_state_json", return_value=mock_state):
            result = get_state("/fake/project")
        assert "position" in result
        assert result["position"]["current_phase"] == "01"

    def test_get_state_no_state(self):
        from gpd.mcp.servers.state_server import get_state

        with patch("gpd.mcp.servers.state_server.load_state_json", return_value=None):
            result = get_state("/fake/project")
        assert "error" in result

    def test_get_state_gpd_error(self):
        from gpd.core.errors import GPDError
        from gpd.mcp.servers.state_server import get_state

        with patch("gpd.mcp.servers.state_server.load_state_json", side_effect=GPDError("boom")):
            with pytest.raises(GPDError, match="boom"):
                get_state("/fake/project")

    def test_get_phase_info_found(self):
        from gpd.mcp.servers.state_server import get_phase_info

        mock_info = MagicMock()
        mock_info.phase_number = "01"
        mock_info.phase_name = "Setup"
        mock_info.directory = ".gpd/phases/01-setup"
        mock_info.phase_slug = "01-setup"
        mock_info.plans = ["plan-01.md", "plan-02.md", "plan-03.md"]
        mock_info.summaries = ["summary-01.md", "summary-02.md"]
        mock_info.incomplete_plans = ["plan-03.md"]

        with patch("gpd.core.phases.find_phase", return_value=mock_info):
            result = get_phase_info("/fake/project", "01")
        assert result["phase_number"] == "01"
        assert result["plan_count"] == 3
        assert result["summary_count"] == 2
        assert result["complete"] is False

    def test_get_phase_info_not_found(self):
        from gpd.mcp.servers.state_server import get_phase_info

        with patch("gpd.core.phases.find_phase", return_value=None):
            result = get_phase_info("/fake/project", "99")
        assert "error" in result

    def test_advance_plan(self):
        from gpd.mcp.servers.state_server import advance_plan

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"advanced": True, "new_plan": 2}

        with patch("gpd.mcp.servers.state_server.state_advance_plan", return_value=mock_result):
            result = advance_plan("/fake/project")
        assert result["advanced"] is True

    def test_get_progress(self):
        from gpd.mcp.servers.state_server import get_progress

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"updated": True, "progress_percent": 50}

        with patch("gpd.mcp.servers.state_server.state_update_progress", return_value=mock_result):
            result = get_progress("/fake/project")
        assert result["progress_percent"] == 50

    def test_validate_state(self):
        from gpd.mcp.servers.state_server import validate_state

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"valid": True, "issues": [], "warnings": []}

        with patch("gpd.mcp.servers.state_server.state_validate", return_value=mock_result):
            result = validate_state("/fake/project")
        assert result["valid"] is True

    def test_run_health_check(self):
        from gpd.mcp.servers.state_server import run_health_check

        mock_report = MagicMock()
        mock_report.model_dump.return_value = {
            "passed": 10,
            "failed": 1,
            "checks": [],
        }

        with patch("gpd.mcp.servers.state_server.run_health", return_value=mock_report):
            result = run_health_check("/fake/project")
        assert result["passed"] == 10

    def test_run_health_check_with_fix(self):
        from gpd.mcp.servers.state_server import run_health_check

        mock_report = MagicMock()
        mock_report.model_dump.return_value = {"passed": 11, "failed": 0, "fixes_applied": 1}

        with patch("gpd.mcp.servers.state_server.run_health", return_value=mock_report) as mock_fn:
            result = run_health_check("/fake/project", fix=True)
        mock_fn.assert_called_once_with(ANY, fix=True)
        assert result["fixes_applied"] == 1

    def test_get_config(self):
        from gpd.mcp.servers.state_server import get_config

        mock_config = MagicMock()
        mock_config.model_dump.return_value = {"model_profile": "deep-theory", "autonomy_mode": "full"}

        with patch("gpd.mcp.servers.state_server.load_config", return_value=mock_config):
            result = get_config("/fake/project")
        assert result["model_profile"] == "deep-theory"


# ---------------------------------------------------------------------------
# 7. Verification server
# ---------------------------------------------------------------------------


class TestVerificationServer:
    """Tests for gpd.mcp.servers.verification_server tool functions."""

    # --- dimensional_check (pure function) ---

    def test_dimensional_check_consistent(self):
        from gpd.mcp.servers.verification_server import dimensional_check

        result = dimensional_check(["[M][L]^2[T]^-2 = [M][L]^2[T]^-2"])
        assert result["all_consistent"] is True

    def test_dimensional_check_inconsistent(self):
        from gpd.mcp.servers.verification_server import dimensional_check

        result = dimensional_check(["[M][L]^2[T]^-2 = [M][L][T]^-2"])
        assert result["all_consistent"] is False
        assert "mismatches" in result["results"][0]
        assert result["results"][0]["mismatches"]["L"]["diff"] == 1

    def test_dimensional_check_no_equals(self):
        from gpd.mcp.servers.verification_server import dimensional_check

        result = dimensional_check(["[M][L]^2"])
        assert result["results"][0]["valid"] is False
        assert "error" in result["results"][0]

    def test_dimensional_check_multiple_expressions(self):
        from gpd.mcp.servers.verification_server import dimensional_check

        result = dimensional_check(
            [
                "[M][L]^2[T]^-2 = [M][L]^2[T]^-2",
                "[M][L][T]^-1 = [M][L][T]^-1",
            ]
        )
        assert result["all_consistent"] is True
        assert result["checked_count"] == 2

    def test_dimensional_check_charge_dimension(self):
        from gpd.mcp.servers.verification_server import dimensional_check

        result = dimensional_check(["[Q][T]^-1 = [Q][T]^-1"])
        assert result["all_consistent"] is True

    # --- limiting_case_check (pure function) ---

    def test_limiting_case_check_basic(self):
        from gpd.mcp.servers.verification_server import limiting_case_check

        result = limiting_case_check(
            "E = gamma * m * c^2",
            {"non-relativistic limit": "E = m*c^2 + 1/2*m*v^2"},
        )
        assert result["limits_checked"] == 1
        assert result["results"][0]["status"] == "documented"

    def test_limiting_case_check_suggests_missing(self):
        from gpd.mcp.servers.verification_server import limiting_case_check

        result = limiting_case_check(
            "psi = exp(-i * hbar * H * t)",
            {},
        )
        assert any("classical" in s.lower() for s in result["suggestions"])

    def test_limiting_case_check_relativistic_suggestion(self):
        from gpd.mcp.servers.verification_server import limiting_case_check

        result = limiting_case_check(
            "E = gamma * m * c^2",
            {},
        )
        assert any("non-relativistic" in s.lower() for s in result["suggestions"])

    def test_limiting_case_check_coupling_suggestion(self):
        from gpd.mcp.servers.verification_server import limiting_case_check

        result = limiting_case_check(
            "sigma = alpha^2 / s * (1 + perturbative corrections)",
            {},
        )
        assert any("weak-coupling" in s.lower() for s in result["suggestions"])

    def test_limiting_case_check_standard_limit_type(self):
        from gpd.mcp.servers.verification_server import limiting_case_check

        result = limiting_case_check(
            "some expression",
            {"classical limit: hbar -> 0": "Hamilton-Jacobi"},
        )
        assert result["results"][0]["limit_type"] == "classical"

    # --- symmetry_check (pure function) ---

    def test_symmetry_check_known_symmetries(self):
        from gpd.mcp.servers.verification_server import symmetry_check

        result = symmetry_check(
            "M(s,t) amplitude",
            ["Lorentz invariance", "gauge invariance", "parity"],
        )
        assert result["symmetries_checked"] == 3
        for r in result["results"]:
            assert r["matched_type"] is not None
            assert r["strategy"] is not None

    def test_symmetry_check_unknown_symmetry(self):
        from gpd.mcp.servers.verification_server import symmetry_check

        result = symmetry_check("expression", ["custom_symmetry_xyz"])
        assert result["results"][0]["matched_type"] is None
        assert "custom_symmetry_xyz" in result["results"][0]["strategy"]

    # --- run_check ---

    def test_run_check_dimensional(self):
        from gpd.mcp.servers.verification_server import run_check

        result = run_check("5.1", "qft", "quantum field theory with \\hbar")
        assert result["check_id"] == "5.1"
        assert result["check_name"] == "Dimensional analysis"
        assert result["schema_version"] == 1
        assert result["evidence_kind"] == "computational"
        assert result["machine_supported"] is True

    def test_run_check_dimensional_missing_hbar(self):
        from gpd.mcp.servers.verification_server import run_check

        result = run_check("5.1", "qft", "quantum commutator calculation")
        assert any("hbar" in issue for issue in result["automated_issues"])

    def test_run_check_limiting_cases_no_limits(self):
        from gpd.mcp.servers.verification_server import run_check

        result = run_check("5.3", "qft", "just some plain calculation here")
        assert any("limiting" in issue.lower() for issue in result["automated_issues"])

    def test_run_check_limiting_cases_with_limits(self):
        from gpd.mcp.servers.verification_server import run_check

        result = run_check("5.3", "qft", "In the limit \\to 0 this reduces to known result")
        assert len(result["automated_issues"]) == 0

    def test_run_check_unknown_id(self):
        from gpd.mcp.servers.verification_server import run_check

        result = run_check("99.99", "qft", "content")
        assert "error" in result
        assert "Unknown check_id" in result["error"]

    def test_run_check_domain_specific_guidance(self):
        from gpd.mcp.servers.verification_server import run_check

        result = run_check("5.9", "qft", "Ward identity computation")
        assert len(result["domain_specific_checks"]) > 0

    # --- get_checklist ---

    def test_get_checklist_qft(self):
        from gpd.mcp.servers.verification_server import get_checklist

        result = get_checklist("qft")
        assert result["found"] is True
        assert result["schema_version"] == 1
        assert result["domain_check_count"] > 0
        assert result["universal_check_count"] == 14
        assert result["universal_checks"][0]["check_id"] == "5.1"
        assert "evidence_kind" in result["universal_checks"][0]

    def test_get_checklist_unknown_domain(self):
        from gpd.mcp.servers.verification_server import get_checklist

        result = get_checklist("unknown_physics_domain")
        assert result["found"] is False
        assert "available_domains" in result

    def test_get_checklist_all_domains(self):
        from gpd.mcp.servers.verification_server import DOMAIN_CHECKLISTS, get_checklist

        for domain in DOMAIN_CHECKLISTS:
            result = get_checklist(domain)
            assert result["found"] is True, f"Checklist for {domain} should exist"

    # --- get_verification_coverage ---

    def test_verification_coverage_full(self):
        from gpd.mcp.servers.verification_server import get_verification_coverage

        result = get_verification_coverage(
            error_class_ids=[15],
            active_checks=["5.1", "5.2", "5.3"],
        )
        assert result["schema_version"] == 1
        assert result["covered"] == 1
        assert result["coverage_percent"] == 100.0

    def test_verification_coverage_partial(self):
        from gpd.mcp.servers.verification_server import get_verification_coverage

        result = get_verification_coverage(
            error_class_ids=[37],  # needs 5.1 + 5.3
            active_checks=["5.1"],
        )
        assert result["partial"] == 1
        assert "missing_checks" in result["partial_classes"][0]

    def test_verification_coverage_uncovered(self):
        from gpd.mcp.servers.verification_server import get_verification_coverage

        result = get_verification_coverage(
            error_class_ids=[15],  # needs 5.1
            active_checks=["5.9", "5.10"],
        )
        assert result["uncovered"] == 1

    def test_verification_coverage_unknown_error_class(self):
        from gpd.mcp.servers.verification_server import get_verification_coverage

        result = get_verification_coverage(
            error_class_ids=[9999],
            active_checks=["5.1"],
        )
        assert result["uncovered"] == 1
        assert result["uncovered_classes"][0]["status"] == "unknown"

    def test_verification_coverage_recommendation(self):
        from gpd.mcp.servers.verification_server import get_verification_coverage

        result = get_verification_coverage(
            error_class_ids=[15, 37],
            active_checks=list(
                __import__("gpd.core.verification_checks", fromlist=["VERIFICATION_CHECKS"]).VERIFICATION_CHECKS.keys()
            ),
        )
        assert "Full coverage" in result["recommendation"]


    # --- _parse_dimensions helper ---

    def test_parse_dimensions(self):
        from gpd.mcp.servers.verification_server import _parse_dimensions

        dims = _parse_dimensions("[M][L]^2[T]^-2")
        assert dims["M"] == 1
        assert dims["L"] == 2
        assert dims["T"] == -2
        assert dims["Q"] == 0

    def test_parse_dimensions_empty(self):
        from gpd.mcp.servers.verification_server import _parse_dimensions

        dims = _parse_dimensions("dimensionless")
        assert all(v == 0 for v in dims.values())

    def test_parse_dimensions_theta(self):
        from gpd.mcp.servers.verification_server import _parse_dimensions

        dims = _parse_dimensions("[M][L]^2[T]^-2[Theta]^-1")
        assert dims["Theta"] == -1


# ---------------------------------------------------------------------------
# ErrorStore unit tests (parsing logic)
# ---------------------------------------------------------------------------


class TestErrorStoreParsing:
    """Test ErrorStore parsing of markdown tables."""

    def test_parse_table_rows(self):
        from gpd.mcp.servers.errors_mcp import _parse_table_rows

        body = """\
| # | Error Class | Description | Detection | Example |
|---|---|---|---|---|
| 1 | **Wrong CG** | Bad coefficients | Check tables | 3j-symbol |
| 2 | **Symmetrization** | Wrong stats | Verify | Bose-Einstein |
"""
        rows = _parse_table_rows(body)
        # Should have header row + 2 data rows (header is not filtered by _parse_table_rows)
        assert len(rows) >= 2

    def test_strip_bold(self):
        from gpd.mcp.servers.errors_mcp import _strip_bold

        assert _strip_bold("**Bold text**") == "Bold text"
        assert _strip_bold("No bold") == "No bold"

    def test_infer_domain_from_id(self):
        from gpd.mcp.servers.errors_mcp import _infer_domain_from_id

        assert _infer_domain_from_id(1) == "core"
        assert _infer_domain_from_id(26) == "field_theory"
        assert _infer_domain_from_id(52) == "extended"
        assert _infer_domain_from_id(72) == "deep_domain"
        assert _infer_domain_from_id(82) == "cross_domain"
        assert _infer_domain_from_id(102) == "newly_identified"
        assert _infer_domain_from_id(200) == "unknown"


# ---------------------------------------------------------------------------
# ProtocolStore unit tests (parsing logic)
# ---------------------------------------------------------------------------


class TestProtocolStoreParsing:
    """Test ProtocolStore internal parsing helpers."""

    def test_extract_sections(self):
        from gpd.mcp.servers.protocols_server import _extract_sections

        body = """\
## Step 1
First step content.

## Step 2
Second step content.

### Sub-step
Details here.
"""
        sections = _extract_sections(body)
        assert len(sections) == 3
        assert sections[0]["title"] == "Step 1"
        assert sections[0]["level"] == 2

    def test_extract_steps(self):
        from gpd.mcp.servers.protocols_server import _extract_steps_and_checkpoints

        body = """\
## Procedure

1. Identify the small parameter
2. Expand to desired order
3. Collect terms

## Results
Some results here.
"""
        steps, _checkpoints = _extract_steps_and_checkpoints(body)
        assert len(steps) == 3
        assert steps[0] == "Identify the small parameter"

    def test_extract_checkpoints(self):
        from gpd.mcp.servers.protocols_server import _extract_steps_and_checkpoints

        body = """\
## Verification Checkpoints

- Check convergence radius
- Verify against known limits

## Other Section
Not a checkpoint.
"""
        _steps, checkpoints = _extract_steps_and_checkpoints(body)
        assert len(checkpoints) == 2

    def test_infer_domain(self):
        from gpd.mcp.servers.protocols_server import _infer_domain

        assert _infer_domain("perturbation-theory", []) == "core_derivation"
        assert _infer_domain("algebraic-qft", []) == "mathematical_methods"
        assert _infer_domain("string-field-theory", []) == "core_derivation"
        assert _infer_domain("monte-carlo", []) == "computational_methods"
        assert _infer_domain("group-theory", []) == "mathematical_methods"
        assert _infer_domain("numerical-computation", []) == "numerical_translation"
        assert _infer_domain("general-relativity", []) == "gr_cosmology"
        assert _infer_domain("unknown-protocol", []) == "general"


# ---------------------------------------------------------------------------
# Server __init__ helpers
# ---------------------------------------------------------------------------


class TestServerHelpers:
    """Test shared helpers from gpd.mcp.servers.__init__."""

    def test_parse_frontmatter_safe_valid(self):
        from gpd.mcp.servers import parse_frontmatter_safe

        text = "---\ntier: 1\ncontext_cost: low\n---\n# Title\nBody content."
        meta, body = parse_frontmatter_safe(text)
        assert meta["tier"] == 1
        assert "Title" in body

    def test_parse_frontmatter_safe_invalid(self):
        from gpd.mcp.servers import parse_frontmatter_safe

        text = "---\ninvalid: yaml: [broken\n---\n# Title"
        meta, body = parse_frontmatter_safe(text)
        assert meta == {}
        assert "Title" in body

    def test_parse_frontmatter_safe_no_frontmatter(self):
        from gpd.mcp.servers import parse_frontmatter_safe

        text = "# Just a document\nNo frontmatter here."
        meta, body = parse_frontmatter_safe(text)
        assert meta == {}


# ---------------------------------------------------------------------------
