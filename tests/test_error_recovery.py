"""Tests for the four-tier error recovery chain: retry -> simplify -> substitute -> skip."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gpd.mcp.research.error_recovery import (
    execute_milestone_with_recovery,
    execute_tool_call,
    find_substitute_tool,
    make_retry_decorator,
    simplify_milestone,
)
from gpd.mcp.research.schemas import (
    ResearchMilestone,
    RetryPolicy,
)


def _make_milestone(
    milestone_id: str = "ms-1",
    tools: list[str] | None = None,
    is_critical: bool = True,
    max_retries: int = 2,
) -> ResearchMilestone:
    """Helper to create a milestone for testing."""
    return ResearchMilestone(
        milestone_id=milestone_id,
        description=f"Test milestone {milestone_id}",
        tools=tools or ["tool_a"],
        is_critical=is_critical,
        retry_policy=RetryPolicy(max_retries=max_retries, backoff_base=1.0, backoff_max=1.0, jitter=False),
    )


class TestMakeRetryDecorator:
    """Test make_retry_decorator builds a callable that retries on expected errors."""

    def test_produces_callable(self) -> None:
        policy = RetryPolicy(max_retries=2)
        decorator = make_retry_decorator(policy)
        assert callable(decorator)

    async def test_retries_on_timeout_error(self) -> None:
        """Verify the decorator retries on TimeoutError then succeeds."""
        policy = RetryPolicy(max_retries=3, backoff_base=1.0, backoff_max=1.0, jitter=False)
        decorator = make_retry_decorator(policy)

        call_count = 0

        @decorator
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("transient")
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 3

    async def test_exhausts_retries_and_reraises(self) -> None:
        """Verify the decorator reraises after max_retries + 1 attempts."""
        policy = RetryPolicy(max_retries=1, backoff_base=1.0, backoff_max=1.0, jitter=False)
        decorator = make_retry_decorator(policy)

        call_count = 0

        @decorator
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("permanent")

        with pytest.raises(TimeoutError, match="permanent"):
            await always_fails()
        # max_retries=1 means stop_after_attempt(2): first try + 1 retry = 2 calls
        assert call_count == 2


class TestExecuteToolCall:
    """Test execute_tool_call delegates to the tool_router."""

    async def test_calls_router_with_args(self) -> None:
        router = AsyncMock(return_value={"data": "result"})
        result = await execute_tool_call("my_tool", {"param": 1}, router)
        router.assert_awaited_once_with("my_tool", {"param": 1})
        assert result == {"data": "result"}


class TestSimplifyMilestone:
    """Test simplify_milestone produces a simplified milestone or None."""

    async def test_returns_simplified_milestone(self) -> None:
        milestone = _make_milestone()
        simplified = ResearchMilestone(
            milestone_id="ms-1",
            description="Simplified test milestone ms-1",
            tools=["tool_a"],
            expected_outputs=["reduced output"],
        )

        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = simplified
        mock_agent.run = AsyncMock(return_value=mock_result)

        result = await simplify_milestone(milestone, planner_agent=mock_agent)
        assert result is not None
        assert "Simplified" in result.description

    async def test_returns_none_when_unchanged(self) -> None:
        milestone = _make_milestone()
        # Agent returns exactly the same milestone
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = milestone.model_copy()
        mock_agent.run = AsyncMock(return_value=mock_result)

        result = await simplify_milestone(milestone, planner_agent=mock_agent)
        assert result is None


class TestFindSubstituteTool:
    """Test find_substitute_tool returns substitute or None."""

    async def test_returns_substitute_milestone(self) -> None:
        milestone = _make_milestone(tools=["broken_tool"])
        substitute = ResearchMilestone(
            milestone_id="ms-1",
            description="Test milestone ms-1",
            tools=["alternative_tool"],
        )

        with patch("gpd.mcp.research.error_recovery.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.output = substitute
            mock_instance.run = AsyncMock(return_value=mock_result)
            MockAgent.return_value = mock_instance

            result = await find_substitute_tool(
                milestone, [{"name": "alternative_tool", "description": "An alternative"}]
            )
            assert result is not None
            assert result.tools == ["alternative_tool"]

    async def test_returns_none_when_no_substitute(self) -> None:
        milestone = _make_milestone(tools=["broken_tool"])
        # Agent returns milestone with empty tools
        no_sub = ResearchMilestone(
            milestone_id="ms-1",
            description="Test milestone ms-1",
            tools=[],
        )

        with patch("gpd.mcp.research.error_recovery.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.output = no_sub
            mock_instance.run = AsyncMock(return_value=mock_result)
            MockAgent.return_value = mock_instance

            result = await find_substitute_tool(milestone, [])
            assert result is None

    async def test_returns_none_when_same_tools(self) -> None:
        milestone = _make_milestone(tools=["broken_tool"])
        same_tools = ResearchMilestone(
            milestone_id="ms-1",
            description="Test milestone ms-1",
            tools=["broken_tool"],
        )

        with patch("gpd.mcp.research.error_recovery.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.output = same_tools
            mock_instance.run = AsyncMock(return_value=mock_result)
            MockAgent.return_value = mock_instance

            result = await find_substitute_tool(milestone, [])
            assert result is None


class TestExecuteMilestoneWithRecovery:
    """Test the full recovery chain: retry -> simplify -> substitute -> skip."""

    async def test_success_on_first_attempt(self) -> None:
        milestone = _make_milestone(max_retries=0)
        router = AsyncMock(return_value={"data": "ok"})

        result = await execute_milestone_with_recovery(milestone, {}, router)

        assert not result.is_error
        assert result.attempt_count == 1
        assert len(result.tool_outputs) == 1

    async def test_success_after_retries(self) -> None:
        """Tool fails twice then succeeds -- verify attempt_count=3."""
        milestone = _make_milestone(max_retries=3)
        call_count = 0

        async def flaky_router(tool_name, args):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("transient")
            return {"data": "recovered"}

        result = await execute_milestone_with_recovery(milestone, {}, flaky_router)

        assert not result.is_error
        assert result.attempt_count == 3
        assert result.tool_outputs == [{"data": "recovered"}]

    async def test_simplify_fallback(self) -> None:
        """All retries fail, simplify succeeds."""
        milestone = _make_milestone(max_retries=0)
        AsyncMock(side_effect=TimeoutError("fail"))
        AsyncMock(return_value={"data": "simplified_result"})

        simplified = ResearchMilestone(
            milestone_id="ms-1",
            description="Simplified milestone",
            tools=["tool_a"],
            expected_outputs=["simple output"],
        )

        with patch("gpd.mcp.research.error_recovery.simplify_milestone", new_callable=AsyncMock) as mock_simplify:
            mock_simplify.return_value = simplified

            # Router fails on first call (original), succeeds on second (simplified)
            call_count = 0

            async def staged_router(tool_name, args):
                nonlocal call_count
                call_count += 1
                if call_count <= 1:
                    raise TimeoutError("original fails")
                return {"data": "simplified_ok"}

            result = await execute_milestone_with_recovery(milestone, {}, staged_router)

            assert not result.is_error
            assert "simplified" in result.result_summary.lower()

    async def test_substitute_fallback(self) -> None:
        """Retries fail, simplify returns None, substitute succeeds."""
        milestone = _make_milestone(max_retries=0)

        substitute_ms = ResearchMilestone(
            milestone_id="ms-1",
            description="Substitute milestone",
            tools=["alt_tool"],
        )

        call_count = 0

        async def staged_router(tool_name, args):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise TimeoutError("original fails")
            return {"data": "substitute_ok"}

        with (
            patch("gpd.mcp.research.error_recovery.simplify_milestone", new_callable=AsyncMock) as mock_simplify,
            patch("gpd.mcp.research.error_recovery.find_substitute_tool", new_callable=AsyncMock) as mock_substitute,
        ):
            mock_simplify.return_value = None
            mock_substitute.return_value = substitute_ms

            result = await execute_milestone_with_recovery(milestone, {}, staged_router)

            assert not result.is_error
            assert "substitute" in result.result_summary.lower()

    async def test_full_exhaustion(self) -> None:
        """All strategies fail -- verify is_error=True, error_type=all_recovery_exhausted."""
        milestone = _make_milestone(max_retries=0)
        router = AsyncMock(side_effect=TimeoutError("permanent"))

        with (
            patch("gpd.mcp.research.error_recovery.simplify_milestone", new_callable=AsyncMock) as mock_simplify,
            patch("gpd.mcp.research.error_recovery.find_substitute_tool", new_callable=AsyncMock) as mock_substitute,
        ):
            mock_simplify.return_value = None
            mock_substitute.return_value = None

            result = await execute_milestone_with_recovery(milestone, {}, router)

            assert result.is_error
            assert result.error_type == "all_recovery_exhausted"
            assert result.attempt_count >= 1

    async def test_dashboard_callback_called(self) -> None:
        """Verify dashboard_callback fires at each recovery phase with consistent 3-arg signature."""
        milestone = _make_milestone(max_retries=0)
        router = AsyncMock(side_effect=TimeoutError("fail"))
        callback = MagicMock()

        with (
            patch("gpd.mcp.research.error_recovery.simplify_milestone", new_callable=AsyncMock) as mock_simplify,
            patch("gpd.mcp.research.error_recovery.find_substitute_tool", new_callable=AsyncMock) as mock_substitute,
        ):
            mock_simplify.return_value = None
            mock_substitute.return_value = None

            await execute_milestone_with_recovery(milestone, {}, router, dashboard_callback=callback)

            # Verify callback was called with each phase name
            phase_names = [call.args[0] for call in callback.call_args_list]
            assert "attempt" in phase_names
            assert "simplify" in phase_names
            assert "substitute" in phase_names
            assert "exhausted" in phase_names

            # All calls must use uniform 3-arg signature: (phase, milestone, info_dict)
            for call in callback.call_args_list:
                assert len(call.args) == 3, (
                    f"dashboard_callback called with {len(call.args)} args "
                    f"(expected 3) for phase '{call.args[0]}'"
                )
                assert isinstance(call.args[2], dict), (
                    f"third arg must be a dict, got {type(call.args[2]).__name__} "
                    f"for phase '{call.args[0]}'"
                )

    async def test_non_critical_milestone_failure_returns_skippable_result(self) -> None:
        """Non-critical milestone failure returns is_error=True but allows continuation."""
        milestone = _make_milestone(is_critical=False, max_retries=0)
        router = AsyncMock(side_effect=TimeoutError("fail"))

        with (
            patch("gpd.mcp.research.error_recovery.simplify_milestone", new_callable=AsyncMock) as mock_simplify,
            patch("gpd.mcp.research.error_recovery.find_substitute_tool", new_callable=AsyncMock) as mock_substitute,
        ):
            mock_simplify.return_value = None
            mock_substitute.return_value = None

            result = await execute_milestone_with_recovery(milestone, {}, router)

            # is_error=True signals failure, but the executor decides whether to halt
            # based on milestone.is_critical -- error_recovery just reports the failure
            assert result.is_error
            assert result.error_type == "all_recovery_exhausted"
