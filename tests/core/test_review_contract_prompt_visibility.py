from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from gpd import registry
from gpd.core.model_visible_text import command_visibility_note, review_contract_visibility_note
from gpd.core.review_contract_prompt import (
    VALID_REVIEW_CONDITIONAL_WHENS,
    normalize_review_contract_frontmatter_payload,
    normalize_review_contract_payload,
    render_review_contract_prompt,
    review_contract_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"


def _read_command(name: str) -> str:
    return Path(registry.get_command(name).path).read_text(encoding="utf-8")


def _read_workflow(name: str) -> str:
    return (WORKFLOWS_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_review_grade_commands_surface_registry_contract_requirements_in_source() -> None:
    for command_name in registry.list_review_commands():
        source = _read_command(command_name)
        command = registry.get_command(command_name)
        contract = command.review_contract

        assert contract is not None
        assert "review-contract:" in source
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


def test_peer_review_workflow_keeps_contract_gate_prose_concise() -> None:
    workflow = _read_workflow("peer-review")
    assert "project_contract_gate.authoritative" in workflow
    assert "effective_reference_intake" in workflow
    assert "Bundle guidance is additive only" in workflow
    assert "Reader-visible claims and surfaced evidence remain first-class" in workflow
    assert "Apply the gate rule above." not in workflow


def test_review_grade_commands_prepend_model_visible_review_contract_to_registry_content() -> None:
    for command_name in registry.list_review_commands():
        command = registry.get_command(command_name)
        contract = command.review_contract

        assert contract is not None
        expected_section = render_review_contract_prompt(review_contract_payload(contract))
        assert command.content.startswith("## Command Requirements\n")
        assert "## Command Requirements" in command.content
        assert command_visibility_note() in command.content
        if command.requires:
            assert "requires:" in command.content
        assert "## Review Contract" in command.content
        assert expected_section in command.content
        assert "review_contract:" in command.content
        assert review_contract_visibility_note() in expected_section
        assert f"review_mode: {contract.review_mode}" in expected_section
        for output in contract.required_outputs:
            assert output in expected_section
        for artifact in contract.stage_artifacts:
            assert artifact in expected_section
        for conditional in contract.conditional_requirements:
            assert conditional.when in expected_section
            for output in conditional.required_outputs:
                assert output in expected_section
            for evidence in conditional.required_evidence:
                assert evidence in expected_section
            for blocker in conditional.blocking_conditions:
                assert blocker in expected_section
            for artifact in conditional.stage_artifacts:
                assert artifact in expected_section
        if command.requires:
            for require_key, require_value in command.requires.items():
                assert str(require_key) in command.content
                if isinstance(require_value, list):
                    for item in require_value:
                        assert str(item) in command.content
                else:
                    assert str(require_value) in command.content


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
    with pytest.raises(ValueError, match=r"Unknown review-contract field\(s\): conditional_requirements\[0\]\.legacy_note"):
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


def test_review_contract_normalizer_accepts_singleton_string_list_fields() -> None:
    payload = normalize_review_contract_payload(
        {
            "schema_version": 1,
            "review_mode": "publication",
            "required_outputs": "GPD/review/PROOF-REDTEAM{round_suffix}.md",
            "preflight_checks": "manuscript",
            "conditional_requirements": [
                {
                    "when": "theorem-bearing claims are present",
                    "required_outputs": "GPD/review/PROOF-REDTEAM{round_suffix}.md",
                }
            ],
        }
    )

    assert payload["required_outputs"] == ["GPD/review/PROOF-REDTEAM{round_suffix}.md"]
    assert payload["preflight_checks"] == ["manuscript"]
    assert payload["conditional_requirements"] == [
        {
            "when": "theorem-bearing claims are present",
            "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            "required_evidence": [],
            "blocking_conditions": [],
            "blocking_preflight_checks": [],
            "stage_artifacts": [],
        }
    ]


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
                "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md", "GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            },
            "required_outputs must not contain duplicates",
        ),
        (
            normalize_review_contract_frontmatter_payload,
            {
                "review-contract": {
                    "schema_version": 1,
                    "review_mode": "publication",
                    "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md", "GPD/review/PROOF-REDTEAM{round_suffix}.md"],
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
                "required_outputs": "GPD/review/PROOF-REDTEAM{round_suffix}.md",
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
            "blocking_preflight_checks": ["compiled_manuscript"],
            "stage_artifacts": [],
        }
    ]
    assert parsed is not None
    assert dataclasses.asdict(parsed) == normalized


def test_review_contract_prompt_and_registry_share_singleton_string_list_normalization() -> None:
    payload = {
        "schema_version": 1,
        "review_mode": "publication",
        "required_outputs": "GPD/REFEREE-REPORT{round_suffix}.md",
        "preflight_checks": "manuscript",
        "conditional_requirements": [
            {
                "when": "theorem-bearing claims are present",
                "required_outputs": "GPD/review/PROOF-REDTEAM{round_suffix}.md",
            }
        ],
    }

    normalized = normalize_review_contract_payload(payload)
    parsed = registry._parse_review_contract(payload, "gpd:test")

    assert parsed is not None
    assert dataclasses.asdict(parsed) == normalized


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

    assert "`preflight_checks`=`" in section
    assert f"`conditional_requirements[].when`={'|'.join(VALID_REVIEW_CONDITIONAL_WHENS)}" in section
    assert (
        "`conditional_requirements[].blocking_preflight_checks` must reuse declared `preflight_checks` values."
        in section
    )


def test_review_contract_renderer_rejects_conditional_blocking_preflight_checks_not_declared_top_level() -> None:
    with pytest.raises(
        ValueError,
        match=(
            r"conditional_requirements\[0\]\.blocking_preflight_checks must also appear in preflight_checks: "
            r"manuscript_proof_review"
        ),
    ):
        render_review_contract_prompt(
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

    assert "command_context" in section
    assert "verification_reports" in section
    assert "artifact_manifest" in section
    assert "bibliography_audit" in section
    assert "bibliography_audit_clean" in section
    assert "publication_blockers" in section
    assert "reproducibility_manifest" in section
    assert "reproducibility_ready" in section


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

    assert "required_state: ''" not in section


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

    assert "required_outputs: []" in section
    assert "required_evidence: []" in section
    assert "blocking_conditions: []" in section
    assert "preflight_checks: []" in section
    assert "stage_artifacts: []" in section
    assert "conditional_requirements: []" in section
    assert "required_state: ''" not in section
    assert "stage_ids" not in section
    assert "final_decision_output" not in section
    assert "requires_fresh_context_per_stage" not in section
    assert "max_review_rounds" not in section


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

    assert "conditional_requirements:" in section
    assert "- when: theorem-bearing claims are present" in section
    assert "required_outputs:" in section
    assert "blocking_preflight_checks:" in section
    assert "stage_artifacts:" in section
    assert "GPD/review/PROOF-REDTEAM{round_suffix}.md" in section


def test_peer_review_contract_surfaces_typed_conditional_proof_requirements() -> None:
    contract = registry.get_command("peer-review").review_contract

    assert contract is not None
    assert contract.conditional_requirements == [
        registry.ReviewContractConditionalRequirement(
            when="theorem-bearing claims are present",
            required_outputs=["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            stage_artifacts=["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
        )
    ]
    source = _read_command("peer-review")
    assert "conditional_requirements:" in source
    assert "when: theorem-bearing claims are present" in source


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
    respond_command = _read_command("respond-to-referees")
    respond_workflow = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in respond_command
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in respond_command
    assert "templates/paper/author-response.md" in respond_workflow
    assert "needs-calculation" in respond_workflow


def test_write_paper_review_contract_uses_round_suffixed_referee_outputs() -> None:
    contract = registry.get_command("write-paper").review_contract

    assert contract is not None
    assert contract.required_outputs == [
        "${PAPER_DIR}/{topic_specific_stem}.tex",
        "${PAPER_DIR}/ARTIFACT-MANIFEST.json",
        "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json",
        "${PAPER_DIR}/reproducibility-manifest.json",
        "GPD/review/CLAIMS{round_suffix}.json",
        "GPD/review/STAGE-reader{round_suffix}.json",
        "GPD/review/STAGE-literature{round_suffix}.json",
        "GPD/review/STAGE-math{round_suffix}.json",
        "GPD/review/STAGE-physics{round_suffix}.json",
        "GPD/review/STAGE-interestingness{round_suffix}.json",
        "GPD/review/REVIEW-LEDGER{round_suffix}.json",
        "GPD/review/REFEREE-DECISION{round_suffix}.json",
        "GPD/REFEREE-REPORT{round_suffix}.md",
        "GPD/REFEREE-REPORT{round_suffix}.tex",
    ]
    write_command = _read_command("write-paper")
    write_workflow = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in write_command
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in write_command
    assert "templates/paper/author-response.md" in write_workflow
    assert "needs-calculation" in write_workflow


def test_author_response_template_is_canonical_and_mentions_new_calculation_tracking() -> None:
    author_response = (TEMPLATES_DIR / "paper" / "author-response.md").read_text(encoding="utf-8")
    referee_response = (TEMPLATES_DIR / "paper" / "referee-response.md").read_text(encoding="utf-8")
    writer = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")

    assert "issues_needing_calculation" in author_response
    assert "needs-calculation" in author_response
    assert "Source phase for new work" in author_response
    assert "templates/paper/author-response.md" in referee_response
    assert "needs-calculation" in referee_response
    assert "templates/paper/author-response.md" in writer
    assert "needs-calculation" in writer


def test_referee_response_template_reuses_canonical_issue_fields_in_worked_sections() -> None:
    referee_response = (TEMPLATES_DIR / "paper" / "referee-response.md").read_text(encoding="utf-8")
    ref_002 = referee_response.split("### REF-002", 1)[1].split("### REF-003", 1)[0]
    ref_101 = referee_response.split("### REF-101", 1)[1].split("### REF-102", 1)[0]

    for section in (ref_002, ref_101):
        assert "**Classification:**" in section
        assert "**Blocking issue:**" in section
        assert "**Decision-artifact context:**" in section
        assert "**Source phase for new work:**" in section
        assert "**Category:**" not in section


def test_write_paper_review_contract_surfaces_manuscript_root_review_dependencies() -> None:
    source = _read_command("write-paper")

    assert "${PAPER_DIR}/ARTIFACT-MANIFEST.json" in source
    assert "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json" in source
    assert "${PAPER_DIR}/reproducibility-manifest.json" in source
    assert "stage review artifacts" not in source


def test_summary_template_surfaces_plan_contract_ref_rule_for_contract_ledgers() -> None:
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")

    assert "single detailed rule source" in summary_template
    assert "plan_contract_ref" in summary_template
    assert "contract_results" in summary_template
    assert "comparison_verdicts" in summary_template
    assert "uncertainty_markers" in summary_template
    assert "suggested_contract_checks" in summary_template
    assert "The canonical schema defines the exact list-trimming semantics" in summary_template
    assert "Blank-after-trim entries are invalid" in contract_results_schema
    assert "duplicate-after-trim entries are invalid" in contract_results_schema


def test_verification_template_forbids_placeholder_uncertainty_fillers() -> None:
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    assert "decisive readout of the same contract-backed ledger" in verification_template
    assert "Keep `uncertainty_markers` explicit" in verification_template
    assert "structured `suggested_contract_checks`" in verification_template
    assert "filler placeholders" not in verification_template


def test_verification_template_surfaces_strict_passed_and_blocked_semantics() -> None:
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    assert "status: passed` is strict" in verification_template
    assert "every required decisive comparison is decisive" in verification_template
    assert "If decisive work remains open, use `partial`, `gaps_found`, `expert_needed`, or `human_needed`" in verification_template
    assert "Reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing and apply it literally." in verification_template
    assert "record structured `suggested_contract_checks` instead of padding prose" in verification_template
    assert "Proof-backed claims follow the proof-audit rules in the canonical schema" in verification_template


def test_research_verification_template_surfaces_non_empty_uncertainty_markers() -> None:
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")

    assert "Use `@{GPD_INSTALL_DIR}/templates/verification-report.md` for the canonical verification frontmatter contract." in research_verification
    assert "verification-side `suggested_contract_checks` entries are part of the same canonical schema surface" in research_verification
    assert "comparison_kind: benchmark" in research_verification
    assert "Allowed body enum values:" in research_verification
    assert "`comparison_kind`: benchmark|prior_work|experiment|cross_method|baseline|other" in research_verification
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]" not in research_verification
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other | \"\"]" not in research_verification
    assert 'comparison_kind: "benchmark"' in research_verification
    assert 'comparison_kind: "benchmark | prior_work | experiment | cross_method | baseline | other"' not in research_verification
    assert "omit both `comparison_kind` and `comparison_reference_id` instead of leaving blank placeholders" in research_verification
    assert "uncertainty_markers:" in research_verification
    assert "weakest_anchors: [anchor-1]" in research_verification
    assert "disconfirming_observations: [observation-1]" in research_verification


def test_write_paper_prompt_discovers_plan_scoped_phase_summaries() -> None:
    source = _read_command("write-paper")

    assert "ls GPD/phases/*/*SUMMARY.md 2>/dev/null" in source


def test_write_paper_prompt_loads_figure_tracker_schema_before_updating_tracker() -> None:
    source = _read_command("write-paper")

    assert "@{GPD_INSTALL_DIR}/templates/paper/figure-tracker.md" in source
    assert "${PAPER_DIR}/FIGURE_TRACKER.md" in source
    assert "canonical schema/template surfaces it loads there" in source


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
    assert "Only `subject_role: decisive` closes a decisive requirement" in internal
    assert "Only `subject_role: decisive` closes a decisive requirement" in experimental
    assert "Must be the canonical project-root-relative `GPD/phases/XX-name/XX-YY-PLAN.md#/contract` path" in contract_results


def test_contract_ledgers_surface_decisive_only_verdict_rules_and_strict_suggested_check_keys() -> None:
    contract_results = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    assert "Do not invent `artifact` or `other` subject kinds" in contract_results
    assert "Only `subject_role: decisive` satisfies a required decisive comparison" in contract_results
    assert "`subject_role` must be explicit on every verdict" in contract_results
    assert "canonical project-root-relative `GPD/phases/XX-name/XX-YY-PLAN.md#/contract` path" in contract_results
    assert "If a decisive external anchor was used, include `reference_id`" in contract_results
    assert "reference-backed decisive comparison is required" in contract_results
    assert "acceptance test with `kind: benchmark` or `kind: cross_method`" in contract_results
    assert "`contract_results` and every nested entry use a closed schema" in contract_results
    assert "uncertainty_markers:" in contract_results
    assert "weakest_anchors: [anchor-1]" in contract_results
    assert "disconfirming_observations: [observation-1]" in contract_results
    assert "Invented keys such as `check_id` fail validation." in contract_results
    assert "Copy the `check_key` returned by `suggest_contract_checks(contract)` into the frontmatter `check` field" in contract_results
    assert "comparison_verdicts" in verification_template
    assert "suggested_contract_checks" in verification_template


def test_contract_ledgers_surface_forbidden_proxy_bindings_and_action_vocabulary() -> None:
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    contract_results = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    state_schema = (TEMPLATES_DIR / "state-json-schema.md").read_text(encoding="utf-8")

    assert "single detailed rule source" in summary_template
    assert "contract_results" in summary_template
    assert "comparison_verdicts" in summary_template
    assert "legacy frontmatter aliases" in summary_template.lower()
    assert "forbidden_proxy_id" in contract_results
    assert "closed action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`" in contract_results
    assert "Blank-after-trim entries are invalid" in contract_results
    assert "duplicate-after-trim entries are invalid" in contract_results
    assert "weakest_anchors: [anchor-1]" in contract_results
    assert "disconfirming_observations: [observation-1]" in contract_results
    assert "uncertainty_markers.weakest_anchors" in state_schema
    assert "uncertainty_markers.disconfirming_observations" in state_schema
    assert (
        "`must_include_prior_outputs[]` entries should be explicit project-artifact paths or filenames that already exist inside the current project root."
        in state_schema
    )
    assert "If `project_root` is unavailable, treat them as non-grounding until the file can be resolved against a concrete root." in state_schema
    assert '"must_include_prior_outputs": ["GPD/phases/00-baseline/00-01-SUMMARY.md"]' in state_schema
    assert "`GPD/phases/.../*-SUMMARY.md`" not in state_schema
    assert "`GPD/phases/.../SUMMARY.md`" not in state_schema


def test_prompt_visible_contracts_surface_literal_boolean_requirements() -> None:
    plan_schema = (TEMPLATES_DIR / "plan-contract-schema.md").read_text(encoding="utf-8")
    review_reader = (AGENTS_DIR / "gpd-review-reader.md").read_text(encoding="utf-8")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")

    assert "`required_in_proof` must be a literal JSON boolean (`true` or `false`)" in plan_schema
    assert "not a quoted string or synonym such as `\"yes\"` / `\"no\"`" in plan_schema
    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" in review_reader
    assert "shared source of truth for the full `ClaimIndex` and `StageReviewReport` contracts" in review_reader
    assert "`blocking` in each finding must be a literal JSON boolean (`true` or `false`)" in panel
    assert "not a quoted string or synonym such as `\"yes\"` / `\"no\"`" in panel


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
    assert "GPD/review/CLAIMS{round_suffix}.json" in panel
    assert "GPD/review/STAGE-reader{round_suffix}.json" in panel
    assert "proof_audits" in panel
    assert "theorem_assumptions" in panel
    assert "theorem_parameters" in panel
    assert "Strict-stage specialist artifacts must use canonical names `STAGE-reader`, `STAGE-literature`, `STAGE-math`, `STAGE-physics`, `STAGE-interestingness`." in panel
    assert "all five must share the same optional `-R<round>` suffix." in panel
    assert "every theorem-bearing Stage 1 claim must be reviewed and proof-audited" in panel
    assert "every theorem-bearing Stage 1 claim must be reviewed and proof-audited" in review_math


def test_executor_completion_reference_requires_loading_contract_schema_before_summary_frontmatter() -> None:
    completion = (REFERENCES_DIR / "execution" / "executor-completion.md").read_text(encoding="utf-8")

    assert "Canonical ledger schema to load before writing SUMMARY frontmatter:" in completion
    assert "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md" in completion
