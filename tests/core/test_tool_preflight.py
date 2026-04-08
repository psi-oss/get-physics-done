from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.frontmatter import compute_knowledge_reviewed_content_sha256
from gpd.core.tool_preflight import (
    PlanToolPreflightError,
    build_plan_tool_preflight,
    parse_plan_tool_requirements,
)


def _write_tool_requirement_plan(plan_path: Path, command: str, *, plan_id: str) -> None:
    plan_path.write_text(
        "---\n"
        "phase: 01-test\n"
        f"plan: {plan_id}\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "tool_requirements:\n"
        "  - id: solver\n"
        "    tool: command\n"
        f"    command: {json.dumps(command)}\n"
        "    purpose: Run external solver\n"
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: What benchmark must this plan recover?\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-main]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
        "  claims:\n"
        "    - id: claim-main\n"
        "      statement: Recover the benchmark value within tolerance\n"
        "      deliverables: [deliv-main]\n"
        "      acceptance_tests: [test-main]\n"
        "      references: [ref-main]\n"
        "  deliverables:\n"
        "    - id: deliv-main\n"
        "      kind: figure\n"
        "      path: figures/main.png\n"
        "      description: Main benchmark figure\n"
        "  references:\n"
        "    - id: ref-main\n"
        "      kind: paper\n"
        "      locator: Author et al., Journal, 2024\n"
        "      role: benchmark\n"
        "      why_it_matters: Published comparison target\n"
        "      applies_to: [claim-main]\n"
        "      must_surface: true\n"
        "      required_actions: [read, compare, cite]\n"
        "  acceptance_tests:\n"
        "    - id: test-main\n"
        "      subject: claim-main\n"
        "      kind: benchmark\n"
        "      procedure: Compare against the benchmark reference\n"
        "      pass_condition: Matches reference within tolerance\n"
        "      evidence_required: [deliv-main, ref-main]\n"
        "  forbidden_proxies:\n"
        "    - id: fp-main\n"
        "      subject: claim-main\n"
        "      proxy: Qualitative trend match without numerical comparison\n"
        "      reason: Would allow false progress without the decisive benchmark\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )


def _write_knowledge_doc(
    tmp_path: Path,
    *,
    knowledge_id: str,
    status: str = "stable",
    superseded_by: str | None = None,
    stale: bool = False,
) -> Path:
    knowledge_dir = tmp_path / "GPD" / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    path = knowledge_dir / f"{knowledge_id}.md"
    base_content = (
        "---\n"
        "knowledge_schema_version: 1\n"
        f"knowledge_id: {knowledge_id}\n"
        "title: Knowledge Dependency Fixture\n"
        "topic: dependency-testing\n"
        f"status: {status}\n"
        "created_at: 2026-04-07T12:00:00Z\n"
        "updated_at: 2026-04-07T12:00:00Z\n"
        "sources:\n"
        "  - source_id: source-main\n"
        "    kind: paper\n"
        "    locator: Author et al., 2026\n"
        "    title: Benchmark Reference\n"
        "    why_it_matters: Trusted source for the topic\n"
        "coverage_summary:\n"
        "  covered_topics: [dependency-testing]\n"
        "  excluded_topics: [implementation]\n"
        "  open_gaps: [none]\n"
    )
    if superseded_by is not None:
        base_content += f"superseded_by: {superseded_by}\n"
    base_content += "---\n\nTrusted knowledge body.\n"
    reviewed_content_sha256 = compute_knowledge_reviewed_content_sha256(base_content)
    if status in {"stable", "in_review", "superseded"}:
        content = base_content.replace(
            "---\n\n",
            (
                "review:\n"
                "  reviewed_at: 2026-04-07T13:00:00Z\n"
                "  review_round: 1\n"
                "  reviewer_kind: workflow\n"
                "  reviewer_id: gpd-review-knowledge\n"
                "  decision: approved\n"
                "  summary: Stable review approved.\n"
                f"  approval_artifact_path: GPD/knowledge/reviews/{knowledge_id}-R1-REVIEW.md\n"
                f"  approval_artifact_sha256: {'a' * 64}\n"
                f"  reviewed_content_sha256: {reviewed_content_sha256}\n"
                f"  stale: {'true' if stale else 'false'}\n"
                "---\n\n"
            ),
        )
    else:
        content = base_content
    path.write_text(content, encoding="utf-8")
    return path


def _plan_with_knowledge_controls(
    *,
    knowledge_gate: str | None = None,
    knowledge_deps: list[str] | None = None,
) -> str:
    fixture = (
        Path(__file__).resolve().parents[1] / "fixtures" / "stage0" / "plan_with_contract.md"
    ).read_text(encoding="utf-8")
    metadata_block = ""
    if knowledge_gate is not None:
        metadata_block += f"knowledge_gate: {knowledge_gate}\n"
    if knowledge_deps is not None:
        metadata_block += "knowledge_deps:\n"
        for dep in knowledge_deps:
            metadata_block += f"  - {dep}\n"
    return fixture.replace("interactive: false\n", f"interactive: false\n{metadata_block}", 1)


def test_parse_plan_tool_requirements_normalizes_mathematica_alias() -> None:
    requirements = parse_plan_tool_requirements(
        [
            {
                "id": "cas-main",
                "tool": "mathematica",
                "purpose": "Symbolic tensor reduction",
                "fallback": "Use SymPy if unavailable",
            }
        ]
    )

    assert requirements[0].tool == "wolfram"


