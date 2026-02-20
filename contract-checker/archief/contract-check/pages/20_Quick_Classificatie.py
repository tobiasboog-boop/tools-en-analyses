#!/usr/bin/env python3
"""
Quick Classificatie - Simpele UI voor dagelijks werk
Voor backoffice medewerkers die snel willen classificeren zonder gedoe.
"""
from datetime import date, timedelta
import streamlit as st
from sqlalchemy import text

from src.models.database import SessionLocal
from src.services.classifier import ClassificationService
from src.services.werkbon_keten_service import WerkbonKetenService, WerkbonVerhaalBuilder
from src.models.classification import Classification
from src.models import db


# Configure page to use full width
st.set_page_config(layout="wide")

st.title("Quick Classificatie")
st.caption("Snel werkbonnen classificeren - geen gedoe, gewoon doen!")

# === HOEVEEL WACHTEN ER? ===
@st.cache_data(ttl=60)  # Cache 1 minuut
def get_waiting_count():
    """Hoeveel werkbonnen wachten op classificatie?"""
    session = SessionLocal()

    # Haal al beoordeelde hoofdwerkbon keys op
    result = session.execute(text("""
        SELECT DISTINCT hoofdwerkbon_key
        FROM contract_checker.classifications
        WHERE modus = 'classificatie'
    """))
    beoordeeld = {row[0] for row in result.fetchall()}

    # Tel uitgevoerd + openstaand werkbonnen (laatste 30 dagen)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    result = session.execute(text("""
        SELECT
            w."WerkbonDocumentKey"
        FROM werkbonnen."Werkbonnen" w
        JOIN stam."Documenten" d ON d."DocumentKey" = w."WerkbonDocumentKey"
        WHERE TRIM(w."Status") = 'Uitgevoerd'
          AND TRIM(w."Documentstatus") = 'Openstaand'
          AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
          AND d."Aanmaakdatum" >= :start_date
          AND d."Aanmaakdatum" <= :end_date
        ORDER BY d."Aanmaakdatum" DESC
        LIMIT 100
    """), {"start_date": start_date, "end_date": end_date})

    alle_werkbonnen = [row[0] for row in result.fetchall()]

    # Filter al beoordeelde
    te_doen = [wb for wb in alle_werkbonnen if wb not in beoordeeld]

    session.close()
    return len(te_doen), len(alle_werkbonnen), te_doen[:50]  # Max 50 per keer

wachtend, totaal, werkbonnen_todo = get_waiting_count()

# === GROTE STATUS ===
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div style="padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 1rem; text-align: center; color: white;">
        <div style="font-size: 3rem; font-weight: bold; margin-bottom: 0.5rem;">{wachtend}</div>
        <div style="font-size: 1.2rem;">Wachten op classificatie</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div style="padding: 2rem; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border-radius: 1rem; text-align: center; color: white;">
        <div style="font-size: 3rem; font-weight: bold; margin-bottom: 0.5rem;">{totaal}</div>
        <div style="font-size: 1.2rem;">Totaal laatste 30 dagen</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    # Haal laatste classificatie datum op
    session = SessionLocal()
    result = session.execute(text("""
        SELECT MAX(created_at)::date
        FROM contract_checker.classifications
        WHERE modus = 'classificatie'
    """))
    laatste_classificatie = result.fetchone()[0]
    session.close()

    laatste_text = laatste_classificatie.strftime("%d-%m-%Y") if laatste_classificatie else "Nog nooit"

    st.markdown(f"""
    <div style="padding: 2rem; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border-radius: 1rem; text-align: center; color: white;">
        <div style="font-size: 1.5rem; font-weight: bold; margin-bottom: 0.5rem;">{laatste_text}</div>
        <div style="font-size: 1.2rem;">Laatst geclassificeerd</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# === START CLASSIFICATIE ===
