from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gpd.core.research_persona import (
    RESEARCH_PERSONA_CAPSULE_ROLE_VALUES,
    ResearchPersona,
    ResearchPersonaError,
    ResearchPersonaFact,
    research_persona_path,
    research_persona_root,
    save_research_persona,
)
from gpd.core.research_persona_runtime import (
    build_research_persona_capsule_bundle,
    build_research_persona_runtime_context,
    select_research_persona_capsules_for_workflow,
)

SAFE_VALUE = "SAFE_RUNTIME_CANARY proof-first derivations with executable checks"
PRIVATE_VALUE = "PRIVATE_RUNTIME_CANARY local notebook path"
PROJECT_VALUE = "PROJECT_RUNTIME_CANARY unpublished collaborator note"
NEVER_VALUE = "NEVER_RUNTIME_CANARY identity secret"
ROLE_PLANNER = "planner"
ROLE_EXECUTOR = "executor"
ROLE_VERIFIER = "verifier"
ROLE_WRITER = "paper_writer"
ROLE_LITERATURE = "literature"
ROLE_EXPLAINER = "explainer"
ROLE_TASTE = "taste"
SOURCE_PROVIDED = "provided_persona"
SOURCE_MISSING = "missing_profile"
SOURCE_INVALID = "invalid_profile"
PURPOSE_PROMPT = "prompt"
WORKFLOW_WRITE_PAPER = "write-paper"
KEY_RAW_PROFILE = "raw_profile_exposed"
KEY_PRIVATE_LOCAL = "private_local_exposed"
KEY_PROJECT_PRIVATE = "project_private_exposed"
KEY_NEVER_PROMPT = "never_prompt_exposed"


def _fact(fact_id: str, value: str, privacy: str) -> ResearchPersonaFact:
    return ResearchPersonaFact(
        id=fact_id,
        category="workstyle",
        value=value,
        confidence="confirmed",
        privacy=privacy,
        sources=["user_statement"],
    )


def _persona() -> ResearchPersona:
    return ResearchPersona(
        facts=[
            _fact("runtime.safe", SAFE_VALUE, "safe_to_share"),
            _fact("runtime.private", PRIVATE_VALUE, "private_local"),
            _fact("runtime.project", PROJECT_VALUE, "project_private"),
            _fact("runtime.never", NEVER_VALUE, "never_prompt"),
        ],
        tools=["pytest", "uv"],
        research_areas=["symbolic physics"],
        expertise=["theorem-first software design"],
        workstyle=["derive the toy model before coding"],
        scientific_taste=["novel but testable projects"],
    )


def _render(payload: object) -> str:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")  # type: ignore[attr-defined]
    return json.dumps(payload, sort_keys=True, default=str)


def _assert_private_canaries_absent(payload: object) -> None:
    rendered = _render(payload)
    for needle in (PRIVATE_VALUE, PROJECT_VALUE, NEVER_VALUE):
        assert needle not in rendered


def test_runtime_context_builds_all_supported_prompt_capsules_from_persona() -> None:
    context = build_research_persona_runtime_context(persona=_persona())
    rendered = _render(context)

    assert context.enabled is True
    assert context.profile_source == SOURCE_PROVIDED
    assert set(context.requested_roles) == set(RESEARCH_PERSONA_CAPSULE_ROLE_VALUES)
    assert set(context.capsules) == set(RESEARCH_PERSONA_CAPSULE_ROLE_VALUES)
    assert context.role_counts["available"] == len(RESEARCH_PERSONA_CAPSULE_ROLE_VALUES)
    assert context.role_counts["with_prompt_safe_signals"] == len(RESEARCH_PERSONA_CAPSULE_ROLE_VALUES)
    assert all(capsule.purpose == PURPOSE_PROMPT for capsule in context.capsules.values())
    assert SAFE_VALUE in rendered
    _assert_private_canaries_absent(context)


