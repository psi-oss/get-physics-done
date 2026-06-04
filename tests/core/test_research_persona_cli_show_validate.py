from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.cli import app
from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaFact,
    research_persona_path,
    save_research_persona,
)
from tests.helpers.cli import StableCliRunner, assert_no_traceback, assert_result_exit

RUNNER = StableCliRunner()

SAFE_FACT_ID = "rp-cli-safe"
SAFE_VALUE = "CLI_SAFE_CANARY theorem-first explanations are preferred"
PRIVATE_FACT_ID = "rp-cli-private-local"
PRIVATE_VALUE = "CLI_PRIVATE_LOCAL_CANARY local note path is private"
PROJECT_FACT_ID = "rp-cli-project-private"
PROJECT_VALUE = "CLI_PROJECT_PRIVATE_CANARY project collaborator preference"
SESSION_FACT_ID = "rp-cli-session-only"
SESSION_VALUE = "CLI_SESSION_ONLY_CANARY temporary chat steering"
NEVER_FACT_ID = "rp-cli-never-prompt"
NEVER_VALUE = "CLI_NEVER_PROMPT_CANARY secret identity detail"


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "data"
    monkeypatch.setenv("GPD_DATA_DIR", str(root))
    return root


def _json_result(result, *, expect_exit: int = 0) -> dict[str, object]:
    assert_no_traceback(result)
    assert_result_exit(result, expect_exit)
    payload = json.loads(result.output)
    assert isinstance(payload, dict)
    return payload


def _tree_snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    snapshot: dict[str, str] = {}
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        snapshot[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return snapshot


def _fact(fact_id: str, value: str, privacy: str) -> ResearchPersonaFact:
    return ResearchPersonaFact(
        id=fact_id,
        category="workstyle",
        value=value,
        confidence="confirmed",
        privacy=privacy,
        sources=["user_statement"],
    )


def _mixed_privacy_persona() -> ResearchPersona:
    return ResearchPersona(
        facts=[
            _fact(SAFE_FACT_ID, SAFE_VALUE, "safe_to_share"),
            _fact(PRIVATE_FACT_ID, PRIVATE_VALUE, "private_local"),
            _fact(PROJECT_FACT_ID, PROJECT_VALUE, "project_private"),
            _fact(SESSION_FACT_ID, SESSION_VALUE, "session_only"),
            _fact(NEVER_FACT_ID, NEVER_VALUE, "never_prompt"),
        ],
        standing_preferences=["Prefer concise verification summaries"],
        papers=["Private draft: persona-memory-design"],
        collaborators=["Private collaborator canary"],
    )


def _invoke_raw(args: list[str], *, cwd: Path | None = None, input_text: str | None = None):
    cli_args = ["--raw"]
    if cwd is not None:
        cli_args.extend(["--cwd", str(cwd)])
    cli_args.extend(args)
    return RUNNER.invoke(app, cli_args, input=input_text)


def _render(payload: object) -> str:
    return json.dumps(payload, sort_keys=True)


def _projection_fact_ids(payload: dict[str, object]) -> set[str]:
    projection = payload["projection"]
    assert isinstance(projection, dict)
    facts = projection["facts"]
    assert isinstance(facts, list)
    return {str(fact["id"]) for fact in facts if isinstance(fact, dict)}


def test_research_persona_show_missing_profile_is_read_only(
    tmp_path: Path,
    data_root: Path,
) -> None:
    project_root = tmp_path / "project"
    gpd_dir = project_root / "GPD"
    gpd_dir.mkdir(parents=True)
    (gpd_dir / "state.json").write_text('{"existing": true}\n', encoding="utf-8")
    (gpd_dir / "STATE.md").write_text("# Existing State\n", encoding="utf-8")
    before_gpd = _tree_snapshot(gpd_dir)

    result = _invoke_raw(["research-persona", "show"], cwd=project_root)
    payload = _json_result(result)

    assert payload["path"] == str(research_persona_path(data_root))
    assert payload["exists"] is False
    assert payload["counts"] == {
        "facts": 0,
        "axes": 0,
        "standing_preferences": 0,
        "negative_preferences": 0,
        "tools": 0,
        "research_areas": 0,
        "papers": 0,
        "collaborators": 0,
        "references": 0,
        "expertise": 0,
        "workstyle": 0,
        "scientific_taste": 0,
    }
    projection = payload["projection"]
    assert isinstance(projection, dict)
    assert projection["purpose"] == "local"
    assert _tree_snapshot(gpd_dir) == before_gpd
    assert not (data_root / "research-persona").exists()


@pytest.mark.parametrize(
    ("projection_name", "purpose", "expected_fact_ids", "forbidden_values"),
    [
        (
            "local",
            "local",
            {SAFE_FACT_ID, PRIVATE_FACT_ID, PROJECT_FACT_ID},
            [SESSION_VALUE, NEVER_VALUE],
        ),
        (
            "project-private",
            "project_private",
            {SAFE_FACT_ID, PROJECT_FACT_ID},
            [PRIVATE_VALUE, SESSION_VALUE, NEVER_VALUE],
        ),
        (
            "prompt",
            "prompt",
            {SAFE_FACT_ID},
            [PRIVATE_VALUE, PROJECT_VALUE, SESSION_VALUE, NEVER_VALUE, "Private draft", "Private collaborator"],
        ),
        (
            "public",
            "public",
            {SAFE_FACT_ID},
            [PRIVATE_VALUE, PROJECT_VALUE, SESSION_VALUE, NEVER_VALUE, "Private draft", "Private collaborator"],
        ),
    ],
)
def test_research_persona_show_projection_privacy_boundaries(
    data_root: Path,
    projection_name: str,
    purpose: str,
    expected_fact_ids: set[str],
    forbidden_values: list[str],
) -> None:
    save_research_persona(_mixed_privacy_persona(), data_root)

    result = _invoke_raw(["research-persona", "show", "--projection", projection_name])
    payload = _json_result(result)

    projection = payload["projection"]
    assert isinstance(projection, dict)
    assert payload["exists"] is True
    assert projection["purpose"] == purpose
    assert _projection_fact_ids(payload) == expected_fact_ids
    rendered = _render(payload)
    assert SAFE_VALUE in rendered
    for forbidden in forbidden_values:
        assert forbidden not in rendered


def test_research_persona_validate_accepts_profile_json_file(
    tmp_path: Path,
    data_root: Path,
) -> None:
    profile_json = tmp_path / "persona.json"
    profile_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "standing_preferences": ["Prefer explicit assumptions"],
                "tools": ["pytest"],
            }
        ),
        encoding="utf-8",
    )

    result = _invoke_raw(["research-persona", "validate", str(profile_json)])
    payload = _json_result(result)

    assert payload["valid"] is True
    assert payload["errors"] == []
    assert payload["path"] == str(profile_json)
    assert payload["exists"] is True
    assert not (data_root / "research-persona").exists()


