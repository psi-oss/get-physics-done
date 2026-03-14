"""Tests for gpd.core.json_utils and the ``gpd json`` CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.errors import ValidationError
from gpd.core.json_utils import (
    json_get,
    json_keys,
    json_list,
    json_merge_files,
    json_pluck,
    json_set,
    json_sum_lengths,
)

runner = CliRunner()


# ─── json_get ────────────────────────────────────────────────────────────────


def test_json_get_simple_key():
    data = json.dumps({"section": "Phase 1 overview", "autonomy": "balanced"})
    assert json_get(data, ".section") == "Phase 1 overview"
    assert json_get(data, ".autonomy") == "balanced"


def test_json_get_missing_key_with_default():
    data = json.dumps({"a": 1})
    assert json_get(data, ".missing", default="fallback") == "fallback"


def test_json_get_missing_key_no_default():
    data = json.dumps({"a": 1})
    assert json_get(data, ".missing") == ""


def test_json_get_nested_key():
    data = json.dumps({"outer": {"inner": "value"}})
    assert json_get(data, ".outer.inner") == "value"


def test_json_get_array_index():
    data = json.dumps({"directories": ["phase-01", "phase-02", "phase-03"]})
    assert json_get(data, ".directories[-1]") == "phase-03"
    assert json_get(data, ".directories[0]") == "phase-01"


def test_json_get_returns_json_for_non_strings():
    data = json.dumps({"decisions": [{"id": 1}, {"id": 2}]})
    result = json_get(data, ".decisions")
    assert json.loads(result) == [{"id": 1}, {"id": 2}]


def test_json_get_default_on_bad_json():
    assert json_get("not json", ".key", default="safe") == "safe"


def test_json_get_raises_on_bad_json_no_default():
    with pytest.raises(ValidationError, match="Invalid JSON"):
        json_get("not json", ".key")


def test_json_get_default_on_empty_string():
    assert json_get("", ".key", default="[]") == "[]"


# ─── json_keys ───────────────────────────────────────────────────────────────


def test_json_keys_basic():
    data = json.dumps({"waves": {"1": ["a"], "2": ["b", "c"]}})
    result = json_keys(data, ".waves")
    assert result == "1\n2"


def test_json_keys_top_level():
    data = json.dumps({"alpha": 1, "beta": 2})
    result = json_keys(data, ".")
    assert "alpha" in result
    assert "beta" in result


def test_json_keys_non_object():
    data = json.dumps({"arr": [1, 2, 3]})
    assert json_keys(data, ".arr") == ""


def test_json_keys_bad_json():
    assert json_keys("bad", ".x") == ""


# ─── json_list ───────────────────────────────────────────────────────────────


def test_json_list_array():
    data = json.dumps({"waves": {"1": ["plan-a", "plan-b"]}})
    result = json_list(data, '.waves.1')
    assert result == "plan-a\nplan-b"


def test_json_list_dict():
    data = json.dumps({"decisions": {"d1": "yes", "d2": "no"}})
    result = json_list(data, ".decisions")
    assert "d1" in result
    assert "d2" in result


def test_json_list_missing():
    data = json.dumps({"a": 1})
    assert json_list(data, ".missing") == ""


# ─── json_pluck ──────────────────────────────────────────────────────────────


def test_json_pluck_basic():
    data = json.dumps({"plans": [{"id": "plan-a"}, {"id": "plan-b"}, {"id": "plan-c"}]})
    result = json_pluck(data, ".plans", "id")
    assert result == "plan-a\nplan-b\nplan-c"


def test_json_pluck_missing_field():
    data = json.dumps({"plans": [{"id": "plan-a"}, {"name": "plan-b"}]})
    result = json_pluck(data, ".plans", "id")
    assert result == "plan-a"


def test_json_pluck_not_array():
    data = json.dumps({"plans": "not-an-array"})
    assert json_pluck(data, ".plans", "id") == ""


# ─── json_set ────────────────────────────────────────────────────────────────


def test_json_set_creates_file(tmp_path):
    fp = str(tmp_path / "commits.json")
    result = json_set(fp, "task_1", "abc123")
    assert result["updated"] is True
    data = json.loads(Path(fp).read_text())
    assert data["task_1"] == "abc123"


def test_json_set_updates_existing(tmp_path):
    fp = tmp_path / "data.json"
    fp.write_text(json.dumps({"existing": "val"}))
    json_set(str(fp), "new_key", "new_val")
    data = json.loads(fp.read_text())
    assert data["existing"] == "val"
    assert data["new_key"] == "new_val"


def test_json_set_nested_path(tmp_path):
    fp = str(tmp_path / "nested.json")
    json_set(fp, "a.b.c", "deep")
    data = json.loads(Path(fp).read_text())
    assert data["a"]["b"]["c"] == "deep"


def test_json_set_json_value(tmp_path):
    fp = str(tmp_path / "typed.json")
    json_set(fp, "count", "42")
    data = json.loads(Path(fp).read_text())
    assert data["count"] == 42  # parsed as int




def test_json_set_out_of_range_index_no_write(tmp_path):
    """json_set must not write when a list index is out of range (updated=False)."""
    fp = tmp_path / 'data.json'
    fp.write_text(json.dumps({'items': ['a', 'b']}))
    original = fp.read_text()
    result = json_set(str(fp), 'items[99]', '"new"')
    assert result['updated'] is False
    # File content must be unchanged
    assert fp.read_text() == original


def test_json_set_out_of_range_deep_nested_no_write(tmp_path):
    """Deeply nested list with OOB index must not rewrite the file."""
    fp = tmp_path / 'data.json'
    fp.write_text(json.dumps({"root": {"nested": {"arr": ["only_one"]}}}))
    original = fp.read_text()
    result = json_set(str(fp), 'root.nested.arr[99]', '"val"')
    assert result['updated'] is False
    assert fp.read_text() == original


def test_json_set_out_of_range_negative_index_no_write(tmp_path):
    """Negative out-of-range list index must not rewrite the file."""
    fp = tmp_path / 'data.json'
    fp.write_text(json.dumps({'arr': ['only']}))
    original = fp.read_text()
    result = json_set(str(fp), 'arr[-99]', '"val"')
    assert result['updated'] is False
    assert fp.read_text() == original


# ─── json_merge_files ────────────────────────────────────────────────────────


def test_json_merge_files_basic(tmp_path):
    f1 = tmp_path / "a.json"
    f2 = tmp_path / "b.json"
    f1.write_text(json.dumps({"task_1": "abc"}))
    f2.write_text(json.dumps({"task_2": "def"}))
    out = str(tmp_path / "merged.json")
    result = json_merge_files(out, [str(f1), str(f2)])
    assert result["merged"] == 2
    merged = json.loads(Path(out).read_text())
    assert merged == {"task_1": "abc", "task_2": "def"}


def test_json_merge_files_overwrites_on_conflict(tmp_path):
    f1 = tmp_path / "a.json"
    f2 = tmp_path / "b.json"
    f1.write_text(json.dumps({"key": "old"}))
    f2.write_text(json.dumps({"key": "new"}))
    out = str(tmp_path / "merged.json")
    json_merge_files(out, [str(f1), str(f2)])
    merged = json.loads(Path(out).read_text())
    assert merged["key"] == "new"


def test_json_merge_files_skips_missing(tmp_path):
    f1 = tmp_path / "a.json"
    f1.write_text(json.dumps({"only": "this"}))
    out = str(tmp_path / "merged.json")
    json_merge_files(out, [str(f1), str(tmp_path / "nonexistent.json")])
    merged = json.loads(Path(out).read_text())
    assert merged == {"only": "this"}


# ─── json_sum_lengths ────────────────────────────────────────────────────────


def test_json_sum_lengths_basic():
    data = json.dumps({
        "truths": ["t1", "t2"],
        "artifacts": ["a1"],
        "key_links": ["k1", "k2", "k3"],
    })
    result = json_sum_lengths(data, [".truths", ".artifacts", ".key_links"])
    assert result == "6"


def test_json_sum_lengths_missing_key():
    data = json.dumps({"truths": ["t1"]})
    result = json_sum_lengths(data, [".truths", ".missing"])
    assert result == "1"


def test_raw_json_keys_outputs_empty_string_for_empty_object() -> None:
    result = runner.invoke(app, ["--raw", "json", "keys", ".empty"], input='{"empty": {}}')

    assert result.exit_code == 0
    assert json.loads(result.output) == ""


def test_raw_json_list_outputs_empty_string_for_missing_collection() -> None:
    result = runner.invoke(app, ["--raw", "json", "list", ".missing"], input='{"items": []}')

    assert result.exit_code == 0
    assert json.loads(result.output) == ""


def test_raw_json_pluck_outputs_empty_string_for_missing_field() -> None:
    payload = json.dumps({"plans": [{"name": "alpha"}]})
    result = runner.invoke(app, ["--raw", "json", "pluck", ".plans", "id"], input=payload)

    assert result.exit_code == 0
    assert json.loads(result.output) == ""


def test_json_sum_lengths_empty():
    result = json_sum_lengths("{}", [".a", ".b"])
    assert result == "0"


# ─── CLI integration tests ──────────────────────────────────────────────────


def test_cli_json_help():
    result = runner.invoke(app, ["json", "--help"])
    assert result.exit_code == 0
    assert "get" in result.output
    assert "keys" in result.output
    assert "set" in result.output


def test_cli_json_get():
    data = json.dumps({"section": "hello"})
    result = runner.invoke(app, ["json", "get", ".section"], input=data)
    assert result.exit_code == 0
    assert "hello" in result.output


def test_cli_json_get_with_default():
    data = json.dumps({"a": 1})
    result = runner.invoke(app, ["json", "get", ".missing", "--default", "fallback"], input=data)
    assert result.exit_code == 0
    assert "fallback" in result.output


def test_cli_json_keys():
    data = json.dumps({"waves": {"1": ["a"], "2": ["b"]}})
    result = runner.invoke(app, ["json", "keys", ".waves"], input=data)
    assert result.exit_code == 0
    assert "1" in result.output
    assert "2" in result.output


def test_cli_json_list():
    data = json.dumps({"items": ["alpha", "beta"]})
    result = runner.invoke(app, ["json", "list", ".items"], input=data)
    assert result.exit_code == 0
    assert "alpha" in result.output
    assert "beta" in result.output


def test_cli_json_pluck():
    data = json.dumps({"plans": [{"id": "p1"}, {"id": "p2"}]})
    result = runner.invoke(app, ["json", "pluck", ".plans", "id"], input=data)
    assert result.exit_code == 0
    assert "p1" in result.output
    assert "p2" in result.output


def test_cli_json_set(tmp_path):
    fp = str(tmp_path / "test.json")
    result = runner.invoke(app, ["json", "set", "--file", fp, "--path", "key", "--value", "val"])
    assert result.exit_code == 0
    data = json.loads(Path(fp).read_text())
    assert data["key"] == "val"


def test_cli_json_merge_files(tmp_path):
    f1 = tmp_path / "a.json"
    f2 = tmp_path / "b.json"
    out = tmp_path / "out.json"
    f1.write_text(json.dumps({"x": 1}))
    f2.write_text(json.dumps({"y": 2}))
    result = runner.invoke(app, ["json", "merge-files", "--out", str(out), str(f1), str(f2)])
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data == {"x": 1, "y": 2}


def test_cli_json_sum_lengths():
    data = json.dumps({"a": [1, 2], "b": [3]})
    result = runner.invoke(app, ["json", "sum-lengths", ".a", ".b"], input=data)
    assert result.exit_code == 0
    assert "3" in result.output