def test_parse_plan_tool_requirements_requires_command_for_command_tool() -> None:
    with pytest.raises(PlanToolPreflightError, match="command tool requires a non-empty command"):
        parse_plan_tool_requirements(
            [
                {
                    "id": "custom-main",
                    "tool": "command",
                    "purpose": "Run external solver",
                }
            ]
        )


def test_parse_plan_tool_requirements_treats_empty_list_as_no_requirements() -> None:
    assert parse_plan_tool_requirements([]) == []


def test_parse_plan_tool_requirements_rejects_duplicate_ids() -> None:
    with pytest.raises(PlanToolPreflightError, match=r"tool_requirements\[\]\.id values must be unique"):
        parse_plan_tool_requirements(
            [
                {
                    "id": "shared-check",
                    "tool": "wolfram",
                    "purpose": "Symbolic tensor reduction",
                },
                {
                    "id": "shared-check",
                    "tool": "command",
                    "command": "python --version",
                    "purpose": "Run a local command",
                },
            ]
        )


def test_build_plan_tool_preflight_without_requirements_passes(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        "---\n"
        "phase: 01-test\n"
        "plan: 01\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: What benchmark must this plan recover?\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-main]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
        "  claims:\n"
        "    - id: claim-main\n"
        "      statement: Recover the benchmark value within tolerance\n"
        "      deliverables: [deliv-main]\n"
        "      acceptance_tests: [test-main]\n"
        "      references: [ref-main]\n"
        "  deliverables:\n"
        "    - id: deliv-main\n"
        "      kind: figure\n"
        "      path: figures/main.png\n"
        "      description: Main benchmark figure\n"
        "  references:\n"
        "    - id: ref-main\n"
        "      kind: paper\n"
        "      locator: Author et al., Journal, 2024\n"
        "      role: benchmark\n"
        "      why_it_matters: Published comparison target\n"
        "      applies_to: [claim-main]\n"
        "      must_surface: true\n"
        "      required_actions: [read, compare, cite]\n"
        "  acceptance_tests:\n"
        "    - id: test-main\n"
        "      subject: claim-main\n"
        "      kind: benchmark\n"
        "      procedure: Compare against the benchmark reference\n"
        "      pass_condition: Matches reference within tolerance\n"
        "      evidence_required: [deliv-main, ref-main]\n"
        "  forbidden_proxies:\n"
        "    - id: fp-main\n"
        "      subject: claim-main\n"
        "      proxy: Qualitative trend match without numerical comparison\n"
        "      reason: Would allow false progress without the decisive benchmark\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is True
    assert result.requirements == []
    assert result.guidance == "No machine-checkable specialized tool requirements declared."


def test_build_plan_tool_preflight_keeps_knowledge_gate_off_silent(
    tmp_path: Path,
) -> None:
    _write_knowledge_doc(tmp_path, knowledge_id="K-dependency-off", status="draft")
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        _plan_with_knowledge_controls(
            knowledge_gate="off",
            knowledge_deps=["K-dependency-off"],
        ),
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is True
    assert result.knowledge_gate == "off"
    assert result.knowledge_deps == ["K-dependency-off"]
    assert result.knowledge_dependency_checks == []
    assert result.warnings == []
    assert result.blocking_conditions == []


def test_build_plan_tool_preflight_warns_but_does_not_fail_on_missing_knowledge_dependency(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        _plan_with_knowledge_controls(
            knowledge_gate="warn",
            knowledge_deps=["K-missing-dependency"],
        ),
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is True
    assert result.knowledge_gate == "warn"
    assert result.knowledge_dependency_checks[0].status == "missing"
    assert result.knowledge_dependency_checks[0].blocking is False
    assert any("K-missing-dependency" in warning for warning in result.warnings)
    assert result.blocking_conditions == []


def test_build_plan_tool_preflight_blocks_on_superseded_knowledge_dependency(
    tmp_path: Path,
) -> None:
    _write_knowledge_doc(tmp_path, knowledge_id="K-next", status="stable")
    _write_knowledge_doc(
        tmp_path,
        knowledge_id="K-legacy",
        status="superseded",
        superseded_by="K-next",
    )
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        _plan_with_knowledge_controls(
            knowledge_gate="block",
            knowledge_deps=["K-legacy"],
        ),
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.knowledge_gate == "block"
    assert result.knowledge_dependency_checks[0].status == "superseded"
    assert result.knowledge_dependency_checks[0].blocking is True
    assert result.knowledge_dependency_checks[0].successor == "K-next"
    assert result.blocking_conditions[0].startswith("K-legacy:")
    assert "superseded by K-next" in result.warnings[0]


def test_build_plan_tool_preflight_combines_tool_blockers_and_knowledge_warnings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda _name: None)
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "knowledge_gate: warn\n"
            "knowledge_deps:\n"
            "  - K-missing-dependency\n"
            "tool_requirements:\n"
            "  - id: wolfram-cas\n"
            "    tool: wolfram\n"
            "    purpose: Symbolic tensor reduction\n"
            "    required: true\n"
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "contract:\n"
            "  schema_version: 1\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  context_intake:\n"
            "    must_read_refs: [ref-main]\n"
            "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value within tolerance\n"
            "      deliverables: [deliv-main]\n"
            "      acceptance_tests: [test-main]\n"
            "      references: [ref-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main benchmark figure\n"
            "  references:\n"
            "    - id: ref-main\n"
            "      kind: paper\n"
            "      locator: Author et al., Journal, 2024\n"
            "      role: benchmark\n"
            "      why_it_matters: Published comparison target\n"
            "      applies_to: [claim-main]\n"
            "      must_surface: true\n"
            "      required_actions: [read, compare, cite]\n"
            "  acceptance_tests:\n"
            "    - id: test-main\n"
            "      subject: claim-main\n"
            "      kind: benchmark\n"
            "      procedure: Compare against the benchmark reference\n"
            "      pass_condition: Matches reference within tolerance\n"
            "      evidence_required: [deliv-main, ref-main]\n"
            "  forbidden_proxies:\n"
            "    - id: fp-main\n"
            "      subject: claim-main\n"
            "      proxy: Qualitative trend match without numerical comparison\n"
            "      reason: Would allow false progress without the decisive benchmark\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
            "---\n\n"
            "Body.\n"
        ),
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert any(check.blocking for check in result.checks)
    assert result.knowledge_dependency_checks[0].status == "missing"
    assert any("K-missing-dependency" in warning for warning in result.warnings)
    assert any("wolframscript not found on PATH" in blocker for blocker in result.blocking_conditions)