def test_research_persona_validate_accepts_stdin(
    data_root: Path,
) -> None:
    stdin_payload = json.dumps({"schema_version": 1, "research_areas": ["quantum field theory"]})

    result = _invoke_raw(["research-persona", "validate", "-"], input_text=stdin_payload)
    payload = _json_result(result)

    assert payload["valid"] is True
    assert payload["errors"] == []
    assert payload["path"] == "stdin"
    assert payload["exists"] is False
    assert not (data_root / "research-persona").exists()


def test_research_persona_validate_invalid_json_returns_raw_error(
    tmp_path: Path,
    data_root: Path,
) -> None:
    profile_json = tmp_path / "broken.json"
    profile_json.write_text("{ not json", encoding="utf-8")

    result = _invoke_raw(["research-persona", "validate", str(profile_json)])
    payload = _json_result(result, expect_exit=1)

    assert "error" in payload
    assert str(payload["error"]).strip()
    assert str(profile_json) in str(payload["error"])
    assert not (data_root / "research-persona").exists()


def test_research_persona_validate_invalid_schema_returns_structured_failure(
    tmp_path: Path,
    data_root: Path,
) -> None:
    profile_json = tmp_path / "invalid-schema.json"
    profile_json.write_text(json.dumps({"schema_version": 2, "tools": "pytest"}), encoding="utf-8")

    result = _invoke_raw(["research-persona", "validate", str(profile_json)])
    payload = _json_result(result)

    assert payload["valid"] is False
    assert payload["path"] == str(profile_json)
    assert payload["exists"] is True
    errors = payload["errors"]
    assert isinstance(errors, list)
    assert errors
    assert "schema_version" in " ".join(str(error) for error in errors)
    assert not (data_root / "research-persona").exists()
