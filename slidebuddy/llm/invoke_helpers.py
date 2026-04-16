"""Retry wrapper for LLM invocations using tenacity."""

import logging

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


def _is_transient(exc: BaseException) -> bool:
    """Return True for errors worth retrying (timeouts, rate limits, server errors)."""
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    msg = str(exc).lower()
    for pattern in ("timeout", "429", "rate", "500", "502", "503", "overloaded"):
        if pattern in msg:
            return True
    return False


def invoke_with_retry(llm, messages, label: str = "llm"):
    """Invoke an LLM with automatic retry on transient errors.

    Args:
        llm: LangChain chat model instance.
        messages: List of BaseMessage (SystemMessage, HumanMessage, etc.).
        label: Human-readable label for log messages.

    Returns:
        The LLM response object.
    """
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=16),
        retry=retry_if_exception(_is_transient),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _invoke():
        return llm.invoke(messages)

    return _invoke()
