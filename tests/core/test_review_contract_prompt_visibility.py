from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

from gpd import registry
from gpd.adapters.install_utils import expand_at_includes
from gpd.core.model_visible_sections import (
    MODEL_VISIBLE_CLOSED_SCHEMA_PHRASE,
)
from gpd.core.model_visible_text import (
    AGENT_ARTIFACT_WRITE_AUTHORITIES,
    AGENT_COMMIT_AUTHORITIES,
    AGENT_ROLE_FAMILIES,
    AGENT_SHARED_STATE_AUTHORITIES,
    AGENT_SURFACES,
    COMMAND_POLICY_FRONTMATTER_KEY,
    COMMAND_POLICY_PROMPT_WRAPPER_KEY,
    REVIEW_CONTRACT_CONDITIONAL_WHENS,
    REVIEW_CONTRACT_FRONTMATTER_KEY,
    REVIEW_CONTRACT_MODES,
    REVIEW_CONTRACT_PREFLIGHT_CHECKS,
    REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
    REVIEW_CONTRACT_REQUIRED_STATES,
    VALID_CONTEXT_MODES,
    agent_visibility_note,
    command_visibility_note,
    review_contract_visibility_note,
)
from gpd.core.review_contract_prompt import (
    normalize_review_contract_frontmatter_payload,
    normalize_review_contract_payload,
    render_review_contract_prompt,
    review_contract_payload,
)
from tests.assertion_taxonomy_support import (
    FragmentMode,
    fragment_count,
    machine_exact,
    semantic_anchor,
    semantic_concept,
)
from tests.markdown_test_support import extract_markdown_section, parse_yaml_fences, require_mapping
from tests.workflow_authority_support import workflow_authority_text

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
REVIEW_CONTRACT_OWNER = "review-contract visibility"


def _assert_prompt_contracts(text: str, *assertions) -> None:
    for assertion in assertions:
        assertion.check(text)


def _read_command(name: str) -> str:
    return Path(registry.get_command(name).path).read_text(encoding="utf-8")


def _read_workflow(name: str) -> str:
    return workflow_authority_text(WORKFLOWS_DIR, name)


def _single_yaml_mapping(text: str, *, context: str) -> dict[object, object]:
    fences = parse_yaml_fences(text, context=context)
    assert len(fences) == 1
    return dict(require_mapping(fences[0].data, context=context))


def _model_visible_wrapper_payload(text: str, heading: str, wrapper_key: str, *, context: str) -> dict[object, object]:
    section = extract_markdown_section(text, f"## {heading}", context=context)
    mapping = _single_yaml_mapping(section, context=f"{context} {heading} YAML")

    assert set(mapping) == {wrapper_key}
    return dict(require_mapping(mapping[wrapper_key], context=f"{context} {wrapper_key} payload"))


def _model_visible_payload(text: str, heading: str, *, context: str) -> dict[object, object]:
    section = extract_markdown_section(text, f"## {heading}", context=context)
    return _single_yaml_mapping(section, context=f"{context} {heading} YAML")


def _assert_review_contract_payload(
    text: str,
    expected: Mapping[str, object],
    *,
    omitted: Iterable[str] = (),
    context: str,
) -> dict[object, object]:
    payload = _model_visible_wrapper_payload(
        text,
        "Review Contract",
        REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
        context=context,
    )
    assert payload == expected
    for field_name in omitted:
        assert field_name not in payload
    return payload


def test_review_grade_commands_surface_registry_contract_requirements_in_source() -> None:
    for command_name in registry.list_review_commands():
        source = _read_command(command_name)
        command = registry.get_command(command_name)
        contract = command.review_contract

        assert contract is not None
        assert f"{REVIEW_CONTRACT_FRONTMATTER_KEY}:" in source
        assert f"review_mode: {contract.review_mode}" in source

        for output in contract.required_outputs:
            assert output in source
        for evidence in contract.required_evidence:
            assert evidence in source
        for blocker in contract.blocking_conditions:
            assert blocker in source
        for check in contract.preflight_checks:
            assert check in source
        for artifact in contract.stage_artifacts:
            assert artifact in source
        for conditional in contract.conditional_requirements:
            assert conditional.when in source
            for output in conditional.required_outputs:
                assert output in source
            for evidence in conditional.required_evidence:
                assert evidence in source
            for blocker in conditional.blocking_conditions:
                assert blocker in source
            for artifact in conditional.stage_artifacts:
                assert artifact in source

        if contract.required_state:
            assert f"required_state: {contract.required_state}" in source


def test_review_contract_registry_uses_the_shared_frontmatter_key_constants() -> None:
    assert REVIEW_CONTRACT_FRONTMATTER_KEY in registry._COMMAND_FRONTMATTER_KEYS
    assert REVIEW_CONTRACT_FRONTMATTER_KEY == "review-contract"
    assert REVIEW_CONTRACT_PROMPT_WRAPPER_KEY == "review_contract"
    assert COMMAND_POLICY_FRONTMATTER_KEY in registry._COMMAND_FRONTMATTER_KEYS
    assert COMMAND_POLICY_FRONTMATTER_KEY == "command-policy"
    assert COMMAND_POLICY_PROMPT_WRAPPER_KEY == "command_policy"


def test_peer_review_workflow_keeps_contract_gate_prose_concise() -> None:
    workflow = _read_workflow("peer-review")
    _assert_prompt_contracts(
        workflow,
        machine_exact(
            "authoritative project-contract gate keys stay exact",
            ("project_contract_gate.authoritative", "effective_reference_intake"),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="workflow routing reads these state/context keys literally",
        ),
        semantic_anchor(
            "bundle guidance cannot override visible evidence",
            (
                "Bundle guidance",
                "additive only",
                "Reader-visible claims",
                "surfaced evidence",
                "first-class",
            ),
        ),
        semantic_anchor(
            "stale gate shorthand stays absent",
            "Apply the gate rule above.",
            mode=FragmentMode.ABSENT,
        ),
    )


def test_review_grade_commands_prepend_model_visible_review_contract_to_registry_content() -> None:
    for command_name in registry.list_review_commands():
        command = registry.get_command(command_name)
        contract = command.review_contract

        assert contract is not None
        expected_section = render_review_contract_prompt(contract)
        expected_payload = _model_visible_wrapper_payload(
            expected_section,
            "Review Contract",
            REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
            context=f"{command_name} rendered review contract",
        )
        actual_payload = _model_visible_wrapper_payload(
            command.content,
            "Review Contract",
            REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
            context=f"{command_name} command content",
        )
        assert command.content.startswith("## Command Requirements\n")
        assert "## Command Requirements" in command.content
        assert command_visibility_note() in command.content
        if command.requires:
            assert "requires:" in command.content
        assert "## Review Contract" in command.content
        assert actual_payload == expected_payload
        assert actual_payload["schema_version"] == 1
        assert actual_payload["review_mode"] == contract.review_mode
        if contract.required_state:
            assert actual_payload["required_state"] == contract.required_state
        assert tuple(actual_payload.get("required_outputs", ())) == tuple(contract.required_outputs)
        assert tuple(actual_payload.get("stage_artifacts", ())) == tuple(contract.stage_artifacts)
        fragment_count(
            "review-contract visibility note appears once",
            review_contract_visibility_note(),
            expected_count=1,
            section="## Review Contract",
        ).check(command.content)
        machine_exact(
            "review-contract wrapper key is exact in command content",
            f"{REVIEW_CONTRACT_PROMPT_WRAPPER_KEY}:",
            owner=REVIEW_CONTRACT_OWNER,
            rationale="model-visible review contracts are wrapped under this exact key",
            section="## Review Contract",
        ).check(command.content)
        if command.requires:
            for require_key, require_value in command.requires.items():
                assert str(require_key) in command.content
                if isinstance(require_value, list):
                    for item in require_value:
                        assert str(item) in command.content
                else:
                    assert str(require_value) in command.content


def test_model_visible_section_renderers_share_one_canonical_wrapper_structure() -> None:
    agent_section = registry.render_agent_requirements_section(
        tools=["git", "python"],
        commit_authority="orchestrator",
        surface="internal",
        role_family="analysis",
        artifact_write_authority="scoped_write",
        shared_state_authority="return_only",
    )
    command_section = registry.render_command_requires_section(
        context_mode="project-required",
        project_reentry_capable=False,
        agent="gpd-planner",
        allowed_tools=["git", "python"],
        requires={"files": ["PROJECT.md"]},
        command_policy=None,
    )
    review_contract_payload_data = normalize_review_contract_payload(
        {
            "schema_version": 1,
            "review_mode": "review",
            "preflight_checks": ["manuscript"],
        }
    )
    review_section = render_review_contract_prompt(review_contract_payload_data)

    assert _model_visible_payload(agent_section, "Agent Requirements", context="agent requirements section") == {
        "commit_authority": "orchestrator",
        "surface": "internal",
        "role_family": "analysis",
        "artifact_write_authority": "scoped_write",
        "shared_state_authority": "return_only",
        "tools": ["git", "python"],
    }
    assert _model_visible_payload(command_section, "Command Requirements", context="command requirements section") == {
        "context_mode": "project-required",
        "project_reentry_capable": False,
        "agent": "gpd-planner",
        "allowed_tools": ["git", "python"],
        "requires": {"files": ["PROJECT.md"]},
        COMMAND_POLICY_PROMPT_WRAPPER_KEY: {
            "schema_version": 1,
            "supporting_context_policy": {
                "project_context_mode": "project-required",
                "project_reentry_mode": "disallowed",
                "required_file_patterns": ["PROJECT.md"],
            },
        },
    }
    _assert_review_contract_payload(
        review_section,
        {
            "schema_version": 1,
            "review_mode": "review",
            "preflight_checks": ["manuscript"],
        },
        context="review contract section",
    )