def test_build_plan_tool_preflight_rejects_duplicate_requirement_ids(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        "---\n"
        "phase: 01-test\n"
        "plan: 01\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "tool_requirements:\n"
        "  - tool: wolfram\n"
        "    purpose: Symbolic tensor reduction\n"
        "  - tool: wolfram\n"
        "    purpose: Secondary symbolic reduction\n"
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: What benchmark must this plan recover?\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-main]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
        "  claims:\n"
        "    - id: claim-main\n"
        "      statement: Recover the benchmark value within tolerance\n"
        "      deliverables: [deliv-main]\n"
        "      acceptance_tests: [test-main]\n"
        "      references: [ref-main]\n"
        "  deliverables:\n"
        "    - id: deliv-main\n"
        "      kind: figure\n"
        "      path: figures/main.png\n"
        "      description: Main benchmark figure\n"
        "  references:\n"
        "    - id: ref-main\n"
        "      kind: paper\n"
        "      locator: Author et al., Journal, 2024\n"
        "      role: benchmark\n"
        "      why_it_matters: Published comparison target\n"
        "      applies_to: [claim-main]\n"
        "      must_surface: true\n"
        "      required_actions: [read, compare, cite]\n"
        "  acceptance_tests:\n"
        "    - id: test-main\n"
        "      subject: claim-main\n"
        "      kind: benchmark\n"
        "      procedure: Compare against the benchmark reference\n"
        "      pass_condition: Matches reference within tolerance\n"
        "      evidence_required: [deliv-main, ref-main]\n"
        "  forbidden_proxies:\n"
        "    - id: fp-main\n"
        "      subject: claim-main\n"
        "      proxy: Qualitative trend match without numerical comparison\n"
        "      reason: Would allow false progress without the decisive benchmark\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.validation_passed is False
    assert any("tool_requirements[].id values must be unique" in error for error in result.errors)


def test_build_plan_tool_preflight_missing_plan_fails(tmp_path: Path) -> None:
    result = build_plan_tool_preflight(tmp_path / "missing-PLAN.md")

    assert result.passed is False
    assert result.valid is False
    assert result.validation_passed is False
    assert result.errors == [f"Plan not found: {(tmp_path / 'missing-PLAN.md').resolve(strict=False)}"]


def test_build_plan_tool_preflight_reports_missing_wolfram(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda _name: None)
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        "---\n"
        "phase: 01-test\n"
        "plan: 01\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "tool_requirements:\n"
        "  - id: wolfram-cas\n"
        "    tool: wolfram\n"
        "    purpose: Symbolic tensor reduction\n"
        "    required: true\n"
        "    fallback: Use SymPy if unavailable\n"
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: What benchmark must this plan recover?\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-main]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
        "  claims:\n"
        "    - id: claim-main\n"
        "      statement: Recover the benchmark value within tolerance\n"
        "      deliverables: [deliv-main]\n"
        "      acceptance_tests: [test-main]\n"
        "      references: [ref-main]\n"
        "  deliverables:\n"
        "    - id: deliv-main\n"
        "      kind: figure\n"
        "      path: figures/main.png\n"
        "      description: Main benchmark figure\n"
        "  references:\n"
        "    - id: ref-main\n"
        "      kind: paper\n"
        "      locator: Author et al., Journal, 2024\n"
        "      role: benchmark\n"
        "      why_it_matters: Published comparison target\n"
        "      applies_to: [claim-main]\n"
        "      must_surface: true\n"
        "      required_actions: [read, compare, cite]\n"
        "  acceptance_tests:\n"
        "    - id: test-main\n"
        "      subject: claim-main\n"
        "      kind: benchmark\n"
        "      procedure: Compare against the benchmark reference\n"
        "      pass_condition: Matches reference within tolerance\n"
        "      evidence_required: [deliv-main, ref-main]\n"
        "  forbidden_proxies:\n"
        "    - id: fp-main\n"
        "      subject: claim-main\n"
        "      proxy: Qualitative trend match without numerical comparison\n"
        "      reason: Would allow false progress without the decisive benchmark\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )
    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.checks[0].tool == "wolfram"
    assert result.checks[0].blocking is True
    assert "wolframscript not found on PATH" in result.blocking_conditions[0]
    assert "live execution and license state are not proven" in result.warnings[0]


