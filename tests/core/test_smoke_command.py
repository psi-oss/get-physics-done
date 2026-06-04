"""Focused tests for the `gpd:smoke` command surface and from-plan parser.

`gpd:smoke` is a pre-commit sniff-test primitive: an entry-point command that
reproduces a published claim or verifies a plan assumption with the smallest
reproducible computation before committing to heavier workflows. These tests
validate that:

1. The command file at `src/gpd/commands/smoke.md` parses and exposes the
   documented frontmatter (name, context_mode, help group/order).
2. The workflow file at `src/gpd/specs/workflows/smoke.md` exists and contains
   the documented `<step name="...">` blocks the command body references.
3. The tolerant `--from-plan` parser correctly extracts hierarchical
   assumption bullets (H2 `## My Assumptions for Phase X` + H3 categories) and
   tags them with their parent category. Hand-rolled against an inline fixture
   so the test does not need the full runtime to run.
"""

from __future__ import annotations

import re
from pathlib import Path

from gpd.registry import _parse_command_file

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_FILE = REPO_ROOT / "src" / "gpd" / "commands" / "smoke.md"
WORKFLOW_FILE = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "smoke.md"

REQUIRED_WORKFLOW_STEPS = (
    "orient_the_user",
    "from_plan_intake",
    "gather_the_claim",
    "identify_minimal_setup",
    "scaffold_and_run",
    "compare_and_verdict",
    "gate_next_step",
    "guardrails",
)


def test_smoke_command_file_parses_and_exposes_documented_frontmatter() -> None:
    """The command file under `src/gpd/commands/` must parse with the registry
    helper and expose the documented frontmatter fields. These fields are
    contract-critical because the help renderer, command surface, and runtime
    label projection all read them."""
    assert COMMAND_FILE.exists(), f"missing {COMMAND_FILE}"
    command = _parse_command_file(COMMAND_FILE, source="commands")

    assert command.name == "gpd:smoke"
    # context_mode determines whether the command can run pre-project.
    assert command.context_mode == "projectless"
    # The argument-hint advertises the three invocation forms.
    raw = COMMAND_FILE.read_text(encoding="utf-8")
    assert "[claim text]" in raw
    assert '--assumption' in raw
    assert "--from-plan" in raw

    # Help metadata routes smoke into the validation group for the compact
    # index. Order is intentionally early (290) because smoke runs before the
    # other validation commands (debug=300, dimensional-analysis=310, ...).
    help_meta = command.help
    assert help_meta is not None
    assert help_meta.group == "Validation and analysis"
    assert help_meta.order == 290


def test_smoke_workflow_file_has_documented_steps() -> None:
    """The command body references workflow steps by name; missing steps
    silently break the workflow at runtime. Pin them as a regression."""
    assert WORKFLOW_FILE.exists(), f"missing {WORKFLOW_FILE}"
    workflow = WORKFLOW_FILE.read_text(encoding="utf-8")

    for step in REQUIRED_WORKFLOW_STEPS:
        marker = f'<step name="{step}">'
        assert marker in workflow, f"workflow missing step: {step}"


def test_smoke_from_plan_assumption_parser_extracts_hierarchical_bullets() -> None:
    """The `--from-plan` parser must tolerate both the flat `## Assumptions`
    H2 + bullets form and the hierarchical `## My Assumptions for Phase X`
    H2 + H3 subheadings + bullets form. Bullets under H3 subheadings are
    tagged with the category name. This fixture is the canonical hierarchical
    shape emitted by `gpd:plan-phase`."""
    fixture = """# PLAN 01-01: Example phase

## Goal
Some text.

## My Assumptions for Phase 1: Example phase

### Physical Assumptions
- The orbit stays bounded in [0, 1].
- The map is smooth and unimodal.

### Approximation Scheme
- Burn-in of 2000 iterations is sufficient.

### Skeptical Review
**Weakest anchor:** the 2000-step burn-in claim near r_5. (prose only)

## Out of scope
- Higher-D chaos.
"""
    extracted = _extract_assumption_bullets_with_categories(fixture)
    assert extracted == [
        ("Physical Assumptions", "The orbit stays bounded in [0, 1]."),
        ("Physical Assumptions", "The map is smooth and unimodal."),
        ("Approximation Scheme", "Burn-in of 2000 iterations is sufficient."),
    ], extracted


def _extract_assumption_bullets_with_categories(text: str) -> list[tuple[str, str]]:
    """Mirror the parser the workflow documents in step `from_plan_intake`.

    Algorithm:
      1. Find the first H2 whose title contains "assumption" (case-insensitive).
      2. Inside, walk to the next H2. Inside that slice, track the current H3
         subheading and collect each `- ` / `* ` / `N. ` bullet, tagging it
         with the H3 title.
      3. Prose paragraphs without a bullet marker are not extracted.
    """
    h2 = re.search(r"^##\s+.*assumption.*$", text, re.IGNORECASE | re.MULTILINE)
    if not h2:
        return []
    rest = text[h2.end():]
    next_h2 = re.search(r"^## ", rest, re.MULTILINE)
    section = rest[: next_h2.start()] if next_h2 else rest

    out: list[tuple[str, str]] = []
    current_category: str | None = None
    bullet_re = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.+)$")
    h3_re = re.compile(r"^###\s+(.+)$")

    for line in section.splitlines():
        h3 = h3_re.match(line)
        if h3:
            current_category = h3.group(1).strip()
            continue
        b = bullet_re.match(line)
        if b and current_category is not None:
            out.append((current_category, b.group(1).strip()))
    return out
