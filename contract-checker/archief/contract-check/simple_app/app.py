#!/usr/bin/env python3
"""
Contract Checker - PILOT VERSIE
Met Claude API (Anthropic) en Mark's WerkbonKetenService.
"""
import os
import json
import secrets
import streamlit as st
from dotenv import load_dotenv
import requests
from sqlalchemy import create_engine, text
from datetime import date, timedelta

# Import Mark's werkbon keten service
from werkbon_keten_service import WerkbonKetenService, WerkbonVerhaalBuilder

load_dotenv()

# Claude API settings
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-3-haiku-20240307"  # Snel en goedkoop

# Password protection - generate once and store
PILOT_PASSWORD = os.getenv("PILOT_PASSWORD", "Xk9#mP2$vL7nQ4wR")  # Random generated

# Fixed batch size
BATCH_SIZE = 10

# === PAGE CONFIG ===
st.set_page_config(
    page_title="Contract Checker - PILOT",
    page_icon="🧪",
    layout="wide"
)

# === LOGO ===
import base64
from pathlib import Path

def get_logo_base64():
    """Get logo as base64 for embedding."""
    logo_path = Path(__file__).parent / "assets" / "notifica-logo-kleur.svg"
    if logo_path.exists():
        return logo_path.read_text()
    return None

# === PASSWORD PROTECTION ===
def check_password():
    """Returns True if the user has entered the correct password."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.markdown("""
    <div style="max-width: 400px; margin: 100px auto; padding: 40px; background: #f8fafc; border-radius: 12px; text-align: center;">
        <h2 style="color: #16136F; margin-bottom: 10px;">🔒 Contract Checker</h2>
        <p style="color: #64748b; margin-bottom: 20px;">PILOT - Toegang beperkt</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("Wachtwoord", type="password", key="password_input")
        if st.button("Inloggen", type="primary", use_container_width=True):
            if password == PILOT_PASSWORD:
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Onjuist wachtwoord")
    return False

if not check_password():
    st.stop()


# === PILOT DISCLAIMER ===
st.markdown("""
<div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); padding: 15px 20px; border-radius: 8px; border-left: 4px solid #f59e0b; margin-bottom: 20px;">
    <strong style="color: #92400e;">⚠️ PILOT VERSIE - NIET VOOR PRODUCTIE</strong>
    <p style="color: #78350f; margin: 8px 0 0 0; font-size: 0.9rem;">
        Deze tool is uitsluitend bedoeld als pilot ter validatie van het classificatiemodel.
        Aan de resultaten kunnen geen rechten worden ontleend met betrekking tot kwaliteit,
        volledigheid of operationele toepassingen. Handmatige controle blijft vereist.
    </p>
</div>
""", unsafe_allow_html=True)


# === DATABASE CONNECTION ===
@st.cache_resource
def get_db_engine():
    """Create database engine."""
    db_url = (
        f"postgresql+psycopg://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', '1210')}"
    )
    return create_engine(db_url, pool_pre_ping=True, pool_recycle=300)


# === USAGE TRACKING ===
def ensure_usage_table():
    """Create pilot_usage table if it doesn't exist."""
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS contract_checker.pilot_usage (
                id SERIAL PRIMARY KEY,
                classification_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT NOW()
            )
        """))
        # Insert initial row if table is empty
        result = conn.execute(text("SELECT COUNT(*) FROM contract_checker.pilot_usage"))
        if result.scalar() == 0:
            conn.execute(text("INSERT INTO contract_checker.pilot_usage (classification_count) VALUES (0)"))
        conn.commit()


def get_usage_count():
    """Get total number of classifications."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COALESCE(classification_count, 0)
                FROM contract_checker.pilot_usage
                LIMIT 1
            """))
            row = result.fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


def increment_usage(count: int = 1):
    """Increment the classification counter."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE contract_checker.pilot_usage
                SET classification_count = classification_count + :count,
                    last_updated = NOW()
            """), {"count": count})
            conn.commit()
    except Exception as e:
        print(f"Warning: Could not update usage counter: {e}")


def get_contracts_from_db():
    """Load all active contracts from database."""
    engine = get_db_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, filename, llm_ready, content
            FROM contract_checker.contracts
            WHERE active = true
            ORDER BY filename
        """))
        contracts = {}
        for row in result:
            content = row[2] if row[2] else row[3]  # llm_ready or content
            if content:
                contracts[row[0]] = {
                    "id": row[0],
                    "filename": row[1],
                    "content": content
                }
        return contracts


