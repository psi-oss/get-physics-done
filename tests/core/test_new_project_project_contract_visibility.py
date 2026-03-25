"""Prompt/schema visibility regression for approved-mode project-contract grounding."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NEW_PROJECT = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "new-project.md"
STATE_SCHEMA = REPO_ROOT / "src" / "gpd" / "specs" / "templates" / "state-json-schema.md"
QUESTIONING = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "research" / "questioning.md"


def test_new_project_prompt_surfaces_the_canonical_state_schema_for_project_contract_grounding() -> None:
    new_project_text = NEW_PROJECT.read_text(encoding="utf-8")

    assert "templates/state-json-schema.md" in new_project_text
    assert "Before you ask for approval, build the raw contract as a literal JSON object that follows `templates/state-json-schema.md` exactly:" in new_project_text
    assert "Do not approve a scoping contract that strips decisive outputs, anchors, prior outputs, or review/stop triggers down to generic placeholders." in new_project_text
    assert "project_contract_load_info" in new_project_text
    assert "project_contract_validation" in new_project_text
    assert "Parse JSON for: `researcher_model`, `synthesizer_model`, `roadmapper_model`, `commit_docs`, `autonomy`, `research_mode`, `project_exists`, `has_research_map`, `planning_exists`, `has_research_files`, `has_project_manifest`, `has_existing_project`, `needs_research_map`, `has_git`, `project_contract`, `project_contract_load_info`, `project_contract_validation`." in new_project_text
    assert "If `project_contract` is present in the init JSON, keep `project_contract`, `project_contract_load_info`, and `project_contract_validation` visible while deciding whether this is fresh work or a continuation." in new_project_text
    assert "If the init JSON already contains `project_contract`, `project_contract_load_info`, or `project_contract_validation`, preserve that state in the approval gate and continuation decision." in new_project_text


def test_state_schema_surfaces_the_exact_approved_mode_grounding_rule() -> None:
    state_schema_text = STATE_SCHEMA.read_text(encoding="utf-8")

    assert (
        "approved project contract requires at least one concrete anchor/reference/prior-output/baseline; "
        "explicit missing-anchor notes preserve uncertainty but do not satisfy approval on their own"
        in state_schema_text
    )
    assert "`must_include_prior_outputs[]` entries should be explicit project-artifact paths or filenames" in state_schema_text
    assert "`GPD/phases/.../*-SUMMARY.md` or `paper/main.tex`" in state_schema_text
    assert "`GPD/phases/.../SUMMARY.md`" not in state_schema_text
    assert (
        "`user_asserted_anchors[]` and `known_good_baselines[]` should name a concrete benchmark, baseline, reference, notebook, figure, dataset, or comparable anchor phrase"
        in state_schema_text
    )
    assert "Placeholder or `TBD` text does not count as concrete grounding." in state_schema_text
    assert "they do not satisfy approved-mode grounding on their own" in state_schema_text


def test_new_project_and_questioning_gate_do_not_treat_missing_anchor_notes_as_approval_ready_grounding() -> None:
    new_project_text = NEW_PROJECT.read_text(encoding="utf-8")
    questioning_text = QUESTIONING.read_text(encoding="utf-8")

    assert "At least one concrete anchor, reference, prior-output constraint, or baseline" in new_project_text
    assert "If the decisive anchor is still unknown, keep that blocker explicit" in new_project_text
    assert "Missing-anchor notes preserve uncertainty, but they do not satisfy approval on their own." in new_project_text
    assert "at least one concrete anchor, reference, prior output, or baseline" in questioning_text
    assert "if the decisive anchor is still unknown, an explicit missing-anchor note" in questioning_text
    assert "do not replace the requirement for at least one concrete reference, prior output, baseline" in questioning_text
