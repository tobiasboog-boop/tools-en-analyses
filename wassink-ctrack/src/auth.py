import streamlit as st


def check_password():
    """Simple password gate. Returns True if authenticated."""
    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        "<div style='max-width: 400px; margin: 80px auto; text-align: center;'>"
        "<h2>Wassink Vlootbeheer</h2>"
        "<p style='color: #666;'>Voer het wachtwoord in om toegang te krijgen.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.form("login", clear_on_submit=True):
        password = st.text_input("Wachtwoord", type="password")
        submitted = st.form_submit_button("Inloggen", use_container_width=True)

    if submitted:
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Onjuist wachtwoord.")

    return False
