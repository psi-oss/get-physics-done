from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaError,
    ResearchPersonaFact,
    ResearchPersonaPatch,
    ResearchPersonaPatchOperation,
    ResearchPersonaTombstone,
    load_research_persona,
    research_persona_path,
    research_persona_root,
    save_research_persona,
)
from gpd.core.research_persona_cli import (
    parse_research_persona_patch_data_strict,
    research_persona_apply_patch_payload,
    research_persona_diff_payload,
    research_persona_export_capsule_payload,
    research_persona_forget_fact_payload,
    research_persona_show_payload,
    research_persona_validate_payload,
)

SAFE_VALUE = "SAFE_CLI_SUPPORT_CANARY theorem-first derivations are preferred"
PRIVATE_VALUE = "PRIVATE_CLI_SUPPORT_CANARY local path /tmp/secret-notebook"
PRIVATE_UPDATED_VALUE = "PRIVATE_CLI_SUPPORT_CANARY updated private local detail"
PRIVATE_LIST_ITEM = "PRIVATE_CLI_SUPPORT_CANARY unpublished collaborator detail"


def _fact(
    fact_id: str,
    *,
    value: str = SAFE_VALUE,
    privacy: str = "safe_to_share",
    category: str = "workstyle",
) -> ResearchPersonaFact:
    return ResearchPersonaFact(
        id=fact_id,
        category=category,
        value=value,
        confidence="confirmed",
        privacy=privacy,
        sources=["user_statement"],
        evidence_refs=[],
    )


