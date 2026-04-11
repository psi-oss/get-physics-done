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

    assert phase_rows["10"]["status"] == "covered_subset_post_fix_copy_runs_green_not_promoted"
    assert phase_rows["10"]["strict_phase10_exit_criteria_met"] is False
    assert phase_rows["10"]["post_fix_copy_run_criteria_met"] is True
    assert phase_rows["18"]["status"] == "local_closure_evidence_green_not_closed"

    for filename in (
        "repro-funnel.json",
        "surface-parity.json",
        "checkpoint-board.json",
        "benchmarks.json",
        "family-closure.json",
        "local-closure-runs.json",
    ):
        assert (SCORECARD_ROOT / filename).exists()

    family_closure = json.loads((SCORECARD_ROOT / "family-closure.json").read_text(encoding="utf-8"))
    assert family_closure["closed_phase15_family_count"] < family_closure["phase15_family_count"]
    assert all(not family["closed"] for family in family_closure["families"])
    assert all(family["local_closure_evidence_all_green"] for family in family_closure["families"])
    assert all(family["unconverted_manual_repro_count"] == 1041 for family in family_closure["families"])


def test_bug_campaign_phase10_reconstruction_is_fixture_covered_subset_only() -> None:
    summary = json.loads((CAMPAIGN_ROOT / "repro" / "10-wave-summary.json").read_text(encoding="utf-8"))

    assert summary["reconstruction_scope"] == "checked_in_fixture_covered_subset"
    assert summary["strict_phase10_exit_criteria_met"] is False
    assert summary["post_fix_copy_run_criteria_met"] is True
    assert summary["status"] == "covered_subset_post_fix_copy_runs_green_not_promoted"
    assert summary["family_count"] == 5
    assert summary["post_fix_copy_run_evidence"]["green_family_count"] == 5

    for family in summary["families"]:
        assert family["promotion_status"] == "not_promoted_partial_reconstruction"
        assert family["expected_pytest_pass_count"] > 0
        assert (CAMPAIGN_ROOT / family["oracle_path"]).exists()
        assert (CAMPAIGN_ROOT / family["script_path"]).exists()
        assert (CAMPAIGN_ROOT / family["transcript_path"]).exists()

    query_oracle = json.loads(
        (CAMPAIGN_ROOT / "repro" / "10-oracles" / "query-vs-result-blindness.json").read_text(encoding="utf-8")
    )
    assert query_oracle["closed_gaps"][0]["class"] == "closed-by-result-registry-projection"
    assert query_oracle["expected_pytest_pass_count"] == 6
    assert query_oracle["phase10_exit_criteria"]["strict_phase10_criteria_met"] is False

    copy_run_evidence = json.loads((CAMPAIGN_ROOT / "repro" / "10-copy-run-evidence.json").read_text(encoding="utf-8"))
    assert copy_run_evidence["post_fix_copy_run_criteria_met"] is True
    assert {family["green_run_count"] for family in copy_run_evidence["families"]} == {3}

    phase_oracle = json.loads(
        (CAMPAIGN_ROOT / "repro" / "10-oracles" / "phase-content-blindness.json").read_text(encoding="utf-8")
    )
    assert phase_oracle["known_gaps"] == []
    assert phase_oracle["accepted_gaps"][0]["class"] == "accepted-by-phase-read-model-alignment-contract"

    surface_parity = json.loads((SCORECARD_ROOT / "surface-parity.json").read_text(encoding="utf-8"))
    assert surface_parity["allowlisted_diff_count"] == 6
    assert surface_parity["unexpected_diff_count"] == 0
