"""Focused prompt/command contract cleanup invariants."""

from __future__ import annotations

import re
from pathlib import Path

from tests.core.test_spawn_contracts import _find_single_task

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
PUBLIC_SURFACE_CONTRACT = REPO_ROOT / "src/gpd/core/public_surface_contract.json"
README = REPO_ROOT / "README.md"
LINUX_DOC = REPO_ROOT / "docs/linux.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def test_discover_managed_outputs_have_write_capability_and_documented_route() -> None:
    command_text = _read(COMMANDS_DIR / "discover.md")
    workflow_text = _read(WORKFLOWS_DIR / "discover.md")

    assert "output_policy:" in command_text
    assert "output_mode: managed" in command_text
    assert "managed_root_kind: gpd_managed_durable" in command_text
    assert "default_output_subtree: GPD/analysis" in command_text
    assert "  - file_write" in command_text
    assert "documented write route" in command_text
    assert "workflow-owned Level 2-3 discovery artifact path" in command_text
    assert "This workflow is the documented write route for `gpd:discover` managed outputs." in workflow_text


def test_owned_project_aware_commands_use_validated_context_instead_of_raw_gpd_includes() -> None:
    command_files = (
        "discover.md",
        "sensitivity-analysis.md",
        "derive-equation.md",
        "review-knowledge.md",
    )

    for command_file in command_files:
        text = _read(COMMANDS_DIR / command_file)
        assert "@GPD/" not in text, command_file
        assert "Validated command-context" in text, command_file


def test_help_reference_stays_static_and_delegates_next_action_routing() -> None:
    help_workflow = _read(WORKFLOWS_DIR / "help.md")
    success_criteria = _between(help_workflow, "<success_criteria>", "</success_criteria>")

    assert "Next action guidance provided based on current project state" not in success_criteria
    assert "Static reference stays project-independent" in success_criteria
    assert (
        "current-state routing is delegated to `gpd:start`, `gpd:progress`, or `gpd:suggest-next`" in success_criteria
    )
    assert "Run `gpd:start` when you need the safest route for this folder" in help_workflow
    assert "Run `gpd:suggest-next` when you only need the next action" in help_workflow


def test_peer_review_file_producing_stage_prompts_carry_spawn_contracts() -> None:
    workflow_path = WORKFLOWS_DIR / "peer-review.md"
    for agent_name in (
        "gpd-review-reader",
        "gpd-review-literature",
        "gpd-review-math",
        "gpd-check-proof",
        "gpd-review-physics",
        "gpd-review-significance",
        "gpd-referee",
    ):
        task = _find_single_task(workflow_path, agent_name)
        assert "<spawn_contract>" in task.text, agent_name
        assert "write_scope:" in task.text, agent_name
        assert "expected_artifacts:" in task.text, agent_name
        assert "shared_state_policy: return_only" in task.text, agent_name


def test_delegation_reference_requires_contract_or_tight_exemption() -> None:
    text = _read(REFERENCES_DIR / "orchestration/agent-delegation.md")

    assert "File-producing or state-sensitive spawned prompts must include this block directly" in text
    assert "adjacent documented exemption" in text
    assert "read-only, produces no artifacts, and returns no shared-state update" in text


def test_public_local_cli_examples_use_prefixless_command_labels() -> None:
    contract = _read(PUBLIC_SURFACE_CONTRACT)
    help_workflow = _read(WORKFLOWS_DIR / "help.md")

    assert "gpd validate command-context <name>" in contract
    assert "gpd validate command-context <name>" in help_workflow
    assert "gpd validate command-context gpd:<name>" not in contract
    assert "gpd validate command-context gpd:<name>" not in help_workflow


