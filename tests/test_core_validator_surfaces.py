from pathlib import Path

from gpd.core.child_return_application import (
    SUPPORTED_CONTINUATION_UPDATE_FIELDS,
    SUPPORTED_STATE_UPDATE_FIELDS,
    ApplyChildReturnResult,
)
from gpd.core.knowledge_constants import (
    KNOWLEDGE_REVIEW_DECISION_APPROVED,
    KNOWLEDGE_REVIEW_DECISION_NEEDS_CHANGES,
    KNOWLEDGE_REVIEW_DECISION_REJECTED,
    KNOWLEDGE_REVIEW_DECISION_VALUES,
    KNOWLEDGE_STATUS_DRAFT,
    KNOWLEDGE_STATUS_IN_REVIEW,
    KNOWLEDGE_STATUS_STABLE,
    KNOWLEDGE_STATUS_SUPERSEDED,
    KNOWLEDGE_STATUS_VALUES,
)
from gpd.core.path_labels import normalize_posix_path_label, project_relative_path_label
from gpd.core.review_contract_schema import (
    REVIEW_CONTRACT_FRONTMATTER_KEY,
    REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
    REVIEW_CONTRACT_WRAPPER_KEYS,
)
from gpd.core.segment_constants import COMPLETED_SEGMENT_STATES, PAUSED_SEGMENT_STATES


def test_path_labels_normalize_posix_and_preserve_external_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    inside = project_root / "GPD" / "STATE.md"
    outside = tmp_path / "other" / "artifact.md"

    assert normalize_posix_path_label("  GPD\\phases//01/../02-SUMMARY.md  ") == "GPD/phases/02-SUMMARY.md"
    assert project_relative_path_label(project_root, inside) == "GPD/STATE.md"
    assert project_relative_path_label(project_root, outside) == outside.as_posix()
    assert project_relative_path_label(project_root, None) is None


def test_review_contract_wrapper_keys_stay_canonical() -> None:
    assert REVIEW_CONTRACT_FRONTMATTER_KEY == "review-contract"
    assert REVIEW_CONTRACT_PROMPT_WRAPPER_KEY == "review_contract"
    assert REVIEW_CONTRACT_WRAPPER_KEYS == ("review_contract", "review-contract")


def test_segment_state_sets_are_disjoint_and_complete() -> None:
    assert {"completed", "complete", "done", "finished"} <= COMPLETED_SEGMENT_STATES
    assert {"paused", "awaiting_user", "ready_to_continue"} <= PAUSED_SEGMENT_STATES
    assert COMPLETED_SEGMENT_STATES.isdisjoint(PAUSED_SEGMENT_STATES)


def test_knowledge_lifecycle_values_are_explicit_and_ordered() -> None:
    assert KNOWLEDGE_STATUS_VALUES == (
        KNOWLEDGE_STATUS_DRAFT,
        KNOWLEDGE_STATUS_IN_REVIEW,
        KNOWLEDGE_STATUS_STABLE,
        KNOWLEDGE_STATUS_SUPERSEDED,
    )
    assert KNOWLEDGE_REVIEW_DECISION_VALUES == (
        KNOWLEDGE_REVIEW_DECISION_APPROVED,
        KNOWLEDGE_REVIEW_DECISION_NEEDS_CHANGES,
        KNOWLEDGE_REVIEW_DECISION_REJECTED,
    )


def test_child_return_applicator_exports_fail_closed_surfaces() -> None:
    assert SUPPORTED_STATE_UPDATE_FIELDS == ("advance_plan", "update_progress", "record_metric")
    assert SUPPORTED_CONTINUATION_UPDATE_FIELDS == ("handoff", "bounded_segment")

    result = ApplyChildReturnResult(passed=False, status="failed", errors=["unsupported state update"])
    assert not result.passed
    assert result.status == "failed"
    assert result.errors == ["unsupported state update"]
    assert result.applied_state_operations == []
    assert result.contract_updates == {}
