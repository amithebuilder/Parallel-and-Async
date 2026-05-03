"""Tests for Day 5: RetryStrategy, error classification, circuit breaker."""

import asyncio
import pytest
import aiohttp
from crawler.retry import (
    RetryStrategy,
    CircuitBreaker,
    classify_error,
    TransientError,
    PermanentError,
    NetworkError,
    CrawlerError,
)


def test_classify_timeout():
    exc = classify_error(asyncio.TimeoutError())
    assert isinstance(exc, TransientError)


def test_classify_404():
    raw = aiohttp.ClientResponseError(
        request_info=None, history=(), status=404, message="Not Found"
    )
    exc = classify_error(raw)
    assert isinstance(exc, PermanentError)


def test_classify_503():
    raw = aiohttp.ClientResponseError(
        request_info=None, history=(), status=503, message="Unavailable"
    )
    exc = classify_error(raw)
    assert isinstance(exc, TransientError)


def test_classify_429():
    raw = aiohttp.ClientResponseError(
        request_info=None, history=(), status=429, message="Too Many"
    )
    exc = classify_error(raw)
    assert isinstance(exc, TransientError)


def test_classify_network():
    raw = aiohttp.ClientConnectionError("conn refused")
    exc = classify_error(raw)
    assert isinstance(exc, NetworkError)


@pytest.mark.asyncio
async def test_retry_success_first_attempt():
    retry = RetryStrategy(max_retries=3)
    call_count = 0

    async def ok():
        nonlocal call_count
        call_count += 1
        return "done"

    result = await retry.execute_with_retry(ok)
    assert result == "done"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt():
    retry = RetryStrategy(max_retries=3, initial_delay=0.01, backoff_factor=1.0)
    call_count = 0

    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise asyncio.TimeoutError()
        return "recovered"

    result = await retry.execute_with_retry(flaky)
    assert result == "recovered"
    assert call_count == 2
    assert retry.get_stats()["successful_retries"] == 1


@pytest.mark.asyncio
async def test_retry_permanent_error_no_retry():
    retry = RetryStrategy(max_retries=3, initial_delay=0.01)
    call_count = 0

    async def perm_fail():
        nonlocal call_count
        call_count += 1
        raise PermanentError("404 Not Found")

    with pytest.raises(PermanentError):
        await retry.execute_with_retry(perm_fail)
    assert call_count == 1  # no retries


@pytest.mark.asyncio
async def test_retry_exhausted():
    retry = RetryStrategy(max_retries=2, initial_delay=0.01, backoff_factor=1.0)

    async def always_fail():
        raise asyncio.TimeoutError()

    with pytest.raises(TransientError):
        await retry.execute_with_retry(always_fail)

    assert retry.get_stats()["errors_by_type"]["TransientError"] == 3  # 1 + 2 retries


def test_circuit_breaker_opens():
    cb = CircuitBreaker(threshold=3, window=60.0, recovery_time=1.0)
    domain = "test.com"

    for _ in range(3):
        cb.record_error(domain)
    assert cb.get_state(domain) == CircuitBreaker.OPEN
    assert not cb.can_request(domain)


@pytest.mark.asyncio
async def test_circuit_breaker_recovers():
    cb = CircuitBreaker(threshold=2, window=60.0, recovery_time=0.1)
    domain = "test.com"

    cb.record_error(domain)
    cb.record_error(domain)
    assert not cb.can_request(domain)

    await asyncio.sleep(0.15)
    assert cb.can_request(domain)  # half-open
    assert cb.get_state(domain) == CircuitBreaker.HALF_OPEN

    cb.record_success(domain)
    assert cb.get_state(domain) == CircuitBreaker.CLOSED
