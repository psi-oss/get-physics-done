from __future__ import annotations

from pathlib import Path

import yaml

from tests.ci_sharding import ci_shard_specs
from tests.phase16_projection_oracle_helpers import phase16_case_keys

REPO_ROOT = Path(__file__).resolve().parent.parent
NIGHTLY_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "nightly-handoff-bundle.yml"
TEST_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "test.yml"

PILOT_CASE_KEYS = (
    "completed-phase/positive",
    "empty-phase/mutation",
    "query-registry-drift/positive",
    "summary-missing-return/mutation",
    "resume-recent-noise/mutation",
    "placeholder-conventions/mutation",
    "bridge-vs-cli/mutation",
)


def _load_workflow(path: Path) -> dict[str, object]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)
    return workflow


def _workflow_on_block(workflow: dict[str, object]) -> dict[str, object]:
    on_block = workflow.get("on")
    if on_block is None:
        on_block = workflow.get(True)
    assert isinstance(on_block, dict)
    return on_block


def _workflow_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def _case_keys(raw: str) -> tuple[str, ...]:
    return tuple(line for line in raw.splitlines() if line)


def test_nightly_handoff_bundle_workflow_is_scheduled_read_only_and_explicit_about_registry_and_benchmarks() -> None:
    workflow = _load_workflow(NIGHTLY_WORKFLOW_PATH)
    workflow_text = NIGHTLY_WORKFLOW_PATH.read_text(encoding="utf-8")

    on_block = _workflow_on_block(workflow)
    assert set(on_block) == {"schedule", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}

    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    assert set(jobs) == {"benchmark-slices"}

    job = jobs["benchmark-slices"]
    assert isinstance(job, dict)
    assert job["runs-on"] == "ubuntu-latest"
    assert job["strategy"]["fail-fast"] is False
    assert job["strategy"]["max-parallel"] == 1
    assert job["env"]["PHASE17_THRESHOLD_FILE"] == "benchmarks/phase17_thresholds.json"

    matrix_include = job["strategy"]["matrix"]["include"]
    assert isinstance(matrix_include, list)
    assert len(matrix_include) == 2
    assert tuple(entry["mode"] for entry in matrix_include) == ("pilot", "full")
    for entry in matrix_include:
        assert tuple(sorted(entry)) == ("case_keys", "mode")

    pilot_entry, full_entry = matrix_include
    assert _case_keys(pilot_entry["case_keys"]) == PILOT_CASE_KEYS
    assert _case_keys(full_entry["case_keys"]) == phase16_case_keys()

    steps = _workflow_steps(workflow, "benchmark-slices")
    step_names = [str(step.get("name", "")) for step in steps]
    assert step_names == [
        "Check out repository",
        "Set up Python",
        "Set up Node.js",
        "Set up uv",
        "Install dependencies",
        "Validate nightly registry slice",
        "Run explicit nightly benchmark modules",
    ]

    validation_command = str(steps[5]["run"])
    benchmark_command = str(steps[6]["run"])
    assert "from tests.phase16_projection_oracle_helpers import phase16_case_keys" in validation_command
    assert "pilot_case_keys = (" in validation_command
    assert 'expected_case_keys = pilot_case_keys if mode == "pilot" else full_case_keys' in validation_command
    assert "uv run pytest -q -n 0" in benchmark_command
    assert "benchmarks/test_resume_recent.py" in benchmark_command
    assert "benchmarks/test_query_index_freshness.py" in benchmark_command
    assert "benchmarks/test_phase_projection_latency.py" in benchmark_command
    assert "benchmarks/test_checkpoint_batch.py" in benchmark_command
    assert "tests/" not in benchmark_command

    assert "npm publish" not in workflow_text
    assert "twine upload" not in workflow_text
    assert "gh release" not in workflow_text
    assert "publish-release" not in workflow_text
    assert "trigger-staging-rebuild" not in workflow_text


def test_nightly_handoff_bundle_workflow_keeps_compatible_ci_topology_shape() -> None:
    nightly_workflow = _load_workflow(NIGHTLY_WORKFLOW_PATH)
    ci_workflow = _load_workflow(TEST_WORKFLOW_PATH)

    ci_jobs = ci_workflow["jobs"]
    assert isinstance(ci_jobs, dict)
    pytest_job = ci_jobs["pytest"]
    assert isinstance(pytest_job, dict)
    include = pytest_job["strategy"]["matrix"]["include"]
    assert isinstance(include, list)
    assert tuple(
        (
            str(entry["display_name"]),
            str(entry["category"]),
            int(entry["shard_index"]),
            int(entry["shard_total"]),
        )
        for entry in include
    ) == tuple((spec.display_name, spec.category, spec.shard_index, spec.shard_total) for spec in ci_shard_specs())

    nightly_jobs = nightly_workflow["jobs"]
    assert isinstance(nightly_jobs, dict)
    nightly_job = nightly_jobs["benchmark-slices"]
    assert isinstance(nightly_job, dict)
    nightly_include = nightly_job["strategy"]["matrix"]["include"]
    assert isinstance(nightly_include, list)
    assert all("category" not in entry for entry in nightly_include)
    assert all("shard_index" not in entry for entry in nightly_include)
    assert all("shard_total" not in entry for entry in nightly_include)
