"""Inventory guardrails for manifest-derived workflow init builders."""

from __future__ import annotations

import inspect

import gpd.core.context as context
from gpd.core.workflow_staging import (
    WORKFLOW_STAGE_MANIFEST_DIR,
    WORKFLOW_STAGE_MANIFEST_SUFFIX,
    known_init_fields_for_workflow,
    load_workflow_stage_manifest,
)

_MANIFEST_DERIVED_KNOWN_INIT_WORKFLOWS = (
    "arxiv-submission",
    "autonomous",
    "build-persona",
    "execute-phase",
    "literature-review",
    "map-research",
    "new-milestone",
    "new-project",
    "peer-review",
    "plan-phase",
    "quick",
    "research-phase",
    "respond-to-referees",
    "resume-work",
    "sync-state",
    "verify-work",
    "write-paper",
)

_FIRST_EXTRACTION_CONTEXT_FACADES = {
    "quick": ("init_quick", ("cwd", "description", "stage"), {"description": None, "stage": None}),
    "sync-state": ("init_sync_state", ("cwd", "stage"), {"stage": None}),
    "map-research": ("init_map_research", ("cwd", "focus", "stage"), {"focus": None, "stage": None}),
    "literature-review": (
        "init_literature_review",
        ("cwd", "topic", "stage"),
        {"topic": None, "stage": None},
    ),
}


def _manifest_workflow_ids() -> tuple[str, ...]:
    return tuple(
        sorted(
            path.name.removesuffix(WORKFLOW_STAGE_MANIFEST_SUFFIX)
            for path in WORKFLOW_STAGE_MANIFEST_DIR.glob(f"*{WORKFLOW_STAGE_MANIFEST_SUFFIX}")
        )
    )


def _manifest_required_field_union(workflow_id: str) -> frozenset[str]:
    manifest = load_workflow_stage_manifest(workflow_id)
    return frozenset(field for stage in manifest.stages for field in stage.required_init_fields)


def test_manifest_derived_known_init_workflow_inventory_is_complete() -> None:
    assert _manifest_workflow_ids() == _MANIFEST_DERIVED_KNOWN_INIT_WORKFLOWS

    for workflow_id in _MANIFEST_DERIVED_KNOWN_INIT_WORKFLOWS:
        assert known_init_fields_for_workflow(workflow_id) == _manifest_required_field_union(workflow_id)


def test_first_extraction_candidates_remain_context_facade_exports() -> None:
    for workflow_id, (
        function_name,
        expected_parameters,
        expected_defaults,
    ) in _FIRST_EXTRACTION_CONTEXT_FACADES.items():
        facade = getattr(context, function_name, None)
        assert callable(facade), f"{workflow_id} must remain importable as context.{function_name}"
        assert vars(context)[function_name] is facade
        assert facade.__module__ == context.__name__

        signature = inspect.signature(facade)
        assert tuple(signature.parameters) == expected_parameters
        assert signature.parameters["cwd"].default is inspect.Signature.empty
        for parameter_name, expected_default in expected_defaults.items():
            assert signature.parameters[parameter_name].default is expected_default

        if workflow_id == "sync-state":
            assert signature.parameters["stage"].kind is inspect.Parameter.KEYWORD_ONLY
        else:
            assert signature.parameters["stage"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
