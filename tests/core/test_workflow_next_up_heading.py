from pathlib import Path


def test_workflow_next_up_heading_style():
    mismatches: list[str] = []
    workflows_dir = Path("src/gpd/specs/workflows")
    for workflow_path in workflows_dir.glob("*.md"):
        for line in workflow_path.read_text(encoding="utf-8").splitlines():
            stripped = line.lstrip()
            if stripped.startswith("##") and "Next Up" in stripped:
                if stripped != "## > Next Up":
                    mismatches.append(f"{workflow_path}:{line.strip()}")
    assert not mismatches, f"Workflow headings must be `## > Next Up`: {mismatches}"
