import re
from pathlib import Path

COMMANDS_DIR = Path("src/gpd/commands")
WORKFLOWS_DIR = Path("src/gpd/specs/workflows")


def test_command_workflow_references_exist() -> None:
    missing_references: list[str] = []
    for command_path in COMMANDS_DIR.glob("*.md"):
        command_text = command_path.read_text(encoding="utf-8")
        workflow_refs = set(re.findall(r"@{GPD_INSTALL_DIR}/workflows/([\\w-]+\\.md)", command_text))
        for workflow_name in workflow_refs:
            if not (WORKFLOWS_DIR / workflow_name).exists():
                missing_references.append(f"{command_path}: {workflow_name}")
    assert not missing_references, "Missing workflow references:\n" + "\n".join(missing_references)
