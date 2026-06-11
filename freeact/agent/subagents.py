import asyncio
import contextlib
import uuid
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

from freeact.agent.approvals import CancelToken
from freeact.agent.session import Session
from freeact.config import ResolvedRuntime
from freeact.events import AgentEvent, Response, ToolOutput

if TYPE_CHECKING:
    from freeact.agent.agent import Agent


class SubagentRunner:
    """Spawns subagents and bridges their event streams into the parent's.

    Each task runs a child agent with its own kernel and MCP connections,
    inheriting the parent's runtime settings (subagents disabled, index
    sync/watch off). Concurrency is bounded by `max_subagents`. Child
    events carry the parent task's correlation id in `parent_corr_id`;
    child failure becomes an error ToolOutput rather than an exception.
    """

    def __init__(
        self,
        *,
        runtime: ResolvedRuntime,
        agent_id: str,
        session_id: str | None,
        session: Session,
        cancel: CancelToken,
        sandbox: bool = False,
        sandbox_config: Path | None = None,
    ) -> None:
        self._runtime = runtime
        self._agent_id = agent_id
        self._session_id = session_id
        self._session = session
        self._cancel = cancel
        self._sandbox = sandbox
        self._sandbox_config = sandbox_config
        self._semaphore = asyncio.Semaphore(runtime.config.max_subagents)

    async def run_task(self, prompt: str, max_turns: int, corr_id: str) -> AsyncIterator[AgentEvent]:
        """Run a subagent task, yielding its events and the final ToolOutput.

        The final ToolOutput (carrying the parent's agent id) contains the
        subagent's last response, or an error message when the subagent
        failed.
        """
        from freeact.agent.agent import Agent

        subagent = Agent(
            self._runtime.for_subagent(),
            agent_id=f"sub-{uuid.uuid4().hex[:4]}",
            session_id=self._session_id,
            sandbox=self._sandbox,
            sandbox_config=self._sandbox_config,
            cancel_token=self._cancel,
        )

        async def _cancel_monitor() -> None:
            await self._cancel.wait()
            subagent.cancel()

        monitor_task = asyncio.create_task(_cancel_monitor())

        last_response = ""
        try:
            async for item in self._stream_subagent(subagent, prompt, max_turns):
                item = replace(item, parent_corr_id=corr_id)
                yield item
                match item:
                    case Response(content=content):
                        last_response = content
        except Exception as e:
            yield ToolOutput(content=f"Subagent error: {e}", agent_id=self._agent_id, corr_id=corr_id)
            return
        finally:
            monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor_task

        final_content, _ = await self._session.materialize_text(last_response)
        yield ToolOutput(content=final_content, agent_id=self._agent_id, corr_id=corr_id)

    async def _stream_subagent(self, subagent: "Agent", prompt: str, max_turns: int) -> AsyncIterator[AgentEvent]:
        # Runs the subagent in a dedicated task so its lifecycle (context
        # manager) survives consumer-side pauses, and streams its events
        # through a queue.
        queue: asyncio.Queue[AgentEvent | Exception | None] = asyncio.Queue()

        async def run_subagent() -> None:
            try:
                async with self._semaphore:
                    async with subagent:
                        async for event in subagent.stream(prompt, max_turns=max_turns):
                            await queue.put(event)
            except Exception as e:
                queue.put_nowait(e)
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(run_subagent())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    return
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
