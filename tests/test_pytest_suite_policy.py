from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from tests.conftest import (
    _FAST_SUITE_ENV_VAR,
    FAST_SUITE_EXCLUDES,
    _explicit_collection_requested,
    _full_suite_requested,
    complementary_heavy_suite_ignore_args,
)


def _read(relpath: str) -> str:
    return (Path(__file__).resolve().parent / relpath).read_text(encoding="utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _all_test_paths() -> tuple[str, ...]:
    tests_root = _repo_root() / "tests"
    return tuple(path.relative_to(tests_root).as_posix() for path in sorted(tests_root.rglob("test_*.py")))


def _workflow_data() -> dict[str, object]:
    return yaml.safe_load((_repo_root() / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8"))


def _workflow_job_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def test_fast_suite_policy_is_centralized_in_root_conftest() -> None:
    root_conftest = _read("conftest.py")
    core_conftest = _read("core/conftest.py")

    assert "FAST_SUITE_EXCLUDES" in root_conftest
    assert "--full-suite" in root_conftest
    assert _FAST_SUITE_ENV_VAR in root_conftest
    assert "collect_ignore" not in core_conftest


def test_full_suite_toggle_accepts_cli_or_env() -> None:
    assert _full_suite_requested(cli_flag=True, env_value=None) is True
    assert _full_suite_requested(cli_flag=False, env_value="1") is True
    assert _full_suite_requested(cli_flag=False, env_value="true") is True
    assert _full_suite_requested(cli_flag=False, env_value="yes") is True
    assert _full_suite_requested(cli_flag=False, env_value=None) is False
    assert _full_suite_requested(cli_flag=False, env_value="0") is False


def test_fast_suite_policy_keeps_heavyweight_skips_explicit() -> None:
    expected = {
        "test_bootstrap_installer.py",
        "test_install_lifecycle.py",
        "test_runtime_cli.py",
        "hooks/test_notify.py",
        "mcp/test_verification_contract_server_regressions.py",
        "core/test_cli.py",
        "core/test_state.py",
    }

    assert expected <= FAST_SUITE_EXCLUDES


def test_fast_suite_policy_keeps_boundary_regressions_in_default_path() -> None:
    required = {
        "core/test_contract_validation_smoke.py",
        "core/test_executor_prompt_contract_visibility.py",
        "core/test_frontmatter_smoke.py",
        "core/test_review_contract_prompt_visibility.py",
        "core/test_plan_contract_prompt_visibility_regressions.py",
        "test_project_contract_boundary_regressions.py",
        "test_runtime_abstraction_boundaries.py",
        "core/test_contract_schema_prompt_parity.py",
        "core/test_verification_contract_evidence.py",
        "mcp/test_tool_contract_visibility.py",
        "core/test_verifier_prompt_contract_visibility.py",
        "core/test_verification_surface_alignment_regressions.py",
    }

    assert required.isdisjoint(FAST_SUITE_EXCLUDES)


def test_ci_and_test_readme_document_explicit_fast_and_full_suite_commands() -> None:
    repo_root = _repo_root()
    workflow = _workflow_data()
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    tests_readme = (repo_root / "tests" / "README.md").read_text(encoding="utf-8")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    pytest_fast_steps = _workflow_job_steps(workflow, "pytest-fast")
    pytest_heavy_steps = _workflow_job_steps(workflow, "pytest-heavy")
    fast_step_names = [str(step.get("name", "")) for step in pytest_fast_steps]
    fast_run_steps = {
        str(step.get("name", "")): str(step.get("run", ""))
        for step in pytest_fast_steps
        if "run" in step
    }
    heavy_step_names = [str(step.get("name", "")) for step in pytest_heavy_steps]
    heavy_run_steps = {
        str(step.get("name", "")): str(step.get("run", ""))
        for step in pytest_heavy_steps
        if "run" in step
    }

    assert jobs["pytest-fast"].get("needs") is None
    assert jobs["pytest-heavy"].get("needs") is None
    trigger_job = jobs["trigger-staging-rebuild"]
    assert isinstance(trigger_job, dict)
    assert trigger_job["needs"] == ["pytest-fast", "pytest-heavy"]

    assert "Set up Node.js" in fast_step_names
    assert fast_step_names.index("Set up Node.js") < fast_step_names.index("Install dependencies")
    fast_suite_command = fast_run_steps["Run fast test suite"]
    assert fast_suite_command == "uv run pytest tests/ -q"
    assert 'addopts = "-n auto --dist=worksteal"' in pyproject
    assert 'pytest-xdist>=3.8.0' in pyproject
    assert "--full-suite" not in fast_suite_command
    assert "Set up Node.js" in heavy_step_names
    assert heavy_step_names.index("Set up Node.js") < heavy_step_names.index("Install dependencies")
    heavy_suite_command = heavy_run_steps["Run complementary heavy suite"]
    assert "from tests.conftest import complementary_heavy_suite_ignore_args" in heavy_suite_command
    assert 'HEAVY_SUITE_IGNORE_ARGS="$(' in heavy_suite_command
    assert "uv run pytest tests/ -q" in heavy_suite_command
    assert "--full-suite" in heavy_suite_command
    assert "$HEAVY_SUITE_IGNORE_ARGS" in heavy_suite_command
    assert "-n auto" not in heavy_suite_command
    assert "--dist=worksteal" not in heavy_suite_command
    assert "Default `uv run pytest tests/ -q` uses the fast daily suite declared in `tests/conftest.py`" in tests_readme
    assert "inherits `-n auto --dist=worksteal` from `pyproject.toml`" in tests_readme
    assert "override that default explicitly with `uv run pytest tests/ -q -n 0`" in tests_readme
    assert "GitHub Actions workflow runs the fast and complementary heavy suites as separate jobs" in tests_readme
    assert "heavy job using `--full-suite` and the shared ignore helper" in tests_readme
    assert "tests/core/test_review_contract_prompt_visibility.py" in tests_readme
    assert complementary_heavy_suite_ignore_args() == tuple(
        f"--ignore=tests/{rel_path}" for rel_path in _all_test_paths() if rel_path not in FAST_SUITE_EXCLUDES
    )


def test_explicit_collection_is_not_treated_as_fast_suite_blacklisting() -> None:
    collection_path = Path(__file__).resolve().parent / "core" / "test_state.py"
    config = SimpleNamespace(
        invocation_params=SimpleNamespace(args=[str(collection_path)]),
    )

    assert _explicit_collection_requested(collection_path.resolve(strict=False), config) is True


def test_k_expression_value_is_not_treated_as_a_collection_root() -> None:
    collection_path = Path(__file__).resolve().parent / "core" / "test_state.py"
    config = SimpleNamespace(
        invocation_params=SimpleNamespace(
            args=[
                "tests/test_runtime_abstraction_boundaries.py",
                "-k",
                "public_surface_contract or runtime_catalog or managed_virtualenv",
            ]
        ),
    )

    assert _explicit_collection_requested(collection_path.resolve(strict=False), config) is False