def test_model_visible_wrapper_notes_surface_their_closed_schema_rules() -> None:
    note = review_contract_visibility_note()
    command_note = command_visibility_note()
    agent_note = agent_visibility_note()
    review_modes = " or ".join(f"`{value}`" for value in REVIEW_CONTRACT_MODES)
    conditional_whens = " or ".join(f"`{value}`" for value in REVIEW_CONTRACT_CONDITIONAL_WHENS)
    preflight_checks = " or ".join(f"`{value}`" for value in REVIEW_CONTRACT_PREFLIGHT_CHECKS)
    required_states = " or ".join(f"`{value}`" for value in REVIEW_CONTRACT_REQUIRED_STATES)
    agent_disjunctions = (
        " or ".join(f"`{value}`" for value in AGENT_COMMIT_AUTHORITIES),
        " or ".join(f"`{value}`" for value in AGENT_SURFACES),
        " or ".join(f"`{value}`" for value in AGENT_ROLE_FAMILIES),
        " or ".join(f"`{value}`" for value in AGENT_ARTIFACT_WRITE_AUTHORITIES),
        " or ".join(f"`{value}`" for value in AGENT_SHARED_STATE_AUTHORITIES),
    )

    fragment_count(
        "agent closed-schema phrase appears once",
        MODEL_VISIBLE_CLOSED_SCHEMA_PHRASE,
        expected_count=1,
    ).check(agent_note)
    fragment_count(
        "command closed-schema phrase appears once",
        MODEL_VISIBLE_CLOSED_SCHEMA_PHRASE,
        expected_count=1,
    ).check(command_note)
    fragment_count(
        "review-contract closed-schema phrase appears once",
        MODEL_VISIBLE_CLOSED_SCHEMA_PHRASE,
        expected_count=1,
    ).check(note)
    _assert_prompt_contracts(
        command_note,
        machine_exact(
            "command-policy wrapper key and field paths stay exact",
            (
                f"`{COMMAND_POLICY_PROMPT_WRAPPER_KEY}`",
                "`schema_version: 1`",
                "`allowed_tools`",
                "`requires`",
                "`files`",
                "context_mode",
                "project_reentry_capable",
                "`context_mode: project-required`",
            ),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="command-policy wrapper keys and field paths are machine contracts",
        ),
        semantic_anchor(
            "command-policy note describes strict typed YAML semantics",
            (
                "Strict booleans",
                "list fields are string lists",
                "omit empty optional fields",
                "typed command policy controls intake",
                "supporting-context routing",
                "managed outputs",
                "suffix lists use dotted suffixes",
            ),
        ),
        semantic_anchor(
            "stale command-policy authority wording stays absent",
            "Typed command policy is runtime-authoritative",
            mode=FragmentMode.ABSENT,
        ),
    )
    for value in VALID_CONTEXT_MODES:
        assert value in command_note
    for value in registry.canonical_agent_names():
        assert value not in command_note
    for disjunction in agent_disjunctions:
        assert disjunction not in agent_note
    semantic_anchor(
        "agent note has closed vocabulary and active-YAML authority",
        ("closed agent-authority vocabularies", "active YAML values below are authoritative for this agent"),
    ).check(agent_note)

    _assert_prompt_contracts(
        note,
        semantic_anchor(
            "review-contract note keeps closed-schema YAML authority",
            (
                "Omit empty optional fields.",
                "wrapper key",
                "closed review-contract vocabularies",
                "active YAML values below are authoritative",
            ),
        ),
        machine_exact(
            "review-contract note field paths stay exact",
            (
                "`schema_version` must be the integer `1`",
                "`conditional_requirements[].preflight_checks`",
                "`conditional_requirements[].blocking_preflight_checks`",
                "`scope_variants[].scope`",
                "`.activation`",
                "`scope_variants[].relaxed_preflight_checks`",
                "`.optional_preflight_checks`",
            ),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="review-contract wrapper field paths are consumed as closed schema guidance",
        ),
        semantic_anchor(
            "review-contract conditionals and scope variants stay semantically constrained",
            (
                "valid preflight-check values",
                "Each `conditional_requirements[].when` value may appear at most once.",
                "List fields reject blank entries and duplicates.",
                "Each conditional requirement needs one non-empty field.",
                "make named checks non-blocking",
                "make missing inputs advisory",
                "Non-empty scope override lists replace matching top-level lists.",
                "Each `scope_variants[].scope` may appear at most once.",
                "Each scope variant needs one non-empty override or preflight field.",
                "Runtime applies active scope variants additively",
            ),
        ),
    )
    for compacted_phrase in (review_modes, required_states, conditional_whens, preflight_checks):
        assert compacted_phrase not in note


@pytest.mark.parametrize(
    ("normalizer", "payload"),
    [
        (
            normalize_review_contract_payload,
            "schema_version: 1\nreview_mode: review\nreview_mode: publication\n",
        ),
        (
            normalize_review_contract_frontmatter_payload,
            (
                "review-contract:\n"
                "  schema_version: 1\n"
                "  review_mode: review\n"
                "  conditional_requirements:\n"
                "    - when: theorem-bearing claims are present\n"
                "      required_outputs:\n"
                "        - one\n"
                "      required_outputs:\n"
                "        - two\n"
            ),
        ),
    ],
)
def test_review_contract_normalizers_reject_duplicate_yaml_keys(normalizer, payload: str) -> None:
    with pytest.raises(ValueError, match="duplicate key"):
        normalizer(payload)


def test_review_contract_renderer_rejects_unknown_keys() -> None:
    contract = review_contract_payload(registry.get_command("write-paper").review_contract)
    assert contract is not None
    contract["unknown_field"] = "legacy drift"

    with pytest.raises(ValueError, match="Unknown review-contract field"):
        render_review_contract_prompt(contract)


def test_non_review_commands_with_requires_still_prepend_model_visible_command_requirements() -> None:
    for command_name in registry.list_commands():
        command = registry.get_command(command_name)
        if not command.requires or command.review_contract is not None:
            continue

        assert command.content.startswith("## Command Requirements\n")
        assert "requires:" in command.content
        assert command_visibility_note() in command.content
        for require_key, require_value in command.requires.items():
            assert str(require_key) in command.content
            if isinstance(require_value, list):
                for item in require_value:
                    assert str(item) in command.content
            else:
                assert str(require_value) in command.content


def test_review_contract_renderer_rejects_unknown_keys_inside_wrapped_payload() -> None:
    with pytest.raises(ValueError, match="Unknown review-contract field"):
        render_review_contract_prompt(
            {
                "review_contract": {
                    "schema_version": 1,
                    "review_mode": "review",
                    "legacy_note": "stale",
                }
            }
        )


def test_review_contract_renderer_rejects_frontmatter_wrapper_alias() -> None:
    with pytest.raises(ValueError, match="wrapper key 'review_contract'"):
        render_review_contract_prompt(
            {
                "review-contract": {
                    "schema_version": 1,
                    "review_mode": "review",
                }
            }
        )


def test_review_contract_renderer_rejects_unknown_nested_conditional_keys() -> None:
    with pytest.raises(
        ValueError, match=r"Unknown review-contract field\(s\): conditional_requirements\[0\]\.legacy_note"
    ):
        render_review_contract_prompt(
            {
                "schema_version": 1,
                "review_mode": "publication",
                "conditional_requirements": [
                    {
                        "when": "theorem-bearing claims are present",
                        "legacy_note": "stale",
                    }
                ],
            }
        )


