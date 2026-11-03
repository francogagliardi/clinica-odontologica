"""Login brute-force protection (C-03, R-02, R-06).

The limiter is a sliding window over failed attempts, keyed by IP + email.
It is intentionally in-memory and therefore **per process**: with more than one
API worker each process would keep its own counters. The Compose demo runs a
single uvicorn process, which is the documented scope for v1; if the API is
scaled horizontally this state must move to Redis (R-06 mandates that Redis
holds queues/counters, never durable domain state).

The clock is injectable so tests do not sleep.
"""

import math
import time
from collections import defaultdict
from collections.abc import Callable
from threading import Lock


class LoginRateLimiter:
    """Sliding-window limiter for failed login attempts per key."""

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 300,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts debe ser mayor o igual a 1")
        if window_seconds < 1:
            raise ValueError("window_seconds debe ser mayor o igual a 1")
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        threshold = now - self.window_seconds
        valid = [t for t in self._attempts.get(key, []) if t >= threshold]
        if valid:
            self._attempts[key] = valid
        else:
            self._attempts.pop(key, None)
        return valid

    def is_blocked(self, key: str) -> bool:
        """True when the key already reached `max_attempts` inside the window."""
        with self._lock:
            now = self._clock()
            valid = self._prune(key, now)
            return len(valid) >= self.max_attempts

    def record_failure(self, key: str) -> int:
        """Record a failed attempt timestamp and return the current count."""
        with self._lock:
            now = self._clock()
            valid = self._prune(key, now)
            valid.append(now)
            self._attempts[key] = valid
            return len(valid)

    def reset(self, key: str) -> None:
        """Clear the counters after a successful login."""
        with self._lock:
            self._attempts.pop(key, None)

    def retry_after(self, key: str) -> int:
        """Seconds until the key stops being blocked (0 when not blocked).

        Exposed as the `Retry-After` header so clients can back off instead of
        hammering the endpoint.
        """
        with self._lock:
            now = self._clock()
            valid = self._prune(key, now)
            if len(valid) < self.max_attempts:
                return 0
            # Enough oldest attempts must fall out of the window for the
            # remaining count to drop below max_attempts.
            oldest_to_expire = valid[len(valid) - self.max_attempts]
            remaining = self.window_seconds - (now - oldest_to_expire)
            return max(1, math.ceil(remaining))


# Default process-level limiter; `api.deps.get_login_limiter` exposes it as an
# injectable FastAPI dependency so tests can substitute an isolated instance.
default_login_limiter = LoginRateLimiter(max_attempts=5, window_seconds=300)
