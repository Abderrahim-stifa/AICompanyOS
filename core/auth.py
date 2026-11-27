"""Session-based authentication for the Streamlit application.

Configure credentials with AICOS_AUTH_USERNAME and AICOS_AUTH_PASSWORD
environment variables, or Streamlit secrets under [auth].
"""

from __future__ import annotations

import hmac
import os

import streamlit as st

_AUTHENTICATED_KEY = "aicos_authenticated"
_AUTH_USERNAME_KEY = "aicos_authenticated_username"


def _configured_credentials() -> tuple[str, str]:
    """Read credentials from environment variables or Streamlit secrets."""
    username = os.environ.get("AICOS_AUTH_USERNAME", "").strip()
    password = os.environ.get("AICOS_AUTH_PASSWORD", "")

    if username and password:
        return username, password

    try:
        auth_secrets = st.secrets.get("auth", {})
        username = str(auth_secrets.get("username", "")).strip()
        password = str(auth_secrets.get("password", ""))
    except (AttributeError, KeyError, RuntimeError):
        return "", ""

    return username, password


def is_authenticated() -> bool:
    """Return whether the current session has a valid authenticated identity."""
    configured_username, configured_password = _configured_credentials()
    if not configured_username or not configured_password:
        st.session_state.pop(_AUTHENTICATED_KEY, None)
        st.session_state.pop(_AUTH_USERNAME_KEY, None)
        return False

    return (
        st.session_state.get(_AUTHENTICATED_KEY) is True
        and st.session_state.get(_AUTH_USERNAME_KEY) == configured_username
    )


def authenticate(username: str, password: str) -> bool:
    """Validate credentials using constant-time comparisons."""
    expected_username, expected_password = _configured_credentials()
    if not expected_username or not expected_password:
        return False

    username_ok = hmac.compare_digest(
        str(username).strip().encode("utf-8"),
        expected_username.encode("utf-8"),
    )
    password_ok = hmac.compare_digest(
        str(password).encode("utf-8"),
        expected_password.encode("utf-8"),
    )
    if username_ok and password_ok:
        st.session_state[_AUTHENTICATED_KEY] = True
        st.session_state[_AUTH_USERNAME_KEY] = expected_username
        st.session_state["username"] = expected_username
        return True

    return False


def logout() -> None:
    """Clear authentication state for the current browser session."""
    st.session_state.pop(_AUTHENTICATED_KEY, None)
    st.session_state.pop(_AUTH_USERNAME_KEY, None)
    st.session_state.pop("username", None)


def show_login() -> bool:
    """Render the login screen and return True only for authenticated sessions."""
    if is_authenticated():
        return True

    st.markdown(
        """
        <div style="max-width:520px;margin:8vh auto 1rem;text-align:center">
          <div style="font-size:2.4rem;font-weight:800">AICompanyOS</div>
          <div style="color:#c4b5fd">منصة إدارة الأعمال والوكلاء الذكيين</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    configured_username, configured_password = _configured_credentials()
    if not configured_username or not configured_password:
        st.error(
            "لم يتم إعداد بيانات الدخول. عيّن AICOS_AUTH_USERNAME و"
            "AICOS_AUTH_PASSWORD في متغيرات البيئة، أو أضفهما إلى "
            "Streamlit secrets داخل القسم [auth]."
        )
        return False

    with st.form("aicos_login"):
        st.subheader("تسجيل الدخول")
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        submitted = st.form_submit_button("دخول", type="primary", use_container_width=True)

    if submitted:
        if authenticate(username, password):
            st.rerun()
        else:
            st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")

    return False