def test_readme_generic_command_surface_stays_prefixless_and_uninstall_requires_scope() -> None:
    readme = _read(README)
    key_paths = _between(readme, "## Key GPD Paths", "## System Requirements")
    uninstall = _between(readme, "## Uninstall", "## Inspiration")

    assert "`write-paper` supports current-project manuscripts" in key_paths
    assert "The full in-runtime reference is runtime-specific; the shared examples here stay prefixless." in key_paths
    assert "gpd:write-paper" not in key_paths
    assert "gpd:peer-review" not in key_paths
    assert "gpd:pause-work" not in key_paths
    assert "Claude Code / Gemini CLI syntax" not in key_paths
    assert "For non-interactive uninstall, select both the runtime and scope explicitly" in uninstall
    assert "npx -y get-physics-done --uninstall --codex --local" in uninstall
    assert "npx -y get-physics-done --uninstall --claude --global" in uninstall


def test_linux_docs_warn_distro_node_packages_still_need_node_20() -> None:
    text = _read(LINUX_DOC)
    install_section = _between(text, "## Install or update missing tools", "## Linux-specific notes")

    assert "do not continue unless `node --version` reports `v20` or newer" in install_section
    assert "Seeing `nodejs`, `npm`, and `npx` on your PATH is not sufficient" in install_section


def test_export_logs_uses_raw_prefixless_command_context_preflight() -> None:
    command = _read(COMMANDS_DIR / "export-logs.md")
    workflow = _read(WORKFLOWS_DIR / "export-logs.md")

    for text in (command, workflow):
        assert 'CONTEXT=$(gpd --raw validate command-context export-logs "$ARGUMENTS")' in text
        assert "gpd validate command-context gpd:export-logs" not in text
    assert "export-logs --command execute-phase --phase 3 --category workflow" in workflow
    assert "gpd:export-logs --command gpd:execute-phase" not in workflow


def test_execute_phase_routes_convention_repair_to_validate_conventions_not_inline_notation() -> None:
    workflow = _read(WORKFLOWS_DIR / "execute-phase.md")

    assert 'subagent_type="gpd-notation-coordinator"' not in workflow
    assert "Do not spawn `gpd-notation-coordinator` from `execute-phase`" in workflow
    assert "route through `gpd:validate-conventions`" in workflow
    assert "fresh continuation handoff owns any notation-coordinator work" in workflow
    assert "CONVENTION UPDATE" not in workflow
    assert "CONVENTION CONFLICT" not in workflow


def test_response_writer_handoff_is_included_once_in_respond_to_referees() -> None:
    workflow = _read(WORKFLOWS_DIR / "respond-to-referees.md")
    include = "@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md"

    assert workflow.count(include) == 1
    assert "Use the publication response-writer handoff already loaded during initialization" in workflow
    assert "Apply the already-loaded shared publication response-writer handoff" in workflow


def test_inline_install_dir_paths_do_not_use_at_include_form() -> None:
    roots = (COMMANDS_DIR, AGENTS_DIR, WORKFLOWS_DIR, TEMPLATES_DIR)
    offenders: list[str] = []

    for root in roots:
        for path in sorted(root.rglob("*.md")):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if "@{GPD_INSTALL_DIR}" not in line:
                    continue
                stripped = line.strip()
                if stripped.startswith("@{GPD_INSTALL_DIR}/"):
                    continue
                if stripped.startswith(("- @{GPD_INSTALL_DIR}/", "* @{GPD_INSTALL_DIR}/")):
                    continue
                if stripped.startswith(("- `@{GPD_INSTALL_DIR}/", "* `@{GPD_INSTALL_DIR}/")):
                    continue
                if re.match(r"\d+[.)]\s+@\{GPD_INSTALL_DIR\}/", stripped):
                    continue
                if re.match(r"\d+[.)]\s+`@\{GPD_INSTALL_DIR\}/", stripped):
                    continue
                if "`@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md`" in stripped:
                    continue
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}:{line}")

    assert offenders == []


def test_public_templates_do_not_expose_internal_verify_phase_wording() -> None:
    roadmap = _read(TEMPLATES_DIR / "roadmap.md")
    state_machine = _read(TEMPLATES_DIR / "state-machine.md")

    assert "verify-phase" not in roadmap
    assert "verify-phase" not in state_machine
    assert "Verified by the phase verification workflow after execution" in roadmap
    assert "**Automated verification:**" in state_machine
