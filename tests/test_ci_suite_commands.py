from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import tests.ci_sharding as ci_sharding
from tests.ci_sharding import assert_ci_workflow_pytest_shard_policy, assert_tests_readme_documents_ci_shard_policy
from tests.helpers.github_actions import load_github_actions_workflow

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
EXPECTED_UV_SETUP_VERSION = "0.9.12"


def _workflow_paths() -> list[Path]:
    return sorted(WORKFLOW_DIR.glob("*.yml"))


def _workflow_data() -> dict[str, object]:
    return load_github_actions_workflow(WORKFLOW_DIR / "test.yml")


def test_all_github_workflows_parse_with_github_actions_shape() -> None:
    workflow_paths = _workflow_paths()

    assert {path.name for path in workflow_paths} == {
        "publish-release.yml",
        "release.yml",
        "staging-rebuild.yml",
        "test.yml",
    }

    for path in workflow_paths:
        workflow = load_github_actions_workflow(path)

        assert isinstance(workflow.get("name"), str), f"{path} must define a workflow name"
        assert isinstance(workflow.get("on"), dict), f"{path} must define GitHub Actions triggers under `on`"
        assert isinstance(workflow.get("permissions"), dict), f"{path} must define explicit permissions"

        jobs = workflow.get("jobs")
        assert isinstance(jobs, dict) and jobs, f"{path} must define at least one job"
        for job_id, job in jobs.items():
            assert isinstance(job_id, str) and job_id, f"{path} has an invalid job id"
            assert isinstance(job, dict), f"{path}:{job_id} must be a mapping"
            assert "runs-on" in job or "uses" in job, f"{path}:{job_id} must be a normal or reusable job"
            steps = job.get("steps")
            if steps is None:
                continue
            assert isinstance(steps, list) and steps, f"{path}:{job_id} steps must be a nonempty list"
            for index, step in enumerate(steps):
                assert isinstance(step, dict), f"{path}:{job_id} step {index} must be a mapping"
                assert "run" in step or "uses" in step, f"{path}:{job_id} step {index} needs `run` or `uses`"


def test_github_actions_loader_preserves_on_key_without_losing_boolean_inputs() -> None:
    workflow = load_github_actions_workflow(WORKFLOW_DIR / "release.yml")
    dry_run = workflow["on"]["workflow_dispatch"]["inputs"]["dry_run"]

    assert "on" in workflow
    assert True not in workflow
    assert dry_run["type"] == "boolean"
    assert dry_run["default"] is False


def test_ci_workflow_runs_human_author_check_on_pull_requests_and_main_pushes() -> None:
    workflow = _workflow_data()
    triggers = workflow["on"]
    jobs = workflow["jobs"]
    human_author_job = jobs["human-authors"]
    steps = human_author_job["steps"]
    step_by_name = {step["name"]: step for step in steps}

    assert triggers["pull_request"]["branches"] == ["main"]
    assert triggers["push"]["branches"] == ["main"]
    assert human_author_job["if"] == "github.event_name == 'pull_request' || github.event_name == 'push'"

    checkout_step = step_by_name["Check out repository"]
    assert checkout_step["uses"] == "actions/checkout@v6"
    assert checkout_step["with"]["fetch-depth"] == 0

    pr_step = step_by_name["Check PR commit attribution uses human authors"]
    assert pr_step["if"] == "github.event_name == 'pull_request'"
    assert pr_step["run"].strip() == 'bash scripts/check-human-authors.sh --range "origin/${{ github.base_ref }}..HEAD"'

    push_step = step_by_name["Check pushed commit attribution uses human authors"]
    assert push_step["if"] == "github.event_name == 'push'"
    assert push_step["env"] == {
        "BEFORE_SHA": "${{ github.event.before }}",
        "HEAD_SHA": "${{ github.sha }}",
    }
    assert 'range="${BEFORE_SHA}..${HEAD_SHA}"' in push_step["run"]
    assert 'bash scripts/check-human-authors.sh --range "$range"' in push_step["run"]


def test_ci_workflow_runs_category_named_runtime_informed_pytest_shards_with_default_parallelism_and_ci_worksteal() -> (
    None
):
    workflow = _workflow_data()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert_ci_workflow_pytest_shard_policy(workflow, pyproject_text=pyproject)