def test_build_plan_tool_preflight_blocks_missing_repo_local_script_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: "/usr/bin/python3" if name == "python" else None,
    )
    project_root = tmp_path / "project"
    plan_path = project_root / "GPD" / "phases" / "01" / "01-10-PLAN.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    _write_tool_requirement_plan(plan_path, "python scripts/missing_solver.py --version", plan_id="10")

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.checks[0].available is False
    assert result.checks[0].blocking is True
    assert "repo-local script target not found" in result.checks[0].detail


def test_build_plan_tool_preflight_blocks_python_script_targets_outside_project_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: "/usr/bin/python3" if name == "python3" else None,
    )
    project_root = tmp_path / "project"
    plan_path = project_root / "GPD" / "phases" / "01" / "01-10a-PLAN.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    external_script = tmp_path / "outside.py"
    external_script.write_text("print('outside')\n", encoding="utf-8")
    _write_tool_requirement_plan(plan_path, f"python3 {external_script}", plan_id="10a")

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.checks[0].available is False
    assert result.checks[0].blocking is True
    assert "repo-local script target must stay within the project roots" in result.checks[0].detail
    assert str(external_script) in result.checks[0].detail


@pytest.mark.parametrize(
    ("command", "runners"),
    [
        ("uv run --python 3.11 python scripts/missing_solver.py --version", {"uv", "python"}),
        ("uv run -- python scripts/missing_solver.py --version", {"uv", "python"}),
        ("pipx run --spec solver python scripts/missing_solver.py --version", {"pipx", "python"}),
        ("hatch run test:python scripts/missing_solver.py --version", {"hatch", "python"}),
    ],
)
def test_build_plan_tool_preflight_unwraps_runner_wrapped_python_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    command: str,
    runners: set[str],
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: f"/usr/bin/{name}" if name in runners else None,
    )
    project_root = tmp_path / "project"
    plan_path = project_root / "GPD" / "phases" / "01" / "01-10b-PLAN.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    _write_tool_requirement_plan(plan_path, command, plan_id="10b")

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.checks[0].available is False
    assert "repo-local script target not found" in result.checks[0].detail


def test_build_plan_tool_preflight_blocks_missing_extensionless_repo_local_python_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: "/usr/bin/python3" if name == "python" else None,
    )
    project_root = tmp_path / "project"
    plan_path = project_root / "GPD" / "phases" / "01" / "01-10c-PLAN.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    _write_tool_requirement_plan(plan_path, "python solver", plan_id="10c")

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.checks[0].available is False
    assert "repo-local script target not found: solver" in result.checks[0].detail


def test_build_plan_tool_preflight_does_not_treat_src_as_script_path_alias(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: "/usr/bin/python3" if name == "python" else None,
    )
    project_root = tmp_path / "project"
    (project_root / "src" / "scripts").mkdir(parents=True, exist_ok=True)
    (project_root / "src" / "scripts" / "solver.py").write_text("print('solver')\n", encoding="utf-8")
    plan_path = project_root / "GPD" / "phases" / "01" / "01-10d-PLAN.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    _write_tool_requirement_plan(plan_path, "python scripts/solver.py --version", plan_id="10d")

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.checks[0].available is False
    assert "repo-local script target not found" in result.checks[0].detail


def test_build_plan_tool_preflight_blocks_missing_repo_local_module_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: "/usr/bin/python3" if name == "python" else None,
    )
    project_root = tmp_path / "project"
    (project_root / "src" / "gpd").mkdir(parents=True, exist_ok=True)
    plan_path = project_root / "GPD" / "phases" / "01" / "01-11-PLAN.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    _write_tool_requirement_plan(plan_path, "python -m gpd.cli", plan_id="11")

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.checks[0].available is False
    assert result.checks[0].blocking is True
    assert "repo-local module target not found" in result.checks[0].detail


def test_build_plan_tool_preflight_reports_configured_shared_wolfram_integration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda _name: None)
    monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "secret-token")
    plan_path = tmp_path / "01-03-PLAN.md"
    plan_path.write_text(
        "---\n"
        "phase: 01-test\n"
        "plan: 03\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "tool_requirements:\n"
        "  - id: wolfram-cas\n"
        "    tool: wolfram\n"
        "    purpose: Symbolic tensor reduction\n"
        "    required: true\n"
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: What benchmark must this plan recover?\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-main]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
        "  claims:\n"
        "    - id: claim-main\n"
        "      statement: Recover the benchmark value within tolerance\n"
        "      deliverables: [deliv-main]\n"
        "      acceptance_tests: [test-main]\n"
        "      references: [ref-main]\n"
        "  deliverables:\n"
        "    - id: deliv-main\n"
        "      kind: figure\n"
        "      path: figures/main.png\n"
        "      description: Main benchmark figure\n"
        "  references:\n"
        "    - id: ref-main\n"
        "      kind: paper\n"
        "      locator: Author et al., Journal, 2024\n"
        "      role: benchmark\n"
        "      why_it_matters: Published comparison target\n"
        "      applies_to: [claim-main]\n"
        "      must_surface: true\n"
        "      required_actions: [read, compare, cite]\n"
        "  acceptance_tests:\n"
        "    - id: test-main\n"
        "      subject: claim-main\n"
        "      kind: benchmark\n"
        "      procedure: Compare against the benchmark reference\n"
        "      pass_condition: Matches reference within tolerance\n"
        "      evidence_required: [deliv-main, ref-main]\n"
        "  forbidden_proxies:\n"
        "    - id: fp-main\n"
        "      subject: claim-main\n"
        "      proxy: Qualitative trend match without numerical comparison\n"
        "      reason: Would allow false progress without the decisive benchmark\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is True
    assert result.checks[0].tool == "wolfram"
    assert result.checks[0].available is True
    assert result.checks[0].provider == "gpd-wolfram"
    assert "shared Wolfram integration configured" in result.checks[0].detail
    assert any("config-level only" in warning for warning in result.warnings)


