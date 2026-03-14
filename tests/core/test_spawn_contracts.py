"""Semantic regression tests for spawned-agent workflow contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"

RUNTIME_NOTE_FRAGMENT = "Runtime delegation:"
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


def _task_blocks_by_agent(path: Path, agent_name: str) -> list[TaskBlock]:
    return [block for block in _extract_task_blocks(_read(path)) if f'subagent_type="{agent_name}"' in block.text]


def _find_single_task(path: Path, agent_name: str) -> TaskBlock:
    matches = _task_blocks_by_agent(path, agent_name)
    assert matches, f"{path.relative_to(REPO_ROOT)} missing task() for {agent_name}"
    return matches[0]


def _assert_runtime_note_present(path: Path) -> None:
    content = _read(path)
    assert RUNTIME_NOTE_FRAGMENT in content, path
    assert MODEL_OMISSION_FRAGMENT in content, path
    assert READONLY_RUNTIME_NOTE_FRAGMENT in content, (
        f"{path.relative_to(REPO_ROOT)} runtime note missing readonly=false instruction"
    )


def _assert_prompt_bootstrap(task: TaskBlock, agent_name: str) -> None:
    assert f'subagent_type="{agent_name}"' in task.text
    assert f"First, read {{GPD_AGENTS_DIR}}/{agent_name}.md for your role and instructions." in task.text


def _extract_output_paths(task: TaskBlock) -> list[str]:
    return re.findall(r"Write to:\s*([^\s`]+)", task.text)


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
        "plan-phase.md": ["gpd-phase-researcher", "gpd-planner", "gpd-plan-checker"],
        "execute-phase.md": ["gpd-executor"],
        "write-paper.md": ["gpd-paper-writer"],
        "new-project.md": ["gpd-project-researcher"],
        "peer-review.md": ["gpd-review-reader", "gpd-referee"],
    }

    for workflow_name, agent_names in coverage.items():
        path = WORKFLOWS_DIR / workflow_name
        _assert_runtime_note_present(path)
        for agent_name in agent_names:
            _assert_prompt_bootstrap(_find_single_task(path, agent_name), agent_name)


def test_quick_and_write_paper_gate_handoffs_on_expected_artifacts() -> None:
    quick = _read(WORKFLOWS_DIR / "quick.md")
    write_paper = _read(WORKFLOWS_DIR / "write-paper.md")

    assert "Verify plan exists at `${QUICK_DIR}/${next_num}-PLAN.md`" in quick
    assert "Verify summary exists at `${QUICK_DIR}/${next_num}-SUMMARY.md`" in quick
    assert "Do not trust the runtime handoff status by itself." in quick
    assert "check for the expected .tex output files before spawning writer agents" in write_paper
    assert "Check if the expected .tex file was written to `paper/`" in write_paper
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
    assert "If the researcher reports `## RESEARCH COMPLETE` but the `expected_artifacts` entry (`RESEARCH.md`) is missing" in content
    assert "<spawn_contract>" in content
    assert "expected_artifacts:" in content
    assert "shared_state_policy: return_only" in content


def test_new_project_parallel_researchers_write_to_disjoint_artifacts() -> None:
    path = WORKFLOWS_DIR / "new-project.md"
    tasks = _task_blocks_by_agent(path, "gpd-project-researcher")
    outputs = {output for task in tasks for output in _extract_output_paths(task)}

    expected = {
        ".gpd/research/PRIOR-WORK.md",
        ".gpd/research/METHODS.md",
        ".gpd/research/COMPUTATIONAL.md",
        ".gpd/research/PITFALLS.md",
    }

    assert expected <= outputs
    assert len(outputs) == len(set(outputs))
    assert "If 1-2 agents failed, proceed with the synthesizer using available files" in _read(path)


def test_new_milestone_research_and_roadmapper_gate_success_path_artifacts() -> None:
    content = _read(WORKFLOWS_DIR / "new-milestone.md")

    assert content.count("<spawn_contract>") >= 3
    assert "Do not trust the runtime handoff status by itself." in content
    assert "If a scout reports success but its `expected_artifacts` entry (`.gpd/research/{FILE}`) is missing" in content
    assert "If the synthesizer reports success but `.gpd/research/SUMMARY.md` is missing" in content
    assert "If the roadmapper reports `## ROADMAP CREATED` but `.gpd/ROADMAP.md` or `.gpd/STATE.md` is missing" in content
    assert "shared_state_policy: return_only" in content


def test_peer_review_stages_use_fresh_context_and_stage_artifacts() -> None:
    path = WORKFLOWS_DIR / "peer-review.md"
    content = _read(path)

    reader = _find_single_task(path, "gpd-review-reader")
    literature = _find_single_task(path, "gpd-review-literature")
    math = _find_single_task(path, "gpd-review-math")
    physics = _find_single_task(path, "gpd-review-physics")
    significance = _find_single_task(path, "gpd-review-significance")
    referee = _find_single_task(path, "gpd-referee")

    assert "Spawn a fresh subagent for the task below." in content
    assert "This stage must start nearly fresh and remain manuscript-first." in reader.text
    assert "fresh context" in literature.text
    assert "fresh context" in math.text
    assert "fresh context" in physics.text
    assert "fresh context" in significance.text
    assert ".gpd/review/STAGE-literature{round_suffix}.json" in literature.text
    assert ".gpd/review/STAGE-math{round_suffix}.json" in math.text
    assert ".gpd/review/STAGE-physics{round_suffix}.json" in physics.text
    assert ".gpd/review/STAGE-interestingness{round_suffix}.json" in significance.text
    assert ".gpd/review/REVIEW-LEDGER{round_suffix}.json" in referee.text
    assert ".gpd/review/REFEREE-DECISION{round_suffix}.json" in referee.text
    assert ".gpd/REFEREE-REPORT{round_suffix}.md" in referee.text


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

    assert "Read the file at .gpd/debug/{slug}.md" in content
    assert "@.gpd/debug/{slug}.md" not in content
