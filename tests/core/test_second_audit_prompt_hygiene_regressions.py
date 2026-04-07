from pathlib import Path

WORKFLOWS_DIR = Path("src/gpd/specs/workflows")
COMMANDS_DIR = Path("src/gpd/commands")
REFERENCES_DIR = Path("src/gpd/specs/references")


def test_help_resume_boundary_note_is_concise_and_contract_aligned() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8").lower()

    assert help_workflow.count("compatibility-only intake fields stay internal") == 1
    assert "canonical continuation fields define the public resume vocabulary" in help_workflow
    assert "public top-level resume vocabulary" not in help_workflow


def test_transition_workflow_stays_runtime_neutral() -> None:
    transition_workflow = (WORKFLOWS_DIR / "transition.md").read_text(encoding="utf-8")

    assert "slash_command(" not in transition_workflow
    assert "installed runtime command surface" in transition_workflow


def test_write_paper_workflow_drops_authoring_note_placeholders() -> None:
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")

    assert "Default bootstrap wording:" not in write_paper


def test_shared_context_budget_guidance_stays_runtime_neutral() -> None:
    owned_surfaces = (
        COMMANDS_DIR / "debug.md",
        COMMANDS_DIR / "research-phase.md",
        COMMANDS_DIR / "literature-review.md",
        COMMANDS_DIR / "respond-to-referees.md",
        WORKFLOWS_DIR / "plan-phase.md",
        WORKFLOWS_DIR / "execute-phase.md",
        WORKFLOWS_DIR / "execute-plan.md",
        REFERENCES_DIR / "orchestration" / "context-budget.md",
    )

    for path in owned_surfaces:
        text = path.read_text(encoding="utf-8").lower()
        assert "200k" not in text, path


def test_debug_workflow_path_note_is_not_self_contradictory() -> None:
    debug_workflow = (WORKFLOWS_DIR / "debug.md").read_text(encoding="utf-8")

    assert "Debug files use the `GPD/debug/` path." in debug_workflow
    assert "hidden directory with leading dot" not in debug_workflow


def test_settings_workflow_reuses_one_terminal_follow_up_list() -> None:
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert settings_workflow.count("For normal-terminal follow-up around these settings:") == 1
    assert "reuse the normal-terminal follow-up list from the `present_settings` step" in settings_workflow
    assert settings_workflow.count("gpd validate unattended-readiness --runtime <runtime> --autonomy <mode>") == 1
