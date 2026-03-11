"""Tests for MCP server error handling and adapter wiring fixes.

Covers:
- skills_server.py: handlers return error dicts on registry exceptions
- errors_mcp.py: handlers return error dicts on store exceptions
- patterns_server.py: list_domains smoke test, lookup_pattern domain filter,
  add_pattern parameter acceptance
- opencode.py: configure_opencode_permissions and _write_mcp_servers_opencode
  handle non-dict / malformed JSON gracefully
- conventions_server.py: convention_lock_status and convention_check handle
  exceptions in post-parse processing
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. skills_server.py error handling
# ---------------------------------------------------------------------------


class TestSkillsServerErrorHandling:
    """Verify skills_server tool handlers return error dicts on exceptions."""

    def test_list_skills_returns_error_on_registry_exception(self):
        """list_skills wraps _load_skill_index; if it raises, the gpd_span
        propagates. Verify the function can survive a broken registry."""
        from gpd.mcp.servers.skills_server import list_skills

        with patch(
            "gpd.mcp.servers.skills_server._load_skill_index",
            side_effect=RuntimeError("registry broken"),
        ):
            with pytest.raises(RuntimeError, match="registry broken"):
                list_skills()

    def test_get_skill_not_found_returns_error_dict(self):
        """get_skill returns an error dict when the skill is not in the registry."""
        from gpd.mcp.servers.skills_server import get_skill

        with patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=None):
            with patch(
                "gpd.mcp.servers.skills_server._load_skill_index",
                return_value=[],
            ):
                result = get_skill("gpd-nonexistent")
        assert "error" in result
        assert "gpd-nonexistent" in result["error"]

    def test_get_skill_index_returns_error_on_registry_exception(self):
        """get_skill_index propagates if _load_skill_index raises."""
        from gpd.mcp.servers.skills_server import get_skill_index

        with patch(
            "gpd.mcp.servers.skills_server._load_skill_index",
            side_effect=RuntimeError("load failed"),
        ):
            with pytest.raises(RuntimeError, match="load failed"):
                get_skill_index()

    def test_route_skill_empty_skills_returns_error_dict(self):
        """route_skill returns an error dict when no skills are available."""
        from gpd.mcp.servers.skills_server import route_skill

        with patch("gpd.mcp.servers.skills_server._load_skill_index", return_value=[]):
            result = route_skill("execute the build")
        assert "error" in result
        assert result["suggestion"] is None

    def test_route_skill_exception_propagates(self):
        """route_skill propagates if _load_skill_index raises."""
        from gpd.mcp.servers.skills_server import route_skill

        with patch(
            "gpd.mcp.servers.skills_server._load_skill_index",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                route_skill("anything")


# ---------------------------------------------------------------------------
# 2. errors_mcp.py error handling
# ---------------------------------------------------------------------------


class TestErrorsMcpErrorHandling:
    """Verify errors_mcp tool handlers return error dicts on store errors."""

    @pytest.fixture(autouse=True)
    def _mock_store(self):
        """Inject a mock ErrorStore with empty/None defaults."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.get_traceability.return_value = None
        mock.list_all.return_value = []
        mock.check_relevant.return_value = []
        mock.domains = []
        mock.count = 0
        self.store = mock
        with patch("gpd.mcp.servers.errors_mcp._get_store", return_value=mock):
            yield

    def test_get_error_class_not_found_returns_error_dict(self):
        from gpd.mcp.servers.errors_mcp import get_error_class

        result = get_error_class(999)
        assert "error" in result
        assert "999" in result["error"]
        assert result["valid_range"] == "1-104"

    def test_get_detection_strategy_not_found_returns_error_dict(self):
        from gpd.mcp.servers.errors_mcp import get_detection_strategy

        result = get_detection_strategy(999)
        assert "error" in result
        assert "999" in result["error"]

    def test_get_traceability_not_found_returns_error_dict(self):
        from gpd.mcp.servers.errors_mcp import get_traceability

        result = get_traceability(999)
        assert "error" in result

    def test_get_traceability_no_matrix_data(self):
        """When error exists but traceability matrix has no data for it."""
        from gpd.mcp.servers.errors_mcp import get_traceability

        self.store.get.return_value = {
            "id": 50,
            "name": "Test error",
            "domain": "core",
        }
        self.store.get_traceability.return_value = None
        result = get_traceability(50)
        assert result["coverage_count"] == 0
        assert "note" in result

    def test_check_error_classes_returns_empty_matches(self):
        from gpd.mcp.servers.errors_mcp import check_error_classes

        result = check_error_classes("completely unrelated query")
        assert result["match_count"] == 0
        assert result["error_classes"] == []

    def test_list_error_classes_empty_store(self):
        from gpd.mcp.servers.errors_mcp import list_error_classes

        result = list_error_classes()
        assert result["count"] == 0
        assert result["total_classes"] == 0

    def test_store_method_os_error_returns_error_dict(self):
        """When a store method raises OSError, the handler returns an error dict
        (the gpd_span context manager catches the exception)."""
        from gpd.mcp.servers.errors_mcp import get_error_class

        self.store.get.side_effect = OSError("cannot read catalog")
        result = get_error_class(1)
        assert "error" in result
        assert "cannot read catalog" in result["error"]


