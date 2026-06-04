"""Exact prompt-assertion budget contracts."""

from __future__ import annotations

import textwrap
from functools import lru_cache
from pathlib import Path

from gpd.core.prompt_exactness_diagnostics import bounded_exact_assertion_diagnostics, scan_exact_assertion_diagnostics

REPO_ROOT = Path(__file__).resolve().parents[2]

EXACTNESS_TOTAL_BUDGETS = {
    # Phase 5 pass4 observed 517/5134 after semantic-helper migration.
    "brittle_prose_assertions": 525,
    # +2 for the numeric-oracle unit + contract-check tests.
    "exact_assertion_count": 5_167,
}
TAXONOMY_HELPER_TOTAL_FLOORS = {
    # Phase 8 observed 80 files and 735 helper calls; keep a small call-count cushion.
    "taxonomy_helper_file_count": 80,
    "taxonomy_helper_call_count": 725,
}
SEMANTIC_HELPER_LITERAL_FRAGMENT_FLOORS = {
    # Phase 5 worker 6 observed 617 direct literal fragments in semantic helpers.
    "semantic_helper_literal_fragment_count": 600,
}
SEMANTIC_HELPER_LONG_PROSE_BUDGETS = {
    # Phase 5 worker 6 observed 37 files / 117 fragments; keep a small cushion
    # so semantic helpers cannot absorb large exact-sentence assertions silently.
    "semantic_helper_long_prose_file_count": 40,
    "semantic_helper_long_prose_fragment_count": 125,
}
HIGH_SEVERITY_BASELINES: dict[str, dict[str, int]] = {}
TAXONOMY_HELPER_BRITTLE_BASELINES = {
    "tests/adapters/test_install_roundtrip.py": 5,
    "tests/core/test_assertion_taxonomy_support.py": 6,
    "tests/core/test_literature_review_workflow_seams.py": 6,
    "tests/core/test_map_research_stage_contract.py": 1,
    "tests/core/test_new_project_project_contract_visibility.py": 1,
    "tests/core/test_new_project_stage_contract.py": 2,
    "tests/core/test_plan_checker_bibliographer_prompt_cleanup.py": 1,
    "tests/core/test_planner_prompt_budget.py": 9,
    "tests/core/test_prompt_cli_consistency.py": 3,
    "tests/core/test_quick_typed_return_routing.py": 1,
    "tests/core/test_review_agent_prompt_cleanup.py": 2,
    "tests/core/test_review_contract_prompt_visibility.py": 6,
    "tests/core/test_start_prompt.py": 2,
    "tests/core/test_verifier_prompt_contract_visibility.py": 1,
    "tests/core/test_write_paper_handoff_artifact_gates.py": 2,
    "tests/doc_surface_contracts.py": 1,
    "tests/mcp/test_servers.py": 10,
    "tests/mcp/test_tool_contract_visibility.py": 4,
    "tests/test_registry.py": 9,
    "tests/test_release_consistency.py": 13,
}


@lru_cache
def _exactness_payload() -> dict[str, object]:
    return scan_exact_assertion_diagnostics(REPO_ROOT)


def _exactness_files_by_path() -> dict[str, dict[str, object]]:
    exactness = _exactness_payload()
    rows = exactness["files"]
    assert isinstance(rows, list)
    return {str(row["path"]): row for row in rows if isinstance(row, dict)}


def _taxonomy_helper_usage_files_by_path() -> dict[str, dict[str, object]]:
    exactness = _exactness_payload()
    usage = exactness["taxonomy_helper_usage"]
    assert isinstance(usage, dict)
    rows = usage["files"]
    assert isinstance(rows, list)
    return {str(row["path"]): row for row in rows if isinstance(row, dict)}


def _migration_files_by_path(exactness: dict[str, object]) -> dict[str, dict[str, object]]:
    migration = exactness["migration"]
    assert isinstance(migration, dict)
    rows = migration["files"]
    assert isinstance(rows, list)
    return {str(row["path"]): row for row in rows if isinstance(row, dict)}


