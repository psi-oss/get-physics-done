from __future__ import annotations

from pathlib import Path

from tests.phase15_contract_helpers import (
    load_phase15_contract_index,
    phase15_checklist_items,
    phase15_contract_index,
    phase15_family_ids,
)


def test_phase15_contract_registry_matches_on_disk_index() -> None:
    index = phase15_contract_index()
    on_disk = load_phase15_contract_index()

    assert on_disk == index
    assert index["schema_version"] == 1
    assert index["phase"] == "15"
    assert index["wave"] == "F5"
    assert index["artifact_root"] == "artifacts/phases/15-verification-contract/verification/fixes"
    assert [family["family_id"] for family in index["families"]] == list(phase15_family_ids())
    assert [family["bug_id"] for family in index["families"]] == list(phase15_family_ids())
    assert len(index["families"]) == 8
    assert len({family["artifact_path"] for family in index["families"]}) == 8
    assert index["checklist_items"] == list(phase15_checklist_items())


def test_phase15_pr_template_contains_verification_gates() -> None:
    template = Path(".github/pull_request_template.md").read_text(encoding="utf-8")

    for item in phase15_checklist_items():
        assert item in template
    assert "Phase 15 Verification" in template
