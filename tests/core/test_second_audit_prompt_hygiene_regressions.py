from pathlib import Path

WORKFLOWS_DIR = Path("src/gpd/specs/workflows")


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
