#!/usr/bin/env python3
"""
Mijn Resultaten - Simpele resultaten view voor dagelijks werk
Alleen de essentie: wat is er geclassificeerd, verdeling JA/NEE/ONZEKER
"""
from datetime import date, timedelta
import streamlit as st
from sqlalchemy import text
import pandas as pd

from src.models.database import SessionLocal


# Configure page to use full width
st.set_page_config(layout="wide")

st.title("Mijn Resultaten")
st.caption("Overzicht van geclassificeerde werkbonnen")

# === LAATSTE RESULTATEN ===
@st.cache_data(ttl=60)  # Cache 1 minuut
def get_recent_results(days=7):
    """Haal recente classificaties op."""
    session = SessionLocal()

    # Totalen per classificatie
    result = session.execute(text("""
        SELECT
            classificatie,
            COUNT(*) as aantal,
            AVG(mapping_score) as avg_score
        FROM contract_checker.classifications
        WHERE modus = 'classificatie'
          AND created_at >= CURRENT_DATE - :days * INTERVAL '1 day'
        GROUP BY classificatie
        ORDER BY
            CASE classificatie
                WHEN 'JA' THEN 1
                WHEN 'NEE' THEN 2
                WHEN 'ONZEKER' THEN 3
            END
    """).bindparams(days=days))

    totalen = [{"classificatie": r[0], "aantal": r[1], "avg_score": r[2]} for r in result.fetchall()]

    # Laatste 20 classificaties
    result = session.execute(text("""
        SELECT
            werkbon_id,
            classificatie,
            mapping_score,
            contract_referentie,
            toelichting,
            created_at
        FROM contract_checker.classifications
        WHERE modus = 'classificatie'
        ORDER BY created_at DESC
        LIMIT 20
    """))

    laatste = [{
        "werkbon_id": r[0],
        "classificatie": r[1],
        "score": r[2],
        "artikel": r[3],
        "toelichting": r[4],
        "datum": r[5]
    } for r in result.fetchall()]

    session.close()
    return totalen, laatste

# Periode selectie
col_period, col_refresh = st.columns([3, 1])
with col_period:
    periode = st.selectbox(
        "Bekijk resultaten van:",
        options=[7, 14, 30, 90],
        format_func=lambda x: f"Laatste {x} dagen",
        index=0
    )
with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)  # Spacing
    if st.button("🔄 Ververs", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

totalen, laatste = get_recent_results(periode)

# === GROTE GETALLEN ===
st.markdown("### Verdeling")

if not totalen:
    st.info(f"📭 Geen classificaties gevonden in de laatste {periode} dagen.")
else:
    # Maak dictionary voor makkelijke lookup
    totalen_dict = {t["classificatie"]: t for t in totalen}

    col1, col2, col3 = st.columns(3)

    ja_data = totalen_dict.get("JA", {"aantal": 0, "avg_score": 0})
    with col1:
        st.markdown(f"""
        <div style="padding: 2rem; background: #dcfce7; border-radius: 1rem; text-align: center; border: 3px solid #22c55e;">
            <div style="font-size: 4rem; margin-bottom: 0.5rem;">✅</div>
            <div style="font-size: 3rem; font-weight: bold; color: #166534;">{ja_data["aantal"]}</div>
            <div style="font-size: 1.2rem; color: #166534; margin-top: 0.5rem;">Binnen contract</div>
            <div style="font-size: 0.9rem; color: #166534; margin-top: 0.5rem;">Gem. score: {ja_data["avg_score"]:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    nee_data = totalen_dict.get("NEE", {"aantal": 0, "avg_score": 0})
    with col2:
        st.markdown(f"""
        <div style="padding: 2rem; background: #fee2e2; border-radius: 1rem; text-align: center; border: 3px solid #ef4444;">
            <div style="font-size: 4rem; margin-bottom: 0.5rem;">❌</div>
            <div style="font-size: 3rem; font-weight: bold; color: #991b1b;">{nee_data["aantal"]}</div>
            <div style="font-size: 1.2rem; color: #991b1b; margin-top: 0.5rem;">Te factureren</div>
            <div style="font-size: 0.9rem; color: #991b1b; margin-top: 0.5rem;">Gem. score: {nee_data["avg_score"]:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    onzeker_data = totalen_dict.get("ONZEKER", {"aantal": 0, "avg_score": 0})
    with col3:
        st.markdown(f"""
        <div style="padding: 2rem; background: #fed7aa; border-radius: 1rem; text-align: center; border: 3px solid #f97316;">
            <div style="font-size: 4rem; margin-bottom: 0.5rem;">❓</div>
            <div style="font-size: 3rem; font-weight: bold; color: #9a3412;">{onzeker_data["aantal"]}</div>
            <div style="font-size: 1.2rem; color: #9a3412; margin-top: 0.5rem;">Handmatig checken</div>
            <div style="font-size: 0.9rem; color: #9a3412; margin-top: 0.5rem;">Gem. score: {onzeker_data["avg_score"]:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # === TABEL MET LAATSTE ===
    st.markdown("### Laatste 20 classificaties")

    if laatste:
        # Maak dataframe
        df = pd.DataFrame(laatste)
        df["datum"] = pd.to_datetime(df["datum"]).dt.strftime("%d-%m-%Y %H:%M")
        df["score"] = pd.to_numeric(df["score"], errors='coerce').round(2)

        # Hernoem kolommen voor duidelijkheid
        df_display = df[[
            "werkbon_id", "classificatie", "score", "artikel", "toelichting", "datum"
        ]].copy()
        df_display.columns = ["Werkbon", "Classificatie", "Score", "Artikel", "Toelichting", "Datum"]

        # Kleur per classificatie
        def highlight_classificatie(row):
            if row["Classificatie"] == "JA":
                return ["background-color: #dcfce7"] * len(row)
            elif row["Classificatie"] == "NEE":
                return ["background-color: #fee2e2"] * len(row)
            elif row["Classificatie"] == "ONZEKER":
                return ["background-color: #fed7aa"] * len(row)
            return [""] * len(row)

        styled_df = df_display.style.apply(highlight_classificatie, axis=1)

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            height=600
        )
    else:
        st.info("Geen recente classificaties gevonden.")

st.divider()

# === ACTIES ===
col_a, col_b = st.columns(2)

with col_a:
    if st.button("⚡ Nieuwe classificatie", type="primary", use_container_width=True):
        st.switch_page("pages/20_Quick_Classificatie.py")

with col_b:
    if st.button("📊 Alle resultaten (uitgebreid)", use_container_width=True):
        st.switch_page("pages/4_Results.py")
