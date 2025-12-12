"""
Retry handler with exponential backoff.
Used by all connectors for reliable external calls.
"""

import asyncio
import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """
    Decorator for retry logic with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay between retries

    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = base_delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except asyncio.TimeoutError:
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} timed out (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, max_delay)  # Exponential backoff
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts (timeout)")
                        raise

                except Exception as e:
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed with {type(e).__name__}: {e} "
                            f"(attempt {attempt + 1}/{max_retries + 1}). Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, max_delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise

            # Should not reach here
            raise RuntimeError(f"{func.__name__} exhausted all retries")

        return wrapper
    return decorator


def timeout_handler(timeout_seconds: float):
    """
    Decorator to add timeout to async functions.

    Args:
        timeout_seconds: Timeout in seconds

    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"{func.__name__} timed out after {timeout_seconds}s")
                raise

        return wrapper
    return decorator
