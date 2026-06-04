"""Manifest-derived staged-init authority contracts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pytest

from gpd.core.workflow_staging import (
    WORKFLOW_STAGE_MANIFEST_DIR,
    WORKFLOW_STAGE_MANIFEST_SUFFIX,
    expanded_required_init_fields_by_stage,
    known_init_fields_for_workflow,
    load_workflow_stage_manifest,
    load_workflow_stage_manifest_from_path,
    validate_workflow_stage_manifest_payload,
)


def _staged_workflow_ids() -> tuple[str, ...]:
    return tuple(
        sorted(
            path.name.removesuffix(WORKFLOW_STAGE_MANIFEST_SUFFIX)
            for path in WORKFLOW_STAGE_MANIFEST_DIR.glob(f"*{WORKFLOW_STAGE_MANIFEST_SUFFIX}")
        )
    )


def _stable_field_union(field_sequences: Iterable[Iterable[str]]) -> tuple[str, ...]:
    fields: list[str] = []
    seen: set[str] = set()
    for sequence in field_sequences:
        for field_name in sequence:
            if field_name in seen:
                continue
            seen.add(field_name)
            fields.append(field_name)
    return tuple(fields)


@pytest.mark.parametrize("workflow_id", _staged_workflow_ids())
def test_known_init_fields_for_all_staged_workflows_are_manifest_effective(workflow_id: str) -> None:
    assert len(_staged_workflow_ids()) == 17

    fields_by_stage = expanded_required_init_fields_by_stage(load_workflow_stage_manifest(workflow_id))
    expected = frozenset(_stable_field_union(fields for _, fields in fields_by_stage))

    assert known_init_fields_for_workflow(workflow_id) == expected


def test_explicit_known_init_fields_still_reject_unknown_manifest_fields() -> None:
    payload = {
        "schema_version": 1,
        "workflow_id": "quick",
        "stages": [
            {
                "id": "task_bootstrap",
                "order": 1,
                "purpose": "Load task bootstrap context.",
                "mode_paths": ["workflows/quick.md"],
                "required_init_fields": ["executor_model", "not_in_explicit_known_fields"],
                "loaded_authorities": ["workflows/quick.md"],
                "conditional_authorities": [],
                "must_not_eager_load": [],
                "allowed_tools": ["file_read"],
                "writes_allowed": [],
                "produced_state": [],
                "next_stages": [],
                "checkpoints": [],
            }
        ],
    }

    with pytest.raises(ValueError, match="unknown field name.*not_in_explicit_known_fields"):
        validate_workflow_stage_manifest_payload(
            payload,
            expected_workflow_id="quick",
            known_init_fields={"executor_model"},
        )


def test_default_manifest_load_keeps_buildability_validation(tmp_path: Path) -> None:
    payload_path = WORKFLOW_STAGE_MANIFEST_DIR / f"execute-phase{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    first_stage = payload["stages"][0]
    first_stage.setdefault("required_init_fields", []).append("not_an_execute_phase_buildable_field")
    manifest_path = tmp_path / "custom-stage-manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown field name.*not_an_execute_phase_buildable_field"):
        load_workflow_stage_manifest_from_path(manifest_path)
