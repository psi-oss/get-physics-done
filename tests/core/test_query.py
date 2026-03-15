"""Tests for gpd.core.query — cross-phase result queries."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from gpd.core.errors import QueryError
from gpd.core.query import (
    AssumptionsResult,
    DepsResult,
    QueryResult,
    collect_summaries,
    extract_context,
    extract_requires_values,
    parse_phase_range,
    query,
    query_assumptions,
    query_deps,
    resolve_field,
    term_matches,
)

# ─── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a project with phase SUMMARY files for testing."""
    phases_dir = tmp_path / ".gpd" / "phases"

    # Phase 01
    p01 = phases_dir / "01-formalism"
    p01.mkdir(parents=True)
    (p01 / "01-01-SUMMARY.md").write_text(
        dedent("""\
        ---
        provides:
          - bare-hamiltonian
          - spectral-gap
        requires: []
        affects:
          - energy-spectrum
        approximations:
          - "weak coupling: g << 1"
        conventions:
          - "metric signature: (-,+,+,+)"
        ---
        # Phase 01 Summary

        We derived the bare Hamiltonian H = p^2/2m + V(x).
        The spectral gap is Delta = 1.5 eV.
    """)
    )

    # Phase 02
    p02 = phases_dir / "02-perturbation"
    p02.mkdir(parents=True)
    (p02 / "02-01-SUMMARY.md").write_text(
        dedent("""\
        ---
        provides:
          - effective-hamiltonian
        requires:
          - provides: bare-hamiltonian
            phase: phase-01-plan-01
        affects:
          - energy-spectrum
        key-decisions:
          - "Use Rayleigh-Schrodinger perturbation theory"
        ---
        # Phase 02 Summary

        Applied perturbation theory to obtain the effective Hamiltonian.
        The correction term is delta_H = g * V_1.
    """)
    )

    # Phase 03 (with SUMMARY.md instead of plan-SUMMARY.md)
    p03 = phases_dir / "03-results"
    p03.mkdir(parents=True)
    (p03 / "SUMMARY.md").write_text(
        dedent("""\
        ---
        provides:
          - scattering-amplitude
        dependency-graph:
          requires:
            - provides: effective-hamiltonian
              phase: phase-02-plan-01
        ---
        # Phase 03 Summary

        Computed the scattering amplitude T = -i * g^2 / (E - E_0).
        This uses the weak coupling approximation.
    """)
    )

    return tmp_path


@pytest.fixture
def empty_project(tmp_path: Path) -> Path:
    """Create a project with no phases."""
    (tmp_path / ".gpd").mkdir()
    return tmp_path


# ─── Helpers ─────────────────────────────────────────────────────────────────────


class TestTermMatches:
    def test_substring_match(self) -> None:
        assert term_matches("hamiltonian", "bare-hamiltonian") is True

    def test_case_insensitive(self) -> None:
        assert term_matches("HAMILTONIAN", "bare-hamiltonian") is True

    def test_no_match(self) -> None:
        assert term_matches("lagrangian", "bare-hamiltonian") is False

    def test_empty_term(self) -> None:
        assert term_matches("", "value") is False

    def test_empty_value(self) -> None:
        assert term_matches("term", "") is False


class TestResolveField:
    def test_top_level(self) -> None:
        fm = {"provides": ["a", "b"]}
        assert resolve_field(fm, "provides") == ["a", "b"]

    def test_top_level_scalar_is_wrapped(self) -> None:
        fm = {"provides": "bare-hamiltonian"}
        assert resolve_field(fm, "provides") == ["bare-hamiltonian"]

    def test_top_level_object_is_wrapped(self) -> None:
        fm = {"provides": {"name": "bare-hamiltonian"}}
        assert resolve_field(fm, "provides") == [{"name": "bare-hamiltonian"}]

    def test_nested_in_dependency_graph(self) -> None:
        fm = {"dependency-graph": {"requires": [{"phase": "01", "provides": "x"}]}}
        assert resolve_field(fm, "requires") == [{"phase": "01", "provides": "x"}]

    def test_nested_scalar_in_dependency_graph_is_wrapped(self) -> None:
        fm = {"dependency-graph": {"requires": "bare-hamiltonian"}}
        assert resolve_field(fm, "requires") == ["bare-hamiltonian"]

    def test_prefers_dependency_graph(self) -> None:
        fm = {"requires": ["top"], "dependency-graph": {"requires": ["nested"]}}
        assert resolve_field(fm, "requires") == ["nested"]

    def test_missing_field(self) -> None:
        assert resolve_field({"provides": ["a"]}, "requires") == []

    def test_empty_fm(self) -> None:
        assert resolve_field({}, "provides") == []

    def test_none_fm(self) -> None:
        assert resolve_field(None, "provides") == []


