from __future__ import annotations

from pathlib import Path

from tests.assertion_taxonomy_support import assert_prompt_contracts, machine_exact, semantic_concept

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    _, start_marker, tail = text.partition(start)
    assert start_marker, f"Missing marker: {start}"
    body, end_marker, _ = tail.partition(end)
    assert end_marker, f"Missing marker: {end}"
    return body


def test_comparison_workflows_call_comparison_contract_validator() -> None:
    compare_experiment = _read(WORKFLOWS_DIR / "compare-experiment.md")
    compare_results = _read(WORKFLOWS_DIR / "compare-results.md")

    expected = 'gpd validate comparison-contract "${COMPARISON_OUTPUT_PATH}"'
    assert expected in compare_experiment
    assert expected in compare_results
    for workflow in (compare_experiment, compare_results):
        assert_prompt_contracts(
            workflow,
            *semantic_concept(
                "comparison workflow rejects incomplete comparison artifacts",
                required=("treat the comparison artifact as incomplete",),
            ),
        )


def test_verifier_artifact_levels_are_four_level_consistent() -> None:
    verifier = _read(AGENTS_DIR / "gpd-verifier.md")

    assert_prompt_contracts(
        verifier,
        machine_exact(
            "verifier four-level artifact headings",
            (
                "## Step 4: Verify Artifacts (Four Levels)",
                "### Level 1: Existence",
                "### Level 2: Substantive Content",
                "### Level 3: Content Validation",
                "### Level 4: Integration",
            ),
        ),
        *semantic_concept("verifier artifact pass semantics", required=("all artifacts pass levels 1-4",)),
    )


def test_domain_judgments_open_relevant_selected_handles_first() -> None:
    planner = _read(AGENTS_DIR / "gpd-planner.md")
    executor = _read(AGENTS_DIR / "gpd-executor.md")
    verifier = _read(AGENTS_DIR / "gpd-verifier.md")

    planner_physics = _between(planner, "<physics_verification>", "</physics_verification>")
    executor_protocol = _between(executor, "<protocol_loading>", "</protocol_loading>")
    verifier_protocol = _between(verifier, "**Protocol bundle guidance", "**Fallback")

    assert_prompt_contracts(
        planner_physics,
        *semantic_concept(
            "planner opens selected bundle handles before domain planning judgments",
            required=(
                "protocol_bundle_load_manifest",
                "Before",
                "domain",
                "method",
                "judgment",
                "open only relevant",
                "planning_guides",
                "verification_domains",
                "execution_guides",
                "portable_path",
                "a handle label alone is not evidence",
            ),
            forbidden=("consult selected protocol bundle context first",),
        ),
    )
    assert planner_physics.index("protocol_bundle_load_manifest") < planner_physics.index("Before")
    assert planner_physics.index("Before") < planner_physics.index("portable_path")

    assert_prompt_contracts(
        executor_protocol,
        *semantic_concept(
            "executor opens selected execution or verification handles before domain judgments",
            required=(
                "protocol_bundle_load_manifest",
                "Before",
                "domain",
                "method",
                "judgment",
                "execution_guides",
                "verification_domains",
                "asset paths",
                "a handle label alone is not evidence",
            ),
            forbidden=("Read `<protocol_bundle_context>`",),
        ),
    )
    assert executor_protocol.index("protocol_bundle_load_manifest") < executor_protocol.index("Before")

    assert_prompt_contracts(
        verifier_protocol,
        *semantic_concept(
            "verifier opens selected verification domain before physics status judgments",
            required=(
                "protocol_bundle_load_manifest",
                "Before",
                "assigning",
                "domain-specific",
                "physics status",
                "verification_domains",
                "portable_path",
                "gpd --raw verify bundle-checklist",
                "fallback/check",
            ),
            forbidden=("prefer `protocol_bundle_verifier_extensions` and `protocol_bundle_context`",),
        ),
    )
    assert verifier_protocol.index("protocol_bundle_load_manifest") < verifier_protocol.index("Before")
    assert verifier_protocol.index("Before") < verifier_protocol.index("gpd --raw verify bundle-checklist")


def test_verify_phase_keeps_independent_confirmed_tally_out_of_machine_fields() -> None:
    verify_phase = _read(WORKFLOWS_DIR / "verify-phase.md")

    assert_prompt_contracts(
        verify_phase,
        *semantic_concept(
            "verify phase keeps independent-confirmed tally narrative-only",
            required=("Keep any independent-confirmed tally in the report body or markdown return narrative only",),
        ),
    )
    assert "do not add it to verification frontmatter or `gpd_return`" in verify_phase
    assert "independently confirmed count (K/M)" not in verify_phase