def test_ci_collection_cache_is_repo_and_category_scoped(tmp_path, monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], Path]] = []

    def _fake_checked_in_test_relpaths(*, repo_root: Path | None = None, category: str | None = None) -> tuple[str, ...]:
        if category == "core":
            return ("core/test_sample.py",)
        return ("test_sample.py",)

    def _fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        cwd = kwargs["cwd"]
        assert isinstance(cwd, Path)
        calls.append((tuple(args), cwd))
        if "tests/core/test_sample.py" in args:
            stdout = "tests/core/test_sample.py::test_core\n"
        else:
            stdout = "tests/test_sample.py::test_root\n"
        return SimpleNamespace(stdout=stdout)

    monkeypatch.setattr(ci_sharding, "checked_in_test_relpaths", _fake_checked_in_test_relpaths)
    monkeypatch.setattr(ci_sharding.subprocess, "run", _fake_run)
    ci_sharding._collected_test_inventory_items.cache_clear()
    try:
        first_root = ci_sharding.collected_test_inventory(repo_root=tmp_path, category="root")
        second_root = ci_sharding.collected_test_inventory(repo_root=tmp_path, category="root")
        core = ci_sharding.collected_test_inventory(repo_root=tmp_path, category="core")
        other_root = ci_sharding.collected_test_inventory(repo_root=tmp_path / "other", category="root")
    finally:
        ci_sharding._collected_test_inventory_items.cache_clear()

    assert first_root == second_root == {"test_sample.py": ("tests/test_sample.py::test_root",)}
    assert core == {"core/test_sample.py": ("tests/core/test_sample.py::test_core",)}
    assert other_root == first_root
    assert calls == [
        (
            (
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "tests/test_sample.py",
                "--collect-only",
                "-q",
                "-n",
                "0",
            ),
            tmp_path.resolve(),
        ),
        (
            (
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "tests/core/test_sample.py",
                "--collect-only",
                "-q",
                "-n",
                "0",
            ),
            tmp_path.resolve(),
        ),
        (
            (
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "tests/test_sample.py",
                "--collect-only",
                "-q",
                "-n",
                "0",
            ),
            (tmp_path / "other").resolve(),
        ),
    ]


def test_ci_represents_documented_default_fast_suite_without_duplicate_full_suite_lane() -> None:
    workflow = _workflow_data()
    jobs = workflow["jobs"]
    pytest_job = jobs["pytest"]
    steps = pytest_job["steps"]
    run_pytest_shard = next(step for step in steps if step.get("name") == "Run pytest shard")
    env = run_pytest_shard["env"]
    run_command = run_pytest_shard["run"]

    assert env["GPD_DEFAULT_FAST_SUITE_COMMAND"] == "uv run pytest tests/ -q"
    assert int(env["GPD_FAST_SUITE_BUDGET_SECONDS"]) <= 180
    assert 'timeout "${GPD_FAST_SUITE_BUDGET_SECONDS}s" uv run pytest -q' in run_command
    assert "${PYTEST_TARGETS[@]}" in run_command

    direct_default_suite_pattern = re.compile(r"(?m)^\s*(?:timeout\s+[^\n]+\s+)?uv run pytest tests/ -q\b")
    assert direct_default_suite_pattern.search("uv run pytest tests/ -q")
    assert direct_default_suite_pattern.search("timeout 180s uv run pytest tests/ -q --durations=20")

    direct_default_suite_steps = [
        f"{job_id}:{step.get('name', '<unnamed>')}"
        for job_id, job in jobs.items()
        for step in job.get("steps", [])
        if direct_default_suite_pattern.search(step.get("run", ""))
    ]

    assert direct_default_suite_steps == []


