from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle" / "manifest.json"
PHASE08_QUEUE_PATH = Path("/tmp/gpd-bug-campaign/repro/08-repro-queue.json")
PHASE08_BLOCKED_PATH = Path("/tmp/gpd-bug-campaign/repro/08-blocked-candidates.json")


def _load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_phase08() -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    queue = json.loads(PHASE08_QUEUE_PATH.read_text(encoding="utf-8"))["queue"]
    blocked = json.loads(PHASE08_BLOCKED_PATH.read_text(encoding="utf-8"))["blocked_families"]
    return (
        {str(row["packet_id"]): row for row in queue},
        {str(row["bug_type_id"]): row for row in blocked},
    )


def test_phase09_manifest_matches_contract_shape() -> None:
    manifest = _load_manifest()

    required = {
        "schema_version",
        "bundle",
        "generated_at",
        "source_phase",
        "source_authority",
        "source_artifacts",
        "fixture_count",
        "positive_fixture_count",
        "mutation_fixture_count",
        "blocked_reference_count",
        "lane_counts",
        "covered_bug_type_ids",
        "covered_packet_ids",
        "fixtures",
        "blocked_references",
    }
    assert required <= set(manifest)
    assert manifest["schema_version"] == 1
    assert manifest["source_phase"] == "09"
    assert manifest["source_authority"] == "accepted_phase08_packet_corpus"
    assert isinstance(manifest["fixtures"], list)
    assert isinstance(manifest["blocked_references"], list)
    assert manifest["fixture_count"] == len(manifest["fixtures"])
    assert manifest["blocked_reference_count"] == len(manifest["blocked_references"])


def test_phase09_manifest_order_and_counts_are_stable() -> None:
    manifest = _load_manifest()
    fixtures = manifest["fixtures"]
    assert fixtures, "Phase 09 must emit live fixtures"

    orders = [fixture["order"] for fixture in fixtures]
    assert orders == list(range(1, len(fixtures) + 1))

    positive_count = sum(1 for fixture in fixtures if fixture["fixture_kind"] == "positive")
    mutation_count = sum(1 for fixture in fixtures if fixture["fixture_kind"] == "mutation")
    assert manifest["positive_fixture_count"] == positive_count
    assert manifest["mutation_fixture_count"] == mutation_count

    lane_counts = {}
    for fixture in fixtures:
        if fixture["fixture_kind"] != "positive":
            continue
        lane = fixture["primary_interface_class"]
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
    assert manifest["lane_counts"] == lane_counts
    assert {"cli", "race", "env"} <= set(lane_counts)


def test_phase09_live_fixtures_reference_only_live_phase08_packets() -> None:
    manifest = _load_manifest()
    queue_by_packet, _ = _load_phase08()

    covered_packet_ids: list[str] = []
    covered_bug_type_ids: set[str] = set()
    for fixture in manifest["fixtures"]:
        fixture_path = REPO_ROOT / fixture["fixture_path"]
        workspace_path = REPO_ROOT / fixture["workspace_path"]
        assert fixture_path.exists()
        assert workspace_path.exists()
        assert (fixture_path / "fixture.json").exists()
        assert fixture["status"] == "live"
        assert fixture["fixture_kind"] in {"positive", "mutation"}
        assert fixture["primary_interface_class"] in {"cli", "race", "env"}

        for packet_id in fixture["packet_ids"]:
            assert packet_id in queue_by_packet
            covered_packet_ids.append(packet_id)
            covered_bug_type_ids.add(str(queue_by_packet[packet_id]["bug_type_id"]))

        for bug_type_id in fixture["bug_type_ids"]:
            assert any(str(queue_by_packet[packet_id]["bug_type_id"]) == bug_type_id for packet_id in fixture["packet_ids"])

    assert manifest["covered_packet_ids"] == covered_packet_ids
    assert manifest["covered_bug_type_ids"] == sorted(covered_bug_type_ids)


def test_phase09_blocked_references_stay_out_of_live_set() -> None:
    manifest = _load_manifest()
    _, blocked_by_bug = _load_phase08()

    live_bug_ids = {bug_type_id for fixture in manifest["fixtures"] for bug_type_id in fixture["bug_type_ids"]}
    blocked_bug_ids = set()
    for record in manifest["blocked_references"]:
        bug_type_id = record["bug_type_id"]
        blocked_bug_ids.add(bug_type_id)
        assert bug_type_id in blocked_by_bug
        reference_path = REPO_ROOT / record["reference_path"]
        assert reference_path.exists()
        assert record["status"] == "blocked"

    assert live_bug_ids.isdisjoint(blocked_bug_ids)


def test_phase09_pairs_preserve_lineage_or_record_positive_only_justification() -> None:
    manifest = _load_manifest()
    by_id = {fixture["fixture_id"]: fixture for fixture in manifest["fixtures"]}

    for fixture in manifest["fixtures"]:
        paired = fixture["paired_fixture_id"]
        if fixture["fixture_kind"] == "mutation":
            assert paired
            counterpart = by_id[paired]
            assert counterpart["fixture_kind"] == "positive"
            assert counterpart["paired_fixture_id"] == fixture["fixture_id"]
            assert counterpart["bug_type_ids"] == fixture["bug_type_ids"]
            assert counterpart["packet_ids"] == fixture["packet_ids"]
            assert counterpart["source_workspaces"] == fixture["source_workspaces"]
            assert counterpart["starting_snapshot_hashes"] == fixture["starting_snapshot_hashes"]
            assert fixture["mutation_axis"]
        else:
            if paired:
                counterpart = by_id[paired]
                assert counterpart["fixture_kind"] == "mutation"
                assert counterpart["paired_fixture_id"] == fixture["fixture_id"]
            else:
                assert fixture["positive_only_justification"]
