from __future__ import annotations

import json

from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaFact,
    build_research_persona_capsule,
    project_research_persona,
)

SAFE_FACT_ID = "rp-safe-to-share-canary"
SAFE_VALUE = "SAFE_TO_SHARE_CANARY theorem-first derivations are preferred"
PRIVATE_LOCAL_VALUE = "PRIVATE_LOCAL_CANARY local notebook path is /tmp/private-lab-note"
PROJECT_PRIVATE_FACT_ID = "rp-project-private-canary"
PROJECT_PRIVATE_VALUE = "PROJECT_PRIVATE_CANARY project-specific collaborator preference"
SESSION_ONLY_FACT_ID = "rp-session-only-canary"
SESSION_ONLY_VALUE = "SESSION_ONLY_CANARY temporary steering for this chat"
NEVER_PROMPT_FACT_ID = "rp-never-prompt-canary"
NEVER_PROMPT_VALUE = "NEVER_PROMPT_CANARY secret identity detail"


def _fact(fact_id: str, value: str, privacy: str) -> ResearchPersonaFact:
    return ResearchPersonaFact(
        id=fact_id,
        category="workstyle",
        value=value,
        confidence="confirmed",
        privacy=privacy,
        sources=["user_statement"],
        evidence_refs=[f"evidence-{fact_id}"],
    )


def _persona_with_mixed_privacy_facts() -> ResearchPersona:
    return ResearchPersona(
        schema_version=1,
        facts=[
            _fact(SAFE_FACT_ID, SAFE_VALUE, "safe_to_share"),
            _fact("rp-private-local-canary", PRIVATE_LOCAL_VALUE, "private_local"),
            _fact(PROJECT_PRIVATE_FACT_ID, PROJECT_PRIVATE_VALUE, "project_private"),
            _fact(SESSION_ONLY_FACT_ID, SESSION_ONLY_VALUE, "session_only"),
            _fact(NEVER_PROMPT_FACT_ID, NEVER_PROMPT_VALUE, "never_prompt"),
        ],
    )


def _dump(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[attr-defined]
    return value


def _render(value: object) -> str:
    return json.dumps(_dump(value), sort_keys=True, default=str)


def _capsule_data(capsule: object) -> dict[str, object]:
    data = _dump(capsule)
    assert isinstance(data, dict)
    return data


def _assert_absent(payload: object, *needles: str) -> None:
    rendered = _render(payload)
    for needle in needles:
        assert needle not in rendered


def test_prompt_projection_excludes_non_prompt_privacy_facts() -> None:
    projection = project_research_persona(_persona_with_mixed_privacy_facts(), purpose="prompt")
    rendered = _render(projection)

    assert SAFE_VALUE in rendered
    _assert_absent(
        projection,
        PRIVATE_LOCAL_VALUE,
        PROJECT_PRIVATE_FACT_ID,
        PROJECT_PRIVATE_VALUE,
        SESSION_ONLY_FACT_ID,
        SESSION_ONLY_VALUE,
        NEVER_PROMPT_FACT_ID,
        NEVER_PROMPT_VALUE,
    )


def test_project_projection_includes_project_private_only_for_project_purpose() -> None:
    persona = _persona_with_mixed_privacy_facts()

    prompt_projection = project_research_persona(persona, purpose="prompt")
    project_projection = project_research_persona(persona, purpose="project")

    assert PROJECT_PRIVATE_VALUE not in _render(prompt_projection)
    assert PROJECT_PRIVATE_FACT_ID not in _render(prompt_projection)
    assert PROJECT_PRIVATE_VALUE in _render(project_projection)
    assert PROJECT_PRIVATE_FACT_ID in _render(project_projection)
    _assert_absent(
        project_projection,
        PRIVATE_LOCAL_VALUE,
        SESSION_ONLY_FACT_ID,
        SESSION_ONLY_VALUE,
        NEVER_PROMPT_FACT_ID,
        NEVER_PROMPT_VALUE,
    )


def test_prompt_capsule_includes_safe_fact_and_redacts_or_omits_private_local() -> None:
    capsule = build_research_persona_capsule(_persona_with_mixed_privacy_facts(), role="planner")
    rendered = _render(capsule)

    assert SAFE_VALUE in rendered
    _assert_absent(
        capsule,
        PRIVATE_LOCAL_VALUE,
        PROJECT_PRIVATE_FACT_ID,
        PROJECT_PRIVATE_VALUE,
        SESSION_ONLY_FACT_ID,
        SESSION_ONLY_VALUE,
        NEVER_PROMPT_FACT_ID,
        NEVER_PROMPT_VALUE,
    )


def test_persisted_style_capsule_excludes_session_only_facts() -> None:
    capsule = build_research_persona_capsule(_persona_with_mixed_privacy_facts(), role="executor")

    _assert_absent(capsule, SESSION_ONLY_FACT_ID, SESSION_ONLY_VALUE)


def test_role_capsule_carries_role_and_prompt_safe_influence_summary() -> None:
    capsule = build_research_persona_capsule(_persona_with_mixed_privacy_facts(), role="verifier")
    data = _capsule_data(capsule)

    assert data["role"] == "verifier"
    assert data["influence_summary"]
    assert SAFE_VALUE in _render(data["influence_summary"])
    _assert_absent(
        data["influence_summary"],
        PRIVATE_LOCAL_VALUE,
        PROJECT_PRIVATE_VALUE,
        SESSION_ONLY_VALUE,
        NEVER_PROMPT_VALUE,
    )
