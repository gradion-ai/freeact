import asyncio
import contextlib
from enum import Enum

from freeact.events import ApprovalRequest
from freeact.toolcalls import ToolCall


class CancelToken:
    """Cooperative cancellation signal shared across a turn's components."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def set(self) -> None:
        self._event.set()

    def clear(self) -> None:
        self._event.clear()

    def is_set(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()


class Decision(Enum):
    """Outcome of an approval request."""

    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def approved(self) -> bool:
        return self is Decision.APPROVED


class ApprovalGate:
    """The single mechanism through which all approvals flow.

    Creates [`ApprovalRequest`][freeact.ApprovalRequest] events and resolves
    them by racing the consumer's decision against cancellation and the
    configured approval timeout. Guarantees exactly-once resolution: a
    request resolved by cancellation or timeout ignores later `approve()`
    calls, and vice versa.
    """

    def __init__(self, *, agent_id: str, cancel: CancelToken, timeout: float | None = None) -> None:
        self._agent_id = agent_id
        self._cancel = cancel
        self._timeout = timeout

    def create(self, tool_call: ToolCall, corr_id: str = "", parent_corr_id: str = "") -> ApprovalRequest:
        """Create an approval request event for a tool call."""
        return ApprovalRequest(
            tool_call=tool_call,
            agent_id=self._agent_id,
            corr_id=corr_id,
            parent_corr_id=parent_corr_id,
        )

    async def decide(self, request: ApprovalRequest) -> Decision:
        """Wait for the request to be resolved, cancelled, or timed out.

        On cancellation or timeout the request itself is resolved as
        rejected, so any other waiter on the same request observes a
        consistent decision.
        """
        cancel_waiter = asyncio.ensure_future(self._cancel.wait())
        approval_waiter = asyncio.ensure_future(request.approved())
        try:
            done, _ = await asyncio.wait(
                [cancel_waiter, approval_waiter],
                timeout=self._timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            # Resolve the request BEFORE reaping the approval waiter:
            # cancelling a task that awaits the request's future would
            # cancel the future itself, making later approved() calls
            # raise instead of returning the decision. This also covers
            # abandonment (GeneratorExit when the consumer closes the
            # event stream): the pending request resolves as rejected so
            # no other waiter hangs.
            if not approval_waiter.done():
                request.approve(False)
            with contextlib.suppress(asyncio.CancelledError):
                await approval_waiter
            if not cancel_waiter.done():
                cancel_waiter.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await cancel_waiter

        if approval_waiter in done:
            return Decision.APPROVED if approval_waiter.result() else Decision.REJECTED
        if cancel_waiter in done:
            return Decision.CANCELLED
        return Decision.TIMED_OUT

    @staticmethod
    def resolve_rejected(request: ApprovalRequest) -> None:
        """Resolve a pending request as rejected (no-op if already resolved).

        Used when the consumer abandons the event stream while a request
        is pending, so nothing upstream stays blocked.
        """
        request.approve(False)
