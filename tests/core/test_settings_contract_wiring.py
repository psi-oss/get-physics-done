"""Prompt/spec assertions for settings and project-contract wiring."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes
from gpd.adapters.runtime_catalog import iter_runtime_descriptors

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
_RUNTIME_DISPLAY_NAMES = tuple(descriptor.display_name for descriptor in iter_runtime_descriptors())


def test_new_project_minimal_contract_guidance_surfaces_contract_enum_vocabulary() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    project_contract_schema_text = expand_at_includes(
        (TEMPLATES_DIR / "project-contract-schema.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd/specs",
        "/runtime/",
    )

    assert "templates/project-contract-schema.md" in workflow_text
    assert "templates/state-json-schema.md" not in workflow_text
    assert "use that schema as the canonical source of truth for the object rules" in workflow_text
    assert (
        "Do not restate the full contract rules here; keep only the approval-critical reminders below." in workflow_text
    )
    assert (
        '`observables[]` — `{ "id", "name", "kind", "definition", "regime?", "units?" }`'
        in project_contract_schema_text
    )
    assert (
        '`acceptance_tests[]` — `{ "id", "subject", "kind", "procedure", "pass_condition", "evidence_required[]", "automation" }`'
        in project_contract_schema_text
    )
    assert (
        '`references[]` — `{ "id", "kind", "locator", "aliases[]", "role", "why_it_matters", "applies_to[]", "carry_forward_to[]", "must_surface": true|false, "required_actions[]" }`'
        in project_contract_schema_text
    )
    assert '`links[]` — `{ "id", "source", "target", "relation", "verified_by[]" }`' in project_contract_schema_text
    assert (
        "`claims[].claim_kind: theorem | lemma | corollary | proposition | result | claim | other`"
        in project_contract_schema_text
    )
    assert (
        "`required_actions[]` uses the same closed action vocabulary enforced downstream in contract ledgers: `read`, `use`, `compare`, `cite`, `avoid`."
        in project_contract_schema_text
    )
    assert (
        "if `references[].must_surface` is `true`, both `references[].applies_to[]` and "
        "`references[].required_actions[]` must be non-empty"
    ) not in workflow_text
    assert (
        "If a project-contract reference sets `must_surface: true`, `required_actions[]` must not be empty."
        in project_contract_schema_text
    )
    assert (
        "If a project-contract reference sets `must_surface: true`, `applies_to[]` must not be empty."
        in project_contract_schema_text
    )


def test_settings_and_planning_config_keep_conventions_outside_config_json() -> None:
    settings_command = (COMMANDS_DIR / "settings.md").read_text(encoding="utf-8")
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    planning_config = (REFERENCES_DIR / "planning" / "planning-config.md").read_text(encoding="utf-8")
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert "physics research preferences" not in settings_command
    assert "physics-specific settings" not in settings_workflow
    assert "Project conventions do **not** live in `GPD/config.json`." in settings_workflow
    assert (
        "Project conventions still live in `GPD/state.json` (`convention_lock`) with "
        "`GPD/CONVENTIONS.md` as the projection/audit surface"
    ) in settings_workflow
    assert '"physics": {' not in planning_config
    assert "Project conventions are not part of `config.json`." in planning_config
    assert "Do **not** introduce a `physics` block there." in planning_config
    assert (
        "The user can run `gpd:validate-conventions`; the fallback lock must match the values written into `GPD/CONVENTIONS.md`."
        in new_project
    )


def test_settings_model_cost_onboarding_stays_qualitative_and_runtime_default_first() -> None:
    settings_command = (COMMANDS_DIR / "settings.md").read_text(encoding="utf-8")
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/settings.md" in settings_command
    assert "Keep this wrapper thin" in settings_command
    assert "Do not invent a parallel settings flow" in settings_command

    assert "Supervised (Recommended)" in settings_workflow
    assert "runtime defaults" in settings_workflow
    assert "gpd:set-tier-models" in settings_workflow
    assert "Use runtime defaults" in settings_workflow
    assert "Configure explicit tier models" in settings_workflow
    assert "tier-1" in settings_workflow
    assert "tier-2" in settings_workflow
    assert "tier-3" in settings_workflow
    assert "dollar" not in settings_workflow.lower()


def test_settings_workflow_surfaces_optional_usd_budget_guardrails_as_advisory_only() -> None:
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert "project_usd_budget" in settings_workflow
    assert "session_usd_budget" in settings_workflow
    assert "To clear a configured USD budget, use literal JSON `null`." in settings_workflow
    assert "Do not advertise or pass `none` or an empty string as a clearing value." in settings_workflow
    assert "Blank / `none` should clear the corresponding USD budget." not in settings_workflow
    assert "never stop work automatically" in settings_workflow
    assert "live budget enforcement" not in settings_workflow


def test_settings_workflow_preset_contract_keeps_runtime_default_tier_model_path_explicit() -> None:
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert "gpd:set-tier-models" in settings_workflow
    assert "How should GPD handle concrete tier models for the active runtime?" in settings_workflow
    assert "Leave current setting unchanged" in settings_workflow
    assert "Use runtime defaults" in settings_workflow
    assert "Configure explicit tier models" in settings_workflow
    assert 'Treat blank / `runtime default` / `none` as "no override for this tier"' in settings_workflow


def test_settings_workflow_uses_same_selected_runtime_for_models_and_permissions() -> None:
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    permissions_sync = re.compile(
        r"gpd --raw permissions sync\b"
        r"(?=[^\n]*--runtime \"\$SELECTED_RUNTIME\")"
        r"(?=[^\n]*--autonomy \"\$SELECTED_AUTONOMY\")"
    )

    assert "`SELECTED_RUNTIME`" in settings_workflow
    assert "model_overrides.<SELECTED_RUNTIME>" in settings_workflow
    assert permissions_sync.search(settings_workflow)
    assert 'gpd --raw permissions sync --autonomy "$SELECTED_AUTONOMY"' not in settings_workflow


def test_set_tier_models_workflow_keeps_runtime_examples_generic() -> None:
    set_tier_models = (WORKFLOWS_DIR / "set-tier-models.md").read_text(encoding="utf-8")

    for display_name in _RUNTIME_DISPLAY_NAMES:
        assert display_name not in set_tier_models
    assert "gpt-5.4" not in set_tier_models
    assert "runtime-native examples are intentionally not hard-coded here" in set_tier_models.lower()


def test_settings_workflow_keeps_convention_ownership_outside_settings_and_routes_changes_to_validate_conventions() -> (
    None
):
    settings_command = (COMMANDS_DIR / "settings.md").read_text(encoding="utf-8")
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert (
        "Convention work stays outside settings; use `gpd convention set <key> <value>` or `gpd:validate-conventions` for project convention updates."
        in settings_command
    )
    assert (
        "Project conventions still live in `GPD/state.json` (`convention_lock`) with "
        "`GPD/CONVENTIONS.md` as the projection/audit surface, not in `GPD/config.json`."
    ) in settings_workflow
    assert "gpd:validate-conventions -- verify convention consistency across the project" in settings_workflow
    assert "gpd convention set <key> <value> -- update the locked project conventions directly" in settings_workflow


def test_settings_workflow_writes_canonical_config_keys_through_cli() -> None:
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    update_step = settings_workflow.split('<step name="update_config">', 1)[1].split("</step>", 1)[0]

    assert 'gpd config set autonomy "$SELECTED_AUTONOMY"' in update_step
    assert 'gpd config set workflow.research "$SELECTED_WORKFLOW_RESEARCH"' in update_step
    assert 'gpd config set execution.review_cadence "$SELECTED_REVIEW_CADENCE"' in update_step
    assert 'gpd config set git.branching_strategy "$SELECTED_BRANCHING_STRATEGY"' in update_step
    assert 'gpd config set model_overrides "$MODEL_OVERRIDES_JSON"' in update_step
    assert 'gpd config set git.phase_branch_template "$SELECTED_PHASE_BRANCH_TEMPLATE"' not in update_step
    assert 'gpd config set git.milestone_branch_template "$SELECTED_MILESTONE_BRANCH_TEMPLATE"' not in update_step
    assert "Preserve `git.phase_branch_template` and `git.milestone_branch_template`" in update_step
    for stale_nested_key in ('"planning": {', '"workflow": {', '"execution": {', '"git": {'):
        assert stale_nested_key not in update_step


def test_settings_update_config_selected_variables_are_collected_before_use() -> None:
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    update_step = settings_workflow.split('<step name="update_config">', 1)[1].split("</step>", 1)[0]

    selected_vars_used = set(re.findall(r"\$(SELECTED_[A-Z0-9_]+)\b", update_step))
    selected_vars_collected = set(re.findall(r"- `(SELECTED_[A-Z0-9_]+)`", update_step))

    assert selected_vars_used
    assert selected_vars_used <= selected_vars_collected
    assert "SELECTED_PHASE_BRANCH_TEMPLATE" not in selected_vars_used
    assert "SELECTED_MILESTONE_BRANCH_TEMPLATE" not in selected_vars_used


def test_settings_and_profile_docs_keep_supervised_dense_defaults_consistent() -> None:
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    set_profile_workflow = (WORKFLOWS_DIR / "set-profile.md").read_text(encoding="utf-8")
    continuous_execution = (REFERENCES_DIR / "orchestration" / "continuous-execution.md").read_text(encoding="utf-8")

    assert "Core research (Recommended): preview the supervised default bundle" in settings_workflow
    assert "balanced default bundle" not in settings_workflow
    assert "using the schema defaults noted below" in settings_workflow

    assert "Keep `execution.review_cadence=dense` for publication-quality passes" in set_profile_workflow
    assert "`execution.review_cadence=adaptive` or `sparse` usually fits" not in set_profile_workflow

    assert "| **Supervised** (default)         | `supervised`" in continuous_execution
    assert "This is an explicit opt-in after the user leaves the default `supervised` posture." in continuous_execution
    assert "The default autonomy setting. The assistant auto-advances" not in continuous_execution
    assert "eligible for auto-advance in `balanced` or `yolo`" in continuous_execution