def get_contract_for_debiteur(debiteur_code: str, contracts: dict):
    """Get contract for a specific debiteur via contract_relatie."""
    engine = get_db_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT contract_id
            FROM contract_checker.contract_relatie
            WHERE client_id = :debiteur_code
            LIMIT 1
        """), {"debiteur_code": debiteur_code})
        row = result.fetchone()
        if row and row[0] in contracts:
            return contracts[row[0]]
        return None


def get_werkbonnen_batch(start_date: date, end_date: date, contract_filter: list = None, limit: int = 10):
    """Load a batch of werkbonnen that need classification with filters."""
    engine = get_db_engine()

    with engine.connect() as conn:
        # Get already classified werkbonnen
        classified = conn.execute(text("""
            SELECT DISTINCT hoofdwerkbon_key
            FROM contract_checker.classifications
            WHERE modus = 'classificatie'
        """))
        classified_keys = {row[0] for row in classified}

        # Build contract filter
        contract_clause = ""
        params = {"start_date": start_date, "end_date": end_date, "limit": limit + 50}

        if contract_filter and len(contract_filter) > 0:
            placeholders = ", ".join([f":contract_{i}" for i in range(len(contract_filter))])
            contract_clause = f"AND c.id IN ({placeholders})"
            for i, cid in enumerate(contract_filter):
                params[f"contract_{i}"] = cid

        result = conn.execute(text(f"""
            SELECT
                w."WerkbonDocumentKey" as key,
                w."HoofdwerkbonDocumentKey" as hoofdwerkbon_key,
                r."Relatie Code" as debiteur_code,
                COALESCE(w."Debiteur", 'Onbekend') as debiteur,
                COALESCE(TRIM(w."Klant"), '') as klant,
                w."Werkbon" as werkbon_nummer,
                d."Aanmaakdatum" as datum,
                c.filename as contract_filename,
                c.id as contract_id
            FROM werkbonnen."Werkbonnen" w
            JOIN stam."Documenten" d ON d."DocumentKey" = w."WerkbonDocumentKey"
            JOIN stam."Relaties" r ON r."RelatieKey" = w."DebiteurRelatieKey"
            JOIN contract_checker.contract_relatie cr ON cr.client_id = r."Relatie Code"
            JOIN contract_checker.contracts c ON c.id = cr.contract_id AND c.active = true
            WHERE TRIM(w."Status") = 'Uitgevoerd'
              AND TRIM(w."Documentstatus") = 'Openstaand'
              AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
              AND d."Aanmaakdatum" >= :start_date
              AND d."Aanmaakdatum" <= :end_date
              {contract_clause}
            ORDER BY d."Aanmaakdatum" DESC
            LIMIT :limit
        """), params)

        werkbonnen = []
        for row in result:
            if row[1] in classified_keys:
                continue
            if len(werkbonnen) >= limit:
                break
            werkbonnen.append({
                "key": row[0],
                "hoofdwerkbon_key": row[1],
                "debiteur_code": row[2],
                "debiteur": row[3],
                "klant": row[4],
                "werkbon_nummer": row[5],
                "datum": row[6],
                "contract_filename": row[7],
                "contract_id": row[8]
            })
        return werkbonnen


def count_pending_werkbonnen(start_date: date, end_date: date, contract_filter: list = None):
    """Count werkbonnen with filters."""
    engine = get_db_engine()

    with engine.connect() as conn:
        params = {"start_date": start_date, "end_date": end_date}
        contract_clause = ""

        if contract_filter and len(contract_filter) > 0:
            placeholders = ", ".join([f":contract_{i}" for i in range(len(contract_filter))])
            contract_clause = f"AND c.id IN ({placeholders})"
            for i, cid in enumerate(contract_filter):
                params[f"contract_{i}"] = cid

        result = conn.execute(text(f"""
            SELECT COUNT(*)
            FROM werkbonnen."Werkbonnen" w
            JOIN stam."Documenten" d ON d."DocumentKey" = w."WerkbonDocumentKey"
            JOIN stam."Relaties" r ON r."RelatieKey" = w."DebiteurRelatieKey"
            JOIN contract_checker.contract_relatie cr ON cr.client_id = r."Relatie Code"
            JOIN contract_checker.contracts c ON c.id = cr.contract_id AND c.active = true
            WHERE TRIM(w."Status") = 'Uitgevoerd'
              AND TRIM(w."Documentstatus") = 'Openstaand'
              AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
              AND d."Aanmaakdatum" >= :start_date
              AND d."Aanmaakdatum" <= :end_date
              {contract_clause}
        """), params)
        total = result.scalar()

        result = conn.execute(text("""
            SELECT COUNT(DISTINCT hoofdwerkbon_key)
            FROM contract_checker.classifications
            WHERE modus = 'classificatie'
        """))
        classified = result.scalar()

        return total, classified


# === CLAUDE API (ANTHROPIC) ===
def check_claude_status():
    """Check if Claude API key is configured."""
    if not ANTHROPIC_API_KEY:
        return False, "Geen API key"
    if not ANTHROPIC_API_KEY.startswith("sk-ant-"):
        return False, "Ongeldige API key"
    return True, "API key geconfigureerd"


def call_claude(system_prompt: str, user_message: str) -> str:
    """Call Claude API via Anthropic."""
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_message}
        ]
    }

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=60
    )
    response.raise_for_status()
    data = response.json()
    return data["content"][0]["text"]


def classify_werkbon(
    contract_text: str,
    werkbon_verhaal: str,
    threshold_ja: float,
    threshold_nee: float
) -> dict:
    """Classify werkbon against contract using Claude API."""

    system_prompt = """Je bent een expert in het analyseren van servicecontracten voor verwarmingssystemen.

