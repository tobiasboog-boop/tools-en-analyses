import streamlit as st
from pathlib import Path


def show_logo():
    """Toon Notifica logo bovenaan de sidebar."""
    logo_path = Path(__file__).parent.parent / "assets" / "notifica-logo-kleur.svg"
    if logo_path.exists():
        st.sidebar.image(str(logo_path), width=140)
