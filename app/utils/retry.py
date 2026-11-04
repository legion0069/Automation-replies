import asyncio
import functools
import logging
from typing import Any, Callable, TypeVar
import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Non-retryable Meta Graph API error codes
PERMANENT_META_ERROR_CODES = {
    10,    # Permission Denied
    100,   # Invalid Parameter / Target object does not exist (e.g. comment was deleted)
    190,   # Invalid OAuth Access Token
    200,   # Permissions error
    230,   # Permissions error
    368,   # Temporarily blocked from posting (spam block / policy)
}

# Retryable Meta Graph API error codes
TRANSIENT_META_ERROR_CODES = {
    1,     # An unknown error occurred
    2,     # Service temporarily unavailable
    4,     # Application request limit reached
    17,    # User request limit reached
    32,    # Page-level throttling
    341,   # Temporary send message limit
    613,   # Calls to this api have exceeded the rate limit
}


def is_retryable_meta_error(status_code: int, error_data: dict) -> bool:
    """Determine whether an HTTP status code and Meta error response is retryable."""
    # 5xx server errors are always retryable
    if status_code >= 500:
        return True

    # 429 Too Many Requests is retryable
    if status_code == 429:
        return True

    error_info = error_data.get("error", {})
    code = error_info.get("code")
    is_transient = error_info.get("is_transient", False)

    if is_transient:
        return True

    if code in TRANSIENT_META_ERROR_CODES:
        return True

    if code in PERMANENT_META_ERROR_CODES or status_code in (400, 401, 403, 404):
        return False

    return False


async def with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    **kwargs: Any,
) -> Any:
    """Execute an async function with exponential backoff for transient errors."""
    attempt = 0
    delay = 1.0

    while True:
        try:
            return await func(*args, **kwargs)
        except httpx.RequestError as exc:
            # Network timeouts and connection drops are transient
            attempt += 1
            if attempt > max_retries:
                logger.error(
                    "Function %s failed after %d retries due to network error: %s",
                    func.__name__,
                    max_retries,
                    exc,
                )
                raise
            logger.warning(
                "Network error in %s: %s. Retrying attempt %d/%d in %.1fs...",
                func.__name__,
                exc,
                attempt,
                max_retries,
                delay,
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor
        except httpx.HTTPStatusError as exc:
            attempt += 1
            status = exc.response.status_code
            error_body = {}
            try:
                error_body = exc.response.json()
            except Exception:
                pass

            if is_retryable_meta_error(status, error_body) and attempt <= max_retries:
                logger.warning(
                    "Transient HTTP %d in %s. Retrying attempt %d/%d in %.1fs... Error: %s",
                    status,
                    func.__name__,
                    attempt,
                    max_retries,
                    delay,
                    error_body,
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(
                    "Permanent or unhandled HTTP %d error in %s: %s",
                    status,
                    func.__name__,
                    error_body,
                )
                raise
