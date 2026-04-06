from __future__ import annotations

import ast
from pathlib import Path

import tests.conftest as tests_conftest

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = REPO_ROOT / "tests"
TOP_LEVEL_CONFTEST = TESTS_ROOT / "conftest.py"
EXPECTED_FAST_SUITE_EXCLUDES = {
    "test_bootstrap_installer.py",
    "test_install_lifecycle.py",
    "test_release_consistency.py",
    "test_runtime_cli.py",
    "test_update_workflow.py",
    "hooks/test_notify.py",
    "hooks/test_runtime_detect.py",
    "hooks/test_update_resolution.py",
    "mcp/test_verification_contract_server_regressions.py",
    "core/test_cli.py",
    "core/test_state.py",
    "core/test_resume_runtime.py",
}


def _assigned_literal(path: Path, *, name: str) -> object | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        value_node: ast.AST | None = None
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                value_node = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                value_node = node.value
        if value_node is not None:
            return ast.literal_eval(value_node)
    return None


def test_fast_suite_exclusions_stay_centralized_and_narrow() -> None:
    assert EXPECTED_FAST_SUITE_EXCLUDES <= set(tests_conftest.FAST_SUITE_EXCLUDES)
    assert "core/test_help_inventory_contract.py" not in tests_conftest.FAST_SUITE_EXCLUDES
    assert "core/test_prompt_wiring.py" not in tests_conftest.FAST_SUITE_EXCLUDES
    assert "core/test_prompt_cli_consistency.py" not in tests_conftest.FAST_SUITE_EXCLUDES
    assert "core/test_review_contract_prompt_visibility.py" not in tests_conftest.FAST_SUITE_EXCLUDES
    assert "core/test_workflow_contract_visibility_regressions.py" not in tests_conftest.FAST_SUITE_EXCLUDES


def test_nested_test_conftests_do_not_hide_suites_via_collect_ignore() -> None:
    offenders: list[str] = []

    for path in sorted(TESTS_ROOT.rglob("conftest.py")):
        if path == TOP_LEVEL_CONFTEST:
            continue
        if _assigned_literal(path, name="collect_ignore") is not None:
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []
