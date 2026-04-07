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


def test_ci_workflow_runs_fast_and_full_pytest_suites_with_default_parallelism_and_ci_loadscope() -> None:
    workflow = _workflow_data()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    steps = _job_steps(workflow, "pytest")

    step_names = [str(step.get("name", "")) for step in steps]
    run_steps = {str(step.get("name", "")): str(step.get("run", "")) for step in steps if "run" in step}

    assert "Set up Node.js" in step_names
    assert step_names.index("Set up Node.js") < step_names.index("Install dependencies")
    assert run_steps["Run fast test suite"] == "uv run pytest tests/ -q --dist=loadscope"
    assert run_steps["Run complementary heavy suite"].startswith("HEAVY_SUITE_IGNORE_ARGS=")
    assert "from tests.conftest import complementary_heavy_suite_ignore_args" in run_steps[
        "Run complementary heavy suite"
    ]
    assert "uv run pytest tests/ -q --full-suite --dist=loadscope $HEAVY_SUITE_IGNORE_ARGS" in run_steps[
        "Run complementary heavy suite"
    ]
    assert "--full-suite" in run_steps["Run complementary heavy suite"]
    assert steps[-2]["name"] == "Run fast test suite"
    assert steps[-1]["name"] == "Run complementary heavy suite"
    assert steps[-2]["run"] == "uv run pytest tests/ -q --dist=loadscope"
    assert "complementary_heavy_suite_ignore_args" in steps[-1]["run"]
    assert steps[2]["uses"] == "actions/setup-node@v6"
    assert steps[2]["with"]["node-version"] == "20"
    assert 'addopts = "-n auto"' not in pyproject
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
    assert "`uv run pytest tests/ -q --dist=loadscope`" in tests_readme
    assert "The GitHub Actions workflow runs the complementary heavy suite with `--full-suite` plus the shared ignore helper" in tests_readme