def test_review_contract_renderer_rejects_invalid_conditional_when_and_empty_payload() -> None:
    with pytest.raises(ValueError, match=r"conditional_requirements\[0\]\.when must be one of:"):
        render_review_contract_prompt(
            {
                "schema_version": 1,
                "review_mode": "publication",
                "conditional_requirements": [
                    {
                        "when": "proof-bearing work is present",
                        "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                    }
                ],
            }
        )

    with pytest.raises(
        ValueError,
        match=r"conditional_requirements\[0\] must declare at least one of:",
    ):
        render_review_contract_prompt(
            {
                "schema_version": 1,
                "review_mode": "publication",
                "conditional_requirements": [{"when": "theorem-bearing claims are present"}],
            }
        )


def test_review_contract_renderer_rejects_conflicting_wrapper_aliases_when_secondary_is_malformed() -> None:
    with pytest.raises(ValueError, match="review contract must use only one wrapper key"):
        render_review_contract_prompt(
            {
                "review_contract": {
                    "schema_version": 1,
                    "review_mode": "review",
                },
                "review-contract": "oops",
            }
        )


def test_review_contract_visibility_note_surfaces_the_hard_constraints() -> None:
    note = review_contract_visibility_note()
    review_modes = " or ".join(f"`{value}`" for value in REVIEW_CONTRACT_MODES)
    conditional_whens = " or ".join(f"`{value}`" for value in REVIEW_CONTRACT_CONDITIONAL_WHENS)
    preflight_checks = " or ".join(f"`{value}`" for value in REVIEW_CONTRACT_PREFLIGHT_CHECKS)

    _assert_prompt_contracts(
        note,
        semantic_anchor(
            "review-contract note states closed-schema authoritative YAML semantics",
            (
                "Closed schema",
                "no extra keys",
                "closed review-contract vocabularies",
                "active YAML values below are authoritative",
            ),
        ),
        machine_exact(
            "review-contract note schema and list fields stay exact",
            (
                "`schema_version` must be the integer `1`;",
                "`required_outputs`",
                "`required_evidence`",
                "`blocking_conditions`",
                "`preflight_checks`",
                "`stage_artifacts`",
                "`scope_variants`",
                "`conditional_requirements[].preflight_checks`",
                "`conditional_requirements[].blocking_preflight_checks`",
                "`required_outputs_override`",
                "`required_evidence_override`",
                "`blocking_conditions_override`",
            ),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="review-contract field paths and integer schema version are machine-facing",
        ),
        semantic_anchor(
            "conditional preflight fields remain valid-check lists",
            "lists of valid preflight-check values when present",
        ),
    )
    assert review_modes not in note
    assert conditional_whens not in note
    assert preflight_checks not in note


@pytest.mark.parametrize(
    ("normalizer", "payload", "error_fragment"),
    [
        (
            normalize_review_contract_payload,
            {
                "schema_version": 1,
                "review_mode": "publication",
                "required_outputs": "GPD/review/PROOF-REDTEAM{round_suffix}.md",
            },
            "required_outputs must be a list of strings",
        ),
        (
            normalize_review_contract_frontmatter_payload,
            {
                "review-contract": {
                    "schema_version": 1,
                    "review_mode": "publication",
                    "preflight_checks": "manuscript",
                }
            },
            "preflight_checks must be a list of strings",
        ),
        (
            normalize_review_contract_payload,
            {
                "schema_version": 1,
                "review_mode": "publication",
                "conditional_requirements": [
                    {
                        "when": "theorem-bearing claims are present",
                        "required_outputs": "GPD/review/PROOF-REDTEAM{round_suffix}.md",
                    }
                ],
            },
            "conditional_requirements[0].required_outputs must be a list of strings",
        ),
    ],
)
def test_review_contract_normalizers_reject_singleton_string_list_fields(
    normalizer,
    payload: dict[str, object],
    error_fragment: str,
) -> None:
    with pytest.raises(ValueError, match=re.escape(error_fragment)):
        normalizer(payload)


def test_review_contract_payload_elides_blank_required_state() -> None:
    payload = review_contract_payload(
        {
            "schema_version": 1,
            "review_mode": "review",
            "required_state": " ",
        }
    )

    assert payload == {"schema_version": 1, "review_mode": "review"}


@pytest.mark.parametrize(
    ("normalizer", "payload", "error_fragment"),
    [
        (
            normalize_review_contract_payload,
            {
                "schema_version": 1,
                "review_mode": "publication",
                "required_outputs": [
                    "GPD/review/PROOF-REDTEAM{round_suffix}.md",
                    "GPD/review/PROOF-REDTEAM{round_suffix}.md",
                ],
            },
            "required_outputs must not contain duplicates",
        ),
        (
            normalize_review_contract_frontmatter_payload,
            {
                "review-contract": {
                    "schema_version": 1,
                    "review_mode": "publication",
                    "required_outputs": [
                        "GPD/review/PROOF-REDTEAM{round_suffix}.md",
                        "GPD/review/PROOF-REDTEAM{round_suffix}.md",
                    ],
                }
            },
            "required_outputs must not contain duplicates",
        ),
        (
            normalize_review_contract_payload,
            {
                "schema_version": 1,
                "review_mode": "publication",
                "preflight_checks": ["Manuscript", "manuscript"],
            },
            "preflight_checks must not contain duplicates",
        ),
        (
            normalize_review_contract_frontmatter_payload,
            {
                "review-contract": {
                    "schema_version": 1,
                    "review_mode": "publication",
                    "preflight_checks": ["Manuscript", "manuscript"],
                }
            },
            "preflight_checks must not contain duplicates",
        ),
    ],
)
def test_review_contract_normalizers_reject_duplicate_list_entries(
    normalizer,
    payload: dict[str, object],
    error_fragment: str,
) -> None:
    with pytest.raises(ValueError, match=re.escape(error_fragment)):
        normalizer(payload)


@pytest.mark.parametrize(
    ("normalizer", "payload", "error_fragment"),
    [
        (
            normalize_review_contract_payload,
            {
                "schema_version": 1,
                "review_mode": "publication",
                "required_outputs": ["GPD/review/STAGE-reader{round_suffix}.json"],
                "stage_artifacts": [
                    "GPD/review/STAGE-reader{round_suffix}.json",
                    "GPD/review/STAGE-legacy{round_suffix}.json",
                ],
            },
            "stage_artifacts must be covered by required_outputs: GPD/review/STAGE-legacy{round_suffix}.json",
        ),
        (
            normalize_review_contract_frontmatter_payload,
            {
                "review-contract": {
                    "schema_version": 1,
                    "review_mode": "publication",
                    "conditional_requirements": [
                        {
                            "when": "theorem-bearing claims are present",
                            "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                            "stage_artifacts": [
                                "GPD/review/PROOF-REDTEAM{round_suffix}.md",
                                "GPD/review/PROOF-LEGACY{round_suffix}.md",
                            ],
                        }
                    ],
                }
            },
            "conditional_requirements[0].stage_artifacts must be covered by "
            "conditional_requirements[0].required_outputs: GPD/review/PROOF-LEGACY{round_suffix}.md",
        ),
        (
            normalize_review_contract_payload,
            {
                "schema_version": 1,
                "review_mode": "publication",
                "required_outputs": ["GPD/review/STAGE-reader{round_suffix}.json"],
                "stage_artifacts": ["GPD/review/STAGE-reader{round_suffix}.json"],
                "scope_variants": [
                    {
                        "scope": "explicit_artifact",
                        "activation": "explicit artifact supplied",
                        "required_outputs_override": ["GPD/review/ARTIFACT-REPORT.md"],
                    }
                ],
            },
            "scope_variants[0].required_outputs_override must cover stage_artifacts: "
            "GPD/review/STAGE-reader{round_suffix}.json",
        ),
    ],
)
def test_review_contract_normalizers_reject_stage_artifact_output_drift(
    normalizer,
    payload: dict[str, object],
    error_fragment: str,
) -> None:
    with pytest.raises(ValueError, match=re.escape(error_fragment)):
        normalizer(payload)


def test_review_contract_prompt_and_registry_reject_stage_artifact_output_drift_consistently() -> None:
    payload = {
        "schema_version": 1,
        "review_mode": "publication",
        "required_outputs": ["GPD/review/STAGE-reader{round_suffix}.json"],
        "stage_artifacts": ["GPD/review/STAGE-legacy{round_suffix}.json"],
    }
    error_fragment = "stage_artifacts must be covered by required_outputs: GPD/review/STAGE-legacy{round_suffix}.json"

    with pytest.raises(ValueError, match=re.escape(error_fragment)):
        normalize_review_contract_payload(payload)
    with pytest.raises(ValueError, match=re.escape(error_fragment)):
        registry._parse_review_contract(payload, "gpd:test")


