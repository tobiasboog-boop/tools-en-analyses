"""Wachtwoord authenticatie voor Streamlit Cloud deployment."""
import os
import streamlit as st


def get_secret(key: str, default: str = "") -> str:
    """Haal een secret op uit Streamlit secrets of environment variable."""
    # Probeer eerst st.secrets (Streamlit Cloud)
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    # Fallback naar environment variable
    return os.getenv(key, default)


def check_password() -> bool:
    """Returns True if the user has the correct password.

    Call this at the start of each protected page.
    """
    # Wachtwoord uit secrets of environment (zelfde als DWH versie)
    correct_password = get_secret("APP_PASSWORD", "Xk9#mP2$vL7nQ4wR")

    def password_entered():
        """Checks if entered password is correct."""
        if st.session_state.get("password") == correct_password:
            st.session_state["password_correct"] = True
            # Don't store password in session state
            if "password" in st.session_state:
                del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    # Already authenticated
    if st.session_state.get("password_correct", False):
        return True

    # Show login form
    st.title("🔐 Contract Check Demo")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.text_input(
            "Wachtwoord",
            type="password",
            on_change=password_entered,
            key="password"
        )

        if st.session_state.get("password_correct") is False:
            st.error("Onjuist wachtwoord")

        st.caption("Neem contact op met Notifica voor toegang")

    return False


def require_auth():
    """Enforce authentication - stops page if not authenticated."""
    if not check_password():
        st.stop()