Je taak is om te bepalen of een werkbon binnen of buiten een servicecontract valt.

Analyseer het werkbon verhaal en vergelijk met de contractvoorwaarden. Let op:
- Type werkzaamheden (onderhoud, reparatie, storing, modificatie)
- Gebruikte materialen en onderdelen
- Arbeidsuren en kostenposten
- Specifieke uitsluitingen in het contract
- Storingscodes en oorzaken

Geef je antwoord ALLEEN in het volgende JSON formaat:
{
    "classificatie": "JA" of "NEE",
    "confidence": 0.0-1.0,
    "contract_referentie": "Verwijzing naar relevant contract artikel",
    "toelichting": "Korte uitleg van je redenering"
}

Classificatie:
- JA: Werkzaamheden vallen volledig binnen het contract (niet factureren aan klant)
- NEE: Werkzaamheden vallen buiten het contract (wel factureren aan klant)

confidence: Je zekerheid over de classificatie (0.0 = zeer onzeker, 1.0 = zeer zeker)

BELANGRIJK: Geef ALTIJD een classificatie (JA of NEE), ook als je onzeker bent.
De confidence score geeft aan hoe zeker je bent."""

    # Truncate contract if too long (keep first 15000 chars)
    contract_truncated = contract_text[:15000] if len(contract_text) > 15000 else contract_text

    user_message = f"""### CONTRACT ###
{contract_truncated}

### WERKBON VERHAAL ###
{werkbon_verhaal}

