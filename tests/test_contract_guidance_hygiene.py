from pathlib import Path


def test_planner_prompt_contract_gate_line_unique():
    prompt = Path("src/gpd/specs/templates/planner-subagent-prompt.md").read_text()
    gating_line = (
        "If `project_contract_gate.authoritative` is false, `project_contract_load_info.status` starts with `blocked`, "
        "or `project_contract_validation.valid` is false, return `gpd_return.status: checkpoint` instead of guessing."
    )
    assert prompt.count(gating_line) == 1