def test_review_contract_normalizer_canonicalizes_case_only_enum_drift() -> None:
    payload = {
        "schema_version": 1,
        "review_mode": "Publication",
        "preflight_checks": ["Manuscript", "Compiled_Manuscript"],
        "required_state": "PHASE_EXECUTED",
        "conditional_requirements": [
            {
                "when": "Theorem-Bearing Claims Are Present",
                "blocking_preflight_checks": ["Compiled_Manuscript"],
                "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            }
        ],
    }

    normalized = normalize_review_contract_payload(payload)
    parsed = registry._parse_review_contract(payload, "gpd:test")

    assert normalized["review_mode"] == "publication"
    assert normalized["preflight_checks"] == ["manuscript", "compiled_manuscript"]
    assert normalized["required_state"] == "phase_executed"
    assert normalized["conditional_requirements"] == [
        {
            "when": "theorem-bearing claims are present",
            "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            "required_evidence": [],
            "blocking_conditions": [],
            "preflight_checks": [],
            "blocking_preflight_checks": ["compiled_manuscript"],
            "stage_artifacts": [],
        }
    ]
    assert parsed is not None
    assert dataclasses.asdict(parsed) == normalized


@pytest.mark.parametrize(
    ("payload", "error_fragment"),
    [
        (
            {
                "schema_version": 1,
                "review_mode": "publication",
                "required_outputs": "GPD/REFEREE-REPORT{round_suffix}.md",
            },
            "required_outputs must be a list of strings",
        ),
        (
            {
                "schema_version": 1,
                "review_mode": "publication",
                "preflight_checks": "manuscript",
            },
            "preflight_checks must be a list of strings",
        ),
        (
            {
                "schema_version": 1,
                "review_mode": "publication",
                "conditional_requirements": [
                    {
                        "when": "theorem-bearing claims are present",
                        "required_outputs": "GPD/review/PROOF-REDTEAM{round_suffix}.md",
                    }
                ],
            },
            "conditional_requirements[0].required_outputs must be a list of strings",
        ),
    ],
)
def test_review_contract_prompt_and_registry_reject_singleton_string_list_fields_consistently(
    payload: dict[str, object], error_fragment: str
) -> None:
    with pytest.raises(ValueError, match=re.escape(error_fragment)):
        normalize_review_contract_payload(payload)
    with pytest.raises(ValueError, match=re.escape(error_fragment)):
        registry._parse_review_contract(payload, "gpd:test")


@pytest.mark.parametrize(
    ("normalizer", "payload"),
    [
        (
            normalize_review_contract_payload,
            {
                "schema_version": 1,
                "review_mode": "publication",
                "conditional_requirements": [
                    {
                        "when": "theorem-bearing claims are present",
                        "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                    },
                    {
                        "when": "theorem-bearing claims are present",
                        "required_evidence": ["duplicate activation clause"],
                    },
                ],
            },
        ),
        (
            normalize_review_contract_frontmatter_payload,
            {
                "review-contract": {
                    "schema_version": 1,
                    "review_mode": "publication",
                    "conditional_requirements": [
                        {
                            "when": "theorem-bearing claims are present",
                            "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                        },
                        {
                            "when": "theorem-bearing claims are present",
                            "required_evidence": ["duplicate activation clause"],
                        },
                    ],
                }
            },
        ),
    ],
)
def test_review_contract_normalizers_reject_duplicate_conditional_requirement_when(
    normalizer, payload: dict[str, object]
) -> None:
    with pytest.raises(
        ValueError,
        match=r"conditional_requirements\[1\]\.when duplicates conditional_requirements\[0\]\.when: theorem-bearing claims are present",
    ):
        normalizer(payload)


def test_review_contract_frontmatter_normalizer_rejects_prompt_wrapper_alias() -> None:
    with pytest.raises(ValueError, match="wrapper key 'review-contract'"):
        normalize_review_contract_frontmatter_payload(
            {
                "review_contract": {
                    "schema_version": 1,
                    "review_mode": "publication",
                }
            }
        )


@pytest.mark.parametrize(
    ("payload", "error_fragment"),
    [
        (
            {"schema_version": 1, "review_mode": "publication", "preflight_checks": ["legacy_gate"]},
            "preflight_checks",
        ),
        (
            {
                "schema_version": 1,
                "review_mode": "publication",
                "conditional_requirements": [{"when": "proof-bearing work is present"}],
            },
            "conditional_requirements[0].when",
        ),
    ],
)
def test_review_contract_prompt_and_registry_reject_the_same_invalid_payloads(
    payload: dict[str, object], error_fragment: str
) -> None:
    with pytest.raises(ValueError, match=re.escape(error_fragment)):
        normalize_review_contract_payload(payload)

    with pytest.raises(ValueError, match=re.escape(error_fragment)):
        registry._parse_review_contract(payload, "gpd:test")


def test_review_contract_renderer_rejects_incomplete_payloads() -> None:
    with pytest.raises(ValueError, match="review contract must set schema_version"):
        render_review_contract_prompt({"review_mode": "review"})


def test_review_contract_renderer_rejects_empty_wrapped_payloads() -> None:
    with pytest.raises(ValueError, match="review contract must set schema_version, review_mode"):
        render_review_contract_prompt({"review_contract": {}})


def test_review_contract_renderer_rejects_explicit_null_wrapped_payloads() -> None:
    with pytest.raises(ValueError, match="review contract must set schema_version, review_mode"):
        render_review_contract_prompt({"review_contract": None})


def test_review_contract_renderer_rejects_non_integer_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version must be the integer 1"):
        render_review_contract_prompt({"schema_version": "1", "review_mode": "review"})


def test_review_contract_renderer_rejects_unknown_review_mode() -> None:
    with pytest.raises(ValueError, match="review_mode must be one of: publication, review"):
        render_review_contract_prompt({"schema_version": 1, "review_mode": "publication-review"})


def test_review_contract_renderer_rejects_unknown_preflight_checks() -> None:
    with pytest.raises(ValueError, match="preflight_checks must contain only:"):
        render_review_contract_prompt(
            {
                "schema_version": 1,
                "review_mode": "review",
                "preflight_checks": ["compiled_manuscript", "legacy_gate"],
            }
        )


def test_review_contract_renderer_always_surfaces_blocking_preflight_dependency_rule() -> None:
    section = render_review_contract_prompt({"schema_version": 1, "review_mode": "review"})

    assert review_contract_visibility_note() in section
    _assert_review_contract_payload(
        section,
        {"schema_version": 1, "review_mode": "review"},
        omitted=(
            "preflight_checks",
            "required_outputs",
            "required_evidence",
            "blocking_conditions",
            "stage_artifacts",
            "conditional_requirements",
        ),
        context="minimal review contract",
    )
    machine_exact(
        "blocking preflight dependency field path stays exact",
        "`conditional_requirements[].blocking_preflight_checks`",
        owner=REVIEW_CONTRACT_OWNER,
        rationale="the renderer note exposes this exact nested field path",
    ).check(section)


def test_review_contract_renderer_accepts_conditional_only_blocking_preflight_checks() -> None:
    section = render_review_contract_prompt(
        {
            "schema_version": 1,
            "review_mode": "publication",
            "preflight_checks": ["manuscript"],
            "conditional_requirements": [
                {
                    "when": "theorem-bearing manuscripts are present",
                    "blocking_preflight_checks": ["manuscript_proof_review"],
                }
            ],
        }
    )

    _assert_review_contract_payload(
        section,
        {
            "schema_version": 1,
            "review_mode": "publication",
            "preflight_checks": ["manuscript"],
            "conditional_requirements": [
                {
                    "when": "theorem-bearing manuscripts are present",
                    "blocking_preflight_checks": ["manuscript_proof_review"],
                }
            ],
        },
        context="conditional-only blocking preflight review contract",
    )


def test_review_contract_renderer_accepts_publication_artifact_preflight_checks() -> None:
    section = render_review_contract_prompt(
        {
            "schema_version": 1,
            "review_mode": "publication",
            "preflight_checks": [
                "command_context",
                "verification_reports",
                "artifact_manifest",
                "bibliography_audit",
                "bibliography_audit_clean",
                "publication_blockers",
                "reproducibility_manifest",
                "reproducibility_ready",
            ],
        }
    )

    payload = _model_visible_wrapper_payload(
        section,
        "Review Contract",
        REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
        context="publication artifact preflight review contract",
    )
    assert payload["preflight_checks"] == [
        "command_context",
        "verification_reports",
        "artifact_manifest",
        "bibliography_audit",
        "bibliography_audit_clean",
        "publication_blockers",
        "reproducibility_manifest",
        "reproducibility_ready",
    ]


def test_render_agent_requirements_section_normalizes_public_inputs() -> None:
    section = registry.render_agent_requirements_section(
        tools=["file_read", "file_read", "file_write"],
        commit_authority="orchestrator",
        surface="internal",
        role_family="analysis",
        artifact_write_authority="scoped_write",
        shared_state_authority="return_only",
    )

    payload = _model_visible_payload(section, "Agent Requirements", context="normalized agent requirements")
    assert payload["tools"] == ["file_read", "file_write"]


def test_render_command_requires_section_normalizes_public_inputs() -> None:
    section = registry.render_command_requires_section(
        context_mode="project-required",
        project_reentry_capable=False,
        agent="gpd-planner",
        allowed_tools=["git", "git", "python"],
        requires={"files": ["PROJECT.md", "PROJECT.md"]},
        command_policy=None,
    )

    payload = _model_visible_payload(section, "Command Requirements", context="normalized command requirements")
    assert payload["allowed_tools"] == ["git", "python"]
    assert payload["requires"] == {"files": ["PROJECT.md"]}
    assert payload[COMMAND_POLICY_PROMPT_WRAPPER_KEY]["supporting_context_policy"] == {
        "project_context_mode": "project-required",
        "project_reentry_mode": "disallowed",
        "required_file_patterns": ["PROJECT.md"],
    }


def test_render_command_requires_section_accepts_explicit_command_policy_mapping() -> None:
    section = registry.render_command_requires_section(
        context_mode="project-aware",
        project_reentry_capable=False,
        agent=None,
        allowed_tools=[],
        requires={},
        command_policy={
            "schema_version": 1,
            "subject_policy": {
                "subject_kind": "publication",
                "resolution_mode": "explicit_or_project_manuscript",
                "allow_external_subjects": True,
            },
            "output_policy": {
                "output_mode": "managed",
                "managed_root_kind": "gpd_managed_durable",
            },
        },
    )

    assert _model_visible_payload(section, "Command Requirements", context="explicit command policy") == {
        "context_mode": "project-aware",
        "project_reentry_capable": False,
        COMMAND_POLICY_PROMPT_WRAPPER_KEY: {
            "schema_version": 1,
            "subject_policy": {
                "subject_kind": "publication",
                "resolution_mode": "explicit_or_project_manuscript",
                "allow_external_subjects": True,
            },
            "supporting_context_policy": {
                "project_context_mode": "project-aware",
                "project_reentry_mode": "disallowed",
            },
            "output_policy": {
                "output_mode": "managed",
                "managed_root_kind": "gpd_managed_durable",
            },
        },
    }


@pytest.mark.parametrize(
    ("kwargs", "error_fragment"),
    [
        (
            {
                "context_mode": "project-aware",
                "project_reentry_capable": True,
                "agent": None,
                "allowed_tools": [],
                "requires": {},
                "command_policy": None,
            },
            "requires context_mode 'project-required'",
        ),
        (
            {
                "context_mode": "project-required",
                "project_reentry_capable": False,
                "agent": "execute-phase",
                "allowed_tools": [],
                "requires": {},
                "command_policy": None,
            },
            "Unknown agent",
        ),
        (
            {
                "context_mode": "project-required",
                "project_reentry_capable": False,
                "agent": None,
                "allowed_tools": [],
                "requires": {"artifact_manifest": "required"},
                "command_policy": None,
            },
            "only supports files",
        ),
    ],
)
def test_render_command_requires_section_rejects_invalid_public_inputs(
    kwargs: dict[str, object],
    error_fragment: str,
) -> None:
    with pytest.raises(ValueError, match=re.escape(error_fragment)):
        registry.render_command_requires_section(**kwargs)


def test_render_agent_requirements_section_rejects_invalid_public_inputs() -> None:
    with pytest.raises(ValueError, match="Invalid role_family"):
        registry.render_agent_requirements_section(
            tools=["file_read"],
            commit_authority="orchestrator",
            surface="internal",
            role_family="planner",
            artifact_write_authority="scoped_write",
            shared_state_authority="return_only",
        )


def test_review_contract_renderer_rejects_invalid_required_state_field() -> None:
    with pytest.raises(ValueError, match="required_state must be one of: phase_executed"):
        render_review_contract_prompt(
            {
                "schema_version": 1,
                "review_mode": "review",
                "required_state": "phase_planned",
            }
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "stage_ids",
        "final_decision_output",
        "requires_fresh_context_per_stage",
        "max_review_rounds",
    ],
)
def test_review_contract_renderer_rejects_removed_dead_review_fields(field_name: str) -> None:
    with pytest.raises(ValueError, match=r"Unknown review-contract field\(s\):"):
        render_review_contract_prompt(
            {
                "schema_version": 1,
                "review_mode": "review",
                field_name: "legacy-value",
            }
        )


def test_review_contract_renderer_normalizes_blank_required_state() -> None:
    section = render_review_contract_prompt(
        {
            "schema_version": 1,
            "review_mode": "review",
            "required_state": "   ",
        }
    )

    payload = _assert_review_contract_payload(
        section,
        {"schema_version": 1, "review_mode": "review"},
        omitted=("required_state",),
        context="blank required-state review contract",
    )
    assert "required_state" not in payload


def test_review_contract_renderer_surfaces_required_state_constraint_in_note() -> None:
    section = render_review_contract_prompt(
        {
            "schema_version": 1,
            "review_mode": "review",
            "required_state": REVIEW_CONTRACT_REQUIRED_STATES[0],
        }
    )

    payload = _model_visible_wrapper_payload(
        section,
        "Review Contract",
        REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
        context="required-state review contract",
    )
    assert payload["required_state"] == "phase_executed"


def test_review_contract_renderer_rejects_non_list_and_non_mapping_conditional_shapes() -> None:
    with pytest.raises(ValueError, match="conditional_requirements must be a list of mappings"):
        render_review_contract_prompt(
            {
                "schema_version": 1,
                "review_mode": "publication",
                "conditional_requirements": True,
            }
        )

    with pytest.raises(ValueError, match=r"conditional_requirements\[0\] must be a mapping"):
        render_review_contract_prompt(
            {
                "schema_version": 1,
                "review_mode": "publication",
                "conditional_requirements": ["oops"],
            }
        )


def test_review_contract_renderer_fills_canonical_defaults_for_minimal_payload() -> None:
    section = render_review_contract_prompt({"schema_version": 1, "review_mode": "review"})

    _assert_review_contract_payload(
        section,
        {"schema_version": 1, "review_mode": "review"},
        omitted=(
            "required_outputs",
            "required_evidence",
            "blocking_conditions",
            "preflight_checks",
            "stage_artifacts",
            "conditional_requirements",
            "required_state",
            "stage_ids",
            "final_decision_output",
            "requires_fresh_context_per_stage",
            "max_review_rounds",
        ),
        context="minimal review contract defaults",
    )


def test_review_contract_renderer_renders_conditional_requirements() -> None:
    section = render_review_contract_prompt(
        {
            "schema_version": 1,
            "review_mode": "publication",
            "preflight_checks": ["manuscript_proof_review"],
            "conditional_requirements": [
                {
                    "when": "theorem-bearing claims are present",
                    "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                    "blocking_preflight_checks": ["manuscript_proof_review"],
                    "stage_artifacts": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                }
            ],
        }
    )

    _assert_review_contract_payload(
        section,
        {
            "schema_version": 1,
            "review_mode": "publication",
            "preflight_checks": ["manuscript_proof_review"],
            "conditional_requirements": [
                {
                    "when": "theorem-bearing claims are present",
                    "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                    "blocking_preflight_checks": ["manuscript_proof_review"],
                    "stage_artifacts": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
                }
            ],
        },
        context="conditional requirements review contract",
    )


def test_review_contract_renderer_renders_scope_variants() -> None:
    section = render_review_contract_prompt(
        {
            "schema_version": 1,
            "review_mode": "publication",
            "scope_variants": [
                {
                    "scope": "explicit_artifact",
                    "activation": "explicit manuscript path was supplied",
                    "relaxed_preflight_checks": ["manuscript"],
                    "optional_preflight_checks": ["bibliography_audit"],
                    "required_outputs_override": ["GPD/review/ARTIFACT-REPORT.md"],
                }
            ],
        }
    )

    _assert_review_contract_payload(
        section,
        {
            "schema_version": 1,
            "review_mode": "publication",
            "scope_variants": [
                {
                    "scope": "explicit_artifact",
                    "activation": "explicit manuscript path was supplied",
                    "relaxed_preflight_checks": ["manuscript"],
                    "optional_preflight_checks": ["bibliography_audit"],
                    "required_outputs_override": ["GPD/review/ARTIFACT-REPORT.md"],
                }
            ],
        },
        context="scope variants review contract",
    )


def test_publication_scope_variant_relaxed_and_optional_checks_have_preflight_detail_keys() -> None:
    from gpd.core.command_preflight import (
        _EXTERNAL_ARTIFACT_OPTIONAL_DETAILS,
        _WRITE_PAPER_EXTERNAL_AUTHORING_OPTIONAL_DETAILS,
    )

    preflight_detail_keys = set(_EXTERNAL_ARTIFACT_OPTIONAL_DETAILS) | set(
        _WRITE_PAPER_EXTERNAL_AUTHORING_OPTIONAL_DETAILS
    )
    missing_detail_keys: dict[str, list[str]] = {}
    for command_name in registry.list_review_commands():
        contract = registry.get_command(command_name).review_contract
        if contract is None or contract.review_mode != "publication":
            continue
        for variant in contract.scope_variants:
            variant_checks = set(variant.relaxed_preflight_checks) | set(variant.optional_preflight_checks)
            missing = sorted(variant_checks - preflight_detail_keys)
            if missing:
                missing_detail_keys[f"{command_name}:{variant.scope}"] = missing

    assert missing_detail_keys == {}


def test_review_contract_renderer_rejects_duplicate_scope_variants() -> None:
    with pytest.raises(
        ValueError,
        match=r"scope_variants\[1\]\.scope duplicates scope_variants\[0\]\.scope: explicit_artifact",
    ):
        render_review_contract_prompt(
            {
                "schema_version": 1,
                "review_mode": "publication",
                "scope_variants": [
                    {
                        "scope": "explicit_artifact",
                        "activation": "explicit manuscript path was supplied",
                        "required_outputs_override": ["GPD/review/ARTIFACT-REPORT.md"],
                    },
                    {
                        "scope": "explicit_artifact",
                        "activation": "same scope repeated",
                        "optional_preflight_checks": ["bibliography_audit"],
                    },
                ],
            }
        )


def test_peer_review_contract_surfaces_typed_conditional_proof_requirements() -> None:
    contract = registry.get_command("peer-review").review_contract

    assert contract is not None
    assert contract.conditional_requirements == [
        registry.ReviewContractConditionalRequirement(
            when="project-backed manuscript review",
            required_evidence=[
                "phase summaries or milestone digest",
                "verification reports",
                "manuscript-root bibliography audit",
                "manuscript-root artifact manifest",
                "manuscript-root reproducibility manifest",
                "manuscript-root publication artifacts",
            ],
            blocking_conditions=[
                "missing project state",
                "missing roadmap",
                "missing conventions",
                "no research artifacts",
            ],
            preflight_checks=[
                "project_state",
                "roadmap",
                "conventions",
                "research_artifacts",
                "verification_reports",
                "artifact_manifest",
                "bibliography_audit",
                "bibliography_audit_clean",
                "reproducibility_manifest",
                "reproducibility_ready",
            ],
            blocking_preflight_checks=[
                "project_state",
                "roadmap",
                "conventions",
                "research_artifacts",
                "verification_reports",
                "artifact_manifest",
                "bibliography_audit",
                "bibliography_audit_clean",
                "reproducibility_manifest",
                "reproducibility_ready",
            ],
        ),
        registry.ReviewContractConditionalRequirement(
            when="theorem-bearing claims are present",
            required_outputs=["${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md"],
            stage_artifacts=["${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md"],
        ),
    ]
    source = _read_command("peer-review")
    _assert_prompt_contracts(
        source,
        machine_exact(
            "peer-review conditional source keys stay exact",
            ("conditional_requirements:", "when: project-backed manuscript review"),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="review-contract conditional frontmatter keys and structured route labels are parsed literally",
        ),
        *semantic_concept(
            "theorem-bearing peer-review conditional remains visible in source",
            required=("when:", "theorem-bearing", "claims"),
        ),
    )


def test_verify_work_review_contract_uses_phase_scoped_output_path() -> None:
    contract = registry.get_command("verify-work").review_contract

    assert contract is not None
    assert contract.required_outputs == ["GPD/phases/XX-name/XX-VERIFICATION.md"]
    assert "GPD/phases/XX-name/XX-VERIFICATION.md" in _read_command("verify-work")


def test_respond_to_referees_review_contract_uses_round_suffixed_output_paths() -> None:
    contract = registry.get_command("respond-to-referees").review_contract

    assert contract is not None
    assert contract.required_outputs == [
        "GPD/review/REFEREE_RESPONSE{round_suffix}.md",
        "GPD/AUTHOR-RESPONSE{round_suffix}.md",
    ]
    assert contract.scope_variants == [
        registry.ReviewContractScopeVariant(
            scope="managed_publication_subject",
            activation="manuscript subject under `GPD/publication/{subject_slug}/manuscript`",
            required_outputs_override=[
                "GPD/publication/{subject_slug}/review/REFEREE_RESPONSE{round_suffix}.md",
                "GPD/publication/{subject_slug}/AUTHOR-RESPONSE{round_suffix}.md",
            ],
        ),
        registry.ReviewContractScopeVariant(
            scope="explicit_external_manuscript",
            activation="explicit `--manuscript` subject outside the current project's canonical manuscript roots",
            relaxed_preflight_checks=["project_state", "conventions"],
            required_outputs_override=[
                "GPD/publication/{subject_slug}/review/REFEREE_RESPONSE{round_suffix}.md",
                "GPD/publication/{subject_slug}/AUTHOR-RESPONSE{round_suffix}.md",
            ],
            required_evidence_override=["explicit manuscript subject", "one or more referee report sources"],
            blocking_conditions_override=[
                "missing manuscript subject",
                "missing referee report source",
                "degraded review integrity",
            ],
        ),
    ]
    respond_command = _read_command("respond-to-referees")
    respond_workflow = _read_workflow("respond-to-referees")
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in respond_command
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in respond_command
    assert "scope_variants:" in respond_command
    assert "scope: managed_publication_subject" in respond_command
    assert "scope: explicit_external_manuscript" in respond_command
    assert "templates/paper/author-response.md" in respond_workflow
    assert "needs-calculation" in respond_workflow


def test_respond_to_referees_command_policy_surfaces_explicit_manuscript_and_report_inputs() -> None:
    command = registry.get_command("respond-to-referees")

    assert command.context_mode == "project-aware"
    assert command.command_policy == registry.CommandPolicy(
        schema_version=1,
        subject_policy=registry.CommandSubjectPolicy(
            subject_kind="publication",
            resolution_mode="explicit_or_project_manuscript",
            explicit_input_kinds=["manuscript_path", "referee_report_path", "paste_referee_report"],
            allow_external_subjects=True,
            supported_roots=["paper", "manuscript", "draft"],
            allowed_suffixes=[".tex", ".md"],
        ),
        supporting_context_policy=registry.CommandSupportingContextPolicy(
            project_context_mode="project-aware",
            project_reentry_mode="disallowed",
        ),
        output_policy=registry.CommandOutputPolicy(
            output_mode="managed",
            managed_root_kind="gpd_managed_durable",
            default_output_subtree="GPD",
        ),
    )


def test_respond_to_referees_response_authoring_keeps_evidence_bodies_until_issue_hydration_exists() -> None:
    staging = registry.get_command("respond-to-referees").staged_loading

    assert staging is not None
    revision_planning = staging.stage("revision_planning")
    response_authoring = staging.stage("response_authoring")

    assert "reference_artifacts_content" not in revision_planning.required_init_fields
    assert "active_reference_context" not in revision_planning.required_init_fields
    assert "protocol_bundle_context" not in revision_planning.required_init_fields
    assert "reference_artifacts_content" in response_authoring.required_init_fields
    assert "active_reference_context" in response_authoring.required_init_fields
    assert "protocol_bundle_context" in response_authoring.required_init_fields
    for field_name in (
        "selected_publication_root",
        "selected_review_root",
        "latest_review_round",
        "latest_review_ledger",
        "latest_referee_decision",
        "latest_referee_report_md",
        "latest_author_response",
        "latest_referee_response",
    ):
        assert field_name in response_authoring.required_init_fields

    response_workflow = _read_workflow("respond-to-referees")
    semantic_anchor(
        "response authoring only uses hydrated bodies for selected evidence comments",
        ("Use hydrated bodies only", "selected evidence-dependent comments"),
    ).check(response_workflow)


def test_write_paper_review_contract_uses_round_suffixed_referee_outputs() -> None:
    contract = registry.get_command("write-paper").review_contract

    assert contract is not None
    assert contract.required_outputs == [
        "${PAPER_DIR}/{topic_specific_stem}.tex",
        "${PAPER_DIR}/PAPER-CONFIG.json",
        "${PAPER_DIR}/ARTIFACT-MANIFEST.json",
        "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json",
        "${PAPER_DIR}/reproducibility-manifest.json",
        "GPD/review/REVIEW-LEDGER{round_suffix}.json",
        "GPD/review/REFEREE-DECISION{round_suffix}.json",
        "GPD/REFEREE-REPORT{round_suffix}.md",
        "GPD/REFEREE-REPORT{round_suffix}.tex",
    ]
    write_command = _read_command("write-paper")
    write_workflow = workflow_authority_text(WORKFLOWS_DIR, "write-paper")
    author_response = (TEMPLATES_DIR / "paper" / "author-response.md").read_text(encoding="utf-8")
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in write_command
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in write_command
    assert "templates/paper/author-response.md" in write_workflow
    assert "needs-calculation" in author_response


def test_author_response_template_is_canonical_and_mentions_new_calculation_tracking() -> None:
    author_response = (TEMPLATES_DIR / "paper" / "author-response.md").read_text(encoding="utf-8")
    referee_response = (TEMPLATES_DIR / "paper" / "referee-response.md").read_text(encoding="utf-8")
    writer = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")

    assert "issues_needing_calculation" in author_response
    assert "needs-calculation" in author_response
    _assert_prompt_contracts(
        author_response,
        *semantic_concept(
            "author response tracks source phase for new work",
            required=("source phase", "new work"),
        ),
    )
    assert "templates/paper/author-response.md" in referee_response
    assert "needs-calculation" in referee_response
    assert "templates/paper/author-response.md" in writer
    assert "{GPD_INSTALL_DIR}/templates/paper/author-response.md" in writer
    assert "@{GPD_INSTALL_DIR}/templates/paper/author-response.md" not in writer
    assert "needs-calculation" in writer


def test_referee_response_template_reuses_canonical_issue_fields_in_worked_sections() -> None:
    referee_response = (TEMPLATES_DIR / "paper" / "referee-response.md").read_text(encoding="utf-8")
    ref_002 = referee_response.split("### REF-002", 1)[1].split("### REF-003", 1)[0]
    ref_101 = referee_response.split("### REF-101", 1)[1].split("### REF-102", 1)[0]

    for section in (ref_002, ref_101):
        assert "**Classification:**" in section
        assert "**Blocking issue:**" in section
        assert "**Decision-artifact context:**" in section
        _assert_prompt_contracts(
            section,
            *semantic_concept(
                "referee response issue section keeps source phase field",
                required=("source phase", "new work"),
            ),
        )
        assert "**Category:**" not in section


def test_write_paper_review_contract_surfaces_manuscript_root_review_dependencies() -> None:
    source = _read_command("write-paper")

    _assert_prompt_contracts(
        source,
        machine_exact(
            "write-paper review artifact paths stay exact",
            (
                "${PAPER_DIR}/ARTIFACT-MANIFEST.json",
                "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json",
                "${PAPER_DIR}/reproducibility-manifest.json",
            ),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="review-contract preflight artifact paths are machine-visible shell/path contracts",
        ),
        semantic_anchor(
            "stale stage-review prose stays absent",
            "stage review artifacts",
            mode=FragmentMode.ABSENT,
        ),
    )


def test_summary_template_surfaces_plan_contract_ref_rule_for_contract_ledgers() -> None:
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")

    _assert_prompt_contracts(
        summary_template,
        semantic_anchor(
            "summary template points to one canonical contract-ledger rule source",
            ("single detailed rule source", "canonical schema", "exact list-trimming semantics"),
        ),
        machine_exact(
            "summary contract-ledger keys stay exact",
            ("plan_contract_ref", "contract_results", "comparison_verdicts", "uncertainty_markers"),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="summary frontmatter contract-ledger keys are parsed machine fields",
        ),
        machine_exact(
            "summary suggested checks key stays exact",
            "suggested_contract_checks",
            owner=REVIEW_CONTRACT_OWNER,
            rationale="verification suggested-check records use this exact key",
        ),
    )
    semantic_anchor(
        "contract-results schema keeps trimmed-list validity semantics",
        ("Blank-after-trim entries are invalid", "duplicate-after-trim entries are invalid"),
    ).check(contract_results_schema)


def test_verification_template_forbids_placeholder_uncertainty_fillers() -> None:
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    _assert_prompt_contracts(
        verification_template,
        semantic_anchor(
            "verification report preserves explicit uncertainty and suggested checks",
            (
                "decisive readout",
                "contract-backed ledger",
                "Keep `uncertainty_markers` explicit",
                "structured `suggested_contract_checks`",
            ),
        ),
        semantic_anchor(
            "placeholder uncertainty filler stays forbidden",
            "filler placeholders",
            mode=FragmentMode.ABSENT,
        ),
    )


def test_verification_template_surfaces_strict_passed_and_blocked_semantics() -> None:
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    _assert_prompt_contracts(
        verification_template,
        machine_exact(
            "verification template status and schema keys stay exact",
            (
                "status: passed`",
                "`gaps_found`",
                "`expert_needed`",
                "`human_needed`",
                "`contract_results`",
                "`{GPD_INSTALL_DIR}/templates/contract-results-schema.md`",
                "`suggested_contract_checks`",
            ),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="contract-result statuses, keys, and schema path are machine/public contracts",
        ),
        semantic_anchor(
            "verification template keeps decisive and proof-audit semantics",
            (
                "strict",
                "every required decisive comparison is decisive",
                "canonical contract-result status vocabulary",
                "apply it literally",
                "instead of padding prose",
                "Proof-backed claims",
                "proof-audit rules",
                "canonical schema",
            ),
        ),
    )


def test_research_verification_template_surfaces_non_empty_uncertainty_markers() -> None:
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")

    _assert_prompt_contracts(
        research_verification,
        machine_exact(
            "research verification template schema path and enum examples stay exact",
            (
                "`{GPD_INSTALL_DIR}/templates/verification-report.md`",
                "comparison_kind: benchmark",
                "Allowed body enum values:",
                "`comparison_kind`: benchmark|prior_work|experiment|cross_method|baseline|other",
            ),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="verification schema path and enum examples are machine-visible contract guidance",
        ),
        semantic_anchor(
            "research verification suggested checks stay on canonical schema surface",
            ("canonical verification frontmatter contract", "`suggested_contract_checks`", "canonical schema surface"),
        ),
    )
    assert (
        "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]"
        not in research_verification
    )
    assert (
        'comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other | ""]'
        not in research_verification
    )
    assert 'comparison_kind: "benchmark"' in research_verification
    assert (
        'comparison_kind: "benchmark | prior_work | experiment | cross_method | baseline | other"'
        not in research_verification
    )
    _assert_prompt_contracts(
        research_verification,
        semantic_anchor(
            "blank comparison placeholders are omitted",
            ("omit both `comparison_kind` and `comparison_reference_id`", "blank placeholders"),
        ),
        machine_exact(
            "uncertainty marker example keys stay exact",
            ("uncertainty_markers:", "weakest_anchors: [anchor-1]", "disconfirming_observations: [observation-1]"),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="frontmatter uncertainty marker keys and examples are parsed schema guidance",
        ),
    )


def test_write_paper_prompt_discovers_plan_scoped_phase_summaries() -> None:
    source = _read_workflow("write-paper")

    assert "GPD/phases/*/*SUMMARY.md" in source
    semantic_anchor(
        "write-paper reads canonical summary artifacts",
        ("summary artifacts", "`SUMMARY.md`", "`*-SUMMARY.md`"),
    ).check(source)


def test_write_paper_prompt_loads_figure_tracker_schema_before_updating_tracker() -> None:
    source = _read_workflow("write-paper")
    staging = registry.get_command("write-paper").staged_loading

    assert staging is not None

    assert "{GPD_INSTALL_DIR}/templates/paper/figure-tracker.md" in source
    assert "${PAPER_DIR}/FIGURE_TRACKER.md" in source
    assert (
        "references/shared/canonical-schema-discipline.md"
        in staging.stage("figure_and_section_authoring").loaded_authorities
    )


def test_write_paper_stage_visibility_delays_publication_review_schemas_until_their_stage() -> None:
    staging = registry.get_command("write-paper").staged_loading

    assert staging is not None
    assert staging.stage_ids() == (
        "paper_bootstrap",
        "outline_and_scaffold",
        "figure_and_section_authoring",
        "consistency_and_references",
        "publication_review",
    )

    bootstrap = staging.stage("paper_bootstrap")
    outline = staging.stage("outline_and_scaffold")
    figures = staging.stage("figure_and_section_authoring")
    consistency = staging.stage("consistency_and_references")
    review = staging.stage("publication_review")

    assert bootstrap.loaded_authorities == (
        "workflows/write-paper/paper-bootstrap.md",
        "references/publication/publication-bootstrap-preflight.md",
        "templates/paper/publication-manuscript-root-preflight.md",
    )
    outline_conditionals = {
        conditional.when: conditional.authorities for conditional in outline.conditional_authorities
    }
    assert outline_conditionals == {
        "publication_lane_or_builder_config_selection": ("references/publication/publication-pipeline-modes.md",),
        "paper_builder_config_or_artifact_manifest_write": (
            "templates/paper/paper-config-schema.md",
            "templates/paper/artifact-manifest-schema.md",
        ),
    }
    assert "templates/paper/paper-config-schema.md" in outline.must_not_eager_load
    assert "templates/paper/artifact-manifest-schema.md" in outline.must_not_eager_load
    assert "templates/paper/bibliography-audit-schema.md" not in outline.loaded_authorities
    assert "templates/paper/review-ledger-schema.md" not in outline.loaded_authorities
    assert "templates/paper/referee-decision-schema.md" not in outline.loaded_authorities
    assert "templates/paper/figure-tracker.md" in figures.loaded_authorities
    assert "references/shared/canonical-schema-discipline.md" in figures.loaded_authorities
    assert "templates/paper/bibliography-audit-schema.md" in consistency.loaded_authorities
    assert "templates/paper/reproducibility-manifest.md" in consistency.loaded_authorities
    assert "templates/paper/figure-tracker.md" not in consistency.loaded_authorities
    assert "references/publication/publication-review-round-artifacts.md" in review.loaded_authorities
    assert "references/publication/peer-review-panel.md" in review.must_not_eager_load
    assert "references/publication/peer-review-reliability.md" in review.must_not_eager_load
    assert "templates/paper/review-ledger-schema.md" in review.must_not_eager_load
    assert "templates/paper/referee-decision-schema.md" in review.must_not_eager_load
    assert "templates/paper/paper-config-schema.md" not in review.loaded_authorities
    assert "templates/paper/artifact-manifest-schema.md" not in review.loaded_authorities
    assert "templates/paper/figure-tracker.md" not in review.loaded_authorities
    assert "templates/paper/reproducibility-manifest.md" not in review.loaded_authorities


def test_comparison_templates_match_full_comparison_verdict_subject_kind_enum() -> None:
    internal = (TEMPLATES_DIR / "paper" / "internal-comparison.md").read_text(encoding="utf-8")
    experimental = (TEMPLATES_DIR / "paper" / "experimental-comparison.md").read_text(encoding="utf-8")
    contract_results = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")

    assert "subject_kind: claim|deliverable|acceptance_test|reference" not in internal
    assert "subject_kind: claim|deliverable|acceptance_test|reference" not in experimental
    assert "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other" not in internal
    assert "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other" not in experimental
    assert "subject_kind: claim" in internal
    assert "subject_kind: claim" in experimental
    assert "comparison_kind: cross_method" in internal
    assert "comparison_kind: experiment" in experimental
    assert "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other" in contract_results
    assert "uncertainty_markers:" in contract_results
    assert "weakest_anchors: [anchor-1]" in contract_results
    assert "disconfirming_observations: [observation-1]" in contract_results
    for comparison_template in (internal, experimental):
        _assert_prompt_contracts(
            comparison_template,
            machine_exact(
                "decisive subject role literal stays exact",
                "`subject_role: decisive`",
                owner=REVIEW_CONTRACT_OWNER,
                rationale="comparison verdict templates use this literal schema example",
            ),
            *semantic_concept(
                "decisive subject role closure rule remains visible",
                required=("only", "closes", "decisive requirement"),
            ),
        )
    assert (
        "Must be the canonical project-root-relative `GPD/phases/XX-name/XX-YY-PLAN.md#/contract` path"
        in contract_results
    )


def test_contract_ledgers_surface_decisive_only_verdict_rules_and_strict_suggested_check_keys() -> None:
    contract_results = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    _assert_prompt_contracts(
        contract_results,
        machine_exact(
            "contract-results verdict keys and path shape stay exact",
            (
                "`artifact`",
                "`other`",
                "`subject_role: decisive`",
                "`subject_role`",
                "`GPD/phases/XX-name/XX-YY-PLAN.md#/contract`",
                "`reference_id`",
                "`kind: benchmark`",
                "`kind: cross_method`",
                "`contract_results`",
                "uncertainty_markers:",
                "weakest_anchors: [anchor-1]",
                "disconfirming_observations: [observation-1]",
                "`check_id`",
                "`check_key`",
                "`gpd --raw verify suggest-checks --contract <file|-> --project-dir DIR`",
                "`check`",
            ),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="contract-results frontmatter keys, path template, and enum examples are parsed contracts",
        ),
        semantic_anchor(
            "contract results require decisive verdicts and strict suggested-check keys",
            (
                "Do not invent",
                "required decisive comparison",
                "explicit on every verdict",
                "decisive external anchor",
                "reference-backed decisive comparison is required",
                "closed schema",
                "fail validation",
            ),
        ),
    )
    machine_exact(
        "verification template contract-ledger keys stay exact",
        ("comparison_verdicts", "suggested_contract_checks"),
        owner=REVIEW_CONTRACT_OWNER,
        rationale="verification frontmatter uses these exact contract-ledger keys",
    ).check(verification_template)


def test_contract_ledgers_surface_forbidden_proxy_bindings_and_action_vocabulary() -> None:
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    contract_results = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    state_schema = (TEMPLATES_DIR / "state-json-schema.md").read_text(encoding="utf-8")
    project_contract_schema = (TEMPLATES_DIR / "project-contract-schema.md").read_text(encoding="utf-8")
    grounding_linkage = (TEMPLATES_DIR / "project-contract-grounding-linkage.md").read_text(encoding="utf-8")

    semantic_anchor(
        "summary template has one detailed contract-ledger source",
        ("single detailed rule source", "non-canonical frontmatter aliases"),
    ).check(summary_template.lower())
    machine_exact(
        "summary contract-ledger keys stay exact",
        ("contract_results", "comparison_verdicts"),
        owner=REVIEW_CONTRACT_OWNER,
        rationale="summary frontmatter uses these exact contract-ledger keys",
    ).check(summary_template)
    _assert_prompt_contracts(
        contract_results,
        machine_exact(
            "contract-results proxy/action/uncertainty keys stay exact",
            (
                "forbidden_proxy_id",
                "closed action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`",
                "weakest_anchors: [anchor-1]",
                "disconfirming_observations: [observation-1]",
            ),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="contract-results schema keys, action enum, and examples are machine-facing",
        ),
        semantic_anchor(
            "contract-results schema keeps trimmed-list validity semantics",
            ("Blank-after-trim entries are invalid", "duplicate-after-trim entries are invalid"),
        ),
    )
    machine_exact(
        "project-contract schema authority path and uncertainty fields stay exact",
        (
            "@{GPD_INSTALL_DIR}/templates/project-contract-schema.md",
            "uncertainty_markers.weakest_anchors",
            "uncertainty_markers.disconfirming_observations",
        ),
        owner=REVIEW_CONTRACT_OWNER,
        rationale="state/project-contract templates surface these exact schema paths and fields",
    ).check(state_schema + "\n" + project_contract_schema)
    semantic_anchor(
        "grounding linkage resolves prior outputs against concrete project roots",
        (
            "`must_include_prior_outputs[]`",
            "explicit project-artifact paths",
            "current project root",
            "`project_root` is unavailable",
            "non-grounding",
            "concrete root",
        ),
    ).check(grounding_linkage)
    assert '"must_include_prior_outputs": ["GPD/phases/00-baseline/00-01-SUMMARY.md"]' in project_contract_schema
    assert "`GPD/phases/.../*-SUMMARY.md`" not in project_contract_schema
    assert "`GPD/phases/.../SUMMARY.md`" not in project_contract_schema


def test_prompt_visible_contracts_surface_literal_boolean_requirements() -> None:
    plan_schema = expand_at_includes(
        (TEMPLATES_DIR / "plan-contract-schema.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd/specs",
        "/runtime/",
    )
    review_reader = (AGENTS_DIR / "gpd-review-reader.md").read_text(encoding="utf-8")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")

    machine_exact(
        "plan contract proof boolean literals stay exact",
        ("`required_in_proof`", "`true`", "`false`", '"yes"', '"no"'),
        owner=REVIEW_CONTRACT_OWNER,
        rationale="plan-contract proof boolean guidance must reject string synonyms",
    ).check(plan_schema)
    machine_exact(
        "review reader panel path stays exact",
        "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md",
        owner=REVIEW_CONTRACT_OWNER,
        rationale="review reader loads this exact publication panel reference",
    ).check(review_reader)
    semantic_anchor(
        "review reader identifies the canonical review contract source",
        ("shared source of truth", "`ClaimIndex`", "`StageReviewReport` contracts"),
    ).check(review_reader)
    machine_exact(
        "panel finding blocking boolean literal stays exact",
        ("`blocking`", "`true`", "`false`", '"yes"', '"no"'),
        owner=REVIEW_CONTRACT_OWNER,
        rationale="stage-review findings must use literal JSON booleans, not string synonyms",
    ).check(panel)


def test_referee_schema_and_panel_surface_strict_stage_artifact_naming_and_round_suffix_rules() -> None:
    referee_schema = (TEMPLATES_DIR / "paper" / "referee-decision-schema.md").read_text(encoding="utf-8")
    review_ledger_schema = (TEMPLATES_DIR / "paper" / "review-ledger-schema.md").read_text(encoding="utf-8")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")
    review_math = (AGENTS_DIR / "gpd-review-math.md").read_text(encoding="utf-8")

    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in referee_schema
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in referee_schema
    assert "REVIEW-LEDGER{round_suffix}.json" in referee_schema
    assert "STAGE-(reader|literature|math|physics|interestingness)(-R<round>)?.json" in referee_schema
    assert "same optional `-R<round>` suffix" in referee_schema
    assert "`{round_suffix}` in path examples means empty for initial review and `-R<round>`" in referee_schema
    assert "proof_audit_coverage_complete" in referee_schema
    assert "theorem_proof_alignment_adequate" in referee_schema
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in review_ledger_schema
    assert "`manuscript_path` must be non-empty" in review_ledger_schema
    assert "REFEREE-DECISION{round_suffix}.json" in review_ledger_schema
    assert "${REVIEW_ROOT}/CLAIMS{round_suffix}.json" in panel
    assert "${REVIEW_ROOT}/STAGE-reader{round_suffix}.json" in panel
    assert "proof_audits" in panel
    assert "theorem_assumptions" in panel
    assert "theorem_parameters" in panel
    _assert_prompt_contracts(
        panel,
        machine_exact(
            "strict stage specialist artifact names stay exact",
            (
                "`STAGE-reader`",
                "`STAGE-literature`",
                "`STAGE-math`",
                "`STAGE-physics`",
                "`STAGE-interestingness`",
                "`-R<round>`",
            ),
            owner=REVIEW_CONTRACT_OWNER,
            rationale="strict stage-review artifact names and round suffix tokens are machine-visible contracts",
        ),
        *semantic_concept(
            "strict stage artifact naming rule remains visible",
            required=("strict-stage specialist artifacts", "canonical names", "same optional", "suffix"),
        ),
    )
    for source in (panel, review_math):
        semantic_anchor(
            "theorem-bearing Stage 1 claims require review and proof audit",
            ("theorem-bearing Stage 1 claim", "reviewed", "proof-audited"),
        ).check(source)


def test_executor_completion_reference_requires_loading_contract_schema_before_summary_frontmatter() -> None:
    completion = (REFERENCES_DIR / "execution" / "executor-completion.md").read_text(encoding="utf-8")

    assert "Canonical ledger schema to load before writing SUMMARY frontmatter:" in completion
    assert "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md" in completion
