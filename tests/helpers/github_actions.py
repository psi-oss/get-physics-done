from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import yaml


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


def load_github_actions_workflow(path: Path) -> dict[str, object]:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=GitHubActionsLoader)

    assert isinstance(data, dict), f"{path} must parse to a mapping"
    assert "on" in data, f"{path} must preserve `on` as a string key"
    assert True not in data, f"{path} parsed the `on` key as a boolean"
    return data


def github_actions_workflow_paths(repo_root: Path) -> list[Path]:
    return sorted((repo_root / ".github" / "workflows").glob("*.yml"))


def load_repo_github_actions_workflow(repo_root: Path, workflow_name: str) -> dict[str, object]:
    return load_github_actions_workflow(repo_root / ".github" / "workflows" / workflow_name)


def workflow_jobs(workflow: dict[str, object]) -> dict[str, object]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    return jobs


def workflow_job(workflow: dict[str, object], job_name: str) -> dict[str, object]:
    job = workflow_jobs(workflow)[job_name]
    assert isinstance(job, dict)
    return job


def workflow_job_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    job = workflow_job(workflow, job_name)
    steps = job["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def iter_workflow_steps(workflow: dict[str, object]) -> Iterator[tuple[str, dict[str, object]]]:
    for job_id, job in workflow_jobs(workflow).items():
        assert isinstance(job_id, str) and job_id
        assert isinstance(job, dict)
        steps = job.get("steps", [])
        assert isinstance(steps, list)
        for step in steps:
            assert isinstance(step, dict)
            yield job_id, step


def workflow_step_by_name(workflow: dict[str, object], job_name: str, step_name: str) -> dict[str, object]:
    for step in workflow_job_steps(workflow, job_name):
        if step.get("name") == step_name:
            return step
    raise AssertionError(f"{job_name} is missing step {step_name!r}")


def workflow_steps_using(workflow: dict[str, object], uses: str) -> list[tuple[str, dict[str, object]]]:
    return [(job_id, step) for job_id, step in iter_workflow_steps(workflow) if step.get("uses") == uses]
