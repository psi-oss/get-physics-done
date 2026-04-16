from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

import yaml

from tests.ci_sharding import (
    CI_SHARD_TARGET_RESOLVER_STEP_NAME,
    CI_SMOKE_PYTEST_STEP_NAME,
    CI_SMOKE_TEST_TARGETS,
    ci_smoke_pytest_command,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_SMOKE_SELECTION_TOKENS = (
    "subprocess",
    "all_test_relpaths",
    "collected_test_inventory",
    "collected_test_counts_by_file",
    "build_ci_work_units",
    "expand_ci_targets_to_nodeids",
    "plan_category_ci_shards",
    "select_ci_shard_targets",
    "write_ci_shard_targets_file",
    "--collect-only",
)
REQUIRED_SMOKE_TEST_TARGETS = (
    "tests/test_release_consistency.py",
    "tests/core/test_workflow_stage_manifest_inventory.py",
)
REQUIRED_SMOKE_TARGET_PREFIXES = (
    "tests/core/test_workflow_staging.py::",
    "tests/core/test_research_phase_stage_manifest.py::",
    "tests/core/test_write_paper_prompt_budget.py::",
)
README_SMOKE_ANCHOR = "Use the fast smoke suite tracked by `tests/ci_sharding.py` before pushing changes."
CONTRIBUTING_SMOKE_ANCHOR = "Fast smoke (≈3 min): run the targets from `tests/ci_sharding.py` via"


def _workflow_data() -> dict[str, object]:
    workflow_path = REPO_ROOT / ".github" / "workflows" / "test.yml"
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def _job_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def _run_steps_by_name(steps: list[dict[str, object]]) -> dict[str, str]:
    return {str(step.get("name", "")): str(step.get("run", "")) for step in steps if "run" in step}


def _job_needs(workflow: dict[str, object], job_name: str) -> tuple[str, ...]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    needs = job.get("needs")
    if needs is None:
        return ()
    if isinstance(needs, str):
        return (needs,)
    assert isinstance(needs, list)
    return tuple(str(entry) for entry in needs)


def _pytest_command_targets(command: str) -> tuple[str, ...]:
    tokens = shlex.split(command)
    assert tokens[:4] == ["uv", "run", "pytest", "-q"]
    return tuple(tokens[4:])


def _normalized_shell_command(command: str) -> str:
    normalized = re.sub(r"\\\s*\n\s*", " ", command)
    return " ".join(normalized.split())


def _extract_markdown_bash_block(rel_path: str, *, anchor: str) -> str:
    text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    anchored_text = text[text.index(anchor) :]
    match = re.search(r"```bash\n(?P<command>.*?)\n```", anchored_text, re.DOTALL)
    assert match is not None, f"missing bash block after {anchor!r} in {rel_path}"
    return match.group("command")


def _package_smoke_command() -> str:
    package_data = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package_data["scripts"]
    assert isinstance(scripts, dict)
    smoke_command = scripts["smoke"]
    assert isinstance(smoke_command, str)
    return smoke_command


def test_ci_smoke_command_builder_uses_only_explicit_fast_targets() -> None:
    command = ci_smoke_pytest_command()
    targets = _pytest_command_targets(command)

    assert targets == CI_SMOKE_TEST_TARGETS
    assert targets
    assert all(token not in command for token in FORBIDDEN_SMOKE_SELECTION_TOKENS)
    assert all(target.startswith("tests/") for target in targets)
    assert all(target not in {"tests", "tests/"} for target in targets)
    assert all("*" not in target for target in targets)
    assert all(("::" in target) or Path(target).suffix == ".py" for target in targets)


def test_ci_smoke_targets_cover_release_package_and_staged_loading_guards() -> None:
    targets = CI_SMOKE_TEST_TARGETS
    target_set = set(targets)

    assert "tests/test_ci_suite_commands.py" not in target_set
    assert set(REQUIRED_SMOKE_TEST_TARGETS) <= target_set
    assert all(any(target.startswith(prefix) for target in targets) for prefix in REQUIRED_SMOKE_TARGET_PREFIXES)


def test_ci_smoke_job_gates_pytest_execution() -> None:
    assert "smoke" in _job_needs(_workflow_data(), "pytest")


def test_ci_smoke_workflow_skips_shard_resolution_and_collect_only_helpers() -> None:
    workflow = _workflow_data()
    smoke_steps = _job_steps(workflow, "smoke")
    smoke_step_names = [str(step.get("name", "")) for step in smoke_steps]
    smoke_command = _run_steps_by_name(smoke_steps)[CI_SMOKE_PYTEST_STEP_NAME]

    assert CI_SHARD_TARGET_RESOLVER_STEP_NAME not in smoke_step_names
    assert smoke_command == ci_smoke_pytest_command()
    assert all(token not in smoke_command for token in FORBIDDEN_SMOKE_SELECTION_TOKENS)


def test_ci_smoke_package_and_docs_surfaces_match_authoritative_command() -> None:
    expected_command = _normalized_shell_command(ci_smoke_pytest_command())
    smoke_surfaces = {
        "package.json scripts.smoke": _package_smoke_command(),
        "README.md smoke block": _extract_markdown_bash_block(
            "README.md",
            anchor=README_SMOKE_ANCHOR,
        ),
        "CONTRIBUTING.md smoke block": _extract_markdown_bash_block(
            "CONTRIBUTING.md",
            anchor=CONTRIBUTING_SMOKE_ANCHOR,
        ),
    }

    for surface_name, surface_command in smoke_surfaces.items():
        normalized_surface_command = _normalized_shell_command(surface_command)
        assert normalized_surface_command == expected_command, surface_name
        assert _pytest_command_targets(normalized_surface_command) == CI_SMOKE_TEST_TARGETS, surface_name
