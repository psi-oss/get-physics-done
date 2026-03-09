"""Atomic budget ledger with PostgreSQL row-level locking.

Enforces the hard budget invariant: spent + reserved <= cap.
Every spend operation in the GPD-Exp pipeline MUST go through this ledger.

Uses SELECT FOR UPDATE to acquire a row-level lock on the experiment row
within a transaction, preventing concurrent reservations from exceeding
the budget cap. All amounts are integer cents -- no floating-point math.

Safety guarantees:
- Atomic: reserve/confirm/release/refund are single-transaction operations.
- Concurrent-safe: SELECT FOR UPDATE serializes access to the budget row.
- Idempotent: Unique index on (experiment_id, idempotency_key) prevents
  duplicate operations on crash recovery.
- Auditable: Every operation creates an append-only ledger entry.
"""

from __future__ import annotations

import uuid

import asyncpg

from gpd.exp.contracts.budget import BudgetExceeded


class BudgetLedger:
    """Atomic budget operations backed by PostgreSQL row-level locking.

    All methods acquire a row lock on gpd_exp_experiments via SELECT FOR UPDATE
    and operate within a single transaction.

    Args:
        pool: An asyncpg connection pool.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def reserve(
        self,
        experiment_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        idempotency_key: str,
    ) -> str:
        """Atomically reserve budget for a spend operation.

        Acquires a row lock on the experiment, checks the budget invariant
        (spent + reserved + amount <= cap), inserts a ledger entry, and
        updates budget_reserved_cents.

        Args:
            experiment_id: UUID string of the experiment.
            amount_cents: Amount to reserve in integer cents.
            currency: Currency code (e.g. "USD").
            description: Human-readable description for the audit trail.
            idempotency_key: Unique key to prevent duplicate reservations.

        Returns:
            The reservation_id (UUID string) of the new ledger entry.

        Raises:
            BudgetExceeded: If the reservation would exceed the budget cap.
            ValueError: If the experiment does not exist.
        """
        exp_uuid = uuid.UUID(experiment_id)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Check for existing entry with same idempotency key first
                existing = await conn.fetchrow(
                    """
                    SELECT id FROM gpd_exp_budget_ledger
                    WHERE experiment_id = $1 AND idempotency_key = $2
                    """,
                    exp_uuid,
                    idempotency_key,
                )
                if existing is not None:
                    return str(existing["id"])

                # Lock the experiment row -- blocks concurrent reservations
                row = await conn.fetchrow(
                    """
                    SELECT budget_cap_cents, budget_spent_cents, budget_reserved_cents
                    FROM gpd_exp_experiments
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    exp_uuid,
                )
                if row is None:
                    raise ValueError(f"Experiment {experiment_id} not found")

                cap = row["budget_cap_cents"]
                spent = row["budget_spent_cents"]
                reserved = row["budget_reserved_cents"]
                available = cap - spent - reserved

                if spent + reserved + amount_cents > cap:
                    raise BudgetExceeded(
                        experiment_id=experiment_id,
                        requested_cents=amount_cents,
                        available_cents=available,
                    )

                # Insert ledger entry
                reservation_id = await conn.fetchval(
                    """
                    INSERT INTO gpd_exp_budget_ledger
                        (experiment_id, action, amount_cents, currency,
                         description, idempotency_key)
                    VALUES ($1, 'reserve', $2, $3, $4, $5)
                    RETURNING id
                    """,
                    exp_uuid,
                    amount_cents,
                    currency,
                    description,
                    idempotency_key,
                )

                # Update reserved total
                await conn.execute(
                    """
                    UPDATE gpd_exp_experiments
                    SET budget_reserved_cents = budget_reserved_cents + $2,
                        updated_at = now()
                    WHERE id = $1
                    """,
                    exp_uuid,
                    amount_cents,
                )

                return str(reservation_id)

    async def confirm(
        self,
        reservation_id: str,
        experiment_id: str,
    ) -> None:
        """Convert a reservation to confirmed spend.

        Moves amount from reserved to spent: reserved -= amount, spent += amount.
        Inserts a 'confirm' ledger entry linked to the original reservation.

        Args:
            reservation_id: UUID string of the original reserve ledger entry.
            experiment_id: UUID string of the experiment.

        Raises:
            ValueError: If the reservation entry is not found.
        """
        exp_uuid = uuid.UUID(experiment_id)
        res_uuid = uuid.UUID(reservation_id)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Look up original reservation amount
                reserve_entry = await conn.fetchrow(
                    """
                    SELECT amount_cents, currency, idempotency_key
                    FROM gpd_exp_budget_ledger
                    WHERE id = $1 AND experiment_id = $2 AND action = 'reserve'
                    """,
                    res_uuid,
                    exp_uuid,
                )
                if reserve_entry is None:
                    raise ValueError(f"Reservation {reservation_id} not found for experiment {experiment_id}")

                amount = reserve_entry["amount_cents"]
                currency = reserve_entry["currency"]

                # Lock the experiment row
                await conn.fetchrow(
                    "SELECT 1 FROM gpd_exp_experiments WHERE id = $1 FOR UPDATE",
                    exp_uuid,
                )

                # Move from reserved to spent
                await conn.execute(
                    """
                    UPDATE gpd_exp_experiments
                    SET budget_reserved_cents = budget_reserved_cents - $2,
                        budget_spent_cents = budget_spent_cents + $2,
                        updated_at = now()
                    WHERE id = $1
                    """,
                    exp_uuid,
                    amount,
                )

                # Insert confirm ledger entry
                await conn.execute(
                    """
                    INSERT INTO gpd_exp_budget_ledger
                        (experiment_id, action, amount_cents, currency,
                         description, idempotency_key, reservation_id)
                    VALUES ($1, 'confirm', $2, $3, $4, $5, $6)
                    """,
                    exp_uuid,
                    amount,
                    currency,
                    f"Confirm reservation {reservation_id}",
                    f"confirm-{reservation_id}",
                    res_uuid,
                )

    async def release(
        self,
        reservation_id: str,
        experiment_id: str,
    ) -> None:
        """Release a reservation, returning funds to the available pool.

        Decreases budget_reserved_cents by the original reservation amount.
        Inserts a 'release' ledger entry.

        Args:
            reservation_id: UUID string of the original reserve ledger entry.
            experiment_id: UUID string of the experiment.

        Raises:
            ValueError: If the reservation entry is not found.
        """
        exp_uuid = uuid.UUID(experiment_id)
        res_uuid = uuid.UUID(reservation_id)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Look up original reservation amount
                reserve_entry = await conn.fetchrow(
                    """
                    SELECT amount_cents, currency
                    FROM gpd_exp_budget_ledger
                    WHERE id = $1 AND experiment_id = $2 AND action = 'reserve'
                    """,
                    res_uuid,
                    exp_uuid,
                )
                if reserve_entry is None:
                    raise ValueError(f"Reservation {reservation_id} not found for experiment {experiment_id}")

                amount = reserve_entry["amount_cents"]
                currency = reserve_entry["currency"]

                # Lock the experiment row
                await conn.fetchrow(
                    "SELECT 1 FROM gpd_exp_experiments WHERE id = $1 FOR UPDATE",
                    exp_uuid,
                )

                # Return reserved amount to pool
                await conn.execute(
                    """
                    UPDATE gpd_exp_experiments
                    SET budget_reserved_cents = budget_reserved_cents - $2,
                        updated_at = now()
                    WHERE id = $1
                    """,
                    exp_uuid,
                    amount,
                )

                # Insert release ledger entry
                await conn.execute(
                    """
                    INSERT INTO gpd_exp_budget_ledger
                        (experiment_id, action, amount_cents, currency,
                         description, idempotency_key, reservation_id)
                    VALUES ($1, 'release', $2, $3, $4, $5, $6)
                    """,
                    exp_uuid,
                    amount,
                    currency,
                    f"Release reservation {reservation_id}",
                    f"release-{reservation_id}",
                    res_uuid,
                )

    async def refund(
        self,
        experiment_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        idempotency_key: str,
    ) -> str:
        """Refund a previously confirmed spend.

        Decreases budget_spent_cents and inserts a 'refund' ledger entry.

        Args:
            experiment_id: UUID string of the experiment.
            amount_cents: Amount to refund in integer cents.
            currency: Currency code (e.g. "USD").
            description: Human-readable description for the audit trail.
            idempotency_key: Unique key to prevent duplicate refunds.

        Returns:
            The refund entry id (UUID string).

        Raises:
            ValueError: If the experiment does not exist.
        """
        exp_uuid = uuid.UUID(experiment_id)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Check for existing entry with same idempotency key
                existing = await conn.fetchrow(
                    """
                    SELECT id FROM gpd_exp_budget_ledger
                    WHERE experiment_id = $1 AND idempotency_key = $2
                    """,
                    exp_uuid,
                    idempotency_key,
                )
                if existing is not None:
                    return str(existing["id"])

                # Lock the experiment row
                row = await conn.fetchrow(
                    """
                    SELECT budget_spent_cents
                    FROM gpd_exp_experiments
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    exp_uuid,
                )
                if row is None:
                    raise ValueError(f"Experiment {experiment_id} not found")

                # Decrease spent
                await conn.execute(
                    """
                    UPDATE gpd_exp_experiments
                    SET budget_spent_cents = budget_spent_cents - $2,
                        updated_at = now()
                    WHERE id = $1
                    """,
                    exp_uuid,
                    amount_cents,
                )

                # Insert refund ledger entry
                refund_id = await conn.fetchval(
                    """
                    INSERT INTO gpd_exp_budget_ledger
                        (experiment_id, action, amount_cents, currency,
                         description, idempotency_key)
                    VALUES ($1, 'refund', $2, $3, $4, $5)
                    RETURNING id
                    """,
                    exp_uuid,
                    amount_cents,
                    currency,
                    description,
                    idempotency_key,
                )

                return str(refund_id)
