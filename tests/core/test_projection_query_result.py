"""Phase 16 oracle coverage for the query/result projection family."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"
runner = CliRunner()


@dataclass(frozen=True, slots=True)
class ProjectionOracleCase:
    fixture_slug: str
    variant: str
    comparison_kind: str
    term_or_identifier: str
    expected_snapshot: dict[str, object]


PHASE16_QUERY_RESULT_CASES: tuple[ProjectionOracleCase, ...] = (
    ProjectionOracleCase(
        fixture_slug="query-registry-drift",
        variant="positive",
        comparison_kind="text-projection",
        term_or_identifier="semiclassical",
        expected_snapshot={
            "fixture": {"slug": "query-registry-drift", "variant": "positive"},
            "query_search": {
                "term": "semiclassical",
                "hit_phases": ("01", "03"),
                "fields": ("text",),
                "total": 2,
            },
            "query_assumptions": {
                "term": "semiclassical",
                "hit_phases": ("01", "03"),
                "found_in": ("body",),
                "total": 2,
            },
            "result_search": {
                "term": "semiclassical",
                "hit_phases": ("01", "02"),
                "result_ids": ("lit-antonini-2023", "lit-manu-2021"),
                "total": 2,
            },
            "known_gap": {
                "class": "projection-gap-expected",
                "fields": ("query_search.hit_phases", "query_assumptions.hit_phases", "result_search.hit_phases"),
            },
        },
    ),
    ProjectionOracleCase(
        fixture_slug="context-indexing",
        variant="positive",
        comparison_kind="deps-projection",
        term_or_identifier="R-05-ml-window",
        expected_snapshot={
            "fixture": {"slug": "context-indexing", "variant": "positive"},
            "query_deps": {
                "identifier": "R-05-ml-window",
                "provides_by": None,
                "provider_conflicts": (),
                "required_by": (),
            },
            "result_deps": {
                "identifier": "R-05-ml-window",
                "result_id": "R-05-ml-window",
                "depends_on": ("R-03-integrality", "R-04-geometry"),
                "direct_dep_ids": ("R-03-integrality", "R-04-geometry"),
                "transitive_dep_ids": ("R-02-gap-bound", "R-01-foundation"),
            },
            "known_gap": {
                "class": "projection-gap-expected",
                "fields": (
                    "query_deps.provides_by",
                    "query_deps.required_by",
                    "result_deps.direct_dep_ids",
                    "result_deps.transitive_dep_ids",
                ),
            },
        },
    ),
    ProjectionOracleCase(
        fixture_slug="bridge-vs-cli",
        variant="positive",
        comparison_kind="text-projection",
        term_or_identifier="observer",
        expected_snapshot={
            "fixture": {"slug": "bridge-vs-cli", "variant": "positive"},
            "query_search": {
                "term": "observer",
                "hit_phases": ("01",),
                "fields": ("text",),
                "total": 1,
            },
            "query_assumptions": {
                "term": "observer",
                "hit_phases": ("01",),
                "found_in": ("body",),
                "total": 1,
            },
            "result_search": {
                "term": "observer",
                "hit_phases": (),
                "result_ids": (),
                "total": 0,
            },
            "known_gap": {
                "class": "projection-gap-expected",
                "fields": ("query_search.hit_phases", "query_search.total", "result_search.total"),
            },
        },
    ),
    ProjectionOracleCase(
        fixture_slug="bridge-vs-cli",
        variant="mutation",
        comparison_kind="text-projection",
        term_or_identifier="observer",
        expected_snapshot={
            "fixture": {"slug": "bridge-vs-cli", "variant": "mutation"},
            "query_search": {
                "term": "observer",
                "hit_phases": ("01",),
                "fields": ("text",),
                "total": 1,
            },
            "query_assumptions": {
                "term": "observer",
                "hit_phases": ("01",),
                "found_in": ("body",),
                "total": 1,
            },
            "result_search": {
                "term": "observer",
                "hit_phases": (),
                "result_ids": (),
                "total": 0,
            },
            "known_gap": {
                "class": "projection-gap-expected",
                "fields": ("query_search.hit_phases", "query_search.total", "result_search.total"),
            },
        },
    ),
)


def _copy_fixture_workspace(tmp_path: Path, fixture_slug: str, variant: str) -> Path:
    source = FIXTURES_DIR / fixture_slug / variant / "workspace"
    destination = tmp_path / f"{fixture_slug}-{variant}"
    shutil.copytree(source, destination)
    return destination


def _run_raw_json(workspace: Path, *argv: str) -> dict[str, object]:
    result = runner.invoke(app, ["--raw", "--cwd", str(workspace), *argv], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _normalize_query_search(payload: dict[str, object], term: str) -> dict[str, object]:
    return {
        "term": term,
        "hit_phases": tuple(match["phase"] for match in payload["matches"]),
        "fields": tuple(dict.fromkeys(match["field"] for match in payload["matches"])),
        "total": payload["total"],
    }


def _normalize_query_assumptions(payload: dict[str, object], term: str) -> dict[str, object]:
    return {
        "term": term,
        "hit_phases": tuple(entry["phase"] for entry in payload["affected_phases"]),
        "found_in": tuple(dict.fromkeys(found_in for entry in payload["affected_phases"] for found_in in entry["found_in"])),
        "total": payload["total"],
    }


def _normalize_result_search(payload: dict[str, object], term: str) -> dict[str, object]:
    return {
        "term": term,
        "hit_phases": tuple(match["phase"] for match in payload["matches"]),
        "result_ids": tuple(match["id"] for match in payload["matches"]),
        "total": payload["total"],
    }


def _normalize_query_deps(payload: dict[str, object], identifier: str) -> dict[str, object]:
    provider = payload["provides_by"]
    return {
        "identifier": identifier,
        "provides_by": None if provider is None else provider.get("value"),
        "provider_conflicts": tuple(conflict.get("value") for conflict in payload["provider_conflicts"]),
        "required_by": tuple(entry.get("value") for entry in payload["required_by"]),
    }


def _normalize_result_deps(payload: dict[str, object], identifier: str) -> dict[str, object]:
    return {
        "identifier": identifier,
        "result_id": payload["result"]["id"],
        "depends_on": tuple(payload["depends_on"]),
        "direct_dep_ids": tuple(entry["id"] for entry in payload["direct_deps"]),
        "transitive_dep_ids": tuple(entry["id"] for entry in payload["transitive_deps"]),
    }


@pytest.mark.parametrize("case", PHASE16_QUERY_RESULT_CASES, ids=lambda case: f"{case.fixture_slug}-{case.variant}")
def test_projection_query_result_oracle(case: ProjectionOracleCase, tmp_path: Path) -> None:
    workspace = _copy_fixture_workspace(tmp_path, case.fixture_slug, case.variant)
    snapshot: dict[str, object] = {"fixture": {"slug": case.fixture_slug, "variant": case.variant}}

    if case.comparison_kind == "text-projection":
        query_search_payload = _run_raw_json(workspace, "query", "search", "--text", case.term_or_identifier)
        query_assumptions_payload = _run_raw_json(workspace, "query", "assumptions", case.term_or_identifier)
        result_search_payload = _run_raw_json(workspace, "result", "search", "--text", case.term_or_identifier)

        snapshot["query_search"] = _normalize_query_search(query_search_payload, case.term_or_identifier)
        snapshot["query_assumptions"] = _normalize_query_assumptions(query_assumptions_payload, case.term_or_identifier)
        snapshot["result_search"] = _normalize_result_search(result_search_payload, case.term_or_identifier)
    elif case.comparison_kind == "deps-projection":
        query_deps_payload = _run_raw_json(workspace, "query", "deps", case.term_or_identifier)
        result_deps_payload = _run_raw_json(workspace, "result", "deps", case.term_or_identifier)

        snapshot["query_deps"] = _normalize_query_deps(query_deps_payload, case.term_or_identifier)
        snapshot["result_deps"] = _normalize_result_deps(result_deps_payload, case.term_or_identifier)
    else:  # pragma: no cover - defensive guard for future case expansion
        raise AssertionError(f"Unknown comparison kind: {case.comparison_kind}")

    snapshot["known_gap"] = case.expected_snapshot["known_gap"]

    assert snapshot == case.expected_snapshot


def test_projection_query_result_bridge_mutation_matches_positive_snapshot(tmp_path: Path) -> None:
    positive_workspace = _copy_fixture_workspace(tmp_path, "bridge-vs-cli", "positive")
    mutation_workspace = _copy_fixture_workspace(tmp_path, "bridge-vs-cli", "mutation")

    positive_snapshot = {
        "query_search": _normalize_query_search(_run_raw_json(positive_workspace, "query", "search", "--text", "observer"), "observer"),
        "query_assumptions": _normalize_query_assumptions(
            _run_raw_json(positive_workspace, "query", "assumptions", "observer"),
            "observer",
        ),
        "result_search": _normalize_result_search(_run_raw_json(positive_workspace, "result", "search", "--text", "observer"), "observer"),
    }
    mutation_snapshot = {
        "query_search": _normalize_query_search(_run_raw_json(mutation_workspace, "query", "search", "--text", "observer"), "observer"),
        "query_assumptions": _normalize_query_assumptions(
            _run_raw_json(mutation_workspace, "query", "assumptions", "observer"),
            "observer",
        ),
        "result_search": _normalize_result_search(_run_raw_json(mutation_workspace, "result", "search", "--text", "observer"), "observer"),
    }

    assert mutation_snapshot == positive_snapshot
