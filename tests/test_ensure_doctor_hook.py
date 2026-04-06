"""Tests for ensure_doctor_hook in install_utils.py."""

from __future__ import annotations

import copy

import pytest

from gpd.adapters.install_utils import HOOK_SCRIPTS, ensure_doctor_hook


DOCTOR_COMMAND = "python3 .claude/hooks/install_doctor.py"


class TestEnsureDoctorHook:
    """Test the ensure_doctor_hook function."""

    def test_adds_doctor_hook_to_empty_settings(self) -> None:
        settings: dict[str, object] = {}
        ensure_doctor_hook(settings, DOCTOR_COMMAND)
        hooks = settings["hooks"]
        assert isinstance(hooks, dict)
        session_start = hooks["SessionStart"]
        assert isinstance(session_start, list)
        assert len(session_start) == 1
        entry = session_start[0]
        assert isinstance(entry, dict)
        inner_hooks = entry["hooks"]
        assert isinstance(inner_hooks, list)
        assert len(inner_hooks) == 1
        assert inner_hooks[0]["type"] == "command"
        assert inner_hooks[0]["command"] == DOCTOR_COMMAND

    def test_preserves_existing_hooks(self) -> None:
        existing_entry = {"hooks": [{"type": "command", "command": "echo hello"}]}
        settings: dict[str, object] = {
            "hooks": {"SessionStart": [existing_entry]}
        }
        ensure_doctor_hook(settings, DOCTOR_COMMAND)
        session_start = settings["hooks"]["SessionStart"]
        assert isinstance(session_start, list)
        # Original entry preserved + new doctor entry added.
        assert len(session_start) == 2
        assert session_start[0] == existing_entry

    def test_updates_stale_doctor_hook(self) -> None:
        old_command = "python3 .claude/hooks/install_doctor.py"
        new_command = "python3.13 .claude/hooks/install_doctor.py"
        settings: dict[str, object] = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": old_command}]}
                ]
            }
        }
        ensure_doctor_hook(
            settings,
            new_command,
            config_dir_name=".claude",
        )
        session_start = settings["hooks"]["SessionStart"]
        assert isinstance(session_start, list)
        assert len(session_start) == 1
        entry = session_start[0]
        inner_hooks = entry["hooks"]
        assert inner_hooks[0]["command"] == new_command

    def test_deduplicates_doctor_hooks(self) -> None:
        settings: dict[str, object] = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": DOCTOR_COMMAND}]},
                    {"hooks": [{"type": "command", "command": DOCTOR_COMMAND}]},
                ]
            }
        }
        ensure_doctor_hook(
            settings,
            DOCTOR_COMMAND,
            config_dir_name=".claude",
        )
        session_start = settings["hooks"]["SessionStart"]
        assert isinstance(session_start, list)
        # Only one doctor hook should remain.
        doctor_count = sum(
            1
            for entry in session_start
            if isinstance(entry, dict)
            for hook in (entry.get("hooks") or [])
            if isinstance(hook, dict) and "install_doctor" in hook.get("command", "")
        )
        assert doctor_count == 1

    def test_install_doctor_in_hook_scripts(self) -> None:
        """Verify install_doctor is registered in HOOK_SCRIPTS."""
        assert "install_doctor" in HOOK_SCRIPTS
        assert HOOK_SCRIPTS["install_doctor"] == "install_doctor.py"
