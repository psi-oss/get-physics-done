from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"

CASES = (
    (
        "literature-review.md",
        "",
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

    assert "Follow `@{GPD_INSTALL_DIR}/workflows/literature-review.md` exactly." in text
    assert "The workflow owns staged loading, scope fixing, artifact gating, and citation verification." in text
    assert "workflow-owned child-return contract" not in text
    assert "gpd_return.status: completed" not in text
    assert "gpd_return.status: checkpoint" not in text
    assert f"Write to: {artifact_token}" not in text

    for marker in heading_markers:
        assert marker not in text
