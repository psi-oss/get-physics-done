"""Tests that advance_plan and validate_state return error dicts instead of raising.

These cover the try/except wrappers added to both tools, matching the
error-handling pattern used by every other tool in state_server.py.
"""

from __future__ import annotations

from gpd.core.errors import GPDError
from gpd.mcp.servers.state_server import advance_plan, validate_state


class TestAdvancePlanErrorHandling:
    """advance_plan must catch exceptions and return {"error": ...}."""

    def test_gpd_error(self, monkeypatch, fake_project_dir):
        monkeypatch.setattr(
            "gpd.mcp.servers.state_server.state_advance_plan",
            lambda _cwd: (_ for _ in ()).throw(GPDError("test error")),
        )
        result = advance_plan(fake_project_dir)
        assert result == {"error": "test error", "schema_version": 1}

    def test_os_error(self, monkeypatch, fake_project_dir):
        monkeypatch.setattr(
            "gpd.mcp.servers.state_server.state_advance_plan",
            lambda _cwd: (_ for _ in ()).throw(OSError("file not found")),
        )
        result = advance_plan(fake_project_dir)
        assert result == {"error": "file not found", "schema_version": 1}


class TestValidateStateErrorHandling:
    """validate_state must catch exceptions and return {"error": ...}."""

    def test_gpd_error(self, monkeypatch, fake_project_dir):
        monkeypatch.setattr(
            "gpd.mcp.servers.state_server.state_validate",
            lambda _cwd, **_kwargs: (_ for _ in ()).throw(GPDError("bad state")),
        )
        result = validate_state(fake_project_dir)
        assert result == {"error": "bad state", "schema_version": 1}

    def test_value_error(self, monkeypatch, fake_project_dir):
        monkeypatch.setattr(
            "gpd.mcp.servers.state_server.state_validate",
            lambda _cwd, **_kwargs: (_ for _ in ()).throw(ValueError("invalid")),
        )
        result = validate_state(fake_project_dir)
        assert result == {"error": "invalid", "schema_version": 1}
