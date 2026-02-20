#!/usr/bin/env python3
"""Classificatie Opdracht - De taak die we aan de LLM stellen."""
from datetime import datetime

import streamlit as st

from src.models import db
from src.models.client_config import ClientConfig


# Configure page to use full width
st.set_page_config(layout="wide")

st.title("Classificatie Opdracht")
st.caption("Definieer de taak die aan de LLM wordt gesteld voor classificatie")


def get_client_config(client_code: str = "WVC") -> ClientConfig:
    """Get or create client configuration."""
    session = db()
    try:
        config = session.query(ClientConfig).filter(
            ClientConfig.client_code == client_code,
            ClientConfig.active == True
        ).first()

        if not config:
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


def save_opdracht(config_id: int, opdracht: str, output_format: str) -> bool:
    """Save classification task configuration."""
    session = db()
    try:
        config = session.query(ClientConfig).filter(ClientConfig.id == config_id).first()
        if config:
            config.classificatie_opdracht = opdracht
            config.classificatie_output_format = output_format
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
De classificatie opdracht definieert wat we de LLM vragen te doen.
Dit is de "taak" die bovenaan elke classificatie prompt staat.
""")

# Explanation of the three layers
with st.expander("Hoe werkt de prompt opbouw?"):
    st.markdown("""
    De volledige prompt naar de LLM bestaat uit drie lagen:

    | Laag | Bron | Beschrijving |
    |------|------|--------------|
    | **1. Opdracht** | Deze pagina | Wat moet de LLM doen? |
    | **2. Bedrijfscontext** | Bedrijfscontext pagina | Hoe werkt het bedrijf? |
    | **3. Contract** | Contracten pagina | Het relevante contract (LLM-ready) |
    | **4. Werkbon Details** | Automatisch (SQL) | Werkbon + paragrafen + kostenregels |

    De LLM ontvangt:
    ```
    [OPDRACHT + BEDRIJFSCONTEXT]  <- System prompt

    [CONTRACT]                     <- User message
    [WERKBON DETAILS]
    Classificeer deze werkbon.
    ```

    **Let op**: De LLM beoordeelt nu ELKE kostenregel afzonderlijk, niet alleen de werkbon als geheel.
    """)

st.divider()

# Form for the classification task
with st.form("opdracht_form"):
    st.subheader("Taakbeschrijving")
    st.caption("Wat moet de LLM doen bij het classificeren van werkbonnen?")

    # Get current value or default
    default_opdracht = getattr(config, 'classificatie_opdracht', None) or """Je bent een expert in het analyseren van servicecontracten voor verwarmingssystemen.

Je taak is om te bepalen of de werkzaamheden op een werkbon binnen of buiten een servicecontract vallen.

Analyseer de werkbon en vergelijk met de contractvoorwaarden. Let op:
- Type werkzaamheden (onderhoud, reparatie, storing, modificatie)
- Materialen en onderdelen die zijn gebruikt
- Of de werkzaamheden onder de contractuele dekking vallen
- Specifieke uitsluitingen in het contract"""

    opdracht = st.text_area(
        "Opdracht",
        value=default_opdracht,
        height=200,
        help="Dit is de hoofdinstructie voor de LLM"
    )

    st.divider()

    st.subheader("Output formaat")
    st.caption("Hoe moet de LLM antwoorden?")

    default_output = getattr(config, 'classificatie_output_format', None) or """Geef je antwoord in het volgende JSON formaat:
{
    "classificatie": "JA" | "NEE" | "ONZEKER" | "GEDEELTELIJK",
    "mapping_score": 0.0-1.0,
    "contract_referentie": "Verwijzing naar relevante contract artikel(en)",
    "toelichting": "Korte uitleg van je redenering op werkbon niveau",
    "kostenregels": [
        {
            "kostenregel_key": 12345,
            "classificatie": "JA" | "NEE" | "ONZEKER",
            "reden": "Uitleg waarom deze kostenregel binnen/buiten contract valt"
        }
    ]
}

Classificatie betekenis (werkbon niveau):
- JA: Alle werkzaamheden vallen binnen het contract (niet factureerbaar aan huurder)
- NEE: Alle werkzaamheden vallen buiten het contract (wel factureerbaar)
- GEDEELTELIJK: Sommige kostenregels binnen, andere buiten contract
- ONZEKER: Niet duidelijk, handmatige review nodig

Classificatie betekenis (kostenregel niveau):
- JA: Deze specifieke kosten vallen binnen het contract
- NEE: Deze specifieke kosten vallen buiten het contract
- ONZEKER: Niet duidelijk voor deze kostenregel

mapping_score: Je zekerheid over de werkbon classificatie (0.0 = zeer onzeker, 1.0 = zeer zeker)

BELANGRIJK: Beoordeel ELKE kostenregel afzonderlijk in het "kostenregels" array."""

    output_format = st.text_area(
        "Output formaat",
        value=default_output,
        height=200,
        help="Dit vertelt de LLM hoe het antwoord gestructureerd moet zijn"
    )

    submitted = st.form_submit_button("Opslaan", type="primary")

    if submitted:
        success = save_opdracht(config.id, opdracht, output_format)
        if success:
            st.success("Opdracht opgeslagen!")
            st.rerun()

st.divider()

# Preview section
st.subheader("Preview: Volledige System Prompt")
st.caption("Dit is wat de LLM ontvangt als system prompt (opdracht + bedrijfscontext)")

# Get bedrijfscontext
bedrijfscontext = ""
if hasattr(config, 'werkwijze') and config.werkwijze:
    bedrijfscontext = f"\n\n## Bedrijfscontext\n{config.werkwijze}"
if hasattr(config, 'contract_context') and config.contract_context:
    bedrijfscontext += f"\n\n## Contract interpretatie\n{config.contract_context}"

full_system_prompt = f"""{opdracht}

{output_format}{bedrijfscontext}"""

st.code(full_system_prompt, language="markdown")

# Show what's missing
if not bedrijfscontext:
    st.warning("Bedrijfscontext is nog niet ingevuld. Ga naar de Bedrijfscontext pagina om dit in te stellen.")