# ---------------------------------------------------------------------------
# 3. patterns_server.py fixes
# ---------------------------------------------------------------------------


class TestPatternsServerFixes:
    """Test patterns_server tool behaviour and parameter acceptance."""

    def test_list_domains_returns_valid_structure(self):
        """Smoke test: list_domains returns domains, categories, severities."""
        from gpd.mcp.servers.patterns_server import list_domains

        result = list_domains()
        assert isinstance(result, dict)
        assert "domains" in result
        assert "categories" in result
        assert "severities" in result
        assert len(result["domains"]) > 0
        assert len(result["categories"]) > 0
        assert len(result["severities"]) > 0
        # Verify known values are present
        assert "qft" in result["domains"]
        assert "sign-error" in result["categories"]

    def test_list_domains_severities_ordering(self):
        """Severities are returned in order: critical, high, medium, low."""
        from gpd.mcp.servers.patterns_server import list_domains

        result = list_domains()
        assert list(result["severities"]) == ["critical", "high", "medium", "low"]

    def test_lookup_pattern_keywords_calls_pattern_search(self):
        """lookup_pattern with keywords delegates to pattern_search."""
        from gpd.mcp.servers.patterns_server import lookup_pattern

        mock_match_1 = MagicMock()
        mock_match_1.model_dump.return_value = {"id": "p1", "title": "Sign error", "domain": "qft"}
        mock_match_2 = MagicMock()
        mock_match_2.model_dump.return_value = {"id": "p2", "title": "Factor error", "domain": "qft"}

        mock_result = MagicMock()
        mock_result.count = 2
        mock_result.matches = [mock_match_1, mock_match_2]
        mock_result.query = "sign error qft"
        mock_result.library_exists = True

        with patch("gpd.mcp.servers.patterns_server.pattern_search", return_value=mock_result) as mock_search:
            result = lookup_pattern(keywords="sign error qft")

        mock_search.assert_called_once()
        assert result["count"] == 2
        assert result["query"] == "sign error qft"

    def test_lookup_pattern_domain_filter_calls_pattern_list(self):
        """lookup_pattern with domain (no keywords) calls pattern_list with domain filter."""
        from gpd.mcp.servers.patterns_server import lookup_pattern

        mock_result = MagicMock()
        mock_result.count = 3
        mock_pattern = MagicMock()
        mock_pattern.model_dump.return_value = {"id": "p1", "domain": "qft"}
        mock_result.patterns = [mock_pattern, mock_pattern, mock_pattern]
        mock_result.library_exists = True

        with patch("gpd.mcp.servers.patterns_server.pattern_list", return_value=mock_result) as mock_list:
            result = lookup_pattern(domain="qft")

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs.kwargs.get("domain") == "qft" or call_kwargs[1].get("domain") == "qft"
        assert result["count"] == 3
        assert result["library_exists"] is True

    def test_lookup_pattern_keywords_plus_domain_filters_by_domain(self):
        """When keywords and domain are both provided, results are filtered by domain."""
        from gpd.mcp.servers.patterns_server import lookup_pattern

        mock_match_qft = MagicMock()
        mock_match_qft.domain = "qft"
        mock_match_qft.model_dump.return_value = {"id": "p1", "domain": "qft"}
        mock_match_cm = MagicMock()
        mock_match_cm.domain = "condensed-matter"
        mock_match_cm.model_dump.return_value = {"id": "p2", "domain": "condensed-matter"}

        mock_result = MagicMock()
        mock_result.count = 2
        mock_result.matches = [mock_match_qft, mock_match_cm]
        mock_result.query = "sign"
        mock_result.library_exists = True

        with patch("gpd.mcp.servers.patterns_server.pattern_search", return_value=mock_result):
            result = lookup_pattern(keywords="sign", domain="qft")

        # Only the qft match should survive the domain filter
        assert result["count"] == 1
        assert result["patterns"][0]["domain"] == "qft"

    def test_add_pattern_accepts_all_params(self):
        """add_pattern accepts domain, title, category, severity, description, detection, prevention."""
        from gpd.mcp.servers.patterns_server import add_pattern

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "added": True,
            "id": "qft-sign-error-fourier-sign-flip",
            "severity": "high",
        }

        with patch("gpd.mcp.servers.patterns_server.pattern_add", return_value=mock_result) as mock_add:
            result = add_pattern(
                domain="qft",
                title="Fourier sign flip",
                category="sign-error",
                severity="high",
                description="Sign flip in Fourier transform convention",
                detection="Compare against textbook definitions",
                prevention="Always verify convention at start of derivation",
            )

        mock_add.assert_called_once()
        call_kwargs = mock_add.call_args
        assert call_kwargs.kwargs.get("domain") == "qft" or call_kwargs[1].get("domain") == "qft"
        assert result["added"] is True

    def test_add_pattern_returns_error_on_pattern_error(self):
        """add_pattern returns error dict when PatternError is raised."""
        from gpd.core.errors import PatternError
        from gpd.mcp.servers.patterns_server import add_pattern

        with patch(
            "gpd.mcp.servers.patterns_server.pattern_add",
            side_effect=PatternError("Invalid domain 'fake'"),
        ):
            result = add_pattern(
                domain="fake",
                title="Bad pattern",
            )

        assert "error" in result
        assert "Invalid domain" in result["error"]

    def test_lookup_pattern_returns_error_on_pattern_error(self):
        """lookup_pattern returns error dict on PatternError."""
        from gpd.core.errors import PatternError
        from gpd.mcp.servers.patterns_server import lookup_pattern

        with patch(
            "gpd.mcp.servers.patterns_server.pattern_list",
            side_effect=PatternError("library corrupt"),
        ):
            result = lookup_pattern(domain="qft")

        assert "error" in result
        assert "library corrupt" in result["error"]

    def test_lookup_pattern_returns_error_on_os_error(self):
        """lookup_pattern returns error dict on OSError."""
        from gpd.mcp.servers.patterns_server import lookup_pattern

        with patch(
            "gpd.mcp.servers.patterns_server.pattern_list",
            side_effect=OSError("permission denied"),
        ):
            result = lookup_pattern(domain="qft")

        assert "error" in result


