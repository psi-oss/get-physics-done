from __future__ import annotations

import re
from pathlib import Path

import yaml

from tests.ci_sharding import assert_ci_workflow_pytest_shard_policy, assert_tests_readme_documents_ci_shard_policy

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"


class GitHubActionsLoader(yaml.SafeLoader):
    """PyYAML loader compatible with GitHub Actions' YAML 1.2-style `on` key."""


GitHubActionsLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
GitHubActionsLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def _load_github_actions_workflow(path: Path) -> dict[str, object]:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=GitHubActionsLoader)
    assert isinstance(data, dict), f"{path} must parse to a mapping"
    return data


def _workflow_paths() -> list[Path]:
    return sorted(WORKFLOW_DIR.glob("*.yml"))


def _workflow_data() -> dict[str, object]:
    return _load_github_actions_workflow(WORKFLOW_DIR / "test.yml")


def test_all_github_workflows_parse_with_github_actions_shape() -> None:
    workflow_paths = _workflow_paths()

    assert {path.name for path in workflow_paths} == {
        "publish-release.yml",
        "release.yml",
        "staging-rebuild.yml",
        "test.yml",
    }

    for path in workflow_paths:
        workflow = _load_github_actions_workflow(path)

        assert True not in workflow, f"{path} parsed the `on` key as a boolean"
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
    workflow = _load_github_actions_workflow(WORKFLOW_DIR / "release.yml")
    dry_run = workflow["on"]["workflow_dispatch"]["inputs"]["dry_run"]

    assert "on" in workflow
    assert True not in workflow
    assert dry_run["type"] == "boolean"
    assert dry_run["default"] is False


def test_ci_workflow_runs_category_named_runtime_informed_pytest_shards_with_default_parallelism_and_ci_worksteal() -> (
    None
):
    workflow = _workflow_data()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert_ci_workflow_pytest_shard_policy(workflow, pyproject_text=pyproject)


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


def test_ci_workflow_installs_dev_dependencies_from_frozen_lockfile() -> None:
    workflow = _workflow_data()
    jobs = workflow["jobs"]
    install_commands: list[str] = []

    for job in jobs.values():
        for step in job.get("steps", []):
            if step.get("name") == "Install dependencies":
                install_commands.append(step["run"])

    assert install_commands == ["uv sync --dev --frozen", "uv sync --dev --frozen", "uv sync --dev --frozen"]


def test_tests_readme_documents_default_full_suite_and_category_named_runtime_informed_ci_shards() -> None:
    tests_readme = (REPO_ROOT / "tests" / "README.md").read_text(encoding="utf-8")

    assert_tests_readme_documents_ci_shard_policy(tests_readme)
