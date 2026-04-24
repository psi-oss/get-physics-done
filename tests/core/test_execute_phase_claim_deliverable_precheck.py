"""Phase 5 contract tests for the `claim_deliverable_alignment_check` precheck step.

Grep-on-spec-text assertions that pin the precheck step's presence, location,
gating, suppression, abort handling, and side-by-side render shape. These
tests mirror the style of `tests/core/test_phase22_execute_phase_ownership.py`:
load `execute-phase.md` once, assert on substrings.
"""

from __future__ import annotations

from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "workflows"
EXECUTE_PHASE = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

_PRECHECK_OPEN_TAG = '<step name="claim_deliverable_alignment_check">'
_STEP_CLOSE_TAG = "</step>"


def _extract_precheck_body() -> str:
    """Slice the precheck step body (between its open tag and matching </step>).

    Returns an empty string if the step is absent, so individual tests produce
    meaningful failures rather than a module-load crash.
    """
    start = EXECUTE_PHASE.find(_PRECHECK_OPEN_TAG)
    if start == -1:
        return ""
    end = EXECUTE_PHASE.find(_STEP_CLOSE_TAG, start)
    if end == -1:
        return ""
    return EXECUTE_PHASE[start:end]


_PRECHECK_BODY = _extract_precheck_body()


def test_precheck_step_exists_and_lives_in_phase_bootstrap_region() -> None:
    assert _PRECHECK_OPEN_TAG in EXECUTE_PHASE, (
        "claim_deliverable_alignment_check step is missing from execute-phase.md"
    )

    structural_tag = '<step name="structural_validation">'
    discover_tag = '<step name="discover_and_group_plans">'

    structural_idx = EXECUTE_PHASE.index(structural_tag)
    precheck_idx = EXECUTE_PHASE.index(_PRECHECK_OPEN_TAG)
    discover_idx = EXECUTE_PHASE.index(discover_tag)

    assert structural_idx < precheck_idx < discover_idx, (
        "claim_deliverable_alignment_check must be positioned after "
        "structural_validation and before discover_and_group_plans "
        f"(got offsets structural={structural_idx}, precheck={precheck_idx}, "
        f"discover={discover_idx})"
    )


def test_precheck_fires_under_supervised() -> None:
    assert _PRECHECK_BODY, "precheck step body could not be extracted"
    assert "autonomy=supervised" in _PRECHECK_BODY, (
        "precheck gating must mention autonomy=supervised"
    )


def test_precheck_fires_under_dense_regardless_of_autonomy() -> None:
    assert _PRECHECK_BODY, "precheck step body could not be extracted"
    assert "review_cadence=dense" in _PRECHECK_BODY, (
        "precheck gating must mention review_cadence=dense"
    )


def test_precheck_skipped_under_yolo_adaptive_no_proof() -> None:
    assert _PRECHECK_BODY, "precheck step body could not be extracted"

    body_lower = _PRECHECK_BODY.lower()
    assert "yolo" in body_lower, "precheck skip clause must mention yolo"
    assert ("adaptive" in body_lower) or ("sparse" in body_lower), (
        "precheck skip clause must mention adaptive or sparse cadence"
    )
    assert "proof-bearing" in body_lower or "proof_bearing" in body_lower, (
        "precheck skip clause must mention a no-proof-bearing condition"
    )


def test_precheck_fires_on_proof_bearing_plans_regardless_of_autonomy() -> None:
    assert _PRECHECK_BODY, "precheck step body could not be extracted"

    body_lower = _PRECHECK_BODY.lower()
    assert (
        "detect_proof_obligation_work" in _PRECHECK_BODY
        or "proof-bearing" in body_lower
        or "proof_bearing" in body_lower
    ), (
        "precheck gating must reference detect_proof_obligation_work or "
        "proof-bearing plans"
    )


def test_precheck_proceed_does_not_reprompt_in_same_session() -> None:
    assert _PRECHECK_BODY, "precheck step body could not be extracted"

    body_lower = _PRECHECK_BODY.lower()
    mentions_confirmed = (
        "contract_alignment_confirmed_at" in _PRECHECK_BODY
        or "already confirmed" in body_lower
    )
    mentions_hash = ("hash" in body_lower) or ("fingerprint" in body_lower)

    assert mentions_confirmed, (
        "precheck must reference contract_alignment_confirmed_at or "
        "'already confirmed' to suppress re-prompts"
    )
    assert mentions_hash, (
        "precheck suppression must reference a hash or fingerprint check"
    )


def test_precheck_abort_does_not_spawn_workers() -> None:
    assert _PRECHECK_BODY, "precheck step body could not be extracted"

    body_lower = _PRECHECK_BODY.lower()
    # Locate the abort / "On n" branch. Accept several wording variants.
    has_abort_marker = (
        "on n" in body_lower
        or "abort" in body_lower
        or "on `n`" in body_lower
    )
    assert has_abort_marker, "precheck must describe an abort / 'On n' branch"

    # The abort branch must clearly instruct not to spawn executors or to
    # exit cleanly. Keep the match case-insensitive and loose.
    abort_guards = (
        "do not spawn",
        "don't spawn",
        "no not spawn",
        "not spawn",
        "exit",
        "stop",
        "halt",
    )
    assert any(marker in body_lower for marker in abort_guards), (
        "precheck abort branch must forbid spawning executors or direct an exit"
    )


def test_precheck_renders_claim_deliverable_side_by_side() -> None:
    assert _PRECHECK_BODY, "precheck step body could not be extracted"

    body_lower = _PRECHECK_BODY.lower()

    mentions_summary = (
        "claim_deliverable_alignment_summary" in _PRECHECK_BODY
        or "claim ↔ deliverable" in body_lower
        or "claim <-> deliverable" in body_lower
        or "alignment-summary" in body_lower
        or "alignment summary" in body_lower
    )
    assert mentions_summary, (
        "precheck must reference claim_deliverable_alignment_summary or a "
        "'Claim ↔ Deliverable' / 'alignment-summary' header"
    )

    intent_tokens = ("observables", "deliverables", "references", "stop", "rethink")
    present = sum(1 for token in intent_tokens if token in body_lower)
    # Treat stop/rethink as one slot: if either is present, count that slot once.
    stop_rethink_present = ("stop" in body_lower) or ("rethink" in body_lower)
    explicit_slots = sum(
        1 for token in ("observables", "deliverables", "references") if token in body_lower
    ) + (1 if stop_rethink_present else 0)

    assert explicit_slots >= 3, (
        "precheck render must mention at least 3 of the 4 user-intent fields "
        f"(observables, deliverables, references, stop/rethink); found {present} tokens "
        f"across the four slots"
    )