def test_build_plan_tool_preflight_respects_project_local_wolfram_disable_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda _name: None)
    monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "secret-token")
    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"wolfram":{"enabled":false}}', encoding="utf-8")
    plan_path = tmp_path / "01-04-PLAN.md"
    plan_path.write_text(
        "---\n"
        "phase: 01-test\n"
        "plan: 04\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "tool_requirements:\n"
        "  - id: wolfram-cas\n"
        "    tool: wolfram\n"
        "    purpose: Symbolic tensor reduction\n"
        "    required: true\n"
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: What benchmark must this plan recover?\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-main]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
        "  claims:\n"
        "    - id: claim-main\n"
        "      statement: Recover the benchmark value within tolerance\n"
        "      deliverables: [deliv-main]\n"
        "      acceptance_tests: [test-main]\n"
        "      references: [ref-main]\n"
        "  deliverables:\n"
        "    - id: deliv-main\n"
        "      kind: figure\n"
        "      path: figures/main.png\n"
        "      description: Main benchmark figure\n"
        "  references:\n"
        "    - id: ref-main\n"
        "      kind: paper\n"
        "      locator: Author et al., Journal, 2024\n"
        "      role: benchmark\n"
        "      why_it_matters: Published comparison target\n"
        "      applies_to: [claim-main]\n"
        "      must_surface: true\n"
        "      required_actions: [read, compare, cite]\n"
        "  acceptance_tests:\n"
        "    - id: test-main\n"
        "      subject: claim-main\n"
        "      kind: benchmark\n"
        "      procedure: Compare against the benchmark reference\n"
        "      pass_condition: Matches reference within tolerance\n"
        "      evidence_required: [deliv-main, ref-main]\n"
        "  forbidden_proxies:\n"
        "    - id: fp-main\n"
        "      subject: claim-main\n"
        "      proxy: Qualitative trend match without numerical comparison\n"
        "      reason: Would allow false progress without the decisive benchmark\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.checks[0].available is False
    assert "not configured" in result.checks[0].detail


def test_build_plan_tool_preflight_reports_invalid_project_wolfram_config_as_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda _name: None)
    monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "secret-token")
    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"wolfram":{"enabled":"yes"}}', encoding="utf-8")
    plan_path = tmp_path / "01-05-PLAN.md"
    plan_path.write_text(
        "---\n"
        "phase: 01-test\n"
        "plan: 05\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "tool_requirements:\n"
        "  - id: wolfram-cas\n"
        "    tool: wolfram\n"
        "    purpose: Symbolic tensor reduction\n"
        "    required: true\n"
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: What benchmark must this plan recover?\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-main]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
        "  claims:\n"
        "    - id: claim-main\n"
        "      statement: Recover the benchmark value within tolerance\n"
        "      deliverables: [deliv-main]\n"
        "      acceptance_tests: [test-main]\n"
        "      references: [ref-main]\n"
        "  deliverables:\n"
        "    - id: deliv-main\n"
        "      kind: figure\n"
        "      path: figures/main.png\n"
        "      description: Main benchmark figure\n"
        "  references:\n"
        "    - id: ref-main\n"
        "      kind: paper\n"
        "      locator: Author et al., Journal, 2024\n"
        "      role: benchmark\n"
        "      why_it_matters: Published comparison target\n"
        "      applies_to: [claim-main]\n"
        "      must_surface: true\n"
        "      required_actions: [read, compare, cite]\n"
        "  acceptance_tests:\n"
        "    - id: test-main\n"
        "      subject: claim-main\n"
        "      kind: benchmark\n"
        "      procedure: Compare against the benchmark reference\n"
        "      pass_condition: Matches reference within tolerance\n"
        "      evidence_required: [deliv-main, ref-main]\n"
        "  forbidden_proxies:\n"
        "    - id: fp-main\n"
        "      subject: claim-main\n"
        "      proxy: Qualitative trend match without numerical comparison\n"
        "      reason: Would allow false progress without the decisive benchmark\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.validation_passed is True
    assert result.valid is True
    assert result.passed is False
    assert result.checks[0].available is False
    assert result.checks[0].provider == "gpd-wolfram"
    assert result.checks[0].detail == "integrations.wolfram.enabled must be a boolean"
    assert result.blocking_conditions == ["wolfram-cas: integrations.wolfram.enabled must be a boolean"]
    assert "Required tool wolfram is unavailable and no fallback is declared." in result.warnings