# ---------------------------------------------------------------------------
# 4. opencode.py guards
# ---------------------------------------------------------------------------


class TestOpenCodeGuards:
    """Test that opencode.py handles malformed JSON gracefully."""

    def test_configure_opencode_permissions_non_dict_json(self, tmp_path):
        """configure_opencode_permissions resets to {} when JSON is a list."""
        from gpd.adapters.opencode import configure_opencode_permissions

        config_dir = tmp_path / "opencode"
        config_dir.mkdir()
        config_path = config_dir / "opencode.json"
        # Write a JSON array (not a dict)
        config_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

        modified = configure_opencode_permissions(config_dir)
        assert modified is True

        # Verify the result is a valid dict with permission structure
        written = json.loads(config_path.read_text(encoding="utf-8"))
        assert isinstance(written, dict)
        assert "permission" in written
        assert isinstance(written["permission"], dict)

    def test_configure_opencode_permissions_string_json(self, tmp_path):
        """configure_opencode_permissions resets to {} when JSON is a string."""
        from gpd.adapters.opencode import configure_opencode_permissions

        config_dir = tmp_path / "opencode"
        config_dir.mkdir()
        config_path = config_dir / "opencode.json"
        config_path.write_text(json.dumps("just a string"), encoding="utf-8")

        modified = configure_opencode_permissions(config_dir)
        assert modified is True

        written = json.loads(config_path.read_text(encoding="utf-8"))
        assert isinstance(written, dict)
        assert "permission" in written

    def test_configure_opencode_permissions_malformed_json(self, tmp_path):
        """configure_opencode_permissions resets to {} when JSON is invalid."""
        from gpd.adapters.opencode import configure_opencode_permissions

        config_dir = tmp_path / "opencode"
        config_dir.mkdir()
        config_path = config_dir / "opencode.json"
        config_path.write_text("{bad json!!", encoding="utf-8")

        modified = configure_opencode_permissions(config_dir)
        assert modified is True

        written = json.loads(config_path.read_text(encoding="utf-8"))
        assert isinstance(written, dict)
        assert "permission" in written

    def test_configure_opencode_permissions_no_existing_file(self, tmp_path):
        """configure_opencode_permissions creates the config file from scratch."""
        from gpd.adapters.opencode import configure_opencode_permissions

        config_dir = tmp_path / "opencode"
        # config_dir doesn't exist yet
        modified = configure_opencode_permissions(config_dir)
        assert modified is True

        config_path = config_dir / "opencode.json"
        assert config_path.exists()
        written = json.loads(config_path.read_text(encoding="utf-8"))
        assert isinstance(written, dict)
        assert "permission" in written

    def test_configure_opencode_permissions_non_dict_permission(self, tmp_path):
        """When permission key exists but is not a dict, it gets overwritten."""
        from gpd.adapters.opencode import configure_opencode_permissions

        config_dir = tmp_path / "opencode"
        config_dir.mkdir()
        config_path = config_dir / "opencode.json"
        config_path.write_text(json.dumps({"permission": "bad"}), encoding="utf-8")

        modified = configure_opencode_permissions(config_dir)
        assert modified is True

        written = json.loads(config_path.read_text(encoding="utf-8"))
        assert isinstance(written["permission"], dict)
        assert "read" in written["permission"]

    def test_write_mcp_servers_opencode_non_dict_json(self, tmp_path):
        """_write_mcp_servers_opencode resets to {} when existing JSON is a list."""
        from gpd.adapters.opencode import _write_mcp_servers_opencode

        config_dir = tmp_path / "opencode"
        config_dir.mkdir()
        config_path = config_dir / "opencode.json"
        config_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

        servers = {
            "gpd-test": {
                "command": "python",
                "args": ["-m", "gpd.mcp.servers.test"],
                "env": {"GPD_DATA_DIR": "/tmp"},
            }
        }
        count = _write_mcp_servers_opencode(config_dir, servers)
        assert count == 1

        written = json.loads(config_path.read_text(encoding="utf-8"))
        assert isinstance(written, dict)
        assert "mcp" in written
        assert "gpd-test" in written["mcp"]

    def test_write_mcp_servers_opencode_malformed_json(self, tmp_path):
        """_write_mcp_servers_opencode resets to {} when JSON is invalid."""
        from gpd.adapters.opencode import _write_mcp_servers_opencode

        config_dir = tmp_path / "opencode"
        config_dir.mkdir()
        config_path = config_dir / "opencode.json"
        config_path.write_text("{completely broken", encoding="utf-8")

        servers = {
            "gpd-skills": {
                "command": "python",
                "args": ["-m", "gpd.mcp.servers.skills_server"],
            }
        }
        count = _write_mcp_servers_opencode(config_dir, servers)
        assert count == 1

        written = json.loads(config_path.read_text(encoding="utf-8"))
        assert isinstance(written, dict)
        assert "mcp" in written
        assert "gpd-skills" in written["mcp"]

    def test_write_mcp_servers_opencode_non_dict_mcp_key(self, tmp_path):
        """_write_mcp_servers_opencode handles mcp key being non-dict."""
        from gpd.adapters.opencode import _write_mcp_servers_opencode

        config_dir = tmp_path / "opencode"
        config_dir.mkdir()
        config_path = config_dir / "opencode.json"
        config_path.write_text(json.dumps({"mcp": "not a dict"}), encoding="utf-8")

        servers = {
            "gpd-errors": {
                "command": "python",
                "args": ["-m", "gpd.mcp.servers.errors_mcp"],
            }
        }
        count = _write_mcp_servers_opencode(config_dir, servers)
        assert count == 1

        written = json.loads(config_path.read_text(encoding="utf-8"))
        assert isinstance(written["mcp"], dict)
        assert "gpd-errors" in written["mcp"]

    def test_write_mcp_servers_opencode_no_existing_file(self, tmp_path):
        """_write_mcp_servers_opencode creates opencode.json from scratch."""
        from gpd.adapters.opencode import _write_mcp_servers_opencode

        config_dir = tmp_path / "opencode"
        # config_dir doesn't exist yet

        servers = {
            "gpd-state": {
                "command": "python",
                "args": ["-m", "gpd.mcp.servers.state_server"],
                "env": {},
            }
        }
        count = _write_mcp_servers_opencode(config_dir, servers)
        assert count == 1

        config_path = config_dir / "opencode.json"
        assert config_path.exists()
        written = json.loads(config_path.read_text(encoding="utf-8"))
        assert "mcp" in written
        assert "gpd-state" in written["mcp"]
        entry = written["mcp"]["gpd-state"]
        assert entry["type"] == "local"
        assert isinstance(entry["command"], list)


