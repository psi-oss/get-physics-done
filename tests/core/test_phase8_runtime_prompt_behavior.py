from __future__ import annotations

from pathlib import Path

import pytest

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import project_markdown_for_runtime
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.command_labels import validated_public_command_prefix

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
SOURCE_ROOT = REPO_ROOT / "src/gpd"

RUNTIME_LABEL_RULE = "Runtime label: Show `gpd:` as native labels;"
OWNED_WORKFLOWS = ("help", "start", "tour", "new-project", "map-research", "resume-work")
_RUNTIME_WITH_NATIVE_INCLUDE_SUPPORT = next(
    descriptor for descriptor in iter_runtime_descriptors() if descriptor.native_include_support
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _workflow(name: str) -> str:
    return _read(WORKFLOWS_DIR / f"{name}.md")


def _extract_step(content: str, step_name: str) -> str:
    start = content.index(f'<step name="{step_name}"')
    body_start = content.index(">", start) + 1
    end = content.index("</step>", body_start)
    return content[body_start:end]


def _project_command(command_name: str, runtime: str) -> str:
    return project_markdown_for_runtime(
        _read(COMMANDS_DIR / f"{command_name}.md"),
        runtime=runtime,
        path_prefix="/runtime/",
        surface_kind="command",
        src_root=SOURCE_ROOT,
        command_name=command_name,
        inject_skeptical_rigor_guardrails=False,
    )


def _project_owned_workflow(workflow_name: str, descriptor) -> str:
    if descriptor.native_include_support:
        return get_adapter(descriptor.runtime_name).translate_shared_markdown(_workflow(workflow_name), "/runtime/")
    return _project_command(workflow_name, descriptor.runtime_name)


def _runtime_label_rule(prefix: str) -> str:
    return f"Runtime label: Show `{prefix}` as native labels;"


def test_owned_workflows_tell_agents_to_render_native_runtime_command_labels() -> None:
    for workflow_name in OWNED_WORKFLOWS:
        content = _workflow(workflow_name)

        assert RUNTIME_LABEL_RULE in content
        assert "keep local CLI `gpd ...` unchanged." in content


@pytest.mark.parametrize(
    "descriptor", tuple(iter_runtime_descriptors()), ids=lambda descriptor: descriptor.runtime_name
)
@pytest.mark.parametrize("command_name", OWNED_WORKFLOWS)
def test_projected_owned_commands_use_descriptor_public_runtime_label_prefix(command_name: str, descriptor) -> None:
    projected = _project_owned_workflow(command_name, descriptor)
    public_prefix = validated_public_command_prefix(descriptor)

    assert _runtime_label_rule(public_prefix) in projected
    if descriptor.runtime_name == "codex":
        assert "Runtime label: Show `gpd:` as native labels;" not in projected
    if descriptor.runtime_name == "opencode":
        assert "Runtime label: Show `gpd-` as native labels;" not in projected


def test_claude_new_project_wrapper_keeps_post_init_next_step_runtime_native() -> None:
    projected = _project_command("new-project", _RUNTIME_WITH_NATIVE_INCLUDE_SUPPORT.runtime_name)

    assert "`gpd:discuss-phase 1`" in projected
    assert "show native runtime label" in projected


def test_new_project_has_one_primary_post_init_next_step() -> None:
    workflow = _workflow("new-project")
    command = _read(COMMANDS_DIR / "new-project.md")
    final_next_up = workflow[workflow.rindex("## > Next Up") :]

    discuss_idx = final_next_up.index("`gpd:discuss-phase 1`")
    plan_idx = final_next_up.index("`gpd:plan-phase 1`")
    also_available_idx = final_next_up.index("**Also available:**")

    assert discuss_idx < also_available_idx
    assert also_available_idx < plan_idx
    assert "**After this command:** Run `gpd:discuss-phase 1`" in command
    assert "- [ ] User knows next step is `gpd:discuss-phase 1`" in workflow
    assert "- [ ] User told the next step is `gpd:discuss-phase 1`" in command


def test_new_project_headless_and_policy_blocks_do_not_auto_approve_or_fabricate() -> None:
    workflow = _workflow("new-project")

    assert "Headless or non-interactive mode is not scope approval" in workflow
    assert "never auto-select approval" in workflow
    assert "inventing anchors, references, baselines, DOI/arXiv/file locators, or prior outputs" in workflow
    assert "do not substitute unvalidated file writes" in workflow


def test_map_research_partial_outputs_block_complete_claims() -> None:
    workflow = _workflow("map-research")
    verify_output = _extract_step(workflow, "verify_output")
    offer_next = _extract_step(workflow, "offer_next")
    partial_output, complete_output = offer_next.split("**If `MAP_STATUS=complete`, use this output format:**", 1)

    assert "stop before secret scan and commit unless the user explicitly chooses partial mode" in verify_output
    assert "Research project mapping is partial, not complete." in verify_output
    assert "Never call partial output complete" in verify_output
    assert "make `gpd:new-project` the primary next step" in verify_output

    assert "Research project mapping partial." in partial_output
    assert "Do not print `Research project mapping complete.`" in partial_output
    assert "make `gpd:new-project` primary" in partial_output
    assert "`gpd:map-research [missing focus]`" in partial_output

    assert "Research project mapping complete." in complete_output
    assert "`gpd:new-project`" in complete_output


def test_resume_work_continuation_examples_are_non_runnable_templates() -> None:
    update_continuation = _extract_step(_workflow("resume-work"), "update_continuation")

    assert "Template only - do not run as-is" in update_continuation
    assert "```text" in update_continuation
    assert "```bash" not in update_continuation
    assert "Resumed, executing phase 3" not in update_continuation
    assert "GPD/phases/03-dispersion/.continue-here.md" not in update_continuation
    assert "<actual selected route and phase>" in update_continuation
    assert "<actual project-relative handoff path>" in update_continuation
