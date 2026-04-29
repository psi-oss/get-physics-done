from __future__ import annotations

from typing import get_args, get_origin

from pydantic import BaseModel

from gpd.contracts import (
    PROJECT_CONTRACT_COLLECTION_LIST_FIELDS,
    PROJECT_CONTRACT_MAPPING_LIST_FIELDS,
    PROJECT_CONTRACT_NESTED_COLLECTION_LIST_FIELDS,
    PROJECT_CONTRACT_REQUIRED_SECTION_FIELDS,
    PROJECT_CONTRACT_REQUIRED_UNCERTAINTY_MARKER_FIELDS,
    PROJECT_CONTRACT_TOP_LEVEL_LIST_FIELDS,
    ContractAcceptanceTest,
    ContractApproachPolicy,
    ContractClaim,
    ContractContextIntake,
    ContractDeliverable,
    ContractLink,
    ContractProofHypothesis,
    ContractProofParameter,
    ContractReference,
    ContractScope,
    ContractUncertaintyMarkers,
    ResearchContract,
)


def _model_list_field_names(model: type[object], *, include_model_items: bool = False) -> tuple[str, ...]:
    field_names: list[str] = []
    for field_name, field in model.model_fields.items():
        if get_origin(field.annotation) is not list:
            continue
        item_args = get_args(field.annotation)
        item_type = item_args[0] if len(item_args) == 1 else None
        if not include_model_items and isinstance(item_type, type) and issubclass(item_type, BaseModel):
            continue
        field_names.append(field_name)
    return tuple(field_names)


def _field_validator_fields(model: type[object], validator_name: str) -> tuple[str, ...]:
    return model.__pydantic_decorators__.field_validators[validator_name].info.fields


def test_project_contract_mapping_list_fields_match_contract_models() -> None:
    assert PROJECT_CONTRACT_MAPPING_LIST_FIELDS == {
        "scope": _model_list_field_names(ContractScope),
        "context_intake": _model_list_field_names(ContractContextIntake),
        "approach_policy": _model_list_field_names(ContractApproachPolicy),
        "uncertainty_markers": _model_list_field_names(ContractUncertaintyMarkers),
    }


def test_project_contract_top_level_list_fields_match_research_contract_model() -> None:
    assert PROJECT_CONTRACT_TOP_LEVEL_LIST_FIELDS == _model_list_field_names(
        ResearchContract,
        include_model_items=True,
    )


def test_project_contract_collection_list_fields_match_item_models() -> None:
    assert PROJECT_CONTRACT_COLLECTION_LIST_FIELDS == {
        "claims": _model_list_field_names(ContractClaim),
        "deliverables": _model_list_field_names(ContractDeliverable),
        "acceptance_tests": _model_list_field_names(ContractAcceptanceTest),
        "references": _model_list_field_names(ContractReference),
        "links": _model_list_field_names(ContractLink),
    }


def test_project_contract_nested_collection_list_fields_match_item_models() -> None:
    assert PROJECT_CONTRACT_NESTED_COLLECTION_LIST_FIELDS == {
        ("claims", "parameters"): _model_list_field_names(ContractProofParameter),
        ("claims", "hypotheses"): _model_list_field_names(ContractProofHypothesis),
    }


def test_project_contract_list_normalizers_match_exported_field_lists() -> None:
    assert (
        _field_validator_fields(ContractScope, "_normalize_scope_lists")
        == PROJECT_CONTRACT_MAPPING_LIST_FIELDS["scope"]
    )
    assert (
        _field_validator_fields(
            ContractContextIntake,
            "_normalize_intake_lists",
        )
        == PROJECT_CONTRACT_MAPPING_LIST_FIELDS["context_intake"]
    )
    assert (
        _field_validator_fields(
            ContractApproachPolicy,
            "_normalize_policy_lists",
        )
        == PROJECT_CONTRACT_MAPPING_LIST_FIELDS["approach_policy"]
    )
    assert (
        _field_validator_fields(
            ContractUncertaintyMarkers,
            "_normalize_uncertainty_lists",
        )
        == PROJECT_CONTRACT_MAPPING_LIST_FIELDS["uncertainty_markers"]
    )

    assert (
        _field_validator_fields(ContractClaim, "_normalize_id_lists")
        == PROJECT_CONTRACT_COLLECTION_LIST_FIELDS["claims"]
    )
    assert (
        _field_validator_fields(
            ContractDeliverable,
            "_normalize_must_contain",
        )
        == PROJECT_CONTRACT_COLLECTION_LIST_FIELDS["deliverables"]
    )
    assert (
        _field_validator_fields(
            ContractAcceptanceTest,
            "_normalize_evidence_required",
        )
        == PROJECT_CONTRACT_COLLECTION_LIST_FIELDS["acceptance_tests"]
    )
    reference_fields = (
        *_field_validator_fields(ContractReference, "_normalize_reference_lists"),
        *_field_validator_fields(ContractReference, "_normalize_required_actions"),
    )
    assert reference_fields == PROJECT_CONTRACT_COLLECTION_LIST_FIELDS["references"]
    assert (
        _field_validator_fields(ContractLink, "_normalize_verified_by")
        == PROJECT_CONTRACT_COLLECTION_LIST_FIELDS["links"]
    )

    assert (
        _field_validator_fields(
            ContractProofParameter,
            "_normalize_aliases",
        )
        == PROJECT_CONTRACT_NESTED_COLLECTION_LIST_FIELDS[("claims", "parameters")]
    )
    assert (
        _field_validator_fields(
            ContractProofHypothesis,
            "_normalize_symbols",
        )
        == PROJECT_CONTRACT_NESTED_COLLECTION_LIST_FIELDS[("claims", "hypotheses")]
    )


def test_project_contract_required_field_lists_match_schema_contract() -> None:
    assert PROJECT_CONTRACT_REQUIRED_SECTION_FIELDS == (
        "schema_version",
        "scope",
        "context_intake",
        "uncertainty_markers",
    )
    assert PROJECT_CONTRACT_REQUIRED_UNCERTAINTY_MARKER_FIELDS == (
        "weakest_anchors",
        "disconfirming_observations",
    )
    assert set(PROJECT_CONTRACT_REQUIRED_UNCERTAINTY_MARKER_FIELDS) <= set(
        PROJECT_CONTRACT_MAPPING_LIST_FIELDS["uncertainty_markers"]
    )
