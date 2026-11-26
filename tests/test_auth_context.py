"""Tests for session-scoped current operator identity."""
from core.auth_context import CurrentUser


def test_current_user_defaults_to_system(monkeypatch):
    state = {}
    monkeypatch.setattr("core.auth_context.st.session_state", state)
    assert CurrentUser.get_username() == "system"
    assert state["username"] == "system"


def test_current_user_can_be_changed(monkeypatch):
    state = {}
    monkeypatch.setattr("core.auth_context.st.session_state", state)
    assert CurrentUser.set_username("Operator 1") == "Operator 1"
    assert CurrentUser.get_username() == "Operator 1"


def test_current_user_rejects_blank_username(monkeypatch):
    monkeypatch.setattr("core.auth_context.st.session_state", {})
    import pytest
    with pytest.raises(ValueError, match="non-empty"):
        CurrentUser.set_username("  ")
