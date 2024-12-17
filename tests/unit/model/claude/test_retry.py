from typing import AsyncIterator, Callable
from unittest.mock import AsyncMock

import httpx
import pytest
from anthropic import APIStatusError

from freeact.logger import Logger
from freeact.model.base import StreamRetry
from freeact.model.claude.model import ClaudeResponse
from freeact.model.claude.retry import (
    WaitExponential,
    WaitStrategy,
    _get_retry_info,
    retry,
)


@pytest.fixture
def logger():
    return AsyncMock(spec=Logger)


def assert_stream_results(
    results: list[str | StreamRetry | ClaudeResponse],
    expected_results: list[str | StreamRetry | ClaudeResponse],
):
    assert len(results) == len(expected_results)
    for result, expected in zip(results, expected_results):
        if isinstance(expected, StreamRetry):
            assert isinstance(result, StreamRetry)
        else:
            assert result == expected


def create_api_status_error_with_body(body: str | dict | None, headers: dict[str, str] | None = None) -> APIStatusError:
    response = httpx.Response(status_code=200, headers=headers)
    response.request = httpx.Request("GET", "https://example.com")

    return APIStatusError(
        message="API Error",
        body=body,
        response=response,
    )


def create_failing_stream(num_failures: int, error_type: str):
    call_count = 0

    async def failing_stream():
        nonlocal call_count

        yield "part-1"

        call_count += 1
        if call_count <= num_failures:
            raise create_api_status_error(error_type)

        yield ClaudeResponse(text="part-1", is_error=False)

    return failing_stream


def create_api_status_error(error_type: str, headers: dict[str, str] | None = None) -> APIStatusError:
    return create_api_status_error_with_body(
        body={
            "type": "error",
            "error": {"type": error_type, "message": "error message"},
        },
        headers=headers,
    )


async def consume_stream(
    stream_fn: Callable[[], AsyncIterator[str | StreamRetry | ClaudeResponse]],
    logger,
    retry_max_attempts: int,
    retry_wait_strategy: WaitStrategy,
):
    results = []
    async for item in retry(
        stream_fn,
        logger,
        retry_max_attempts=retry_max_attempts,
        retry_wait_strategy=retry_wait_strategy,
    ):
        results.append(item)
    return results


