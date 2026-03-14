"""Tests for structured ingestion of literature and research-map anchor artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.context import init_verify_work
from gpd.core.reference_ingestion import ingest_reference_artifacts
from gpd.core.state import default_state_dict


def _bootstrap_project(tmp_path: Path) -> Path:
    planning = tmp_path / ".gpd"
    planning.mkdir()
    (planning / "state.json").write_text(json.dumps(default_state_dict(), indent=2), encoding="utf-8")
    (planning / "PROJECT.md").write_text("# Project\n\n## Core Research Question\nWhat matters?\n", encoding="utf-8")
    phase_dir = planning / "phases" / "01-demo"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        "---\n"
        "phase: 01\n"
        "plan: 01\n"
        "type: execute\n"
        "depth: full\n"
        "wave: 1\n"
        "status: ready\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "contract:\n"
        "  scope:\n"
        "    question: What benchmark anchor must remain visible during verification?\n"
        "  claims:\n"
        "    - id: claim-anchor\n"
        "      statement: Keep the decisive benchmark and prior baseline in scope during verification.\n"
        "      deliverables: [deliv-note]\n"
        "      acceptance_tests: [test-anchor]\n"
        "  deliverables:\n"
        "    - id: deliv-note\n"
        "      kind: note\n"
        "      path: notes/anchor-context.md\n"
        "      description: Note capturing the benchmark and carry-forward baseline.\n"
        "  acceptance_tests:\n"
        "    - id: test-anchor\n"
        "      subject: claim-anchor\n"
        "      kind: human_review\n"
        "      procedure: Confirm that the benchmark anchor and prior artifact are both surfaced before verification.\n"
        "      pass_condition: The verification context names the decisive benchmark and baseline artifact.\n"
        "      evidence_required: [deliv-note]\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Benchmark source still needs to be read in full]\n"
        "    disconfirming_observations: [Verification proceeds without naming the decisive benchmark]\n"
        "---\n\n# Plan\n",
        encoding="utf-8",
    )
    return tmp_path


def test_ingest_reference_artifacts_parses_literature_and_reference_map(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / ".gpd" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "REVIEW.md").write_text(
        "# Review\n\n"
        "## Active Anchor Registry\n\n"
        "| Anchor ID | Anchor | Type | Source / Locator | Why It Matters | Contract Subject IDs | Required Action | Carry Forward To |\n"
        "| --------- | ------ | ---- | ---------------- | -------------- | -------------------- | --------------- | ---------------- |\n"
        "| ref-benchmark | Ref Benchmark | benchmark | Benchmark Paper | Decisive benchmark | claim-anchor | read/use/compare | planning/verification |\n"
        "\n"
        "```yaml\n"
        "---\n"
        "review_summary:\n"
        "  active_anchors:\n"
        "    - anchor_id: \"ref-benchmark\"\n"
        "      anchor: \"Ref Benchmark\"\n"
        "      locator: \"Benchmark Paper\"\n"
        "      type: \"benchmark\"\n"
        "      why_it_matters: \"Decisive benchmark\"\n"
        "      contract_subject_ids: [\"claim-anchor\"]\n"
        "      required_action: \"read/use/compare\"\n"
        "      carry_forward_to: \"planning/verification\"\n"
        "  benchmark_values:\n"
        "    - quantity: \"critical exponent\"\n"
        "      value: \"1.23\"\n"
        "      source: \"Benchmark Paper\"\n"
        "---\n"
        "```\n",
        encoding="utf-8",
    )

    research_map_dir = tmp_path / ".gpd" / "research-map"
    research_map_dir.mkdir(parents=True)
    (research_map_dir / "REFERENCES.md").write_text(
        "# Reference and Anchor Map\n\n"
        "## Active Anchor Registry\n\n"
        "| Anchor ID | Anchor | Type | Source / Locator | Why It Matters | Contract Subject IDs | Required Action | Carry Forward To |\n"
        "| --------- | ------ | ---- | ---------------- | -------------- | -------------------- | --------------- | ---------------- |\n"
        "| prior-figure | Baseline summary | prior artifact | `.gpd/phases/00-baseline/00-SUMMARY.md` | Carry forward baseline plot | deliv-note | use/compare | execution/writing |\n"
        "\n"
        "## Benchmarks and Comparison Targets\n\n"
        "- Published threshold\n"
        "  - Source: Benchmark Table\n"
        "  - Compared in: `.gpd/phases/00-baseline/00-SUMMARY.md`\n"
        "  - Status: pending\n"
        "\n"
        "## Prior Artifacts and Baselines\n\n"
        "- `.gpd/phases/00-baseline/00-SUMMARY.md`: Existing baseline fit that later phases must preserve\n",
        encoding="utf-8",
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=[".gpd/literature/REVIEW.md"],
        research_map_reference_files=[".gpd/research-map/REFERENCES.md"],
    )

    ids = {ref.id for ref in result.references}
    assert ids
    assert "ref-benchmark" in ids
    assert any(ref.role == "benchmark" for ref in result.references)
    assert any(ref.locator == "Benchmark Paper" for ref in result.references)
    assert any(".gpd/phases/00-baseline/00-SUMMARY.md" in item for item in result.intake.must_include_prior_outputs)
    assert any("critical exponent" in item for item in result.intake.known_good_baselines)
    assert "ref-benchmark" in result.intake.must_read_refs


def test_ingest_reference_artifacts_ignores_legacy_review_summary_aliases(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / ".gpd" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "LEGACY-REVIEW.md").write_text(
        "# Review\n\n"
        "```yaml\n"
        "---\n"
        "review_summary:\n"
        "  active_references:\n"
        "    - anchor_id: \"ref-legacy\"\n"
        "      anchor: \"Legacy Benchmark\"\n"
        "      locator: \"Legacy Paper\"\n"
        "      type: \"benchmark\"\n"
        "  known_good_baselines:\n"
        "    - \"critical exponent — 1.23 — source: Legacy Paper\"\n"
        "  must_read_references: [\"ref-legacy\"]\n"
        "---\n"
        "```\n",
        encoding="utf-8",
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=[".gpd/literature/LEGACY-REVIEW.md"],
        research_map_reference_files=[],
    )

    assert result.references == []
    assert result.intake.must_read_refs == []
    assert result.intake.known_good_baselines == []


def test_context_surfaces_derived_reference_registry_without_project_contract(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / ".gpd" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "REVIEW.md").write_text(
        "## Active Anchor Registry\n\n"
        "| Anchor | Type | Why It Matters | Required Action | Downstream Use |\n"
        "| ------ | ---- | -------------- | --------------- | -------------- |\n"
        "| Benchmark note | benchmark | Must compare with benchmark note | read/compare | verification |\n",
        encoding="utf-8",
    )
    research_map_dir = tmp_path / ".gpd" / "research-map"
    research_map_dir.mkdir(parents=True)
    (research_map_dir / "REFERENCES.md").write_text(
        "## Prior Artifacts and Baselines\n\n"
        "- `.gpd/phases/00-baseline/00-SUMMARY.md`: Baseline artifact to keep visible\n",
        encoding="utf-8",
    )

    ctx = init_verify_work(tmp_path, "1")

    assert ctx["project_contract"] is None
    assert ctx["derived_active_reference_count"] >= 1
    assert any(ref["source_kind"] == "artifact" for ref in ctx["derived_active_references"])
    assert ".gpd/phases/00-baseline/00-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]
    assert "Benchmark note" in ctx["active_reference_context"]


def test_ingest_reference_artifacts_accepts_bullet_registries_and_direct_intake_sections(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / ".gpd" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "ALT-REVIEW.md").write_text(
        "# Review\n\n"
        "## Active References\n\n"
        "- Benchmark Ref 2025\n"
        "  - Anchor ID: ref-benchmark-2025\n"
        "  - Source / Locator: Benchmark Ref 2025, J. Phys. 2025\n"
        "  - Type: benchmark target\n"
        "  - Why It Matters: Decisive comparison target\n"
        "  - Contract Subject IDs: claim-anchor\n"
        "  - Required Actions: review/compare/reference\n"
        "  - Carry Forward To: planning/verification\n"
        "\n"
        "## Must Read References\n\n"
        "- ref-benchmark-2025\n"
        "\n"
        "## Context Gaps\n\n"
        "- Need the definitive normalization note\n",
        encoding="utf-8",
    )

    research_map_dir = tmp_path / ".gpd" / "research-map"
    research_map_dir.mkdir(parents=True)
    (research_map_dir / "CONCERNS.md").write_text(
        "# Reference Context\n\n"
        "## Prior Outputs\n\n"
        "- `.gpd/phases/00-baseline/00-SUMMARY.md`\n"
        "\n"
        "## Known Good Baselines\n\n"
        "- Control window from the accepted benchmark run\n"
        "\n"
        "## Critical Inputs\n\n"
        "- `notes/reference-intake.md`\n",
        encoding="utf-8",
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=[".gpd/literature/ALT-REVIEW.md"],
        research_map_reference_files=[".gpd/research-map/CONCERNS.md"],
    )

    ref = next(ref for ref in result.references if ref.id == "ref-benchmark-2025")
    assert ref.role == "benchmark"
    assert ref.locator == "Benchmark Ref 2025, J. Phys. 2025"
    assert ref.required_actions == ["read", "compare", "cite"]
    assert "ref-benchmark-2025" in result.intake.must_read_refs
    assert ".gpd/phases/00-baseline/00-SUMMARY.md" in result.intake.must_include_prior_outputs
    assert "notes/reference-intake.md" in result.intake.crucial_inputs
    assert "Need the definitive normalization note" in result.intake.context_gaps
    assert "Control window from the accepted benchmark run" in result.intake.known_good_baselines


def test_context_discovers_additional_research_map_reference_artifacts(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    research_map_dir = tmp_path / ".gpd" / "research-map"
    research_map_dir.mkdir(parents=True)
    (research_map_dir / "CONCERNS.md").write_text(
        "# Reference Context\n\n"
        "## Prior Outputs\n\n"
        "- `.gpd/phases/00-baseline/00-SUMMARY.md`\n",
        encoding="utf-8",
    )

    ctx = init_verify_work(tmp_path, "1")

    assert ".gpd/research-map/CONCERNS.md" in ctx["research_map_reference_files"]
    assert ".gpd/phases/00-baseline/00-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]
