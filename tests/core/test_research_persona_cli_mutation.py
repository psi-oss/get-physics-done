from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.cli import app
from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaFact,
    load_research_persona,
    research_persona_path,
    research_persona_root,
    save_research_persona,
)
from tests.helpers.cli import StableCliRunner

RUNNER = StableCliRunner()


def _set_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_root = tmp_path / "data"
    monkeypatch.setenv("GPD_DATA_DIR", str(data_root))
    return data_root


def _invoke_raw(
    *args: str,
    input_payload: object | None = None,
    expected_exit: int = 0,
) -> dict[str, object]:
    input_text = None if input_payload is None else json.dumps(input_payload) + "\n"
    result = RUNNER.invoke(
        app,
        ["--raw", "research-persona", *args],
        input=input_text,
        catch_exceptions=False,
    )
    assert result.exit_code == expected_exit, (
        f"expected exit {expected_exit}, got {result.exit_code}\n\n"
        f"stdout:\n{result.output}\n\nexception:\n{result.exception!r}"
    )
    payload = json.loads(result.output)
    assert isinstance(payload, dict)
    return payload


def _fact_payload(fact_id: str, *, value: str | None = None, privacy: str = "safe_to_share") -> dict[str, object]:
    return {
        "id": fact_id,
        "category": "workstyle",
        "value": value or f"{fact_id} prefers explicit verification before applying persona changes.",
        "confidence": "confirmed",
        "privacy": privacy,
        "sources": ["manual_patch"],
        "evidence_refs": [],
    }


def _add_patch(*, fact_id: str = "fact.cli.added", include_tombstone: bool = False) -> dict[str, object]:
    patch: dict[str, object] = {
        "schema_version": 1,
        "source_kind": "manual_patch",
        "reason": "CLI mutation contract test",
        "operations": [
            {
                "op": "add_fact",
                "fact": _fact_payload(fact_id),
            }
        ],
        "tombstones": [],
    }
    if include_tombstone:
        patch["tombstones"] = [
            {
                "schema_version": 1,
                "fact_id": "fact.cli.retired",
                "reason": "superseded_by_cli_patch",
                "source_kind": "manual_patch",
                "created_at": "2026-06-04T00:00:00Z",
            }
        ]
    return patch


def _snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        snapshot[relative] = "<DIR>" if path.is_dir() else path.read_text(encoding="utf-8")
    return snapshot


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    assert path.is_file(), f"expected JSONL ledger at {path}"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    return rows


def _history_path(data_root: Path) -> Path:
    return research_persona_root(data_root) / "history" / "events.jsonl"


def _tombstone_path(data_root: Path) -> Path:
    return research_persona_root(data_root) / "tombstones" / "events.jsonl"


def _fact_ids(data_root: Path) -> list[str]:
    return [fact.id for fact in load_research_persona(data_root, strict=True).facts]


def test_research_persona_diff_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = _set_data_root(tmp_path, monkeypatch)
    patch = _add_patch()

    payload = _invoke_raw("diff", "-", input_payload=patch)

    assert payload["would_update"] is True
    assert "diff" in payload
    assert _snapshot(data_root) == {}
    assert not research_persona_root(data_root).exists()


def test_research_persona_apply_patch_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = _set_data_root(tmp_path, monkeypatch)
    patch = _add_patch()

    payload = _invoke_raw("apply-patch", "-", "--dry-run", input_payload=patch)

    assert payload["dry_run"] is True
    assert "diff" in payload
    assert _snapshot(data_root) == {}
    assert not research_persona_root(data_root).exists()


def test_research_persona_apply_patch_writes_profile_history_and_tombstones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = _set_data_root(tmp_path, monkeypatch)
    patch = _add_patch(fact_id="fact.cli.persisted", include_tombstone=True)

    payload = _invoke_raw("apply-patch", "-", input_payload=patch)

    assert payload["dry_run"] is False
    assert payload["updated"] is True
    assert research_persona_path(data_root).is_file()
    assert _fact_ids(data_root) == ["fact.cli.persisted"]

    history_rows = _read_jsonl(_history_path(data_root))
    tombstone_rows = _read_jsonl(_tombstone_path(data_root))
    assert history_rows[-1]["event_type"] == "patch_applied"
    assert tombstone_rows[-1]["fact_id"] == "fact.cli.retired"
    assert tombstone_rows[-1]["reason"] == "superseded_by_cli_patch"


def test_research_persona_forget_removes_fact_and_writes_tombstone_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = _set_data_root(tmp_path, monkeypatch)
    save_research_persona(
        ResearchPersona(facts=[ResearchPersonaFact.model_validate(_fact_payload("fact.cli.forget"))]),
        data_root,
    )

    payload = _invoke_raw("forget", "fact.cli.forget", "--reason", "user_requested_removal")

    assert payload["forgot_fact_id"] == "fact.cli.forget"
    assert _fact_ids(data_root) == []

    history_rows = _read_jsonl(_history_path(data_root))
    tombstone_rows = _read_jsonl(_tombstone_path(data_root))
    assert history_rows[-1]["event_type"] == "fact_forgotten"
    assert tombstone_rows[-1]["fact_id"] == "fact.cli.forget"
    assert tombstone_rows[-1]["reason"] == "user_requested_removal"


def test_research_persona_mutation_fails_closed_when_existing_profile_is_corrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = _set_data_root(tmp_path, monkeypatch)
    path = research_persona_path(data_root)
    path.parent.mkdir(parents=True)
    path.write_text("{ not valid json", encoding="utf-8")
    before = _snapshot(data_root)

    payload = _invoke_raw("apply-patch", "-", input_payload=_add_patch(), expected_exit=1)

    assert "error" in payload
    assert str(payload["error"]).strip()
    assert _snapshot(data_root) == before
    assert not _history_path(data_root).exists()
    assert not _tombstone_path(data_root).exists()
