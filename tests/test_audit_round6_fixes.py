"""Tests for round 6 codebase audit fixes."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


def test_strikethrough_regex_non_greedy():
    """The strikethrough removal regex should use non-greedy matching."""
    import re
    import inspect
    import gpd.core.state as state_mod
    source = inspect.getsource(state_mod)
    # The regex should use non-greedy ~~.*?~~ not greedy ~~.*~~
    assert "~~.*?~~" in source or "~~[^~]*~~" in source, (
        "Strikethrough regex should be non-greedy"
    )
    # Verify the greedy version is NOT present
    greedy_matches = re.findall(r'~~\.\*~~', source)
    assert len(greedy_matches) == 0, (
        "No greedy ~~.*~~ patterns should remain"
    )


def test_pattern_entry_has_validate_assignment():
    """PatternEntry should have validate_assignment=True."""
    from gpd.core.patterns import PatternEntry
    config = PatternEntry.model_config
    assert config.get("validate_assignment") is True, (
        "PatternEntry should have validate_assignment=True"
    )


def test_health_check_has_validate_assignment():
    """HealthCheck should have validate_assignment=True."""
    from gpd.core.health import HealthCheck
    config = HealthCheck.model_config
    assert config.get("validate_assignment") is True, (
        "HealthCheck should have validate_assignment=True"
    )


def test_decision_phase_none_roundtrip():
    """Decision with phase=None should round-trip through markdown without becoming '?'."""
    from gpd.core.state import generate_state_markdown, parse_state_md
    state = {
        "project": {},
        "position": {"current_phase": "01", "status": "Executing"},
        "decisions": [{"phase": None, "summary": "Use natural units", "rationale": "simplicity"}],
        "blockers": [],
        "session": {},
        "metrics": [],
        "active_calculations": [],
        "intermediate_results": [],
        "open_questions": [],
    }
    md = generate_state_markdown(state)
    parsed = parse_state_md(md)
    for d in parsed.get("decisions", []):
        if "natural units" in d.get("summary", "").lower():
            assert d.get("phase") is None or d.get("phase") == "\u2014", (
                f"Decision phase should be None or em-dash after round-trip, got {d.get('phase')!r}"
            )
            break


def test_state_server_catches_timeout_error():
    """State server MCP tools should catch TimeoutError."""
    import ast
    import inspect
    from gpd.mcp.servers import state_server
    source = inspect.getsource(state_server)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type:
            # Check if any except handler includes TimeoutError
            if isinstance(node.type, ast.Tuple):
                names = [
                    elt.id if isinstance(elt, ast.Name) else ""
                    for elt in node.type.elts
                ]
                if "GPDError" in names:
                    assert "TimeoutError" in names, (
                        f"except clause with GPDError should also catch TimeoutError: {names}"
                    )


def test_show_events_no_fallback_when_global_exists(tmp_path):
    """show_events should not fall back to session events when global file exists but has no matches."""
    from gpd.core.observability import show_events
    # Create minimal project structure
    gpd_dir = tmp_path / ".gpd"
    obs_dir = gpd_dir / "observability"
    obs_dir.mkdir(parents=True)
    events_file = obs_dir / "events.jsonl"
    events_file.write_text('{"event_id": "e1", "action": "log", "category": "test"}\n', encoding="utf-8")

    result = show_events(tmp_path, category="nonexistent")
    # Should return result with empty events, NOT fall back to session events
    assert hasattr(result, "events") or isinstance(result, dict)
    events = result.events if hasattr(result, "events") else result.get("events", [])
    assert events == []


def test_init_todos_handles_corrupt_file(tmp_path):
    """init_todos should skip corrupt todo files instead of crashing."""
    from gpd.core.context import init_todos
    gpd_dir = tmp_path / ".gpd"
    todo_dir = gpd_dir / "pending-todos"
    todo_dir.mkdir(parents=True)

    # Create a valid todo
    (todo_dir / "valid.md").write_text("# Valid Todo\nDo something", encoding="utf-8")
    # Create a binary/corrupt file
    (todo_dir / "corrupt.md").write_bytes(b"\x80\x81\x82\x83\x84\x85")

    # Should not crash
    result = init_todos(tmp_path)
    assert isinstance(result, dict)


def test_state_result_models_are_frozen():
    """State result models should be frozen (immutable)."""
    from gpd.core.state import (
        UpdateProgressResult,
        AddDecisionResult,
        AddBlockerResult,
        ResolveBlockerResult,
        RecordSessionResult,
        StateSnapshotResult,
        StateCompactResult,
    )
    for model_cls in [
        UpdateProgressResult,
        AddDecisionResult,
        AddBlockerResult,
        ResolveBlockerResult,
        RecordSessionResult,
        StateSnapshotResult,
        StateCompactResult,
    ]:
        config = model_cls.model_config
        assert config.get("frozen") is True, (
            f"{model_cls.__name__} should have frozen=True"
        )


def test_artifact_check_has_validate_assignment():
    """ArtifactCheck should have validate_assignment=True for safe mutation."""
    from gpd.core.frontmatter import ArtifactCheck
    config = ArtifactCheck.model_config
    assert config.get("validate_assignment") is True, (
        "ArtifactCheck should have validate_assignment=True"
    )
