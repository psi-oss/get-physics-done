"""Focused regressions for the Phase 9 handoff contract unification."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_planner_template_routes_on_typed_gpd_return_status_not_heading_markers() -> None:
    prompt = _read(TEMPLATES_DIR / "planner-subagent-prompt.md")

    assert "The markdown headings `## PLANNING COMPLETE`, `## CHECKPOINT REACHED`, and `## PLANNING INCONCLUSIVE` are human-readable labels only." in prompt
    assert "Do not route on them; route on `gpd_return.status` and the artifact gate below." in prompt
    assert "gpd_return.status: completed" in prompt
    assert "gpd_return.status: checkpoint" in prompt
    assert "gpd_return.status: blocked" in prompt
    assert "gpd_return.status: failed" in prompt
    assert "gpd_return.files_written" in prompt


def test_plan_phase_uses_structured_status_and_artifact_gating_for_research_and_planner_returns() -> None:
    workflow = _read(WORKFLOWS_DIR / "plan-phase.md")

    assert 'REQUIREMENTS=$(echo "$INIT" | gpd json get .requirements_content --default "")' in workflow
    assert 'grep -A100 "## Requirements"' not in workflow
    assert "gpd_return.status: completed" in workflow
    assert "gpd_return.status: checkpoint" in workflow
    assert "gpd_return.status: failed" in workflow
    assert "gpd_return.files_written" in workflow
    assert "Human-readable headings such as `## VERIFICATION PASSED`, `## ISSUES FOUND`, and `## PARTIAL APPROVAL` are presentation only." in workflow


def test_research_phase_routes_on_typed_status_and_expected_artifacts() -> None:
    workflow = _read(WORKFLOWS_DIR / "research-phase.md")

    assert (
        "Human-readable headings such as `## RESEARCH COMPLETE` and `## CHECKPOINT REACHED` are presentation only; route on `gpd_return.status`, `gpd_return.files_written`, and the artifact gate."
        in workflow
    )
    assert "gpd_return.status: completed" in workflow
    assert "gpd_return.status: checkpoint" in workflow
    assert "gpd_return.status: blocked` or `failed" in workflow
    assert "gpd_return.files_written" in workflow
    assert "If `gpd_return.status: completed` but the `expected_artifacts` entry (`RESEARCH.md`) is missing" in workflow


def test_map_research_routes_on_typed_status_and_expected_artifacts() -> None:
    workflow = _read(WORKFLOWS_DIR / "map-research.md")

    assert "Each mapper agent is a one-shot file-producing handoff." in workflow
    assert "Route on `gpd_return.status`, then verify `gpd_return.files_written` against the expected artifacts before accepting the run." in workflow
    assert workflow.count("<spawn_contract>") >= 4
    assert "shared_state_policy: return_only" in workflow
    assert "gpd_return.status: completed" in workflow
    assert "gpd_return.files_written" in workflow
    assert "gpd --raw config get research_mode" not in workflow
    assert 'RESEARCH_MODE=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_mode --default balanced)' in workflow


def test_verify_work_uses_frontmatter_session_lookup_and_canonical_verification_status() -> None:
    workflow = _read(WORKFLOWS_DIR / "verify-work.md")

    assert "gpd frontmatter get \"$file\" --field session_status" in workflow
    assert "Only treat files whose frontmatter `session_status` is `validating` or `diagnosed` as active researcher sessions." in workflow
    assert "Human-readable headings in the verifier output are presentation only; route on the canonical verification frontmatter and `gpd_return.status`, not on headings or marker strings." in workflow
    assert "gpd_return.status" in workflow
    assert "rg -l '^session_status: (validating|diagnosed)$' GPD/phases/*/*-VERIFICATION.md 2>/dev/null | sort | head-5" not in workflow
