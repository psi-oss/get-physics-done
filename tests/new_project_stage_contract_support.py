"""Test-only loader for the staged `new-project` manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

__all__ = [
    "NEW_PROJECT_STAGE_MANIFEST_PATH",
    "NewProjectStage",
    "NewProjectStageContract",
    "load_new_project_stage_contract",
    "load_new_project_stage_contract_from_path",
    "validate_new_project_stage_contract_payload",
]


REPO_ROOT = Path(__file__).resolve().parents[1]
NEW_PROJECT_STAGE_MANIFEST_PATH = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "new-project-stage-manifest.json"

_ALLOWED_TOP_LEVEL_KEYS = {"schema_version", "workflow_id", "stages"}
_ALLOWED_STAGE_KEYS = {
    "id",
    "order",
    "purpose",
    "mode_paths",
    "required_init_fields",
    "loaded_authorities",
    "must_not_eager_load",
    "allowed_tools",
    "writes_allowed",
    "produced_state",
    "next_stages",
    "checkpoints",
}


@dataclass(frozen=True, slots=True)
class NewProjectStage:
    id: str
    order: int
    purpose: str
    mode_paths: tuple[str, ...]
    required_init_fields: tuple[str, ...]
    loaded_authorities: tuple[str, ...]
    must_not_eager_load: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    writes_allowed: tuple[str, ...]
    produced_state: tuple[str, ...]
    next_stages: tuple[str, ...]
    checkpoints: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NewProjectStageContract:
    schema_version: int
    workflow_id: str
    stages: tuple[NewProjectStage, ...]

    def stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.id for stage in self.stages)


def _require_string(raw: object, *, label: str) -> str:
    if not isinstance(raw, str):
        raise ValueError(f"{label} must be a non-empty string")
    stripped = raw.strip()
    if not stripped:
        raise ValueError(f"{label} must be a non-empty string")
    return stripped


def _require_int(raw: object, *, label: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"{label} must be an integer")
    return raw


def _require_string_tuple(raw: object, *, label: str, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ValueError(f"{label} must be a list of non-empty strings")
    if not raw and not allow_empty:
        raise ValueError(f"{label} must be a non-empty list of non-empty strings")

    items: list[str] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, str):
            raise ValueError(f"{label} entries must be non-empty strings")
        normalized = entry.strip()
        if not normalized:
            raise ValueError(f"{label} entries must be non-empty strings")
        if normalized in seen:
            raise ValueError(f"{label} must not contain duplicate entries")
        seen.add(normalized)
        items.append(normalized)
    return tuple(items)


def _validate_stage(raw: object, *, index: int) -> NewProjectStage:
    if not isinstance(raw, dict):
        raise ValueError(f"stages[{index}] must be a JSON object")

    unknown_keys = sorted(str(key) for key in raw if str(key) not in _ALLOWED_STAGE_KEYS)
    if unknown_keys:
        raise ValueError(f"stages[{index}] contains unexpected key(s): {', '.join(unknown_keys)}")

    required_keys = tuple(sorted(_ALLOWED_STAGE_KEYS - {"checkpoints"}))
    missing_keys = sorted(key for key in required_keys if key not in raw)
    if missing_keys:
        raise ValueError(f"stages[{index}] is missing required key(s): {', '.join(missing_keys)}")

    return NewProjectStage(
        id=_require_string(raw["id"], label=f"stages[{index}].id"),
        order=_require_int(raw["order"], label=f"stages[{index}].order"),
        purpose=_require_string(raw["purpose"], label=f"stages[{index}].purpose"),
        mode_paths=_require_string_tuple(raw["mode_paths"], label=f"stages[{index}].mode_paths"),
        required_init_fields=_require_string_tuple(
            raw["required_init_fields"],
            label=f"stages[{index}].required_init_fields",
            allow_empty=True,
        ),
        loaded_authorities=_require_string_tuple(
            raw["loaded_authorities"],
            label=f"stages[{index}].loaded_authorities",
            allow_empty=True,
        ),
        must_not_eager_load=_require_string_tuple(
            raw["must_not_eager_load"],
            label=f"stages[{index}].must_not_eager_load",
            allow_empty=True,
        ),
        allowed_tools=_require_string_tuple(raw["allowed_tools"], label=f"stages[{index}].allowed_tools", allow_empty=True),
        writes_allowed=_require_string_tuple(
            raw["writes_allowed"],
            label=f"stages[{index}].writes_allowed",
            allow_empty=True,
        ),
        produced_state=_require_string_tuple(raw["produced_state"], label=f"stages[{index}].produced_state", allow_empty=True),
        next_stages=_require_string_tuple(raw["next_stages"], label=f"stages[{index}].next_stages", allow_empty=True),
        checkpoints=_require_string_tuple(raw.get("checkpoints", []), label=f"stages[{index}].checkpoints", allow_empty=True),
    )


def validate_new_project_stage_contract_payload(raw: object) -> NewProjectStageContract:
    if not isinstance(raw, dict):
        raise ValueError("new-project stage manifest must be a JSON object")

    unknown_keys = sorted(str(key) for key in raw if str(key) not in _ALLOWED_TOP_LEVEL_KEYS)
    if unknown_keys:
        raise ValueError(f"new-project stage manifest contains unexpected key(s): {', '.join(unknown_keys)}")

    missing_keys = sorted(key for key in _ALLOWED_TOP_LEVEL_KEYS if key not in raw)
    if missing_keys:
        raise ValueError(f"new-project stage manifest is missing required key(s): {', '.join(missing_keys)}")

    schema_version = _require_int(raw["schema_version"], label="schema_version")
    if schema_version != 1:
        raise ValueError("new-project stage manifest schema_version must be 1")

    workflow_id = _require_string(raw["workflow_id"], label="workflow_id")
    if workflow_id != "new-project":
        raise ValueError("new-project stage manifest workflow_id must be 'new-project'")

    stages_raw = raw["stages"]
    if not isinstance(stages_raw, list) or not stages_raw:
        raise ValueError("stages must be a non-empty list")

    stages = tuple(_validate_stage(stage, index=index) for index, stage in enumerate(stages_raw))

    stage_ids = [stage.id for stage in stages]
    if len(set(stage_ids)) != len(stage_ids):
        raise ValueError("stage ids must be unique")

    stage_orders = [stage.order for stage in stages]
    if len(set(stage_orders)) != len(stage_orders):
        raise ValueError("stage order values must be unique")
    if stage_orders != list(range(1, len(stages) + 1)):
        raise ValueError("stage order values must start at 1 and increase by 1")

    stage_id_set = set(stage_ids)
    for stage in stages:
        missing_next = sorted(next_stage for next_stage in stage.next_stages if next_stage not in stage_id_set)
        if missing_next:
            raise ValueError(f"stage {stage.id!r} references unknown next stage(s): {', '.join(missing_next)}")
        for authority in (*stage.loaded_authorities, *stage.must_not_eager_load):
            if authority and not authority.startswith(("workflows/", "references/", "templates/")):
                raise ValueError(f"stage {stage.id!r} has invalid authority path: {authority!r}")

    expected_stage_ids = ["scope_intake", "scope_approval", "post_scope"]
    if stage_ids != expected_stage_ids:
        raise ValueError("new-project stage manifest must define scope_intake, scope_approval, and post_scope in order")

    return NewProjectStageContract(schema_version=schema_version, workflow_id=workflow_id, stages=stages)


def load_new_project_stage_contract_from_path(manifest_path: Path) -> NewProjectStageContract:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to read new-project stage manifest {manifest_path}: {exc}") from exc
    return validate_new_project_stage_contract_payload(payload)


@lru_cache(maxsize=1)
def load_new_project_stage_contract() -> NewProjectStageContract:
    return load_new_project_stage_contract_from_path(NEW_PROJECT_STAGE_MANIFEST_PATH)