class TestExtractRequiresValues:
    def test_strings(self) -> None:
        assert extract_requires_values(["a", "b"]) == ["a", "b"]

    def test_objects(self) -> None:
        values = extract_requires_values([{"provides": "x", "phase": "y"}])
        assert "x" in values
        assert "y" in values

    def test_mixed(self) -> None:
        values = extract_requires_values(["a", {"provides": "b"}])
        assert "a" in values
        assert "b" in values

    def test_objects_with_scalar_and_list_values(self) -> None:
        values = extract_requires_values([{"provides": ["x", "y"], "phase": "phase-01"}])
        assert values == ["x", "y", "phase-01"]


class TestParsePhaseRange:
    def test_single_phase(self) -> None:
        assert parse_phase_range("3") == ("3", "3")

    def test_range(self) -> None:
        assert parse_phase_range("1-5") == ("1", "5")

    def test_decimal_phase(self) -> None:
        assert parse_phase_range("2.1.1") == ("2.1.1", "2.1.1")

    def test_invalid(self) -> None:
        assert parse_phase_range("abc") is None

    def test_none(self) -> None:
        assert parse_phase_range(None) is None

    def test_empty(self) -> None:
        assert parse_phase_range("") is None


class TestExtractContext:
    def test_found(self) -> None:
        text = "The Hamiltonian is H = p^2/2m + V(x)."
        ctx = extract_context(text, "Hamiltonian")
        assert ctx is not None
        assert "Hamiltonian" in ctx

    def test_not_found(self) -> None:
        assert extract_context("some text", "missing") is None

    def test_ellipsis_added(self) -> None:
        text = "x" * 200 + "TARGET" + "y" * 200
        ctx = extract_context(text, "TARGET")
        assert ctx is not None
        assert ctx.startswith("...")
        assert ctx.endswith("...")

    def test_none_inputs(self) -> None:
        assert extract_context(None, "term") is None
        assert extract_context("text", None) is None


# ─── collect_summaries ───────────────────────────────────────────────────────────


class TestCollectSummaries:
    def test_collects_all(self, project_dir: Path) -> None:
        summaries = collect_summaries(project_dir)
        assert len(summaries) == 3
        phases = [s.phase for s in summaries]
        assert "1" in phases or "01" in phases

    def test_sorted_by_phase(self, project_dir: Path) -> None:
        summaries = collect_summaries(project_dir)
        phase_nums = [int(s.phase.split(".")[0]) for s in summaries]
        assert phase_nums == sorted(phase_nums)

    def test_empty_project(self, empty_project: Path) -> None:
        assert collect_summaries(empty_project) == []

    def test_parses_frontmatter(self, project_dir: Path) -> None:
        summaries = collect_summaries(project_dir)
        s01 = next(s for s in summaries if s.phase in ("1", "01"))
        assert "provides" in s01.frontmatter
        assert "bare-hamiltonian" in s01.frontmatter["provides"]

    def test_extracts_body(self, project_dir: Path) -> None:
        summaries = collect_summaries(project_dir)
        s01 = next(s for s in summaries if s.phase in ("1", "01"))
        assert "bare Hamiltonian" in s01.body

    def test_plan_id_from_filename(self, project_dir: Path) -> None:
        summaries = collect_summaries(project_dir)
        s03 = next(s for s in summaries if s.phase in ("3", "03"))
        assert s03.plan is None  # SUMMARY.md has no plan prefix

    def test_skips_parse_errors(self, tmp_path: Path) -> None:
        phases_dir = tmp_path / ".gpd" / "phases" / "01-test"
        phases_dir.mkdir(parents=True)
        (phases_dir / "01-01-SUMMARY.md").write_text("---\nbad: [yaml: {{\n---\n")
        summaries = collect_summaries(tmp_path)
        assert len(summaries) == 0

    def test_skips_invalid_utf8_summary_files(self, tmp_path: Path) -> None:
        bad_phase_dir = tmp_path / ".gpd" / "phases" / "01-bad"
        bad_phase_dir.mkdir(parents=True)
        (bad_phase_dir / "01-01-SUMMARY.md").write_bytes(b"\xff\xfe\x00\x80invalid")

        good_phase_dir = tmp_path / ".gpd" / "phases" / "02-good"
        good_phase_dir.mkdir(parents=True)
        (good_phase_dir / "02-01-SUMMARY.md").write_text(
            dedent("""\
            ---
            provides:
              - valid-result
            ---
            # Phase 02 Summary

            This summary should still be collected.
        """)
        )

        summaries = collect_summaries(tmp_path)

        assert len(summaries) == 1
        assert summaries[0].phase in ("2", "02")
        assert summaries[0].file == "02-01-SUMMARY.md"


