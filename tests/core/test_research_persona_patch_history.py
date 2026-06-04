from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaError,
    ResearchPersonaFact,
    ResearchPersonaHistoryEvent,
    ResearchPersonaPatch,
    ResearchPersonaPatchOperation,
    ResearchPersonaTombstone,
    append_research_persona_history,
    append_research_persona_tombstone,
    apply_research_persona_patch,
    research_persona_root,
)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines, f"expected at least one JSONL row in {path}"
    return [json.loads(line) for line in lines]


def _fact(
    fact_id: str,
    *,
    value: str = "Prefers explicit theorem assumptions before proof sketches.",
    privacy: str = "safe_to_share",
) -> ResearchPersonaFact:
    return ResearchPersonaFact(
        id=fact_id,
        category="standing_preference",
        value=value,
        confidence="confirmed",
        privacy=privacy,
        sources=["user_statement"],
        evidence_refs=[],
        last_confirmed_at="2026-01-01T00:00:00Z",
        expires_at=None,
    )


def _fact_ids(persona: ResearchPersona) -> list[str]:
    return [fact.id for fact in persona.facts]


def _fact_by_id(persona: ResearchPersona, fact_id: str) -> ResearchPersonaFact:
    matches = [fact for fact in persona.facts if fact.id == fact_id]
    assert len(matches) == 1
    return matches[0]


def _patch(*operations: ResearchPersonaPatchOperation) -> ResearchPersonaPatch:
    return ResearchPersonaPatch(operations=list(operations))


class TestResearchPersonaPatchOperations:
    def test_patch_applies_add_update_and_remove_fact_operations(self) -> None:
        persona = ResearchPersona()

        updated = apply_research_persona_patch(
            persona,
            _patch(
                ResearchPersonaPatchOperation(
                    op="add",
                    path="/facts",
                    value=_fact("fact.methods").model_dump(),
                ),
                ResearchPersonaPatchOperation(
                    op="add",
                    path="/facts",
                    value=_fact("fact.removed", value="Temporary note to remove.").model_dump(),
                ),
                ResearchPersonaPatchOperation(
                    op="update",
                    path="/facts/fact.methods",
                    value={
                        "value": "Prefers assumptions, definitions, and counterexamples before proof sketches.",
                        "privacy": "project_private",
                    },
                ),
                ResearchPersonaPatchOperation(
                    op="remove",
                    path="/facts/fact.removed",
                ),
            ),
        )

        assert _fact_ids(updated) == ["fact.methods"]
        fact = _fact_by_id(updated, "fact.methods")
        assert fact.value == "Prefers assumptions, definitions, and counterexamples before proof sketches."
        assert fact.privacy == "project_private"
        assert _fact_ids(persona) == []

    def test_patch_suppresses_tombstoned_facts(self) -> None:
        persona = ResearchPersona(facts=[_fact("fact.deleted", value="Old private note.")])
        patch = ResearchPersonaPatch(
            tombstones=[
                ResearchPersonaTombstone(
                    fact_id="fact.deleted",
                    reason="user_requested_removal",
                    created_at="2026-01-02T00:00:00Z",
                ),
            ],
            operations=[
                ResearchPersonaPatchOperation(
                    op="add",
                    path="/facts",
                    value=_fact("fact.deleted", value="Reintroduced note.").model_dump(),
                ),
                ResearchPersonaPatchOperation(
                    op="add",
                    path="/facts",
                    value=_fact("fact.visible", value="Keep this fact.").model_dump(),
                ),
            ],
        )

        updated = apply_research_persona_patch(persona, patch)

        assert _fact_ids(updated) == ["fact.visible"]
        assert _fact_by_id(updated, "fact.visible").value == "Keep this fact."

    def test_patch_rejects_unsupported_operation(self) -> None:
        with pytest.raises((ResearchPersonaError, ValidationError)):
            patch = _patch(
                ResearchPersonaPatchOperation(
                    op="move",
                    path="/facts/fact.methods",
                    value={"path": "/facts/fact.other"},
                )
            )
            apply_research_persona_patch(ResearchPersona(), patch)

    def test_patch_rejects_non_persona_input(self) -> None:
        patch = _patch(
            ResearchPersonaPatchOperation(
                op="add",
                path="/facts",
                value=_fact("fact.methods").model_dump(),
            )
        )

        with pytest.raises(ResearchPersonaError):
            apply_research_persona_patch({"schema_version": 1, "facts": []}, patch)  # type: ignore[arg-type]


class TestResearchPersonaAppendLedgers:
    def test_history_append_writes_jsonl_under_private_root(self, tmp_path: Path) -> None:
        data_root = tmp_path / "private-data"
        first = ResearchPersonaHistoryEvent(
            event_id="history-001",
            event_type="patch_applied",
            created_at="2026-01-03T00:00:00Z",
            summary="Added research-method preference.",
            patch=_patch(
                ResearchPersonaPatchOperation(
                    op="add",
                    path="/facts",
                    value=_fact("fact.methods").model_dump(),
                )
            ),
        )
        second = ResearchPersonaHistoryEvent(
            event_id="history-002",
            event_type="patch_applied",
            created_at="2026-01-03T00:01:00Z",
            summary="Removed obsolete preference.",
            patch=_patch(ResearchPersonaPatchOperation(op="remove", path="/facts/fact.methods")),
        )

        path = append_research_persona_history(first, data_root)
        second_path = append_research_persona_history(second, data_root)

        private_root = research_persona_root(data_root)
        assert path == private_root / "history" / "events.jsonl"
        assert second_path == path
        assert tmp_path / "GPD" not in path.parents
        rows = _read_jsonl(path)
        assert [row["event_id"] for row in rows] == ["history-001", "history-002"]
        assert [row["event_type"] for row in rows] == ["patch_applied", "patch_applied"]

    def test_tombstone_append_writes_jsonl_under_private_root(self, tmp_path: Path) -> None:
        data_root = tmp_path / "private-data"
        first = ResearchPersonaTombstone(
            fact_id="fact.deleted",
            reason="user_requested_removal",
            created_at="2026-01-04T00:00:00Z",
        )
        second = ResearchPersonaTombstone(
            fact_id="fact.stale",
            reason="stale_or_incorrect",
            created_at="2026-01-04T00:01:00Z",
        )

        path = append_research_persona_tombstone(first, data_root)
        second_path = append_research_persona_tombstone(second, data_root)

        private_root = research_persona_root(data_root)
        assert path == private_root / "tombstones" / "events.jsonl"
        assert second_path == path
        assert tmp_path / "GPD" not in path.parents
        rows = _read_jsonl(path)
        assert [row["fact_id"] for row in rows] == ["fact.deleted", "fact.stale"]
        assert [row["reason"] for row in rows] == ["user_requested_removal", "stale_or_incorrect"]