Classificeer deze werkbon. Geef je antwoord in JSON formaat."""

    # Call Claude API
    response_text = call_claude(system_prompt, user_message)

    # Parse response
    try:
        text = response_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())

        confidence = float(result.get("confidence", 0.5))
        base_classificatie = result.get("classificatie", "NEE").upper()

        # Apply thresholds
        if base_classificatie == "JA":
            final = "JA" if confidence >= threshold_ja else "TWIJFEL"
        else:
            final = "NEE" if confidence >= threshold_nee else "TWIJFEL"

        return {
            "classificatie": final,
            "basis_classificatie": base_classificatie,
            "confidence": confidence,
            "contract_referentie": result.get("contract_referentie", ""),
            "toelichting": result.get("toelichting", ""),
            "raw_response": response_text
        }

    except (json.JSONDecodeError, KeyError) as e:
        return {
            "classificatie": "TWIJFEL",
            "basis_classificatie": "ONBEKEND",
            "confidence": 0.0,
            "contract_referentie": "",
            "toelichting": f"Kon response niet parsen: {str(e)}",
            "raw_response": response_text
        }


# === MAIN APP ===

st.title("🧪 Contract Checker - PILOT")
st.caption("Werkbonnen classificeren met volledige context")
st.markdown("[📖 Handleiding & uitleg](https://notifica.nl/tools/contract-checker)", unsafe_allow_html=True)

# === SIDEBAR ===
with st.sidebar:
    # Logo bovenaan sidebar
    logo_svg = get_logo_base64()
    if logo_svg:
        st.image("assets/notifica-logo-kleur.svg", width=140)

    # Ensure usage table exists
    try:
        ensure_usage_table()
    except Exception:
        pass  # Ignore if table creation fails

    st.header("Status")

    # Claude API check
    claude_ok, claude_status = check_claude_status()

    if claude_ok:
        st.success("✅ Claude API")
        st.caption(f"Model: {CLAUDE_MODEL}")
    else:
        st.error(f"❌ {claude_status}")
        st.info("Voeg ANTHROPIC_API_KEY toe aan .env")

    st.divider()

    # Thresholds
    st.header("Drempelwaardes")

    threshold_ja = st.slider("JA drempel", 0.5, 1.0, 0.85, 0.05)
    threshold_nee = st.slider("NEE drempel", 0.5, 1.0, 0.85, 0.05)

    st.info(f"""
    - JA + ≥{threshold_ja:.0%} → **JA**
    - NEE + ≥{threshold_nee:.0%} → **NEE**
    - Anders → **TWIJFEL**
    """)

    st.divider()
    st.caption(f"Batch grootte: {BATCH_SIZE} (vast)")

    # Usage counter
    st.divider()
    st.header("Pilot Gebruik")
    usage_count = get_usage_count()
    st.metric("Geclassificeerd", f"{usage_count} werkbonnen")

    st.markdown("[📖 Handleiding](https://notifica.nl/tools/contract-checker)")

# === MAIN CONTENT ===

if not claude_ok:
    st.warning("⚠️ Claude API niet geconfigureerd")
    st.info("""
    **Configuratie:**
    1. Voeg je Anthropic API key toe aan `.env`:
       `ANTHROPIC_API_KEY=sk-ant-...`
    2. Ververs deze pagina
    """)
    st.stop()

# Load contracts
try:
    contracts = get_contracts_from_db()
    if not contracts:
        st.error("Geen contracten gevonden in database")
        st.stop()
except Exception as e:
    st.error(f"Database fout: {e}")
    st.stop()

# === FILTERS ===
st.header("Filters")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Datumbereik")
    default_end = date.today()
    default_start = default_end - timedelta(days=30)

    date_range = st.date_input(
        "Selecteer periode",
        value=(default_start, default_end),
        max_value=default_end,
        key="date_filter"
    )

    if len(date_range) == 2:
        filter_start, filter_end = date_range
    else:
        filter_start, filter_end = default_start, default_end

with col2:
    st.subheader("Contract")
    contract_options = {c["id"]: c["filename"] for c in contracts.values()}
    selected_contracts = st.multiselect(
        "Filter op contract (leeg = alle)",
        options=list(contract_options.keys()),
        format_func=lambda x: contract_options[x],
        key="contract_filter"
    )

# Count with filters
try:
    total, classified = count_pending_werkbonnen(
        filter_start, filter_end,
        selected_contracts if selected_contracts else None
    )
    pending = total - classified
except Exception as e:
    st.error(f"Fout bij tellen: {e}")
    pending = 0
    total = 0
    classified = 0

st.metric("Te classificeren werkbonnen", pending, delta=f"van {total} totaal")

if pending == 0:
    st.success("🎉 Alle werkbonnen in dit filter zijn geclassificeerd!")
    st.stop()

st.divider()

# === LOAD BATCH ===
st.header(f"Volgende {BATCH_SIZE} werkbonnen")

if st.button("🔄 Laad werkbonnen", type="secondary"):
    st.session_state.werkbonnen_batch = None
    st.session_state.verhalen_cache = {}
    st.rerun()

# Load or use cached batch
if "werkbonnen_batch" not in st.session_state or st.session_state.werkbonnen_batch is None:
    with st.spinner("Werkbonnen laden..."):
        st.session_state.werkbonnen_batch = get_werkbonnen_batch(
            filter_start, filter_end,
            selected_contracts if selected_contracts else None,
            limit=BATCH_SIZE
        )
        st.session_state.verhalen_cache = {}

werkbonnen = st.session_state.werkbonnen_batch

if not werkbonnen:
    st.info("Geen werkbonnen gevonden met de huidige filters")
    st.stop()

st.success(f"{len(werkbonnen)} werkbonnen geladen")

# Show preview
with st.expander(f"Bekijk {len(werkbonnen)} werkbonnen", expanded=True):
    for i, wb in enumerate(werkbonnen):
        contract_name = wb.get("contract_filename", "Contract")
        st.markdown(f"""
        **{i+1}. {wb['debiteur']}** ✅ {contract_name}
        - Werkbon: {wb['werkbon_nummer']} | Datum: {wb['datum']}
        - Klant: {wb['klant']}
        """)

st.divider()

# === CLASSIFY ===
if st.button("🚀 Classificeer batch", type="primary", use_container_width=True):
    results = []
    verhalen_cache = {}
    progress = st.progress(0)
    status = st.empty()

    # Initialize services
    keten_service = WerkbonKetenService()
    verhaal_builder = WerkbonVerhaalBuilder()

    for i, wb in enumerate(werkbonnen):
        status.text(f"Classificeren {i+1}/{len(werkbonnen)}: {wb['debiteur'][:30]}...")

        # Get contract for this debiteur
        contract = get_contract_for_debiteur(wb["debiteur_code"], contracts)

        if not contract:
            results.append({
                "werkbon_key": wb["key"],
                "hoofdwerkbon_key": wb["hoofdwerkbon_key"],
                "debiteur": wb["debiteur"],
                "classificatie": "TWIJFEL",
                "basis_classificatie": "GEEN_CONTRACT",
                "confidence": 0.0,
                "toelichting": "Geen contract gevonden voor deze debiteur",
                "contract_referentie": "",
                "contract_filename": None,
                "verhaal_full": "",
                "verhaal_preview": ""
            })
            progress.progress((i + 1) / len(werkbonnen))
            continue

        try:
            # Get full werkbon keten with all details (Mark's service)
            keten = keten_service.get_werkbon_keten(
                wb["hoofdwerkbon_key"],
                include_kosten_details=True,
                include_opvolgingen=False,
                include_oplossingen=False
            )

            if not keten:
                results.append({
                    "werkbon_key": wb["key"],
                    "hoofdwerkbon_key": wb["hoofdwerkbon_key"],
                    "debiteur": wb["debiteur"],
                    "classificatie": "TWIJFEL",
                    "basis_classificatie": "GEEN_KETEN",
                    "confidence": 0.0,
                    "toelichting": "Kon werkbon keten niet laden",
                    "contract_referentie": "",
                    "contract_filename": contract["filename"],
                    "verhaal_full": "",
                    "verhaal_preview": ""
                })
                progress.progress((i + 1) / len(werkbonnen))
                continue

            # Build narrative (Mark's verhaal builder)
            verhaal = verhaal_builder.build_verhaal(keten)
            verhalen_cache[wb["hoofdwerkbon_key"]] = verhaal

            # Classify
            result = classify_werkbon(
                contract_text=contract["content"],
                werkbon_verhaal=verhaal,
                threshold_ja=threshold_ja,
                threshold_nee=threshold_nee
            )

            result["werkbon_key"] = wb["key"]
            result["hoofdwerkbon_key"] = wb["hoofdwerkbon_key"]
            result["debiteur"] = wb["debiteur"]
            result["contract_filename"] = contract["filename"]
            result["verhaal_full"] = verhaal  # Store full verhaal
            result["verhaal_preview"] = verhaal[:500] + "..." if len(verhaal) > 500 else verhaal
            result["totaal_kosten"] = keten.totaal_kosten
            result["aantal_werkbonnen"] = keten.aantal_werkbonnen
            results.append(result)

        except Exception as e:
            results.append({
                "werkbon_key": wb["key"],
                "hoofdwerkbon_key": wb["hoofdwerkbon_key"],
                "debiteur": wb["debiteur"],
                "classificatie": "TWIJFEL",
                "basis_classificatie": "ERROR",
                "confidence": 0.0,
                "toelichting": f"Fout: {str(e)[:100]}",
                "contract_referentie": "",
                "contract_filename": contract["filename"] if contract else None,
                "verhaal_full": "",
                "verhaal_preview": ""
            })

        progress.progress((i + 1) / len(werkbonnen))

    keten_service.close()
    status.empty()
    progress.empty()

    st.session_state.results = results
    st.session_state.verhalen_cache = verhalen_cache
    st.session_state.werkbonnen_batch = None  # Clear for next batch

    # Update usage counter
    increment_usage(len(results))

    st.success(f"✅ {len(results)} werkbonnen geclassificeerd!")

# === RESULTS ===
if "results" in st.session_state and st.session_state.results:
    results = st.session_state.results

    st.divider()
    st.header("Resultaten")

    # Summary
    ja = sum(1 for r in results if r["classificatie"] == "JA")
    nee = sum(1 for r in results if r["classificatie"] == "NEE")
    twijfel = sum(1 for r in results if r["classificatie"] == "TWIJFEL")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div style="padding: 1.5rem; background: #dcfce7; border-radius: 0.5rem; text-align: center; border: 2px solid #22c55e;">
            <div style="font-size: 2.5rem; font-weight: bold; color: #166534;">{ja}</div>
            <div style="color: #166534;">✅ Binnen contract</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="padding: 1.5rem; background: #fee2e2; border-radius: 0.5rem; text-align: center; border: 2px solid #ef4444;">
            <div style="font-size: 2.5rem; font-weight: bold; color: #991b1b;">{nee}</div>
            <div style="color: #991b1b;">❌ Te factureren</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="padding: 1.5rem; background: #fed7aa; border-radius: 0.5rem; text-align: center; border: 2px solid #f97316;">
            <div style="font-size: 2.5rem; font-weight: bold; color: #9a3412;">{twijfel}</div>
            <div style="color: #9a3412;">❓ Handmatig checken</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Details per result
    for result in results:
        classificatie = result["classificatie"]

        if classificatie == "JA":
            color, border, icon = "#dcfce7", "#22c55e", "✅"
        elif classificatie == "NEE":
            color, border, icon = "#fee2e2", "#ef4444", "❌"
        else:
            color, border, icon = "#fed7aa", "#f97316", "❓"

        kosten_info = f" | €{result.get('totaal_kosten', 0):,.2f}" if result.get('totaal_kosten') else ""
        keten_info = f" | {result.get('aantal_werkbonnen', 1)} bon(nen)" if result.get('aantal_werkbonnen', 1) > 1 else ""

        st.markdown(f"""
        <div style="padding: 1rem; background: {color}; border-radius: 0.5rem; border-left: 4px solid {border}; margin-bottom: 0.5rem;">
            <strong>{icon} {result['debiteur'][:40]}</strong>
            <span style="margin-left: 1rem; padding: 0.2rem 0.5rem; background: white; border-radius: 0.25rem;">
                {classificatie}
            </span>
            <span style="margin-left: 0.5rem; color: #666; font-size: 0.9rem;">
                ({result['confidence']:.0%}){kosten_info}{keten_info}
            </span>
        </div>
        """, unsafe_allow_html=True)

        with st.expander(f"Details - {result['debiteur'][:30]}"):
            # Tabs for different views
            tab1, tab2 = st.tabs(["📋 Classificatie", "📄 Volledige Werkbon Keten"])

            with tab1:
                st.markdown(f"**Toelichting:** {result['toelichting']}")
                st.markdown(f"**Contract:** {result.get('contract_filename', 'N/A')}")
                st.markdown(f"**Referentie:** {result['contract_referentie']}")

                if result.get("verhaal_preview"):
                    st.markdown("**Werkbon verhaal (preview):**")
                    st.code(result["verhaal_preview"], language="markdown")

            with tab2:
                if result.get("verhaal_full"):
                    st.markdown("**Volledige werkbon keten (zoals verzonden naar Claude):**")
                    st.text_area(
                        "Werkbon Keten",
                        result["verhaal_full"],
                        height=400,
                        key=f"verhaal_{result['werkbon_key']}"
                    )
                else:
                    st.info("Geen werkbon keten beschikbaar")

    # Export
    st.divider()
    import pandas as pd
    df = pd.DataFrame([{
        "Debiteur": r["debiteur"],
        "Classificatie": r["classificatie"],
        "Confidence": f"{r['confidence']:.0%}",
        "Kosten": f"€{r.get('totaal_kosten', 0):,.2f}",
        "Toelichting": r["toelichting"],
        "Contract": r.get("contract_filename", "")
    } for r in results])

    st.download_button(
        "📥 Download resultaten",
        df.to_csv(index=False),
        "classificatie_resultaten.csv",
        "text/csv",
        use_container_width=True
    )

    # Next batch button
    st.divider()
    if st.button("➡️ Volgende batch", type="primary", use_container_width=True):
        st.session_state.results = None
        st.rerun()
