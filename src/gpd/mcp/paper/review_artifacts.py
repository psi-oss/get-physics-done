"""Helpers for persisting staged peer-review artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from gpd.mcp.paper.models import ClaimIndex, ReviewLedger, ReviewPanelBundle, StageReviewReport

if TYPE_CHECKING:
    from gpd.core.referee_policy import RefereeDecisionInput

_T = TypeVar("_T", bound=BaseModel)


def _write_model(model: BaseModel, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(model.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")


def _read_model(model_cls: type[_T], input_path: Path) -> _T:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    return model_cls.model_validate(payload)


def write_claim_index(index: ClaimIndex, output_path: Path) -> None:
    """Persist a claim index JSON artifact."""

    _write_model(index, output_path)


def read_claim_index(input_path: Path) -> ClaimIndex:
    """Load a claim index JSON artifact."""

    return _read_model(ClaimIndex, input_path)


def write_stage_review_report(report: StageReviewReport, output_path: Path) -> None:
    """Persist a staged reviewer JSON artifact."""

    _write_model(report, output_path)


def read_stage_review_report(input_path: Path) -> StageReviewReport:
    """Load a staged reviewer JSON artifact."""

    return _read_model(StageReviewReport, input_path)


def write_review_ledger(ledger: ReviewLedger, output_path: Path) -> None:
    """Persist a review-ledger JSON artifact."""

    _write_model(ledger, output_path)


def read_review_ledger(input_path: Path) -> ReviewLedger:
    """Load a review-ledger JSON artifact."""

    return _read_model(ReviewLedger, input_path)


def write_referee_decision(decision: RefereeDecisionInput, output_path: Path) -> None:
    """Persist a referee-decision JSON artifact."""

    _write_model(decision, output_path)


def read_referee_decision(input_path: Path) -> RefereeDecisionInput:
    """Load a referee-decision JSON artifact."""

    from gpd.core.referee_policy import RefereeDecisionInput

    return _read_model(RefereeDecisionInput, input_path)


def write_review_panel_bundle(bundle: ReviewPanelBundle, output_path: Path) -> None:
    """Persist the final staged-review bundle JSON."""

    _write_model(bundle, output_path)


def read_review_panel_bundle(input_path: Path) -> ReviewPanelBundle:
    """Load the final staged-review bundle JSON."""

    return _read_model(ReviewPanelBundle, input_path)
