from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.cli import app
from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaAxis,
    ResearchPersonaFact,
    research_persona_root,
    save_research_persona,
)
from tests.helpers.cli import StableCliRunner, assert_no_traceback, assert_result_exit, json_output_from_result

RUNNER = StableCliRunner()
CHECK_CAPSULE = "capsule_not_ready"
CHECK_INVALID_PRIVACY = "invalid_privacy"
CHECK_MODEL = "model_validation"
CHECK_ORPHAN_AXIS = "orphan_axis_fact_ids"
CHECK_PRIVATE = "private_not_prompt_projected"
KEY_CANDIDATE_PATCH = "candidate_patch"
KEY_EXISTS = "exists"
KEY_FINDINGS = "findings"
KEY_OP = "op"
KEY_OPERATIONS = "operations"
KEY_READ_ONLY = "read_only"
KEY_REVIEW_ROUTE = "review_route"
KEY_SEVERITY = "severity"
KEY_VALID = "valid"
KEY_WRITES_PERSONA_STORAGE = "writes_persona_storage"
OP_UPDATE = "update"
PRIVATE_VALUE = "CLI_AUDIT_PRIVATE_CANARY unpublished notebook route"
SEVERITY_INFO = "info"
STDIN_MARKER = "-"


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "data"
    monkeypatch.setenv("GPD_DATA_DIR", str(root))
    return root


def _fact(fact_id: str, *, privacy: str = "safe_to_share") -> ResearchPersonaFact:
    return ResearchPersonaFact(
        id=fact_id,
        category="workstyle",
        value=PRIVATE_VALUE if privacy == "private_local" else "Use short proof-first plans",
        privacy=privacy,
        confidence="confirmed",
        sources=["user_statement"],
        evidence_refs=["ev:cli"],
    )


def _write_persona(data_root: Path) -> None:
    save_research_persona(
        ResearchPersona(
            facts=[
                _fact("fact.private", privacy="private_local"),
                _fact("fact.safe"),
            ],
            axes=[
                ResearchPersonaAxis(
                    id="axis.orphan",
                    privacy="safe_to_share",
                    confidence="confirmed",
                    fact_ids=["fact.safe", "fact.missing"],
                )
            ],
        ),
        data_root,
    )


def _tree_snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    snapshot: dict[str, str] = {}
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        snapshot[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return snapshot


def _invoke_raw(args: list[str], *, input_payload: object | None = None) -> dict[str, object]:
    input_text = None if input_payload is None else json.dumps(input_payload) + "\n"
    result = RUNNER.invoke(app, ["--raw", *args], input=input_text, catch_exceptions=False)
    assert_no_traceback(result)
    assert_result_exit(result)
    payload = json_output_from_result(result)
    assert isinstance(payload, dict)
    return payload


def _finding_checks(payload: dict[str, object]) -> set[str]:
    findings = payload[KEY_FINDINGS]
    assert isinstance(findings, list)
    return {str(row["check"]) for row in findings if isinstance(row, dict)}


def test_research_persona_audit_cli_is_read_only_for_stored_profile(data_root: Path) -> None:
    _write_persona(data_root)
    before = _tree_snapshot(research_persona_root(data_root))

    payload = _invoke_raw(["research-persona", "audit"])
    operations = payload[KEY_CANDIDATE_PATCH][KEY_OPERATIONS]  # type: ignore[index]
    rendered = json.dumps(payload, sort_keys=True)

    assert payload[KEY_VALID] is True
    assert payload[KEY_EXISTS] is True
    assert payload[KEY_READ_ONLY] is True
    assert payload[KEY_WRITES_PERSONA_STORAGE] is False
    assert CHECK_ORPHAN_AXIS in _finding_checks(payload)
    assert any(operation[KEY_OP] == OP_UPDATE for operation in operations)
    assert KEY_REVIEW_ROUTE in payload
    assert PRIVATE_VALUE not in rendered
    assert _tree_snapshot(research_persona_root(data_root)) == before


def test_research_persona_audit_cli_no_info_suppresses_privacy_boundary_findings(data_root: Path) -> None:
    _write_persona(data_root)

    payload = _invoke_raw(["research-persona", "audit", "--no-info"])
    severities = {
        str(row[KEY_SEVERITY])
        for row in payload[KEY_FINDINGS]  # type: ignore[index]
        if isinstance(row, dict)
    }

    assert SEVERITY_INFO not in severities
    assert CHECK_PRIVATE not in _finding_checks(payload)


def test_research_persona_audit_cli_accepts_stdin_invalid_profile(data_root: Path) -> None:
    raw_profile = {
        "schema_version": 1,
        "facts": [
            {
                "id": "fact.bad",
                "category": "tool",
                "value": "Julia",
                "confidence": "confirmed",
                "privacy": "public",
                "sources": ["user_statement"],
            }
        ],
    }

    payload = _invoke_raw(["research-persona", "audit", STDIN_MARKER], input_payload=raw_profile)

    assert payload[KEY_VALID] is False
    assert CHECK_MODEL in _finding_checks(payload)
    assert CHECK_INVALID_PRIVACY in _finding_checks(payload)
    assert not research_persona_root(data_root).exists()


def test_research_persona_audit_cli_missing_profile_is_read_only(data_root: Path) -> None:
    payload = _invoke_raw(["research-persona", "audit"])

    assert payload[KEY_VALID] is True
    assert payload[KEY_EXISTS] is False
    assert CHECK_CAPSULE in _finding_checks(payload)
    assert not research_persona_root(data_root).exists()
