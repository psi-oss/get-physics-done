from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from gpd.cli import app
from gpd.core import research_persona_cli as support
from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaFact,
    ResearchPersonaPatch,
    research_persona_root,
    save_research_persona,
)
from tests.helpers.cli import StableCliRunner, assert_result_exit, json_output_from_result

RUNNER = StableCliRunner()

INGESTION_MODULE = "gpd.core.research_persona_ingestion"
APPLICATIONS_MODULE = "gpd.core.research_persona_applications"
PRIVACY_DEFAULT = "project_private"
SAFE_VALUE = "CLI_APPLICATION_SAFE_CANARY theorem-first explanations"
PRIVATE_VALUE = "CLI_APPLICATION_PRIVATE_CANARY private notebook detail"
TASK_TEXT = "compare two candidate derivations"
FOCUS_TEXT = "derivation taste"
AUDIENCE_TEXT = "advanced reader"
APPLICATION_DOPPELGANGER = "doppelganger"
APPLICATION_EXPLAIN_PLAN = "explain_plan"
APPLICATION_TASTE_CHECK = "taste_check"
KEY_ADVICE = "advice"
KEY_APPLICATION = "application"
KEY_AUDIENCE = "audience"
KEY_CANDIDATE_DOCUMENT = "candidate_document"
KEY_EVIDENCE_SUMMARY = "evidence_summary"
KEY_FACT = "fact"
KEY_FOCUS = "focus"
KEY_OUTPUT = "output"
KEY_PATCH = "patch"
KEY_PERSONA_CAPSULE = "persona_capsule"
KEY_PLAN_DOCUMENT = "plan_document"
KEY_PRIVACY_DEFAULT = "privacy_default"
KEY_PRIVACY_DEFAULTS = "privacy_defaults"
KEY_PRIVACY = "privacy"
KEY_PROMPT_SAFE = "prompt_safe"
KEY_PURPOSE = "purpose"
KEY_RAW_PROFILE_EXPOSED = "raw_profile_exposed"
KEY_REVIEW_ROUTE = "review_route"
KEY_SOURCE_DOCUMENT = "source_document"
KEY_SOURCE_EXISTS = "source_exists"
KEY_SOURCE_KIND = "source_kind"
KEY_SOURCE_PATH = "source_path"
KEY_TASK = "task"
KEY_WRITES_PERSONA_STORAGE = "writes_persona_storage"
KEY_APPROVAL_REQUIRED = "approval_required"
STDIN_MARKER = "-"
STDIN_SOURCE = "stdin"
PROMPT_PURPOSE = "prompt"
SOURCE_KIND_PAPER_IMPORT = "paper_import"
OPERATIONS_FIELD = "operations"
WRITTEN_FIELD = "written"


def _patch_payload(*, privacy: str = PRIVACY_DEFAULT) -> dict[str, object]:
    return {
        "schema_version": 1,
        KEY_SOURCE_KIND: SOURCE_KIND_PAPER_IMPORT,
        "reason": "source ingestion contract fixture",
        OPERATIONS_FIELD: [
            {
                "op": "add_fact",
                "fact": {
                    "id": "ingested.source.preference",
                    "category": "research_area",
                    "value": "prefers operator-algebra framing",
                    "confidence": "inferred",
                    "privacy": privacy,
                    "sources": ["paper_import"],
                    "evidence_refs": ["source-doc:0"],
                },
            }
        ],
        "evidence": [
            {
                "id": "source-doc:0",
                "source_kind": "paper_import",
                "summary": "Explicit source document",
            }
        ],
    }


def _source_document() -> dict[str, object]:
    return {
        "documents": [
            {
                "kind": "paper",
                "title": "Persona-aware research planning",
                "summary": "A consented source fixture for persona ingestion.",
            }
        ]
    }


def _install_ingestion_module(monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, object]]) -> None:
    module = ModuleType(INGESTION_MODULE)

    def build_research_persona_ingestion_payload(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            KEY_PATCH: _patch_payload(privacy=str(kwargs[KEY_PRIVACY_DEFAULT])),
            KEY_EVIDENCE_SUMMARY: {"source_count": 1},
        }

    module.build_research_persona_ingestion_payload = (  # type: ignore[attr-defined]
        build_research_persona_ingestion_payload
    )
    monkeypatch.setitem(sys.modules, INGESTION_MODULE, module)