def test_ci_workflow_runs_lightweight_python_compatibility_matrix() -> None:
    workflow = _workflow_data()
    jobs = workflow["jobs"]
    compat_job = jobs["python-compatibility"]
    steps = compat_job["steps"]
    step_by_name = {step["name"]: step for step in steps}

    assert compat_job["name"] == "python compatibility (${{ matrix.python-version }})"
    assert compat_job["runs-on"] == "ubuntu-latest"
    assert compat_job["strategy"]["fail-fast"] is False
    assert compat_job["strategy"]["matrix"]["python-version"] == ["3.12", "3.13"]
    assert step_by_name["Check out repository"]["uses"] == "actions/checkout@v6"
    assert step_by_name["Set up Python"]["uses"] == "actions/setup-python@v6"
    assert step_by_name["Set up Python"]["with"]["python-version"] == "${{ matrix.python-version }}"
    assert step_by_name["Set up Node.js"]["uses"] == "actions/setup-node@v6"
    assert step_by_name["Set up Node.js"]["with"]["node-version"] == "20"
    assert step_by_name["Set up uv"]["uses"] == "astral-sh/setup-uv@v7"
    assert step_by_name["Set up uv"]["with"] == {"version": EXPECTED_UV_SETUP_VERSION}
    assert step_by_name["Install dependencies"]["run"] == "uv sync --dev --frozen"

    import_smoke = step_by_name["Import package surfaces"]["run"]
    assert "importlib.import_module(module)" in import_smoke
    assert '"gpd.cli"' in import_smoke
    assert '"gpd.core.artifact_text"' in import_smoke
    assert '"gpd.mcp.paper.compiler"' in import_smoke
    assert '"gpd.mcp.servers.arxiv_bridge"' in import_smoke

    console_smoke = step_by_name["Smoke console script"]["run"]
    assert "uv run gpd --version" in console_smoke
    assert "uv run gpd --help > /tmp/gpd-help.txt" in console_smoke
    assert "test -s /tmp/gpd-help.txt" in console_smoke

    targeted_tests = step_by_name["Run installer and runtime compatibility tests"]["run"]
    assert "tests/test_runtime_catalog_bootstrap_contract.py" in targeted_tests
    assert "tests/test_runtime_install_smoke.py" in targeted_tests
    assert "tests/test_install_lifecycle.py::test_markdown_command_runtime_lifecycle_round_trip" in targeted_tests
    assert "test_bootstrap_prefers_versioned_python_when_generic_alias_is_newer" in targeted_tests
    assert "test_bootstrap_recreates_managed_env_when_selected_minor_changes" in targeted_tests
    assert "uv run pytest -q tests/" not in targeted_tests
    assert step_by_name["Build wheel"]["run"] == "uv build --wheel --out-dir dist/compat-${{ matrix.python-version }}"


def test_ci_workflow_uses_current_action_versions() -> None:
    workflow = _workflow_data()
    action_uses = [step["uses"] for job in workflow["jobs"].values() for step in job.get("steps", []) if "uses" in step]

    assert "actions/checkout@v6" in action_uses
    assert "actions/setup-node@v6" in action_uses
    assert "actions/checkout@v5" not in action_uses
    assert "actions/setup-node@v5" not in action_uses


def test_github_workflows_pin_setup_uv_tool_version() -> None:
    setup_uv_step_count = 0
    for path in _workflow_paths():
        workflow = load_github_actions_workflow(path)
        setup_uv_steps = [
            step
            for job in workflow["jobs"].values()
            for step in job.get("steps", [])
            if step.get("uses") == "astral-sh/setup-uv@v7"
        ]
        setup_uv_step_count += len(setup_uv_steps)

        for step in setup_uv_steps:
            assert step.get("with") == {"version": EXPECTED_UV_SETUP_VERSION}, path.name

    assert setup_uv_step_count > 0


def test_ci_workflow_installs_dev_dependencies_from_frozen_lockfile() -> None:
    workflow = _workflow_data()
    jobs = workflow["jobs"]
    install_commands_by_job: dict[str, list[str]] = {}

    for job_id, job in jobs.items():
        for step in job.get("steps", []):
            if step.get("name") == "Install dependencies":
                install_commands_by_job.setdefault(str(job_id), []).append(step["run"])

    assert {"ruff", "python-compatibility", "pytest"} <= set(install_commands_by_job)
    for job_id, install_commands in install_commands_by_job.items():
        assert install_commands, f"{job_id} must have at least one matching install step"
        for install_command in install_commands:
            assert install_command == "uv sync --dev --frozen", f"{job_id} install must use the frozen lockfile"


def test_tests_readme_documents_default_full_suite_and_category_named_runtime_informed_ci_shards() -> None:
    tests_readme = (REPO_ROOT / "tests" / "README.md").read_text(encoding="utf-8")

    assert_tests_readme_documents_ci_shard_policy(tests_readme)
