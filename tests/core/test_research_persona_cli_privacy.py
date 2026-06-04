"""CLI privacy contracts for Research Persona capsule export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.cli import app
from gpd.core.research_persona import ResearchPersona, ResearchPersonaFact, save_research_persona
from tests.helpers.cli import (
    StableCliRunner,
    assert_cli_help_contract,
    assert_result_exit,
    invoke_help_text,
    json_output_from_result,
)

runner = StableCliRunner()

_CAPSULE_ROLES = ("planner", "explainer", "doppelganger", "taste")

_SAFE_FACT_ID = "rp-cli-safe-to-share-canary"
_SAFE_FACT_VALUE = "SAFE_TO_SHARE_CLI_CANARY theorem-first explanations are useful"
_SAFE_STANDING_VALUE = "SAFE_STANDING_CLI_CANARY show assumptions before tactics"
_SAFE_TASTE_VALUE = "SAFE_TASTE_CLI_CANARY prefers invariant checks"

_PRIVATE_FACT_CANARIES = {
    "private_local": (
        "rp-cli-private-local-canary",
        "PRIVATE_LOCAL_CLI_CANARY local notebook path is /tmp/secret-lab-note",
    ),
    "project_private": (
        "rp-cli-project-private-canary",
        "PROJECT_PRIVATE_CLI_CANARY collaborator constraint for a specific repository",
    ),
    "session_only": (
        "rp-cli-session-only-canary",
        "SESSION_ONLY_CLI_CANARY temporary instruction for this chat only",
    ),
    "never_prompt": (
        "rp-cli-never-prompt-canary",
        "NEVER_PROMPT_CLI_CANARY credential-like identity detail",
    ),
}

_NON_PROMPT_TOP_LEVEL_CANARIES = (
    "PRIVATE_PAPER_CLI_CANARY unpublished draft title",
    "PRIVATE_COLLABORATOR_CLI_CANARY collaborator name",
    "PRIVATE_REFERENCE_CLI_CANARY local bibliography note",
)


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


def _write_mixed_privacy_persona(data_root: Path) -> None:
    private_facts = [
        _fact(fact_id, value, privacy)
        for privacy, (fact_id, value) in _PRIVATE_FACT_CANARIES.items()
    ]
    save_research_persona(
        ResearchPersona(
            facts=[_fact(_SAFE_FACT_ID, _SAFE_FACT_VALUE, "safe_to_share"), *private_facts],
            standing_preferences=[_SAFE_STANDING_VALUE],
            tools=["pytest"],
            research_areas=["mathematical physics"],
            papers=[_NON_PROMPT_TOP_LEVEL_CANARIES[0]],
            collaborators=[_NON_PROMPT_TOP_LEVEL_CANARIES[1]],
            references=[_NON_PROMPT_TOP_LEVEL_CANARIES[2]],
            expertise=["spectral methods"],
            workstyle=["small targeted tests before full-suite runs"],
            scientific_taste=[_SAFE_TASTE_VALUE],
        ),
        data_root,
    )


def _render_json(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def _assert_private_canaries_absent(payload: object) -> None:
    rendered = _render_json(payload)
    for privacy, (fact_id, value) in _PRIVATE_FACT_CANARIES.items():
        assert privacy not in rendered
        assert fact_id not in rendered
        assert value not in rendered
    for value in _NON_PROMPT_TOP_LEVEL_CANARIES:
        assert value not in rendered


def test_research_persona_help_surfaces_local_privacy_commands() -> None:
    root_help = invoke_help_text(runner, app, ())
    assert_cli_help_contract(
        root_help,
        commands=("research-persona",),
        sections=("Machine-local research persona",),
    )

    group_help = invoke_help_text(runner, app, ("research-persona",))
    assert_cli_help_contract(
        group_help,
        commands=("show", "validate", "apply-patch", "diff", "forget", "export-capsule"),
        sections=("Machine-local research persona",),
    )

    capsule_help = invoke_help_text(runner, app, ("research-persona", "export-capsule"))
    assert_cli_help_contract(capsule_help, options=("--role",), sections=("prompt-safe",))


@pytest.mark.parametrize("role", _CAPSULE_ROLES)
def test_export_capsule_role_is_prompt_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    data_root = tmp_path / "machine-data"
    _write_mixed_privacy_persona(data_root)
    monkeypatch.setenv("GPD_DATA_DIR", str(data_root))

    result = runner.invoke(app, ["--raw", "research-persona", "export-capsule", "--role", role])

    assert_result_exit(result)
    payload = json_output_from_result(result)
    assert isinstance(payload, dict)
    assert payload["schema_version"] == 1
    assert payload["role"] == role
    assert payload["purpose"] == "prompt"
    assert payload["summary"]
    assert isinstance(payload["influence_summary"], dict)
    assert _SAFE_FACT_VALUE in _render_json(payload)
    assert _SAFE_STANDING_VALUE in _render_json(payload)
    assert _SAFE_TASTE_VALUE in _render_json(payload)
    _assert_private_canaries_absent(payload)
