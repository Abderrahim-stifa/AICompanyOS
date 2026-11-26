"""Streamlit session context for the currently selected operator."""
import streamlit as st


class CurrentUser:
    """Resolve the operator identity stored in the active Streamlit session."""

    @staticmethod
    def get_username() -> str:
        username = st.session_state.get("username")
        if not isinstance(username, str) or not username.strip():
            username = "system"
            st.session_state["username"] = username
        return username.strip()

    @staticmethod
    def set_username(username: str) -> str:
        if not isinstance(username, str) or not username.strip():
            raise ValueError("username must be a non-empty string")
        username = username.strip()
        if len(username) > 100:
            raise ValueError("username must be at most 100 characters")
        st.session_state["username"] = username
        return username
