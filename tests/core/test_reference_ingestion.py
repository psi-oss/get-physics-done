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
        "---\nphase: 01\nplan: 01\ndepth: full\nwave: 1\nstatus: ready\nmust_haves: {}\n---\n\n# Plan\n",
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
        "| Anchor | Type | Why It Matters | Required Action | Downstream Use |\n"
        "| ------ | ---- | -------------- | --------------- | -------------- |\n"
        "| Ref Benchmark | benchmark | Decisive benchmark | read/use/compare | planning/verification |\n"
        "\n"
        "```yaml\n"
        "---\n"
        "review_summary:\n"
        "  active_anchors:\n"
        "    - anchor: \"Ref Benchmark\"\n"
        "      type: \"benchmark\"\n"
        "      why_it_matters: \"Decisive benchmark\"\n"
        "      required_action: \"read/use/compare\"\n"
        "      downstream_use: \"planning/verification\"\n"
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
        "| Anchor | Type | Source / Locator | What It Constrains | Required Action | Carry Forward To |\n"
        "| ------ | ---- | ---------------- | ------------------ | --------------- | ---------------- |\n"
        "| prior-figure | prior artifact | `.gpd/phases/00-baseline/00-SUMMARY.md` | Carry forward baseline plot | use/compare | execution/writing |\n"
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
    assert any(ref.role == "benchmark" for ref in result.references)
    assert any(".gpd/phases/00-baseline/00-SUMMARY.md" in item for item in result.intake.must_include_prior_outputs)
    assert any("critical exponent" in item for item in result.intake.known_good_baselines)
    assert any("Ref Benchmark" in item for item in result.intake.must_read_refs)


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
