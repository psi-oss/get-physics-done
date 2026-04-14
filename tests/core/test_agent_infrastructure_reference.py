from pathlib import Path

TARGET_AGENT_FILES = [
    "src/gpd/agents/gpd-project-researcher.md",
    "src/gpd/agents/gpd-phase-researcher.md",
    "src/gpd/agents/gpd-plan-checker.md",
    "src/gpd/agents/gpd-paper-writer.md",
    "src/gpd/agents/gpd-research-mapper.md",
    "src/gpd/agents/gpd-roadmapper.md",
    "src/gpd/agents/gpd-experiment-designer.md",
    "src/gpd/agents/gpd-consistency-checker.md",
    "src/gpd/agents/gpd-debugger.md",
]


def test_agents_reference_infrastructure_doc():
    for relative_path in TARGET_AGENT_FILES:
        path = Path(relative_path)
        content = path.read_text(encoding="utf-8")
        assert "agent-infrastructure.md" in content, f"{path} must reference the shared infrastructure doc"


def test_agents_drop_shared_headings():
    banned_headings = {"## Context Pressure Management", "## External Tool Failure Protocol"}
    for relative_path in TARGET_AGENT_FILES:
        path = Path(relative_path)
        content = path.read_text(encoding="utf-8")
        for heading in banned_headings:
            assert heading not in content, f"{path} must rely on the shared infrastructure doc for {heading}"
