from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"

CASES = (
    (
        "research-phase.md",
        "gpd-phase-researcher",
        "{phase_dir}/{phase_number}-RESEARCH.md",
        ("RESEARCH COMPLETE", "CHECKPOINT REACHED", "RESEARCH INCONCLUSIVE"),
    ),
    (
        "literature-review.md",
        "gpd-literature-reviewer",
        "GPD/literature/{slug}-REVIEW.md",
        ("REVIEW COMPLETE", "CHECKPOINT REACHED", "REVIEW INCONCLUSIVE"),
    ),
)


@pytest.mark.parametrize(("command_name", "agent_name", "artifact_token", "heading_markers"), CASES)
def test_wrapper_child_return_contract_is_typed_and_thin(
    command_name: str,
    agent_name: str,
    artifact_token: str,
    heading_markers: tuple[str, ...],
) -> None:
    text = (COMMANDS_DIR / command_name).read_text(encoding="utf-8")

    assert f"read {{GPD_AGENTS_DIR}}/{agent_name}.md for your role and instructions" in text
    assert "workflow-owned child-return contract" in text
    assert "gpd_return.status: completed" in text
    assert "gpd_return.status: checkpoint" in text
    assert "artifact gate" in text
    assert "fresh continuation run" in text
    assert f"Write to: {artifact_token}" in text
    assert "Do not branch on heading text here." in text

    for marker in heading_markers:
        assert marker not in text

