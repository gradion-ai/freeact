# Covers behavior-inventory.md sections: 5 (approvals), 6 (cancellation racing)
import asyncio

import pytest

from freeact.agent.approvals import ApprovalGate, CancelToken, Decision
from freeact.events import ApprovalRequest
from freeact.toolcalls import CodeAction


def make_gate(timeout: float | None = None) -> tuple[ApprovalGate, CancelToken]:
    cancel = CancelToken()
    gate = ApprovalGate(agent_id="main", cancel=cancel, timeout=timeout)
    return gate, cancel


def make_call() -> CodeAction:
    return CodeAction(tool_name="ipybox_execute_ipython_cell", code="print(1)")


class TestApprovalGate:
    def test_create_carries_ids(self) -> None:
        gate, _ = make_gate()
        request = gate.create(make_call(), corr_id="c1", parent_corr_id="p1")
        assert request.agent_id == "main"
        assert request.corr_id == "c1"
        assert request.parent_corr_id == "p1"

    @pytest.mark.asyncio
    async def test_decide_approved(self) -> None:
        gate, _ = make_gate()
        request = gate.create(make_call())
        request.approve(True)
        assert await gate.decide(request) is Decision.APPROVED

    @pytest.mark.asyncio
    async def test_decide_rejected(self) -> None:
        gate, _ = make_gate()
        request = gate.create(make_call())
        request.approve(False)
        decision = await gate.decide(request)
        assert decision is Decision.REJECTED
        assert not decision.approved

    @pytest.mark.asyncio
    async def test_decide_cancelled_resolves_request_rejected(self) -> None:
        gate, cancel = make_gate()
        request = gate.create(make_call())

        async def cancel_soon() -> None:
            cancel.set()

        task = asyncio.create_task(cancel_soon())
        decision = await gate.decide(request)
        await task

        assert decision is Decision.CANCELLED
        # The request itself was resolved as rejected so other waiters
        # observe a consistent decision.
        assert await request.approved() is False

    @pytest.mark.asyncio
    async def test_decide_timeout_resolves_request_rejected(self) -> None:
        gate, _ = make_gate(timeout=0.05)
        request = gate.create(make_call())

        decision = await gate.decide(request)

        assert decision is Decision.TIMED_OUT
        assert await request.approved() is False

    @pytest.mark.asyncio
    async def test_decision_before_timeout_wins(self) -> None:
        gate, _ = make_gate(timeout=5)
        request = gate.create(make_call())
        request.approve(True)
        assert await gate.decide(request) is Decision.APPROVED

    @pytest.mark.asyncio
    async def test_approve_after_resolution_is_noop(self) -> None:
        """Exactly-once resolution: late approve() calls never raise.

        When cancel races with a terminal approval, both paths may try to
        resolve the same request. The second call must not raise
        InvalidStateError and must not change the decision.
        """
        gate, cancel = make_gate()
        request = gate.create(make_call())

        cancel.set()
        decision = await gate.decide(request)
        assert decision is Decision.CANCELLED

        request.approve(True)  # late approval, no error
        request.approve(False)  # also safe
        assert await request.approved() is False

    @pytest.mark.asyncio
    async def test_resolve_rejected_unblocks_waiter(self) -> None:
        gate, _ = make_gate()
        request = gate.create(make_call())

        waiter = asyncio.create_task(gate.decide(request))
        await asyncio.sleep(0)
        ApprovalGate.resolve_rejected(request)

        assert await waiter is Decision.REJECTED

    @pytest.mark.asyncio
    async def test_cancel_set_before_decide(self) -> None:
        gate, cancel = make_gate()
        cancel.set()
        request = gate.create(make_call())
        assert await gate.decide(request) is Decision.CANCELLED


class TestCancelToken:
    @pytest.mark.asyncio
    async def test_set_clear_roundtrip(self) -> None:
        token = CancelToken()
        assert not token.is_set()
        token.set()
        assert token.is_set()
        token.clear()
        assert not token.is_set()

    @pytest.mark.asyncio
    async def test_shared_token_identity_survives_clear(self) -> None:
        """Components capture the token object; clear() must not detach them."""
        token = CancelToken()
        token.set()
        token.clear()

        async def wait() -> bool:
            await token.wait()
            return True

        waiter = asyncio.create_task(wait())
        await asyncio.sleep(0)
        token.set()
        assert await waiter is True


class TestApprovalRequest:
    def test_approve_idempotent_without_loop(self) -> None:
        async def run() -> None:
            request = ApprovalRequest(
                agent_id="main",
                corr_id="test",
                tool_call=make_call(),
            )
            request.approve(False)
            request.approve(False)
            request.approve(True)
            assert await request.approved() is False

        asyncio.run(run())