def _fact(fact_id: str, value: str, privacy: str) -> ResearchPersonaFact:
    return ResearchPersonaFact(
        id=fact_id,
        category="workstyle",
        value=value,
        confidence="confirmed",
        privacy=privacy,
        sources=["user_statement"],
    )


def _write_persona(data_root: Path) -> None:
    save_research_persona(
        ResearchPersona(
            facts=[
                _fact("app.safe", SAFE_VALUE, "safe_to_share"),
                _fact("app.private", PRIVATE_VALUE, "private_local"),
            ],
            scientific_taste=["Prefer conserved quantities as diagnostics"],
        ),
        data_root,
    )


def _install_applications_module(
    monkeypatch: pytest.MonkeyPatch,
    calls: dict[str, dict[str, object]],
) -> None:
    module = ModuleType(APPLICATIONS_MODULE)

    def build_researcher_doppelganger_payload(**kwargs: object) -> dict[str, object]:
        calls[APPLICATION_DOPPELGANGER] = kwargs
        return {KEY_ADVICE: [{"kind": "workstyle", "text": "Start from invariants."}]}

    def build_expertise_explanation_plan_payload(**kwargs: object) -> dict[str, object]:
        calls[APPLICATION_EXPLAIN_PLAN] = kwargs
        return {"sections": [{"kind": "math", "text": "State assumptions first."}]}

    def build_scientific_taste_check_payload(**kwargs: object) -> dict[str, object]:
        calls[APPLICATION_TASTE_CHECK] = kwargs
        return {"checks": [{"kind": "taste", "text": "Look for basis-independent tests."}]}

    module.build_researcher_doppelganger_payload = (  # type: ignore[attr-defined]
        build_researcher_doppelganger_payload
    )
    module.build_expertise_explanation_plan_payload = (  # type: ignore[attr-defined]
        build_expertise_explanation_plan_payload
    )
    module.build_scientific_taste_check_payload = (  # type: ignore[attr-defined]
        build_scientific_taste_check_payload
    )
    monkeypatch.setitem(sys.modules, APPLICATIONS_MODULE, module)


def _raw_payload(args: list[str], *, input_payload: object | None = None) -> tuple[dict[str, object], object]:
    input_text = None if input_payload is None else json.dumps(input_payload) + "\n"
    result = RUNNER.invoke(app, ["--raw", *args], input=input_text, catch_exceptions=False)
    assert_result_exit(result)
    payload = json_output_from_result(result)
    assert isinstance(payload, dict)
    return payload, result


def test_ingest_source_helper_uses_core_payload_and_never_writes_persona_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    _install_ingestion_module(monkeypatch, calls)

    payload = support.build_ingest_source_payload(
        cwd=tmp_path,
        source_document=_source_document(),
        source_path=STDIN_MARKER,
        privacy_default=PRIVACY_DEFAULT,
    )

    assert calls
    assert payload[KEY_WRITES_PERSONA_STORAGE] is False
    assert payload[KEY_SOURCE_PATH] == STDIN_SOURCE
    assert payload[KEY_SOURCE_EXISTS] is False
    assert (
        payload[KEY_PATCH][OPERATIONS_FIELD][0][KEY_FACT][KEY_PRIVACY]  # type: ignore[index]
        == PRIVACY_DEFAULT
    )
    assert payload[KEY_REVIEW_ROUTE][KEY_APPROVAL_REQUIRED] is True  # type: ignore[index]
    assert not research_persona_root(tmp_path).exists()


def test_ingest_source_output_writes_only_candidate_patch_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    _install_ingestion_module(monkeypatch, calls)
    output_path = tmp_path / "candidate-persona-patch.json"

    payload = support.build_ingest_source_payload(
        cwd=tmp_path,
        source_document=_source_document(),
        source_path=STDIN_MARKER,
        output_path=str(output_path),
        privacy_default=PRIVACY_DEFAULT,
    )
    artifact = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload[KEY_OUTPUT][WRITTEN_FIELD] is True  # type: ignore[index]
    assert artifact == payload[KEY_PATCH]
    assert OPERATIONS_FIELD in artifact
    assert KEY_REVIEW_ROUTE not in artifact
    assert not research_persona_root(tmp_path).exists()


