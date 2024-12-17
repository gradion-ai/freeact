import asyncio
import sys
from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable

from anthropic import APIStatusError

from freeact.logger import Logger
from freeact.model.base import StreamRetry

_MAX_WAIT = sys.maxsize / 2


class WaitStrategy(ABC):
    @abstractmethod
    def compute_wait_time(self, retry_attempt: int) -> float: ...


class WaitExponential(WaitStrategy):
    """Wait strategy that applies exponential backoff.

    Args:
        multiplier (float, optional): Value to multiply the exponential factor by.
            Defaults to 1.
        max (float, optional): Maximum wait time allowed. Defaults to system's maxsize/2.
        exp_base (float, optional): Base for exponential calculation. Defaults to 2.
        min (float, optional): Minimum wait time allowed. Defaults to 0.
    """

    def __init__(
        self,
        multiplier: float = 1,
        max: float = _MAX_WAIT,
        exp_base: float = 2,
        min: float = 0,
    ) -> None:
        self._multiplier = multiplier
        self._min = min
        self._max = max
        self._exp_base = exp_base

    def compute_wait_time(self, retry_attempt: int) -> float:
        try:
            exp = self._exp_base ** (retry_attempt - 1)
            result = self._multiplier * exp
        except OverflowError:
            return self._max
        return max(max(0, self._min), min(result, self._max))


async def retry(
    stream_func: Callable[[], AsyncIterator],
    logger: Logger,
    retry_max_attempts: int,
    retry_wait_strategy: WaitStrategy,
) -> AsyncIterator:
    from freeact.model.claude.model import ClaudeResponse

    retry_attempt = 0
    while True:
        try:
            async for elem in stream_func():
                match elem:
                    case str():
                        yield elem
                    case ClaudeResponse() as res:
                        yield res
                        return
        except APIStatusError as err:
            async with logger.context("error"):
                message = f"APIStatusError occurred:\nStatus Code: {err.status_code}\nMessage: {err.message}\nBody: {err.body}\nHeaders: {err.response.headers}"
                await logger.log(message, metadata={"message": err.message})

            retry_attempt += 1
            if retry_attempt > retry_max_attempts:
                raise RuntimeError(f"Maximum retry attempts reached (retry_max_attempts={retry_max_attempts}).", err)

            is_retryable, retry_wait_time = _get_retry_info(retry_wait_strategy, err, retry_attempt)
            if not is_retryable:
                raise err

            yield StreamRetry(cause=str(err), retry_wait_time=retry_wait_time)  # type: ignore
            await asyncio.sleep(retry_wait_time)  # type: ignore


def _get_retry_info(wait_strategy: WaitStrategy, error: Exception, retry_attempt: int) -> tuple[bool, float | None]:
    match error:
        case APIStatusError(body=body, response=res):
            if not body or not isinstance(body, dict) or body.get("type") != "error" or "type" not in body["error"]:
                # Body is not a valid JSON object or is not a valid error body. For more details, see:
                # * https://docs.anthropic.com/en/api/messages-streaming#error-events
                # * https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/_streaming.py#L192
                return False, None

            error_type = body["error"]["type"]

            if error_type in ["api_error", "overloaded_error"]:
                return True, wait_strategy.compute_wait_time(retry_attempt)

            if error_type == "rate_limit_error":
                try:
                    return True, float(
                        res.headers.get("retry-after")
                    )  # see https://docs.anthropic.com/en/api/rate-limits#response-headers
                except (ValueError, TypeError):
                    return True, wait_strategy.compute_wait_time(retry_attempt)

            return False, None
        case _:
            return False, None
