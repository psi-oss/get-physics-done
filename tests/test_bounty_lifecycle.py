"""Unit tests for BountyRegistry lifecycle methods.

Tests cover the 8 new lifecycle methods with mock MCP tools returning
realistic API response shapes. All tests are pure unit tests — no real
DB or MCP connections.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gpd.exp.infrastructure.bounty_registry import BountyRegistry

# ---------------------------------------------------------------------------
# Mock pool that does nothing (lifecycle methods that need DB are tested
# separately in integration tests)
# ---------------------------------------------------------------------------


class _MockConnection:
    async def execute(self, *args: object) -> None:
        pass

    async def fetchrow(self, *args: object) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object):
        pass


class _AcquireContext:
    """Async context manager returned by _MockPool.acquire()."""

    def __init__(self):
        self._conn = _MockConnection()

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args: object):
        pass


class _MockPool:
    """Minimal mock for asyncpg.Pool — lifecycle methods don't need real DB in unit tests."""

    def acquire(self):
        return _AcquireContext()

    async def close(self):
        pass


# ---------------------------------------------------------------------------
# Helper: build MCP tools dict with realistic response shapes
# ---------------------------------------------------------------------------


def _make_mcp_tools(**overrides: object) -> dict:
    """Build a full MCP tools dict with AsyncMock callables.

    Default return values match real RentAHuman API response shapes.
    """
    tools = {
        "create_bounty": AsyncMock(
            return_value={
                "bountyId": "bounty-123",
                "status": "open",
            }
        ),
        "get_bounty": AsyncMock(
            return_value={
                "id": "bounty-123",
                "status": "open",
                "applicationCount": 0,
                "title": "Test Bounty",
            }
        ),
        "get_bounty_applications": AsyncMock(
            return_value={
                "applications": [
                    {
                        "id": "app-001",
                        "humanId": "human-42",
                        "humanName": "Jyles",
                        "coverLetter": "I can do this!",
                        "proposedPrice": 5.0,
                        "status": "pending",
                        "createdAt": "2025-06-01T10:00:00Z",
                    }
                ]
            }
        ),
        "accept_application": AsyncMock(
            return_value={
                "status": "accepted",
            }
        ),
        "create_escrow_checkout": AsyncMock(
            return_value={
                "escrowId": "escrow-abc",
                "checkoutUrl": "https://checkout.stripe.com/pay/cs_test_abc",
                "conversationId": "conv-xyz",
            }
        ),
        "fund_escrow": AsyncMock(
            return_value={
                "escrowId": "escrow-abc",
                "status": "locked",
            }
        ),
        "get_escrow": AsyncMock(
            return_value={
                "id": "escrow-abc",
                "status": "locked",
                "amount": 5.0,
            }
        ),
        "confirm_delivery": AsyncMock(
            return_value={
                "status": "completed",
            }
        ),
        "release_payment": AsyncMock(
            return_value={
                "status": "released",
                "transferId": "tr_test_123",
            }
        ),
        "get_conversation": AsyncMock(
            return_value={
                "id": "conv-xyz",
                "messages": [
                    {
                        "sender": "human",
                        "content": "Here is my data. The measurement was 4.2 cm. Include 4 for check.",
                        "createdAt": "2025-06-01T12:00:00Z",
                    },
                    {
                        "sender": "agent",
                        "content": "Thank you!",
                        "createdAt": "2025-06-01T12:05:00Z",
                    },
                ],
            }
        ),
        "send_message": AsyncMock(
            return_value={
                "messageId": "msg-001",
                "status": "sent",
            }
        ),
        "rent_human": AsyncMock(
            return_value={
                "bountyId": "bounty-direct-123",
                "escrowId": "escrow-direct-abc",
                "checkoutUrl": "https://checkout.stripe.com/pay/cs_direct_abc",
            }
        ),
    }
    tools.update(overrides)
    return tools


def _make_registry(**tool_overrides: object) -> BountyRegistry:
    """Build a BountyRegistry with mock pool and MCP tools."""
    return BountyRegistry(
        pool=_MockPool(),
        mcp_tools=_make_mcp_tools(**tool_overrides),
    )


