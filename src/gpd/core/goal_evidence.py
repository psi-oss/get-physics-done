"""Aggregate plan-contract claim outcomes from phase VERIFICATION.md files.

The goal gate's only accepted evidence source: ``contract_results.claims``
frontmatter written by the verification machinery. Phases are scanned in
sorted order, so a later phase's status for the same claim id supersedes an
earlier one (revision phases can repair a previously failed claim).
"""

from __future__ import annotations

from pathlib import Path

from gpd.core.frontmatter import extract_frontmatter

__all__ = ["collect_claim_outcomes", "collect_phase_statuses"]


def _iter_verification_meta(project_root: Path):
    """Yield (phase_dir_name, frontmatter_meta) for each parseable VERIFICATION.md."""
    phases_dir = project_root / "GPD" / "phases"
    if not phases_dir.is_dir():
        return
    for verification_path in sorted(phases_dir.glob("*/*-VERIFICATION.md")):
        try:
            meta, _body = extract_frontmatter(verification_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict):
            yield verification_path.parent.name, meta


def collect_claim_outcomes(project_root: Path) -> dict[str, str]:
    """Map claim id -> latest contract_results claim status across phases."""
    outcomes: dict[str, str] = {}
    for _phase_name, meta in _iter_verification_meta(project_root):
        contract_results = meta.get("contract_results")
        if not isinstance(contract_results, dict):
            continue
        claims = contract_results.get("claims")
        if not isinstance(claims, dict):
            continue
        for claim_id, claim_payload in claims.items():
            if not isinstance(claim_payload, dict):
                continue
            status = claim_payload.get("status")
            if isinstance(status, str) and status:
                outcomes[str(claim_id)] = status
    return outcomes


def collect_phase_statuses(project_root: Path) -> dict[str, str]:
    """Map phase directory name -> top-level VERIFICATION.md frontmatter status."""
    statuses: dict[str, str] = {}
    for phase_name, meta in _iter_verification_meta(project_root):
        status = meta.get("status")
        if isinstance(status, str) and status:
            statuses[phase_name] = status
    return statuses