def test_taxonomy_helper_usage_tracks_semantic_concept_without_hiding_raw_exactness(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_prompt_contracts.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        textwrap.dedent(
            """
            from tests.assertion_taxonomy_support import (
                assert_prompt_contracts,
                machine_exact,
                public_exact,
                semantic_anchor,
                semantic_concept,
            )

            PROMPT = (
                "Quick Start\\n"
                "gpd_return.status\\n"
                "stable semantic anchor\\n"
                "this full sentence remains visible inside semantic helper diagnostics\\n"
            )

            def test_prompt_contracts():
                assert "gpd_return.status" in PROMPT
                assert "Quick Start" in PROMPT
                assert_prompt_contracts(
                    PROMPT,
                    machine_exact("schema", "gpd_return.status"),
                    public_exact("help", "Quick Start"),
                    semantic_anchor("meaning", "stable semantic anchor"),
                    *semantic_concept(
                        "meaning concept",
                        required=(
                            "stable semantic anchor",
                            "this full sentence remains visible inside semantic helper diagnostics",
                        ),
                        forbidden=("the exact old sentence is gone forever",),
                    ),
                )
            """
        ).lstrip(),
        encoding="utf-8",
    )

    exactness = scan_exact_assertion_diagnostics(tmp_path)
    totals = exactness["totals"]
    usage = exactness["taxonomy_helper_usage"]
    assert isinstance(totals, dict)
    assert isinstance(usage, dict)
    usage_totals = usage["totals"]
    assert isinstance(usage_totals, dict)

    assert totals["exact_assertion_count"] == 2
    assert totals["machine_contract_exact_assertions"] == 1
    assert totals["public_ux_exact_assertions"] == 1
    assert totals["brittle_prose_assertions"] == 0
    assert usage_totals["assert_prompt_contracts"] == 1
    assert usage_totals["machine_exact"] == 1
    assert usage_totals["public_exact"] == 1
    assert usage_totals["semantic_anchor"] == 1
    assert usage_totals["semantic_concept"] == 1
    assert usage_totals["semantic_helper_literal_fragment_count"] == 4
    assert usage_totals["semantic_helper_long_prose_file_count"] == 1
    assert usage_totals["semantic_helper_long_prose_fragment_count"] == 1
    usage_row = usage["files"][0]
    assert isinstance(usage_row, dict)
    assert usage_row["semantic_helper_literal_fragment_count"] == 4
    assert usage_row["semantic_helper_long_prose_fragment_count"] == 1
    examples = usage_row["semantic_helper_long_prose_examples"]
    assert isinstance(examples, list)
    assert examples[0]["helper"] == "semantic_concept"
    assert examples[0]["field"] == "required"

    migration = exactness["migration"]
    assert isinstance(migration, dict)
    migration_totals = migration["totals"]
    assert isinstance(migration_totals, dict)
    migration_rows = _migration_files_by_path(exactness)
    migration_row = migration_rows["tests/test_prompt_contracts.py"]
    assert migration["schema_version"] == "exactness_migration.v1"
    assert migration_totals["taxonomy_helper_file_count"] == 1
    assert migration_totals["taxonomy_helper_brittle_file_count"] == 0
    assert migration_totals["taxonomy_helper_brittle_assertions"] == 0
    assert migration_row["machine_exact_keep_assertions"] == 1
    assert migration_row["public_exact_keep_assertions"] == 1
    assert migration_row["semantic_concept_candidate_assertions"] == 0
    assert migration_row["raw_brittle_prose_assertions"] == 0
    assert migration_row["taxonomy_helper_call_count"] == 5
    assert migration_row["semantic_helper_call_count"] == 2
    assert migration_row["taxonomy_helper_brittle_gate"] == "ok"


def test_exactness_migration_ledger_marks_helper_raw_brittle_candidates(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_prompt_contracts.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        textwrap.dedent(
            """
            from tests.assertion_taxonomy_support import assert_prompt_contracts, semantic_concept

            PROMPT = "stable semantic anchor\\n"

            def test_prompt_contracts():
                assert "This internal sentence should migrate toward conceptual coverage" in PROMPT
                assert_prompt_contracts(
                    PROMPT,
                    *semantic_concept("meaning", required=("stable semantic anchor",)),
                )
            """
        ).lstrip(),
        encoding="utf-8",
    )

    exactness = scan_exact_assertion_diagnostics(tmp_path)
    totals = exactness["totals"]
    assert isinstance(totals, dict)
    assert totals["exact_assertion_count"] == 1
    assert totals["brittle_prose_assertions"] == 1

    migration = exactness["migration"]
    assert isinstance(migration, dict)
    migration_totals = migration["totals"]
    assert isinstance(migration_totals, dict)
    migration_row = _migration_files_by_path(exactness)["tests/test_prompt_contracts.py"]
    assert migration_totals["semantic_concept_candidate_assertions"] == 1
    assert migration_totals["raw_brittle_prose_assertions"] == 1
    assert migration_totals["taxonomy_helper_brittle_file_count"] == 1
    assert migration_totals["taxonomy_helper_brittle_assertions"] == 1
    assert migration_row["semantic_concept_candidate_assertions"] == 1
    assert migration_row["raw_brittle_prose_assertions"] == 1
    assert migration_row["taxonomy_helper_brittle_gate"] == "soft_warn"
    examples = migration_row["examples"]
    assert isinstance(examples, dict)
    semantic_candidates = examples["semantic_concept_candidate"]
    assert isinstance(semantic_candidates, list)
    assert semantic_candidates[0]["migration_reason"] == "taxonomy_helper_file_brittle_prose"


