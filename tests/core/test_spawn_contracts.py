"""Semantic regression tests for spawned-agent workflow contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
WORKFLOW_PATHS = (
    WORKFLOWS_DIR / "quick.md",
    WORKFLOWS_DIR / "map-research.md",
    WORKFLOWS_DIR / "plan-phase.md",
    WORKFLOWS_DIR / "research-phase.md",
    WORKFLOWS_DIR / "execute-phase.md",
    WORKFLOWS_DIR / "verify-work.md",
    WORKFLOWS_DIR / "write-paper.md",
    WORKFLOWS_DIR / "respond-to-referees.md",
    WORKFLOWS_DIR / "new-project.md",
    WORKFLOWS_DIR / "new-milestone.md",
    WORKFLOWS_DIR / "parameter-sweep.md",
    WORKFLOWS_DIR / "literature-review.md",
    WORKFLOWS_DIR / "peer-review.md",
    WORKFLOWS_DIR / "validate-conventions.md",
    WORKFLOWS_DIR / "derive-equation.md",
    WORKFLOWS_DIR / "explain.md",
    WORKFLOWS_DIR / "audit-milestone.md",
    WORKFLOWS_DIR / "debug.md",
)

RUNTIME_NOTE_INCLUDE_FRAGMENT = "@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md"
RUNTIME_NOTE_BODY_FRAGMENT = "Spawn a fresh subagent for the task below."
MODEL_OMISSION_FRAGMENT = (
    "If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model."
)
READONLY_FALSE_FRAGMENT = "readonly=false"
READONLY_RUNTIME_NOTE_FRAGMENT = "Always pass `readonly=false` for file-producing agents."


@dataclass(frozen=True, slots=True)
class TaskBlock:
    start: int
    text: str


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_task_blocks(text: str) -> list[TaskBlock]:
    blocks: list[TaskBlock] = []
    cursor = 0

    while True:
        start = text.find("task(", cursor)
        if start == -1:
            return blocks

        line_start = text.rfind("\n", 0, start) + 1
        if text[line_start:start].lstrip().startswith("#"):
            cursor = start + len("task(")
            continue

        index = start + len("task(")
        depth = 1
        quote: str | None = None
        escaped = False

        while index < len(text):
            char = text[index]

            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
            else:
                if char in {'"', "'"}:
                    quote = char
                elif char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        blocks.append(TaskBlock(start=start, text=text[start : index + 1]))
                        cursor = index + 1
                        break

            index += 1
        else:
            raise AssertionError("Unterminated task() block")


def _task_agent_name(task_text: str) -> str:
    match = re.search(r'subagent_type="([^"]+)"', task_text)
    assert match is not None, f"task() block missing subagent_type:\n{task_text}"
    return match.group(1)


def _task_is_commented_out(text: str, start: int) -> bool:
    line_start = text.rfind("\n", 0, start) + 1
    line_prefix = text[line_start:start].lstrip()
    return line_prefix.startswith("#")


def _task_blocks_by_agent(path: Path, agent_name: str) -> list[TaskBlock]:
    return [block for block in _extract_task_blocks(_read(path)) if f'subagent_type="{agent_name}"' in block.text]


def _find_single_task(path: Path, agent_name: str) -> TaskBlock:
    matches = _task_blocks_by_agent(path, agent_name)
    assert matches, f"{path.relative_to(REPO_ROOT)} missing task() for {agent_name}"
    return matches[0]


def _assert_runtime_note_include(path: Path) -> None:
    content = _read(path)
    assert RUNTIME_NOTE_INCLUDE_FRAGMENT in content, path
    assert RUNTIME_NOTE_BODY_FRAGMENT not in content, (
        f"{path.relative_to(REPO_ROOT)} should reference the shared runtime note instead of duplicating it"
    )


def _assert_expanded_runtime_note(path: Path) -> None:
    content = expand_at_includes(_read(path), REPO_ROOT / "src/gpd", "/runtime/")
    assert RUNTIME_NOTE_BODY_FRAGMENT in content, path
    assert MODEL_OMISSION_FRAGMENT in content, path
    assert READONLY_RUNTIME_NOTE_FRAGMENT in content, (
        f"{path.relative_to(REPO_ROOT)} expanded runtime note missing readonly=false instruction"
    )


def _assert_prompt_bootstrap_in_content(content: str, agent_name: str) -> None:
    assert f"First, read {{GPD_AGENTS_DIR}}/{agent_name}.md for your role and instructions." in content


def _extract_output_paths(task: TaskBlock) -> list[str]:
    return re.findall(r"Write to:\s*([^\s`]+)", task.text)


def _assert_spawn_contract(
    task: TaskBlock,
    expected_outputs: tuple[str, ...],
    *,
    shared_state_policy: str = "return_only",
) -> None:
    assert "<spawn_contract>" in task.text
    assert "write_scope:" in task.text
    assert "expected_artifacts:" in task.text
    assert f"shared_state_policy: {shared_state_policy}" in task.text
    for output in expected_outputs:
        assert output in task.text


def test_agent_delegation_reference_defines_canonical_task_contract() -> None:
    path = REFERENCES_DIR / "orchestration" / "agent-delegation.md"
    content = _read(path)
    blocks = [
        block
        for block in _extract_task_blocks(content)
        if 'subagent_type="gpd-{agent}"' in block.text and 'description="{short description}"' in block.text
    ]

    assert len(blocks) == 1
    canonical = blocks[0].text

    assert 'subagent_type="gpd-{agent}"' in canonical
    assert 'model="{AGENT_MODEL}"' in canonical
    assert READONLY_FALSE_FRAGMENT in canonical
    assert 'description="{short description}"' in canonical
    assert "First, read {GPD_AGENTS_DIR}/gpd-{agent}.md for your role and instructions." in canonical
    assert "Do not use `@...` references inside task() prompt strings." in content
    assert "Assign an explicit write scope for every subagent." in content
    assert "Always set `readonly=false` for file-producing agents." in content
    assert "Fresh context:" in content
    assert "Model semantics:" in content
    assert "Write access:" in content
    assert "Write-scope isolation:" in content
    assert "Blocking completion semantics:" in content
    assert "Success-path artifact gate:" in content
    assert "Return-envelope parity:" in content
    assert "write_scope:" in content
    assert "expected_artifacts:" in content
    assert "shared_state_policy:" in content
    assert "effective installed runtime" in content
    assert "SKILL.md" not in content
    assert "discoverable action/tool surface" in content
    assert "installed agent prompt instructions" in content
    assert "Artifact Recovery Protocol" in content
    assert "Write the files directly in the main orchestrator context" in content
    assert "Never silently proceed" in content


def test_representative_workflows_keep_runtime_note_and_agent_prompt_bootstrap() -> None:
    coverage = {
        "quick.md": ["gpd-planner", "gpd-executor"],
        "map-research.md": ["gpd-research-mapper"],
        "write-paper.md": ["gpd-paper-writer", "gpd-bibliographer"],
        "respond-to-referees.md": ["gpd-paper-writer"],
        "peer-review.md": ["gpd-review-reader", "gpd-referee"],
        "validate-conventions.md": ["gpd-consistency-checker"],
        "new-project.md": [
            "gpd-project-researcher",
            "gpd-research-synthesizer",
            "gpd-roadmapper",
            "gpd-notation-coordinator",
        ],
        "verify-work.md": ["gpd-check-proof", "gpd-verifier"],
        "derive-equation.md": ["gpd-check-proof"],
        "explain.md": ["gpd-explainer"],
        "audit-milestone.md": ["gpd-consistency-checker", "gpd-referee"],
        "debug.md": ["gpd-debugger"],
    }

    for workflow_name, agent_names in coverage.items():
        path = WORKFLOWS_DIR / workflow_name
        content = _read(path)
        _assert_runtime_note_include(path)
        _assert_expanded_runtime_note(path)
        expanded_content = expand_at_includes(content, REPO_ROOT / "src/gpd", "/runtime/")
        if workflow_name == "explain.md":
            assert 'prompt=filled_prompt' in content
            assert 'subagent_type="gpd-explainer"' in content
            assert 'description="Explain {slug}"' in content
            continue
        for agent_name in agent_names:
            _assert_prompt_bootstrap_in_content(expanded_content, agent_name)


def test_every_workflow_task_block_carries_runtime_delegation_note_and_bootstrap() -> None:
    for path in WORKFLOW_PATHS:
        _assert_runtime_note_include(path)
        _assert_expanded_runtime_note(path)


def test_debug_workflow_and_command_share_the_same_one_shot_debugger_contract() -> None:
    workflow = _read(WORKFLOWS_DIR / "debug.md")
    command = _read(COMMANDS_DIR / "debug.md")
    expanded_workflow = expand_at_includes(workflow, REPO_ROOT / "src/gpd", "/runtime/")

    assert workflow.count('subagent_type="gpd-debugger"') == 1
    assert workflow.count("readonly=false") == 1
    assert 'description="Investigate: {truth_short}"' in workflow
    assert "Spawn a fresh subagent for the task below." in expanded_workflow
    assert "one-shot handoff" in expanded_workflow
    assert "Always pass `readonly=false` for file-producing agents." in expanded_workflow

    assert command.count('subagent_type="gpd-debugger"') == 2
    assert command.count("readonly=false") == 2
    assert 'description="Debug {slug}"' in command
    assert 'description="Continue debug {slug}"' in command
    assert "Create: GPD/debug/{slug}.md" in command
    assert "Debug file path: GPD/debug/{slug}.md" in command
    assert "expected debug session artifact" in command
    assert "artifact gate" in command


def test_quick_and_write_paper_gate_handoffs_on_expected_artifacts() -> None:
    quick = _read(WORKFLOWS_DIR / "quick.md")
    write_paper = _read(WORKFLOWS_DIR / "write-paper.md")

    assert "Verify plan exists at `${QUICK_DIR}/${next_num}-PLAN.md`" in quick
    assert "Verify summary exists at `${QUICK_DIR}/${next_num}-SUMMARY.md`" in quick
    assert "Do not trust the runtime handoff status by itself." in quick
    assert "check for the expected .tex output files before spawning writer agents" in write_paper
    assert "Check if the expected .tex file was written to `${PAPER_DIR}/`" in write_paper
    assert "If the file exists, proceed to the next section." in write_paper


def test_plan_phase_reloads_research_from_disk_and_keeps_checker_advisory() -> None:
    content = _read(WORKFLOWS_DIR / "plan-phase.md")

    assert "Verify RESEARCH.md was written (guard against silent researcher failure):" in content
    assert "Re-read RESEARCH.md from disk" in content
    assert "research_content` from INIT (step 1) is **stale**" in content
    assert "Proceed without plan verification. Plans are still executable." in content
    assert "Approved plans from partial approval are final" in content


def test_execute_phase_requires_state_return_envelope_and_handoff_spot_checks() -> None:
    content = _read(WORKFLOWS_DIR / "execute-phase.md")
    executor = _find_single_task(WORKFLOWS_DIR / "execute-phase.md", "gpd-executor")

    assert "Return state updates (position, decisions, metrics) in your response -- do NOT write STATE.md directly." in executor.text
    assert "State updates returned (NOT written to STATE.md directly)" in executor.text
    assert "Executor subagents MUST NOT write STATE.md directly." in content
    assert "Verify expected output files, the structured return envelope, and git commits" in content
    assert "pre_execution_specialists" in content
    assert '# task(subagent_type="gpd-notation-coordinator"' not in content
    assert '# task(subagent_type="gpd-experiment-designer"' not in content


def test_parameter_sweep_executor_uses_spawn_contract_and_return_only_state_updates() -> None:
    path = WORKFLOWS_DIR / "parameter-sweep.md"
    executor = _find_single_task(path, "gpd-executor")

    assert "Return state updates in your response -- do NOT write STATE.md directly." in executor.text
    assert "<spawn_contract>" in executor.text
    assert "write_scope:" in executor.text
    assert "expected_artifacts:" in executor.text
    assert "shared_state_policy: return_only" in executor.text
    assert "State updates returned (NOT written to STATE.md directly)" in executor.text
    assert "${SWEEP_ARTIFACT_DIR}/results/point-{PADDED_INDEX}.json" in executor.text
    assert "${SWEEP_PHASE_DIR}/sweep-{PADDED_INDEX}-SUMMARY.md" in executor.text
    assert "${SWEEP_DIR}/results/point-{PADDED_INDEX}.json" not in executor.text


def test_research_phase_verifies_research_artifact_before_accepting_handoff() -> None:
    content = _read(WORKFLOWS_DIR / "research-phase.md")

    assert "Accept the researcher handoff automatically only once `expected_artifacts` exist and pass the artifact check." in content
    assert "Do not trust the runtime handoff status by itself." in content
    assert "Artifact gate:" in content
    assert "If `gpd_return.status: completed` but the `expected_artifacts` entry (`RESEARCH.md`) is missing" in content
    assert "<spawn_contract>" in content
    assert "expected_artifacts:" in content
    assert "shared_state_policy: return_only" in content


def test_new_project_parallel_researchers_write_to_disjoint_artifacts() -> None:
    path = WORKFLOWS_DIR / "new-project.md"
    tasks = _task_blocks_by_agent(path, "gpd-project-researcher")
    outputs = {output for task in tasks for output in _extract_output_paths(task)}

    expected = {
        "GPD/literature/PRIOR-WORK.md",
        "GPD/literature/METHODS.md",
        "GPD/literature/COMPUTATIONAL.md",
        "GPD/literature/PITFALLS.md",
    }

    assert expected <= outputs
    assert len(outputs) == len(set(outputs))
    assert len(tasks) == 4

    for task in tasks:
        task_outputs = tuple(_extract_output_paths(task))
        assert len(task_outputs) == 1
        _assert_spawn_contract(task, task_outputs)

    content = _read(path)
    synth = _find_single_task(path, "gpd-research-synthesizer")
    _assert_spawn_contract(synth, ("GPD/literature/SUMMARY.md",))
    assert "GPD/PROJECT.md" in synth.text
    assert "GPD/config.json" in synth.text
    assert "GPD/literature/SUMMARY.md (if re-synthesizing an existing survey)" in synth.text
    assert "Do not trust the runtime handoff status by itself." in content
    assert "If a scout reports success but its `expected_artifacts` entry" in content
    assert "`GPD/literature/{FILE}`" in content
    assert "If the synthesizer reports success but `GPD/literature/SUMMARY.md` is missing" in content
    assert "Do not proceed with a partial literature survey" in content
    assert "Do not synthesize from incomplete scout output" in content
    assert "Do not fabricate a fallback summary in the main context" in content


def test_new_project_roadmapper_uses_spawn_contract_and_artifact_gate() -> None:
    path = WORKFLOWS_DIR / "new-project.md"
    content = _read(path)
    roadmapper = _find_single_task(path, "gpd-roadmapper")

    _assert_spawn_contract(roadmapper, ("GPD/ROADMAP.md", "GPD/STATE.md"), shared_state_policy="direct")
    assert "GPD/REQUIREMENTS.md" in roadmapper.text
    assert "GPD/literature/SUMMARY.md" in roadmapper.text
    assert "allowed_paths:" in roadmapper.text
    assert "If the roadmapper reports `gpd_return.status: completed`" in content
    assert "`GPD/ROADMAP.md` or `GPD/STATE.md` is missing" in content
    assert "Do not trust the runtime handoff status by itself." in content
    assert "Do not create a second main-context roadmap implementation path" in content


def test_new_project_notation_coordinator_uses_explicit_model_and_spawn_contract() -> None:
    path = WORKFLOWS_DIR / "new-project.md"
    content = _read(path)
    notation = _find_single_task(path, "gpd-notation-coordinator")

    _assert_spawn_contract(notation, ("GPD/CONVENTIONS.md",), shared_state_policy="direct")
    assert 'model="{NOTATION_MODEL}"' in notation.text
    assert "gpd convention set" in notation.text
    assert "Do not hardcode `natural` or `mostly_minus`" in content
    assert 'gpd convention set units "$RESOLVED_UNITS"' in content
    assert 'gpd convention set metric_signature "$RESOLVED_METRIC"' in content


def test_validate_conventions_uses_one_shot_delegation_and_artifact_gating_for_resolution() -> None:
    content = _read(WORKFLOWS_DIR / "validate-conventions.md")

    assert content.count('subagent_type="gpd-consistency-checker"') == 1
    assert content.count('subagent_type="gpd-notation-coordinator"') == 0
    assert "Thin wrapper around `gpd-consistency-checker` for convention validation." in content
    assert "Spawn `gpd-consistency-checker` once and let it own convention policy." in content
    assert "Runtime delegation rule: this is a one-shot handoff." in content
    assert "Route only on the canonical `gpd_return.status`:" in content
    assert "Do not route on checker-local text markers or headings." in content
    assert "gpd-notation-coordinator" in content
    assert "If the checker's `next_actions` call for notation repair, spawn `gpd-notation-coordinator` with the checker report and the same scope." in content
    assert "Keep that handoff thin: the coordinator owns the repair policy, not this workflow." in content
    assert "If the checker returns `gpd_return.status: completed`, accept success only after verifying that:" in content
    assert "The same path appears in `gpd_return.files_written`." in content


def test_new_milestone_research_and_roadmapper_gate_success_path_artifacts() -> None:
    content = _read(WORKFLOWS_DIR / "new-milestone.md")

    assert content.count("<spawn_contract>") >= 3
    assert "Do not trust the runtime handoff status by itself." in content
    assert "If a scout reports success but its `expected_artifacts` entry (`GPD/literature/{FILE}`) is missing" in content
    assert "If the synthesizer reports success but `GPD/literature/SUMMARY.md` is missing" in content
    assert "If the roadmapper reports `gpd_return.status: completed` but `GPD/ROADMAP.md` or `GPD/STATE.md` is missing" in content
    assert "shared_state_policy: return_only" in content

    assert 'subagent_type="gpd-project-researcher"' in content
    assert "GPD/literature/{FILE}" in content
    assert "expected_artifacts:" in content
    assert "PRIOR-WORK.md" in content
    assert "METHODS.md" in content
    assert "COMPUTATIONAL.md" in content
    assert "PITFALLS.md" in content
    assert 'subagent_type="gpd-research-synthesizer"' in content
    assert "GPD/literature/SUMMARY.md" in content
    assert 'subagent_type="gpd-roadmapper"' in content
    assert "GPD/ROADMAP.md" in content
    assert "GPD/STATE.md" in content


def test_peer_review_stages_use_fresh_context_and_stage_artifacts() -> None:
    path = WORKFLOWS_DIR / "peer-review.md"
    content = _read(path)
    expanded_content = expand_at_includes(content, REPO_ROOT / "src/gpd", "/runtime/")

    reader = _find_single_task(path, "gpd-review-reader")
    literature = _find_single_task(path, "gpd-review-literature")
    math = _find_single_task(path, "gpd-review-math")
    check_proof = _find_single_task(path, "gpd-check-proof")
    physics = _find_single_task(path, "gpd-review-physics")
    significance = _find_single_task(path, "gpd-review-significance")
    referee = _find_single_task(path, "gpd-referee")

    assert RUNTIME_NOTE_INCLUDE_FRAGMENT in content
    assert RUNTIME_NOTE_BODY_FRAGMENT not in content
    assert RUNTIME_NOTE_BODY_FRAGMENT in expanded_content
    assert MODEL_OMISSION_FRAGMENT in expanded_content
    assert READONLY_RUNTIME_NOTE_FRAGMENT in expanded_content
    assert "This stage must start nearly fresh and remain manuscript-first." in reader.text
    assert "fresh context" in literature.text
    assert "fresh context" in math.text
    assert "fresh context" in check_proof.text
    assert "fresh context" in physics.text
    assert "fresh context" in significance.text
    assert "GPD/review/CLAIMS{round_suffix}.json" in referee.text
    assert "GPD/review/STAGE-reader{round_suffix}.json" in referee.text
    assert "GPD/review/STAGE-literature{round_suffix}.json" in literature.text
    assert "GPD/review/STAGE-math{round_suffix}.json" in math.text
    assert "GPD/review/STAGE-physics{round_suffix}.json" in physics.text
    assert "GPD/review/STAGE-interestingness{round_suffix}.json" in significance.text
    assert "GPD/review/STAGE-literature{round_suffix}.json" in referee.text
    assert "GPD/review/STAGE-math{round_suffix}.json" in referee.text
    assert "GPD/review/PROOF-REDTEAM{round_suffix}.md" in check_proof.text
    assert "GPD/review/STAGE-physics{round_suffix}.json" in referee.text
    assert "GPD/review/STAGE-interestingness{round_suffix}.json" in referee.text
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in referee.text
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in referee.text
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in referee.text
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in referee.text


def test_referee_response_template_uses_round_suffixed_decision_artifacts() -> None:
    content = _read(TEMPLATES_DIR / "paper" / "referee-response.md")

    assert "REFEREE-DECISION{round_suffix}.json" in content
    assert "REVIEW-LEDGER{round_suffix}.json" in content
    assert "REFEREE-REPORT{round_suffix}.md" in content
    assert "REFEREE-REPORT.md" not in content


def test_all_workflow_task_blocks_include_readonly_false() -> None:
    """Every task() block that spawns a GPD agent must include readonly=false.

    Without this, some runtimes default subagents to read-only mode where
    file writes silently fail -- the agent reports success but no files are
    persisted to disk.
    """
    exclusions = {"execute-plan.md"}
    failures: list[str] = []
    for workflow_path in sorted(WORKFLOWS_DIR.glob("*.md")):
        if workflow_path.name in exclusions:
            continue
        blocks = _extract_task_blocks(_read(workflow_path))
        for block in blocks:
            if 'subagent_type="gpd-' not in block.text:
                continue
            if READONLY_FALSE_FRAGMENT not in block.text:
                agent = "unknown"
                match = re.search(r'subagent_type="(gpd-[^"]+)"', block.text)
                if match:
                    agent = match.group(1)
                failures.append(f"{workflow_path.name}:{block.start} ({agent})")

    assert not failures, "task() blocks missing readonly=false:\n  " + "\n  ".join(failures)


def test_debug_subagent_template_continuations_use_explicit_file_reads() -> None:
    content = _read(TEMPLATES_DIR / "debug-subagent-prompt.md")

    assert "Read the file at GPD/debug/{slug}.md" in content
    assert "@GPD/debug/{slug}.md" not in content