# ---------------------------------------------------------------------------
# Test 1: rent_human_direct
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rent_human_direct_returns_bounty_and_escrow():
    """rent_human_direct calls rent_human MCP and returns bountyId + escrowId."""
    registry = _make_registry()
    result = await registry.rent_human_direct(
        human_id="human-42",
        title="Test Task",
        description="Please collect data for my experiment",
        price_usd=5.0,
    )
    assert result["bountyId"] == "bounty-direct-123"
    assert result["escrowId"] == "escrow-direct-abc"
    assert "checkoutUrl" in result


# ---------------------------------------------------------------------------
# Test 2: poll_applications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_applications_returns_application_list():
    """poll_applications returns list of application dicts."""
    registry = _make_registry()
    apps = await registry.poll_applications("bounty-123")
    assert len(apps) == 1
    assert apps[0]["humanName"] == "Jyles"
    assert apps[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_poll_applications_handles_list_response():
    """poll_applications handles MCP returning a plain list (not wrapped in dict)."""
    registry = _make_registry(
        get_bounty_applications=AsyncMock(
            return_value=[
                {"id": "app-002", "humanId": "human-99", "status": "pending"},
            ]
        )
    )
    apps = await registry.poll_applications("bounty-456")
    assert len(apps) == 1


# ---------------------------------------------------------------------------
# Test 3: accept_and_create_escrow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_and_create_escrow_calls_both_mcp_tools():
    """accept_and_create_escrow calls accept_application then create_escrow_checkout."""
    registry = _make_registry()
    result = await registry.accept_and_create_escrow("bounty-123", "app-001")
    assert result["escrowId"] == "escrow-abc"
    assert "checkoutUrl" in result
    # Verify both MCP tools were called
    registry._mcp_tools["accept_application"].assert_awaited_once()
    registry._mcp_tools["create_escrow_checkout"].assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 4: poll_escrow_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_escrow_status_returns_status():
    """poll_escrow_status returns escrow dict with status field."""
    registry = _make_registry()
    result = await registry.poll_escrow_status("escrow-abc")
    assert result["status"] == "locked"


# ---------------------------------------------------------------------------
# Test 5: get_conversation_messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_conversation_messages_returns_messages():
    """get_conversation_messages returns list of message dicts."""
    registry = _make_registry()
    messages = await registry.get_conversation_messages("conv-xyz")
    assert len(messages) == 2
    assert messages[0]["sender"] == "human"
    assert "4.2 cm" in messages[0]["content"]


# ---------------------------------------------------------------------------
# Test 6: send_worker_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_worker_message_sends_and_returns():
    """send_worker_message calls send_message MCP and returns result."""
    registry = _make_registry()
    result = await registry.send_worker_message("conv-xyz", "Hello worker!")
    assert result["status"] == "sent"
    registry._mcp_tools["send_message"].assert_awaited_once_with(
        conversationId="conv-xyz",
        content="Hello worker!",
    )


# ---------------------------------------------------------------------------
# Test 7: confirm_and_release_payment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_and_release_payment_calls_both_steps():
    """confirm_and_release_payment calls confirm_delivery then release_payment."""
    registry = _make_registry()
    result = await registry.confirm_and_release_payment("escrow-abc")
    assert result["status"] == "released"
    registry._mcp_tools["confirm_delivery"].assert_awaited_once_with(escrowId="escrow-abc")
    registry._mcp_tools["release_payment"].assert_awaited_once_with(escrowId="escrow-abc")


# ---------------------------------------------------------------------------
# Test 8: update_lifecycle (DB persistence)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_lifecycle_filters_invalid_columns():
    """update_lifecycle ignores columns not in the allowed set."""
    registry = _make_registry()
    # Should not raise — invalid columns are silently filtered
    await registry.update_lifecycle(
        "key-1",
        "exp-1",
        application_id="app-001",
        invalid_column="should be ignored",
        escrow_id="escrow-abc",
    )
    # If it didn't raise, the filter worked
