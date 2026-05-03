"""Day 5 demo: Error handling and automatic retries."""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.client import AsyncCrawler
from crawler.retry import (
    RetryStrategy,
    CircuitBreaker,
    TransientError,
    PermanentError,
    NetworkError,
    classify_error,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def demo_retries():
    print("\n=== Retry Demo ===")
    retry = RetryStrategy(max_retries=2, backoff_factor=1.5, initial_delay=0.5)

    async with AsyncCrawler(max_concurrent=5, timeout_total=5.0) as crawler:
        # This will succeed
        try:
            result = await retry.execute_with_retry(crawler.fetch_url, "https://httpbin.org/get")
            print(f"  OK: httpbin.org/get ({len(result)} bytes)")
        except Exception as exc:
            print(f"  FAIL: {exc}")

        # This will get retried (503)
        try:
            result = await retry.execute_with_retry(crawler.fetch_url, "https://httpbin.org/status/503")
            print(f"  OK: status/503 ({len(result)} bytes)")
        except Exception as exc:
            classified = classify_error(exc)
            print(f"  Expected failure (503): {type(classified).__name__}: {classified}")

        # This will NOT be retried (404 → PermanentError)
        try:
            result = await retry.execute_with_retry(crawler.fetch_url, "https://httpbin.org/status/404")
        except PermanentError as exc:
            print(f"  Expected permanent failure (404): {exc}")
        except Exception as exc:
            print(f"  FAIL: {type(exc).__name__}: {exc}")

        # Network error (unreachable host)
        try:
            result = await retry.execute_with_retry(crawler.fetch_url, "https://192.0.2.1/")
        except Exception as exc:
            classified = classify_error(exc)
            print(f"  Expected network failure: {type(classified).__name__}: {classified}")

    print(f"\nRetry stats: {retry.get_stats()}")


async def demo_circuit_breaker():
    print("\n=== Circuit Breaker Demo ===")
    cb = CircuitBreaker(threshold=3, window=10.0, recovery_time=2.0)
    domain = "test.example.com"

    for i in range(5):
        if cb.can_request(domain):
            print(f"  Request {i+1}: allowed (state={cb.get_state(domain)})")
            cb.record_error(domain)
        else:
            print(f"  Request {i+1}: BLOCKED (state={cb.get_state(domain)})")

    print(f"  Waiting 2.5s for recovery...")
    await asyncio.sleep(2.5)

    if cb.can_request(domain):
        print(f"  Probe request: allowed (state={cb.get_state(domain)})")
        cb.record_success(domain)
        print(f"  After success: state={cb.get_state(domain)}")


async def main():
    await demo_retries()
    await demo_circuit_breaker()


if __name__ == "__main__":
    asyncio.run(main())
