"""Data point contracts for the GPD-Exp pipeline.

Defines BaseDataPoint and typed variants (Numeric, Categorical, Timing,
Observation) with a discriminated union on measurement_type.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class QualityStatus(StrEnum):
    """Quality validation status for a data point."""

    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    FLAGGED = "flagged"


class BaseDataPoint(BaseModel):
    """Common fields shared by all data point types."""

    id: UUID
    run_id: UUID
    bounty_id: str
    timestamp: datetime
    quality_status: QualityStatus = QualityStatus.PENDING
    worker_id: str | None = None


class NumericDataPoint(BaseDataPoint):
    """A numeric measurement data point."""

    measurement_type: Literal["numeric"] = "numeric"
    value: float
    unit: str
    uncertainty: float | None = None


class CategoricalDataPoint(BaseDataPoint):
    """A categorical observation data point."""

    measurement_type: Literal["categorical"] = "categorical"
    category: str
    confidence: float | None = None


class TimingDataPoint(BaseDataPoint):
    """A timing/duration measurement data point."""

    measurement_type: Literal["timing"] = "timing"
    duration_seconds: float
    start_time: datetime | None = None
    end_time: datetime | None = None


class ObservationDataPoint(BaseDataPoint):
    """A free-text observation data point with optional attachments."""

    measurement_type: Literal["observation"] = "observation"
    description: str
    attachments: list[str] = Field(default_factory=list)


DataPoint = Annotated[
    NumericDataPoint | CategoricalDataPoint | TimingDataPoint | ObservationDataPoint,
    Field(discriminator="measurement_type"),
]
