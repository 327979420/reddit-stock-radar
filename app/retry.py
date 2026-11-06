from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable


async def retry_async[T](
    operation: Callable[[], Awaitable[T]],
    *,
    retry_on: tuple[type[BaseException], ...],
    attempts: int = 6,
    initial_delay: float = 10.0,
    logger: logging.Logger | None = None,
    operation_name: str = "network_operation",
) -> T:
    """Retry transient failures long enough for networking to recover after wake."""
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except retry_on:
            if attempt == attempts:
                raise
            delay = initial_delay * attempt
            if logger:
                logger.warning(
                    "%s_transient_failure attempt=%s/%s retry_in=%.0fs",
                    operation_name,
                    attempt,
                    attempts,
                    delay,
                )
            await asyncio.sleep(delay)
    raise RuntimeError("retry loop exited unexpectedly")