def test_runtime_context_loads_stored_profile_without_writing_project_state(tmp_path: Path) -> None:
    save_research_persona(_persona(), tmp_path)
    before = research_persona_path(tmp_path).read_text(encoding="utf-8")

    context = build_research_persona_runtime_context(
        data_root=tmp_path,
        roles=[ROLE_PLANNER, ROLE_EXPLAINER, ROLE_TASTE],
    )
    after = research_persona_path(tmp_path).read_text(encoding="utf-8")

    assert context.enabled is True
    assert context.profile_exists is True
    assert set(context.capsules) == {ROLE_PLANNER, ROLE_EXPLAINER, ROLE_TASTE}
    assert before == after
    _assert_private_canaries_absent(context)


def test_missing_profile_is_non_fatal_and_read_only(tmp_path: Path) -> None:
    context = build_research_persona_runtime_context(data_root=tmp_path, roles=ROLE_PLANNER)

    assert context.enabled is False
    assert context.profile_exists is False
    assert context.profile_source == SOURCE_MISSING
    assert context.capsules == {}
    assert context.role_counts["missing"] == 1
    assert context.prompt_safety[KEY_RAW_PROFILE] is False
    assert not research_persona_root(tmp_path).exists()


def test_invalid_stored_profile_returns_disabled_context(tmp_path: Path) -> None:
    path = research_persona_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")

    context = build_research_persona_runtime_context(data_root=tmp_path, roles=[ROLE_EXECUTOR])

    assert context.enabled is False
    assert context.profile_exists is True
    assert context.profile_source == SOURCE_INVALID
    assert context.capsules == {}
    assert context.warnings
    assert path.read_text(encoding="utf-8") == "{not valid json"


def test_capsule_bundle_rejects_raw_profile_dumps() -> None:
    raw_profile = _persona().model_dump(mode="json")

    with pytest.raises(ResearchPersonaError):
        build_research_persona_capsule_bundle(persona=raw_profile)  # type: ignore[arg-type]


def test_workflow_selection_returns_only_prompt_safe_subset() -> None:
    context = build_research_persona_runtime_context(persona=_persona())

    selection = select_research_persona_capsules_for_workflow(context, workflow_id=WORKFLOW_WRITE_PAPER)

    assert selection.enabled is True
    assert set(selection.selected_roles) == {ROLE_WRITER, ROLE_LITERATURE, ROLE_VERIFIER}
    assert set(selection.capsules) == {ROLE_WRITER, ROLE_LITERATURE, ROLE_VERIFIER}
    assert selection.missing_roles == []
    assert selection.prompt_safety[KEY_PRIVATE_LOCAL] is False
    assert selection.prompt_safety[KEY_PROJECT_PRIVATE] is False
    assert selection.prompt_safety[KEY_NEVER_PROMPT] is False
    _assert_private_canaries_absent(selection)


def test_workflow_selection_reports_missing_roles_when_context_is_narrow() -> None:
    context = build_research_persona_runtime_context(persona=_persona(), roles=[ROLE_PLANNER])

    selection = select_research_persona_capsules_for_workflow(
        context,
        workflow_id=WORKFLOW_WRITE_PAPER,
        roles=[ROLE_PLANNER, ROLE_WRITER],
    )

    assert selection.enabled is True
    assert set(selection.capsules) == {ROLE_PLANNER}
    assert selection.missing_roles == [ROLE_WRITER]
    assert selection.role_counts["requested"] == 2
    assert selection.role_counts["available"] == 1
    assert selection.warnings


def test_runtime_models_are_strict_and_immutable() -> None:
    context = build_research_persona_runtime_context(persona=_persona(), roles=[ROLE_PLANNER])
    payload = context.model_dump(mode="json")
    payload["legacy"] = True

    with pytest.raises(ValidationError):
        type(context).model_validate(payload)

    with pytest.raises(ValidationError):
        context.enabled = False  # type: ignore[misc]