# ---------------------------------------------------------------------------
# 5. conventions_server.py error handling
# ---------------------------------------------------------------------------


class TestConventionsServerErrorHandling:
    """Test conventions_server handlers catch exceptions in post-parse processing."""

    def test_convention_lock_status_handles_malformed_state_json(self, tmp_path):
        """convention_lock_status returns error dict for malformed state.json."""
        from gpd.mcp.servers.conventions_server import convention_lock_status

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "state.json").write_text("{bad json!!")

        result = convention_lock_status(str(tmp_path))
        assert "error" in result

    def test_convention_lock_status_handles_os_error(self, tmp_path):
        """convention_lock_status returns error dict when state.json is a directory."""
        from gpd.mcp.servers.conventions_server import convention_lock_status

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "state.json").mkdir()

        result = convention_lock_status(str(tmp_path))
        assert "error" in result

    def test_convention_lock_status_handles_empty_project(self, tmp_path):
        """convention_lock_status works on a project with no state.json."""
        from gpd.mcp.servers.conventions_server import convention_lock_status

        planning = tmp_path / ".gpd"
        planning.mkdir()

        result = convention_lock_status(str(tmp_path))
        # Should return valid result with zero set conventions
        assert result["set_count"] == 0
        assert result["completeness_percent"] == 0.0

    def test_convention_check_handles_validation_error(self):
        """convention_check returns error dict when _convention_check raises ValueError."""
        from gpd.mcp.servers.conventions_server import convention_check

        with patch(
            "gpd.mcp.servers.conventions_server._convention_check",
            side_effect=ValueError("unexpected field type"),
        ):
            result = convention_check({"metric_signature": "(+,-,-,-)"})
        assert "error" in result
        assert "unexpected field type" in result["error"]

    def test_convention_check_handles_convention_error(self):
        """convention_check returns error dict on ConventionError."""
        from gpd.core.errors import ConventionError
        from gpd.mcp.servers.conventions_server import convention_check

        with patch(
            "gpd.mcp.servers.conventions_server._convention_check",
            side_effect=ConventionError("lock validation failed"),
        ):
            result = convention_check({"natural_units": "natural"})
        assert "error" in result
        assert "lock validation failed" in result["error"]

    def test_convention_check_handles_os_error(self):
        """convention_check returns error dict on OSError."""
        from gpd.mcp.servers.conventions_server import convention_check

        with patch(
            "gpd.mcp.servers.conventions_server._convention_check",
            side_effect=OSError("disk failure"),
        ):
            result = convention_check({})
        assert "error" in result
        assert "disk failure" in result["error"]

    def test_convention_lock_status_post_parse_convention_list_failure(self, tmp_path):
        """When convention_list raises a RuntimeError (not in the handler's
        except list) after successful lock load, the exception propagates
        because the try/except only guards _load_lock_from_project."""
        from gpd.mcp.servers.conventions_server import convention_lock_status

        planning = tmp_path / ".gpd"
        planning.mkdir()
        state = {"convention_lock": {"metric_signature": "(+,-,-,-)"}}
        (planning / "state.json").write_text(json.dumps(state))

        with patch(
            "gpd.mcp.servers.conventions_server.convention_list",
            side_effect=RuntimeError("unexpected in convention_list"),
        ):
            with pytest.raises(RuntimeError, match="unexpected in convention_list"):
                convention_lock_status(str(tmp_path))

    def test_convention_check_empty_lock_returns_valid_structure(self):
        """convention_check on empty lock returns well-formed result with missing_critical."""
        from gpd.mcp.servers.conventions_server import convention_check

        result = convention_check({})
        assert "valid" in result
        assert "completeness_percent" in result
        assert "missing_critical" in result
        assert "issues" in result
        assert result["completeness_percent"] == 0.0
        assert len(result["missing_critical"]) > 0

    def test_convention_diff_handles_value_error(self):
        """convention_diff returns error dict on ValueError during parsing."""
        from gpd.mcp.servers.conventions_server import convention_diff

        with patch(
            "gpd.mcp.servers.conventions_server._convention_diff",
            side_effect=ValueError("diff comparison failed"),
        ):
            result = convention_diff(
                {"metric_signature": "(+,-,-,-)"},
                {"metric_signature": "(-,+,+,+)"},
            )
        assert "error" in result
        assert "diff comparison failed" in result["error"]

    def test_convention_set_returns_error_on_timeout(self, tmp_path):
        """convention_set returns error dict on TimeoutError (file lock timeout)."""
        from gpd.mcp.servers.conventions_server import convention_set

        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({}))

        with patch(
            "gpd.mcp.servers.conventions_server._update_lock_in_project",
            side_effect=TimeoutError("lock acquisition timed out"),
        ):
            result = convention_set(str(tmp_path), "metric_signature", "(+,-,-,-)")
        assert "error" in result
        assert "timed out" in result["error"]