def test_exactness_totals_do_not_grow_past_baseline() -> None:
    exactness = _exactness_payload()
    totals = exactness["totals"]
    assert isinstance(totals, dict)

    for field, budget in EXACTNESS_TOTAL_BUDGETS.items():
        observed = totals[field]
        assert isinstance(observed, int)
        assert observed <= budget, f"{field} budget exceeded: observed={observed} max={budget}"


def test_taxonomy_helper_usage_reaches_phase8_floor() -> None:
    exactness = _exactness_payload()
    usage = exactness["taxonomy_helper_usage"]
    assert isinstance(usage, dict)
    totals = usage["totals"]
    assert isinstance(totals, dict)

    for field, floor in TAXONOMY_HELPER_TOTAL_FLOORS.items():
        observed = totals[field]
        assert isinstance(observed, int)
        assert observed >= floor, f"{field} floor missed: observed={observed} min={floor}"


def test_semantic_helper_literal_fragments_are_measured_and_long_prose_is_bounded() -> None:
    exactness = _exactness_payload()
    usage = exactness["taxonomy_helper_usage"]
    assert isinstance(usage, dict)
    totals = usage["totals"]
    assert isinstance(totals, dict)

    for field, floor in SEMANTIC_HELPER_LITERAL_FRAGMENT_FLOORS.items():
        observed = totals[field]
        assert isinstance(observed, int)
        assert observed >= floor, f"{field} floor missed: observed={observed} min={floor}"

    for field, budget in SEMANTIC_HELPER_LONG_PROSE_BUDGETS.items():
        observed = totals[field]
        assert isinstance(observed, int)
        assert observed <= budget, f"{field} budget exceeded: observed={observed} max={budget}"


def test_exactness_migration_ledger_preserves_existing_exactness_totals() -> None:
    exactness = _exactness_payload()
    totals = exactness["totals"]
    migration = exactness["migration"]
    assert isinstance(totals, dict)
    assert isinstance(migration, dict)
    migration_totals = migration["totals"]
    assert isinstance(migration_totals, dict)

    assert migration_totals["machine_exact_keep_assertions"] == totals["machine_contract_exact_assertions"]
    assert migration_totals["public_exact_keep_assertions"] == totals["public_ux_exact_assertions"]
    assert migration_totals["raw_brittle_prose_assertions"] == totals["brittle_prose_assertions"]


def test_exactness_migration_bounded_top_limits_file_rows() -> None:
    bounded = bounded_exact_assertion_diagnostics(_exactness_payload(), 1)
    migration = bounded["migration"]
    assert isinstance(migration, dict)
    migration_rows = migration["files"]
    assert isinstance(migration_rows, list)
    assert len(migration_rows) == 1


def test_taxonomy_helper_files_do_not_gain_raw_brittle_prose() -> None:
    rows_by_path = _exactness_files_by_path()
    helper_rows = _taxonomy_helper_usage_files_by_path()
    failures: list[str] = []

    for path, usage in sorted(helper_rows.items()):
        row = rows_by_path.get(path, {})
        brittle_count = row.get("brittle_prose_assertions", 0)
        assert isinstance(brittle_count, int)
        baseline = TAXONOMY_HELPER_BRITTLE_BASELINES.get(path, 0)
        if brittle_count > baseline:
            failures.append(f"{path}: observed={brittle_count} max={baseline} helpers={usage.get('helpers', {})}")

    assert failures == []


def test_exactness_has_no_new_high_severity_files() -> None:
    rows_by_path = _exactness_files_by_path()
    high_paths = {path for path, row in rows_by_path.items() if row["severity"] == "high"}
    unexpected_high_paths = sorted(high_paths - set(HIGH_SEVERITY_BASELINES))

    assert unexpected_high_paths == []


def test_existing_high_severity_files_do_not_gain_exact_or_brittle_assertions() -> None:
    rows_by_path = _exactness_files_by_path()

    for path, baseline in HIGH_SEVERITY_BASELINES.items():
        row = rows_by_path.get(path)
        if row is None:
            continue
        exact_count = row["exact_assertion_count"]
        brittle_count = row["brittle_prose_assertions"]
        assert isinstance(exact_count, int)
        assert isinstance(brittle_count, int)
        assert exact_count <= baseline["exact"], (
            f"{path} exact assertion budget exceeded: observed={exact_count} max={baseline['exact']}"
        )
        assert brittle_count <= baseline["brittle"], (
            f"{path} brittle prose budget exceeded: observed={brittle_count} max={baseline['brittle']}"
        )
