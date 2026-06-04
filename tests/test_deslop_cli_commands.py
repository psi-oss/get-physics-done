"""CLI tests for the deslopification gate commands (`gpd deslop …`)."""
from __future__ import annotations

from pathlib import Path

from gpd.cli import app
from tests.helpers.cli import json_output_from_result
from tests.test_cli_commands import runner


def test_deslop_scan_blocks_on_placeholder(tmp_path: Path) -> None:
    m = tmp_path / "m.tex"
    m.write_text(
        "The catalog is locked by commit c18e666, verbatim from PROOF.md H.3.\n"
        "ORCID: 0000-0000-0000-0000 (TODO: insert at submission time).\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["--raw", "deslop", "scan", str(m), "--no-write"], catch_exceptions=False)
    assert result.exit_code == 0  # audit reports; only ci mode fails
    payload = json_output_from_result(result)
    assert payload["release_blocker_count"] >= 1
    assert payload["gate_status"] == "blocked"
    assert payload["edit_candidate_count"] >= 1


def test_deslop_check_rejects_science_change(tmp_path: Path) -> None:
    b = tmp_path / "b.tex"
    a = tmp_path / "a.tex"
    b.write_text(r"The factor $X^2 - dY^2 = 4$ \cite{HR18}.", encoding="utf-8")
    a.write_text(r"The factor $X^2 - dY^2 = 5$ \cite{HR18}.", encoding="utf-8")
    result = runner.invoke(app, ["--raw", "deslop", "check", str(b), str(a)], catch_exceptions=False)
    assert result.exit_code == 2  # protected span drifted -> rejected


def test_deslop_check_accepts_prose_edit(tmp_path: Path) -> None:
    b = tmp_path / "b.tex"
    a = tmp_path / "a.tex"
    b.write_text(r"It is worth noting that the factor $X^2 - dY^2 = 4$ \cite{HR18}.", encoding="utf-8")
    a.write_text(r"The factor $X^2 - dY^2 = 4$ \cite{HR18}.", encoding="utf-8")
    result = runner.invoke(app, ["--raw", "deslop", "check", str(b), str(a)], catch_exceptions=False)
    assert result.exit_code == 0  # prose-only edit, science intact


def test_validate_deslop_invariants_alias_rejects_status_change(tmp_path: Path) -> None:
    b = tmp_path / "b.tex"
    a = tmp_path / "a.tex"
    b.write_text(r"Theorem 1 is conditional on Conjecture CPA.", encoding="utf-8")
    a.write_text(r"Theorem 1 is unconditional.", encoding="utf-8")
    result = runner.invoke(app, ["--raw", "validate", "deslop-invariants", str(b), str(a)], catch_exceptions=False)
    assert result.exit_code == 2  # theorem-status drift
