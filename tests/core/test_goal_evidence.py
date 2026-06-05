"""Tests for aggregating plan-contract claim outcomes for the goal gate."""

from pathlib import Path

from gpd.core.goal_evidence import collect_claim_outcomes

_VERIFICATION_TEMPLATE = """---
phase: {phase}
verified: 2026-06-04T12:00:00Z
status: passed
contract_results:
  claims:
    {claim_id}:
      status: {claim_status}
      summary: Claim checked by verifier.
---

# Verification Report
"""


def _write_verification(project_root: Path, phase_dir: str, claim_id: str, claim_status: str) -> None:
    phase_path = project_root / "GPD" / "phases" / phase_dir
    phase_path.mkdir(parents=True, exist_ok=True)
    number = phase_dir.split("-", 1)[0]
    (phase_path / f"{number}-VERIFICATION.md").write_text(
        _VERIFICATION_TEMPLATE.format(phase=phase_dir, claim_id=claim_id, claim_status=claim_status),
        encoding="utf-8",
    )


def test_collects_claim_statuses_across_phases(tmp_path: Path) -> None:
    _write_verification(tmp_path, "01-derivation", "goal-gc-1", "passed")
    _write_verification(tmp_path, "02-limits", "goal-gc-2", "failed")
    outcomes = collect_claim_outcomes(tmp_path)
    assert outcomes == {"goal-gc-1": "passed", "goal-gc-2": "failed"}


def test_later_phase_supersedes_earlier_status_for_same_claim(tmp_path: Path) -> None:
    _write_verification(tmp_path, "01-derivation", "goal-gc-1", "failed")
    _write_verification(tmp_path, "02-revision", "goal-gc-1", "passed")
    outcomes = collect_claim_outcomes(tmp_path)
    assert outcomes == {"goal-gc-1": "passed"}


def test_returns_empty_for_missing_phases_dir(tmp_path: Path) -> None:
    assert collect_claim_outcomes(tmp_path) == {}


def test_ignores_verification_files_without_contract_results(tmp_path: Path) -> None:
    phase_path = tmp_path / "GPD" / "phases" / "01-derivation"
    phase_path.mkdir(parents=True)
    (phase_path / "01-VERIFICATION.md").write_text(
        "---\nphase: 01-derivation\nstatus: passed\n---\n\n# Report\n", encoding="utf-8"
    )
    assert collect_claim_outcomes(tmp_path) == {}


def test_ignores_malformed_frontmatter_instead_of_raising(tmp_path: Path) -> None:
    phase_path = tmp_path / "GPD" / "phases" / "01-derivation"
    phase_path.mkdir(parents=True)
    (phase_path / "01-VERIFICATION.md").write_text(
        "---\n: not yaml :\n---\n", encoding="utf-8"
    )
    assert collect_claim_outcomes(tmp_path) == {}


def test_collects_phase_statuses(tmp_path: Path) -> None:
    from gpd.core.goal_evidence import collect_phase_statuses

    _write_verification(tmp_path, "01-derivation", "goal-gc-1", "passed")
    _write_verification(tmp_path, "02-limits", "goal-gc-2", "failed")
    statuses = collect_phase_statuses(tmp_path)
    # top-level frontmatter status of each VERIFICATION.md (template uses "passed")
    assert statuses == {"01-derivation": "passed", "02-limits": "passed"}


def test_phase_statuses_empty_for_missing_phases_dir(tmp_path: Path) -> None:
    from gpd.core.goal_evidence import collect_phase_statuses

    assert collect_phase_statuses(tmp_path) == {}
