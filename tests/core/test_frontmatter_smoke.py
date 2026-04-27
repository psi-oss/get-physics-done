"""Focused smoke coverage for plan frontmatter validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.frontmatter import validate_frontmatter, verify_plan_structure


def _plan_markdown(*, extra_frontmatter: str = "") -> str:
    lines = [
        "---",
        "phase: 01-test",
        "plan: 01",
        "type: execute",
        "wave: 1",
        "depends_on: []",
        "files_modified: []",
        "interactive: false",
    ]
    if extra_frontmatter.strip():
        lines.extend(line.rstrip() for line in extra_frontmatter.strip().splitlines())
    lines.extend(
        [
            "conventions:",
            "  units: natural",
            "  metric: (+,-,-,-)",
            "  coordinates: Cartesian",
            "contract:",
            "  schema_version: 1",
            "  scope:",
            "    question: What benchmark must this plan recover?",
            "    in_scope: [benchmark recovery]",
            "  context_intake:",
            "    must_read_refs: [ref-main]",
            "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]",
            "  claims:",
            "    - id: claim-main",
            "      statement: Recover the benchmark value within tolerance",
            "      deliverables: [deliv-main]",
            "      acceptance_tests: [test-main]",
            "      references: [ref-main]",
            "  deliverables:",
            "    - id: deliv-main",
            "      kind: figure",
            "      path: figures/main.png",
            "      description: Main benchmark figure",
            "  references:",
            "    - id: ref-main",
            "      kind: paper",
            "      locator: Author et al., Journal, 2024",
            "      role: benchmark",
            "      why_it_matters: Published comparison target",
            "      applies_to: [claim-main]",
            "      must_surface: true",
            "      required_actions: [read, compare, cite]",
            "  acceptance_tests:",
            "    - id: test-main",
            "      subject: claim-main",
            "      kind: benchmark",
            "      procedure: Compare against the benchmark reference",
            "      pass_condition: Matches reference within tolerance",
            "      evidence_required: [deliv-main, ref-main]",
            "  forbidden_proxies:",
            "    - id: fp-main",
            "      subject: claim-main",
            "      proxy: Qualitative trend match without numerical comparison",
            "      reason: Would allow false progress without the decisive benchmark",
            "  uncertainty_markers:",
            "    weakest_anchors: [Reference tolerance interpretation]",
            "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]",
            "---",
            "",
            "Body",
            "",
        ]
    )
    return "\n".join(lines)


def test_verify_plan_structure_accepts_minimal_valid_plan_frontmatter(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(_plan_markdown(), encoding="utf-8")

    result = verify_plan_structure(tmp_path, plan_path)

    assert result.valid is True
    assert result.errors == []
    assert result.warnings == ["No <task> elements found"]


@pytest.mark.parametrize(
    ("field_name", "expected_missing"),
    [
        ("wave", "wave"),
        ("conventions", "conventions"),
    ],
)
def test_validate_frontmatter_plan_reports_missing_required_fields(
    field_name: str,
    expected_missing: str,
) -> None:
    content = (
        _plan_markdown().replace("wave: 1\n", "", 1)
        if field_name == "wave"
        else _plan_markdown().replace(
            "conventions:\n  units: natural\n  metric: (+,-,-,-)\n  coordinates: Cartesian\n",
            "",
            1,
        )
    )

    result = validate_frontmatter(content, "plan")

    assert result.valid is False
    assert expected_missing in result.missing


def test_validate_frontmatter_plan_rejects_invalid_tool_requirements_shape() -> None:
    content = _plan_markdown(extra_frontmatter="tool_requirements: oops")

    result = validate_frontmatter(content, "plan")

    assert result.valid is False
    assert "tool_requirements: Input should be a valid list" in result.errors
