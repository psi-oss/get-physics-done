from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN_ROOT = REPO_ROOT / "artifacts" / "bug-campaign"
SCORECARD_ROOT = REPO_ROOT / "artifacts" / "verification" / "scorecards"
VERIFIED_PATH = REPO_ROOT / "tmp" / "handoff-bundle" / "verification-02" / "VERIFIED-BUGS-VERIFICATION.json"
FIXTURE_MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle" / "manifest.json"


def _jsonl_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line)


def _jsonl_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        payload = json.loads(line)
        assert isinstance(payload, dict)
        rows.append(payload)
    return rows


def test_bug_campaign_stage_a_ledgers_cover_the_full_verified_corpus() -> None:
    verified = json.loads(VERIFIED_PATH.read_text(encoding="utf-8"))
    assert isinstance(verified, dict)
    source_candidates = verified["candidates"]
    assert isinstance(source_candidates, list)

    candidates_path = CAMPAIGN_ROOT / "taxonomy" / "02-candidates.jsonl"
    atomic_path = CAMPAIGN_ROOT / "taxonomy" / "03-atomic-findings.jsonl"
    normalized_path = CAMPAIGN_ROOT / "taxonomy" / "04-normalized-findings.jsonl"
    product_path = CAMPAIGN_ROOT / "taxonomy" / "05-product-findings.jsonl"
    cluster_path = CAMPAIGN_ROOT / "taxonomy" / "06-cluster-seeds.jsonl"
    registry_path = CAMPAIGN_ROOT / "taxonomy" / "07-bug-type-registry.json"
    finding_map_path = CAMPAIGN_ROOT / "taxonomy" / "07-finding-to-type-map.csv"

    assert _jsonl_count(candidates_path) == len(source_candidates) == 1356
    assert _jsonl_count(atomic_path) >= _jsonl_count(candidates_path)
    assert _jsonl_count(normalized_path) == _jsonl_count(atomic_path)
    assert _jsonl_count(product_path) > 0
    assert _jsonl_count(cluster_path) > 0

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert isinstance(registry, dict)
    assert registry["bug_type_count"] > 0
    assert registry["unresolved_singleton_count"] >= 0
    assert finding_map_path.exists()


def test_bug_campaign_disposition_files_partition_normalized_findings() -> None:
    normalized_rows = _jsonl_rows(CAMPAIGN_ROOT / "taxonomy" / "04-normalized-findings.jsonl")
    disposition_files = {
        "product_finding": CAMPAIGN_ROOT / "taxonomy" / "05-product-findings.jsonl",
        "noise": CAMPAIGN_ROOT / "taxonomy" / "05-noise-registry.jsonl",
        "expected_behavior_or_non_product": CAMPAIGN_ROOT / "taxonomy" / "05-expected-behavior-registry.jsonl",
        "insufficient_detail": CAMPAIGN_ROOT / "taxonomy" / "05-insufficient-detail.jsonl",
    }

    total = sum(_jsonl_count(path) for path in disposition_files.values())
    assert total == len(normalized_rows)
    assert {row["disposition"] for row in normalized_rows} <= set(disposition_files)


def test_bug_campaign_phase08_reconstruction_is_explicitly_partial_and_matches_fixture_manifest() -> None:
    fixture_manifest = json.loads(FIXTURE_MANIFEST_PATH.read_text(encoding="utf-8"))
    family_manifest = json.loads((CAMPAIGN_ROOT / "repro" / "08-family-manifest.json").read_text(encoding="utf-8"))
    queue = json.loads((CAMPAIGN_ROOT / "repro" / "08-repro-queue.json").read_text(encoding="utf-8"))
    blocked = json.loads((CAMPAIGN_ROOT / "repro" / "08-blocked-candidates.json").read_text(encoding="utf-8"))

    assert family_manifest["reconstruction_scope"] == "covered_live_phase09_subset"
    assert family_manifest["accepted_phase08_packet_count"] == fixture_manifest["accepted_phase08_packet_count"]
    assert family_manifest["accepted_phase08_blocked_count"] == fixture_manifest["accepted_phase08_blocked_count"]
    assert family_manifest["covered_bug_type_count"] == len(fixture_manifest["covered_bug_type_ids"])
    assert family_manifest["covered_packet_count"] == len(fixture_manifest["covered_packet_ids"])
    assert family_manifest["covered_unique_packet_count"] == len(set(fixture_manifest["covered_packet_ids"]))
    assert len(queue) == len(fixture_manifest["covered_packet_ids"])
    assert len(blocked) == fixture_manifest["blocked_reference_count"]


def test_bug_campaign_scorecards_and_phase_status_expose_unclosed_gates() -> None:
    phase_status = json.loads((CAMPAIGN_ROOT / "phase-status.json").read_text(encoding="utf-8"))
    phase_rows = {row["phase"]: row for row in phase_status["phase_statuses"]}

    assert phase_rows["10"]["status"] == "missing_exact_repro_artifacts"
    assert phase_rows["18"]["status"] == "scorecards_generated_not_closed"

    for filename in (
        "repro-funnel.json",
        "surface-parity.json",
        "checkpoint-board.json",
        "benchmarks.json",
        "family-closure.json",
    ):
        assert (SCORECARD_ROOT / filename).exists()

    family_closure = json.loads((SCORECARD_ROOT / "family-closure.json").read_text(encoding="utf-8"))
    assert family_closure["closed_phase15_family_count"] < family_closure["phase15_family_count"]
    assert all(not family["closed"] for family in family_closure["families"])
