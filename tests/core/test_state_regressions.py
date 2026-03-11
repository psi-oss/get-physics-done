"""Behavior-focused state regressions curated from historical audit rounds."""

from __future__ import annotations

from pathlib import Path


_SAMPLE_STATE_MD = """\
# Research State

## Project Reference

See: .gpd/PROJECT.md (updated 2026-03-08)

**Core research question:** What is the mass gap in Yang-Mills theory?
**Current focus:** Lattice simulations

## Current Position

**Current Phase:** 2
**Current Phase Name:** Formulate Hamiltonian
**Total Phases:** 6
**Current Plan:** 1
**Total Plans in Phase:** 3
**Status:** Executing
**Last Activity:** 2026-03-08
**Last Activity Description:** Set up lattice parameters

**Progress:** [####......] 40%

## Active Calculations

None yet.

## Intermediate Results

None yet.

## Open Questions

None yet.

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |

## Accumulated Context

### Decisions

None yet.

### Active Approximations

None yet.

**Convention Lock:**

No conventions locked yet.

### Propagated Uncertainties

None yet.

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

**Last session:** 2026-03-08T14:00:00+00:00
**Stopped at:** Phase 2 P1
**Resume file:** None
"""


def _make_state_md(tmp_path: Path) -> Path:
    gpd_dir = tmp_path / ".gpd"
    gpd_dir.mkdir(parents=True)
    state_md = gpd_dir / "STATE.md"
    state_md.write_text(
        "# State\n\n"
        "## Current Position\n\n"
        "**Status:** Active\n\n"
        "### Decisions\nNone yet.\n\n"
        "### Blockers\nNone.\n",
        encoding="utf-8",
    )
    (gpd_dir / "state.json").write_text("{}", encoding="utf-8")
    return state_md


def test_parse_state_md_uses_core_research_question_key() -> None:
    from gpd.core.state import parse_state_md

    parsed = parse_state_md(_SAMPLE_STATE_MD)

    assert "core_research_question" in parsed["project"]
    assert "core_question" not in parsed["project"]
    assert parsed["project"]["core_research_question"] == "What is the mass gap in Yang-Mills theory?"


def test_parse_state_to_json_reads_core_research_question() -> None:
    from gpd.core.state import parse_state_to_json

    result = parse_state_to_json(_SAMPLE_STATE_MD)

    assert result["project_reference"]["core_research_question"] == (
        "What is the mass gap in Yang-Mills theory?"
    )


def test_core_research_question_round_trips() -> None:
    from gpd.core.state import parse_state_md, parse_state_to_json

    parsed = parse_state_md(_SAMPLE_STATE_MD)
    result = parse_state_to_json(_SAMPLE_STATE_MD)

    assert parsed["project"]["core_research_question"] == result["project_reference"]["core_research_question"]


def test_decision_newlines_are_sanitized(tmp_path: Path) -> None:
    from gpd.core.state import state_add_decision

    state_md = _make_state_md(tmp_path)
    result = state_add_decision(
        tmp_path,
        summary="Line one\nLine two\nLine three",
        phase="1",
        rationale="Because\nof\nthis",
    )

    assert result.added is True
    content = state_md.read_text(encoding="utf-8")
    assert "Line one Line two Line three" in content


def test_blocker_newlines_are_sanitized(tmp_path: Path) -> None:
    from gpd.core.state import state_add_blocker

    state_md = _make_state_md(tmp_path)
    result = state_add_blocker(tmp_path, "Problem\nwith\nspacing")

    assert result.added is True
    assert "Problem with spacing" in state_md.read_text(encoding="utf-8")


def test_decision_phase_none_round_trips_without_placeholder_leak() -> None:
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

    parsed = parse_state_md(generate_state_markdown(state))

    decision = next(item for item in parsed.get("decisions", []) if "natural units" in item.get("summary", "").lower())
    assert decision.get("phase") in {None, "—"}


def test_strip_placeholder_returns_stripped_value() -> None:
    from gpd.core.state import _strip_placeholder

    assert _strip_placeholder("  some_value  ") == "some_value"
    assert _strip_placeholder("—") is None
    assert _strip_placeholder("None") is None
    assert _strip_placeholder("[Not set]") is None
    assert _strip_placeholder(None) is None


def test_resume_file_none_round_trips_as_none() -> None:
    from gpd.core.state import generate_state_markdown, parse_state_to_json

    state = {
        "project": {},
        "position": {"current_phase": "01", "status": "Executing"},
        "decisions": [],
        "blockers": [],
        "session": {"resume_file": None, "agent_model": "test"},
        "metrics": [],
        "active_calculations": [],
        "intermediate_results": [],
        "open_questions": [],
    }

    parsed = parse_state_to_json(generate_state_markdown(state))

    assert parsed.get("session", {}).get("resume_file") is None


def test_state_extract_field_treats_em_dash_as_missing() -> None:
    from gpd.core.state import state_extract_field

    assert state_extract_field("**Status:** —", "Status") is None
