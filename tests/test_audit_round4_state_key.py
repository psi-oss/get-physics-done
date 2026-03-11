"""Tests for audit round 4: fix core_question -> core_research_question key naming asymmetry.

The intermediate dict produced by ``parse_state_md`` now uses
``"core_research_question"`` (matching the Pydantic model field name) instead
of the old ``"core_question"`` key, eliminating a maintenance-hazard mismatch
between the parser output and the model.
"""

from __future__ import annotations

from gpd.core.state import parse_state_md, parse_state_to_json

# A minimal but valid STATE.md for testing the key-naming fix.
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


# --- Test 1: parse_state_md uses the new key name ---


def test_parse_state_md_uses_core_research_question_key():
    """parse_state_md must store the core question under 'core_research_question',
    matching the Pydantic model field name."""
    parsed = parse_state_md(_SAMPLE_STATE_MD)
    project = parsed["project"]

    assert "core_research_question" in project, (
        "Expected 'core_research_question' key in parsed['project']; "
        f"got keys: {list(project.keys())}"
    )
    assert "core_question" not in project, (
        "Old 'core_question' key must no longer appear in parsed['project']"
    )
    assert project["core_research_question"] == "What is the mass gap in Yang-Mills theory?"


# --- Test 2: parse_state_to_json correctly reads the new key ---


def test_parse_state_to_json_reads_new_key():
    """parse_state_to_json must successfully translate the new
    'core_research_question' key into the output JSON."""
    result = parse_state_to_json(_SAMPLE_STATE_MD)

    assert result["project_reference"]["core_research_question"] == (
        "What is the mass gap in Yang-Mills theory?"
    )


# --- Test 3: round-trip consistency ---


def test_round_trip_core_research_question():
    """parse STATE.md -> convert to JSON -> check core_research_question field
    is consistent through the pipeline."""
    parsed = parse_state_md(_SAMPLE_STATE_MD)
    json_result = parse_state_to_json(_SAMPLE_STATE_MD)

    # The intermediate dict value ...
    intermediate_value = parsed["project"]["core_research_question"]
    # ... must match the final JSON output value.
    final_value = json_result["project_reference"]["core_research_question"]

    assert intermediate_value == final_value, (
        f"Round-trip mismatch: intermediate={intermediate_value!r}, "
        f"final={final_value!r}"
    )
    assert final_value == "What is the mass gap in Yang-Mills theory?"
