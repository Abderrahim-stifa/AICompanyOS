"""In-process brute-force protection for the shared login account.

AICompanyOS has a single shared account per deployment, so failures are tracked
globally rather than per browser session (a new session would otherwise reset
the counter). After ``max_failures`` failed attempts inside ``window`` seconds
the login is locked for ``lockout`` seconds.

Trade-off: someone who can reach the login page can lock the legitimate user
out for the lockout period. That is preferable to unlimited password guessing;
tune it with AICOS_AUTH_MAX_FAILURES and AICOS_AUTH_LOCKOUT_SECONDS.
"""
from __future__ import annotations

import math
import os
import threading
import time
from typing import Callable

DEFAULT_MAX_FAILURES = 5
DEFAULT_WINDOW_SECONDS = 900.0
DEFAULT_LOCKOUT_SECONDS = 300.0


def _env_number(name: str, default: float, minimum: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


class LoginThrottle:
    def __init__(
        self,
        max_failures: int = DEFAULT_MAX_FAILURES,
        window: float = DEFAULT_WINDOW_SECONDS,
        lockout: float = DEFAULT_LOCKOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_failures < 1:
            raise ValueError("max_failures must be at least 1")
        self.max_failures = max_failures
        self.window = window
        self.lockout = lockout
        self._clock = clock
        self._lock = threading.Lock()
        self._failures: list[float] = []
        self._locked_until = 0.0

    def retry_after(self) -> int:
        """Seconds until another attempt is allowed; 0 when login is open."""
        with self._lock:
            remaining = self._locked_until - self._clock()
            return math.ceil(remaining) if remaining > 0 else 0

    def record_failure(self) -> None:
        with self._lock:
            now = self._clock()
            self._failures = [t for t in self._failures if now - t < self.window]
            self._failures.append(now)
            if len(self._failures) >= self.max_failures:
                self._locked_until = now + self.lockout
                self._failures.clear()

    def record_success(self) -> None:
        with self._lock:
            self._failures.clear()
            self._locked_until = 0.0

    def reset(self) -> None:
        self.record_success()


def from_env() -> LoginThrottle:
    return LoginThrottle(
        max_failures=int(_env_number("AICOS_AUTH_MAX_FAILURES", DEFAULT_MAX_FAILURES, 1)),
        window=_env_number("AICOS_AUTH_FAILURE_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS, 1),
        lockout=_env_number("AICOS_AUTH_LOCKOUT_SECONDS", DEFAULT_LOCKOUT_SECONDS, 1),
    )
