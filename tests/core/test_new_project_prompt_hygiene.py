from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _read_new_project_workflow() -> str:
    return (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")


def test_new_project_contract_block_has_single_bash_code_fence() -> None:
    workflow = _read_new_project_workflow()
    marker = "After approval, validate the contract before persisting it:"
    assert marker in workflow, "workflow must describe the validation step"
    end_marker = "**Project contract schema visibility:**"
    section = workflow.split(marker, 1)[1]
    assert end_marker in section
    section = section.split(end_marker, 1)[0]
    assert section.count("```bash") == 1, "validation/persistence should share one code block"


def test_new_project_schema_reference_count() -> None:
    workflow = _read_new_project_workflow()
    schema_mentions = workflow.count("templates/project-contract-schema.md")
    assert 1 <= schema_mentions <= 2
