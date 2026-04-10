"""Tests for the built-in GPD MCP servers.

Calls @mcp.tool() decorated functions directly with mock backends.
Covers: conventions, errors, patterns, protocols, skills, state, verification.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import anyio
import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _load_project_contract_fixture() -> dict[str, object]:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def _multi_claim_contract_fixture() -> dict[str, object]:
    return {
        "schema_version": 1,
        "scope": {
            "question": "Which benchmark and asymptotic regime does each claim recover?",
            "in_scope": ["claim-specific benchmark recovery"],
        },
        "context_intake": {
            "must_read_refs": ["ref-a", "ref-b"],
            "crucial_inputs": ["Use the claim-specific benchmark anchor and regime for each check."],
        },
        "observables": [
            {
                "id": "obs-a",
                "name": "observable A",
                "kind": "scalar",
                "definition": "Observable for claim A",
                "regime": "small-k",
            },
            {
                "id": "obs-b",
                "name": "observable B",
                "kind": "scalar",
                "definition": "Observable for claim B",
                "regime": "large-k",
            },
        ],
        "claims": [
            {
                "id": "claim-a",
                "statement": "Recover benchmark A",
                "observables": ["obs-a"],
                "deliverables": ["deliv-a"],
                "acceptance_tests": ["test-a"],
                "references": ["ref-a"],
            },
            {
                "id": "claim-b",
                "statement": "Recover benchmark B",
                "observables": ["obs-b"],
                "deliverables": ["deliv-b"],
                "acceptance_tests": ["test-b"],
                "references": ["ref-b"],
            },
        ],
        "deliverables": [
            {
                "id": "deliv-a",
                "description": "Benchmark A recovery note",
                "kind": "report",
                "must_contain": ["claim-a", "ref-a"],
            },
            {
                "id": "deliv-b",
                "description": "Benchmark B recovery note",
                "kind": "report",
                "must_contain": ["claim-b", "ref-b"],
            },
        ],
        "acceptance_tests": [
            {
                "id": "test-a",
                "subject": "claim-a",
                "kind": "benchmark",
                "procedure": "Compare against benchmark A",
                "pass_condition": "Matches A",
                "evidence_required": ["ref-a"],
            },
            {
                "id": "test-b",
                "subject": "claim-b",
                "kind": "benchmark",
                "procedure": "Compare against benchmark B",
                "pass_condition": "Matches B",
                "evidence_required": ["ref-b"],
            },
        ],
        "references": [
            {
                "id": "ref-a",
                "kind": "paper",
                "locator": "doi:10.1234/benchmark-a",
                "role": "benchmark",
                "why_it_matters": "Claim A anchor",
                "applies_to": ["claim-a"],
                "must_surface": True,
                "required_actions": ["compare"],
            },
            {
                "id": "ref-b",
                "kind": "paper",
                "locator": "doi:10.1234/benchmark-b",
                "role": "benchmark",
                "why_it_matters": "Claim B anchor",
                "applies_to": ["claim-b"],
                "must_surface": True,
                "required_actions": ["compare"],
            },
        ],
        "forbidden_proxies": [
            {
                "id": "fp-a",
                "subject": "claim-a",
                "proxy": "qualitative agreement without benchmark anchoring",
                "reason": "Claim A requires the explicit benchmark anchor.",
            },
            {
                "id": "fp-b",
                "subject": "claim-b",
                "proxy": "qualitative agreement without benchmark anchoring",
                "reason": "Claim B requires the explicit benchmark anchor.",
            },
        ],
        "links": [],
        "uncertainty_markers": {
            "weakest_anchors": ["Benchmark interpretation"],
            "disconfirming_observations": ["Claim-specific benchmark mismatch"],
        },
    }


def _proof_contract_fixture() -> dict[str, object]:
    return {
        "schema_version": 1,
        "scope": {
            "question": "Does the proof establish the theorem for all r_0 > 0?",
            "in_scope": ["proof-obligation audit"],
        },
        "context_intake": {
            "must_read_refs": ["ref-proof"],
            "crucial_inputs": ["Track every theorem parameter and conclusion clause through the proof."],
        },
        "observables": [
            {
                "id": "obs-proof",
                "name": "main theorem proof obligation",
                "kind": "proof_obligation",
                "definition": "Formal proof obligation for the main theorem",
            }
        ],
        "claims": [
            {
                "id": "claim-theorem",
                "statement": "For all r_0 > 0, the full theorem holds.",
                "claim_kind": "theorem",
                "observables": ["obs-proof"],
                "deliverables": ["deliv-summary"],
                "acceptance_tests": [
                    "test-proof-param",
                    "test-proof-align",
                    "test-proof-counterexample",
                ],
                "references": ["ref-proof"],
                "parameters": [
                    {"symbol": "r_0", "domain_or_type": "positive real", "aliases": ["r0"], "required_in_proof": True},
                    {"symbol": "n", "domain_or_type": "integer", "required_in_proof": True},
                ],
                "hypotheses": [{"id": "hyp-main", "text": "r_0 > 0", "required_in_proof": True}],
                "quantifiers": ["for all r_0 > 0"],
                "conclusion_clauses": [{"id": "conclusion-main", "text": "the theorem holds"}],
                "proof_deliverables": ["deliv-proof"],
            }
        ],
        "deliverables": [
            {
                "id": "deliv-summary",
                "kind": "report",
                "description": "Theorem summary note",
                "must_contain": ["theorem statement"],
            },
            {
                "id": "deliv-proof",
                "kind": "derivation",
                "description": "Formal theorem proof",
                "must_contain": ["proof audit"],
            },
        ],
        "acceptance_tests": [
            {
                "id": "test-proof-param",
                "subject": "claim-theorem",
                "kind": "proof_parameter_coverage",
                "procedure": "Audit theorem parameters against the proof body.",
                "pass_condition": "All theorem parameters remain present in the proof.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-align",
                "subject": "claim-theorem",
                "kind": "claim_to_proof_alignment",
                "procedure": "Audit the theorem statement against the proof conclusion.",
                "pass_condition": "The proof establishes the theorem exactly as stated.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-counterexample",
                "subject": "claim-theorem",
                "kind": "counterexample_search",
                "procedure": "Attempt an adversarial counterexample search.",
                "pass_condition": "No counterexample or narrowed claim is found.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
        ],
        "references": [
            {
                "id": "ref-proof",
                "kind": "paper",
                "locator": "doi:10.1000/proof",
                "role": "definition",
                "why_it_matters": "Defines the theorem statement and notation.",
                "applies_to": ["claim-theorem"],
                "must_surface": True,
                "required_actions": ["read"],
            }
        ],
        "forbidden_proxies": [
            {
                "id": "fp-proof",
                "subject": "claim-theorem",
                "proxy": "Algebraic consistency without theorem alignment",
                "reason": "The theorem still requires statement-to-proof alignment.",
            }
        ],
        "links": [],
        "uncertainty_markers": {
            "weakest_anchors": ["A theorem parameter could disappear from the proof body."],
            "disconfirming_observations": ["The proof only covers the r_0 = 0 special case."],
        },
    }


def _tool_description_and_schema(tool_name: str) -> tuple[str, dict[str, object]]:
    async def _load() -> tuple[str, dict[str, object]]:
        from gpd.mcp.servers.conventions_server import mcp

        tools = await mcp.list_tools()
        tool = next(tool for tool in tools if tool.name == tool_name)
        return tool.description, tool.inputSchema

    return anyio.run(_load)


class TestBuiltinServerDescriptors:
    """Tests for public built-in MCP server descriptor metadata."""

    def test_public_descriptor_prerequisites_are_runtime_neutral(self):
        from gpd.mcp.builtin_servers import build_public_descriptors

        descriptors = build_public_descriptors()
        expected = ["Install GPD before enabling built-in MCP servers."]

        for name, descriptor in descriptors.items():
            assert descriptor["prerequisites"] == expected, name
            prerequisite = descriptor["prerequisites"][0].lower()
            assert "npx" not in prerequisite, name
            assert "get-physics-done" not in prerequisite, name

    def test_public_descriptor_python_module_alternative_uses_versioned_launcher_label(self):
        from gpd.mcp.builtin_servers import build_public_descriptors

        descriptor = build_public_descriptors()["gpd-state"]
        python_module = descriptor["alternatives"]["python_module"]

        assert python_module["command"] == "${GPD_PYTHON}"
        assert isinstance(python_module["command"], str)
        assert (
            python_module["notes"]
            == "Replace `${GPD_PYTHON}` with a Python >=3.11 interpreter that has GPD installed."
        )

    def test_state_public_descriptor_lists_only_live_tools(self):
        from gpd.mcp.builtin_servers import build_public_descriptors

        descriptor = build_public_descriptors()["gpd-state"]

        assert descriptor["capabilities"] == [
            "get_state",
            "get_phase_info",
            "advance_plan",
            "get_progress",
            "validate_state",
            "run_health_check",
            "get_config",
        ]
        assert "emit_phase_event" not in descriptor["capabilities"]

    def test_state_public_descriptor_health_check_is_executable_without_fake_project_path(self):
        from gpd.mcp.builtin_servers import build_public_descriptors
        from gpd.mcp.servers.state_server import mcp

        descriptor = build_public_descriptors()["gpd-state"]
        health_check = descriptor["health_check"]

        async def _call() -> dict[str, object]:
            result = await mcp.call_tool(str(health_check["tool"]), dict(health_check["input"]))
            if isinstance(result, dict):
                return result
            if (
                isinstance(result, tuple)
                and len(result) == 2
                and isinstance(result[1], dict)
            ):
                return result[1]
            if (
                isinstance(result, list)
                and len(result) == 1
                and hasattr(result[0], "text")
                and isinstance(result[0].text, str)
            ):
                return json.loads(result[0].text)
            raise AssertionError(f"Unexpected MCP call result: {result!r}")

        result = anyio.run(_call)

        assert health_check["tool"] == "get_state"
        assert health_check["input"] == {}
        assert "missing required project_dir" in str(health_check["expect"])
        assert "/tmp/test" not in json.dumps(health_check)
        assert result["schema_version"] == 1
        assert "error" in result
        assert "project_dir" in result["error"]

    def test_build_mcp_servers_dict_checks_optional_modules_in_target_interpreter(self, monkeypatch):
        from gpd.mcp import builtin_servers

        target_python = "/opt/gpd/python3.11"
        current_python = "/usr/bin/python3.9"
        observed: dict[str, object] = {}

        def fake_run(command, *, check, stdout, stderr):
            observed["command"] = command
            observed["check"] = check
            observed["stdout"] = stdout
            observed["stderr"] = stderr
            return SimpleNamespace(returncode=0 if command[0] == target_python else 1)

        monkeypatch.setattr(builtin_servers.sys, "executable", current_python)
        monkeypatch.setattr(builtin_servers.subprocess, "run", fake_run)

        servers = builtin_servers.build_mcp_servers_dict(python_path=target_python)

        assert "gpd-arxiv" in servers
        assert observed["command"][0] == target_python
        assert observed["command"][2].startswith("import importlib.util")
        assert observed["command"][3] == "arxiv_mcp_server"
        assert observed["check"] is False


class TestMcpServerRunner:
    """Tests for shared MCP server CLI transport wiring."""

    def test_run_mcp_server_preserves_explicit_port_zero(self, monkeypatch):
        from gpd.mcp.servers import run_mcp_server

        calls: list[str] = []

        class FakeMCP:
            def __init__(self) -> None:
                self.settings = SimpleNamespace(host=None, port=8123)

            def run(self, transport: str) -> None:
                calls.append(transport)

        monkeypatch.setattr(sys, "argv", ["gpd-mcp-state", "--transport", "sse", "--port", "0"])

        mcp = FakeMCP()
        run_mcp_server(mcp, "fake server")

        assert mcp.settings.port == 0
        assert calls == ["sse"]

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

    def test_assert_convention_validate_missing_required_key(self):
        from gpd.mcp.servers.conventions_server import assert_convention_validate

        content = "% ASSERT_CONVENTION: metric_signature=(+,-,-,-)"
        lock = {
            "metric_signature": "(+,-,-,-)",
            "fourier_convention": "physics",
        }
        result = assert_convention_validate(content, lock)
        assert result["valid"] is False
        assert result["missing_required_keys"] == ["fourier_convention"]

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

        planning = tmp_path / "GPD"
        planning.mkdir()
        state = {
            "convention_lock": {
                "metric_signature": "(+,-,-,-)",
                "natural_units": "natural",
            }
        }
        (planning / "state.json").write_text(json.dumps(state), encoding="utf-8")
        result = convention_lock_status(str(tmp_path))
        assert result["set_count"] >= 2
        assert "metric_signature" in result["set_fields"]

    def test_convention_lock_status_empty_project(self, tmp_path):
        from gpd.mcp.servers.conventions_server import convention_lock_status

        planning = tmp_path / "GPD"
        planning.mkdir()
        result = convention_lock_status(str(tmp_path))
        assert result["set_count"] == 0

    def test_convention_set(self, tmp_path):
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({}), encoding="utf-8")

        result = convention_set(str(tmp_path), "metric_signature", "(+,-,-,-)")
        assert result["status"] == "set"
        assert result["key"] == "metric_signature"

    def test_convention_set_already_set(self, tmp_path):
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / "GPD"
        planning.mkdir()
        state = {"convention_lock": {"metric_signature": "(+,-,-,-)"}}
        (planning / "state.json").write_text(json.dumps(state), encoding="utf-8")

        result = convention_set(str(tmp_path), "metric_signature", "(-,+,+,+)")
        assert result["status"] == "already_set"

    def test_convention_set_custom_key(self, tmp_path):
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({}), encoding="utf-8")

        result = convention_set(str(tmp_path), "custom:my_convention", "my_value")
        assert result["status"] == "set"
        assert result["type"] == "custom"

    def test_convention_set_tool_schema_constrains_key_and_value_surface(self):
        from gpd.core.conventions import KEY_ALIASES, KNOWN_CONVENTIONS

        description, schema = _tool_description_and_schema("convention_set")

        key_schema = schema["properties"]["key"]
        value_schema = schema["properties"]["value"]

        assert "custom:<slug>" in description
        assert "blank or placeholder string" in description
        assert "Use None to clear a convention." not in description

        key_branches = key_schema["anyOf"]
        assert any(set(branch["enum"]) == set(KNOWN_CONVENTIONS) for branch in key_branches if "enum" in branch)
        assert any(set(branch["enum"]) == set(KEY_ALIASES) for branch in key_branches if "enum" in branch)
        assert any(
            branch.get("pattern") == r"^custom:[A-Za-z0-9][A-Za-z0-9_-]*$" and "custom:<slug>" in branch["description"]
            for branch in key_branches
        )
        assert "alias" in key_schema["description"]
        assert value_schema["minLength"] == 1
        assert value_schema["pattern"] == r"^(?!\s*(?:null|none|undefined)\s*$)\S(?:.*\S)?$"
        assert "placeholder strings" in value_schema["description"]
        assert "Use None to clear a convention." not in value_schema["description"]

    def test_convention_set_rejects_invalid_custom_key_shape(self, tmp_path):
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({}), encoding="utf-8")

        result = convention_set(str(tmp_path), "custom:bad key", "my_value")
        assert "error" in result
        assert "Custom convention keys" in result["error"]


    def test_load_lock_non_dict_state_json_fails_closed(self, tmp_path):
        """If state exists but is unrecoverable, the helper should fail closed."""
        from gpd.mcp.servers.conventions_server import _load_lock_from_project

        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="not recoverable"):
            _load_lock_from_project(str(tmp_path))

    def test_load_lock_string_state_json_fails_closed(self, tmp_path):
        """If state exists but is unrecoverable, the helper should fail closed."""
        from gpd.mcp.servers.conventions_server import _load_lock_from_project

        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps("just a string"), encoding="utf-8")
        with pytest.raises(ValueError, match="not recoverable"):
            _load_lock_from_project(str(tmp_path))

    def test_update_lock_non_dict_state_json_fails_closed(self, tmp_path):
        """If state exists but is unrecoverable, mutation should not flatten it to defaults."""
        from gpd.mcp.servers.conventions_server import _update_lock_in_project

        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="not recoverable"):
            _update_lock_in_project(str(tmp_path), lambda lk: lk.metric_signature)

    def test_load_lock_recovers_backup_only_convention_state(self, tmp_path):
        from gpd.core.state import default_state_dict
        from gpd.mcp.servers.conventions_server import _load_lock_from_project

        planning = tmp_path / "GPD"
        planning.mkdir()
        state = default_state_dict()
        state["convention_lock"] = {"metric_signature": "(+,-,-,-)"}
        (planning / "state.json.bak").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        lock = _load_lock_from_project(str(tmp_path))

        assert lock.metric_signature == "(+,-,-,-)"

    def test_load_lock_does_not_recover_intent_during_read_only_status_lookup(self, tmp_path):
        from gpd.core.constants import ProjectLayout
        from gpd.core.state import default_state_dict, generate_state_markdown, save_state_json
        from gpd.mcp.servers.conventions_server import _load_lock_from_project

        stale_state = default_state_dict()
        stale_state["convention_lock"] = {"metric_signature": "(+,-,-,-)"}
        save_state_json(tmp_path, stale_state)

        layout = ProjectLayout(tmp_path)
        recovered_state = default_state_dict()
        recovered_state["convention_lock"] = {"metric_signature": "(-,+,+,+)"}
        json_tmp = layout.gpd / ".state-json-tmp"
        md_tmp = layout.gpd / ".state-md-tmp"
        json_tmp.write_text(json.dumps(recovered_state, indent=2) + "\n", encoding="utf-8")
        md_tmp.write_text(generate_state_markdown(recovered_state), encoding="utf-8")
        layout.state_intent.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")

        before_state = layout.state_json.read_text(encoding="utf-8")

        lock = _load_lock_from_project(str(tmp_path))

        assert lock.metric_signature == "(+,-,-,-)"
        assert layout.state_intent.exists()
        assert layout.state_json.read_text(encoding="utf-8") == before_state

    def test_convention_set_preserves_backup_only_state_when_mutating_lock(self, tmp_path):
        from gpd.core.state import default_state_dict
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / "GPD"
        planning.mkdir()
        state = default_state_dict()
        state["position"]["current_phase"] = "09"
        state["convention_lock"] = {"metric_signature": "(+,-,-,-)"}
        (planning / "state.json.bak").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        result = convention_set(str(tmp_path), "fourier_convention", "physics")

        assert result["status"] == "set"
        persisted = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        assert persisted["position"]["current_phase"] == "09"
        assert persisted["convention_lock"]["metric_signature"] == "(+,-,-,-)"
        assert persisted["convention_lock"]["fourier_convention"] == "physics"

    def test_convention_set_returns_error_on_malformed_state_json(self, tmp_path):
        """convention_set returns an error dict (not raises) when state.json is malformed."""
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text("{bad json!!", encoding="utf-8")

        result = convention_set(str(tmp_path), "metric_signature", "(+,-,-,-)")
        assert "error" in result
        assert "Malformed" in result["error"] or "state.json" in result["error"]

    def test_convention_set_returns_error_on_empty_custom_key(self, tmp_path):
        """convention_set returns error dict for empty custom key."""
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({}), encoding="utf-8")

        result = convention_set(str(tmp_path), "custom:", "val")
        assert "error" in result
        assert "empty" in result["error"].lower()

    def test_convention_set_returns_error_on_os_error(self, tmp_path):
        """convention_set returns error dict when state.json is a directory (IsADirectoryError)."""
        from gpd.mcp.servers.conventions_server import convention_set

        # Make state.json a directory so reading it triggers IsADirectoryError
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").mkdir()

        result = convention_set(str(tmp_path), "metric_signature", "(+,-,-,-)")
        assert "error" in result

    def test_convention_lock_status_returns_error_on_malformed_state_json(self, tmp_path):
        """convention_lock_status returns error dict when state.json is malformed."""
        from gpd.mcp.servers.conventions_server import convention_lock_status

        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text("{bad json!!", encoding="utf-8")

        result = convention_lock_status(str(tmp_path))
        assert "error" in result
        assert "Malformed" in result["error"] or "state.json" in result["error"]

    def test_convention_lock_status_returns_error_on_os_error(self, tmp_path):
        """convention_lock_status returns error dict when state.json is a directory."""
        from gpd.mcp.servers.conventions_server import convention_lock_status

        # Make state.json a directory so reading it triggers IsADirectoryError
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").mkdir()

        result = convention_lock_status(str(tmp_path))
        assert "error" in result

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
        from gpd.mcp.servers.errors_mcp import REFERENCES_DIR, ErrorStore

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
            "requires:\n"
            "  files: [\"GPD/ROADMAP.md\"]\n"
            "---\n"
            "\n"
            "Canonical execute command.\n",
            encoding="utf-8",
        )
        (commands_dir / "plan-phase.md").write_text(
            "---\n"
            "name: gpd:plan-phase\n"
            "description: Create detailed execution plan.\n"
            "agent: gpd-planner\n"
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
            "Canonical help command.\n"
            "Try /gpd:help or /gpd:execute-phase for runtime-installed shells.\n"
            "## Contextual Help (State-Aware Variant)\n"
            "\n"
            "Use the state-aware help block to pick the current-state command set.\n",
            encoding="utf-8",
        )
        (commands_dir / "slides.md").write_text(
            "---\n"
            "name: gpd:slides\n"
            "description: Create presentation slides from a project or folder.\n"
            "---\n"
            "\n"
            "Canonical slides command.\n"
            "Read @{GPD_INSTALL_DIR}/workflows/slides.md.\n",
            encoding="utf-8",
        )
        (commands_dir / "peer-review.md").write_text(
            "---\n"
            "name: gpd:peer-review\n"
            "description: Conduct standalone peer review.\n"
            "context_mode: project-required\n"
            "requires:\n"
            "  files: [\"paper/*.tex\", \"paper/*.md\", \"manuscript/*.tex\", \"manuscript/*.md\", \"draft/*.tex\", \"draft/*.md\"]\n"
            "review-contract:\n"
            "  review_mode: publication\n"
            "  schema_version: 1\n"
            "  required_outputs: []\n"
            "  required_evidence: []\n"
            "  blocking_conditions: []\n"
            "  preflight_checks: []\n"
            "  stage_artifacts: []\n"
            "  conditional_requirements:\n"
            "    - when: theorem-bearing claims are present\n"
            "      required_outputs:\n"
            "        - GPD/review/PROOF-REDTEAM{round_suffix}.md\n"
            "      stage_artifacts:\n"
            "        - GPD/review/PROOF-REDTEAM{round_suffix}.md\n"
            "---\n"
            "\n"
            "Canonical peer review command.\n"
            "Use @{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md and "
            "@{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md.\n",
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
        (agents_dir / "gpd-check-proof.md").write_text(
            "---\n"
            "name: gpd-check-proof\n"
            "description: Red-team theorem proofs against their stated claims, parameters, hypotheses, quantifiers, and conclusion clauses, then writes a fail-closed proof audit artifact.\n"
            "---\n"
            "\n"
            "Proof critique kernel.\n"
            "Read {GPD_INSTALL_DIR}/references/shared/shared-protocols.md, "
            "{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md, "
            "{GPD_INSTALL_DIR}/references/physics-subfields.md, "
            "{GPD_INSTALL_DIR}/references/verification/core/verification-core.md, "
            "{GPD_INSTALL_DIR}/templates/proof-redteam-schema.md, "
            "{GPD_INSTALL_DIR}/references/verification/core/proof-redteam-protocol.md, "
            "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md.\n",
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

    def test_list_skills_returns_canonical_registry_index(self):
        from gpd.mcp.servers.skills_server import list_skills

        result = list_skills()
        assert result["count"] == 7
        names = {s["name"] for s in result["skills"]}
        # The MCP skills server exposes the canonical registry index, not a
        # runtime-specific discoverable install surface.
        assert "gpd-execute-phase" in names
        assert "gpd-plan-phase" in names
        assert "gpd-peer-review" in names
        assert "gpd-check-proof" in names
        assert "gpd-slides" in names
        assert "gpd-debugger" in names
        assert "gpd-help" in names

    def test_list_skills_by_category(self):
        from gpd.mcp.servers.skills_server import list_skills

        result = list_skills(category="execution")
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "gpd-execute-phase"

    def test_list_skills_empty_category(self):
        from gpd import registry as content_registry
        from gpd.mcp.servers.skills_server import list_skills

        result = list_skills(category="nonexistent")
        assert result == {
            "error": f"category must be one of: {', '.join(content_registry.skill_categories())}",
            "schema_version": 1,
        }

    def test_get_skill_found(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-execute-phase")
        assert result["name"] == "gpd-execute-phase"
        assert "Canonical execute command" in result["content"]
        assert result["requires"] == {"files": ["GPD/ROADMAP.md"]}
        assert result["content_authority"] == "canonical"
        assert result["structured_metadata_authority"] == {
            "content": "canonical",
            "context_mode": "mirrored",
            "project_reentry_capable": "mirrored",
            "allowed_tools": "mirrored",
            "requires": "mirrored",
            "review_contract": "mirrored",
        }
        assert "Treat `content` as the wrapper/context surface." in result["loading_hint"]
        assert "See `referenced_files` for external markdown dependencies." in result["loading_hint"]
        assert "It already embeds the model-visible `Command Requirements` section." in result["loading_hint"]
        assert result["file_count"] == 1
        assert result["allowed_tools_surface"] == "command.allowed-tools"

    def test_get_skill_surfaces_command_agent_metadata(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from gpd import registry as content_registry
        from gpd.mcp.servers.skills_server import get_skill

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir(exist_ok=True)
        (commands_dir / "plan-phase.md").write_text(
            "---\n"
            "name: gpd:plan-phase\n"
            "description: Plan.\n"
            "agent: gpd-planner\n"
            "allowed-tools:\n"
            "  - file_read\n"
            "---\n"
            "Read @{GPD_INSTALL_DIR}/workflows/plan-phase.md and {GPD_AGENTS_DIR}/gpd-planner.md.\n",
            encoding="utf-8",
        )
        manifest_path = tmp_path / "plan-phase-stage-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workflow_id": "plan-phase",
                    "stages": [
                        {
                            "id": "phase_bootstrap",
                            "order": 1,
                            "purpose": "phase lookup and routing",
                            "mode_paths": ["workflows/plan-phase.md"],
                            "required_init_fields": [],
                            "loaded_authorities": ["workflows/plan-phase.md"],
                            "conditional_authorities": [],
                            "must_not_eager_load": ["references/ui/ui-brand.md"],
                            "allowed_tools": ["file_read"],
                            "writes_allowed": [],
                            "produced_state": [],
                            "next_stages": [],
                            "checkpoints": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        original_resolve_manifest_path = content_registry.resolve_workflow_stage_manifest_path
        monkeypatch.setattr(content_registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(
            content_registry,
            "resolve_workflow_stage_manifest_path",
            lambda workflow_id: manifest_path if workflow_id == "plan-phase" else original_resolve_manifest_path(workflow_id),
        )
        content_registry.invalidate_cache()

        result = get_skill("gpd-plan-phase")

        assert result["agent"] == "gpd-planner"
        assert result["structured_metadata_authority"]["agent"] == "mirrored"
        assert "agent: gpd-planner" in result["content"]
        assert result["staged_loading"]["workflow_id"] == "plan-phase"
        assert result["staged_loading"]["stages"][0]["id"] == "phase_bootstrap"

    def test_get_skill_surfaces_plan_phase_staged_loading_sidecar(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from gpd import registry as content_registry
        from gpd.mcp.servers.skills_server import get_skill

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir(exist_ok=True)
        (commands_dir / "plan-phase.md").write_text(
            "---\n"
            "name: gpd:plan-phase\n"
            "description: Plan.\n"
            "agent: gpd-planner\n"
            "allowed-tools:\n"
            "  - file_read\n"
            "---\n"
            "Read @{GPD_INSTALL_DIR}/workflows/plan-phase.md and {GPD_AGENTS_DIR}/gpd-planner.md.\n",
            encoding="utf-8",
        )
        manifest_path = tmp_path / "plan-phase-stage-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workflow_id": "plan-phase",
                    "stages": [
                        {
                            "id": "phase_bootstrap",
                            "order": 1,
                            "purpose": "phase lookup and routing",
                            "mode_paths": ["workflows/plan-phase.md"],
                            "required_init_fields": [],
                            "loaded_authorities": ["workflows/plan-phase.md"],
                            "conditional_authorities": [],
                            "must_not_eager_load": ["references/ui/ui-brand.md"],
                            "allowed_tools": ["file_read"],
                            "writes_allowed": [],
                            "produced_state": [],
                            "next_stages": [],
                            "checkpoints": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        original_resolve_manifest_path = content_registry.resolve_workflow_stage_manifest_path
        monkeypatch.setattr(content_registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(
            content_registry,
            "resolve_workflow_stage_manifest_path",
            lambda workflow_id: manifest_path if workflow_id == "plan-phase" else original_resolve_manifest_path(workflow_id),
        )
        content_registry.invalidate_cache()

        result = get_skill("gpd-plan-phase")

        assert result["staged_loading"]["workflow_id"] == "plan-phase"
        assert result["staged_loading"]["stages"][0]["id"] == "phase_bootstrap"
        assert result["staged_loading"]["stages"][0]["loaded_authorities"] == ["workflows/plan-phase.md"]
        assert result["structured_metadata_authority"]["staged_loading"] == "mirrored"

    def test_get_skill_surfaces_execute_phase_staged_loading_sidecar(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from gpd import registry as content_registry
        from gpd.mcp.servers.skills_server import get_skill

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir(exist_ok=True)
        (commands_dir / "execute-phase.md").write_text(
            "---\n"
            "name: gpd:execute-phase\n"
            "description: Execute.\n"
            "agent: gpd-executor\n"
            "allowed-tools:\n"
            "  - file_read\n"
            "---\n"
            "Read @{GPD_INSTALL_DIR}/workflows/execute-phase.md and {GPD_AGENTS_DIR}/gpd-executor.md.\n",
            encoding="utf-8",
        )
        manifest_path = tmp_path / "execute-phase-stage-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workflow_id": "execute-phase",
                    "stages": [
                        {
                            "id": "phase_bootstrap",
                            "order": 1,
                            "purpose": "phase lookup and routing",
                            "mode_paths": ["workflows/execute-phase.md"],
                            "required_init_fields": [],
                            "loaded_authorities": ["workflows/execute-phase.md"],
                            "conditional_authorities": [],
                            "must_not_eager_load": ["references/ui/ui-brand.md"],
                            "allowed_tools": ["file_read"],
                            "writes_allowed": [],
                            "produced_state": [],
                            "next_stages": [],
                            "checkpoints": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        original_resolve_manifest_path = content_registry.resolve_workflow_stage_manifest_path
        monkeypatch.setattr(content_registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(
            content_registry,
            "resolve_workflow_stage_manifest_path",
            lambda workflow_id: manifest_path if workflow_id == "execute-phase" else original_resolve_manifest_path(workflow_id),
        )
        content_registry.invalidate_cache()

        result = get_skill("gpd-execute-phase")

        assert result["staged_loading"]["workflow_id"] == "execute-phase"
        assert result["staged_loading"]["stages"][0]["id"] == "phase_bootstrap"
        assert result["staged_loading"]["stages"][0]["loaded_authorities"] == ["workflows/execute-phase.md"]
        assert result["structured_metadata_authority"]["staged_loading"] == "mirrored"

    def test_get_skill_surfaces_referenced_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from gpd import registry as content_registry
        from gpd.mcp.servers.skills_server import get_skill

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir(exist_ok=True)
        (commands_dir / "plan-phase.md").write_text(
            "---\n"
            "name: gpd:plan-phase\n"
            "description: Plan.\n"
            "agent: gpd-planner\n"
            "allowed-tools:\n"
            "  - file_read\n"
            "---\n"
            "Read @{GPD_INSTALL_DIR}/workflows/plan-phase.md and {GPD_AGENTS_DIR}/gpd-planner.md.\n",
            encoding="utf-8",
        )
        manifest_path = tmp_path / "plan-phase-stage-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workflow_id": "plan-phase",
                    "stages": [
                        {
                            "id": "phase_bootstrap",
                            "order": 1,
                            "purpose": "phase lookup and routing",
                            "mode_paths": ["workflows/plan-phase.md"],
                            "required_init_fields": [],
                            "loaded_authorities": ["workflows/plan-phase.md"],
                            "conditional_authorities": [],
                            "must_not_eager_load": ["references/ui/ui-brand.md"],
                            "allowed_tools": ["file_read"],
                            "writes_allowed": [],
                            "produced_state": [],
                            "next_stages": [],
                            "checkpoints": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        original_resolve_manifest_path = content_registry.resolve_workflow_stage_manifest_path
        monkeypatch.setattr(content_registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(
            content_registry,
            "resolve_workflow_stage_manifest_path",
            lambda workflow_id: manifest_path if workflow_id == "plan-phase" else original_resolve_manifest_path(workflow_id),
        )
        content_registry.invalidate_cache()

        result = get_skill("gpd-plan-phase")

        assert result["reference_count"] >= 1
        assert any(entry["kind"] == "workflow" for entry in result["referenced_files"])
        assert all(not entry["path"].startswith("/") for entry in result["referenced_files"])

    def test_get_skill_surfaces_direct_and_transitive_references_when_exposed(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-bibliographer")

        if "transitive_referenced_files" not in result:
            pytest.skip("Phase 15 product lane has not exposed transitive skill metadata yet")

        direct_paths = {entry["path"] for entry in result["referenced_files"]}
        transitive_paths = {entry["path"] for entry in result["transitive_referenced_files"]}

        assert "error" not in result
        assert result["reference_count"] == len(direct_paths)
        assert result["transitive_reference_count"] == len(transitive_paths)
        assert direct_paths.isdisjoint(transitive_paths)
        assert any(path.endswith("shared-protocols.md") for path in direct_paths)
        assert any(path.endswith("bibliography-advanced-search.md") for path in transitive_paths)

    def test_get_skill_consistency_checker_surfaces_agent_metadata(self):
        from gpd import registry as content_registry
        from gpd.mcp.servers.skills_server import get_skill

        repo_root = Path(__file__).resolve().parents[2]
        with (
            patch("gpd.registry.COMMANDS_DIR", repo_root / "src" / "gpd" / "commands"),
            patch("gpd.registry.AGENTS_DIR", repo_root / "src" / "gpd" / "agents"),
        ):
            content_registry.invalidate_cache()
            result = get_skill("gpd-consistency-checker")
            content_registry.invalidate_cache()

        direct_paths = {entry["path"] for entry in result["referenced_files"]}

        assert "error" not in result
        assert result["name"] == "gpd-consistency-checker"
        assert result["allowed_tools_surface"] == "agent.tools"
        assert result["content_authority"] == "canonical"
        assert result["allowed_tools"] == ["file_read", "file_write", "shell", "search_files", "find_files"]
        assert result["agent_policy"] == {
            "commit_authority": "orchestrator",
            "surface": "internal",
            "role_family": "verification",
            "artifact_write_authority": "scoped_write",
            "shared_state_authority": "return_only",
            "tools": ["file_read", "file_write", "shell", "search_files", "find_files"],
        }
        assert result["structured_metadata_authority"] == {
            "content": "canonical",
            "allowed_tools": "mirrored",
            "agent_policy": "mirrored",
        }
        assert result["schema_references"] == []
        assert result["schema_documents"] == []
        assert result["contract_references"] == []
        assert result["contract_documents"] == []
        assert result["reference_count"] == len(direct_paths)
        assert result["transitive_reference_count"] == 0
        assert result["transitive_referenced_files"] == []
        assert "@GPD/CONVENTIONS.md" in direct_paths
        assert "@GPD/phases/{scope}/CONSISTENCY-CHECK.md" in direct_paths
        assert "@GPD/CONSISTENCY-CHECK.md" in direct_paths

    def test_get_skill_surfaces_schema_references(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-peer-review")
        schema_documents = {Path(entry["path"]).name: entry for entry in result["schema_documents"]}
        contract_documents = {Path(entry["path"]).name: entry for entry in result["contract_documents"]}

        assert "error" not in result
        assert any(path.endswith("review-ledger-schema.md") for path in result["schema_references"])
        assert any(path.endswith("referee-decision-schema.md") for path in result["schema_references"])
        assert "review-ledger-schema.md" in schema_documents
        assert "Review Ledger Schema" in schema_documents["review-ledger-schema.md"]["body"]
        assert "referee-decision-schema.md" in schema_documents
        assert "Referee Decision Schema" in schema_documents["referee-decision-schema.md"]["body"]
        assert "review-ledger-schema.md" not in contract_documents
        assert "Treat `content` as the wrapper/context surface." in result["loading_hint"]
        assert "Load `schema_documents` and `contract_documents` too when present" in result["loading_hint"]
        assert result["content_authority"] == "canonical"
        assert result["structured_metadata_authority"] == {
            "content": "canonical",
            "context_mode": "mirrored",
            "project_reentry_capable": "mirrored",
            "allowed_tools": "mirrored",
            "requires": "mirrored",
            "review_contract": "mirrored",
        }
        assert "It already embeds the model-visible `Command Requirements` section." in result["loading_hint"]
        assert result["context_mode"] == "project-required"
        assert result["project_reentry_capable"] is False
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
        assert "## Review Contract" in result["content"]
        assert "review_contract:" in result["content"]
        assert "review-contract:" not in result["content"]
        assert all(not entry["path"].startswith("/") for entry in result["schema_documents"])
        assert all(not entry["path"].startswith("/") for entry in result["contract_documents"])

    def test_get_skill_surfaces_direct_plan_checker_schema_reference(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from functools import lru_cache
        from shutil import copytree

        from gpd import registry as content_registry
        from gpd.mcp.servers.skills_server import get_skill

        agents_dir = tmp_path / "agents"
        copytree(Path(__file__).resolve().parents[2] / "src" / "gpd" / "agents", agents_dir, dirs_exist_ok=True)
        plan_checker_path = agents_dir / "gpd-plan-checker.md"
        plan_checker_text = plan_checker_path.read_text(encoding="utf-8")
        plan_checker_text = plan_checker_text.replace(
            "artifact_write_authority: return_only",
            "artifact_write_authority: read_only",
        )
        plan_checker_path.write_text(
            plan_checker_text.replace(
                "tools: file_read, file_write, shell, find_files, search_files, web_search, web_fetch",
                "tools: file_read, shell, find_files, search_files, web_search, web_fetch",
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(content_registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(
            content_registry,
            "_builtin_agent_names",
            lru_cache(maxsize=1)(lambda: frozenset()),
        )
        content_registry.invalidate_cache()

        result = get_skill("gpd-plan-checker")
        schema_documents = {Path(entry["path"]).name: entry for entry in result["schema_documents"]}

        assert "error" not in result
        assert result["allowed_tools_surface"] == "agent.tools"
        assert "file_write" not in result["allowed_tools"]
        assert any(path.endswith("plan-contract-schema.md") for path in result["schema_references"])
        assert "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" in result["content"]
        assert "plan-contract-schema.md" in schema_documents
        assert "PLAN Contract Schema" in schema_documents["plan-contract-schema.md"]["body"]
        assert "approved_plans" in result["content"]
        assert "blocked_plans" in result["content"]

    def test_get_skill_surfaces_dedicated_proof_redteam_schema_and_contract_docs(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-check-proof")
        schema_documents = {Path(entry["path"]).name: entry for entry in result["schema_documents"]}
        contract_documents = {Path(entry["path"]).name: entry for entry in result["contract_documents"]}

        assert "error" not in result
        assert any(path.endswith("proof-redteam-schema.md") for path in result["schema_references"])
        assert any(path.endswith("proof-redteam-protocol.md") for path in result["contract_references"])
        assert "proof-redteam-schema.md" in schema_documents
        assert "Proof Redteam" in schema_documents["proof-redteam-schema.md"]["body"]
        assert "proof-redteam-protocol.md" in contract_documents
        assert "Proof Redteam Protocol" in contract_documents["proof-redteam-protocol.md"]["body"]
        assert any(path.endswith("peer-review-panel.md") for path in result["contract_references"])
        assert "Treat `content` as the wrapper/context surface." in result["loading_hint"]
        assert "Load `schema_documents` and `contract_documents` too when present" in result["loading_hint"]

    def test_get_skill_resume_work_surfaces_project_reentry_metadata(self):
        from gpd.mcp.servers.skills_server import get_skill
        from gpd.registry import CommandDef, SkillDef

        command = CommandDef(
            name="gpd:resume-work",
            description="Resume.",
            argument_hint="",
            requires={},
            allowed_tools=["file_read", "shell"],
            content="Resume body.",
            path="/tmp/gpd-resume-work.md",
            source="commands",
            context_mode="project-required",
            project_reentry_capable=True,
        )
        skill = SkillDef(
            name="gpd-resume-work",
            description="Resume.",
            content="Resume body.",
            category="session",
            path="/tmp/gpd-resume-work.md",
            source_kind="command",
            registry_name="resume-work",
        )

        with (
            patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
            patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
        ):
            result = get_skill("gpd-resume-work")

        assert result["context_mode"] == "project-required"
        assert result["project_reentry_capable"] is True
        assert result["argument_hint"] == ""

    @pytest.mark.parametrize(
        ("skill_name", "visible_token"),
        [
            ("gpd-resume-work", "Canonical continuation fields define the public resume vocabulary"),
            ("gpd-sync-state", "Canonical reconciliation contract:"),
        ],
    )
    def test_get_skill_resume_and_sync_state_keep_prompt_visibility_without_staged_loading_sidecar(
        self,
        skill_name: str,
        visible_token: str,
    ) -> None:
        from gpd.mcp.servers.skills_server import get_skill
        from gpd.registry import CommandDef, SkillDef

        command = CommandDef(
            name=skill_name.replace("gpd-", "gpd:"),
            description="Resume." if skill_name == "gpd-resume-work" else "Sync state.",
            argument_hint="",
            requires={},
            allowed_tools=["file_read", "shell"],
            content=f"{visible_token} Body.",
            path=f"/tmp/{skill_name}.md",
            source="commands",
            context_mode="project-required",
            project_reentry_capable=skill_name == "gpd-resume-work",
        )
        skill = SkillDef(
            name=skill_name,
            description=command.description,
            content=command.content,
            category="session",
            path=command.path,
            source_kind="command",
            registry_name=skill_name.removeprefix("gpd-"),
        )

        with (
            patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
            patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
        ):
            result = get_skill(skill_name)

        assert "staged_loading" not in result
        assert visible_token in result["content"]
        assert result["allowed_tools_surface"] == "command.allowed-tools"

    def test_get_skill_new_project_surfaces_staged_loading_sidecar(self):
        from gpd import registry
        from gpd.mcp.servers.skills_server import get_skill

        repo_root = Path(__file__).resolve().parents[2]
        with (
            patch("gpd.registry.COMMANDS_DIR", repo_root / "src" / "gpd" / "commands"),
            patch("gpd.registry.AGENTS_DIR", repo_root / "src" / "gpd" / "agents"),
        ):
            registry.invalidate_cache()
            result = get_skill("gpd-new-project")

        assert result["staged_loading"]["workflow_id"] == "new-project"
        assert result["staged_loading"]["stages"][0]["id"] == "scope_intake"
        assert result["staged_loading"]["stages"][1]["loaded_authorities"] == [
            "templates/project-contract-schema.md",
            "templates/project-contract-grounding-linkage.md",
            "references/shared/canonical-schema-discipline.md",
        ]
        assert result["structured_metadata_authority"]["staged_loading"] == "mirrored"

    def test_get_skill_new_milestone_surfaces_staged_loading_sidecar(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from gpd import registry
        from gpd.mcp.servers.skills_server import get_skill

        manifest_path = tmp_path / "new-milestone-stage-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workflow_id": "new-milestone",
                    "stages": [
                        {
                            "id": "milestone_bootstrap",
                            "order": 1,
                            "purpose": "milestone lookup and routing",
                            "mode_paths": ["workflows/new-milestone.md"],
                            "required_init_fields": [],
                            "loaded_authorities": ["workflows/new-milestone.md"],
                            "conditional_authorities": [],
                            "must_not_eager_load": ["references/research/questioning.md"],
                            "allowed_tools": ["file_read", "task"],
                            "writes_allowed": [],
                            "produced_state": [],
                            "next_stages": [],
                            "checkpoints": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        original_resolve_manifest_path = registry.resolve_workflow_stage_manifest_path
        monkeypatch.setattr(
            registry,
            "resolve_workflow_stage_manifest_path",
            lambda workflow_id: manifest_path
            if workflow_id == "new-milestone"
            else original_resolve_manifest_path(workflow_id),
        )
        repo_root = Path(__file__).resolve().parents[2]
        with (
            patch("gpd.registry.COMMANDS_DIR", repo_root / "src" / "gpd" / "commands"),
            patch("gpd.registry.AGENTS_DIR", repo_root / "src" / "gpd" / "agents"),
        ):
            registry.invalidate_cache()
            command = registry.get_command("gpd:new-milestone")
            skill = registry.SkillDef(
                name="gpd-new-milestone",
                description="Milestone.",
                content=command.content,
                category="session",
                path=command.path,
                source_kind="command",
                registry_name="new-milestone",
            )

            with (
                patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
                patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
            ):
                result = get_skill("gpd-new-milestone")

        assert result["staged_loading"]["workflow_id"] == "new-milestone"
        assert result["staged_loading"]["stages"][0]["id"] == "milestone_bootstrap"
        assert result["staged_loading"]["stages"][0]["loaded_authorities"] == ["workflows/new-milestone.md"]
        assert result["structured_metadata_authority"]["staged_loading"] == "mirrored"

    def test_get_skill_agent_uses_primary_agent_content(self):
        from gpd import registry
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-debugger")
        agent = registry.get_agent("gpd-debugger")
        # Agent-backed entries remain part of the canonical MCP skill index.
        assert result["name"] == "gpd-debugger"
        assert result["content"] == agent.system_prompt
        assert "Primary debugger agent" in result["content"]
        assert "## Agent Requirements" in result["content"]
        assert result["content"].count("## Agent Requirements") == 1
        assert "## Agent Policy" not in result["content"]
        assert result["structured_metadata_authority"] == {
            "content": "canonical",
            "allowed_tools": "mirrored",
            "agent_policy": "mirrored",
        }
        assert "commit_authority" in result["content"]
        assert "artifact_write_authority" in result["content"]
        assert "shared_state_authority" in result["content"]
        assert result["agent_policy"] == {
            "commit_authority": agent.commit_authority,
            "surface": agent.surface,
            "role_family": agent.role_family,
            "artifact_write_authority": agent.artifact_write_authority,
            "shared_state_authority": agent.shared_state_authority,
            "tools": agent.tools,
        }


    def test_get_skill_debug_command_surfaces_debugger_seam_and_has_no_direct_schema_dependencies(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        from gpd import registry as content_registry
        from gpd.mcp.servers.skills_server import get_skill

        repo_root = Path(__file__).resolve().parents[2]
        monkeypatch.setattr(content_registry, "COMMANDS_DIR", repo_root / "src" / "gpd" / "commands")
        monkeypatch.setattr(content_registry, "AGENTS_DIR", repo_root / "src" / "gpd" / "agents")
        content_registry.invalidate_cache()

        result = get_skill("gpd-debug")

        assert result["name"] == "gpd-debug"
        assert result["allowed_tools_surface"] == "command.allowed-tools"
        assert result["allowed_tools"] == ["file_read", "shell", "task", "ask_user"]
        assert result["structured_metadata_authority"] == {
            "content": "canonical",
            "context_mode": "mirrored",
            "project_reentry_capable": "mirrored",
            "allowed_tools": "mirrored",
            "requires": "mirrored",
            "review_contract": "mirrored",
        }
        assert result["schema_references"] == []
        assert result["schema_documents"] == []
        assert result["contract_references"] == []
        assert result["contract_documents"] == []
        assert "gpd-debugger" in result["content"]
        assert 'subagent_type="gpd-debugger"' in result["content"]


    def test_get_skill_executor_agent_defers_completion_only_materials_until_summary_creation(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        from gpd import registry as content_registry
        from gpd.mcp.servers.skills_server import get_skill

        repo_agents_dir = Path(__file__).resolve().parents[2] / "src/gpd/agents"
        monkeypatch.setattr(content_registry, "AGENTS_DIR", repo_agents_dir)
        content_registry.invalidate_cache()

        result = get_skill("gpd-executor")

        assert "error" not in result
        bootstrap, _, _ = result["content"].partition("<summary_creation>")

        assert result["name"] == "gpd-executor"
        assert result["allowed_tools_surface"] == "agent.tools"
        assert "staged_loading" not in result
        assert "templates/summary.md" not in bootstrap
        assert "templates/calculation-log.md" not in bootstrap
        assert "Order-of-Limits Awareness" not in bootstrap

    def test_get_skill_planner_agent_defers_execution_materials_into_on_demand_references(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        from gpd import registry as content_registry
        from gpd.mcp.servers.skills_server import get_skill

        repo_agents_dir = Path(__file__).resolve().parents[2] / "src/gpd/agents"
        monkeypatch.setattr(content_registry, "AGENTS_DIR", repo_agents_dir)
        content_registry.invalidate_cache()

        result = get_skill("gpd-planner")
        bootstrap, separator, _ = result["content"].partition("On-demand references:")

        assert "error" not in result
        assert result["name"] == "gpd-planner"
        assert result["allowed_tools_surface"] == "agent.tools"
        assert "staged_loading" not in result
        assert separator == "On-demand references:"
        assert "Phase Plan Prompt" in bootstrap
        assert "PLAN Contract Schema" in bootstrap
        assert "Read config.json for planning behavior settings." not in bootstrap
        assert "## Summary Template" not in bootstrap
        assert "Order-of-Limits Awareness" not in bootstrap

    def test_get_skill_loading_hint_only_claims_schema_documents_when_loaded(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-slides")

        assert "error" not in result
        assert result["reference_count"] > 0
        assert result["schema_documents"] == []
        assert result["contract_documents"] == []
        assert "See `referenced_files` for external markdown dependencies." in result["loading_hint"]
        assert "schema_documents and contract_documents mirror loaded schema and contract markdown bodies." not in result[
            "loading_hint"
        ]

    def test_get_skill_canonicalizes_runtime_command_examples(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd-help")

        assert "/gpd:" not in result["content"]
        assert "gpd-help" in result["content"]
        assert "gpd-execute-phase" in result["content"]
        assert "## Command Requirements" in result["content"]
        assert "Try gpd-help or gpd-execute-phase for runtime-installed shells." in result["content"]
        assert "## Contextual Help" in result["content"]

    def test_get_skill_resolves_install_and_agents_placeholders(self):
        from gpd.mcp.servers.skills_server import get_skill
        from gpd.registry import AGENTS_DIR, SPECS_DIR

        result = get_skill("gpd-plan-phase")

        assert str(SPECS_DIR.resolve()) not in result["content"]
        assert str(AGENTS_DIR.resolve()) not in result["content"]
        assert "@{GPD_INSTALL_DIR}/workflows/plan-phase.md" in result["content"]

    def test_get_skill_resolves_slides_workflow_placeholder(self):
        from gpd.mcp.servers.skills_server import get_skill
        from gpd.registry import SPECS_DIR

        result = get_skill("gpd-slides")

        assert str(SPECS_DIR.resolve()) not in result["content"]
        assert "@{GPD_INSTALL_DIR}/workflows/slides.md" in result["content"]

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

    def test_route_skill_slides(self):
        from gpd.mcp.servers.skills_server import route_skill

        result = route_skill("build a beamer slide deck for a seminar presentation")
        assert result["suggestion"] == "gpd-slides"

    def test_route_skill_suggest_next_from_direct_question(self):
        from gpd.mcp.servers.skills_server import route_skill
        from gpd.registry import SkillDef

        with patch(
            "gpd.mcp.servers.skills_server._load_skill_index",
            return_value=[
                SkillDef(
                    name="gpd-suggest-next",
                    description="Suggest the next action.",
                    content="Suggest next.",
                    category="help",
                    path="/tmp/gpd-suggest-next.md",
                    source_kind="command",
                    registry_name="suggest-next",
                ),
                SkillDef(
                    name="gpd-help",
                    description="Help.",
                    content="Help.",
                    category="help",
                    path="/tmp/gpd-help.md",
                    source_kind="command",
                    registry_name="help",
                ),
                SkillDef(
                    name="gpd-new-project",
                    description="Create projects.",
                    content="New project.",
                    category="project",
                    path="/tmp/gpd-new-project.md",
                    source_kind="command",
                    registry_name="new-project",
                ),
            ],
        ):
            result = route_skill("what should I do next for this project?")
        assert result["suggestion"] == "gpd-suggest-next"

    def test_route_skill_suggest_next_from_next_step_prompt(self):
        from gpd.mcp.servers.skills_server import route_skill
        from gpd.registry import SkillDef

        with patch(
            "gpd.mcp.servers.skills_server._load_skill_index",
            return_value=[
                SkillDef(
                    name="gpd-suggest-next",
                    description="Suggest the next action.",
                    content="Suggest next.",
                    category="help",
                    path="/tmp/gpd-suggest-next.md",
                    source_kind="command",
                    registry_name="suggest-next",
                ),
                SkillDef(
                    name="gpd-help",
                    description="Help.",
                    content="Help.",
                    category="help",
                    path="/tmp/gpd-help.md",
                    source_kind="command",
                    registry_name="help",
                ),
                SkillDef(
                    name="gpd-progress",
                    description="Project progress.",
                    content="Progress.",
                    category="status",
                    path="/tmp/gpd-progress.md",
                    source_kind="command",
                    registry_name="progress",
                ),
            ],
        ):
            result = route_skill("what is the next step for my project?")
        assert result["suggestion"] == "gpd-suggest-next"

    def test_route_skill_no_match(self):
        from gpd.mcp.servers.skills_server import route_skill

        result = route_skill("zzz yyy xxx")
        assert result["suggestion"] == "gpd-help"
        assert result["confidence"] <= 0.1

    def test_route_skill_debug_intent_prefers_gpd_debug(self):
        from gpd.mcp.servers.skills_server import route_skill
        from gpd.registry import SkillDef

        with patch(
            "gpd.mcp.servers.skills_server._load_skill_index",
            return_value=[
                SkillDef(
                    name="gpd-debug",
                    description="Debug physics calculations.",
                    content="Debug command.",
                    category="execution",
                    path="/tmp/gpd-debug.md",
                    source_kind="command",
                    registry_name="debug",
                ),
                SkillDef(
                    name="gpd-debugger",
                    description="Debugger.",
                    content="Debugger agent.",
                    category="debugging",
                    path="/tmp/gpd-debugger.md",
                    source_kind="agent",
                    registry_name="gpd-debugger",
                ),
                SkillDef(
                    name="gpd-help",
                    description="Help.",
                    content="Help.",
                    category="help",
                    path="/tmp/gpd-help.md",
                    source_kind="command",
                    registry_name="help",
                ),
            ],
        ):
            result = route_skill("debug this physics calculation")

        assert result["suggestion"] == "gpd-debug"

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

    def test_route_skill_matches_multiword_resume_phrase(self):
        from gpd.mcp.servers.skills_server import route_skill
        from gpd.registry import SkillDef

        with patch(
            "gpd.mcp.servers.skills_server._load_skill_index",
            return_value=[
                SkillDef(
                    name="gpd-resume-work",
                    description="Resume interrupted work.",
                    content="Resume command.",
                    category="execution",
                    path="/tmp/gpd-resume-work.md",
                    source_kind="command",
                    registry_name="resume-work",
                ),
                SkillDef(
                    name="gpd-help",
                    description="Help.",
                    content="Help.",
                    category="help",
                    path="/tmp/gpd-help.md",
                    source_kind="command",
                    registry_name="help",
                ),
                SkillDef(
                    name="gpd-progress",
                    description="Progress.",
                    content="Progress command.",
                    category="status",
                    path="/tmp/gpd-progress.md",
                    source_kind="command",
                    registry_name="progress",
                ),
            ],
        ):
            result = route_skill("pick up where I left off after the last checkpoint")

        assert result["suggestion"] == "gpd-resume-work"

    def test_get_skill_index(self):
        from gpd.mcp.servers.skills_server import get_skill_index

        result = get_skill_index()
        assert result["total_skills"] == 7
        assert "index_text" in result
        assert "gpd-execute-phase" in result["index_text"]
        assert "gpd-peer-review" in result["index_text"]
        assert "gpd-debugger" in result["index_text"]
        assert "/gpd:debugger" not in result["index_text"]

    def test_get_skill_accepts_command_style_name(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("gpd:execute-phase")
        assert result["name"] == "gpd-execute-phase"
        assert "Canonical execute command" in result["content"]

    def test_get_skill_accepts_public_index_label(self):
        from gpd.mcp.servers.skills_server import get_skill

        result = get_skill("/gpd:execute-phase")
        assert result["name"] == "gpd-execute-phase"
        assert "Canonical execute command" in result["content"]


# ---------------------------------------------------------------------------
# 6. State server
# ---------------------------------------------------------------------------


class TestStateServer:
    """Tests for gpd.mcp.servers.state_server tool functions."""

    def test_get_state_rejects_relative_project_dir(self):
        from gpd.mcp.servers.state_server import get_state

        with patch("gpd.mcp.servers.state_server.load_state_json", side_effect=AssertionError("should not run")):
            result = get_state("relative/project")

        assert result["error"] == "project_dir must be an absolute path"
        assert result["schema_version"] == 1

    def test_load_state_json_omits_legacy_session_mirror(self, fake_project_dir):
        from gpd.mcp.servers.state_server import load_state_json

        mock_state = {
            "position": {"current_phase": "01"},
            "decisions": [],
            "blockers": [],
            "session": {"last_date": "2026-01-01"},
        }

        with (
            patch("gpd.mcp.servers.state_server.peek_state_json", return_value=(mock_state, [], "state.json")),
            patch(
                "gpd.mcp.servers.state_server._project_contract_runtime_payload_for_state",
                return_value=(
                    {"status": "loaded"},
                    {"valid": True},
                    {"authoritative": True},
                ),
            ),
        ):
            result = load_state_json(Path(fake_project_dir))

        assert result is not None
        assert "session" not in result
        assert result["position"]["current_phase"] == "01"
        assert result["project_contract_load_info"]["status"] == "loaded"
        assert result["project_contract_validation"]["valid"] is True
        assert result["project_contract_gate"]["authoritative"] is True

    def test_get_state(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_state

        mock_state = {
            "position": {"current_phase": "01"},
            "decisions": [],
            "blockers": [],
            "project_contract_load_info": {"status": "loaded"},
            "project_contract_validation": {"valid": True},
            "project_contract_gate": {"authoritative": True},
        }

        with patch("gpd.mcp.servers.state_server.load_state_json", return_value=mock_state):
            result = get_state(fake_project_dir)
        assert "position" in result
        assert result["position"]["current_phase"] == "01"
        assert result["project_contract_load_info"]["status"] == "loaded"
        assert result["project_contract_validation"]["valid"] is True
        assert result["project_contract_gate"]["authoritative"] is True

    def test_state_server_load_state_json_does_not_recover_intent_during_read_only_lookup(self, tmp_path):
        from gpd.core.constants import ProjectLayout
        from gpd.core.state import default_state_dict, generate_state_markdown, save_state_json
        from gpd.mcp.servers.state_server import load_state_json

        stale_state = default_state_dict()
        stale_state["position"]["current_phase"] = "01"
        save_state_json(tmp_path, stale_state)

        layout = ProjectLayout(tmp_path)
        recovered_state = default_state_dict()
        recovered_state["position"]["current_phase"] = "05"
        json_tmp = layout.gpd / ".state-json-tmp"
        md_tmp = layout.gpd / ".state-md-tmp"
        json_tmp.write_text(json.dumps(recovered_state, indent=2) + "\n", encoding="utf-8")
        md_tmp.write_text(generate_state_markdown(recovered_state), encoding="utf-8")
        layout.state_intent.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")

        before_state = layout.state_json.read_text(encoding="utf-8")

        result = load_state_json(tmp_path)

        assert result is not None
        assert result["position"]["current_phase"] == "01"
        assert layout.state_intent.exists()
        assert layout.state_json.read_text(encoding="utf-8") == before_state

    def test_get_state_no_state(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_state

        with patch("gpd.mcp.servers.state_server.load_state_json", return_value=None):
            result = get_state(fake_project_dir)
        assert "error" in result

    def test_get_state_gpd_error(self, fake_project_dir):
        from gpd.core.errors import GPDError
        from gpd.mcp.servers.state_server import get_state

        with patch("gpd.mcp.servers.state_server.load_state_json", side_effect=GPDError("boom")):
            result = get_state(fake_project_dir)
        assert result == {"error": "boom", "schema_version": 1}

    def test_get_state_os_error(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_state

        with patch("gpd.mcp.servers.state_server.load_state_json", side_effect=OSError("permission denied")):
            result = get_state(fake_project_dir)
        assert result == {"error": "permission denied", "schema_version": 1}

    def test_get_state_value_error(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_state

        with patch("gpd.mcp.servers.state_server.load_state_json", side_effect=ValueError("bad json")):
            result = get_state(fake_project_dir)
        assert result == {"error": "bad json", "schema_version": 1}

    def test_get_phase_info_gpd_error(self, fake_project_dir):
        from gpd.core.errors import GPDError
        from gpd.mcp.servers.state_server import get_phase_info

        with patch("gpd.core.phases.find_phase", side_effect=GPDError("phase read failed")):
            result = get_phase_info(fake_project_dir, "01")
        assert result == {"error": "phase read failed", "schema_version": 1}

    def test_get_phase_info_os_error(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_phase_info

        with patch("gpd.core.phases.find_phase", side_effect=OSError("disk error")):
            result = get_phase_info(fake_project_dir, "01")
        assert result == {"error": "disk error", "schema_version": 1}

    def test_get_progress_gpd_error(self, fake_project_dir):
        from gpd.core.errors import GPDError
        from gpd.mcp.servers.state_server import get_progress

        with patch("gpd.mcp.servers.state_server.progress_render", side_effect=GPDError("no state")):
            result = get_progress(fake_project_dir)
        assert result == {"error": "no state", "schema_version": 1}

    def test_get_progress_os_error(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_progress

        with patch("gpd.mcp.servers.state_server.progress_render", side_effect=OSError("read only")):
            result = get_progress(fake_project_dir)
        assert result == {"error": "read only", "schema_version": 1}

    def test_run_health_check_gpd_error(self, fake_project_dir):
        from gpd.core.errors import GPDError
        from gpd.mcp.servers.state_server import run_health_check

        with patch("gpd.mcp.servers.state_server.run_health", side_effect=GPDError("health broke")):
            result = run_health_check(fake_project_dir)
        assert result == {"error": "health broke", "schema_version": 1}

    def test_run_health_check_os_error(self, fake_project_dir):
        from gpd.mcp.servers.state_server import run_health_check

        with patch("gpd.mcp.servers.state_server.run_health", side_effect=OSError("no access")):
            result = run_health_check(fake_project_dir)
        assert result == {"error": "no access", "schema_version": 1}

    def test_get_config_gpd_error(self, fake_project_dir):
        from gpd.core.errors import GPDError
        from gpd.mcp.servers.state_server import get_config

        with patch("gpd.mcp.servers.state_server.load_config", side_effect=GPDError("config missing")):
            result = get_config(fake_project_dir)
        assert result == {"error": "config missing", "schema_version": 1}

    def test_get_config_os_error(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_config

        with patch("gpd.mcp.servers.state_server.load_config", side_effect=OSError("not found")):
            result = get_config(fake_project_dir)
        assert result == {"error": "not found", "schema_version": 1}

    def test_get_config_value_error(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_config

        with patch("gpd.mcp.servers.state_server.load_config", side_effect=ValueError("invalid toml")):
            result = get_config(fake_project_dir)
        assert result == {"error": "invalid toml", "schema_version": 1}

    def test_get_phase_info_found(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_phase_info

        mock_info = MagicMock()
        mock_info.phase_number = "01"
        mock_info.phase_name = "Setup"
        mock_info.directory = "GPD/phases/01-setup"
        mock_info.phase_slug = "01-setup"
        mock_info.plans = ["plan-01.md", "plan-02.md", "plan-03.md"]
        mock_info.summaries = ["summary-01.md", "summary-02.md"]
        mock_info.incomplete_plans = ["plan-03.md"]

        with patch("gpd.core.phases.find_phase", return_value=mock_info):
            result = get_phase_info(fake_project_dir, "01")
        assert result["phase_number"] == "01"
        assert result["plan_count"] == 3
        assert result["summary_count"] == 2
        assert result["complete"] is False

    def test_get_phase_info_not_found(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_phase_info

        with patch("gpd.core.phases.find_phase", return_value=None):
            result = get_phase_info(fake_project_dir, "99")
        assert "error" in result

    def test_advance_plan(self, fake_project_dir):
        from gpd.mcp.servers.state_server import advance_plan

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"advanced": True, "new_plan": 2}

        with patch("gpd.mcp.servers.state_server.state_advance_plan", return_value=mock_result):
            result = advance_plan(fake_project_dir)
        assert result["advanced"] is True

    def test_get_progress(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_progress

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"milestone_version": "v1.0", "milestone_name": "Test", "percent": 50}

        with patch("gpd.mcp.servers.state_server.progress_render", return_value=mock_result):
            result = get_progress(fake_project_dir)
        assert result["percent"] == 50

    def test_validate_state(self, fake_project_dir):
        from gpd.mcp.servers.state_server import validate_state

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"valid": True, "issues": [], "warnings": []}

        with patch("gpd.mcp.servers.state_server.state_validate", return_value=mock_result):
            result = validate_state(fake_project_dir)
        assert result["valid"] is True

    def test_run_health_check(self, fake_project_dir):
        from gpd.mcp.servers.state_server import run_health_check

        mock_report = MagicMock()
        mock_report.model_dump.return_value = {
            "passed": 10,
            "failed": 1,
            "checks": [],
        }

        with patch("gpd.mcp.servers.state_server.run_health", return_value=mock_report):
            result = run_health_check(fake_project_dir)
        assert result["passed"] == 10

    def test_run_health_check_with_fix(self, fake_project_dir):
        from gpd.mcp.servers.state_server import run_health_check

        mock_report = MagicMock()
        mock_report.model_dump.return_value = {"passed": 11, "failed": 0, "fixes_applied": 1}

        with patch("gpd.mcp.servers.state_server.run_health", return_value=mock_report) as mock_fn:
            result = run_health_check(fake_project_dir, fix=True)
        mock_fn.assert_called_once_with(ANY, fix=True)
        assert result["fixes_applied"] == 1

    def test_get_config(self, fake_project_dir):
        from gpd.mcp.servers.state_server import get_config

        mock_config = MagicMock()
        mock_config.model_dump.return_value = {"model_profile": "deep-theory", "autonomy": "balanced"}

        with patch("gpd.mcp.servers.state_server.load_config", return_value=mock_config):
            result = get_config(fake_project_dir)
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

    def test_dimensional_check_invalid_element_returns_error_envelope(self):
        from gpd.mcp.servers.verification_server import dimensional_check

        result = dimensional_check(["[M] = [M]", 3])

        assert result["schema_version"] == 1
        assert result["error"] == "expressions[1] must be a string"

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

    def test_limiting_case_check_invalid_limit_key_returns_error_envelope(self):
        from gpd.mcp.servers.verification_server import limiting_case_check

        result = limiting_case_check("E = m * c^2", {1: "classical"})

        assert result["schema_version"] == 1
        assert result["error"] == "limits keys must be strings"

    def test_limiting_case_check_invalid_limit_value_returns_error_envelope(self):
        from gpd.mcp.servers.verification_server import limiting_case_check

        result = limiting_case_check("E = m * c^2", {"classical limit": 0})

        assert result["schema_version"] == 1
        assert result["error"] == "limits[classical limit] must be a string"

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

    def test_symmetry_check_invalid_element_returns_error_envelope(self):
        from gpd.mcp.servers.verification_server import symmetry_check

        result = symmetry_check("expression", ["parity", 7])

        assert result["schema_version"] == 1
        assert result["error"] == "symmetries[1] must be a string"

    def test_dimensional_check_rejects_whitespace_only_expression(self):
        from gpd.mcp.servers.verification_server import dimensional_check

        result = dimensional_check(["  "])

        assert result["schema_version"] == 1
        assert result["error"] == "expressions[0] must be a non-empty string"

    def test_limiting_case_check_rejects_whitespace_only_expression(self):
        from gpd.mcp.servers.verification_server import limiting_case_check

        result = limiting_case_check("   ", {"hbar -> 0": "classical limit"})

        assert result["schema_version"] == 1
        assert result["error"] == "expression must be a non-empty string"

    def test_symmetry_check_rejects_whitespace_only_symmetry(self):
        from gpd.mcp.servers.verification_server import symmetry_check

        result = symmetry_check("expression", ["  "])

        assert result["schema_version"] == 1
        assert result["error"] == "symmetries[0] must be a non-empty string"

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

    def test_run_check_contract_limit_recovery(self):
        from gpd.mcp.servers.verification_server import run_check

        result = run_check("contract.limit_recovery", "qft", "This derivation includes the asymptotic scaling limit.")
        assert result["check_id"] == "5.15"
        assert result["check_key"] == "contract.limit_recovery"
        assert result["contract_aware"] is True
        assert result["required_request_fields"] == ["metadata.regime_label", "metadata.expected_behavior"]
        assert result["request_template"]["metadata"]["regime_label"] is None
        assert result["request_template"]["metadata"]["expected_behavior"] is None

    def test_run_check_contract_benchmark_reproduction_flags_missing_anchor(self):
        from gpd.mcp.servers.verification_server import run_check

        result = run_check("5.16", "qft", "Computed a result but did not compare it to anything.")
        assert any("benchmark" in issue.lower() or "baseline" in issue.lower() for issue in result["automated_issues"])

    def test_run_check_non_contract_check_omits_request_hints(self):
        from gpd.mcp.servers.verification_server import run_check

        result = run_check("5.1", "qft", "quantum field theory with \\hbar")

        assert "required_request_fields" not in result
        assert "request_template" not in result

    def test_get_verification_coverage_rejects_whitespace_only_active_check(self):
        from gpd.mcp.servers.verification_server import get_verification_coverage

        result = get_verification_coverage([1], ["  "])

        assert result["schema_version"] == 1
        assert result["error"] == "active_checks[0] must be a non-empty string"

    def test_run_contract_check_benchmark_reproduction(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "binding": {"claim_ids": ["claim-benchmark"], "reference_ids": ["ref-benchmark"]},
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result["status"] == "pass"
        assert result["check_id"] == "5.16"
        assert result["binding"]["claim_ids"] == ["claim-benchmark"]

    def test_run_contract_check_proof_parameter_coverage_flags_missing_theorem_parameter(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.proof_parameter_coverage",
                "contract": _proof_contract_fixture(),
                "observed": {"covered_parameter_symbols": ["n"]},
            }
        )

        assert result["status"] == "fail"
        assert result["check_id"] == "5.21"
        assert result["metrics"]["missing_parameter_symbols"] == ["r_0"]

    def test_run_contract_check_claim_to_proof_alignment_accepts_claim_statement_path(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.claim_to_proof_alignment",
                "contract": _proof_contract_fixture(),
                "observed": {"scope_status": "matched"},
            }
        )

        assert result["status"] == "pass"
        assert result["missing_inputs"] == []

    def test_run_contract_check_claim_to_proof_alignment_requires_clause_audit_when_clause_ids_are_explicit(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.claim_to_proof_alignment",
                "contract": _proof_contract_fixture(),
                "metadata": {"conclusion_clause_ids": ["conclusion-main"]},
                "observed": {"scope_status": "matched"},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "observed.uncovered_conclusion_clause_ids" in result["missing_inputs"]

    def test_run_contract_check_requires_identifier(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check({})

        assert result == {"error": "Missing check_key", "schema_version": 1}

    def test_run_contract_check_rejects_legacy_check_id_alias(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check({"check_id": "contract.limit_recovery "})

        assert result == {
            "error": (
                "request contains unsupported keys: check_id; supported keys are "
                "check_key, contract, binding, metadata, observed, artifact_content"
            ),
            "schema_version": 1,
        }

    def test_run_contract_check_preserves_plural_binding_lists(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.limit_recovery",
                "binding": {"claim_ids": ["claim-main"], "reference_ids": ["ref-main"]},
                "metadata": {"regime_label": "large-k", "expected_behavior": "approaches the asymptotic limit"},
                "observed": {"limit_passed": True, "observed_limit": "large-k"},
            }
        )

        assert result["status"] == "pass"
        assert result["contract_impacts"] == ["claim-main", "ref-main"]

    def test_run_contract_check_rejects_unsupported_binding_keys(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "contract": _load_project_contract_fixture(),
                "binding": {"cliam_ids": ["claim-benchmark"]},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result == {
            "error": (
                "binding contains unsupported keys: cliam_ids; supported keys are "
                "binding.claim_ids, binding.deliverable_ids, binding.acceptance_test_ids, binding.reference_ids"
            ),
            "schema_version": 1,
        }

    def test_run_contract_check_treats_empty_binding_like_omitted_binding(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        omitted = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "contract": _load_project_contract_fixture(),
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )
        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "contract": _load_project_contract_fixture(),
                "binding": {},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result == omitted
        assert result["status"] == "pass"

    def test_run_contract_check_requires_limit_metadata_for_decisive_pass(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.limit_recovery",
                "contract": _load_project_contract_fixture(),
                "binding": {"claim_ids": ["claim-benchmark"]},
                "observed": {"limit_passed": True, "observed_limit": "large-k"},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "metadata.regime_label" in result["missing_inputs"]
        assert "metadata.expected_behavior" in result["missing_inputs"]

    def test_run_contract_check_requires_benchmark_anchor_when_contract_context_is_ambiguous(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "contract": _multi_claim_contract_fixture(),
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "metadata.source_reference_id" in result["missing_inputs"]

    def test_run_contract_check_unknown_binding_ids_block_decisive_verdict(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "contract": _load_project_contract_fixture(),
                "binding": {"claim_ids": ["claim-missing"], "reference_ids": ["ref-missing"]},
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result == {
            "error": "binding.claim_ids references unknown contract claim claim-missing",
            "schema_version": 1,
        }

    def test_run_contract_check_rejects_non_target_binding_keys(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.direct_proxy_consistency",
                "contract": _load_project_contract_fixture(),
                "binding": {
                    "claim_ids": ["claim-benchmark"],
                    "forbidden_proxy_ids": ["fp-01"],
                    "reference_ids": ["ref-benchmark"],
                },
                "observed": {"proxy_only": True, "proxy_available": True, "direct_available": False},
            }
        )

        assert result == {
            "error": (
                "binding contains unsupported keys: reference_ids; supported keys are "
                "binding.claim_ids, binding.deliverable_ids, binding.acceptance_test_ids, "
                "binding.forbidden_proxy_ids"
            ),
            "schema_version": 1,
        }

    def test_run_contract_check_benchmark_default_follows_bound_claim_context(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "contract": _multi_claim_contract_fixture(),
                "binding": {"claim_ids": ["claim-b"]},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result["status"] == "pass"
        assert result["contract_impacts"] == ["claim-b"]
        assert result["metrics"]["source_reference_id"] == "ref-b"
        assert result["metrics"]["metric_value"] == 0.01

    def test_run_contract_check_rejects_benchmark_anchor_that_conflicts_with_bound_claim_context(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "contract": _multi_claim_contract_fixture(),
                "binding": {"claim_ids": ["claim-b"]},
                "metadata": {"source_reference_id": "ref-a"},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "metadata.source_reference_id" in result["missing_inputs"]
        assert any("bound contract context" in issue for issue in result["automated_issues"])

    def test_run_contract_check_rejects_conflicting_benchmark_binding_contexts(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "contract": _multi_claim_contract_fixture(),
                "binding": {
                    "claim_ids": ["claim-b"],
                    "acceptance_test_ids": ["test-b"],
                    "reference_ids": ["ref-a"],
                },
                "metadata": {"source_reference_id": "ref-a"},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "metadata.source_reference_id" in result["missing_inputs"]
        assert any("binding contexts disagree on benchmark reference candidates" in issue for issue in result["automated_issues"])

    def test_run_contract_check_rejects_explicit_benchmark_anchor_against_single_contract_default_without_binding(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        contract = copy.deepcopy(_load_project_contract_fixture())
        contract["references"].append(
            {
                "id": "ref-background",
                "kind": "paper",
                "locator": "Background note",
                "role": "background",
                "why_it_matters": "Useful context but not the benchmark anchor",
                "applies_to": ["claim-benchmark"],
                "required_actions": ["read"],
            }
        )

        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "contract": contract,
                "metadata": {"source_reference_id": "ref-background"},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "metadata.source_reference_id" in result["missing_inputs"]
        assert any("resolved contract context" in issue for issue in result["automated_issues"])

    def test_run_contract_check_limit_default_follows_bound_claim_context(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.limit_recovery",
                "contract": _multi_claim_contract_fixture(),
                "binding": {"claim_ids": ["claim-b"]},
                "metadata": {"expected_behavior": "approaches the contracted large-k family"},
                "observed": {"limit_passed": True, "observed_limit": "large-k"},
            }
        )

        assert result["status"] == "pass"
        assert result["metrics"]["regime_label"] == "large-k"

    def test_run_contract_check_rejects_regime_label_that_conflicts_with_bound_claim_context(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.limit_recovery",
                "contract": _multi_claim_contract_fixture(),
                "binding": {"claim_ids": ["claim-b"]},
                "metadata": {
                    "regime_label": "small-k",
                    "expected_behavior": "approaches the contracted large-k family",
                },
                "observed": {"limit_passed": True, "observed_limit": "large-k"},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "metadata.regime_label" in result["missing_inputs"]
        assert any("bound contract context" in issue for issue in result["automated_issues"])

    def test_run_contract_check_rejects_conflicting_limit_binding_contexts(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.limit_recovery",
                "contract": _multi_claim_contract_fixture(),
                "binding": {
                    "claim_ids": ["claim-b"],
                    "acceptance_test_ids": ["test-b"],
                    "reference_ids": ["ref-a"],
                },
                "metadata": {
                    "regime_label": "large-k",
                    "expected_behavior": "approaches the contracted large-k family",
                },
                "observed": {"limit_passed": True, "observed_limit": "large-k"},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "metadata.regime_label" in result["missing_inputs"]
        assert any("binding contexts disagree on limit regime candidates" in issue for issue in result["automated_issues"])

    def test_run_contract_check_rejects_explicit_regime_label_against_single_contract_default_without_binding(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        contract = copy.deepcopy(_load_project_contract_fixture())
        contract["observables"][0]["regime"] = "large-k"

        result = run_contract_check(
            {
                "check_key": "contract.limit_recovery",
                "contract": contract,
                "metadata": {
                    "regime_label": "small-k",
                    "expected_behavior": "approaches the contracted large-k family",
                },
                "observed": {"limit_passed": True, "observed_limit": "large-k"},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "metadata.regime_label" in result["missing_inputs"]
        assert any("resolved contract context" in issue for issue in result["automated_issues"])

    def test_run_contract_check_fit_family_pass_requires_declared_family(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.fit_family_mismatch",
                "contract": _load_project_contract_fixture(),
                "observed": {"selected_family": "benchmark-ansatz", "competing_family_checked": True},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "metadata.declared_family" in result["missing_inputs"]

    def test_run_contract_check_estimator_family_reports_missing_diagnostics(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.estimator_family_mismatch",
                "contract": _load_project_contract_fixture(),
                "metadata": {"declared_family": "bootstrap"},
                "observed": {"selected_family": "bootstrap"},
            }
        )

        assert result["status"] == "insufficient_evidence"
        assert "observed.bias_checked" in result["missing_inputs"]
        assert "observed.calibration_checked" in result["missing_inputs"]

    def test_run_contract_check_rejects_whitespace_only_benchmark_anchor(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "metadata": {"source_reference_id": "   "},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result == {"error": "metadata.source_reference_id must be a non-empty string", "schema_version": 1}

    def test_run_contract_check_rejects_whitespace_only_limit_metadata(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.limit_recovery",
                "metadata": {"regime_label": "   ", "expected_behavior": "   "},
                "observed": {"limit_passed": True, "observed_limit": "large-k"},
            }
        )

        assert result == {"error": "metadata.regime_label must be a non-empty string", "schema_version": 1}

    def test_run_contract_check_rejects_whitespace_only_declared_fit_family(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"declared_family": "   "},
                "observed": {"selected_family": "power_law", "competing_family_checked": True},
            }
        )

        assert result == {"error": "metadata.declared_family must be a non-empty string", "schema_version": 1}

    def test_run_contract_check_direct_proxy_consistency_fails_on_proxy_only(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(
            {
                "check_key": "contract.direct_proxy_consistency",
                "binding": {"claim_ids": ["claim-benchmark"], "forbidden_proxy_ids": ["fp-benchmark"]},
                "observed": {"proxy_only": True, "proxy_available": True, "direct_available": False},
            }
        )

        assert result["status"] == "fail"
        assert any("proxy" in issue.lower() for issue in result["automated_issues"])

    @pytest.mark.parametrize(
        ("field_name", "payload", "expected_error"),
        [
            ("contract", "not-a-dict", "contract must be an object"),
            ("binding", ["claim-b"], "binding must be an object"),
            ("metadata", "not-a-dict", "metadata must be an object"),
            ("observed", ["metric"], "observed must be an object"),
        ],
    )
    def test_run_contract_check_rejects_non_mapping_payload_sections(self, field_name, payload, expected_error):
        from gpd.mcp.servers.verification_server import run_contract_check

        request = {"check_key": "contract.benchmark_reproduction", field_name: payload}

        result = run_contract_check(request)

        assert result == {"error": expected_error, "schema_version": 1}

    @pytest.mark.parametrize(
        ("request_payload", "expected_error"),
        [
            (
                {
                    "check_key": "contract.benchmark_reproduction",
                    "binding": {"claim_ids": ["claim-benchmark", 9]},
                    "observed": {"metric_value": 0.01, "threshold_value": 0.02},
                },
                "binding.claim_ids[1] must be a non-empty string",
            ),
            (
                {
                    "check_key": "contract.limit_recovery",
                    "binding": {"reference_ids": ["ref-benchmark", "   "]},
                    "metadata": {
                        "regime_label": "large-k",
                        "expected_behavior": "approaches the asymptotic limit",
                    },
                    "observed": {"limit_passed": True, "observed_limit": "large-k"},
                },
                "binding.reference_ids[1] must be a non-empty string",
            ),
            (
                {
                    "check_key": "contract.fit_family_mismatch",
                    "metadata": {"allowed_families": ["power_law", None]},
                    "observed": {"selected_family": "power_law", "competing_family_checked": True},
                },
                "metadata.allowed_families[1] must be a non-empty string",
            ),
            (
                {
                    "check_key": "contract.estimator_family_mismatch",
                    "metadata": {"forbidden_families": ["", "jackknife"]},
                    "observed": {
                        "selected_family": "bootstrap",
                        "bias_checked": True,
                        "calibration_checked": True,
                    },
                },
                "metadata.forbidden_families[0] must be a non-empty string",
            ),
        ],
    )
    def test_run_contract_check_rejects_malformed_binding_and_metadata_list_members(
        self, request_payload, expected_error
    ):
        from gpd.mcp.servers.verification_server import run_contract_check

        result = run_contract_check(request_payload)

        assert result == {"error": expected_error, "schema_version": 1}

    def test_run_contract_check_rejects_unknown_nested_contract_fields(self):
        from gpd.mcp.servers.verification_server import run_contract_check

        contract = copy.deepcopy(_load_project_contract_fixture())
        contract["claims"][0]["notes"] = "legacy extra field"

        result = run_contract_check(
            {
                "check_key": "contract.benchmark_reproduction",
                "contract": contract,
                "binding": {"claim_ids": ["claim-benchmark"], "reference_ids": ["ref-benchmark"]},
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            }
        )

        assert result == {
            "error": "Invalid contract payload: claims.0.notes: Extra inputs are not permitted",
            "schema_version": 1,
        }

    def test_suggest_contract_checks_from_contract(self):
        import json
        from pathlib import Path

        from gpd.mcp.servers.verification_server import suggest_contract_checks

        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "stage0" / "project_contract.json"
        contract = json.loads(fixture.read_text(encoding="utf-8"))

        result = suggest_contract_checks(contract)
        suggested = {entry["check_key"] for entry in result["suggested_checks"]}

        assert "contract.benchmark_reproduction" in suggested
        assert "contract.direct_proxy_consistency" in suggested
        benchmark = next(entry for entry in result["suggested_checks"] if entry["check_key"] == "contract.benchmark_reproduction")
        assert benchmark["check"] == benchmark["check_key"]
        assert benchmark["binding_targets"] == ["claim", "deliverable", "acceptance_test", "reference"]
        assert benchmark["required_request_fields"] == [
            "observed.metric_value",
            "observed.threshold_value",
        ]
        assert benchmark["request_template"]["metadata"]["source_reference_id"] == "ref-benchmark"
        assert benchmark["request_template"]["observed"]["metric_value"] is None
        assert benchmark["request_template"]["observed"]["threshold_value"] is None
        assert "artifact_content" not in benchmark["request_template"]

    def test_suggest_contract_checks_from_proof_contract(self):
        from gpd.mcp.servers.verification_server import suggest_contract_checks

        result = suggest_contract_checks(_proof_contract_fixture())
        suggested = {entry["check_key"] for entry in result["suggested_checks"]}

        assert "contract.proof_parameter_coverage" in suggested
        assert "contract.claim_to_proof_alignment" in suggested
        assert "contract.counterexample_search" in suggested
        parameter = next(entry for entry in result["suggested_checks"] if entry["check_key"] == "contract.proof_parameter_coverage")
        assert parameter["check"] == parameter["check_key"]
        assert parameter["binding_targets"] == ["observable", "claim", "deliverable", "acceptance_test"]
        assert parameter["request_template"]["binding"]["claim_ids"] == ["claim-theorem"]
        assert parameter["request_template"]["metadata"]["theorem_parameter_symbols"] == ["r_0", "n"]
        assert parameter["request_template"]["observed"]["covered_parameter_symbols"] is None

    def test_suggest_contract_checks_returns_deep_copied_request_templates(self):
        import json
        from pathlib import Path

        from gpd.mcp.servers.verification_server import suggest_contract_checks

        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "stage0" / "project_contract.json"
        contract = json.loads(fixture.read_text(encoding="utf-8"))

        first = suggest_contract_checks(contract)
        benchmark = next(entry for entry in first["suggested_checks"] if entry["check_key"] == "contract.benchmark_reproduction")
        benchmark["request_template"]["metadata"]["source_reference_id"] = "poisoned"

        second = suggest_contract_checks(contract)
        fresh = next(entry for entry in second["suggested_checks"] if entry["check_key"] == "contract.benchmark_reproduction")

        assert fresh["request_template"]["metadata"]["source_reference_id"] == "ref-benchmark"

    def test_suggest_contract_checks_rejects_unknown_nested_contract_fields(self):
        from gpd.mcp.servers.verification_server import suggest_contract_checks

        contract = copy.deepcopy(_load_project_contract_fixture())
        contract["references"][0]["notes"] = "legacy extra field"

        result = suggest_contract_checks(contract)

        assert result == {
            "error": "Invalid contract payload: references.0.notes: Extra inputs are not permitted",
            "schema_version": 1,
        }

    @pytest.mark.parametrize("payload", ["not-a-dict", ["claim-benchmark"], 3])
    def test_suggest_contract_checks_rejects_non_mapping_payloads(self, payload):
        from gpd.mcp.servers.verification_server import suggest_contract_checks

        result = suggest_contract_checks(payload)

        assert result == {"error": "contract must be an object", "schema_version": 1}

    # --- get_checklist ---

    def test_get_checklist_qft(self):
        from gpd.mcp.servers.verification_server import get_checklist

        result = get_checklist("qft")
        assert result["found"] is True
        assert result["schema_version"] == 1
        assert result["domain_check_count"] > 0
        assert result["universal_check_count"] == 24
        assert result["universal_checks"][0]["check_id"] == "5.1"
        assert "evidence_kind" in result["universal_checks"][0]
        contract_check = next(entry for entry in result["universal_checks"] if entry["check_key"] == "contract.limit_recovery")
        assert contract_check["required_request_fields"] == ["metadata.regime_label", "metadata.expected_behavior"]
        assert contract_check["request_template"]["metadata"]["regime_label"] is None
        assert contract_check["request_template"]["metadata"]["expected_behavior"] is None
        proof_check = next(
            entry for entry in result["universal_checks"] if entry["check_key"] == "contract.proof_parameter_coverage"
        )
        assert proof_check["request_template"]["metadata"]["theorem_parameter_symbols"] is None

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

    def test_get_bundle_checklist_returns_additive_extensions(self):
        from gpd.mcp.servers.verification_server import get_bundle_checklist

        result = get_bundle_checklist(["stat-mech-simulation"])

        assert result["found"] is True
        assert result["bundle_count"] == 1
        assert result["bundles"][0]["bundle_id"] == "stat-mech-simulation"
        assert result["bundles"][0]["asset_paths"]
        assert "## Selected Protocol Bundles" in result["protocol_bundle_context"]
        assert "Statistical Mechanics Simulation" in result["protocol_bundle_context"]
        assert result["bundle_check_count"] == 2
        assert result["bundle_checks"][0]["check_ids"] == ["5.4", "5.14", "5.16"]

    def test_get_bundle_checklist_supports_multiple_curated_bundles(self):
        from gpd.mcp.servers.verification_server import get_bundle_checklist

        result = get_bundle_checklist(["stat-mech-simulation", "numerical-relativity"])

        assert result["found"] is True
        assert result["bundle_count"] == 2
        assert {bundle["bundle_id"] for bundle in result["bundles"]} == {
            "stat-mech-simulation",
            "numerical-relativity",
        }
        assert result["bundle_check_count"] == 4
        assert result["missing_bundle_ids"] == []

    def test_get_bundle_checklist_reports_missing_ids(self):
        from gpd.mcp.servers.verification_server import get_bundle_checklist

        result = get_bundle_checklist(["missing-bundle"])

        assert result["found"] is False
        assert result["bundle_count"] == 0
        assert result["missing_bundle_ids"] == ["missing-bundle"]

    def test_get_bundle_checklist_preserves_partial_success_when_some_bundles_exist(self):
        from gpd.mcp.servers.verification_server import get_bundle_checklist

        result = get_bundle_checklist(["stat-mech-simulation", "missing-bundle"])

        assert result["found"] is True
        assert result["bundle_count"] == 1
        assert result["bundles"][0]["bundle_id"] == "stat-mech-simulation"
        assert result["missing_bundle_ids"] == ["missing-bundle"]

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

    def test_verification_coverage_invalid_error_class_id_returns_error_envelope(self):
        from gpd.mcp.servers.verification_server import get_verification_coverage

        result = get_verification_coverage(
            error_class_ids=[15, {"id": 37}],
            active_checks=["5.1"],
        )

        assert result["schema_version"] == 1
        assert result["error"] == "error_class_ids[1] must be an integer"

    def test_verification_coverage_invalid_active_check_returns_error_envelope(self):
        from gpd.mcp.servers.verification_server import get_verification_coverage

        result = get_verification_coverage(
            error_class_ids=[15],
            active_checks=["5.1", 5.3],
        )

        assert result["schema_version"] == 1
        assert result["error"] == "active_checks[1] must be a string"

    def test_verification_coverage_normalizes_whitespace_padded_active_checks(self):
        from gpd.mcp.servers.verification_server import get_verification_coverage

        result = get_verification_coverage(
            error_class_ids=[15],
            active_checks=[" 5.1 "],
        )

        assert result["schema_version"] == 1
        assert result["active_checks"] == ["5.1"]
        assert result["covered"] == 1
        assert result["coverage_percent"] == 100.0
        assert result["recommendation"] == "Full coverage"


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

    def test_protocol_domain_manifest_covers_all_protocol_files(self):
        from gpd.mcp.servers.protocols_server import PROTOCOLS_DIR, _load_protocol_domain_manifest

        _load_protocol_domain_manifest.cache_clear()
        domains = _load_protocol_domain_manifest()
        protocol_names = {path.stem for path in PROTOCOLS_DIR.glob("*.md")}

        assert set(domains) == protocol_names
        assert domains["perturbation-theory"] == "core_derivation"
        assert domains["general-relativity"] == "gr_cosmology"
        assert domains["reproducibility"] == "general"

    def test_protocol_store_rejects_missing_domain_metadata(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from gpd.mcp.servers.protocols_server import ProtocolStore

        protocols_dir = tmp_path / "protocols"
        protocols_dir.mkdir()
        (protocols_dir / "demo.md").write_text("---\n---\n# Demo\nBody\n", encoding="utf-8")
        (protocols_dir / "protocol-domains.json").write_text(
            json.dumps({"schema_version": 1, "protocol_domains": {}}),
            encoding="utf-8",
        )

        monkeypatch.setattr("gpd.mcp.servers.protocols_server.PROTOCOLS_DIR", protocols_dir)
        monkeypatch.setattr(
            "gpd.mcp.servers.protocols_server.PROTOCOL_DOMAINS_MANIFEST",
            protocols_dir / "protocol-domains.json",
        )
        monkeypatch.setattr(
            "gpd.mcp.servers.protocols_server._load_protocol_domain_manifest",
            lambda: {},
        )

        with pytest.raises(ValueError, match="missing domain metadata"):
            ProtocolStore(protocols_dir)


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