@pytest.mark.asyncio
async def test_retry_on_successful_stream(logger):
    async def stream_func():
        yield "part-1"
        yield "part-2"
        yield ClaudeResponse(text="part-1 part-2", is_error=False)

    results = await consume_stream(
        stream_func,
        logger,
        retry_max_attempts=3,
        retry_wait_strategy=WaitExponential(),
    )

    assert_stream_results(
        results,
        [
            "part-1",
            "part-2",
            ClaudeResponse(text="part-1 part-2", is_error=False),
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [
        "api_error",
        "rate_limit_error",
        "overloaded_error",
    ],
)
async def test_single_retry_on_retryable_api_error(logger, error_type):
    stream_fn = create_failing_stream(
        num_failures=1,
        error_type=error_type,
    )
    retry_max_attempts = 3

    results = await consume_stream(
        stream_fn,
        logger,
        retry_max_attempts=retry_max_attempts,
        retry_wait_strategy=WaitExponential(multiplier=0.1),
    )

    assert_stream_results(
        results,
        [
            "part-1",
            StreamRetry(cause=error_type, retry_wait_time=0.1),
            "part-1",
            ClaudeResponse(text="part-1", is_error=False),
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [
        "api_error",
        "rate_limit_error",
        "overloaded_error",
    ],
)
async def test_multiple_retries_on_retryable_api_error(logger, error_type):
    stream_fn = create_failing_stream(
        num_failures=2,
        error_type=error_type,
    )
    retry_max_attempts = 3

    results = await consume_stream(
        stream_fn,
        logger,
        retry_max_attempts=retry_max_attempts,
        retry_wait_strategy=WaitExponential(multiplier=0.1),
    )

    assert_stream_results(
        results,
        [
            "part-1",
            StreamRetry(cause=error_type, retry_wait_time=0.1),
            "part-1",
            StreamRetry(cause=error_type, retry_wait_time=0.1),
            "part-1",
            ClaudeResponse(text="part-1", is_error=False),
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [
        "invalid_request_error",
        "authentication_error",
        "permission_error",
        "not_found_error",
        "request_too_large",
    ],
)
async def test_retry_on_non_retryable_api_error(logger, error_type):
    stream_fn = create_failing_stream(
        num_failures=1,
        error_type=error_type,
    )
    retry_max_attempts = 3

    with pytest.raises(APIStatusError):
        await consume_stream(
            stream_fn,
            logger,
            retry_max_attempts=retry_max_attempts,
            retry_wait_strategy=WaitExponential(multiplier=0.1),
        )


@pytest.mark.asyncio
async def test_stop_retry_on_max_attempts(logger):
    stream_fn = create_failing_stream(num_failures=5, error_type="overloaded_error")
    retry_max_attempts = 3

    with pytest.raises(RuntimeError) as exc_info:
        await consume_stream(
            stream_fn,
            logger,
            retry_max_attempts=retry_max_attempts,
            retry_wait_strategy=WaitExponential(multiplier=0.1),
        )
        assert "Maximum retry attempts reached" in str(exc_info.value)


def test_get_retry_info_on_api_error():
    should_retry, wait_time = _get_retry_info(
        error=create_api_status_error("api_error"),
        wait_strategy=WaitExponential(multiplier=0.5),
        retry_attempt=1,
    )

    assert should_retry is True
    assert wait_time == 0.5


def test_get_retry_info_on_overloaded_error():
    should_retry, wait_time = _get_retry_info(
        error=create_api_status_error("overloaded_error"),
        wait_strategy=WaitExponential(multiplier=0.5),
        retry_attempt=1,
    )

    assert should_retry is True
    assert wait_time == 0.5


def test_get_retry_info_on_rate_limit_error_without_retry_after():
    should_retry, wait_time = _get_retry_info(
        error=create_api_status_error("rate_limit_error"),
        wait_strategy=WaitExponential(multiplier=0.5),
        retry_attempt=1,
    )

    assert should_retry is True
    assert wait_time == 0.5


def test_get_retry_info_on_rate_limit_error_with_retry_after():
    should_retry, wait_time = _get_retry_info(
        error=create_api_status_error("rate_limit_error", headers={"retry-after": "30"}),
        wait_strategy=WaitExponential(multiplier=0.5),
        retry_attempt=1,
    )

    assert should_retry is True
    assert wait_time == 30


def test_get_retry_info_on_non_retryable_api_error():
    should_retry, wait_time = _get_retry_info(
        error=create_api_status_error("invalid_request_error"),
        wait_strategy=WaitExponential(multiplier=0.5),
        retry_attempt=1,
    )

    assert should_retry is False
    assert wait_time is None


def test_get_retry_info_on_non_api_error():
    should_retry, wait_time = _get_retry_info(
        error=RuntimeError("Non-API error"),
        wait_strategy=WaitExponential(multiplier=0.5),
        retry_attempt=1,
    )

    assert should_retry is False
    assert wait_time is None


def test_get_retry_info_on_api_error_with_non_json_body():
    should_retry, wait_time = _get_retry_info(
        error=create_api_status_error_with_body(body="not a valid JSON object"),
        wait_strategy=WaitExponential(multiplier=0.5),
        retry_attempt=1,
    )

    assert should_retry is False
    assert wait_time is None


def test_get_retry_info_on_api_error_with_empty_body():
    should_retry, wait_time = _get_retry_info(
        error=create_api_status_error_with_body(body=None),
        wait_strategy=WaitExponential(multiplier=0.5),
        retry_attempt=1,
    )

    assert should_retry is False
    assert wait_time is None


def test_get_retry_info_on_non_error_api_result():
    should_retry, wait_time = _get_retry_info(
        error=create_api_status_error_with_body(body={"type": "other"}),
        wait_strategy=WaitExponential(multiplier=0.5),
        retry_attempt=1,
    )

    assert should_retry is False
    assert wait_time is None