# ─── query ───────────────────────────────────────────────────────────────────────


class TestQuery:
    def test_query_provides(self, project_dir: Path) -> None:
        result = query(project_dir, provides="hamiltonian")
        assert isinstance(result, QueryResult)
        assert result.total >= 1
        fields = [m.field for m in result.matches]
        assert "provides" in fields

    def test_query_requires(self, project_dir: Path) -> None:
        result = query(project_dir, requires="bare-hamiltonian")
        assert result.total >= 1

    def test_query_affects(self, project_dir: Path) -> None:
        result = query(project_dir, affects="energy-spectrum")
        assert result.total >= 1

    def test_query_equation(self, project_dir: Path) -> None:
        result = query(project_dir, equation="p^2/2m")
        assert result.total >= 1
        fields = [m.field for m in result.matches]
        assert "equation" in fields

    def test_query_text(self, project_dir: Path) -> None:
        result = query(project_dir, text="scattering")
        assert result.total >= 1

    def test_query_no_filters_returns_all(self, project_dir: Path) -> None:
        result = query(project_dir)
        assert result.total == 3  # All 3 summaries

    def test_query_no_match(self, project_dir: Path) -> None:
        result = query(project_dir, provides="nonexistent-thing")
        assert result.total == 0

    def test_query_empty_project(self, empty_project: Path) -> None:
        result = query(empty_project, provides="anything")
        assert result.total == 0

    def test_query_phase_range(self, project_dir: Path) -> None:
        result = query(project_dir, phase_range="1-2")
        # Should only return phases 1 and 2
        for m in result.matches:
            phase_num = int(m.phase.split(".")[0])
            assert 1 <= phase_num <= 2

    def test_query_text_handles_yaml_dates_in_frontmatter(self, project_dir: Path) -> None:
        phase_dir = project_dir / ".gpd" / "phases" / "04-dated-frontmatter"
        phase_dir.mkdir(parents=True)
        (phase_dir / "04-01-SUMMARY.md").write_text(
            dedent("""\
            ---
            completed: 2026-03-14
            notes: renormalization note
            ---
            # Phase 04 Summary

            Body text intentionally unrelated.
        """)
        )

        result = query(project_dir, text="renormalization note")

        assert any(m.phase in ("4", "04") and m.field == "text" for m in result.matches)

    def test_query_provides_handles_yaml_dates_in_structured_values(self, project_dir: Path) -> None:
        phase_dir = project_dir / ".gpd" / "phases" / "04-structured-provides"
        phase_dir.mkdir(parents=True)
        (phase_dir / "04-02-SUMMARY.md").write_text(
            dedent("""\
            ---
            provides:
              - name: dated-result
                recorded: 2026-03-14
            ---
            # Phase 04 Summary

            Structured provides entry.
        """)
        )

        result = query(project_dir, provides="dated-result")

        assert any(m.phase in ("4", "04") and m.field == "provides" for m in result.matches)


