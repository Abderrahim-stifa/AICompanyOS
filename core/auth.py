"""Session-based authentication for the Streamlit application.

Configure credentials with AICOS_AUTH_USERNAME and AICOS_AUTH_PASSWORD
environment variables, or Streamlit secrets under [auth].
"""

from __future__ import annotations

import hmac
import os

import streamlit as st

from core.login_throttle import from_env as _throttle_from_env

_AUTHENTICATED_KEY = "aicos_authenticated"
_AUTH_USERNAME_KEY = "aicos_authenticated_username"
_THROTTLE = _throttle_from_env()


def login_lockout_remaining() -> int:
    """Seconds left before login attempts are accepted again (0 = not locked)."""
    return _THROTTLE.retry_after()


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
    except (AttributeError, KeyError, RuntimeError, FileNotFoundError):
        # Streamlit Cloud raises StreamlitSecretNotFoundError (a
        # FileNotFoundError subclass) when no secrets.toml is configured.
        # Treat missing secrets as unconfigured credentials so the login page
        # can render its setup message instead of crashing the whole app.
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
    if _THROTTLE.retry_after():
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
        _THROTTLE.record_success()
        st.session_state[_AUTHENTICATED_KEY] = True
        st.session_state[_AUTH_USERNAME_KEY] = expected_username
        st.session_state["username"] = expected_username
        return True

    _THROTTLE.record_failure()
    return False


def logout() -> None:
    """Clear authentication state for the current browser session."""
    st.session_state.pop(_AUTHENTICATED_KEY, None)
    st.session_state.pop(_AUTH_USERNAME_KEY, None)
    st.session_state.pop("username", None)



def _render_copyright_footer() -> None:
    """Render the author attribution at the bottom of the login screen."""
    st.markdown(
        "<div style='text-align:center; margin:38px auto 18px; padding:14px 8px; "
        "border-top:1px solid rgba(148,163,184,.25); color:#94a3b8; "
        "font-size:12px; line-height:1.9'>"
        "AICompanyOS · © 2026 Abderrahim Stifa<br>"
        "All rights reserved.</div>",
        unsafe_allow_html=True,
    )

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
        _render_copyright_footer()
        return False

    locked_for = login_lockout_remaining()
    if locked_for:
        st.error(
            f"تم إيقاف تسجيل الدخول مؤقتاً بسبب محاولات فاشلة متكررة. "
            f"حاول مجدداً بعد {locked_for} ثانية."
        )
        _render_copyright_footer()
        return False

    with st.form("aicos_login"):
        st.subheader("تسجيل الدخول")
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        submitted = st.form_submit_button("دخول", type="primary", use_container_width=True)

    if submitted:
        if authenticate(username, password):
            st.rerun()
        elif login_lockout_remaining():
            st.rerun()
        else:
            st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")

    _render_copyright_footer()
    return False


def check_password() -> bool:
    """Compatibility entry point: show the login form and gate application access."""
    return show_login()