def _patch_payload(patch: ResearchPersonaPatch) -> dict[str, object]:
    return patch.model_dump(mode="json")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _tree_snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _render(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def test_show_missing_profile_is_read_only(tmp_path: Path) -> None:
    payload = research_persona_show_payload(data_root=tmp_path, projection="prompt")

    assert payload["path"] == str(tmp_path / "research-persona" / "profile.json")
    assert payload["exists"] is False
    assert payload["counts"]["facts"] == 0  # type: ignore[index]
    assert payload["projection_counts"]["facts"] == 0  # type: ignore[index]
    assert not research_persona_root(tmp_path).exists()


def test_validate_payload_reports_counts_and_schema_errors() -> None:
    valid_data = ResearchPersona(
        standing_preferences=["Prefer explicit assumptions"],
        tools=["pytest"],
        facts=[_fact("fact.safe")],
    ).model_dump(mode="json")

    valid = research_persona_validate_payload(valid_data, path="profile.json", exists=True)
    invalid = research_persona_validate_payload({"schema_version": 1, "standing_preferences": "not-a-list"})

    assert valid["valid"] is True
    assert valid["path"] == "profile.json"
    assert valid["exists"] is True
    assert valid["counts"]["facts"] == 1  # type: ignore[index]
    assert invalid["valid"] is False
    assert invalid["errors"]
    assert "counts" not in invalid


def test_parse_patch_strict_rejects_malformed_patch_data() -> None:
    with pytest.raises(ResearchPersonaError, match="requires fact"):
        parse_research_persona_patch_data_strict(
            {"schema_version": 1, "operations": [{"op": "add_fact"}]},
        )

    with pytest.raises(ResearchPersonaError, match="JSON object"):
        parse_research_persona_patch_data_strict(["not", "an", "object"])


def test_diff_payload_summarizes_without_private_values(tmp_path: Path) -> None:
    save_research_persona(
        ResearchPersona(
            facts=[_fact("fact.private", value=PRIVATE_VALUE, privacy="private_local")],
            standing_preferences=[PRIVATE_LIST_ITEM],
        ),
        tmp_path,
    )
    before_tree = _tree_snapshot(research_persona_root(tmp_path))
    patch = ResearchPersonaPatch(
        operations=[
            ResearchPersonaPatchOperation(
                op="update",
                path="/facts/fact.private",
                value={"value": PRIVATE_UPDATED_VALUE, "confidence": "stale"},
            ),
            ResearchPersonaPatchOperation(
                op="set_list",
                list_name="standing_preferences",
                values=["another private standing preference"],
            ),
        ]
    )

    payload = research_persona_diff_payload(_patch_payload(patch), data_root=tmp_path)
    rendered = _render(payload)

    assert payload["would_update"] is True
    assert payload["diff"]["facts"]["changed"][0]["changed_fields"] == ["confidence", "value"]  # type: ignore[index]
    assert payload["diff"]["lists"]["standing_preferences"]["changed"] is True  # type: ignore[index]
    assert PRIVATE_VALUE not in rendered
    assert PRIVATE_UPDATED_VALUE not in rendered
    assert PRIVATE_LIST_ITEM not in rendered
    assert _tree_snapshot(research_persona_root(tmp_path)) == before_tree


def test_apply_patch_dry_run_writes_nothing(tmp_path: Path) -> None:
    patch = ResearchPersonaPatch(
        operations=[ResearchPersonaPatchOperation(op="add_fact", fact=_fact("fact.safe"))],
    )

    payload = research_persona_apply_patch_payload(_patch_payload(patch), data_root=tmp_path, dry_run=True)

    assert payload["dry_run"] is True
    assert payload["updated"] is True
    assert not research_persona_path(tmp_path).exists()
    assert not research_persona_root(tmp_path).exists()


def test_apply_patch_strict_loads_saves_history_and_tombstones(tmp_path: Path) -> None:
    save_research_persona(
        ResearchPersona(facts=[_fact("fact.deleted", value=PRIVATE_VALUE, privacy="private_local")]),
        tmp_path,
    )
    patch = ResearchPersonaPatch(
        operations=[
            ResearchPersonaPatchOperation(
                op="add_fact",
                fact=_fact("fact.safe", value=SAFE_VALUE, privacy="safe_to_share"),
            )
        ],
        tombstones=[
            ResearchPersonaTombstone(
                fact_id="fact.deleted",
                reason="user_requested_removal",
                created_at="2026-06-04T00:00:00Z",
            )
        ],
        reason="Apply CLI support test patch.",
    )

    payload = research_persona_apply_patch_payload(
        _patch_payload(patch),
        data_root=tmp_path,
        actor="test",
        now="2026-06-04T12:00:00Z",
    )
    loaded = load_research_persona(tmp_path, strict=True)

    assert payload["dry_run"] is False
    assert payload["exists"] is True
    assert [fact.id for fact in loaded.facts] == ["fact.safe"]
    assert Path(str(payload["history_path"])).is_file()
    assert Path(str(payload["tombstone_path"])).is_file()
    history_rows = _read_jsonl(Path(str(payload["history_path"])))
    tombstone_rows = _read_jsonl(Path(str(payload["tombstone_path"])))
    assert history_rows[-1]["event_type"] == "patch_applied"
    assert tombstone_rows[-1]["fact_id"] == "fact.deleted"
    assert PRIVATE_VALUE not in _render(payload)


def test_apply_patch_refuses_malformed_existing_profile(tmp_path: Path) -> None:
    path = research_persona_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")
    patch = ResearchPersonaPatch(operations=[ResearchPersonaPatchOperation(op="add_fact", fact=_fact("fact.safe"))])

    with pytest.raises(ResearchPersonaError, match="not valid JSON"):
        research_persona_apply_patch_payload(_patch_payload(patch), data_root=tmp_path)

    assert path.read_text(encoding="utf-8") == "{not valid json"
    assert not (research_persona_root(tmp_path) / "history").exists()


def test_forget_fact_removes_fact_and_records_tombstone(tmp_path: Path) -> None:
    save_research_persona(ResearchPersona(facts=[_fact("fact.private", value=PRIVATE_VALUE)]), tmp_path)

    payload = research_persona_forget_fact_payload(
        "fact.private",
        data_root=tmp_path,
        reason="user_requested_removal",
        now="2026-06-04T12:00:00Z",
    )
    loaded = load_research_persona(tmp_path, strict=True)
    tombstone_rows = _read_jsonl(Path(str(payload["tombstone_path"])))

    assert payload["forgot_fact_id"] == "fact.private"
    assert [fact.id for fact in loaded.facts] == []
    assert tombstone_rows[-1]["fact_id"] == "fact.private"
    assert tombstone_rows[-1]["reason"] == "user_requested_removal"


def test_export_capsule_payload_is_prompt_safe_for_ambitious_roles(tmp_path: Path) -> None:
    save_research_persona(
        ResearchPersona(
            facts=[
                _fact("fact.safe", value=SAFE_VALUE, privacy="safe_to_share"),
                _fact("fact.private", value=PRIVATE_VALUE, privacy="private_local"),
            ],
            tools=["pytest"],
        ),
        tmp_path,
    )

    payload = research_persona_export_capsule_payload(role="doppelganger", data_root=tmp_path)
    rendered = _render(payload)

    assert payload["role"] == "doppelganger"
    assert SAFE_VALUE in rendered
    assert PRIVATE_VALUE not in rendered


def test_mutation_helpers_write_machine_data_not_project_gpd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_gpd = project_root / "GPD"
    data_root = tmp_path / "machine-data"
    project_gpd.mkdir(parents=True)
    (project_gpd / "state.json").write_text('{"existing": true}\n', encoding="utf-8")
    (project_gpd / "STATE.md").write_text("# Existing\n", encoding="utf-8")
    before = _tree_snapshot(project_gpd)
    monkeypatch.chdir(project_root)
    monkeypatch.setenv("GPD_DATA_DIR", str(data_root))
    patch = ResearchPersonaPatch(operations=[ResearchPersonaPatchOperation(op="add_fact", fact=_fact("fact.safe"))])

    payload = research_persona_apply_patch_payload(_patch_payload(patch), now="2026-06-04T12:00:00Z")

    assert payload["path"] == str(data_root / "research-persona" / "profile.json")
    assert _tree_snapshot(project_gpd) == before
    assert not (project_gpd / "research-persona").exists()
