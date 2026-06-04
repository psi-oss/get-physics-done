"""CLI smoke coverage for prompt-surface diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.cli import app


class _StableCliRunner(CliRunner):
    def invoke(self, *args, **kwargs):
        kwargs.setdefault("color", False)
        return super().invoke(*args, **kwargs)


runner = _StableCliRunner()
COMPACT_ONLY_MANIFEST_KEYS = {
    "authority_groups",
    "cold_authority_policy",
    "derived_init_field_rules",
    "must_not_eager_load_groups",
    "required_init_field_groups",
    "stage_defaults",
}


def _rendered_tail_after(output: str, marker: str) -> str:
    assert marker in output
    return output.split(marker, 1)[1]


def _non_native_runtime_name() -> str:
    return next(
        descriptor.runtime_name for descriptor in iter_runtime_descriptors() if not descriptor.native_include_support
    )


def _tree_snapshot(root: Path) -> tuple[tuple[str, bool, bytes], ...]:
    return tuple(
        sorted(
            (
                path.relative_to(root).as_posix(),
                path.is_dir(),
                b"" if path.is_dir() else path.read_bytes(),
            )
            for path in root.rglob("*")
        )
    )


def _assert_no_dashboard_keys(value: object) -> None:
    if isinstance(value, dict):
        assert all("dashboard" not in key for key in value)
        for child in value.values():
            _assert_no_dashboard_keys(child)
        return
    if isinstance(value, list):
        for child in value:
            _assert_no_dashboard_keys(child)


def _assert_no_compact_manifest_keys(value: object) -> None:
    if isinstance(value, dict):
        assert not (COMPACT_ONLY_MANIFEST_KEYS & set(value))
        for child in value.values():
            _assert_no_compact_manifest_keys(child)
        return
    if isinstance(value, list):
        for child in value:
            _assert_no_compact_manifest_keys(child)


def test_prompt_surface_diagnostics_raw_json_shape() -> None:
    result = runner.invoke(
        app,
        ["--raw", "diagnostics", "prompt-surface", "--top", "3", "--no-runtime-projections"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    assert payload["schema_version"]
    assert isinstance(payload["totals"], dict)
    assert 1 <= len(payload["items"]) <= 3
    assert payload["runtime_top_prompts"] == {}
    assert payload["stage_diagnostics"]
    assert len(payload["stage_diagnostics"]) <= 3
    assert payload["items"][0]["runtime_projection"] == []
    for key in (
        "review_contract_frontload_section_count",
        "review_contract_frontload_line_count",
        "review_contract_frontload_char_count",
    ):
        assert isinstance(payload["items"][0][key], int)
        assert payload["items"][0][key] >= 0
    assert isinstance(payload["invalid_gpd_return_examples"], list)
    assert isinstance(payload["invalid_frontmatter_examples"], list)
    assert isinstance(payload["disallowed_return_field_mentions"], list)
    assert isinstance(payload["stage_mechanics_prose_mentions"], list)
    assert isinstance(payload["manifest_must_not_duplicate_entries"], list)
    assert isinstance(payload["exactness_migration_rows"], list)
    assert len(payload["duplicate_invariants"]) <= 3
    assert isinstance(payload["semantic_duplicate_invariants"], list)
    assert len(payload["semantic_duplicate_invariants"]) <= 3
    assert all(len(group["examples"]) <= 3 for group in payload["semantic_duplicate_invariants"])
    stage_totals = payload["totals"]["stage_diagnostics"]
    assert stage_totals["workflow_count"] == 17
    assert stage_totals["must_not_eager_load_violation_count"] == 0
    assert stage_totals["must_not_eager_load_actionable_violation_count"] == 0
    assert stage_totals["manifest_must_not_duplicate_entry_count"] == 0
    assert stage_totals["manifest_must_not_duplicate_stage_count"] == 0
    assert stage_totals["manifest_must_not_duplicate_authority_count"] == 0
    _assert_no_compact_manifest_keys(payload["stage_diagnostics"])


def test_prompt_surface_diagnostics_dashboard_cli_smoke() -> None:
    result = runner.invoke(
        app,
        [
            "diagnostics",
            "prompt-surface",
            "--format",
            "dashboard",
            "--top",
            "3",
            "--include-tests",
            "--no-runtime-projections",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert not result.output.lstrip().startswith("{")
    output = result.output.casefold()
    for label in ("prompt surface", "prompt totals", "safety floors", "validation timing"):
        assert label in output


def test_prompt_surface_diagnostics_raw_dashboard_format_preserves_json_shape() -> None:
    base_result = runner.invoke(
        app,
        ["--raw", "diagnostics", "prompt-surface", "--top", "3", "--no-runtime-projections"],
        catch_exceptions=False,
    )
    dashboard_result = runner.invoke(
        app,
        [
            "--raw",
            "diagnostics",
            "prompt-surface",
            "--format",
            "dashboard",
            "--top",
            "3",
            "--no-runtime-projections",
        ],
        catch_exceptions=False,
    )

    assert base_result.exit_code == 0, base_result.output
    assert dashboard_result.exit_code == 0, dashboard_result.output
    base_payload = json.loads(base_result.output)
    dashboard_payload = json.loads(dashboard_result.output)

    assert dashboard_payload.keys() == base_payload.keys()
    assert dashboard_payload["items"][0].keys() == base_payload["items"][0].keys()
    assert dashboard_payload["stage_diagnostics"][0].keys() == base_payload["stage_diagnostics"][0].keys()
    assert dashboard_payload["runtime_top_prompts"] == {}
    _assert_no_dashboard_keys(dashboard_payload)


def test_prompt_surface_diagnostics_stage_authority_and_init_pressure_raw_shape() -> None:
    result = runner.invoke(
        app,
        ["--raw", "diagnostics", "prompt-surface", "--top", "20", "--no-runtime-projections"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    stage_totals = payload["totals"]["stage_diagnostics"]
    assert isinstance(stage_totals, dict)
    for key in (
        "stage_eager_char_count",
        "selected_init_content_field_count",
        "likely_bulky_init_field_count",
        "must_not_eager_load_prior_stage_residue_count",
        "repeated_prior_stage_residue_authority_count",
        "repeated_prior_stage_residue_occurrence_count",
        "repeated_prior_stage_residue_char_count",
        "repeated_prior_stage_residue_line_count",
    ):
        assert isinstance(stage_totals[key], int)
        assert stage_totals[key] >= 0

    residue_rows = payload["repeated_prior_stage_residue_rows"]
    assert isinstance(residue_rows, list)
    assert 1 <= len(residue_rows) <= 20
    residue_row = residue_rows[0]
    assert {
        "authority",
        "occurrence_count",
        "workflow_count",
        "stage_count",
        "expanded_char_count",
        "expanded_line_count",
        "first_turn_chain_count",
        "transitive_include_count",
        "workflows",
        "stages",
        "eager_via",
    } <= set(residue_row)
    assert isinstance(residue_row["authority"], str)
    assert residue_row["authority"].endswith(".md")
    for key in (
        "occurrence_count",
        "workflow_count",
        "stage_count",
        "expanded_char_count",
        "expanded_line_count",
        "first_turn_chain_count",
        "transitive_include_count",
    ):
        assert isinstance(residue_row[key], int)
        assert residue_row[key] > 0 if key != "transitive_include_count" else residue_row[key] >= 0
    assert isinstance(residue_row["workflows"], list)
    assert isinstance(residue_row["stages"], list)
    assert isinstance(residue_row["eager_via"], list)
    assert stage_totals["repeated_prior_stage_residue_occurrence_count"] >= residue_row["occurrence_count"]
    assert stage_totals["repeated_prior_stage_residue_char_count"] >= residue_row["expanded_char_count"]
    assert stage_totals["repeated_prior_stage_residue_line_count"] >= residue_row["expanded_line_count"]

    authority_rows = payload["stage_authority_top_prompts"]
    assert isinstance(authority_rows, list)
    assert 1 <= len(authority_rows) <= 20
    authority_row = authority_rows[0]
    assert {
        "workflow_id",
        "stage_id",
        "bucket",
        "authority",
        "expanded_char_count",
        "expanded_line_count",
        "raw_line_count",
        "raw_include_count",
        "transitive_include_count",
        "violation_source",
        "eager_via",
    } <= set(authority_row)
    assert authority_row["bucket"] in {
        "first_turn_active",
        "prior_stage_residue",
        "stage_eager",
        "conditional",
        "lazy",
        "violation",
    }
    assert isinstance(authority_row["authority"], str)
    assert authority_row["authority"].endswith(".md")
    assert isinstance(authority_row["expanded_char_count"], int)
    assert authority_row["expanded_char_count"] > 0
    assert isinstance(authority_row["transitive_include_count"], int)
    assert isinstance(authority_row["eager_via"], list)

    init_field_rows = payload["stage_init_field_diagnostics"]
    assert isinstance(init_field_rows, list)
    assert 1 <= len(init_field_rows) <= 20
    init_field_row = init_field_rows[0]
    assert {
        "workflow_id",
        "stage_id",
        "required_init_field_count",
        "likely_bulky_field_count",
        "field_name",
        "field_kind_guess",
        "field_pressure_class",
        "selection_count",
    } <= set(init_field_row)
    assert isinstance(init_field_row["field_name"], str)
    assert init_field_row["field_name"]
    assert isinstance(init_field_row["required_init_field_count"], int)
    assert init_field_row["required_init_field_count"] > 0
    assert isinstance(init_field_row["likely_bulky_field_count"], int)
    assert isinstance(init_field_row["selection_count"], int)
    assert init_field_row["selection_count"] > 0


def test_prompt_surface_diagnostics_include_tests_exactness_summary() -> None:
    result = runner.invoke(
        app,
        [
            "--raw",
            "diagnostics",
            "prompt-surface",
            "--include-tests",
            "--top",
            "1",
            "--no-runtime-projections",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    exactness = payload["exact_assertion_diagnostics"]
    assert exactness["schema_version"] == "exact_assertions.v1"
    assert exactness["totals"]["files_scanned"] > 0
    assert exactness["totals"]["exact_assertion_count"] > 0
    assert len(exactness["files"]) == 1
    assert exactness["taxonomy_helper_usage"]["schema_version"] == "taxonomy_helper_usage.v1"
    assert exactness["taxonomy_helper_usage"]["totals"]["taxonomy_helper_call_count"] > 0
    assert len(exactness["taxonomy_helper_usage"]["files"]) == 1
    assert isinstance(payload["exactness_migration_rows"], list)
    assert len(payload["exact_prose_assertion_files"]) == 1


def test_prompt_surface_diagnostics_stage_authority_and_init_pressure_renderers() -> None:
    markdown_result = runner.invoke(
        app,
        ["diagnostics", "prompt-surface", "--top", "5", "--no-runtime-projections", "--format", "markdown"],
        catch_exceptions=False,
    )
    table_result = runner.invoke(
        app,
        ["diagnostics", "prompt-surface", "--top", "5", "--no-runtime-projections"],
        catch_exceptions=False,
    )

    assert markdown_result.exit_code == 0, markdown_result.output
    markdown_authority = _rendered_tail_after(markdown_result.output, "## Stage Authority Hotspots")
    for column in (
        "Workflow",
        "Stage",
        "Bucket",
        "Authority",
        "Expanded chars",
        "Transitive includes",
    ):
        assert column in markdown_authority
    markdown_init_fields = _rendered_tail_after(markdown_result.output, "## Staged-Init Field Pressure")
    for column in (
        "Workflow",
        "Stage",
        "Required fields",
        "Likely bulky",
        "Field",
        "Kind",
        "Pressure",
        "Selections",
    ):
        assert column in markdown_init_fields
    markdown_stage_loading = _rendered_tail_after(markdown_result.output, "## Stage-Aware Staged Loading")
    for column in ("Residue chars", "Residue lines", "Residue records"):
        assert column in markdown_stage_loading
    markdown_residue = _rendered_tail_after(markdown_result.output, "## Prior-Stage Residue Contributors")
    for column in (
        "Authority",
        "Occurrences",
        "Workflows",
        "Stages",
        "Expanded chars",
        "Expanded lines",
        "First-turn chains",
        "Transitive includes",
        "Eager via",
    ):
        assert column in markdown_residue

    assert table_result.exit_code == 0, table_result.output
    table_authority = _rendered_tail_after(table_result.output, "stage authority hotspots")
    for column in ("workflow", "stage", "bucket", "authority", "expanded_chars", "transitive_includes"):
        assert column in table_authority
    table_init_fields = _rendered_tail_after(table_result.output, "staged-init field pressure")
    for column in (
        "workflow",
        "stage",
        "required_fields",
        "likely_bulky",
        "field_name",
        "field_kind",
        "pressure",
        "selections",
    ):
        assert column in table_init_fields
    table_stage_loading = _rendered_tail_after(table_result.output, "stage top prompts")
    for column in ("residue_chars", "residue_lines", "residue_records"):
        assert column in table_stage_loading
    table_residue = _rendered_tail_after(table_result.output, "prior-stage residue contributors")
    for column in (
        "authority",
        "occurrences",
        "workflows",
        "stages",
        "expanded_chars",
        "expanded_lines",
        "first_turn_chains",
        "transitive_includes",
        "eager_via",
    ):
        assert column in table_residue


def test_prompt_surface_diagnostics_runtime_projection_and_renderers() -> None:
    runtime_name = _non_native_runtime_name()
    raw_result = runner.invoke(
        app,
        ["--raw", "diagnostics", "prompt-surface", "--top", "1", "--surface", "command", "--runtime", runtime_name],
        catch_exceptions=False,
    )
    markdown_result = runner.invoke(
        app,
        ["diagnostics", "prompt-surface", "--top", "1", "--no-runtime-projections", "--format", "markdown"],
        catch_exceptions=False,
    )
    table_result = runner.invoke(
        app,
        ["diagnostics", "prompt-surface", "--top", "1", "--surface", "command", "--runtime", runtime_name],
        catch_exceptions=False,
    )

    assert raw_result.exit_code == 0, raw_result.output
    payload = json.loads(raw_result.output)
    projection = payload["items"][0]["runtime_projection"][0]
    assert projection["runtime"] == runtime_name
    assert isinstance(projection["expanded_char_count"], int)
    assert isinstance(projection["shell_rewrite_count"], int)
    assert payload["runtime_top_prompts"][runtime_name][0]["runtime"] == runtime_name

    assert markdown_result.exit_code == 0, markdown_result.output
    assert "Prompt Surface Diagnostics" in markdown_result.output
    assert ".md" in markdown_result.output
    assert (
        "| Rank | Kind | Name | Expanded chars | Raw lines | Includes | Hard gates | "
        "Shell parse | Schemas | Invalid returns | Invalid frontmatter | Bad fields | Rigidity |"
    ) in markdown_result.output.splitlines()

    assert table_result.exit_code == 0, table_result.output
    header = table_result.output.splitlines()[0]
    for column in (
        "kind",
        "name",
        "expanded_chars",
        "includes",
        "schemas",
        "invalid",
        "bad_frontmatter",
        "bad_fields",
        "hard_gates",
        "shell_parse",
        "rigidity",
    ):
        assert column in header
    assert header.endswith("rigidity")
    assert "runtime top prompts" in table_result.output
    assert "projected_chars" in table_result.output
    assert runtime_name in table_result.output


def test_prompt_surface_diagnostics_is_read_only_outside_project(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("scratch notes, not a GPD project\n", encoding="utf-8")
    before = _tree_snapshot(workspace)

    monkeypatch.chdir(workspace)
    result = runner.invoke(
        app,
        [
            "--cwd",
            str(workspace),
            "--raw",
            "diagnostics",
            "prompt-surface",
            "--top",
            "3",
            "--no-runtime-projections",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    json.loads(result.output)
    assert _tree_snapshot(workspace) == before