# ─── query_deps ──────────────────────────────────────────────────────────────────


class TestQueryDeps:
    def test_deps_finds_provider(self, project_dir: Path) -> None:
        result = query_deps(project_dir, "bare-hamiltonian")
        assert isinstance(result, DepsResult)
        assert result.provides_by is not None
        assert result.provides_by.phase in ("1", "01")

    def test_deps_finds_consumers(self, project_dir: Path) -> None:
        result = query_deps(project_dir, "bare-hamiltonian")
        assert len(result.required_by) >= 1

    def test_deps_no_match(self, project_dir: Path) -> None:
        result = query_deps(project_dir, "nonexistent")
        assert result.provides_by is None
        assert result.required_by == []

    def test_deps_empty_identifier_raises(self, project_dir: Path) -> None:
        with pytest.raises(QueryError, match="identifier required"):
            query_deps(project_dir, "")

    def test_deps_accepts_scalar_provides_and_requires(self, tmp_path: Path) -> None:
        phase1 = tmp_path / ".gpd" / "phases" / "01-setup"
        phase1.mkdir(parents=True)
        (phase1 / "01-01-SUMMARY.md").write_text(
            dedent("""\
            ---
            provides: bare-hamiltonian
            ---
            # Summary
            """)
        )

        phase2 = tmp_path / ".gpd" / "phases" / "02-core"
        phase2.mkdir(parents=True)
        (phase2 / "02-01-SUMMARY.md").write_text(
            dedent("""\
            ---
            requires: bare-hamiltonian
            ---
            # Summary
            """)
        )

        result = query_deps(tmp_path, "bare-hamiltonian")

        assert result.provides_by is not None
        assert result.provides_by.phase in ("1", "01")
        assert len(result.required_by) == 1
        assert result.required_by[0].phase in ("2", "02")


# ─── query_assumptions ───────────────────────────────────────────────────────────


class TestQueryAssumptions:
    def test_finds_in_approximations(self, project_dir: Path) -> None:
        result = query_assumptions(project_dir, "weak coupling")
        assert isinstance(result, AssumptionsResult)
        assert result.total >= 1
        found_locations = set()
        for a in result.affected_phases:
            found_locations.update(a.found_in)
        assert "approximations" in found_locations or "body" in found_locations

    def test_finds_in_conventions(self, project_dir: Path) -> None:
        result = query_assumptions(project_dir, "metric signature")
        assert result.total >= 1

    def test_finds_in_key_decisions(self, project_dir: Path) -> None:
        result = query_assumptions(project_dir, "Rayleigh-Schrodinger")
        assert result.total >= 1
        found_locations = set()
        for a in result.affected_phases:
            found_locations.update(a.found_in)
        assert "key-decisions" in found_locations or "body" in found_locations

    def test_finds_in_body(self, project_dir: Path) -> None:
        result = query_assumptions(project_dir, "perturbation theory")
        assert result.total >= 1

    def test_no_match(self, project_dir: Path) -> None:
        result = query_assumptions(project_dir, "string theory compactification")
        assert result.total == 0

    def test_empty_assumption_raises(self, project_dir: Path) -> None:
        with pytest.raises(QueryError, match="assumption term required"):
            query_assumptions(project_dir, "")

    def test_fallback_frontmatter_search_handles_yaml_dates(self, project_dir: Path) -> None:
        phase_dir = project_dir / ".gpd" / "phases" / "05-dated-assumptions"
        phase_dir.mkdir(parents=True)
        (phase_dir / "05-01-SUMMARY.md").write_text(
            dedent("""\
            ---
            completed: 2026-03-14
            notes: adiabatic switching remains assumed
            ---
            # Phase 05 Summary

            Body text intentionally unrelated.
        """)
        )

        result = query_assumptions(project_dir, "adiabatic switching")

        assert any(
            a.phase in ("5", "05") and "frontmatter" in a.found_in
            for a in result.affected_phases
        )