def test_build_plan_tool_preflight_uses_project_root_integrations_config_for_nested_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda _name: None)
    monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "secret-token")
    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"wolfram":{"enabled":false}}', encoding="utf-8")
    plan_dir = tmp_path / "GPD" / "phases" / "01-test"
    plan_dir.mkdir(parents=True)
    plan_path = plan_dir / "01-06-PLAN.md"
    plan_path.write_text(
        "---\n"
        "phase: 01-test\n"
        "plan: 06\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "tool_requirements:\n"
        "  - id: wolfram-cas\n"
        "    tool: wolfram\n"
        "    purpose: Symbolic tensor reduction\n"
        "    required: true\n"
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: What benchmark must this plan recover?\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-main]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
        "  claims:\n"
        "    - id: claim-main\n"
        "      statement: Recover the benchmark value within tolerance\n"
        "      deliverables: [deliv-main]\n"
        "      acceptance_tests: [test-main]\n"
        "      references: [ref-main]\n"
        "  deliverables:\n"
        "    - id: deliv-main\n"
        "      kind: figure\n"
        "      path: figures/main.png\n"
        "      description: Main benchmark figure\n"
        "  references:\n"
        "    - id: ref-main\n"
        "      kind: paper\n"
        "      locator: Author et al., Journal, 2024\n"
        "      role: benchmark\n"
        "      why_it_matters: Published comparison target\n"
        "      applies_to: [claim-main]\n"
        "      must_surface: true\n"
        "      required_actions: [read, compare, cite]\n"
        "  acceptance_tests:\n"
        "    - id: test-main\n"
        "      subject: claim-main\n"
        "      kind: benchmark\n"
        "      procedure: Compare against the benchmark reference\n"
        "      pass_condition: Matches reference within tolerance\n"
        "      evidence_required: [deliv-main, ref-main]\n"
        "  forbidden_proxies:\n"
        "    - id: fp-main\n"
        "      subject: claim-main\n"
        "      proxy: Qualitative trend match without numerical comparison\n"
        "      reason: Would allow false progress without the decisive benchmark\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is False
    assert result.checks[0].available is False
    assert "not configured" in result.checks[0].detail


def test_build_plan_tool_preflight_parses_quoted_command_executables_with_spaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    executable = "/tmp/My Tool/bin/run"
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: executable if name == executable else None,
    )
    plan_path = tmp_path / "01-07-PLAN.md"
    plan_path.write_text("---\nphase: 01-test\nplan: 07\ntype: execute\nwave: 1\ndepends_on: []\nfiles_modified: []\ninteractive: false\nconventions:\n  units: natural\n  metric: (+,-,-,-)\n  coordinates: Cartesian\ncontract:\n  schema_version: 1\n  scope:\n    question: q\n  context_intake:\n    must_read_refs: [ref-main]\n    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n  claims:\n    - id: claim-main\n      statement: s\n      deliverables: [deliv-main]\n      acceptance_tests: [test-main]\n      references: [ref-main]\n  deliverables:\n    - id: deliv-main\n      description: d\n  references:\n    - id: ref-main\n      locator: l\n      why_it_matters: w\n  acceptance_tests:\n    - id: test-main\n      subject: claim-main\n      procedure: p\n      pass_condition: c\nuncertainty_markers:\n  disconfirming_observations: [o]\n---\nbody\n", encoding="utf-8")
    requirements = parse_plan_tool_requirements(
        [
            {
                "id": "solver",
                "tool": "command",
                "command": '"/tmp/My Tool/bin/run" --flag',
                "purpose": "Run external solver",
            }
        ]
    )

    result = build_plan_tool_preflight(plan_path, requirements=requirements)

    assert result.passed is True
    assert result.checks[0].available is True
    assert result.checks[0].detail == f"{executable} found at {Path(executable).resolve(strict=False)}"


def test_build_plan_tool_preflight_skips_leading_env_assignments_when_probing_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: "/usr/local/bin/mycmd" if name == "mycmd" else None,
    )
    plan_path = tmp_path / "01-08-PLAN.md"
    plan_path.write_text("---\nphase: 01-test\nplan: 08\ntype: execute\nwave: 1\ndepends_on: []\nfiles_modified: []\ninteractive: false\nconventions:\n  units: natural\n  metric: (+,-,-,-)\n  coordinates: Cartesian\ncontract:\n  schema_version: 1\n  scope:\n    question: q\n  context_intake:\n    must_read_refs: [ref-main]\n    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n  claims:\n    - id: claim-main\n      statement: s\n      deliverables: [deliv-main]\n      acceptance_tests: [test-main]\n      references: [ref-main]\n  deliverables:\n    - id: deliv-main\n      description: d\n  references:\n    - id: ref-main\n      locator: l\n      why_it_matters: w\n  acceptance_tests:\n    - id: test-main\n      subject: claim-main\n      procedure: p\n      pass_condition: c\nuncertainty_markers:\n  disconfirming_observations: [o]\n---\nbody\n", encoding="utf-8")
    requirements = parse_plan_tool_requirements(
        [
            {
                "id": "solver",
                "tool": "command",
                "command": 'OMP_NUM_THREADS=1 MKL_DEBUG_CPU_TYPE=5 mycmd --version',
                "purpose": "Run external solver",
            }
        ]
    )

    result = build_plan_tool_preflight(plan_path, requirements=requirements)

    assert result.passed is True
    assert result.checks[0].detail == "mycmd found at /usr/local/bin/mycmd"


