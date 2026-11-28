"""Tests for the Streamlit session authentication helpers."""

import pytest

from core import auth


@pytest.fixture(autouse=True)
def _reset_login_throttle():
    auth._THROTTLE.reset()
    yield
    auth._THROTTLE.reset()


def test_authenticate_accepts_configured_credentials(monkeypatch):
    state = {}
    monkeypatch.setattr(auth.st, "session_state", state)
    monkeypatch.setenv("AICOS_AUTH_USERNAME", "operator")
    monkeypatch.setenv("AICOS_AUTH_PASSWORD", "correct horse battery")
    assert auth.authenticate("operator", "correct horse battery") is True
    assert auth.is_authenticated() is True
    assert state["username"] == "operator"


def test_authenticate_rejects_invalid_credentials(monkeypatch):
    state = {}
    monkeypatch.setattr(auth.st, "session_state", state)
    monkeypatch.setenv("AICOS_AUTH_USERNAME", "operator")
    monkeypatch.setenv("AICOS_AUTH_PASSWORD", "correct horse battery")
    assert auth.authenticate("operator", "wrong") is False
    assert auth.is_authenticated() is False


def test_authentication_fails_closed_without_configuration(monkeypatch):
    state = {}
    monkeypatch.setattr(auth.st, "session_state", state)
    monkeypatch.delenv("AICOS_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("AICOS_AUTH_PASSWORD", raising=False)
    monkeypatch.setattr(auth.st, "secrets", {})
    assert auth.authenticate("operator", "anything") is False
    assert auth.is_authenticated() is False


def test_logout_clears_session_identity(monkeypatch):
    state = {
        auth._AUTHENTICATED_KEY: True,
        auth._AUTH_USERNAME_KEY: "operator",
        "username": "operator",
    }
    monkeypatch.setattr(auth.st, "session_state", state)
    auth.logout()
    assert auth._AUTHENTICATED_KEY not in state
    assert auth._AUTH_USERNAME_KEY not in state
    assert "username" not in state


def test_repeated_failures_lock_out_even_correct_password(monkeypatch):
    state = {}
    monkeypatch.setattr(auth.st, "session_state", state)
    monkeypatch.setenv("AICOS_AUTH_USERNAME", "operator")
    monkeypatch.setenv("AICOS_AUTH_PASSWORD", "correct horse battery")
    for _ in range(auth._THROTTLE.max_failures):
        assert auth.authenticate("operator", "wrong") is False
    assert auth.login_lockout_remaining() > 0
    assert auth.authenticate("operator", "correct horse battery") is False
    assert auth.is_authenticated() is False


def test_successful_login_resets_failure_count(monkeypatch):
    state = {}
    monkeypatch.setattr(auth.st, "session_state", state)
    monkeypatch.setenv("AICOS_AUTH_USERNAME", "operator")
    monkeypatch.setenv("AICOS_AUTH_PASSWORD", "correct horse battery")
    for _ in range(auth._THROTTLE.max_failures - 1):
        auth.authenticate("operator", "wrong")
    assert auth.authenticate("operator", "correct horse battery") is True
    for _ in range(auth._THROTTLE.max_failures - 1):
        auth.authenticate("operator", "wrong")
    assert auth.login_lockout_remaining() == 0
