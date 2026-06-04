"""Tests for the deslopification engine: tell detection + the invariant checker.

The invariant tests are the proof that a style edit is *machine-verified* to leave
the science untouched: a prose-only edit passes; any change to math, a citation key,
a number, or theorem status is rejected.
"""
from pathlib import Path

from gpd.core.deslopification import check_invariants, detect_tells, scan_manuscript

BEFORE = (
    r"We prove Theorem~1, which is conditional on Conjecture CPA. It is worth noting "
    r"that the Pell factor $X^2 - dY^2 = 4$ with $d = A^2 - 1$ does not lie in the "
    r"canonical menu, as shown by Halverson--Ruehle \cite{HR18}. We delve into the "
    r"landscape of 92 active blocks."
)
AFTER_GOOD = (
    r"We prove Theorem~1, which is conditional on Conjecture CPA. The Pell factor "
    r"$X^2 - dY^2 = 4$ with $d = A^2 - 1$ does not lie in the canonical menu "
    r"\cite{HR18}. The construction uses 92 active blocks."
)


def test_invariants_pass_on_prose_only_edit() -> None:
    rep = check_invariants(BEFORE, AFTER_GOOD)
    assert rep["passed"] is True
    assert rep["protected_spans_changed"] == 0
    assert rep["math_spans_identical"] and rep["citations_identical"]


def test_invariants_reject_math_change() -> None:
    rep = check_invariants(BEFORE, BEFORE.replace("dY^2 = 4", "dY^2 = 5"))
    assert rep["passed"] is False
    assert "math" in rep["drift"]
    assert "numbers" in rep["drift"]


def test_invariants_reject_citation_change() -> None:
    rep = check_invariants(BEFORE, BEFORE.replace("HR18", "HR19"))
    assert rep["passed"] is False
    assert "citations" in rep["drift"]


def test_invariants_reject_theorem_status_change() -> None:
    rep = check_invariants(BEFORE, BEFORE.replace("conditional on Conjecture CPA", "unconditional"))
    assert rep["passed"] is False
    assert "theorem_status" in rep["drift"]


def test_detect_tells_locates_scaffolding_and_vocab() -> None:
    text = (
        "The catalog is locked by Plan 01-01 commit c18e666, verbatim from PROOF.md H.3.\n"
        "We delve into the landscape of the problem.\n"
    )
    tells = {f.tell for f in detect_tells(text)}
    assert "agent_scaffolding_leakage" in tells
    assert "stock_vocabulary" in tells


def test_scan_blocks_on_placeholder_metadata(tmp_path: Path) -> None:
    p = tmp_path / "m.tex"
    p.write_text(
        "The catalog is locked by commit c18e666, verbatim from PROOF.md H.3.\n"
        "ORCID: 0000-0000-0000-0000 (TODO: insert at submission time).\n",
        encoding="utf-8",
    )
    res = scan_manuscript(p, write=False)
    assert res.release_blocker_count >= 1  # the ORCID / TODO placeholder
    assert res.gate_status == "blocked"
    assert res.edit_candidate_count >= 1   # the scaffolding leakage is rewritable