def test_build_plan_tool_preflight_resolves_env_wrapped_command_to_real_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: "/usr/bin/env" if name == "env" else None,
    )
    plan_path = tmp_path / "01-08b-PLAN.md"
    plan_path.write_text("---\nphase: 01-test\nplan: 08b\ntype: execute\nwave: 1\ndepends_on: []\nfiles_modified: []\ninteractive: false\nconventions:\n  units: natural\n  metric: (+,-,-,-)\n  coordinates: Cartesian\ncontract:\n  schema_version: 1\n  scope:\n    question: q\n  context_intake:\n    must_read_refs: [ref-main]\n    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n  claims:\n    - id: claim-main\n      statement: s\n      deliverables: [deliv-main]\n      acceptance_tests: [test-main]\n      references: [ref-main]\n  deliverables:\n    - id: deliv-main\n      description: d\n  references:\n    - id: ref-main\n      locator: l\n      why_it_matters: w\n  acceptance_tests:\n    - id: test-main\n      subject: claim-main\n      procedure: p\n      pass_condition: c\nuncertainty_markers:\n  disconfirming_observations: [o]\n---\nbody\n", encoding="utf-8")
    requirements = parse_plan_tool_requirements(
        [
            {
                "id": "solver",
                "tool": "command",
                "command": "env OMP_NUM_THREADS=1 missing-solver --version",
                "purpose": "Run external solver",
            }
        ]
    )

    result = build_plan_tool_preflight(plan_path, requirements=requirements)

    assert result.passed is False
    assert result.checks[0].available is False
    assert result.checks[0].detail == "missing-solver not found on PATH"


def test_build_plan_tool_preflight_handles_env_only_invocations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: "/usr/bin/env" if name == "env" else None,
    )
    plan_path = tmp_path / "01-08c-PLAN.md"
    plan_path.write_text("---\nphase: 01-test\nplan: 08c\ntype: execute\nwave: 1\ndepends_on: []\nfiles_modified: []\ninteractive: false\nconventions:\n  units: natural\n  metric: (+,-,-,-)\n  coordinates: Cartesian\ncontract:\n  schema_version: 1\n  scope:\n    question: q\n  context_intake:\n    must_read_refs: [ref-main]\n    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n  claims:\n    - id: claim-main\n      statement: s\n      deliverables: [deliv-main]\n      acceptance_tests: [test-main]\n      references: [ref-main]\n  deliverables:\n    - id: deliv-main\n      description: d\n  references:\n    - id: ref-main\n      locator: l\n      why_it_matters: w\n  acceptance_tests:\n    - id: test-main\n      subject: claim-main\n      procedure: p\n      pass_condition: c\nuncertainty_markers:\n  disconfirming_observations: [o]\n---\nbody\n", encoding="utf-8")
    requirements = parse_plan_tool_requirements(
        [
            {
                "id": "env-only",
                "tool": "command",
                "command": "env -i",
                "purpose": "Inspect the clean environment",
            }
        ]
    )

    result = build_plan_tool_preflight(plan_path, requirements=requirements)

    assert result.passed is True
    assert result.checks[0].available is True
    assert result.checks[0].detail == f"env found at {Path('/usr/bin/env').resolve(strict=False)}"


def test_build_plan_tool_preflight_resolves_env_wrapped_command_after_env_flag_with_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: "/usr/bin/env" if name == "env" else None,
    )
    plan_path = tmp_path / "01-08d-PLAN.md"
    plan_path.write_text("---\nphase: 01-test\nplan: 08d\ntype: execute\nwave: 1\ndepends_on: []\nfiles_modified: []\ninteractive: false\nconventions:\n  units: natural\n  metric: (+,-,-,-)\n  coordinates: Cartesian\ncontract:\n  schema_version: 1\n  scope:\n    question: q\n  context_intake:\n    must_read_refs: [ref-main]\n    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n  claims:\n    - id: claim-main\n      statement: s\n      deliverables: [deliv-main]\n      acceptance_tests: [test-main]\n      references: [ref-main]\n  deliverables:\n    - id: deliv-main\n      description: d\n  references:\n    - id: ref-main\n      locator: l\n      why_it_matters: w\n  acceptance_tests:\n    - id: test-main\n      subject: claim-main\n      procedure: p\n      pass_condition: c\nuncertainty_markers:\n  disconfirming_observations: [o]\n---\nbody\n", encoding="utf-8")
    requirements = parse_plan_tool_requirements(
        [
            {
                "id": "solver",
                "tool": "command",
                "command": "env -u OMP_NUM_THREADS missing-solver --version",
                "purpose": "Run external solver",
            }
        ]
    )

    result = build_plan_tool_preflight(plan_path, requirements=requirements)

    assert result.passed is False
    assert result.checks[0].available is False
    assert result.checks[0].detail == "missing-solver not found on PATH"


