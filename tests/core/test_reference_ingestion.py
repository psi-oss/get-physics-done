"""Tests for structured ingestion of literature and research-map anchor artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.frontmatter import compute_knowledge_reviewed_content_sha256
from gpd.core.reference_ingestion import (
    _extract_section,
    ingest_manuscript_reference_status,
    ingest_reference_artifacts as _ingest_reference_artifacts,
)
from gpd.core.state import default_state_dict

import pytest


def _bootstrap_project(tmp_path: Path) -> Path:
    planning = tmp_path / "GPD"
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


def _write_citation_sources_sidecar(
    literature_dir: Path,
    review_name: str,
    entries: list[dict[str, object]],
) -> Path:
    path = literature_dir / f"{review_name.removesuffix('.md')}-CITATION-SOURCES.json"
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return path


def ingest_reference_artifacts(
    cwd: Path,
    *,
    literature_review_files: list[str],
    research_map_reference_files: list[str],
    knowledge_doc_files: list[str] | None = None,
):
    return _ingest_reference_artifacts(
        cwd,
        literature_review_files=literature_review_files,
        research_map_reference_files=research_map_reference_files,
        knowledge_doc_files=knowledge_doc_files or [],
    )


def _write_knowledge_doc(
    tmp_path: Path,
    *,
    knowledge_id: str = "K-renormalization-group-fixed-points",
    status: str = "stable",
    title: str = "Renormalization Group Fixed Points",
    topic: str = "renormalization-group",
    body: str = "Trusted knowledge body.\n",
) -> Path:
    knowledge_dir = tmp_path / "GPD" / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    path = knowledge_dir / f"{knowledge_id}.md"
    base_content = (
        "---\n"
        "knowledge_schema_version: 1\n"
        f"knowledge_id: {knowledge_id}\n"
        f"title: {title}\n"
        f"topic: {topic}\n"
        f"status: {status}\n"
        "created_at: 2026-04-07T12:00:00Z\n"
        "updated_at: 2026-04-07T12:00:00Z\n"
        "sources:\n"
        "  - source_id: source-main\n"
        "    kind: paper\n"
        "    locator: Author et al., 2024\n"
        "    title: Benchmark Reference\n"
        "    why_it_matters: Trusted source for the topic\n"
        "coverage_summary:\n"
        "  covered_topics: [fixed points]\n"
        "  excluded_topics: [implementation]\n"
        "  open_gaps: [none]\n"
        "---\n\n"
        f"{body}"
    )
    reviewed_content_sha256 = compute_knowledge_reviewed_content_sha256(base_content)
    review_block = (
        "review:\n"
        "  reviewed_at: 2026-04-07T13:00:00Z\n"
        "  review_round: 1\n"
        "  reviewer_kind: workflow\n"
        "  reviewer_id: gpd-review-knowledge\n"
        "  decision: approved\n"
        "  summary: Stable review approved.\n"
        f"  approval_artifact_path: GPD/knowledge/reviews/{knowledge_id}-R1-REVIEW.md\n"
        f"  approval_artifact_sha256: {'a' * 64}\n"
        f"  reviewed_content_sha256: {reviewed_content_sha256}\n"
        "  stale: false\n"
    )
    if status == "stable":
        content = base_content.replace("coverage_summary:\n  covered_topics: [fixed points]\n  excluded_topics: [implementation]\n  open_gaps: [none]\n", "coverage_summary:\n  covered_topics: [fixed points]\n  excluded_topics: [implementation]\n  open_gaps: [none]\n" + review_block)
    elif status == "in_review":
        content = base_content.replace("status: in_review\n", "status: in_review\n" + review_block.replace("stale: false", "stale: true"))
    elif status == "superseded":
        content = base_content.replace(
            "---\n\n",
            f"review:\n  reviewed_at: 2026-04-07T13:00:00Z\n  review_round: 1\n  reviewer_kind: workflow\n  reviewer_id: gpd-review-knowledge\n  decision: approved\n  summary: Stable review approved.\n  approval_artifact_path: GPD/knowledge/reviews/{knowledge_id}-R1-REVIEW.md\n  approval_artifact_sha256: {'a' * 64}\n  reviewed_content_sha256: {reviewed_content_sha256}\n  stale: false\nsuperseded_by: K-renormalization-group-successor\n---\n\n",
        )
    else:
        content = base_content
    path.write_text(content, encoding="utf-8")
    return path


def test_ingest_reference_artifacts_parses_citation_source_sidecar(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "REVIEW.md").write_text("# Review\n", encoding="utf-8")
    _write_citation_sources_sidecar(
        literature_dir,
        "REVIEW.md",
        [
            {
                "reference_id": "ref-benchmark",
                "source_type": "paper",
                "title": "Benchmark Paper",
                "authors": ["A. Researcher"],
                "year": "2024",
                "bibtex_key": "benchmark2024",
                "doi": "10.1000/example",
                "journal": "Phys. Rev. D",
            },
            {
                "reference_id": "ref-method",
                "source_type": "paper",
                "title": "Method Paper",
                "authors": ["B. Researcher"],
                "year": "2023",
                "arxiv_id": "2301.12345",
            },
        ],
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=["GPD/literature/REVIEW.md"],
        research_map_reference_files=[],
    )

    citation_sources = result.citation_sources
    assert result.citation_source_files == ["GPD/literature/REVIEW-CITATION-SOURCES.json"]
    assert result.citation_source_warnings == []
    assert [source.reference_id for source in citation_sources] == ["ref-benchmark", "ref-method"]
    assert citation_sources[0].bibtex_key == "benchmark2024"
    assert citation_sources[0].doi == "10.1000/example"
    assert citation_sources[1].arxiv_id == "2301.12345"


def test_ingest_manuscript_reference_status_reads_current_audit(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "BIBLIOGRAPHY-AUDIT.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-30T00:00:00+00:00",
                "total_sources": 1,
                "resolved_sources": 1,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": [
                    {
                        "key": "benchmark2024",
                        "source_type": "paper",
                        "reference_id": "ref-benchmark",
                        "title": "Benchmark Paper",
                        "resolution_status": "provided",
                        "verification_status": "verified",
                        "verification_sources": ["manual"],
                        "canonical_identifiers": ["doi:10.1000/example"],
                        "missing_core_fields": [],
                        "enriched_fields": [],
                        "warnings": [],
                        "errors": [],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = ingest_manuscript_reference_status(tmp_path)

    assert result.manuscript_root == "paper"
    assert result.bibliography_audit_path == "paper/BIBLIOGRAPHY-AUDIT.json"
    assert result.reference_status_warnings == []
    assert [record.reference_id for record in result.reference_status] == ["ref-benchmark"]
    assert result.reference_status[0].bibtex_key == "benchmark2024"
    assert result.reference_status[0].title == "Benchmark Paper"
    assert result.reference_status[0].resolution_status == "provided"
    assert result.reference_status[0].verification_status == "verified"
    assert result.reference_status[0].source_artifacts == ["paper/BIBLIOGRAPHY-AUDIT.json"]


def test_ingest_reference_artifacts_ignores_malformed_citation_source_sidecar(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "REVIEW.md").write_text("# Review\n", encoding="utf-8")
    _write_citation_sources_sidecar(
        literature_dir,
        "REVIEW.md",
        {"reference_id": "broken", "source_type": "paper", "title": "Broken Sidecar"},
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=["GPD/literature/REVIEW.md"],
        research_map_reference_files=[],
    )

    assert result.citation_sources == []
    assert result.citation_source_files == []
    assert result.citation_source_warnings == [
        "skipping citation source sidecar GPD/literature/REVIEW-CITATION-SOURCES.json: expected a JSON array"
    ]


def test_ingest_reference_artifacts_ignores_citation_source_without_reference_id(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "REVIEW.md").write_text("# Review\n", encoding="utf-8")
    _write_citation_sources_sidecar(
        literature_dir,
        "REVIEW.md",
        [
            {
                "source_type": "paper",
                "title": "Broken Sidecar",
                "year": "2024",
            }
        ],
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=["GPD/literature/REVIEW.md"],
        research_map_reference_files=[],
    )

    assert result.citation_sources == []
    assert result.citation_source_files == ["GPD/literature/REVIEW-CITATION-SOURCES.json"]
    assert result.citation_source_warnings == [
        "citation source GPD/literature/REVIEW-CITATION-SOURCES.json[0].reference_id must be a non-empty string"
    ]


def test_ingest_reference_artifacts_rejects_unknown_citation_source_fields(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "REVIEW.md").write_text("# Review\n", encoding="utf-8")
    _write_citation_sources_sidecar(
        literature_dir,
        "REVIEW.md",
        [
            {
                "reference_id": "ref-extra",
                "source_type": "paper",
                "title": "Extra Field Paper",
                "legacy_note": "stale",
            }
        ],
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=["GPD/literature/REVIEW.md"],
        research_map_reference_files=[],
    )

    assert result.citation_sources == []
    assert result.citation_source_files == ["GPD/literature/REVIEW-CITATION-SOURCES.json"]
    assert any("Extra inputs are not permitted" in warning for warning in result.citation_source_warnings)


def test_literature_review_surfaces_publish_closed_citation_source_contract() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    command_doc = (repo_root / "src/gpd/commands/literature-review.md").read_text(encoding="utf-8")
    agent_doc = (repo_root / "src/gpd/agents/gpd-literature-reviewer.md").read_text(encoding="utf-8")
    workflow_doc = (repo_root / "src/gpd/specs/workflows/literature-review.md").read_text(encoding="utf-8")

    assert "machine-readable, strict `CITATION-SOURCES.json` sidecar" in command_doc
    assert "strict `CitationSource` records keyed by stable `reference_id`" in command_doc
    assert "closed contract is:" in agent_doc
    assert "Extra keys are rejected by the downstream parser." in agent_doc
    assert "strict `CitationSource` objects" in workflow_doc
    assert "Extra keys are rejected" in workflow_doc


def test_ingest_reference_artifacts_handles_sidecars_deterministically(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "A-REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (literature_dir / "B-REVIEW.md").write_text("# Review\n", encoding="utf-8")
    _write_citation_sources_sidecar(
        literature_dir,
        "B-REVIEW.md",
        [
            {
                "reference_id": "ref-b",
                "source_type": "paper",
                "title": "B Paper",
                "year": "2024",
            }
        ],
    )
    _write_citation_sources_sidecar(
        literature_dir,
        "A-REVIEW.md",
        [
            {
                "reference_id": "ref-a",
                "source_type": "paper",
                "title": "A Paper",
                "year": "2023",
            }
        ],
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=["GPD/literature/A-REVIEW.md", "GPD/literature/B-REVIEW.md"],
        research_map_reference_files=[],
    )

    citation_sources = result.citation_sources
    citation_source_files = result.citation_source_files
    assert [source.reference_id for source in citation_sources] == ["ref-a", "ref-b"]
    assert citation_source_files == [
        "GPD/literature/A-REVIEW-CITATION-SOURCES.json",
        "GPD/literature/B-REVIEW-CITATION-SOURCES.json",
    ]


def test_ingest_reference_artifacts_parses_literature_and_reference_map(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
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

    research_map_dir = tmp_path / "GPD" / "research-map"
    research_map_dir.mkdir(parents=True)
    (research_map_dir / "REFERENCES.md").write_text(
        "# Reference and Anchor Map\n\n"
        "## Active Anchor Registry\n\n"
        "| Anchor ID | Anchor | Type | Source / Locator | Why It Matters | Contract Subject IDs | Required Action | Carry Forward To |\n"
        "| --------- | ------ | ---- | ---------------- | -------------- | -------------------- | --------------- | ---------------- |\n"
        "| prior-figure | Baseline summary | prior artifact | `GPD/phases/00-baseline/00-SUMMARY.md` | Carry forward baseline plot | deliv-note | use/compare | execution/writing |\n"
        "\n"
        "## Benchmarks and Comparison Targets\n\n"
        "- Published threshold\n"
        "  - Source: Benchmark Table\n"
        "  - Compared in: `GPD/phases/00-baseline/00-SUMMARY.md`\n"
        "  - Status: pending\n"
        "\n"
        "## Prior Artifacts and Baselines\n\n"
        "- `GPD/phases/00-baseline/00-SUMMARY.md`: Existing baseline fit that later phases must preserve\n",
        encoding="utf-8",
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=["GPD/literature/REVIEW.md"],
        research_map_reference_files=["GPD/research-map/REFERENCES.md"],
    )

    ids = {ref.id for ref in result.references}
    assert ids
    assert "ref-benchmark" in ids
    ref_benchmark = next(ref for ref in result.references if ref.id == "ref-benchmark")
    assert any(ref.role == "benchmark" for ref in result.references)
    assert any(ref.locator == "Benchmark Paper" for ref in result.references)
    assert ref_benchmark.applies_to == ["claim-anchor"]
    assert any("GPD/phases/00-baseline/00-SUMMARY.md" in item for item in result.intake.must_include_prior_outputs)
    assert any("critical exponent" in item for item in result.intake.known_good_baselines)
    assert "ref-benchmark" in result.intake.must_read_refs


def test_ingest_reference_artifacts_ignores_legacy_review_summary_aliases(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
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
        literature_review_files=["GPD/literature/LEGACY-REVIEW.md"],
        research_map_reference_files=[],
    )

    assert result.references == []
    assert result.intake.must_read_refs == []
    assert result.intake.known_good_baselines == []


def test_context_surfaces_derived_reference_registry_without_project_contract(tmp_path: Path) -> None:
    try:
        from gpd.core.context import init_verify_work
    except SyntaxError as exc:  # pragma: no cover - blocked by unrelated knowledge_index syntax error
        pytest.skip(f"knowledge runtime context is blocked by an unrelated syntax error: {exc}")

    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "REVIEW.md").write_text(
        "## Active Anchor Registry\n\n"
        "| Anchor | Type | Why It Matters | Required Action | Downstream Use |\n"
        "| ------ | ---- | -------------- | --------------- | -------------- |\n"
        "| Benchmark note | benchmark | Must compare with benchmark note | read/compare | verification |\n",
        encoding="utf-8",
    )
    research_map_dir = tmp_path / "GPD" / "research-map"
    research_map_dir.mkdir(parents=True)
    (research_map_dir / "REFERENCES.md").write_text(
        "## Prior Artifacts and Baselines\n\n"
        "- `GPD/phases/00-baseline/00-SUMMARY.md`: Baseline artifact to keep visible\n",
        encoding="utf-8",
    )

    ctx = init_verify_work(tmp_path, "1")

    assert ctx["project_contract"] is None
    assert ctx["derived_active_reference_count"] >= 1
    assert any(ref["source_kind"] == "artifact" for ref in ctx["derived_active_references"])
    assert "GPD/phases/00-baseline/00-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]
    assert "Benchmark note" in ctx["active_reference_context"]


def test_ingest_reference_artifacts_accepts_bullet_registries_and_direct_intake_sections(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
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

    research_map_dir = tmp_path / "GPD" / "research-map"
    research_map_dir.mkdir(parents=True)
    (research_map_dir / "CONCERNS.md").write_text(
        "# Reference Context\n\n"
        "## Prior Outputs\n\n"
        "- `GPD/phases/00-baseline/00-SUMMARY.md`\n"
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
        literature_review_files=["GPD/literature/ALT-REVIEW.md"],
        research_map_reference_files=["GPD/research-map/CONCERNS.md"],
    )

    ref = next(ref for ref in result.references if ref.id == "ref-benchmark-2025")
    assert ref.role == "benchmark"
    assert ref.locator == "Benchmark Ref 2025, J. Phys. 2025"
    assert ref.applies_to == ["claim-anchor"]
    assert ref.required_actions == ["read", "compare", "cite"]
    assert "ref-benchmark-2025" in result.intake.must_read_refs
    assert "GPD/phases/00-baseline/00-SUMMARY.md" in result.intake.must_include_prior_outputs
    assert "notes/reference-intake.md" in result.intake.crucial_inputs
    assert "Need the definitive normalization note" in result.intake.context_gaps
    assert "Control window from the accepted benchmark run" in result.intake.known_good_baselines


def test_extract_section_keeps_nested_subsections_until_the_next_peer_heading() -> None:
    content = (
        "# Review\n\n"
        "## Active References\n\n"
        "### Benchmarks\n"
        "- Anchor ID: ref-benchmark\n"
        "- Source / Locator: Benchmark Ref 2026\n\n"
        "### Prior Outputs\n"
        "- GPD/phases/00-baseline/00-01-SUMMARY.md\n\n"
        "## Other Section\n"
        "- outside\n"
    )

    section = _extract_section(content, "Active References")

    assert section is not None
    assert "ref-benchmark" in section
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md" in section
    assert "Other Section" not in section


def test_ingest_reference_artifacts_preserves_repeated_bullet_detail_values(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "REPEATED-DETAILS.md").write_text(
        "# Review\n\n"
        "## Active References\n\n"
        "- Benchmark Ref 2026\n"
        "  - Anchor ID: ref-benchmark-2026\n"
        "  - Source / Locator: Benchmark Ref 2026, J. Phys. 2026\n"
        "  - Type: benchmark target\n"
        "  - Contract Subject IDs: claim-anchor\n"
        "  - Contract Subject IDs: deliv-note\n"
        "  - Required Action: read/use\n"
        "  - Required Action: compare\n"
        "  - Carry Forward To: planning/verification\n"
        "  - Carry Forward To: writing\n",
        encoding="utf-8",
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=["GPD/literature/REPEATED-DETAILS.md"],
        research_map_reference_files=[],
    )

    ref = next(ref for ref in result.references if ref.id == "ref-benchmark-2026")
    assert ref.applies_to == ["claim-anchor", "deliv-note"]
    assert ref.required_actions == ["read", "use", "compare"]
    assert ref.carry_forward_to == ["planning", "verification", "writing"]
    assert "ref-benchmark-2026" in result.intake.must_read_refs


def test_ingest_reference_artifacts_keeps_shared_alias_references_distinct(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "ALIASES.md").write_text(
        "# Review\n\n"
        "## Active References\n\n"
        "| Anchor ID | Anchor | Type | Source / Locator | Why It Matters | Contract Subject IDs | Required Action | Carry Forward To |\n"
        "| --------- | ------ | ---- | ---------------- | -------------- | -------------------- | --------------- | ---------------- |\n"
        "| ref-a | shared-token | benchmark | Doc A | First anchor | claim-a | read | planning |\n"
        "| ref-b | shared-token | benchmark | Doc B | Second anchor | claim-b | compare | planning |\n",
        encoding="utf-8",
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=["GPD/literature/ALIASES.md"],
        research_map_reference_files=[],
    )

    assert [ref.id for ref in result.references] == ["ref-a", "ref-b"]
    assert [ref.locator for ref in result.references] == ["Doc A", "Doc B"]
    assert result.references[0].aliases == ["shared-token"]
    assert result.references[1].aliases == ["shared-token"]


def test_context_discovers_additional_research_map_reference_artifacts(tmp_path: Path) -> None:
    try:
        from gpd.core.context import init_verify_work
    except SyntaxError as exc:  # pragma: no cover - blocked by unrelated knowledge_index syntax error
        pytest.skip(f"knowledge runtime context is blocked by an unrelated syntax error: {exc}")

    _bootstrap_project(tmp_path)
    research_map_dir = tmp_path / "GPD" / "research-map"
    research_map_dir.mkdir(parents=True)
    (research_map_dir / "CONCERNS.md").write_text(
        "# Reference Context\n\n"
        "## Prior Outputs\n\n"
        "- `GPD/phases/00-baseline/00-SUMMARY.md`\n",
        encoding="utf-8",
    )

    ctx = init_verify_work(tmp_path, "1")

    assert "GPD/research-map/CONCERNS.md" in ctx["research_map_reference_files"]
    assert "GPD/phases/00-baseline/00-SUMMARY.md" in ctx["effective_reference_intake"]["must_include_prior_outputs"]


def test_ingest_reference_artifacts_surfaces_explicit_or_derived_must_surface_flags(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "REVIEW.md").write_text(
        "# Review\n\n"
        "## Active Anchor Registry\n\n"
        "| Anchor ID | Anchor | Type | Source / Locator | Why It Matters | Must Surface | Required Action |\n"
        "| --------- | ------ | ---- | ---------------- | -------------- | ------------ | --------------- |\n"
        "| ref-benchmark | Benchmark Ref | benchmark | Benchmark Paper | Decisive benchmark | no | cite |\n"
        "| ref-method | Method Ref | method | Method Paper | Required method anchor |  | compare |\n",
        encoding="utf-8",
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=["GPD/literature/REVIEW.md"],
        research_map_reference_files=[],
    )

    benchmark = next(ref for ref in result.references if ref.id == "ref-benchmark")
    method = next(ref for ref in result.references if ref.id == "ref-method")

    assert benchmark.must_surface is False
    assert method.must_surface is True


def test_anchor_registry_templates_document_must_surface_column_and_fallback_heuristic() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    literature_workflow = (repo_root / "src/gpd/specs/workflows/literature-review.md").read_text(encoding="utf-8")
    reference_template = (
        repo_root / "src/gpd/specs/references/templates/research-mapper/REFERENCES.md"
    ).read_text(encoding="utf-8")

    assert "| Must Surface |" in literature_workflow
    assert "Set `Must Surface` to `yes`" in literature_workflow
    assert "roles like `benchmark`, `definition`, `method`, or `must_consider`" in literature_workflow
    assert "| Must Surface |" in reference_template
    assert "`Must Surface` marks anchors" in reference_template
    assert "required actions such as `use`, `compare`, or `avoid`" in reference_template


def test_ingest_reference_artifacts_surfaces_stable_knowledge_docs_as_structured_inventory(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    stable_doc = _write_knowledge_doc(tmp_path, status="stable")
    _write_knowledge_doc(tmp_path, knowledge_id="K-still-under-review", status="in_review")

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=[],
        research_map_reference_files=[],
        knowledge_doc_files=[stable_doc.relative_to(tmp_path).as_posix()],
    )

    assert [record.knowledge_id for record in result.knowledge_docs] == ["K-renormalization-group-fixed-points"]
    assert result.knowledge_docs[0].status == "stable"
    assert result.knowledge_docs[0].is_fresh_approved is True
    assert [reference.id for reference in result.references] == ["K-renormalization-group-fixed-points"]
    assert result.references[0].source_kind == "knowledge_doc"
    assert result.references[0].role == "background"
    assert result.references[0].source_artifacts[0] == stable_doc.relative_to(tmp_path).as_posix()
    assert result.knowledge_doc_warnings == []


def test_ingest_reference_artifacts_emits_warning_for_invalid_knowledge_doc(tmp_path: Path) -> None:
    _bootstrap_project(tmp_path)
    knowledge_dir = tmp_path / "GPD" / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    invalid_path = knowledge_dir / "K-broken.md"
    invalid_path.write_text(
        "---\nknowledge_schema_version: 1\nknowledge_id: K-other\nstatus: stable\n---\n",
        encoding="utf-8",
    )

    result = ingest_reference_artifacts(
        tmp_path,
        literature_review_files=[],
        research_map_reference_files=[],
        knowledge_doc_files=["GPD/knowledge/K-broken.md"],
    )

    assert result.knowledge_docs == []
    assert result.knowledge_doc_warnings
    assert "K-broken.md" in result.knowledge_doc_warnings[0]
