"""Unit tests for login brute-force throttling (C-03, R-02)."""

import pytest

from app.core.throttling import LoginRateLimiter


class FakeClock:
    """Deterministic clock so window tests never sleep."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_throttling_within_threshold_allows_attempts() -> None:
    limiter = LoginRateLimiter(
        max_attempts=3, window_seconds=60, clock=FakeClock()
    )
    key = "127.0.0.1:user@clinica.local"

    assert limiter.is_blocked(key) is False
    limiter.record_failure(key)
    assert limiter.is_blocked(key) is False
    limiter.record_failure(key)
    assert limiter.is_blocked(key) is False


def test_throttling_exceeding_threshold_blocks() -> None:
    limiter = LoginRateLimiter(
        max_attempts=3, window_seconds=60, clock=FakeClock()
    )
    key = "127.0.0.1:attacker@clinica.local"

    for _ in range(3):
        limiter.record_failure(key)

    assert limiter.is_blocked(key) is True


def test_throttling_reset_clears_blocked_state() -> None:
    limiter = LoginRateLimiter(
        max_attempts=2, window_seconds=60, clock=FakeClock()
    )
    key = "127.0.0.1:user2@clinica.local"

    limiter.record_failure(key)
    limiter.record_failure(key)
    assert limiter.is_blocked(key) is True

    limiter.reset(key)
    assert limiter.is_blocked(key) is False


def test_throttling_window_expiration() -> None:
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_attempts=2, window_seconds=30, clock=clock
    )
    key = "127.0.0.1:user3@clinica.local"

    limiter.record_failure(key)
    limiter.record_failure(key)
    assert limiter.is_blocked(key) is True

    clock.advance(31)
    assert limiter.is_blocked(key) is False


def test_retry_after_is_zero_when_not_blocked() -> None:
    limiter = LoginRateLimiter(
        max_attempts=3, window_seconds=60, clock=FakeClock()
    )
    assert limiter.retry_after("nadie") == 0


def test_retry_after_counts_down_and_unblocks() -> None:
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_attempts=2, window_seconds=60, clock=clock
    )
    key = "127.0.0.1:user4@clinica.local"

    limiter.record_failure(key)
    clock.advance(10)
    limiter.record_failure(key)

    # Oldest attempt at t=0 must leave the window; 50s remain.
    assert limiter.retry_after(key) == 50
    assert limiter.is_blocked(key) is True

    clock.advance(51)
    assert limiter.retry_after(key) == 0
    assert limiter.is_blocked(key) is False


def test_limiter_isolates_keys() -> None:
    limiter = LoginRateLimiter(
        max_attempts=1, window_seconds=60, clock=FakeClock()
    )
    limiter.record_failure("ip:uno@clinica.local")

    assert limiter.is_blocked("ip:uno@clinica.local") is True
    assert limiter.is_blocked("ip:dos@clinica.local") is False


@pytest.mark.parametrize(
    ("max_attempts", "window_seconds"),
    [(0, 60), (3, 0)],
)
def test_limiter_rejects_invalid_configuration(
    max_attempts: int, window_seconds: int
) -> None:
    with pytest.raises(ValueError):
        LoginRateLimiter(
            max_attempts=max_attempts, window_seconds=window_seconds
        )
