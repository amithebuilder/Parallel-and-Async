"""Day 5 demo: RetryStrategy + CircuitBreaker."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.retry import RetryStrategy, CircuitBreaker, TransientError, PermanentError


async def main():
    # --- RetryStrategy ---
    retry = RetryStrategy(max_retries=3, backoff_factor=1.5, initial_delay=0.1)
    attempt = 0

    async def flaky():
        nonlocal attempt
        attempt += 1
        if attempt < 3:
            raise TransientError("not ready yet")
        return "success"

    result = await retry.execute_with_retry(flaky)
    print(f"Retry result: {result!r} after {attempt} attempts")
    print(f"Retry stats:  {retry.get_stats()}")

    # --- CircuitBreaker ---
    print()
    cb = CircuitBreaker(threshold=3, recovery_time=1.0)
    domain = "broken.example.com"
    for i in range(4):
        cb.record_error(domain)
        print(f"  error #{i+1}: circuit state = {cb.get_state(domain)}")

    print(f"can_request: {cb.can_request(domain)}")
    await asyncio.sleep(1.1)
    print(f"after recovery wait, can_request: {cb.can_request(domain)}")
    cb.record_success(domain)
    print(f"after success probe, state: {cb.get_state(domain)}")


if __name__ == "__main__":
    asyncio.run(main())
