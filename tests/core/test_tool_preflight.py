from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.tool_preflight import (
    PlanToolPreflightError,
    build_plan_tool_preflight,
    parse_plan_tool_requirements,
)


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
    plan_path.write_text("---\nphase: 01-test\nplan: 07\ntype: execute\nwave: 1\ndepends_on: []\nfiles_modified: []\ninteractive: false\nconventions:\n  units: natural\n  metric: (+,-,-,-)\n  coordinates: Cartesian\ncontract:\n  scope:\n    question: q\n  context_intake:\n    must_read_refs: [ref-main]\n    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n  claims:\n    - id: claim-main\n      statement: s\n      deliverables: [deliv-main]\n      acceptance_tests: [test-main]\n      references: [ref-main]\n  deliverables:\n    - id: deliv-main\n      description: d\n  references:\n    - id: ref-main\n      locator: l\n      why_it_matters: w\n  acceptance_tests:\n    - id: test-main\n      subject: claim-main\n      procedure: p\n      pass_condition: c\nuncertainty_markers:\n  disconfirming_observations: [o]\n---\nbody\n", encoding="utf-8")
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
        "Optional specialized tools are unavailable; continue only if the plan can genuinely proceed without them."
    )
    assert any("no fallback is declared" in warning for warning in result.warnings)
