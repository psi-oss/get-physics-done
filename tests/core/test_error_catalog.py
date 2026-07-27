"""Tests for gpd.core.error_catalog — physics error catalog domain logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.error_catalog import (
    ERROR_CATALOG_FILES,
    ERROR_DOMAIN_RANGES,
    ERROR_ID_RANGE_LABEL,
    KNOWN_ERROR_DOMAINS,
    MAX_ERROR_CLASS_MATCHES,
    REFERENCES_DIR,
    TRACEABILITY_COLUMNS,
    TRACEABILITY_FILE,
    ErrorStore,
    check_error_classes,
    get_detection_strategy,
    get_error_class,
    get_error_store,
    get_traceability,
    list_error_classes,
    normalize_computation_description,
    normalize_error_domain,
)

TOTAL_ERROR_CLASSES = 104

_CATALOG_HEADER = "| # | Error Class | Description | Detection Strategy | Example |\n|---|---|---|---|---|\n"


@pytest.fixture(scope="module")
def store() -> ErrorStore:
    """The shipped catalog parsed from specs/references (no fixtures, real files)."""
    return get_error_store()


def _write_catalog(tmp_path: Path, filename: str, rows: str) -> Path:
    path = tmp_path / "verification" / "errors" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_CATALOG_HEADER + rows, encoding="utf-8")
    return path


def test_shipped_catalog_loads_all_error_classes(store: ErrorStore) -> None:
    assert store.count == TOTAL_ERROR_CLASSES
    assert sorted(store.list_all(), key=lambda entry: int(str(entry["id"])))[0]["id"] == 1
    assert [entry["id"] for entry in store.list_all()][-1] == TOTAL_ERROR_CLASSES
    assert store.domains == sorted(KNOWN_ERROR_DOMAINS)
    assert ERROR_ID_RANGE_LABEL == f"1-{TOTAL_ERROR_CLASSES}"


def test_catalog_source_files_are_attributed_to_their_declared_part_file(store: ErrorStore) -> None:
    sources = {str(store.get(error_id)["source_file"]) for error_id in (1, 30, 60, 90, 103)}

    assert sources == {
        "llm-errors-core.md",
        "llm-errors-field-theory.md",
        "llm-errors-extended.md",
        "llm-errors-deep.md",
    }
    assert [Path(name).name for name in ERROR_CATALOG_FILES] == [
        "llm-errors-core.md",
        "llm-errors-field-theory.md",
        "llm-errors-extended.md",
        "llm-errors-deep.md",
    ]


def test_get_error_class_returns_full_record_for_valid_id(store: ErrorStore) -> None:
    record = get_error_class(store, 1)

    assert record == {
        "id": 1,
        "name": store.get(1)["name"],
        "description": store.get(1)["description"],
        "detection_strategy": store.get(1)["detection_strategy"],
        "example": store.get(1)["example"],
        "domain": "core",
        "source_file": "llm-errors-core.md",
    }
    assert record["name"] == "Wrong Clebsch-Gordan coefficients"
    assert "error" not in record


def test_get_error_class_rejects_ids_outside_the_catalog_range(store: ErrorStore) -> None:
    assert get_error_class(store, 105) == {
        "valid_range": "1-104",
        "total_classes": TOTAL_ERROR_CLASSES,
        "error": "Error class #105 not found",
    }
    assert get_error_class(store, 0)["error"] == "Error class #0 not found"
    assert get_detection_strategy(store, 105) == {
        "valid_range": "1-104",
        "error": "Error class #105 not found",
    }
    assert get_traceability(store, 105) == {
        "valid_range": "1-104",
        "error": "Error class #105 not found",
    }


def test_error_class_payloads_match_the_mcp_server_envelopes(store: ErrorStore) -> None:
    from gpd.mcp.servers import errors_mcp

    found = errors_mcp.get_error_class(1)
    missing = errors_mcp.get_error_class(105)
    detection = errors_mcp.get_detection_strategy(1)
    traceability = errors_mcp.get_traceability(1)
    listed = errors_mcp.list_error_classes("core")

    assert dict(found) == {**get_error_class(store, 1), "schema_version": 1}
    assert dict(missing) == {**get_error_class(store, 105), "schema_version": 1}
    assert dict(detection) == {**get_detection_strategy(store, 1), "schema_version": 1}
    assert dict(traceability) == {**get_traceability(store, 1), "schema_version": 1}
    assert dict(listed) == {**list_error_classes(store, "core"), "schema_version": 1}


def test_get_detection_strategy_returns_only_detection_fields(store: ErrorStore) -> None:
    payload = get_detection_strategy(store, 1)

    assert set(payload) == {"id", "name", "detection_strategy", "example"}
    assert payload["id"] == 1
    assert payload["detection_strategy"] == store.get(1)["detection_strategy"]


def test_list_error_classes_per_domain_stays_inside_that_domain_range(store: ErrorStore) -> None:
    listed_ids: list[int] = []
    for domain in KNOWN_ERROR_DOMAINS:
        start, end = ERROR_DOMAIN_RANGES[domain]
        payload = list_error_classes(store, domain)
        ids = [int(str(entry["id"])) for entry in payload["error_classes"]]

        assert ids == sorted(ids)
        assert ids == list(range(start, end + 1))
        assert {entry["domain"] for entry in payload["error_classes"]} == {domain}
        assert payload["count"] == end - start + 1
        assert payload["total_classes"] == TOTAL_ERROR_CLASSES
        assert payload["available_domains"] == sorted(KNOWN_ERROR_DOMAINS)
        listed_ids.extend(ids)

    assert listed_ids == list(range(1, TOTAL_ERROR_CLASSES + 1))
    assert list_error_classes(store, None)["count"] == TOTAL_ERROR_CLASSES


def test_list_error_classes_rejects_blank_and_unknown_domains(store: ErrorStore) -> None:
    with pytest.raises(ValueError, match="domain must be a non-empty string"):
        list_error_classes(store, "   ")
    with pytest.raises(ValueError, match="unknown domain 'quantum'; expected one of: core, field_theory"):
        list_error_classes(store, "quantum")

    assert normalize_error_domain(None) is None
    assert normalize_error_domain("  core  ") == "core"


def test_traceability_matrix_covers_every_column_and_error_class(store: ErrorStore) -> None:
    covered_columns: set[str] = set()
    for error_id in range(1, TOTAL_ERROR_CLASSES + 1):
        checks = store.get_traceability(error_id)
        assert checks is not None, error_id
        assert set(checks) <= set(TRACEABILITY_COLUMNS)
        covered_columns |= set(checks)

    assert len(TRACEABILITY_COLUMNS) == 8
    assert covered_columns == set(TRACEABILITY_COLUMNS)
    assert (REFERENCES_DIR / TRACEABILITY_FILE).is_file()


def test_get_traceability_reports_coverage_for_a_known_error_class(store: ErrorStore) -> None:
    payload = get_traceability(store, 1)

    assert payload["id"] == 1
    assert payload["verification_checks"] == {
        "Symmetry": "angular momentum algebra",
        "Cross-Check Literature": "tabulated values",
    }
    assert payload["covered_by"] == ["Symmetry", "Cross-Check Literature"]
    assert payload["coverage_count"] == 2
    assert "note" not in payload


def test_get_traceability_notes_missing_rows_without_dropping_the_checks_key(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "catalog.md", "| 1 | Foo | Desc | Detect | Example |\n")
    (tmp_path / "verification" / "errors" / "traceability.md").write_text(
        "| Error Class | Dimensional Analysis |\n|---|---|\n| 2. Bar | direct |\n",
        encoding="utf-8",
    )
    local_store = ErrorStore(
        tmp_path,
        catalog_files=["verification/errors/catalog.md"],
        catalog_file_ranges=(),
        traceability_file="verification/errors/traceability.md",
    )

    payload = get_traceability(local_store, 1)

    assert payload["verification_checks"] == {}
    assert payload["covered_by"] == []
    assert payload["coverage_count"] == 0
    assert payload["note"] == "No traceability data available for this error class"


def test_check_error_classes_ranks_matches_and_caps_the_result_list(store: ErrorStore) -> None:
    payload = check_error_classes(store, "  Clebsch-Gordan angular momentum coupling  ")

    scores = [int(str(entry["relevance_score"])) for entry in payload["error_classes"]]

    assert payload["query"] == "Clebsch-Gordan angular momentum coupling"
    assert payload["match_count"] >= len(payload["error_classes"])
    assert len(payload["error_classes"]) <= MAX_ERROR_CLASS_MATCHES
    assert scores == sorted(scores, reverse=True)
    assert [entry["id"] for entry in payload["error_classes"][:2]] == [28, 1]
    assert payload["error_classes"][0]["name"] == "Angular momentum addition errors for j > 1"
    assert all(len(str(entry["description_preview"])) <= 200 for entry in payload["error_classes"])


def test_check_error_classes_rejects_blank_descriptions(store: ErrorStore) -> None:
    with pytest.raises(ValueError, match="computation_desc must be a non-empty string"):
        check_error_classes(store, "   ")
    with pytest.raises(ValueError, match="computation_desc must be a non-empty string"):
        check_error_classes(store, None)

    assert normalize_computation_description(" one-loop  ") == "one-loop"


def test_store_rejects_catalog_rows_outside_the_declared_id_ranges(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "catalog.md", "| 2 | Foo | Desc | Detect | Example |\n")

    with pytest.raises(ValueError, match=r"catalog\.md declares ID range\(s\) 1; found out-of-range error class id 2"):
        ErrorStore(
            tmp_path,
            catalog_files=["verification/errors/catalog.md"],
            catalog_file_ranges=(("verification/errors/catalog.md", ((1, 1),)),),
            traceability_file="verification/errors/traceability.md",
        )


def test_store_accepts_split_declared_id_ranges(tmp_path: Path) -> None:
    _write_catalog(
        tmp_path,
        "catalog.md",
        "| 52 | Foo | Desc | Detect | Example |\n| 104 | Bar | Desc | Detect | Example |\n",
    )
    (tmp_path / "verification" / "errors" / "traceability.md").write_text(
        "| Error Class | Dimensional Analysis |\n|---|---|\n| 52. Foo | direct |\n",
        encoding="utf-8",
    )

    local_store = ErrorStore(
        tmp_path,
        catalog_files=["verification/errors/catalog.md"],
        catalog_file_ranges=(("verification/errors/catalog.md", ((52, 81), (102, 104))),),
        traceability_file="verification/errors/traceability.md",
    )

    assert [entry["id"] for entry in local_store.list_all()] == [52, 104]
    assert local_store.get(104)["domain"] == "newly_identified"


def test_store_fails_closed_on_missing_catalog_and_empty_traceability(tmp_path: Path) -> None:
    with pytest.raises(OSError, match="Error catalog not found"):
        ErrorStore(tmp_path, catalog_files=["verification/errors/absent.md"])

    _write_catalog(tmp_path, "catalog.md", "| 1 | Foo | Desc | Detect | Example |\n")
    (tmp_path / "verification" / "errors" / "traceability.md").write_text(
        "| Error Class | Dimensional Analysis |\n|---|---|\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="did not contain any error-class rows"):
        ErrorStore(
            tmp_path,
            catalog_files=["verification/errors/catalog.md"],
            catalog_file_ranges=(),
            traceability_file="verification/errors/traceability.md",
        )


def test_store_rejects_duplicate_error_ids_across_catalog_files(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "catalog-a.md", "| 1 | Foo | Desc | Detect A | Example |\n")
    _write_catalog(tmp_path, "catalog-b.md", "| 1 | Bar | Desc | Detect B | Example |\n")

    with pytest.raises(ValueError, match="Duplicate error class id 1 in catalog-b.md; already defined in catalog-a.md"):
        ErrorStore(
            tmp_path,
            catalog_files=["verification/errors/catalog-a.md", "verification/errors/catalog-b.md"],
            catalog_file_ranges=(),
            traceability_file="verification/errors/traceability.md",
        )


def test_store_rejects_malformed_frontmatter_in_a_catalog(tmp_path: Path) -> None:
    path = tmp_path / "verification" / "errors" / "catalog.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\ntitle: unterminated\n" + _CATALOG_HEADER, encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed frontmatter in .*catalog.md: Unclosed frontmatter block"):
        ErrorStore(tmp_path, catalog_files=["verification/errors/catalog.md"], catalog_file_ranges=())


def test_store_parses_escaped_pipes_and_strips_bold_names(tmp_path: Path) -> None:
    _write_catalog(
        tmp_path,
        "catalog.md",
        "| 1 | **Wrong \\| ambiguous sign** | Desc | Detect | a \\| b |\n",
    )
    (tmp_path / "verification" / "errors" / "traceability.md").write_text(
        "| Error Class | Dimensional Analysis |\n|---|---|\n| 1. Wrong | direct |\n",
        encoding="utf-8",
    )

    local_store = ErrorStore(
        tmp_path,
        catalog_files=["verification/errors/catalog.md"],
        catalog_file_ranges=(),
        traceability_file="verification/errors/traceability.md",
    )
    record = local_store.get(1)

    assert record["name"] == "Wrong | ambiguous sign"
    assert record["example"] == "a | b"


def test_get_error_store_returns_the_same_cached_instance() -> None:
    assert get_error_store() is get_error_store()
