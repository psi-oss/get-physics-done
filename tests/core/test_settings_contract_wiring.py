"""Prompt/spec regressions for settings and project-contract wiring."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"


def test_new_project_minimal_contract_guidance_surfaces_exact_schema_enum_vocabulary() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert "`observables[].kind`: `scalar | curve | map | classification | proof_obligation | other`" in workflow_text
    assert "`acceptance_tests[].automation`: `automated | hybrid | human`" in workflow_text
    assert "`references[].role`: `definition | benchmark | method | must_consider | background | other`" in workflow_text
    assert "`links[].relation`: `supports | computes | visualizes | benchmarks | depends_on | evaluated_by | other`" in workflow_text
    assert (
        "do **not** invent near-miss enum values such as `anchor`, `manual`, `content-check`, `benchmark-record`, or `anchors`"
        in workflow_text
    )


def test_settings_and_planning_config_keep_conventions_outside_config_json() -> None:
    settings_command = (COMMANDS_DIR / "settings.md").read_text(encoding="utf-8")
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    planning_config = (REFERENCES_DIR / "planning" / "planning-config.md").read_text(encoding="utf-8")
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert "physics research preferences" not in settings_command
    assert "physics-specific settings" not in settings_workflow
    assert "Project conventions do **not** live in `.gpd/config.json`." in settings_workflow
    assert "Project conventions still live in `.gpd/CONVENTIONS.md` and `.gpd/state.json` (`convention_lock`)" in settings_workflow
    assert '"physics": {' not in planning_config
    assert "Project conventions are not part of `config.json`." in planning_config
    assert "Do **not** introduce a `physics` block there." in planning_config
    assert "The user can run `gpd convention set ...` or `/gpd:validate-conventions` later to complete convention setup." in new_project
