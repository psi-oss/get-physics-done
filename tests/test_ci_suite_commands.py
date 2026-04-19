from __future__ import annotations

from pathlib import Path

import yaml

from tests.ci_sharding import assert_ci_workflow_pytest_shard_policy, assert_tests_readme_documents_ci_shard_policy

REPO_ROOT = Path(__file__).resolve().parent.parent


def _workflow_data() -> dict[str, object]:
    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8"))


def test_ci_workflow_runs_category_named_runtime_informed_pytest_shards_with_default_parallelism_and_ci_worksteal() -> None:
    workflow = _workflow_data()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert_ci_workflow_pytest_shard_policy(workflow, pyproject_text=pyproject)


def test_tests_readme_documents_default_full_suite_and_category_named_runtime_informed_ci_shards() -> None:
    tests_readme = (REPO_ROOT / "tests" / "README.md").read_text(encoding="utf-8")

    assert_tests_readme_documents_ci_shard_policy(tests_readme)
