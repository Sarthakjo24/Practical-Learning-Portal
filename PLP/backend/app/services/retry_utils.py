from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Iterable, TypeVar

T = TypeVar("T")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    retryable_exceptions: Iterable[type[BaseException]],
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    backoff_seconds: Callable[[int], float] | None = None,
) -> T:
    if max_attempts <= 0:
        raise ValueError("max_attempts must be greater than 0.")

    last_error: BaseException | None = None
    retryable = tuple(retryable_exceptions)
    compute_backoff = backoff_seconds or (lambda attempt_idx: float(2**attempt_idx))

    for attempt in range(max_attempts):
        try:
            return await operation()
        except retryable as exc:  # type: ignore[misc]
            last_error = exc
            if attempt < max_attempts - 1:
                await sleep(compute_backoff(attempt))
                continue
            break

    if last_error is None:
        raise RuntimeError("retry_async exhausted without recording an error.")
    raise last_error
