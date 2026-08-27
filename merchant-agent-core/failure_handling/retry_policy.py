from __future__ import annotations

from dataclasses import dataclass

from failure_handling.error_types import StandardError


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for RetryPolicy. All values are plain, deterministic
    numbers - never derived from an LLM call.

    max_retries         - how many retry attempts are allowed after the
                          initial attempt (attempt 1 = initial call).
    base_delay_seconds  - delay before the first retry.
    backoff_multiplier  - multiplier applied per additional retry.
    max_delay_seconds    - hard cap so backoff never grows unbounded.
    """

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 30.0


class RetryPolicy:
    """Deterministic retry decision + exponential backoff calculation.

    Attempt numbering: attempt 1 is the initial (non-retry) call. Retries
    are attempts 2..(max_retries + 1). With the default config:

        attempt 1 -> failure
        attempt 2 -> retry   (1st retry)
        attempt 3 -> retry   (2nd retry)
        attempt 4 -> stop    (3rd retry would exceed max_retries)

    Never retries a non-retryable error, and never retries past
    max_retries regardless of how the error is classified.
    """

    def __init__(self, config: RetryConfig | None = None):
        self._config = config or RetryConfig()

    @property
    def config(self) -> RetryConfig:
        return self._config

    def should_retry(self, error: StandardError, attempt: int) -> bool:
        """attempt is the number of the attempt that just failed (1-based).
        Returns True only if the error is retryable AND another attempt is
        still within max_retries."""
        if not error.retryable:
            return False
        retries_so_far = attempt - 1
        return retries_so_far < self._config.max_retries

    def next_attempt_delay(self, attempt: int) -> float:
        """Delay (seconds) to wait before making `attempt + 1`, given that
        `attempt` (1-based) just failed. Exponential backoff from
        base_delay_seconds, capped at max_delay_seconds."""
        retries_so_far = max(attempt - 1, 0)
        delay = self._config.base_delay_seconds * (self._config.backoff_multiplier ** retries_so_far)
        return min(delay, self._config.max_delay_seconds)
