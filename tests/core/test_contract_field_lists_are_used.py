from __future__ import annotations

from typing import get_args, get_origin

from pydantic import BaseModel

from gpd.contracts import (
    PROJECT_CONTRACT_COLLECTION_LIST_FIELDS,
    PROJECT_CONTRACT_MAPPING_LIST_FIELDS,
    PROJECT_CONTRACT_NESTED_COLLECTION_LIST_FIELDS,
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
        if (
            not include_model_items
            and isinstance(item_type, type)
            and issubclass(item_type, BaseModel)
        ):
            continue
        field_names.append(field_name)
    return tuple(field_names)


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
