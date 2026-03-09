"""Integration tests for the atomic BudgetLedger.

These tests verify the core safety invariant: spent + reserved <= cap,
enforced via PostgreSQL SELECT FOR UPDATE row-level locking.

Requires a live PostgreSQL database. Set GPD_EXP_DATABASE_URL to run.
Tests are skipped cleanly when no database is available.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from tests.conftest import requires_db

# ---------------------------------------------------------------------------
# All tests in this module require a live database
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration, requires_db]


@pytest.fixture
def ledger(migrated_db):
    """Create a BudgetLedger backed by the migrated database pool."""
    from gpd.exp.infrastructure.budget_ledger import BudgetLedger

    return BudgetLedger(migrated_db)


# ---------------------------------------------------------------------------
# reserve()
# ---------------------------------------------------------------------------


async def test_reserve_creates_ledger_entry(test_experiment, ledger) -> None:
    """reserve() inserts a ledger row and updates budget_reserved_cents."""
    experiment_id, pool = test_experiment

    reservation_id = await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=2000,
        currency="USD",
        description="Bounty for measuring gravity",
        idempotency_key="idem-001",
    )

    assert reservation_id is not None
    # Verify it's a valid UUID string
    uuid.UUID(reservation_id)

    # Verify the experiment row was updated
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT budget_reserved_cents, budget_spent_cents FROM gpd_exp_experiments WHERE id = $1",
            uuid.UUID(experiment_id),
        )
        assert row["budget_reserved_cents"] == 2000
        assert row["budget_spent_cents"] == 0

    # Verify ledger entry was inserted
    async with pool.acquire() as conn:
        entry = await conn.fetchrow(
            "SELECT action, amount_cents, idempotency_key FROM gpd_exp_budget_ledger WHERE id = $1",
            uuid.UUID(reservation_id),
        )
        assert entry["action"] == "reserve"
        assert entry["amount_cents"] == 2000
        assert entry["idempotency_key"] == "idem-001"


async def test_reserve_exact_remaining_succeeds(test_experiment, ledger) -> None:
    """Reserving exactly the remaining budget succeeds."""
    experiment_id, _ = test_experiment

    # Reserve the full 10000 cents
    reservation_id = await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=10000,
        currency="USD",
        description="Full budget reservation",
        idempotency_key="idem-full",
    )
    assert reservation_id is not None


async def test_reserve_exceeds_budget_raises(test_experiment, ledger) -> None:
    """Reserving more than available raises BudgetExceeded."""
    from gpd.exp.contracts.budget import BudgetExceeded

    experiment_id, _ = test_experiment

    with pytest.raises(BudgetExceeded) as exc_info:
        await ledger.reserve(
            experiment_id=experiment_id,
            amount_cents=10001,
            currency="USD",
            description="Over budget",
            idempotency_key="idem-over",
        )

    assert exc_info.value.requested_cents == 10001
    assert exc_info.value.available_cents == 10000


async def test_reserve_after_partial_spend_checks_remaining(test_experiment, ledger) -> None:
    """After a partial reservation, the next reserve checks remaining budget."""
    from gpd.exp.contracts.budget import BudgetExceeded

    experiment_id, _ = test_experiment

    # Reserve 6000 of 10000
    await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=6000,
        currency="USD",
        description="First reservation",
        idempotency_key="idem-first",
    )

    # Reserve 4000 more (exactly remaining) -- should succeed
    await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=4000,
        currency="USD",
        description="Second reservation",
        idempotency_key="idem-second",
    )

    # Reserve 1 more cent -- should fail
    with pytest.raises(BudgetExceeded):
        await ledger.reserve(
            experiment_id=experiment_id,
            amount_cents=1,
            currency="USD",
            description="One cent too many",
            idempotency_key="idem-over-by-one",
        )


# ---------------------------------------------------------------------------
# confirm()
# ---------------------------------------------------------------------------


async def test_confirm_moves_reserved_to_spent(test_experiment, ledger) -> None:
    """confirm() decreases reserved and increases spent by the same amount."""
    experiment_id, pool = test_experiment

    reservation_id = await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=3000,
        currency="USD",
        description="Bounty reservation",
        idempotency_key="idem-confirm-test",
    )

    await ledger.confirm(
        reservation_id=reservation_id,
        experiment_id=experiment_id,
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT budget_spent_cents, budget_reserved_cents FROM gpd_exp_experiments WHERE id = $1",
            uuid.UUID(experiment_id),
        )
        assert row["budget_spent_cents"] == 3000
        assert row["budget_reserved_cents"] == 0


# ---------------------------------------------------------------------------
# release()
# ---------------------------------------------------------------------------


async def test_release_returns_reserved_to_pool(test_experiment, ledger) -> None:
    """release() decreases reserved, making funds available again."""
    experiment_id, pool = test_experiment

    reservation_id = await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=5000,
        currency="USD",
        description="Will be released",
        idempotency_key="idem-release-test",
    )

    await ledger.release(
        reservation_id=reservation_id,
        experiment_id=experiment_id,
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT budget_spent_cents, budget_reserved_cents FROM gpd_exp_experiments WHERE id = $1",
            uuid.UUID(experiment_id),
        )
        assert row["budget_spent_cents"] == 0
        assert row["budget_reserved_cents"] == 0

    # Budget is fully available again -- new reservation should work
    await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=10000,
        currency="USD",
        description="After release, full budget available",
        idempotency_key="idem-after-release",
    )


# ---------------------------------------------------------------------------
# refund()
# ---------------------------------------------------------------------------


async def test_refund_decreases_spent(test_experiment, ledger) -> None:
    """refund() decreases budget_spent_cents and creates a refund ledger entry."""
    experiment_id, pool = test_experiment

    # Reserve and confirm first
    reservation_id = await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=4000,
        currency="USD",
        description="Bounty reservation",
        idempotency_key="idem-refund-reserve",
    )
    await ledger.confirm(reservation_id=reservation_id, experiment_id=experiment_id)

    # Now refund 1500 cents
    refund_id = await ledger.refund(
        experiment_id=experiment_id,
        amount_cents=1500,
        currency="USD",
        description="Partial refund for overpayment",
        idempotency_key="idem-refund-001",
    )
    assert refund_id is not None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT budget_spent_cents, budget_reserved_cents FROM gpd_exp_experiments WHERE id = $1",
            uuid.UUID(experiment_id),
        )
        assert row["budget_spent_cents"] == 2500  # 4000 - 1500
        assert row["budget_reserved_cents"] == 0

    # Verify ledger entry
    async with pool.acquire() as conn:
        entry = await conn.fetchrow(
            "SELECT action, amount_cents FROM gpd_exp_budget_ledger WHERE id = $1",
            uuid.UUID(refund_id),
        )
        assert entry["action"] == "refund"
        assert entry["amount_cents"] == 1500


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


async def test_idempotency_key_prevents_duplicate_reserve(test_experiment, ledger) -> None:
    """Duplicate idempotency_key on reserve is handled gracefully."""
    experiment_id, pool = test_experiment

    first_id = await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=2000,
        currency="USD",
        description="First attempt",
        idempotency_key="idem-dup-001",
    )

    # Second attempt with same idempotency_key should return the same reservation_id
    # (or raise UniqueViolation handled gracefully)
    second_id = await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=2000,
        currency="USD",
        description="Duplicate attempt",
        idempotency_key="idem-dup-001",
    )

    assert first_id == second_id

    # Budget should only have been reserved once (2000, not 4000)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT budget_reserved_cents FROM gpd_exp_experiments WHERE id = $1",
            uuid.UUID(experiment_id),
        )
        assert row["budget_reserved_cents"] == 2000


# ---------------------------------------------------------------------------
# Concurrent reservations (core safety test)
# ---------------------------------------------------------------------------


async def test_concurrent_reservations_reject_over_budget(test_experiment, ledger) -> None:
    """Two concurrent reserve() calls that together exceed budget: first succeeds, second fails.

    This validates the SELECT FOR UPDATE locking mechanism. Without proper locking,
    both reservations could see the full budget and both succeed, violating the invariant.
    """
    from gpd.exp.contracts.budget import BudgetExceeded

    experiment_id, pool = test_experiment

    # Budget is 10000. Two concurrent 6000 reservations -- only one should succeed.
    results: list[str | BudgetExceeded] = []

    async def attempt_reserve(key: str) -> None:
        try:
            rid = await ledger.reserve(
                experiment_id=experiment_id,
                amount_cents=6000,
                currency="USD",
                description=f"Concurrent reservation {key}",
                idempotency_key=key,
            )
            results.append(rid)
        except BudgetExceeded as exc:
            results.append(exc)

    await asyncio.gather(
        attempt_reserve("concurrent-a"),
        attempt_reserve("concurrent-b"),
    )

    successes = [r for r in results if isinstance(r, str)]
    failures = [r for r in results if isinstance(r, BudgetExceeded)]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}"

    # Verify the database invariant holds
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT budget_spent_cents, budget_reserved_cents, budget_cap_cents FROM gpd_exp_experiments WHERE id = $1",
            uuid.UUID(experiment_id),
        )
        assert row["budget_reserved_cents"] == 6000
        assert row["budget_spent_cents"] + row["budget_reserved_cents"] <= row["budget_cap_cents"]


# ---------------------------------------------------------------------------
# Full lifecycle: reserve -> confirm -> refund
# ---------------------------------------------------------------------------


async def test_full_lifecycle_reserve_confirm_refund(test_experiment, ledger) -> None:
    """End-to-end lifecycle: reserve -> confirm -> refund maintains invariant."""
    experiment_id, pool = test_experiment

    # Step 1: Reserve 5000
    rid = await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=5000,
        currency="USD",
        description="Lifecycle test bounty",
        idempotency_key="idem-lifecycle-reserve",
    )

    # Step 2: Confirm the reservation
    await ledger.confirm(reservation_id=rid, experiment_id=experiment_id)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT budget_spent_cents, budget_reserved_cents FROM gpd_exp_experiments WHERE id = $1",
            uuid.UUID(experiment_id),
        )
        assert row["budget_spent_cents"] == 5000
        assert row["budget_reserved_cents"] == 0

    # Step 3: Refund 2000
    await ledger.refund(
        experiment_id=experiment_id,
        amount_cents=2000,
        currency="USD",
        description="Partial refund",
        idempotency_key="idem-lifecycle-refund",
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT budget_spent_cents, budget_reserved_cents FROM gpd_exp_experiments WHERE id = $1",
            uuid.UUID(experiment_id),
        )
        assert row["budget_spent_cents"] == 3000
        assert row["budget_reserved_cents"] == 0

    # Step 4: Reserve again with freed-up budget
    await ledger.reserve(
        experiment_id=experiment_id,
        amount_cents=7000,
        currency="USD",
        description="Post-refund reservation",
        idempotency_key="idem-lifecycle-re-reserve",
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT budget_spent_cents, budget_reserved_cents, budget_cap_cents FROM gpd_exp_experiments WHERE id = $1",
            uuid.UUID(experiment_id),
        )
        assert row["budget_spent_cents"] == 3000
        assert row["budget_reserved_cents"] == 7000
        assert row["budget_spent_cents"] + row["budget_reserved_cents"] <= row["budget_cap_cents"]


# ---------------------------------------------------------------------------
# Edge case: reserve for nonexistent experiment
# ---------------------------------------------------------------------------


async def test_reserve_nonexistent_experiment_raises(ledger) -> None:
    """reserve() on a nonexistent experiment raises ValueError."""
    fake_id = str(uuid.uuid4())

    with pytest.raises(ValueError, match="not found"):
        await ledger.reserve(
            experiment_id=fake_id,
            amount_cents=100,
            currency="USD",
            description="Should fail",
            idempotency_key="idem-nonexistent",
        )
