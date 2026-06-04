"""Tests for deterministic ``gpd:ideate`` blackboard artifacts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from gpd.core.constants import BLACKBOARDS_DIR_NAME, IDEATE_FILE_PREFIX, ProjectLayout
from gpd.core.frontmatter import extract_frontmatter
from gpd.core.ideate_blackboard import (
    BlackboardUpdate,
    TranscriptTurn,
    allocate_ideate_session,
    append_transcript_turn,
    initialize_ideate_artifacts,
    merge_blackboard_update,
    slugify_ideate_topic,
)
from tests.assertion_taxonomy_support import assert_prompt_contracts, semantic_concept

TODAY = date(2026, 5, 5)


def _meta(path: Path) -> dict:
    metadata, _body = extract_frontmatter(path.read_text(encoding="utf-8"))
    return metadata


def test_ideate_session_paths_are_projectless_date_and_slug_deterministic(tmp_path: Path) -> None:
    session = allocate_ideate_session(tmp_path, "Finite-temperature SYK chaos?", today=TODAY, turn_budget=3)

    assert session.topic_slug == "finite-temperature-syk-chaos"
    assert session.paths.blackboard == tmp_path / "GPD/blackboards/ideate-2026-05-05-finite-temperature-syk-chaos.md"
    assert session.paths.transcript == (
        tmp_path / "GPD/blackboards/ideate-2026-05-05-finite-temperature-syk-chaos-transcript.md"
    )
    assert session.paths.report == tmp_path / "GPD/blackboards/ideate-2026-05-05-finite-temperature-syk-chaos-report.md"
    assert ProjectLayout(tmp_path).blackboards_dir.name == BLACKBOARDS_DIR_NAME
    assert session.paths.blackboard.name.startswith(f"{IDEATE_FILE_PREFIX}-2026-05-05-")
    assert not (tmp_path / "GPD/PROJECT.md").exists()


def test_ideate_slug_has_stable_fallback_for_empty_topic() -> None:
    assert slugify_ideate_topic("?!   ") == "untitled-topic"


def test_ideate_session_paths_are_collision_safe_for_the_whole_trio(tmp_path: Path) -> None:
    first = allocate_ideate_session(tmp_path, "finite temperature", today=TODAY)
    first.paths.transcript.parent.mkdir(parents=True)
    first.paths.transcript.write_text("existing", encoding="utf-8")

    second = allocate_ideate_session(tmp_path, "finite temperature", today=TODAY)

    assert second.session_slug == "finite-temperature-2"
    assert second.paths.blackboard.name == "ideate-2026-05-05-finite-temperature-2.md"
    assert second.paths.transcript.name == "ideate-2026-05-05-finite-temperature-2-transcript.md"
    assert second.paths.report.name == "ideate-2026-05-05-finite-temperature-2-report.md"


def test_initialize_ideate_artifacts_renders_linked_templates(tmp_path: Path) -> None:
    session = allocate_ideate_session(
        tmp_path,
        "Matrix models",
        today=TODAY,
        turn_budget=2,
        source_inputs=["2303.00000", "papers/main.tex"],
        knowledge_docs=["GPD/knowledge/K-001.md"],
        source_manifest={
            "source_manifest": {
                "sources": [
                    {
                        "source_id": "SRC-001",
                        "kind": "arxiv",
                        "input": "2303.00000",
                        "normalized_ref": "2303.00000",
                        "status": "pending",
                        "digest_path": "",
                        "warnings": [],
                    }
                ]
            }
        },
    )

    paths = initialize_ideate_artifacts(session)

    blackboard = _meta(paths.blackboard)
    transcript = _meta(paths.transcript)
    report = _meta(paths.report)
    blackboard_body = paths.blackboard.read_text(encoding="utf-8")

    assert blackboard["blackboard_schema_version"] == 2
    assert blackboard["blackboard_id"] == "BB-20260505-matrix-models"
    assert blackboard["command"] == "gpd:ideate"
    assert blackboard["status"] == "active"
    assert blackboard["turn"] == 0
    assert blackboard["turn_budget"] == 2
    assert {"role": "gpd-ideator"} in blackboard["participants"]
    assert blackboard["related_artifacts"]["transcript"] == "GPD/blackboards/ideate-2026-05-05-matrix-models-transcript.md"
    assert transcript["transcript_schema_version"] == 2
    assert transcript["blackboard_id"] == blackboard["blackboard_id"]
    assert transcript["turn_count"] == 0
    assert report["ideation_report_schema_version"] == 2
    assert report["blackboard_id"] == blackboard["blackboard_id"]
    assert report["related_artifacts"]["blackboard"] == "GPD/blackboards/ideate-2026-05-05-matrix-models.md"
    assert blackboard["source_inputs"] == ["2303.00000", "papers/main.tex"]
    assert report["knowledge_docs"] == ["GPD/knowledge/K-001.md"]
    assert_prompt_contracts(
        blackboard_body,
        *semantic_concept("ideate blackboard source manifest", required=("## Source Manifest", "source_id: SRC-001")),
    )
    assert_prompt_contracts(
        paths.report.read_text(encoding="utf-8"),
        *semantic_concept("ideate report template sections", required="## Ranked Research Questions"),
    )


def test_initialize_ideate_artifacts_replaces_template_placeholders(tmp_path: Path) -> None:
    session = allocate_ideate_session(tmp_path, "BFSS bootstrap", today=TODAY)
    paths = initialize_ideate_artifacts(session)

    for path in paths.all:
        content = path.read_text(encoding="utf-8")
        assert_prompt_contracts(
            content,
            *semantic_concept(
                "ideate template placeholder cleanup",
                forbidden=("{{", "}}", "YYYY-MM-DD", "<topic-slug>"),
            ),
        )


def test_append_transcript_turn_preserves_turn_and_thread_shape(tmp_path: Path) -> None:
    session = allocate_ideate_session(tmp_path, "turns", today=TODAY)
    paths = initialize_ideate_artifacts(session)

    append_transcript_turn(
        paths.transcript,
        TranscriptTurn(
            turn_id="TURN-001",
            thread_id="TH-001",
            entries={"gpd-ideator": "Try a double-scaling question.", "gpd-ideation-critic": "Needs source support."},
            summary="Generator and critic disagreed on evidence strength.",
        ),
        updated=TODAY,
    )

    content = paths.transcript.read_text(encoding="utf-8")
    metadata = _meta(paths.transcript)
    assert metadata["turn_count"] == 1
    assert_prompt_contracts(
        content,
        *semantic_concept(
            "ideate transcript turn shape",
            required=(
                "## Turn 1",
                "- turn_id: TURN-001",
                "- thread_id: TH-001",
                "### Summary",
                "### gpd-ideator",
                "### gpd-ideation-critic",
            ),
            forbidden="No turns recorded.",
        ),
    )


def test_merge_blackboard_update_replaces_manifest_and_appends_sections(tmp_path: Path) -> None:
    session = allocate_ideate_session(tmp_path, "updates", today=TODAY, turn_budget=3)
    paths = initialize_ideate_artifacts(session)

    merge_blackboard_update(
        paths.blackboard,
        BlackboardUpdate(
            turn=1,
            source_manifest={
                "source_manifest": {
                    "sources": [
                        {
                            "source_id": "SRC-001",
                            "kind": "pdf",
                            "input": "paper.pdf",
                            "normalized_ref": "paper.pdf",
                            "status": "completed",
                            "digest_path": "GPD/blackboards/digest.md",
                            "warnings": [],
                        }
                    ]
                }
            },
            candidate_ideas=["RQ-001: Check whether the saddle survives the deformation."],
            critic_notes=["The idea needs an explicit order-of-limits check."],
        ),
        updated=TODAY,
    )

    content = paths.blackboard.read_text(encoding="utf-8")
    metadata = _meta(paths.blackboard)
    assert metadata["turn"] == 1
    assert "status: completed" in content
    assert_prompt_contracts(
        content,
        *semantic_concept(
            "ideate blackboard appended sections",
            required=(
                "- RQ-001: Check whether the saddle survives the deformation.",
                "- The idea needs an explicit order-of-limits check.",
            ),
        ),
    )
