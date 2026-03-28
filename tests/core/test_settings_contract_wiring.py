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
    assert "Project conventions do **not** live in `GPD/config.json`." in settings_workflow
    assert "Project conventions still live in `GPD/CONVENTIONS.md` and `GPD/state.json` (`convention_lock`)" in settings_workflow
    assert '"physics": {' not in planning_config
    assert "Project conventions are not part of `config.json`." in planning_config
    assert "Do **not** introduce a `physics` block there." in planning_config
    assert "The user can run `gpd convention set ...` or `/gpd:validate-conventions` later to complete convention setup." in new_project


def test_settings_model_cost_onboarding_stays_qualitative_and_runtime_default_first() -> None:
    settings_command = (COMMANDS_DIR / "settings.md").read_text(encoding="utf-8")
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert "**Model cost posture**: Max quality / Balanced / Budget-aware" in settings_command
    assert "Prefer runtime defaults unless the user explicitly wants pinned tier overrides" in settings_command
    assert "Treat `Balanced` as the default qualitative posture" in settings_command
    assert "dollar" not in settings_command.lower()

    assert "Balanced (Recommended)" in settings_workflow
    assert "runtime defaults" in settings_workflow
    assert "Step-by-step setup for runtime-specific tier-1, tier-2, and tier-3 model strings" in settings_workflow
    assert "Prefer leaving overrides unset unless the user explicitly asks to pin concrete model ids." in settings_workflow
    assert "use runtime defaults" in settings_command
    assert "Use runtime defaults" in settings_workflow
    assert "configure explicit tier-1, tier-2, tier-3 model strings" in settings_command
    assert "Configure explicit tier models" in settings_workflow
    assert "dollar" not in settings_workflow.lower()


def test_settings_workflow_surfaces_optional_usd_budget_guardrails_as_advisory_only() -> None:
    settings_command = (COMMANDS_DIR / "settings.md").read_text(encoding="utf-8")
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert "Optional USD budget guardrails are advisory only" in settings_command
    assert "project_usd_budget" in settings_workflow
    assert "session_usd_budget" in settings_workflow
    assert "Blank / `none` should clear the corresponding USD budget." in settings_workflow
    assert "never stop work automatically" in settings_workflow
    assert "live budget enforcement" not in settings_workflow


def test_settings_workflow_preset_contract_keeps_runtime_default_tier_model_path_explicit() -> None:
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert "How should GPD handle concrete tier models for the active runtime?" in settings_workflow
    assert "Leave current setting unchanged" in settings_workflow
    assert "Use runtime defaults" in settings_workflow
    assert "Configure explicit tier models" in settings_workflow
    assert "Ask for the exact model string the active runtime accepts rather than normalizing it inside GPD." in settings_workflow
    assert "Preserve any provider prefixes, slash-delimited ids, brackets, or alias syntax the active runtime already uses." in settings_workflow
    assert 'Treat blank / `runtime default` / `none` as "no override for this tier"' in settings_workflow
    assert "Prefer leaving overrides unset unless the user explicitly asks to pin concrete model ids." in settings_workflow
