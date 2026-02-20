#!/usr/bin/env python3
"""Bedrijfscontext - Hoe werkt de klant-organisatie (bijv. WVC)."""
from datetime import datetime

import streamlit as st

from src.models import db, ClientConfig


# Configure page to use full width
st.set_page_config(layout="wide")

st.title("Bedrijfscontext")
st.caption("Beschrijf hoe de klant-organisatie werkt met contracten, werkbonnen en Syntess")


def get_client_config(client_code: str = "WVC") -> ClientConfig:
    """Get or create client configuration."""
    session = db()
    try:
        config = session.query(ClientConfig).filter(
            ClientConfig.client_code == client_code,
            ClientConfig.active == True
        ).first()

        if not config:
            # Create default config
            config = ClientConfig(
                client_code=client_code,
                client_name=f"{client_code} Groep",
                active=True
            )
            session.add(config)
            session.commit()
            session.refresh(config)

        session.expunge(config)
        return config
    finally:
        session.close()


def save_client_config(
    config_id: int,
    client_name: str,
    werkwijze: str,
    syntess_context: str,
    werkbon_context: str,
    contract_context: str
) -> bool:
    """Save client configuration."""
    session = db()
    try:
        config = session.query(ClientConfig).filter(ClientConfig.id == config_id).first()
        if config:
            config.client_name = client_name or None
            config.werkwijze = werkwijze or None
            config.syntess_context = syntess_context or None
            config.werkbon_context = werkbon_context or None
            config.contract_context = contract_context or None
            config.updated_at = datetime.utcnow()
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        st.error(f"Fout bij opslaan: {e}")
        return False
    finally:
        session.close()


# Load current config
config = get_client_config("WVC")

st.info("""
De bedrijfscontext beschrijft hoe de klant-organisatie werkt:
- Hoe gaan zij om met contracten?
- Hoe werken zij met Syntess?
- Hoe verwerken zij werkbonnen?

Dit wordt samen met de classificatie opdracht meegegeven aan de LLM.
""")

# Form for editing
with st.form("client_config_form"):
    st.subheader("Klant identificatie")

    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Klant code", value=config.client_code, disabled=True)
    with col2:
        client_name = st.text_input(
            "Klant naam",
            value=config.client_name or "",
            placeholder="Bijv: WVC Groep"
        )

    st.divider()

    # Main workflow description
    st.subheader("Algemene werkwijze")
    st.caption(
        "Beschrijf in algemene termen hoe de klant werkt. "
        "Dit is de belangrijkste context voor de LLM."
    )
    werkwijze = st.text_area(
        "Werkwijze",
        value=config.werkwijze or "",
        height=200,
        placeholder="""Beschrijf hier de algemene werkwijze van de klant. Bijvoorbeeld:

- WVC is een woningcorporatie die onderhoud uitbesteedt aan aannemers
- Werkbonnen komen binnen via Syntess en moeten geclassificeerd worden
- Per aannemer (relatie) is er een contract met specifieke tarieven
- Werkbonnen moeten gekoppeld worden aan de juiste contractregel
- etc."""
    )

    # Submit button for werkwijze
    submitted_werkwijze = st.form_submit_button("💾 Opslaan", type="primary")

    if submitted_werkwijze:
        success = save_client_config(
            config_id=config.id,
            client_name=client_name,
            werkwijze=werkwijze,
            syntess_context=config.syntess_context or "",
            werkbon_context=config.werkbon_context or "",
            contract_context=config.contract_context or ""
        )
        if success:
            st.success("Werkwijze opgeslagen!")
            st.rerun()

st.divider()

# Optional: more specific context sections
st.subheader("Specifieke context (optioneel)")
st.caption("Voor meer gedetailleerde instructies per onderwerp")

with st.form("specific_context_form"):
    tab1, tab2, tab3 = st.tabs(["Syntess", "Werkbonnen", "Contracten"])

    with tab1:
        syntess_context = st.text_area(
            "Syntess configuratie",
            value=config.syntess_context or "",
            height=150,
            placeholder="""Specifieke Syntess instellingen en conventies:

- Welke velden worden gebruikt
- Hoe kostenplaatsen werken
- Categorie structuur
- etc."""
        )

    with tab2:
        werkbon_context = st.text_area(
            "Werkbon verwerking",
            value=config.werkbon_context or "",
            height=150,
            placeholder="""Hoe werkbonnen gestructureerd en verwerkt worden:

- Welke informatie staat in de omschrijving
- Hoe zijn kosten opgebouwd
- Welke statussen worden gebruikt
- etc."""
        )

    with tab3:
        contract_context = st.text_area(
            "Contract interpretatie",
            value=config.contract_context or "",
            height=150,
            placeholder="""Hoe contracten geinterpreteerd moeten worden:

- Hoe tarieven matchen met werkbonregels
- Wanneer iets wel/niet onder contract valt
- Uitzonderingen en speciale gevallen
- etc."""
        )

    # Submit button for specific context
    submitted_context = st.form_submit_button("💾 Opslaan", type="primary")

    if submitted_context:
        success = save_client_config(
            config_id=config.id,
            client_name=config.client_name or "",
            werkwijze=config.werkwijze or "",
            syntess_context=syntess_context,
            werkbon_context=werkbon_context,
            contract_context=contract_context
        )
        if success:
            st.success("Specifieke context opgeslagen!")
            st.rerun()

# Preview section
st.divider()
st.subheader("Preview: LLM Context")
st.caption("Dit is de gecombineerde context die aan de LLM wordt meegegeven")

# Rebuild context from current form values (not saved yet)
preview_parts = []
if werkwijze:
    preview_parts.append(f"## Algemene werkwijze {client_name or config.client_code}\n{werkwijze}")
if syntess_context:
    preview_parts.append(f"## Syntess configuratie\n{syntess_context}")
if werkbon_context:
    preview_parts.append(f"## Werkbon verwerking\n{werkbon_context}")
if contract_context:
    preview_parts.append(f"## Contract interpretatie\n{contract_context}")

if preview_parts:
    st.code("\n\n".join(preview_parts), language="markdown")
else:
    st.warning("Nog geen context ingevuld")
