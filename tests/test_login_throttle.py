"""Tests for the login brute-force throttle (no Streamlit required)."""

import pytest

from core.login_throttle import LoginThrottle, from_env


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(max_failures=3, window=60.0, lockout=30.0):
    clock = FakeClock()
    return LoginThrottle(max_failures, window, lockout, clock=clock), clock


def test_open_by_default():
    throttle, _ = make()
    assert throttle.retry_after() == 0


def test_locks_after_max_failures_and_reports_remaining_time():
    throttle, clock = make()
    for _ in range(2):
        throttle.record_failure()
    assert throttle.retry_after() == 0
    throttle.record_failure()
    assert throttle.retry_after() == 30
    clock.now += 10.2
    assert throttle.retry_after() == 20


def test_lock_expires():
    throttle, clock = make()
    for _ in range(3):
        throttle.record_failure()
    clock.now += 30.1
    assert throttle.retry_after() == 0


def test_failures_outside_window_do_not_count():
    throttle, clock = make()
    throttle.record_failure()
    throttle.record_failure()
    clock.now += 61
    throttle.record_failure()
    assert throttle.retry_after() == 0


def test_success_clears_failures_and_lock():
    throttle, _ = make()
    throttle.record_failure()
    throttle.record_failure()
    throttle.record_success()
    throttle.record_failure()
    throttle.record_failure()
    assert throttle.retry_after() == 0
    throttle.record_failure()
    assert throttle.retry_after() > 0
    throttle.reset()
    assert throttle.retry_after() == 0


def test_counter_restarts_after_a_lockout():
    throttle, clock = make()
    for _ in range(3):
        throttle.record_failure()
    clock.now += 31
    throttle.record_failure()
    throttle.record_failure()
    assert throttle.retry_after() == 0


def test_rejects_invalid_max_failures():
    with pytest.raises(ValueError):
        LoginThrottle(max_failures=0)


def test_from_env_reads_overrides_and_ignores_bad_values(monkeypatch):
    monkeypatch.setenv("AICOS_AUTH_MAX_FAILURES", "2")
    monkeypatch.setenv("AICOS_AUTH_LOCKOUT_SECONDS", "not-a-number")
    monkeypatch.setenv("AICOS_AUTH_FAILURE_WINDOW_SECONDS", "-5")
    throttle = from_env()
    assert throttle.max_failures == 2
    assert throttle.lockout == 300.0
    assert throttle.window == 900.0
