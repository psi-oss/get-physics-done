"""Idempotent bounty registry backed by PostgreSQL and rent-a-human MCP.

BountyRegistry provides crash-safe, idempotent bounty posting against the
gpd_exp_bounties table. Every call to post_idempotent checks local state
before calling the MCP API, preventing duplicate real-world bounties on
crash recovery.

Full lifecycle support:
- post_idempotent: Create bounty on platform
- poll_applications / accept_and_create_escrow: Handle worker applications
- poll_escrow_status: Track escrow funding
- get_conversation_messages / send_worker_message: Worker communication
- confirm_and_release_payment: Complete the lifecycle
- rent_human_direct: One-step hire shortcut
- update_lifecycle: Persist lifecycle state transitions to DB

Safety guarantees:
- Idempotent: A second call with the same (experiment_id, idempotency_key)
  returns the cached platform_bounty_id without a second API call.
- Crash-safe: An orphaned draft (platform_bounty_id IS NULL) is deleted and
  re-posted on the next call.
- Conversion: price_cents is always divided by 100 before passing to the MCP
  (result is a USD float like 5.0 for $5, never raw integer cents).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import asyncpg
import structlog
from mcp.shared.exceptions import McpError

from gpd.exp.contracts.bounty import BountyRecord

logger = structlog.get_logger(__name__)


class BountyPlatformUnavailableError(Exception):
    """Raised when rent-a-human MCP signals subscription or availability issue."""


class BountyRegistry:
    """Idempotent bounty posting, polling, lifecycle management, and status update.

    Wraps the gpd_exp_bounties table and the rent-a-human MCP tools.
    All methods are async and safe to call from multiple coroutines.

    Args:
        pool: An asyncpg connection pool.
        mcp_tools: Dict of MCP tool callables keyed by tool name.
            Required keys: "create_bounty", "get_bounty",
            "get_bounty_applications", "accept_application".
            Lifecycle keys: "create_escrow_checkout", "fund_escrow",
            "get_escrow", "confirm_delivery", "release_payment",
            "get_conversation", "send_message", "rent_human".
            Each value is an async callable.
    """

    def __init__(self, pool: asyncpg.Pool, mcp_tools: dict) -> None:
        self._pool = pool
        self._mcp_tools = mcp_tools

    async def post_idempotent(self, bounty_record: BountyRecord) -> str:
        """Post a bounty idempotently, returning the platform_bounty_id.

        Idempotency protocol (exact sequence):
        1. Query gpd_exp_bounties for (idempotency_key, experiment_id).
        2. If found with platform_bounty_id: return cached ID (no API call).
        3. If found with platform_bounty_id IS NULL: delete orphaned draft,
           fall through to fresh post.
        4. Insert draft row with ON CONFLICT upsert.
        5. Call create_bounty MCP tool with price as USD float (cents / 100).
        6. Subscription/lapsed errors -> BountyPlatformUnavailableError.
        7. Extract platform_id from response dict.
        8. UPDATE row with platform_bounty_id and status='posted'.
        9. Return platform_id.

        Args:
            bounty_record: Full bounty record including idempotency_key and spec.

        Returns:
            The platform_bounty_id string from the rent-a-human MCP.

        Raises:
            BountyPlatformUnavailableError: If the MCP signals subscription lapsed.
            ValueError: If the MCP response is missing a bounty ID field.
        """
        idempotency_key = bounty_record.idempotency_key
        experiment_id = bounty_record.experiment_id

        log = logger.bind(
            idempotency_key=idempotency_key,
            experiment_id=str(experiment_id),
        )

        async with self._pool.acquire() as conn:
            # Step 1: Query for existing row
            existing = await conn.fetchrow(
                """
                SELECT platform_bounty_id
                FROM gpd_exp_bounties
                WHERE idempotency_key = $1 AND experiment_id = $2
                """,
                idempotency_key,
                experiment_id,
            )

            # Step 2: Already posted successfully — return cached ID
            if existing is not None and existing["platform_bounty_id"] is not None:
                log.info("bounty.idempotent_hit", platform_bounty_id=existing["platform_bounty_id"])
                return existing["platform_bounty_id"]

            # Step 3: Orphaned draft — crash recovery path, delete and re-post
            if existing is not None and existing["platform_bounty_id"] is None:
                log.warning("bounty.orphaned_draft_found", action="deleting_and_reposting")
                await conn.execute(
                    """
                    DELETE FROM gpd_exp_bounties
                    WHERE idempotency_key = $1 AND experiment_id = $2
                    """,
                    idempotency_key,
                    experiment_id,
                )

            # Step 4: Insert draft row
            await conn.execute(
                """
                INSERT INTO gpd_exp_bounties
                    (id, experiment_id, idempotency_key, status, price_cents,
                     task_description, deadline_utc)
                VALUES ($1, $2, $3, 'draft', $4, $5, $6)
                ON CONFLICT (experiment_id, idempotency_key)
                DO UPDATE SET status = 'draft', updated_at = now()
                """,
                bounty_record.id,
                experiment_id,
                idempotency_key,
                bounty_record.amount_cents,
                bounty_record.specification.description,
                bounty_record.specification.deadline,
            )
            log.info("bounty.draft_inserted")

        # Step 5: Call create_bounty MCP tool (outside connection context)
        spec = bounty_record.specification

        if spec.deadline is not None:
            now_utc = datetime.now(tz=UTC)
            hours_remaining = (spec.deadline - now_utc).total_seconds() / 3600
            estimated_hours = max(0.5, hours_remaining)
        else:
            estimated_hours = 1.0

        # CRITICAL: price is USD float (cents / 100), never raw integer cents
        price_usd = bounty_record.specification.price_cents / 100

        create_kwargs: dict = {
            "agentType": "other",
            "title": spec.title,
            "description": spec.description,
            "estimatedHours": estimated_hours,
            "priceType": "fixed",
            "price": price_usd,
            "category": "physical-tasks",
            "skillsNeeded": spec.skills_needed,
            "requirements": spec.requirements,
            "location": {"isRemoteAllowed": True},
            "spotsAvailable": spec.spots_available,
        }
        if spec.deadline is not None:
            create_kwargs["deadline"] = spec.deadline.isoformat()

        log.info("bounty.calling_create_bounty", price_usd=price_usd)
        try:
            result = await self._mcp_tools["create_bounty"](**create_kwargs)
        except McpError as exc:
            msg = str(exc).lower()
            if "subscription" in msg or "lapsed" in msg:
                log.error("bounty.platform_unavailable", error=str(exc))
                raise BountyPlatformUnavailableError(str(exc)) from exc
            raise

        # Step 7: Extract platform_id from response
        platform_id = result.get("bountyId") or result.get("id") or result.get("bounty_id")
        if platform_id is None:
            raise ValueError(f"create_bounty response missing bounty ID field. Response keys: {list(result.keys())}")

        log.info("bounty.created", platform_bounty_id=platform_id)

        # Step 8: Update row with platform_bounty_id and status='posted'
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE gpd_exp_bounties
                SET platform_bounty_id = $1, status = 'posted', updated_at = now()
                WHERE idempotency_key = $2 AND experiment_id = $3
                """,
                platform_id,
                idempotency_key,
                experiment_id,
            )

        return platform_id

    async def get_status(self, platform_bounty_id: str) -> dict:
        """Fetch current status of a posted bounty from the MCP platform.

        Args:
            platform_bounty_id: The platform-assigned bounty ID returned by
                post_idempotent.

        Returns:
            Raw response dict from get_bounty MCP tool. Callers extract
            status, resultData, acceptedAt, completedAt, workerId fields.
        """
        return await self._mcp_tools["get_bounty"](bountyId=platform_bounty_id)

    async def update_local_status(
        self,
        idempotency_key: str,
        experiment_id: str,
        status: str,
        result_data: dict | None = None,
    ) -> None:
        """Update the local gpd_exp_bounties row status and result data.

        Args:
            idempotency_key: Idempotency key identifying the bounty row.
            experiment_id: Experiment UUID string.
            status: New status string (e.g. "completed", "failed").
            result_data: Optional dict to store as JSONB result_data column.
        """
        result_json = json.dumps(result_data) if result_data is not None else None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE gpd_exp_bounties
                SET status = $1, result_data = $2::jsonb, updated_at = now()
                WHERE idempotency_key = $3 AND experiment_id = $4
                """,
                status,
                result_json,
                idempotency_key,
                experiment_id,
            )
        logger.info(
            "bounty.local_status_updated",
            idempotency_key=idempotency_key,
            experiment_id=experiment_id,
            status=status,
        )

    # ------------------------------------------------------------------
    # Full RentAHuman lifecycle methods
    # ------------------------------------------------------------------

    async def rent_human_direct(
        self,
        human_id: str,
        title: str,
        description: str,
        price_usd: float,
    ) -> dict:
        """Hire a human in one step via rent_human MCP tool.

        Creates bounty + escrow atomically. Returns dict with bountyId,
        escrowId, checkoutUrl (operator must visit to fund).

        Args:
            human_id: RentAHuman human ID.
            title: Task title (5-200 chars).
            description: Task description (10+ chars).
            price_usd: Price in USD (not cents).

        Returns:
            Dict with keys: bountyId, escrowId, checkoutUrl, and any
            additional fields from the MCP response.
        """
        result = await self._mcp_tools["rent_human"](
            humanId=human_id,
            taskTitle=title,
            taskDescription=description,
            price=price_usd,
        )
        logger.info(
            "bounty.rent_human_direct",
            human_id=human_id,
            bounty_id=result.get("bountyId"),
            escrow_id=result.get("escrowId"),
        )
        return result

    async def poll_applications(self, platform_bounty_id: str) -> list[dict]:
        """Fetch applications for a bounty.

        Args:
            platform_bounty_id: The platform-assigned bounty ID.

        Returns:
            List of application dicts with keys like: id, humanId, humanName,
            coverLetter, proposedPrice, status, createdAt.
        """
        result = await self._mcp_tools["get_bounty_applications"](
            bountyId=platform_bounty_id,
        )
        applications = result if isinstance(result, list) else result.get("applications", [])
        logger.info(
            "bounty.poll_applications",
            platform_bounty_id=platform_bounty_id,
            count=len(applications),
        )
        return applications

    async def accept_and_create_escrow(
        self,
        bounty_id: str,
        application_id: str,
    ) -> dict:
        """Accept an application and create an escrow checkout.

        Calls accept_application then create_escrow_checkout. The returned
        checkoutUrl must be visited by the operator to fund the escrow.

        Args:
            bounty_id: Platform bounty ID.
            application_id: Application ID to accept.

        Returns:
            Dict with escrowId, checkoutUrl, and any additional MCP fields.
        """
        # Accept the application first
        await self._mcp_tools["accept_application"](
            bountyId=bounty_id,
            applicationId=application_id,
        )
        logger.info(
            "bounty.application_accepted",
            bounty_id=bounty_id,
            application_id=application_id,
        )

        # Create escrow checkout for the accepted application
        escrow_result = await self._mcp_tools["create_escrow_checkout"](
            bountyId=bounty_id,
            applicationId=application_id,
        )
        logger.info(
            "bounty.escrow_checkout_created",
            bounty_id=bounty_id,
            escrow_id=escrow_result.get("escrowId"),
            checkout_url=escrow_result.get("checkoutUrl"),
        )
        return escrow_result

    async def poll_escrow_status(self, escrow_id: str) -> dict:
        """Fetch the current status of an escrow.

        Args:
            escrow_id: The escrow ID from accept_and_create_escrow.

        Returns:
            Escrow dict with status field ("funding", "funded", "locked",
            "delivered", "completed", "released", "cancelled").
        """
        result = await self._mcp_tools["get_escrow"](escrowId=escrow_id)
        logger.info(
            "bounty.poll_escrow",
            escrow_id=escrow_id,
            status=result.get("status"),
        )
        return result

    async def get_conversation_messages(self, conversation_id: str) -> list[dict]:
        """Fetch all messages in a conversation.

        Args:
            conversation_id: RentAHuman conversation ID.

        Returns:
            List of message dicts with keys: sender, content, createdAt, etc.
        """
        result = await self._mcp_tools["get_conversation"](
            conversationId=conversation_id,
        )
        messages = result.get("messages", []) if isinstance(result, dict) else []
        logger.info(
            "bounty.get_conversation",
            conversation_id=conversation_id,
            message_count=len(messages),
        )
        return messages

    async def send_worker_message(
        self,
        conversation_id: str,
        content: str,
    ) -> dict:
        """Send a message to a worker in a conversation.

        Args:
            conversation_id: RentAHuman conversation ID.
            content: Message text to send.

        Returns:
            Message dict from the MCP response.
        """
        result = await self._mcp_tools["send_message"](
            conversationId=conversation_id,
            content=content,
        )
        logger.info(
            "bounty.message_sent",
            conversation_id=conversation_id,
        )
        return result

    async def confirm_and_release_payment(self, escrow_id: str) -> dict:
        """Confirm delivery and release payment to the worker.

        Two-step process: confirm_delivery transitions escrow to "completed",
        then release_payment sends funds to the worker's bank account.

        Args:
            escrow_id: The escrow ID to confirm and release.

        Returns:
            Dict with release confirmation from the MCP.
        """
        await self._mcp_tools["confirm_delivery"](escrowId=escrow_id)
        logger.info("bounty.delivery_confirmed", escrow_id=escrow_id)

        release_result = await self._mcp_tools["release_payment"](escrowId=escrow_id)
        logger.info("bounty.payment_released", escrow_id=escrow_id)
        return release_result

    async def update_lifecycle(
        self,
        idempotency_key: str,
        experiment_id: str,
        **lifecycle_fields: object,
    ) -> None:
        """Persist lifecycle state transitions to the gpd_exp_bounties DB row.

        Updates any combination of lifecycle columns: application_id, escrow_id,
        conversation_id, checkout_url, human_id, human_name, escrow_status,
        delivery_evidence, status.

        Args:
            idempotency_key: Idempotency key identifying the bounty row.
            experiment_id: Experiment UUID string.
            **lifecycle_fields: Column name → value pairs to update.
        """
        allowed_columns = {
            "application_id",
            "escrow_id",
            "conversation_id",
            "checkout_url",
            "human_id",
            "human_name",
            "escrow_status",
            "delivery_evidence",
            "status",
            "result_data",
        }
        updates = {k: v for k, v in lifecycle_fields.items() if k in allowed_columns}
        if not updates:
            return

        # Build SET clause dynamically
        set_parts: list[str] = []
        values: list[object] = []
        for i, (col, val) in enumerate(updates.items(), start=1):
            if col in ("delivery_evidence", "result_data"):
                set_parts.append(f"{col} = ${i}::jsonb")
                values.append(json.dumps(val) if val is not None else None)
            else:
                set_parts.append(f"{col} = ${i}")
                values.append(val)
        set_parts.append("updated_at = now()")

        n = len(values)
        values.extend([idempotency_key, experiment_id])

        sql = f"""
            UPDATE gpd_exp_bounties
            SET {", ".join(set_parts)}
            WHERE idempotency_key = ${n + 1} AND experiment_id = ${n + 2}
        """

        async with self._pool.acquire() as conn:
            await conn.execute(sql, *values)

        logger.info(
            "bounty.lifecycle_updated",
            idempotency_key=idempotency_key,
            experiment_id=experiment_id,
            fields=list(updates.keys()),
        )
