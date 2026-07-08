import logging
import threading
import time
from collections import defaultdict, deque
from typing import Callable, Iterable, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

_RATE_LOCK = threading.Lock()
_RECENT_CALLS: dict = defaultdict(deque)


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "resource_exhausted" in msg or "resource exhausted" in msg


def _throttle(model_name: str, min_interval: float, max_per_minute: int) -> None:
    with _RATE_LOCK:
        now = time.monotonic()
        recent = _RECENT_CALLS[model_name]
        while recent and now - recent[0] > 60:
            recent.popleft()

        wait = 0.0
        if recent:
            wait = max(wait, min_interval - (now - recent[-1]))
        if len(recent) >= max_per_minute:
            wait = max(wait, 60 - (now - recent[0]) + 0.5)

    if wait > 0:
        time.sleep(wait)

    with _RATE_LOCK:
        _RECENT_CALLS[model_name].append(time.monotonic())


def call_with_fallback(
    call_fn: Callable[[str], str],
    models: Sequence[str],
    *,
    min_interval: float = 4.0,
    max_per_minute: int = 10,
    max_retries_per_model: int = 2,
    retry_delay: float = 5.0,
) -> Tuple[Optional[str], Optional[str]]:
    """Call `call_fn(model_name)` against each model in `models`, in order.

    Proactively throttles calls per-model (min_interval / max_per_minute) before
    every attempt, so free-tier rate limits are avoided rather than just reacted to.
    On a quota/rate-limit error, switches to the next model immediately. On any
    other error, retries the same model up to `max_retries_per_model` times before
    moving on. Returns (result, model_used), or (None, None) if every model in the
    chain is exhausted.
    """
    last_exc: Optional[Exception] = None
    for model_name in models:
        for attempt in range(max_retries_per_model):
            _throttle(model_name, min_interval, max_per_minute)
            try:
                result = call_fn(model_name)
                # A call that returns cleanly but with empty/None content (e.g. the
                # model's response had no text part) is still a failure - treat it
                # like an exception instead of silently propagating it as "success".
                if not result:
                    raise ValueError(f"Model '{model_name}' returned empty/no content.")
                return result, model_name
            except Exception as exc:
                last_exc = exc
                if _is_quota_error(exc):
                    logger.warning(
                        "Model '%s' hit its quota/rate limit; switching to the next fallback model.",
                        model_name,
                    )
                    break
                logger.warning(
                    "Model '%s' call failed (attempt %d/%d): %s",
                    model_name, attempt + 1, max_retries_per_model, exc,
                )
                time.sleep(retry_delay)

    logger.critical("All fallback models exhausted. Last error: %s", last_exc)
    return None, None


def call_with_fallback_stream(
    call_fn: Callable[[str], Iterable[str]],
    models: Sequence[str],
    *,
    min_interval: float = 4.0,
    max_per_minute: int = 10,
):
    """Streaming counterpart to `call_with_fallback`.

    `call_fn(model_name)` must return an iterable/generator of text chunks (e.g.
    a `generate_content(..., stream=True)` response). Yields `(chunk_text,
    model_name)` as chunks arrive, switching to the next model in `models` if a
    model fails *before* yielding anything for it (a clean swap - no partial
    content was sent yet, so nothing is duplicated). If a model fails *after*
    already yielding some content, the stream stops rather than restarting on a
    different model, since re-issuing the same prompt elsewhere would duplicate
    or corrupt what the caller already forwarded to the end user.
    """
    last_exc: Optional[Exception] = None
    for model_name in models:
        _throttle(model_name, min_interval, max_per_minute)
        yielded_any_for_this_model = False
        try:
            for chunk in call_fn(model_name):
                if chunk:
                    yielded_any_for_this_model = True
                    yield chunk, model_name
            return
        except Exception as exc:
            last_exc = exc
            if yielded_any_for_this_model:
                logger.error(
                    "Model '%s' failed mid-stream after partial output was already sent: %s",
                    model_name, exc,
                )
                return
            if _is_quota_error(exc):
                logger.warning(
                    "Model '%s' hit its quota/rate limit; switching to the next fallback model.",
                    model_name,
                )
            else:
                logger.warning(
                    "Model '%s' streaming call failed before yielding any content: %s",
                    model_name, exc,
                )

    logger.critical("All fallback models exhausted for streaming call. Last error: %s", last_exc)