def test_ingest_source_helper_accepts_alias_wrapped_sources_with_real_core(tmp_path: Path) -> None:
    payload = support.build_ingest_source_payload(
        cwd=tmp_path,
        source_document={
            "sources": [
                {
                    "kind": "paper",
                    "title": "Alias-normalized research profile",
                    "summary": "Research areas: conformal bootstrap\nTools: Python",
                }
            ]
        },
        source_path=STDIN_MARKER,
        privacy_default=PRIVACY_DEFAULT,
    )
    patch = ResearchPersonaPatch.model_validate(payload[KEY_PATCH])

    assert patch.operations
    assert payload[KEY_WRITES_PERSONA_STORAGE] is False
    assert not research_persona_root(tmp_path).exists()


def test_application_helpers_pass_prompt_safe_capsules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "machine-data"
    _write_persona(data_root)
    calls: dict[str, dict[str, object]] = {}
    _install_applications_module(monkeypatch, calls)

    doppelganger = support.research_persona_doppelganger_payload(
        data_root=data_root,
        task=TASK_TEXT,
        focus=FOCUS_TEXT,
        max_items=3,
    )
    explain_plan = support.research_persona_explain_plan_payload(
        data_root=data_root,
        plan_document={"steps": ["derive bound"]},
        audience=AUDIENCE_TEXT,
    )
    taste_check = support.research_persona_taste_check_payload(
        data_root=data_root,
        candidate_document={"claim": "basis-dependent shortcut"},
        focus=FOCUS_TEXT,
    )

    rendered_calls = json.dumps(calls, sort_keys=True, default=str)
    assert doppelganger[KEY_PROMPT_SAFE] is True
    assert explain_plan[KEY_RAW_PROFILE_EXPOSED] is False
    assert taste_check[KEY_PERSONA_CAPSULE][KEY_PURPOSE] == PROMPT_PURPOSE  # type: ignore[index]
    assert SAFE_VALUE in rendered_calls
    assert PRIVATE_VALUE not in rendered_calls
    assert calls[APPLICATION_DOPPELGANGER][KEY_TASK] == TASK_TEXT
    assert calls[APPLICATION_EXPLAIN_PLAN][KEY_AUDIENCE] == AUDIENCE_TEXT
    assert calls[APPLICATION_TASTE_CHECK][KEY_FOCUS] == FOCUS_TEXT


def test_raw_cli_invokes_ingest_source_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_document()
    calls: list[dict[str, object]] = []

    def fake_payload(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            KEY_PATCH: _patch_payload(),
            KEY_EVIDENCE_SUMMARY: {},
            KEY_PRIVACY_DEFAULTS: {},
            KEY_REVIEW_ROUTE: {},
            KEY_OUTPUT: {},
        }

    monkeypatch.setattr(support, "build_ingest_source_payload", fake_payload)

    payload, _result = _raw_payload(
        [
            "research-persona",
            "ingest-source",
            STDIN_MARKER,
            "--output",
            str(tmp_path / "candidate.json"),
            "--privacy-default",
            PRIVACY_DEFAULT,
        ],
        input_payload=source,
    )

    assert payload[KEY_PATCH][KEY_SOURCE_KIND] == SOURCE_KIND_PAPER_IMPORT  # type: ignore[index]
    assert calls[0][KEY_SOURCE_DOCUMENT] == source
    assert calls[0][KEY_SOURCE_PATH] == STDIN_MARKER
    assert calls[0][KEY_PRIVACY_DEFAULT] == PRIVACY_DEFAULT


@pytest.mark.parametrize(
    ("command_args", "helper_name", "input_payload", "expected_key"),
    [
        (
            ["research-persona", "doppelganger", "--task", TASK_TEXT],
            "build_doppelganger_payload",
            None,
            "task",
        ),
        (
            ["research-persona", "explain-plan", "-", "--audience", AUDIENCE_TEXT],
            "build_explain_plan_payload",
            {"steps": ["explain assumptions"]},
            "plan_document",
        ),
        (
            ["research-persona", "taste-check", "-", "--focus", FOCUS_TEXT],
            "build_taste_check_payload",
            {"claim": "candidate shortcut"},
            "candidate_document",
        ),
    ],
)
def test_raw_cli_invokes_application_preview_payloads(
    monkeypatch: pytest.MonkeyPatch,
    command_args: list[str],
    helper_name: str,
    input_payload: object | None,
    expected_key: str,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_payload(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {KEY_APPLICATION: helper_name, KEY_PROMPT_SAFE: True, KEY_RAW_PROFILE_EXPOSED: False}

    monkeypatch.setattr(support, helper_name, fake_payload)

    payload, _result = _raw_payload(command_args, input_payload=input_payload)

    assert payload[KEY_PROMPT_SAFE] is True
    assert calls
    assert expected_key in calls[0]