@pytest.mark.parametrize("command", ["bash -lc 'missing-solver --version'", "sh -c 'missing-solver --version'"])
def test_build_plan_tool_preflight_unwraps_shell_launchers_to_probe_the_real_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    command: str,
) -> None:
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: f"/bin/{name}" if name in {"bash", "sh"} else None,
    )
    plan_path = tmp_path / "01-08e-PLAN.md"
    plan_path.write_text("---\nphase: 01-test\nplan: 08e\ntype: execute\nwave: 1\ndepends_on: []\nfiles_modified: []\ninteractive: false\nconventions:\n  units: natural\n  metric: (+,-,-,-)\n  coordinates: Cartesian\ncontract:\n  schema_version: 1\n  scope:\n    question: q\n  context_intake:\n    must_read_refs: [ref-main]\n    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n  claims:\n    - id: claim-main\n      statement: s\n      deliverables: [deliv-main]\n      acceptance_tests: [test-main]\n      references: [ref-main]\n  deliverables:\n    - id: deliv-main\n      description: d\n  references:\n    - id: ref-main\n      locator: l\n      why_it_matters: w\n  acceptance_tests:\n    - id: test-main\n      subject: claim-main\n      procedure: p\n      pass_condition: c\nuncertainty_markers:\n  disconfirming_observations: [o]\n---\nbody\n", encoding="utf-8")
    requirements = parse_plan_tool_requirements(
        [
            {
                "id": "solver",
                "tool": "command",
                "command": command,
                "purpose": "Run external solver",
            }
        ]
    )

    result = build_plan_tool_preflight(plan_path, requirements=requirements)

    assert result.passed is False
    assert result.checks[0].available is False
    assert result.checks[0].detail == "missing-solver not found on PATH"


def test_build_plan_tool_preflight_parses_quoted_windows_command_executables_with_spaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    executable = r"C:\Program Files\Solver\solver.exe"
    monkeypatch.setattr(
        "gpd.core.tool_preflight.shutil.which",
        lambda name: executable if name == executable else None,
    )
    plan_path = tmp_path / "01-09-PLAN.md"
    plan_path.write_text("---\nphase: 01-test\nplan: 09\ntype: execute\nwave: 1\ndepends_on: []\nfiles_modified: []\ninteractive: false\nconventions:\n  units: natural\n  metric: (+,-,-,-)\n  coordinates: Cartesian\ncontract:\n  schema_version: 1\n  scope:\n    question: q\n  context_intake:\n    must_read_refs: [ref-main]\n    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n  claims:\n    - id: claim-main\n      statement: s\n      deliverables: [deliv-main]\n      acceptance_tests: [test-main]\n      references: [ref-main]\n  deliverables:\n    - id: deliv-main\n      description: d\n  references:\n    - id: ref-main\n      locator: l\n      why_it_matters: w\n  acceptance_tests:\n    - id: test-main\n      subject: claim-main\n      procedure: p\n      pass_condition: c\nuncertainty_markers:\n  disconfirming_observations: [o]\n---\nbody\n", encoding="utf-8")
    requirements = parse_plan_tool_requirements(
        [
            {
                "id": "solver",
                "tool": "command",
                "command": '"C:\\Program Files\\Solver\\solver.exe" --flag',
                "purpose": "Run external solver",
            }
        ]
    )

    result = build_plan_tool_preflight(plan_path, requirements=requirements)

    assert result.passed is True
    assert result.checks[0].detail == f"{executable} found at {Path(executable).resolve(strict=False)}"


def test_build_plan_tool_preflight_optional_missing_tool_without_fallback_stays_non_blocking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda _name: None)
    plan_path = tmp_path / "01-02-PLAN.md"
    plan_path.write_text(
        "---\n"
        "phase: 01-test\n"
        "plan: 02\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "tool_requirements:\n"
        "  - id: wolfram-optional\n"
        "    tool: wolfram\n"
        "    purpose: Optional symbolic simplification\n"
        "    required: false\n"
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: What benchmark must this plan recover?\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-main]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
        "  claims:\n"
        "    - id: claim-main\n"
        "      statement: Recover the benchmark value within tolerance\n"
        "      deliverables: [deliv-main]\n"
        "      acceptance_tests: [test-main]\n"
        "      references: [ref-main]\n"
        "  deliverables:\n"
        "    - id: deliv-main\n"
        "      kind: figure\n"
        "      path: figures/main.png\n"
        "      description: Main benchmark figure\n"
        "  references:\n"
        "    - id: ref-main\n"
        "      kind: paper\n"
        "      locator: Author et al., Journal, 2024\n"
        "      role: benchmark\n"
        "      why_it_matters: Published comparison target\n"
        "      applies_to: [claim-main]\n"
        "      must_surface: true\n"
        "      required_actions: [read, compare, cite]\n"
        "  acceptance_tests:\n"
        "    - id: test-main\n"
        "      subject: claim-main\n"
        "      kind: benchmark\n"
        "      procedure: Compare against the benchmark reference\n"
        "      pass_condition: Matches reference within tolerance\n"
        "      evidence_required: [deliv-main, ref-main]\n"
        "  forbidden_proxies:\n"
        "    - id: fp-main\n"
        "      subject: claim-main\n"
        "      proxy: Qualitative trend match without numerical comparison\n"
        "      reason: Would allow false progress without the decisive benchmark\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = build_plan_tool_preflight(plan_path)

    assert result.passed is True
    assert result.checks[0].blocking is False
    assert result.guidance == (
        "Optional specialized tools are unavailable; continue only if the plan can genuinely proceed without them. "
        "Otherwise report the gap instead of fabricating outputs."
    )
    assert any("no fallback is declared" in warning for warning in result.warnings)
