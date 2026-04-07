from __future__ import annotations

from pathlib import Path

import yaml

from tests.conftest import FAST_SUITE_EXCLUDES, complementary_heavy_suite_ignore_args

REPO_ROOT = Path(__file__).resolve().parent.parent


def _workflow_data() -> dict[str, object]:
    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8"))


def _job_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def test_ci_workflow_runs_fast_and_full_pytest_suites_with_default_parallelism_and_ci_worksteal() -> None:
    workflow = _workflow_data()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    fast_steps = _job_steps(workflow, "pytest-fast")
    heavy_steps = _job_steps(workflow, "pytest-heavy")

    fast_step_names = [str(step.get("name", "")) for step in fast_steps]
    fast_run_steps = {str(step.get("name", "")): str(step.get("run", "")) for step in fast_steps if "run" in step}
    heavy_step_names = [str(step.get("name", "")) for step in heavy_steps]
    heavy_run_steps = {str(step.get("name", "")): str(step.get("run", "")) for step in heavy_steps if "run" in step}

    assert jobs["pytest-fast"].get("needs") is None
    assert jobs["pytest-heavy"].get("needs") is None
    trigger_job = jobs["trigger-staging-rebuild"]
    assert isinstance(trigger_job, dict)
    assert trigger_job["needs"] == ["pytest-fast", "pytest-heavy"]

    assert "Set up Node.js" in fast_step_names
    assert fast_step_names.index("Set up Node.js") < fast_step_names.index("Install dependencies")
    fast_suite_command = fast_run_steps["Run fast test suite"]
    assert fast_suite_command == "uv run pytest tests/ -q"
    assert fast_steps[-1]["name"] == "Run fast test suite"
    assert fast_steps[-1]["run"] == fast_suite_command

    assert "Set up Node.js" in heavy_step_names
    assert heavy_step_names.index("Set up Node.js") < heavy_step_names.index("Install dependencies")
    assert heavy_run_steps["Run complementary heavy suite"].startswith("HEAVY_SUITE_IGNORE_ARGS=")
    assert "from tests.conftest import complementary_heavy_suite_ignore_args" in heavy_run_steps[
        "Run complementary heavy suite"
    ]
    heavy_suite_command = heavy_run_steps["Run complementary heavy suite"]
    assert "uv run pytest tests/ -q" in heavy_suite_command
    assert "--full-suite" in heavy_suite_command
    assert "$HEAVY_SUITE_IGNORE_ARGS" in heavy_suite_command
    assert "-n auto" not in heavy_suite_command
    assert "--dist=worksteal" not in heavy_suite_command
    assert heavy_steps[-1]["name"] == "Run complementary heavy suite"
    assert "complementary_heavy_suite_ignore_args" in heavy_steps[-1]["run"]
    assert fast_steps[2]["uses"] == "actions/setup-node@v6"
    assert fast_steps[2]["with"]["node-version"] == "20"
    assert heavy_steps[2]["uses"] == "actions/setup-node@v6"
    assert heavy_steps[2]["with"]["node-version"] == "20"
    assert 'addopts = "-n auto --dist=worksteal"' in pyproject
    assert 'pytest-xdist>=3.8.0' in pyproject
    assert complementary_heavy_suite_ignore_args() == tuple(
        f"--ignore=tests/{rel_path}"
        for rel_path in sorted(
            path.relative_to(REPO_ROOT / "tests").as_posix()
            for path in (REPO_ROOT / "tests").rglob("test_*.py")
            if path.relative_to(REPO_ROOT / "tests").as_posix() not in FAST_SUITE_EXCLUDES
        )
    )


def test_tests_readme_documents_fast_and_full_suite_entrypoints() -> None:
    tests_readme = (REPO_ROOT / "tests" / "README.md").read_text(encoding="utf-8")

    assert "Default `uv run pytest tests/ -q` uses the fast daily suite declared in" in tests_readme
    assert "inherits `-n auto --dist=worksteal` from `pyproject.toml`" in tests_readme
    assert "override that default explicitly with `uv run pytest tests/ -q -n 0`" in tests_readme
    assert "The GitHub Actions workflow runs the fast and complementary heavy suites as separate jobs" in tests_readme
    assert "heavy job using `--full-suite` and the shared ignore helper" in tests_readme
