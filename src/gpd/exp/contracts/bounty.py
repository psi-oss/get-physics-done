"""Bounty contracts for the GPD-Exp pipeline.

Defines BountySpec, BountyRecord, BountyLifecycleRecord, and BountyStatus
for tracking human-sourced data collection tasks through the full
RentAHuman lifecycle.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from gpd.exp.contracts.budget import Currency


class BountyStatus(StrEnum):
    """Lifecycle status of a bounty."""

    DRAFT = "draft"
    POSTED = "posted"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    RETRYING = "retrying"
    CANCELLED = "cancelled"

    # Full RentAHuman lifecycle states
    AWAITING_APPLICATION = "awaiting_application"
    APPLICATION_RECEIVED = "application_received"
    AWAITING_ESCROW = "awaiting_escrow"
    ESCROW_FUNDED = "escrow_funded"
    WORKER_ACTIVE = "worker_active"
    DELIVERED = "delivered"


class BountyLifecycleRecord(BaseModel):
    """Tracks RentAHuman lifecycle state for a bounty.

    Populated progressively as the bounty moves through the platform lifecycle:
    POSTED → AWAITING_APPLICATION → APPLICATION_RECEIVED → AWAITING_ESCROW
    → ESCROW_FUNDED → WORKER_ACTIVE → DELIVERED → COMPLETED.
    """

    application_id: str | None = None
    escrow_id: str | None = None
    conversation_id: str | None = None
    checkout_url: str | None = None
    human_id: str | None = None
    human_name: str | None = None
    escrow_status: str | None = None


class BountySpec(BaseModel):
    """Specification for a bounty to post on a human-task platform."""

    title: str
    description: str
    price_cents: int = Field(ge=0)
    currency: Currency
    deadline: datetime | None = None
    skills_needed: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    spots_available: int = Field(default=1, ge=1)


class BountyRecord(BaseModel):
    """Full record of a bounty including platform tracking."""

    id: UUID
    experiment_id: UUID
    platform_bounty_id: str | None = None
    status: BountyStatus = BountyStatus.DRAFT
    specification: BountySpec
    amount_cents: int = Field(ge=0)
    currency: Currency
    reservation_id: UUID | None = None
    idempotency_key: str
    deadline: datetime | None = None
    created_at: datetime
    updated_at: datetime
    lifecycle: BountyLifecycleRecord = Field(default_factory=BountyLifecycleRecord)
