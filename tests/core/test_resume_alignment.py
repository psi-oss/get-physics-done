"""Regression tests for resume/state documentation alignment."""

from __future__ import annotations

import json
import re
from pathlib import Path

from gpd.core import context as context_module
from gpd.core.context import init_resume
from gpd.core.state import default_state_dict


ROOT = Path(__file__).resolve().parents[2]


def _setup_project(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()


def _write_state(tmp_path: Path, state: dict) -> None:
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def test_resume_docs_use_canonical_paths_and_no_legacy_resume_command() -> None:
    resume_doc = (ROOT / "src/gpd/specs/workflows/resume-work.md").read_text(encoding="utf-8")
    portability_doc = (ROOT / "src/gpd/specs/references/orchestration/state-portability.md").read_text(encoding="utf-8")
    schema_doc = (ROOT / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8")

    for doc in (resume_doc, portability_doc):
        assert ".gpd/" not in doc
        assert re.search(r"/gpd:resume(?!-work)\b", doc) is None
        assert "auto_checkpoint" not in doc

    assert "/gpd:resume-work" in portability_doc
    assert "execution_resume_file" in resume_doc
    assert "execution_resume_file" in portability_doc
    assert "machine_change_detected" in resume_doc
    assert "session_resume_file" in resume_doc
    assert "hostname" in schema_doc
    assert "platform" in schema_doc
    assert "GPD/phases/03-analysis/.continue-here.md" in schema_doc
    assert '"resume_file": "GPD/phases/03-analysis/.continue-here.md"' in schema_doc


def test_init_resume_surfaces_machine_change_and_session_resume_candidate(
    tmp_path: Path, monkeypatch
) -> None:
    _setup_project(tmp_path)
    state = default_state_dict()
    state["session"]["hostname"] = "old-host"
    state["session"]["platform"] = "Linux 5.15 x86_64"
    state["session"]["resume_file"] = "GPD/phases/03-analysis/.continue-here.md"
    _write_state(tmp_path, state)
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "new-host", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["execution_resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["execution_resume_file_source"] == "session_resume_file"
    assert ctx["execution_paused_at"] is None
    assert ctx["resume_mode"] is None
    assert ctx["segment_candidates"] == [
        {
            "source": "session_resume_file",
            "status": "handoff",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "resumable": False,
        }
    ]
    assert ctx["active_execution_segment"] is None
    assert ctx["has_interrupted_agent"] is False
    assert ctx["session_hostname"] == "old-host"
    assert ctx["session_platform"] == "Linux 5.15 x86_64"
    assert ctx["current_hostname"] == "new-host"
    assert ctx["current_platform"] == "Linux 6.1 x86_64"
    assert ctx["machine_change_detected"] is True
    assert "old-host" in ctx["machine_change_notice"]
    assert "new-host" in ctx["machine_change_notice"]