if wachtend == 0:
    st.success("🎉 Geen werkbonnen te doen! Alles is al geclassificeerd.")
    st.balloons()

    if st.button("🔄 Ververs", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
else:
    st.info(f"📋 Er staan **{wachtend} werkbonnen** klaar om geclassificeerd te worden.")

    # Hoeveel doen we?
    aantal_te_doen = min(wachtend, 50)
    st.caption(f"We classificeren maximaal {aantal_te_doen} werkbonnen per keer.")

    st.divider()

    # GROTE START KNOP
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        if st.button("▶️ START CLASSIFICATIE", type="primary", use_container_width=True):
            st.session_state.classificatie_gestart = True
            st.rerun()

# === CLASSIFICATIE PROCES ===
if st.session_state.get("classificatie_gestart"):
    st.divider()
    st.markdown("### 🤖 Bezig met classificeren...")

    # Load werkbonnen met details
    session = SessionLocal()

    # Haal werkbon details op
    werkbonnen_data = []
    for hoofdwerkbon_key in werkbonnen_todo[:aantal_te_doen]:
        result = session.execute(text("""
            SELECT
                w."WerkbonDocumentKey",
                w."HoofdwerkbonDocumentKey",
                COALESCE(TRIM(w."Klant"), '') as klant,
                COALESCE(r."Code" || ' - ' || r."Naam", 'Onbekend') as debiteur,
                w."Omschrijving"
            FROM werkbonnen."Werkbonnen" w
            LEFT JOIN stam."Relaties" r ON r."RelatieKey" = w."DebiteurKey"
            WHERE w."WerkbonDocumentKey" = :key
        """), {"key": hoofdwerkbon_key})

        row = result.fetchone()
        if row:
            werkbonnen_data.append({
                "werkbon": f"W{row[0]}",
                "hoofdwerkbon_key": hoofdwerkbon_key,
                "klant": row[2],
                "debiteur": row[3],
                "omschrijving": row[4]
            })

    session.close()

    if not werkbonnen_data:
        st.error("Geen werkbonnen kunnen laden.")
        st.session_state.classificatie_gestart = False
        st.stop()

    # Initialize services
    keten_service = WerkbonKetenService()
    verhaal_builder = WerkbonVerhaalBuilder()
    classifier = ClassificationService()

    # Progress
    progress_bar = st.progress(0)
    status_text = st.empty()

    results = []
    success_count = 0
    error_count = 0

    for i, wb in enumerate(werkbonnen_data):
        status_text.text(f"Bezig: {wb['werkbon']} ({i+1}/{len(werkbonnen_data)})...")

        try:
            # Load keten
            keten = keten_service.get_werkbon_keten(
                wb["hoofdwerkbon_key"],
                include_kosten_details=True,
                include_opvolgingen=True,
                include_oplossingen=True
            )

            if not keten:
                error_count += 1
                continue

            # Build verhaal
            verhaal = verhaal_builder.build_verhaal(keten)

            # Classify
            werkbon_for_classifier = {
                "werkbon_id": wb["werkbon"],
                "hoofdwerkbon_key": wb["hoofdwerkbon_key"],
                "client_id": keten.relatie_code,  # Key for contract lookup via ContractRelatie
                "klant_naam": wb["klant"],
                "debiteur": wb["debiteur"],
                "omschrijving": verhaal,
                "bedrag": keten.totaal_kosten,
            }

            result = classifier.classify_werkbon(werkbon_for_classifier)
            result["werkbon_nummer"] = wb["werkbon"]
            result["hoofdwerkbon_key"] = wb["hoofdwerkbon_key"]

            results.append(result)
            success_count += 1

        except Exception as e:
            error_count += 1
            st.warning(f"⚠️ Fout bij {wb['werkbon']}: {str(e)[:100]}")

        progress_bar.progress((i + 1) / len(werkbonnen_data))

    keten_service.close()
    status_text.text("Opslaan...")

    # Save to database
    if results:
        session = db()
        try:
            for result in results:
                classification = Classification(
                    werkbon_id=result["werkbon_nummer"],
                    hoofdwerkbon_key=result["hoofdwerkbon_key"],
                    modus="classificatie",
                    classificatie=result["classificatie"],
                    mapping_score=result["mapping_score"],
                    contract_referentie=result.get("contract_referentie"),
                    toelichting=result.get("toelichting"),
                    werkbon_bedrag=result.get("werkbon_bedrag"),
                )
                session.add(classification)
            session.commit()
        except Exception as e:
            session.rollback()
            st.error(f"Fout bij opslaan: {e}")
        finally:
            session.close()

    status_text.empty()
    progress_bar.empty()

    # === RESULTAAT ===
    st.success(f"✅ Klaar! {success_count} werkbonnen geclassificeerd")

    if error_count > 0:
        st.warning(f"⚠️ {error_count} werkbonnen overgeslagen (kon keten niet laden)")

    st.divider()

    # Simpele verdeling
    ja = sum(1 for r in results if r["classificatie"] == "JA")
    nee = sum(1 for r in results if r["classificatie"] == "NEE")
    onzeker = sum(1 for r in results if r["classificatie"] == "ONZEKER")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div style="padding: 2rem; background: #dcfce7; border-radius: 1rem; text-align: center; border: 3px solid #22c55e;">
            <div style="font-size: 4rem; margin-bottom: 0.5rem;">✅</div>
            <div style="font-size: 3rem; font-weight: bold; color: #166534;">{ja}</div>
            <div style="font-size: 1.2rem; color: #166534; margin-top: 0.5rem;">Binnen contract</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="padding: 2rem; background: #fee2e2; border-radius: 1rem; text-align: center; border: 3px solid #ef4444;">
            <div style="font-size: 4rem; margin-bottom: 0.5rem;">❌</div>
            <div style="font-size: 3rem; font-weight: bold; color: #991b1b;">{nee}</div>
            <div style="font-size: 1.2rem; color: #991b1b; margin-top: 0.5rem;">Te factureren</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="padding: 2rem; background: #fed7aa; border-radius: 1rem; text-align: center; border: 3px solid #f97316;">
            <div style="font-size: 4rem; margin-bottom: 0.5rem;">❓</div>
            <div style="font-size: 3rem; font-weight: bold; color: #9a3412;">{onzeker}</div>
            <div style="font-size: 1.2rem; color: #9a3412; margin-top: 0.5rem;">Handmatig checken</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Action buttons
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("🔄 Nog een keer", use_container_width=True):
            st.session_state.classificatie_gestart = False
            st.cache_data.clear()
            st.rerun()

    with col_b:
        if st.button("📊 Bekijk alle resultaten", type="primary", use_container_width=True):
            st.switch_page("pages/4_Results.py")

    with col_c:
        if st.button("🏠 Terug naar Home", use_container_width=True):
            st.session_state.classificatie_gestart = False
            st.switch_page("Home.py")
