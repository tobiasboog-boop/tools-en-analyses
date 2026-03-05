"""
Liquiditeitsprognose Dashboard
==============================
Datagedreven liquiditeitsprognose: Structuur x Volume x Realiteit.

Notifica - Business Intelligence voor installatiebedrijven
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any, Tuple

# Local imports
from config import AppConfig, COLORS, LIQUIDITY_THRESHOLDS
from src.database import get_database, MockDatabase, NotificaDataSource, FailedConnectionDatabase
from src.calculations import (
    calculate_liquidity_metrics,
    create_weekly_cashflow_forecast,
    calculate_aging_buckets,
    create_enhanced_cashflow_forecast,
    calculate_recurring_costs_per_week,
    create_ml_forecast,
    backtest_forecast_model,
    ForecastModelMetrics,
    LiquidityMetrics,
    # Fading Weight Ensemble methode
    create_fading_weight_forecast,
    calculate_dso_adjustment,
    # Nieuwe fasen 3-5
    create_enhanced_forecast,
    DeterministicCostConfig,
    estimate_deterministic_costs_from_history,
    PROPHET_AVAILABLE,
    # NIEUW: 4-Lagen Model (Omzet-first approach)
    create_layered_cashflow_forecast,
    GhostInvoice,
    LayeredForecastResult,
    # NIEUW: Backtesting en Klantinzichten
    create_customer_profile,
    CustomerProfile,
    CustomerInsight,
    BacktestResult,
    run_walk_forward_backtest,
)
from src.daily_forecast import create_daily_forecast
from src.forecast_model import create_forecast_for_app, run_walk_forward_backtest as run_backtest_new
from src.forecast_v7 import create_forecast_v7
from src.customer_insights import generate_customer_insights, generate_insights_markdown

# Klant configuratie
import os
CUSTOMER_CODE = os.getenv("KLANTNUMMER", "1229")
CUSTOMER_NAME = "Zenith"  # Demo klant

# Page configuration
st.set_page_config(
    page_title=f"Liquiditeitsprognose - {CUSTOMER_NAME}",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS with additional styles for transparency indicators
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1E3A5F;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #666;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 10px 15px;
        margin: 10px 0;
    }
    .danger-box {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 10px 15px;
        margin: 10px 0;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 10px 15px;
        margin: 10px 0;
    }
    .transparency-legend {
        background-color: #f0f4f8;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
        font-size: 0.85rem;
    }
    .transparency-legend .realisatie {
        color: #1E3A5F;
        font-weight: 600;
    }
    .transparency-legend .forecast {
        color: #6c757d;
        font-style: italic;
    }
    .filter-section {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# DATA FILTERING FUNCTIONS (gebaseerd op Thin Reports filteropties)
# =============================================================================

def apply_data_filters(
    data: Dict[str, pd.DataFrame],
    filters: Dict[str, Any]
) -> Dict[str, pd.DataFrame]:
    """
    Pas filters toe op de data.

    Ondersteunde filters:
    - administratie: Filter op administratie naam
    - bedrijfseenheid: Filter op bedrijfseenheid
    - bankrekeningen: Filter op specifieke bankrekeningen
    """
    filtered_data = {k: v.copy() for k, v in data.items()}

    # Administratie filter
    admin_filter = filters.get("administratie")
    if admin_filter and admin_filter != "Alle":
        # Filter debiteuren
        if not filtered_data["debiteuren"].empty and "administratie" in filtered_data["debiteuren"].columns:
            filtered_data["debiteuren"] = filtered_data["debiteuren"][
                filtered_data["debiteuren"]["administratie"] == admin_filter
            ]

        # Filter crediteuren
        if not filtered_data["crediteuren"].empty and "administratie" in filtered_data["crediteuren"].columns:
            filtered_data["crediteuren"] = filtered_data["crediteuren"][
                filtered_data["crediteuren"]["administratie"] == admin_filter
            ]

    # Bedrijfseenheid filter
    be_filter = filters.get("bedrijfseenheid")
    if be_filter and be_filter != "Alle":
        # Filter debiteuren
        if not filtered_data["debiteuren"].empty and "bedrijfseenheid" in filtered_data["debiteuren"].columns:
            filtered_data["debiteuren"] = filtered_data["debiteuren"][
                filtered_data["debiteuren"]["bedrijfseenheid"] == be_filter
            ]

        # Filter crediteuren
        if not filtered_data["crediteuren"].empty and "bedrijfseenheid" in filtered_data["crediteuren"].columns:
            filtered_data["crediteuren"] = filtered_data["crediteuren"][
                filtered_data["crediteuren"]["bedrijfseenheid"] == be_filter
            ]

    # Filter banksaldo (op rekening indien filter actief)
    if not filtered_data["banksaldo"].empty:
        bank = filtered_data["banksaldo"]

        if filters.get("bankrekeningen") and len(filters["bankrekeningen"]) > 0:
            if "bank_naam" in bank.columns:
                bank = bank[bank["bank_naam"].isin(filters["bankrekeningen"])]

        filtered_data["banksaldo"] = bank

    return filtered_data


def get_filter_options(data: Dict[str, pd.DataFrame]) -> Dict[str, List[str]]:
    """Haal beschikbare filteropties op uit de data."""
    options = {
        "debiteuren": [],
        "crediteuren": [],
        "bankrekeningen": [],
    }

    if not data["debiteuren"].empty and "debiteur_naam" in data["debiteuren"].columns:
        options["debiteuren"] = sorted(data["debiteuren"]["debiteur_naam"].unique().tolist())

    if not data["crediteuren"].empty and "crediteur_naam" in data["crediteuren"].columns:
        options["crediteuren"] = sorted(data["crediteuren"]["crediteur_naam"].unique().tolist())

    if not data["banksaldo"].empty and "bank_naam" in data["banksaldo"].columns:
        options["bankrekeningen"] = sorted(data["banksaldo"]["bank_naam"].unique().tolist())

    return options


# =============================================================================
# TRANSPARANTIE: REALISATIE vs FORECAST
# =============================================================================

def create_transparent_cashflow_forecast(
    banksaldo: pd.DataFrame,
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    salarissen: pd.DataFrame,
    historisch: pd.DataFrame,
    weeks_history: int = 4,
    weeks_forecast: int = 13,
    debiteur_delay_days: int = 0,
    crediteur_delay_days: int = 0,
    reference_date: date = None,
) -> Tuple[pd.DataFrame, int]:
    """
    Maak cashflow overzicht met duidelijk onderscheid tussen:
    - REALISATIE: Historische data (afgelopen X weken vanaf standdatum)
    - PROGNOSE: Verwachte cashflow (komende Y weken vanaf standdatum)

    Args:
        reference_date: De standdatum - startpunt voor de forecast (default: vandaag)

    Returns:
        Tuple van (DataFrame met alle data, index waar forecast begint)
    """
    # Gebruik standdatum als referentiepunt (niet vandaag)
    today = reference_date if reference_date else datetime.now().date()

    # -------------------------------------------------------------------------
    # DEEL 1: HISTORISCHE DATA (REALISATIE) - uit historisch betalingsgedrag
    # -------------------------------------------------------------------------
    history_rows = []

    if not historisch.empty and "maand" in historisch.columns:
        # Gebruik laatste 4 weken van historische data
        hist = historisch.copy()
        hist["maand"] = pd.to_datetime(hist["maand"])
        hist = hist.sort_values("maand", ascending=False).head(weeks_history)

        for i, row in enumerate(hist.itertuples()):
            week_num = -(weeks_history - i)
            week_start = today + timedelta(weeks=week_num)
            history_rows.append({
                "week_nummer": week_num,
                "week_label": f"Week {week_num}",
                "week_start": week_start,
                "week_eind": week_start + timedelta(days=7),
                "inkomsten_debiteuren": getattr(row, "inkomsten", 0) / 4,  # Schatting per week
                "uitgaven_crediteuren": getattr(row, "uitgaven", 0) / 4,
                "uitgaven_salarissen": 0.0,
                "uitgaven_overig": 0.0,
                "netto_cashflow": (getattr(row, "inkomsten", 0) - getattr(row, "uitgaven", 0)) / 4,
                "is_realisatie": True,
                "data_type": "Realisatie",
            })
    else:
        # Genereer placeholder historische data als er geen historiek is
        for i in range(weeks_history):
            week_num = -(weeks_history - i)
            week_start = today + timedelta(weeks=week_num)
            history_rows.append({
                "week_nummer": week_num,
                "week_label": f"Week {week_num}",
                "week_start": week_start,
                "week_eind": week_start + timedelta(days=7),
                "inkomsten_debiteuren": 0.0,
                "uitgaven_crediteuren": 0.0,
                "uitgaven_salarissen": 0.0,
                "uitgaven_overig": 0.0,
                "netto_cashflow": 0.0,
                "is_realisatie": True,
                "data_type": "Realisatie",
            })

    # -------------------------------------------------------------------------
    # DEEL 2: PROGNOSE DATA (FORECAST) - uit openstaande posten
    # -------------------------------------------------------------------------
    forecast_rows = []
    week_starts = [today + timedelta(weeks=i) for i in range(weeks_forecast + 1)]

    for i in range(weeks_forecast):
        week_start = week_starts[i]
        week_end = week_starts[i + 1]

        # Inkomsten van debiteuren (met vertraging scenario)
        deb_income = 0.0
        if not debiteuren.empty and "vervaldatum" in debiteuren.columns:
            deb = debiteuren.copy()
            deb["vervaldatum"] = pd.to_datetime(deb["vervaldatum"]).dt.date
            deb["verwachte_betaling"] = deb["vervaldatum"].apply(
                lambda x: x + timedelta(days=debiteur_delay_days) if x else x
            )
            mask = (deb["verwachte_betaling"] >= week_start) & (deb["verwachte_betaling"] < week_end)
            deb_income = deb.loc[mask, "openstaand"].sum()

        # Uitgaven aan crediteuren (met vertraging scenario)
        cred_expense = 0.0
        if not crediteuren.empty and "vervaldatum" in crediteuren.columns:
            cred = crediteuren.copy()
            cred["vervaldatum"] = pd.to_datetime(cred["vervaldatum"]).dt.date
            cred["verwachte_betaling"] = cred["vervaldatum"].apply(
                lambda x: x + timedelta(days=crediteur_delay_days) if x else x
            )
            mask = (cred["verwachte_betaling"] >= week_start) & (cred["verwachte_betaling"] < week_end)
            cred_expense = cred.loc[mask, "openstaand"].sum()

        # Salarissen
        sal_expense = 0.0
        if not salarissen.empty and "betaaldatum" in salarissen.columns:
            sal = salarissen.copy()
            sal["betaaldatum"] = pd.to_datetime(sal["betaaldatum"]).dt.date
            mask = (sal["betaaldatum"] >= week_start) & (sal["betaaldatum"] < week_end)
            sal_expense = sal.loc[mask, "bedrag"].sum()

        forecast_rows.append({
            "week_nummer": i + 1,
            "week_label": f"Week {i + 1}",
            "week_start": week_start,
            "week_eind": week_end,
            "inkomsten_debiteuren": deb_income,
            "uitgaven_crediteuren": cred_expense,
            "uitgaven_salarissen": sal_expense,
            "uitgaven_overig": 0.0,
            "netto_cashflow": deb_income - cred_expense - sal_expense,
            "is_realisatie": False,
            "data_type": "Prognose",
        })

    # Combineer historie en forecast
    all_rows = history_rows + forecast_rows
    df = pd.DataFrame(all_rows)

    # Bereken cumulatief saldo
    start_balance = banksaldo["saldo"].sum() if not banksaldo.empty else 0
    df["cumulatief_saldo"] = start_balance + df["netto_cashflow"].cumsum()

    # Index waar forecast begint
    forecast_start_idx = len(history_rows)

    return df, forecast_start_idx


# =============================================================================
# RENDERING FUNCTIONS
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)  # Cache voor 5 minuten
def _fetch_data_cached(use_mock: bool, customer_code: str, standdatum_str: str, administratie: str):
    """
    Cached data fetching - wordt alleen opnieuw uitgevoerd bij wijziging van parameters.
    Scenario slider wijzigingen triggeren GEEN nieuwe database query.
    """
    standdatum = datetime.strptime(standdatum_str, "%Y-%m-%d").date() if standdatum_str else datetime.now().date()

    # Convert empty strings back to None
    customer_code = customer_code if customer_code else None
    administratie = administratie if administratie else None

    db = get_database(use_mock=use_mock, customer_code=customer_code)

    # Check if connection failed
    if isinstance(db, FailedConnectionDatabase):
        return {"error": db.error_msg, "detected_admin": None}

    # Bereken periodes
    hist_startdatum = date(standdatum.year - 1, standdatum.month, 1)
    dso_startdatum = date(standdatum.year - 2, standdatum.month, 1)

    # Haal eerst debiteuren op om administratie te detecteren
    debiteuren = db.get_openstaande_debiteuren(standdatum=standdatum, administratie=administratie)

    # Auto-detect administratie
    detected_admin = administratie
    if not administratie and not debiteuren.empty and "administratie" in debiteuren.columns:
        unique_admins = debiteuren["administratie"].dropna().unique()
        if len(unique_admins) > 0:
            admin_counts = debiteuren["administratie"].value_counts()
            detected_admin = admin_counts.index[0] if len(admin_counts) > 0 else unique_admins[0]

    data = {
        "banksaldo": db.get_banksaldo(standdatum=standdatum, administratie=detected_admin),
        "debiteuren": debiteuren,
        "crediteuren": db.get_openstaande_crediteuren(standdatum=standdatum),
        "salarissen": db.get_geplande_salarissen(),
        "historisch": db.get_historisch_betalingsgedrag(),
        "detected_admin": detected_admin,
        "calibrated_dso": None,
        "calibrated_dpo": None,
        "betaalgedrag_debiteuren": pd.DataFrame(),
        "betaalgedrag_crediteuren": pd.DataFrame(),
        "terugkerende_kosten": pd.DataFrame(),
        "historische_cashflow": pd.DataFrame(),
    }

    is_mock_db = type(db).__name__ == "MockDatabase"

    if is_mock_db:
        data["terugkerende_kosten"] = db.get_terugkerende_kosten()
        data["historische_cashflow"] = db.get_historische_cashflow_per_week()
        if hasattr(db, 'get_betaalgedrag_per_debiteur'):
            data["betaalgedrag_debiteuren"] = db.get_betaalgedrag_per_debiteur()
            data["betaalgedrag_crediteuren"] = db.get_betaalgedrag_per_crediteur()
    elif detected_admin:
        # Echte database met administratie
        if hasattr(db, 'get_historische_cashflow_per_week'):
            data["historische_cashflow"] = db.get_historische_cashflow_per_week(
                startdatum=hist_startdatum,
                einddatum=standdatum,
                administratie=detected_admin
            )

        # Betaalgedrag data
        if hasattr(db, 'get_betaalgedrag_per_debiteur'):
            data["betaalgedrag_debiteuren"] = db.get_betaalgedrag_per_debiteur(
                startdatum=dso_startdatum, einddatum=standdatum, administratie=detected_admin
            )
            data["betaalgedrag_crediteuren"] = db.get_betaalgedrag_per_crediteur(
                startdatum=dso_startdatum, einddatum=standdatum, administratie=detected_admin
            )

        # DSO/DPO calibratie
        if hasattr(db, 'get_calibrated_dso_dpo'):
            try:
                dso_dpo = db.get_calibrated_dso_dpo(detected_admin)
                data["calibrated_dso"] = dso_dpo.get('dso')
                data["calibrated_dpo"] = dso_dpo.get('dpo')
            except Exception:
                pass

        # V7 data sources
        try:
            data["btw_aangifteregels"] = db.get_btw_aangifteregels(
                startdatum=dso_startdatum, einddatum=standdatum)
        except Exception:
            data["btw_aangifteregels"] = pd.DataFrame()

        try:
            data["salarishistorie"] = db.get_salarishistorie(
                startdatum=dso_startdatum, einddatum=standdatum)
        except Exception:
            data["salarishistorie"] = pd.DataFrame()

        try:
            data["budgetten"] = db.get_budgetten(
                boekjaar=standdatum.year, administratie=detected_admin)
        except Exception:
            data["budgetten"] = pd.DataFrame()

        try:
            data["orderportefeuille"] = db.get_orderportefeuille(
                administratie=detected_admin)
        except Exception:
            data["orderportefeuille"] = pd.DataFrame()

        data["geplande_salarissen"] = pd.DataFrame()

    return data


def load_data(use_mock: bool = True, customer_code: Optional[str] = None, standdatum: date = None, administratie: str = None):
    """
    Load data from database or mock (uses caching for performance).
    Slider wijzigingen triggeren GEEN database reload meer.
    """
    if standdatum is None:
        standdatum = datetime.now().date()

    # Convert to string for cache key (dates are not hashable)
    standdatum_str = standdatum.strftime("%Y-%m-%d")

    # Fetch data (cached - alleen nieuwe query bij andere parameters)
    data = _fetch_data_cached(
        use_mock=use_mock,
        customer_code=customer_code or "",
        standdatum_str=standdatum_str,
        administratie=administratie or ""
    )

    # Handle errors
    if "error" in data:
        st.error(f"Verbindingsfout: {data['error']}. Controleer de netwerk/VPN verbinding.")

    # UI updates (niet gecached)
    st.sidebar.caption(f"Data source: {'Demo' if use_mock else customer_code}")
    if data.get("detected_admin"):
        st.sidebar.caption(f"Administratie: {data['detected_admin']}")
    if data.get("calibrated_dso"):
        st.sidebar.caption(f"Gecalibreerde DSO: {data['calibrated_dso']:.0f} dagen")

    return data


def render_kpi_cards(metrics: LiquidityMetrics):
    """Render KPI cards at top of dashboard."""
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Current Ratio",
            value=f"{metrics.current_ratio:.2f}",
            delta="Gezond" if metrics.current_ratio >= 1.5 else "Let op",
            delta_color="normal" if metrics.current_ratio >= 1.5 else "inverse"
        )

    with col2:
        st.metric(
            label="Quick Ratio",
            value=f"{metrics.quick_ratio:.2f}",
            delta="OK" if metrics.quick_ratio >= 1.0 else "Laag",
            delta_color="normal" if metrics.quick_ratio >= 1.0 else "inverse"
        )

    with col3:
        st.metric(
            label="Liquiditeit",
            value=f"€ {metrics.cash_position:,.0f}",
            help="Totaal banksaldo"
        )

    with col4:
        st.metric(
            label="Debiteuren",
            value=f"€ {metrics.total_receivables:,.0f}",
            help="Openstaande vorderingen"
        )

    with col5:
        st.metric(
            label="Crediteuren",
            value=f"€ {metrics.total_payables:,.0f}",
            help="Openstaande schulden"
        )


def render_transparent_cashflow_chart(forecast: pd.DataFrame, forecast_start_idx: int, reference_date: date = None, show_scenario_bands: bool = True):
    """
    Render cashflow chart met duidelijk onderscheid tussen REALISATIE en PROGNOSE.

    - Realisatie: Solid kleuren, volle opacity
    - Prognose: Gestreept patroon, lagere opacity
    - Scenario banden: Low/Medium/High bandbreedte voor onzekerheid
    """
    fig = go.Figure()

    # Split data in realisatie en prognose
    realisatie = forecast[forecast["is_realisatie"] == True]
    prognose = forecast[forecast["is_realisatie"] == False]

    # Bereken Low/High scenario's - bandbreedte GROEIT over tijd (onzekerheid neemt toe)
    if show_scenario_bands and not prognose.empty:
        medium_saldo = prognose["cumulatief_saldo"].values
        n_weeks = len(medium_saldo)

        # Bandbreedte groeit: start bij 3%, eindigt bij 20% na 13 weken
        # Dit reflecteert toenemende onzekerheid naarmate we verder vooruit kijken
        uncertainty_pct = np.array([0.03 + (0.17 * i / max(n_weeks-1, 1)) for i in range(n_weeks)])

        # Bereken absolute bandbreedte op basis van startsaldo (niet het wisselende saldo)
        start_saldo = abs(medium_saldo[0]) if medium_saldo[0] != 0 else 100000
        band_size = start_saldo * uncertainty_pct

        low_saldo = medium_saldo - band_size
        high_saldo = medium_saldo + band_size

        # Scenario band (fill between high and low)
        fig.add_trace(go.Scatter(
            x=list(prognose["week_label"]) + list(prognose["week_label"])[::-1],
            y=list(high_saldo) + list(low_saldo)[::-1],
            fill="toself",
            fillcolor="rgba(52, 152, 219, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="Bandbreedte",
            hoverinfo="skip",
            showlegend=False,
        ))

        # Low scenario rand (subtiel)
        fig.add_trace(go.Scatter(
            x=prognose["week_label"],
            y=low_saldo,
            line=dict(color="rgba(231, 76, 60, 0.5)", width=1.5, dash="dot"),
            mode="lines",
            hovertemplate="<b>PESSIMISTISCH</b><br>%{x}<br>EUR %{y:,.0f}<extra></extra>",
            showlegend=False,
        ))

        # High scenario rand (subtiel)
        fig.add_trace(go.Scatter(
            x=prognose["week_label"],
            y=high_saldo,
            line=dict(color="rgba(39, 174, 96, 0.5)", width=1.5, dash="dot"),
            mode="lines",
            hovertemplate="<b>OPTIMISTISCH</b><br>%{x}<br>EUR %{y:,.0f}<extra></extra>",
            showlegend=False,
        ))

    # --- REALISATIE BARS (Solid) ---
    if not realisatie.empty:
        colors_real = [COLORS["primary"] if x >= 0 else COLORS["danger"] for x in realisatie["netto_cashflow"]]
        fig.add_trace(go.Bar(
            x=realisatie["week_label"],
            y=realisatie["netto_cashflow"],
            name="Realisatie",
            marker_color=colors_real,
            opacity=1.0,
            hovertemplate="<b>REALISATIE</b><br>%{x}<br>Cashflow: EUR %{y:,.0f}<extra></extra>",
            legendgroup="realisatie",
        ))

    # --- PROGNOSE BARS (vereenvoudigd: 1 serie, kleur varieert) ---
    if not prognose.empty:
        # Kleur gebaseerd op positief/negatief en zekerheid
        colors_prognose = []
        for i, row in prognose.iterrows():
            if row["week_nummer"] < 5:
                # Hoge zekerheid: groen/oranje
                colors_prognose.append(COLORS["success"] if row["netto_cashflow"] >= 0 else COLORS["warning"])
            else:
                # Lagere zekerheid: lichter
                colors_prognose.append("#FFA500" if row["netto_cashflow"] >= 0 else "#FF6347")

        fig.add_trace(go.Bar(
            x=prognose["week_label"],
            y=prognose["netto_cashflow"],
            name="Prognose",
            marker_color=colors_prognose,
            opacity=0.7,
            marker_pattern_shape="/",
            hovertemplate="<b>PROGNOSE</b><br>%{x}<br>Verwacht: EUR %{y:,.0f}<extra></extra>",
            legendgroup="prognose",
        ))

    # --- CUMULATIEF SALDO LIJNEN (2 kleuren: realisatie vs prognose) ---
    # Realisatie saldo (donkerblauw, solid)
    if not realisatie.empty:
        fig.add_trace(go.Scatter(
            x=realisatie["week_label"],
            y=realisatie["cumulatief_saldo"],
            name="Saldo (realisatie)",
            line=dict(color=COLORS["primary"], width=3),
            mode="lines+markers",
            marker=dict(size=7),
            hovertemplate="<b>REALISATIE</b><br>%{x}<br>Saldo: EUR %{y:,.0f}<extra></extra>",
            showlegend=False,
        ))

    # Prognose saldo (lichtblauw, dashed)
    if not prognose.empty:
        fig.add_trace(go.Scatter(
            x=prognose["week_label"],
            y=prognose["cumulatief_saldo"],
            name="Saldo (prognose)",
            line=dict(color=COLORS["secondary"], width=3, dash="dash"),
            mode="lines+markers",
            marker=dict(size=6, symbol="diamond"),
            hovertemplate="<b>PROGNOSE</b><br>%{x}<br>Verwacht saldo: EUR %{y:,.0f}<extra></extra>",
            showlegend=False,
        ))

    # Verbindingslijn tussen realisatie en prognose (subtiel)
    if not realisatie.empty and not prognose.empty:
        fig.add_trace(go.Scatter(
            x=[realisatie["week_label"].iloc[-1], prognose["week_label"].iloc[0]],
            y=[realisatie["cumulatief_saldo"].iloc[-1], prognose["cumulatief_saldo"].iloc[0]],
            line=dict(color=COLORS["neutral"], width=2, dash="dot"),
            mode="lines",
            showlegend=False,
            hoverinfo="skip",
        ))

    # Verticale scheidingslijn tussen realisatie en prognose
    if forecast_start_idx > 0 and forecast_start_idx < len(forecast):
        date_label = reference_date.strftime("%d-%m-%Y") if reference_date else "Vandaag"
        fig.add_vline(
            x=forecast_start_idx - 0.5,
            line_dash="solid",
            line_color="#333",
            line_width=2,
            annotation_text=f"Peildatum: {date_label}",
            annotation_position="top",
        )

    # Nul-lijn voor referentie
    fig.add_hline(
        y=0,
        line_dash="solid",
        line_color="#ccc",
        line_width=1,
    )

    # Forceer correcte X-as volgorde: historie links, prognose rechts
    correct_order = forecast["week_label"].tolist()

    fig.update_layout(
        title="Cashflow Overzicht",
        xaxis_title="",
        yaxis_title="Bedrag (EUR)",
        hovermode="x unified",
        showlegend=False,  # Legenda staat in blauwe sectie
        height=450,
        barmode="relative",
        xaxis=dict(
            categoryorder="array",
            categoryarray=correct_order
        ),
    )

    return fig


def render_transparency_legend():
    """Render legenda voor de grafiek."""
    st.markdown("""
    <div style="background: #f8f9fa; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; line-height: 1.8;">
        <strong style="color:#333;">Legenda:</strong><br>
        <span style="color:#1E3A5F;">■</span> <b>Realisatie</b> = historische cashflow (werkelijk gebeurd)
        &nbsp;|&nbsp;
        <span style="color:#27AE60;">■</span> <b>Prognose</b> = verwachte cashflow<br>
        <span style="color:#1E3A5F;">━</span> <b>Saldo lijn</b> = cumulatief banksaldo
        &nbsp;|&nbsp;
        <span style="color:#3498DB;">┅</span> <b>Verwacht saldo</b> = prognose banksaldo<br>
        <span style="background:rgba(52,152,219,0.2); padding:1px 8px; border-radius:3px;">Bandbreedte</span> = onzekerheidsmarge (groeit naarmate prognose verder in toekomst ligt)
    </div>
    """, unsafe_allow_html=True)


def render_pie_charts_with_filter(debiteuren: pd.DataFrame, crediteuren: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    """
    Render pie charts showing composition of debiteuren and crediteuren.
    Returns selected debiteur/crediteur names for filtering the aging analysis.
    """
    st.subheader("Openstaande Posten per Relatie")
    st.caption("Selecteer een relatie om de ouderdomsanalyse te filteren")

    selected_deb = None
    selected_cred = None

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Debiteuren**")
        if not debiteuren.empty and "debiteur_naam" in debiteuren.columns:
            # Group by debiteur and sum openstaand
            deb_grouped = debiteuren.groupby("debiteur_naam")["openstaand"].sum().reset_index()
            deb_grouped = deb_grouped.sort_values("openstaand", ascending=False)

            # Top 10 + Others
            if len(deb_grouped) > 10:
                top10 = deb_grouped.head(10)
                others = pd.DataFrame({
                    "debiteur_naam": ["Overige"],
                    "openstaand": [deb_grouped.iloc[10:]["openstaand"].sum()]
                })
                deb_grouped = pd.concat([top10, others], ignore_index=True)

            totaal = deb_grouped["openstaand"].sum()

            fig_deb = px.pie(
                deb_grouped,
                values="openstaand",
                names="debiteur_naam",
                hole=0.4,
            )
            fig_deb.update_traces(textposition='outside', textinfo='percent+label')
            fig_deb.update_layout(
                showlegend=False,
                height=350,
                annotations=[dict(text=f"EUR {totaal:,.0f}", x=0.5, y=0.5, font_size=14, showarrow=False)]
            )
            st.plotly_chart(fig_deb, key="pie_deb_chart", use_container_width=True)

            # Selectbox als filter
            deb_options = ["Alle debiteuren"] + deb_grouped["debiteur_naam"].tolist()
            selected_deb = st.selectbox(
                "Filter op debiteur:",
                deb_options,
                key="deb_select",
                help="Selecteer een debiteur om de ouderdomsanalyse hieronder te filteren"
            )

            if selected_deb == "Alle debiteuren" or selected_deb == "Overige":
                selected_deb = None

            # Toon factuurdetails als er een specifieke debiteur is geselecteerd
            if selected_deb:
                detail_df = debiteuren[debiteuren["debiteur_naam"] == selected_deb].copy()
                if not detail_df.empty:
                    st.markdown(f"**Facturen van {selected_deb}:**")
                    detail_cols = ["factuurnummer", "factuurdatum", "vervaldatum", "openstaand"]
                    available_cols = [c for c in detail_cols if c in detail_df.columns]
                    st.dataframe(
                        detail_df[available_cols].style.format({"openstaand": "EUR {:,.2f}"}),
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("Geen debiteuren data beschikbaar")

    with col2:
        st.markdown("**Crediteuren**")
        if not crediteuren.empty and "crediteur_naam" in crediteuren.columns:
            # Group by crediteur and sum openstaand
            cred_grouped = crediteuren.groupby("crediteur_naam")["openstaand"].sum().reset_index()
            cred_grouped = cred_grouped.sort_values("openstaand", ascending=False)

            # Top 10 + Others
            if len(cred_grouped) > 10:
                top10 = cred_grouped.head(10)
                others = pd.DataFrame({
                    "crediteur_naam": ["Overige"],
                    "openstaand": [cred_grouped.iloc[10:]["openstaand"].sum()]
                })
                cred_grouped = pd.concat([top10, others], ignore_index=True)

            totaal = cred_grouped["openstaand"].sum()

            fig_cred = px.pie(
                cred_grouped,
                values="openstaand",
                names="crediteur_naam",
                hole=0.4,
            )
            fig_cred.update_traces(textposition='outside', textinfo='percent+label')
            fig_cred.update_layout(
                showlegend=False,
                height=350,
                annotations=[dict(text=f"EUR {totaal:,.0f}", x=0.5, y=0.5, font_size=14, showarrow=False)]
            )
            st.plotly_chart(fig_cred, key="pie_cred_chart", use_container_width=True)

            # Selectbox als filter
            cred_options = ["Alle crediteuren"] + cred_grouped["crediteur_naam"].tolist()
            selected_cred = st.selectbox(
                "Filter op crediteur:",
                cred_options,
                key="cred_select",
                help="Selecteer een crediteur om de ouderdomsanalyse hieronder te filteren"
            )

            if selected_cred == "Alle crediteuren" or selected_cred == "Overige":
                selected_cred = None

            # Toon factuurdetails als er een specifieke crediteur is geselecteerd
            if selected_cred:
                detail_df = crediteuren[crediteuren["crediteur_naam"] == selected_cred].copy()
                if not detail_df.empty:
                    st.markdown(f"**Facturen van {selected_cred}:**")
                    detail_cols = ["factuurnummer", "factuurdatum", "vervaldatum", "openstaand"]
                    available_cols = [c for c in detail_cols if c in detail_df.columns]
                    st.dataframe(
                        detail_df[available_cols].style.format({"openstaand": "EUR {:,.2f}"}),
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("Geen crediteuren data beschikbaar")

    return selected_deb, selected_cred


def render_aging_chart(
    aging_deb: pd.DataFrame,
    aging_cred: pd.DataFrame,
    selected_deb: Optional[str] = None,
    selected_cred: Optional[str] = None
):
    """Render aging analysis charts, optionally filtered by selected relation."""
    st.subheader("Ouderdomsanalyse")

    # Toon filter indicatie als er een filter actief is
    if selected_deb or selected_cred:
        filter_parts = []
        if selected_deb:
            filter_parts.append(f"Debiteur: **{selected_deb}**")
        if selected_cred:
            filter_parts.append(f"Crediteur: **{selected_cred}**")
        st.info(f"Gefilterd op: {', '.join(filter_parts)}")

    col1, col2 = st.columns(2)

    with col1:
        title = f"**Debiteuren per vervaldatum**"
        if selected_deb:
            title += f" ({selected_deb})"
        st.markdown(title)

        fig_deb = px.bar(
            aging_deb,
            x="bucket",
            y="bedrag",
            color="bucket",
            color_discrete_sequence=[COLORS["success"], COLORS["secondary"],
                                     COLORS["warning"], COLORS["danger"], "#8B0000"],
            text="percentage",
        )
        fig_deb.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_deb.update_layout(showlegend=False, height=350, xaxis_title="", yaxis_title="Bedrag (€)")
        st.plotly_chart(fig_deb, key="aging_deb_chart")

    with col2:
        title = f"**Crediteuren per vervaldatum**"
        if selected_cred:
            title += f" ({selected_cred})"
        st.markdown(title)

        fig_cred = px.bar(
            aging_cred,
            x="bucket",
            y="bedrag",
            color="bucket",
            color_discrete_sequence=[COLORS["success"], COLORS["secondary"],
                                     COLORS["warning"], COLORS["danger"], "#8B0000"],
            text="percentage",
        )
        fig_cred.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_cred.update_layout(showlegend=False, height=350, xaxis_title="", yaxis_title="Bedrag (€)")
        st.plotly_chart(fig_cred, key="aging_cred_chart")


def render_cashflow_details(forecast: pd.DataFrame):
    """Render detailed cashflow table with realisatie/prognose indicator."""
    st.subheader("Cashflow Details per Week")

    # Bepaal welke kolommen beschikbaar zijn
    has_vaste_lasten = "uitgaven_vaste_lasten" in forecast.columns
    has_salarissen = "uitgaven_salarissen" in forecast.columns

    # Selecteer kolommen afhankelijk van wat beschikbaar is
    base_cols = ["data_type", "week_label", "week_start", "inkomsten_debiteuren", "uitgaven_crediteuren"]
    if has_vaste_lasten:
        base_cols.append("uitgaven_vaste_lasten")
    elif has_salarissen:
        base_cols.append("uitgaven_salarissen")
    base_cols.extend(["netto_cashflow", "cumulatief_saldo"])

    display_df = forecast[base_cols].copy()

    # Rename kolommen
    if has_vaste_lasten:
        display_df.columns = ["Type", "Week", "Startdatum", "Inkomsten", "Crediteuren", "Vaste Lasten", "Netto", "Saldo"]
        currency_cols = ["Inkomsten", "Crediteuren", "Vaste Lasten", "Netto", "Saldo"]
    elif has_salarissen:
        display_df.columns = ["Type", "Week", "Startdatum", "Inkomsten", "Crediteuren", "Salarissen", "Netto", "Saldo"]
        currency_cols = ["Inkomsten", "Crediteuren", "Salarissen", "Netto", "Saldo"]
    else:
        display_df.columns = ["Type", "Week", "Startdatum", "Inkomsten", "Crediteuren", "Netto", "Saldo"]
        currency_cols = ["Inkomsten", "Crediteuren", "Netto", "Saldo"]

    def highlight_type(row):
        if row["Type"] == "Realisatie":
            return ["background-color: #e3f2fd"] * len(row)
        else:
            return ["background-color: #fff8e1"] * len(row)

    st.dataframe(
        display_df.style.format({
            col: "EUR {:,.0f}" for col in currency_cols
        }).apply(highlight_type, axis=1),
        hide_index=True,
        height=400,
    )

    # Legenda voor tabel
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Blauw = Realisatie (historische data)")
    with col2:
        st.caption("Geel = Prognose (verwachte cashflow)")


def render_filter_sidebar(data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    Render filter controls in sidebar.
    Filters: Administratie, Bedrijfseenheid, Standdatum, Bankrekening
    """
    st.sidebar.header("🔍 Filters")

    filters = {}

    # Administratie filter
    administraties = set()
    if not data["debiteuren"].empty and "administratie" in data["debiteuren"].columns:
        administraties.update(data["debiteuren"]["administratie"].dropna().unique())
    if not data["crediteuren"].empty and "administratie" in data["crediteuren"].columns:
        administraties.update(data["crediteuren"]["administratie"].dropna().unique())

    if administraties:
        admin_options = sorted([a for a in administraties if a and a != "Onbekend"])
        if admin_options:
            filters["administratie"] = st.sidebar.selectbox(
                "Administratie",
                options=["Alle"] + admin_options,
                index=0,
                help="Filter op administratie/bedrijfsonderdeel"
            )

    # Bedrijfseenheid filter
    bedrijfseenheden = set()
    if not data["debiteuren"].empty and "bedrijfseenheid" in data["debiteuren"].columns:
        bedrijfseenheden.update(data["debiteuren"]["bedrijfseenheid"].dropna().unique())
    if not data["crediteuren"].empty and "bedrijfseenheid" in data["crediteuren"].columns:
        bedrijfseenheden.update(data["crediteuren"]["bedrijfseenheid"].dropna().unique())

    if bedrijfseenheden:
        be_options = sorted([b for b in bedrijfseenheden if b and b != "Onbekend"])
        if be_options:
            filters["bedrijfseenheid"] = st.sidebar.selectbox(
                "Bedrijfseenheid",
                options=["Alle"] + be_options,
                index=0,
                help="Filter op bedrijfseenheid"
            )

    # Bankrekening filter (standdatum is nu in main() gedefinieerd, vóór data laden)
    options = get_filter_options(data)
    if options["bankrekeningen"]:
        filters["bankrekeningen"] = st.sidebar.multiselect(
            "Bankrekeningen",
            options=options["bankrekeningen"],
            default=[],
            help="Filter op specifieke bankrekeningen"
        )

    return filters


def render_scenario_sidebar():
    """
    Render prognose instellingen in sidebar.
    Scenario sliders staan nu in main content voor betere interactie.
    """
    st.sidebar.header("Prognose Instellingen")

    st.sidebar.markdown("**Horizon:**")

    forecast_weeks = st.sidebar.selectbox(
        "Weken vooruit",
        options=[13, 26, 52],
        index=0,  # Default: 13 weken
        help="Aantal weken voor de cashflow prognose"
    )

    history_weeks = st.sidebar.selectbox(
        "Weken historie",
        options=[4, 8, 13],
        index=2,  # Default: 13 weken
        help="Aantal weken historische data tonen (realisatie)"
    )

    # Toon model info (geen keuze, alleen informatie)
    st.sidebar.markdown("---")
    with st.sidebar.expander("Over het forecast model", expanded=False):
        st.markdown("""
        **Run Rate + Seasonality Model**

        Dit model combineert:

        1. **Run Rate**: Gemiddelde weekomzet uit laatste 90 dagen
        2. **Seasonality**: Patroon per week-van-de-maand
        3. **DSO Calibratie**: Werkelijk betaalgedrag van klanten
        4. **Blending**: Harde ERP data + voorspelling

        *Gevalideerd: 88% gemiddelde accuracy over 16+ klanten*
        """)

    # Return alleen forecast/history weeks (scenario controls zijn nu in main)
    return (forecast_weeks, history_weeks)


def render_scenario_controls():
    """
    Render scenario analyse controls in main content area.
    Geplaatst boven de grafiek voor directe interactie.

    Returns:
        tuple: (debiteur_delay, crediteur_delay, omzet_wijziging_pct, show_bands)
    """
    with st.expander("🔮 Scenario Analyse - Wat als...", expanded=False):
        st.markdown("""
        **Simuleer verschillende situaties** om te zien hoe deze uw cashflow beïnvloeden.
        """)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**📈 Omzet**")
            omzet_wijziging = st.slider(
                "Omzet wijziging",
                min_value=-50,
                max_value=50,
                value=0,
                step=5,
                format="%d%%",
                help="Simuleer omzetdaling of -groei. Kosten wijzigen proportioneel mee.",
                label_visibility="collapsed"
            )
            if omzet_wijziging > 0:
                st.caption(f"📈 +{omzet_wijziging}% meer omzet → meer inkomsten én kosten")
            elif omzet_wijziging < 0:
                st.caption(f"📉 {omzet_wijziging}% minder omzet → minder inkomsten én kosten")
            else:
                st.caption("Geen wijziging in omzet")

        with col2:
            st.markdown("**💰 Klanten betalen**")
            debiteur_delay = st.slider(
                "Betaaltermijn klanten",
                min_value=-14,
                max_value=30,
                value=0,
                format="%d dagen",
                help="Hoe betalingsgedrag van klanten verandert t.o.v. huidige situatie.",
                label_visibility="collapsed"
            )
            if debiteur_delay > 0:
                st.caption(f"⏳ Klanten betalen {debiteur_delay} dagen **later** → geld komt later binnen")
            elif debiteur_delay < 0:
                st.caption(f"⚡ Klanten betalen {abs(debiteur_delay)} dagen **eerder** → geld komt eerder binnen")
            else:
                st.caption("Betalingsgedrag klanten ongewijzigd")

        with col3:
            st.markdown("**🧾 Wij betalen leveranciers**")
            crediteur_delay = st.slider(
                "Betaaltermijn leveranciers",
                min_value=-14,
                max_value=30,
                value=0,
                format="%d dagen",
                help="Hoe wij onze betalingen aan leveranciers aanpassen.",
                label_visibility="collapsed"
            )
            if crediteur_delay > 0:
                st.caption(f"⏳ Wij betalen {crediteur_delay} dagen **later** → geld blijft langer staan")
            elif crediteur_delay < 0:
                st.caption(f"⚡ Wij betalen {abs(crediteur_delay)} dagen **eerder** → geld gaat eerder uit")
            else:
                st.caption("Betalingsgedrag leveranciers ongewijzigd")

        # Toon actief scenario met impact
        if omzet_wijziging != 0 or debiteur_delay != 0 or crediteur_delay != 0:
            impact_parts = []
            if omzet_wijziging > 0:
                impact_parts.append(f"omzet +{omzet_wijziging}%")
            elif omzet_wijziging < 0:
                impact_parts.append(f"omzet {omzet_wijziging}%")

            if debiteur_delay > 0:
                impact_parts.append(f"klanten +{debiteur_delay}d later")
            elif debiteur_delay < 0:
                impact_parts.append(f"klanten {debiteur_delay}d eerder")

            if crediteur_delay > 0:
                impact_parts.append(f"leveranciers +{crediteur_delay}d later")
            elif crediteur_delay < 0:
                impact_parts.append(f"leveranciers {crediteur_delay}d eerder")

            st.success(f"**📊 Scenario actief:** {' | '.join(impact_parts)}")

    return (debiteur_delay, crediteur_delay, omzet_wijziging)


def render_alerts(forecast: pd.DataFrame, metrics: LiquidityMetrics):
    """Render alert messages based on liquidity status."""
    alerts = []

    # Check for negative cash balance in forecast (only prognose weeks)
    prognose_weeks = forecast[forecast["is_realisatie"] == False]
    if not prognose_weeks.empty:
        negative_weeks = prognose_weeks[prognose_weeks["cumulatief_saldo"] < 0]
        if not negative_weeks.empty:
            first_negative = negative_weeks.iloc[0]
            alerts.append({
                "type": "danger",
                "message": f"⚠️ **Let op:** Verwacht negatief saldo in {first_negative['week_label']} "
                           f"(€ {first_negative['cumulatief_saldo']:,.0f})"
            })

    # Check current ratio
    if metrics.current_ratio < LIQUIDITY_THRESHOLDS["current_ratio_danger"]:
        alerts.append({
            "type": "danger",
            "message": f"🚨 **Current ratio te laag:** {metrics.current_ratio:.2f} "
                       f"(minimum: {LIQUIDITY_THRESHOLDS['current_ratio_danger']})"
        })
    elif metrics.current_ratio < LIQUIDITY_THRESHOLDS["current_ratio_warning"]:
        alerts.append({
            "type": "warning",
            "message": f"⚡ **Current ratio onder streefwaarde:** {metrics.current_ratio:.2f} "
                       f"(streef: {LIQUIDITY_THRESHOLDS['current_ratio_warning']})"
        })

    # Check days cash on hand
    if metrics.days_cash_on_hand < LIQUIDITY_THRESHOLDS["min_cash_buffer_days"]:
        alerts.append({
            "type": "warning",
            "message": f"💰 **Beperkte kasbuffer:** {metrics.days_cash_on_hand:.0f} dagen "
                       f"(aanbevolen: {LIQUIDITY_THRESHOLDS['min_cash_buffer_days']} dagen)"
        })

    # Render alerts
    for alert in alerts:
        if alert["type"] == "danger":
            st.error(alert["message"])
        elif alert["type"] == "warning":
            st.warning(alert["message"])
        else:
            st.info(alert["message"])

    if not alerts:
        st.success("✅ Liquiditeitspositie is gezond")


def render_customer_insights_tab(
    customer_profile: CustomerProfile,
    customer_code: str
):
    """
    Render klantinzichten tab met profiel, backtesting en learnings.

    Dit is waar we tonen:
    - Wat karakteriseert deze klant?
    - Hoe betrouwbaar is het model voor deze klant?
    - Wat heeft het model geleerd uit historische data?
    """
    st.header(f"Klantprofiel: {customer_code}")
    st.caption(f"Analyse datum: {customer_profile.analyse_datum}")

    # === SECTIE 1: KERNMETRICS ===
    st.subheader("1. Kernkarakteristieken")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        dso_color = "green" if customer_profile.portfolio_dso <= 30 else (
            "orange" if customer_profile.portfolio_dso <= 45 else "red"
        )
        st.metric(
            "Portfolio DSO",
            f"{customer_profile.portfolio_dso:.0f} dagen",
            help="Gemiddelde betaaltijd van debiteuren"
        )
        st.markdown(f"Discipline: **:{dso_color}[{customer_profile.betaal_discipline}]**")

    with col2:
        voorspel_color = "green" if customer_profile.cashflow_voorspelbaarheid == "hoog" else (
            "orange" if customer_profile.cashflow_voorspelbaarheid == "gemiddeld" else "red"
        )
        st.metric(
            "Voorspelbaarheid",
            customer_profile.cashflow_voorspelbaarheid.capitalize(),
            help="Hoe voorspelbaar is de cashflow?"
        )
        st.markdown(f"Volatiliteit: {customer_profile.omzet_volatiliteit:.2f}")

    with col3:
        seizoen_label = "Sterk" if customer_profile.seizoen_sterkte > 0.2 else (
            "Matig" if customer_profile.seizoen_sterkte > 0.1 else "Zwak"
        )
        st.metric(
            "Seizoenseffect",
            seizoen_label,
            help="Sterkte van seizoenspatronen in de omzet"
        )
        if customer_profile.piek_maanden:
            maand_namen = {1: "Jan", 2: "Feb", 3: "Mrt", 4: "Apr", 5: "Mei", 6: "Jun",
                         7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dec"}
            piek_str = ", ".join([maand_namen[m] for m in customer_profile.piek_maanden[:3]])
            st.caption(f"Piek: {piek_str}")

    with col4:
        if customer_profile.backtest_result:
            mape = customer_profile.backtest_result.overall_mape
            mape_color = "green" if mape < 15 else ("orange" if mape < 30 else "red")
            st.metric(
                "Model Nauwkeurigheid",
                f"{100 - mape:.0f}%",
                help="Gebaseerd op backtesting"
            )
            st.markdown(f"MAPE: **:{mape_color}[{mape:.1f}%]**")
        else:
            st.metric("Model Nauwkeurigheid", "N/A")
            st.caption("Geen backtest data")

    # === SECTIE 2: BACKTESTING RESULTATEN ===
    if customer_profile.backtest_result and customer_profile.backtest_result.n_cutoff_dates > 0:
        st.markdown("---")
        st.subheader("2. Backtesting Resultaten")

        bt = customer_profile.backtest_result

        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown("**Test Periode:**")
            st.caption(f"{bt.test_period_start} tot {bt.test_period_end}")
            st.caption(f"{bt.n_cutoff_dates} test momenten")

            st.markdown("**Metrics:**")

            # Bias indicator
            if bt.bias > 0:
                st.markdown(f"📈 Bias: +€{bt.bias:,.0f}/week *(overschatting)*")
            else:
                st.markdown(f"📉 Bias: €{bt.bias:,.0f}/week *(onderschatting)*")

            st.markdown(f"📊 RMSE: €{bt.rmse:,.0f}")

            # Layer performance
            st.markdown("**Per Laag:**")
            st.markdown(f"- Laag 1 (AR): {bt.layer1_accuracy:.0f}% nauwkeurig")
            st.markdown(f"- Laag 3 (Ghost): {bt.layer3_accuracy:.0f}% nauwkeurig")

        with col2:
            # Accuracy Decay grafiek
            if bt.mape_per_horizon:
                st.markdown("**Accuracy Decay per Forecast Horizon:**")

                horizons = sorted(bt.mape_per_horizon.keys())
                mapes = [bt.mape_per_horizon[h] for h in horizons]

                decay_df = pd.DataFrame({
                    "Week vooruit": horizons,
                    "MAPE (%)": mapes,
                    "Nauwkeurigheid (%)": [100 - m for m in mapes]
                })

                # Maak grafiek
                fig = go.Figure()

                fig.add_trace(go.Scatter(
                    x=decay_df["Week vooruit"],
                    y=decay_df["Nauwkeurigheid (%)"],
                    mode="lines+markers",
                    name="Nauwkeurigheid",
                    line=dict(color=COLORS["primary"], width=2),
                    marker=dict(size=8)
                ))

                # Reference lines
                fig.add_hline(y=85, line_dash="dash", line_color="green",
                            annotation_text="Goed (85%)")
                fig.add_hline(y=70, line_dash="dash", line_color="orange",
                            annotation_text="Acceptabel (70%)")

                fig.update_layout(
                    title="Model Nauwkeurigheid per Week Vooruit",
                    xaxis_title="Weken vooruit",
                    yaxis_title="Nauwkeurigheid (%)",
                    yaxis=dict(range=[0, 100]),
                    height=300,
                    showlegend=False
                )

                st.plotly_chart(fig, use_container_width=True)

    # === SECTIE 3: KLANTINZICHTEN ===
    st.markdown("---")
    st.subheader("3. Klantinzichten")

    # Groepeer inzichten per categorie
    categorieen = {}
    for inzicht in customer_profile.inzichten:
        if inzicht.categorie not in categorieen:
            categorieen[inzicht.categorie] = []
        categorieen[inzicht.categorie].append(inzicht)

    # Render per categorie
    for categorie, inzichten in categorieen.items():
        categorie_icons = {
            "betaalgedrag": "💰",
            "seizoen": "📅",
            "trend": "📈",
            "volatiliteit": "📊",
            "risico": "⚠️",
            "backtest": "🔬"
        }
        icon = categorie_icons.get(categorie, "📌")

        with st.expander(f"{icon} {categorie.capitalize()}", expanded=True):
            for inzicht in inzichten:
                # Impact kleuren
                if inzicht.impact == "positief":
                    st.success(f"**{inzicht.titel}**")
                elif inzicht.impact == "negatief":
                    st.warning(f"**{inzicht.titel}**")
                else:
                    st.info(f"**{inzicht.titel}**")

                st.markdown(inzicht.beschrijving)

                # Toon confidence als het niet 100% zeker is
                if inzicht.confidence < 0.9:
                    st.caption(f"Betrouwbaarheid: {inzicht.confidence*100:.0f}%")

    # === SECTIE 4: MODEL LEARNINGS ===
    if customer_profile.backtest_result and customer_profile.backtest_result.learnings:
        st.markdown("---")
        st.subheader("4. Wat het Model Heeft Geleerd")

        st.markdown("""
        *Op basis van historische backtesting heeft het model de volgende
        patronen en karakteristieken van deze klant geïdentificeerd:*
        """)

        for learning in customer_profile.backtest_result.learnings:
            st.markdown(f"- {learning}")

        # Aanbevelingen
        st.markdown("---")
        st.markdown("**Aanbevelingen voor deze klant:**")

        mape = customer_profile.backtest_result.overall_mape
        if mape < 15:
            st.markdown("✅ Het model is betrouwbaar voor deze klant. "
                       "Gebruik de forecast met vertrouwen voor planning.")
        elif mape < 30:
            st.markdown("⚠️ Het model geeft een redelijke indicatie. "
                       "Houd rekening met een marge van ±20% bij beslissingen.")
        else:
            st.markdown("❌ Het model heeft moeite met deze klant. "
                       "Overweeg conservatievere scenario's en kortere forecast horizons.")

        if customer_profile.backtest_result.bias > 5000:
            st.markdown("📉 Het model overschat systematisch. "
                       "Plan met een buffer voor lagere inkomsten.")
        elif customer_profile.backtest_result.bias < -5000:
            st.markdown("📈 Het model onderschat systematisch. "
                       "De werkelijke cashflow is vaak beter dan voorspeld.")


def render_methodologie_v7_tab(metadata: dict = None):
    """Methodologie tab: 3-pilaren model uitleg met implementatiestatus."""
    st.header("Methodologie: Structuur x Volume x Realiteit")
    st.caption("Gebaseerd op 'Datagedreven Liquiditeitsprognose' - wat is geimplementeerd en wat niet")

    st.markdown("""
    **Legenda:** ✅ Geimplementeerd | 🔶 Deels / afhankelijk van data | ❌ Roadmap
    """)

    # 1. DOEL
    st.subheader("1. Doel")
    st.markdown("""
    Een betrouwbare, bestuurbare liquiditeitsprognose die:
    - Volledig gevoed wordt vanuit ERP en het semantisch model
    - Geen handmatige aannames of Excel-correcties bevat
    - Gebruik maakt van historische patronen voor timing
    - Actuele feiten direct verwerkt
    - Geschikt is voor scenario-analyse

    > *De liquiditeitsprognose is geen rapport achteraf, maar een stuurinstrument vooruit.*

    **Status:** ✅ Geimplementeerd
    """)

    st.markdown("---")

    # 2. BRONNEN
    st.subheader("2. Bronnen")
    st.markdown("De prognose wordt gevoed door ERP + Semantisch model. Status per bron:")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **ERP-bronnen:**
        - ✅ Verkoopfacturen (debiteuren)
        - ✅ Debiteurenbetalingen (betaalgedrag/DSO)
        - ✅ Crediteurenfacturen
        - ✅ Betalingen crediteuren (DPO)
        - ✅ Historische cashflow (banktransacties)
        - ✅ BTW aangifteregels *(nieuw in V7)*
        - ✅ Salarishistorie *(nieuw in V7)*
        """)
    with col2:
        st.markdown("""
        **Uitgebreid / Roadmap:**
        - 🔶 Orders/orderportefeuille *(data per klant)*
        - 🔶 Projectadministratie *(data per klant)*
        - 🔶 Budget/Forecast *(run rate als proxy)*
        - ❌ Onderaanneming *(roadmap)*
        - ❌ Inkooporders *(roadmap)*
        """)

    # Toon welke bronnen daadwerkelijk data bevatten
    if metadata and 'sources_used' in metadata:
        sources = metadata['sources_used']
        active = [k for k, v in sources.items() if v]
        inactive = [k for k, v in sources.items() if not v]
        if active:
            st.success(f"**Actieve bronnen voor deze klant:** {', '.join(active)}")
        if inactive:
            st.info(f"**Geen data beschikbaar:** {', '.join(inactive)}")

    st.markdown("---")

    # 3. HET MODELPRINCIPE
    st.subheader("3. Het Modelprincipe: 3 Pilaren")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        **REALITEIT** *(week 0-3)*
        *Harde feiten domineren*

        - ✅ Gefactureerd → echte datum
        - ✅ Betaald → echte datum
        - ✅ Inkoopfactuur → vervaldatum
        - ✅ Banksaldo → actueel
        - 🔶 Salarismutatie → historie
        - ❌ Projectvoortgang
        """)

    with col2:
        st.markdown("""
        **STRUCTUUR** *(patronen)*
        *Timing uit 12+ mnd historie*

        - ✅ Betaalgedrag klanten (DSO)
        - ✅ Betaalgedrag leveranciers (DPO)
        - ✅ Seizoensverloop (maand + week)
        - ✅ BTW-ritme *(nieuw)*
        - ✅ Loonkosten seizoen *(nieuw)*
        - 🔶 Order → facturatieverloop
        - ❌ Projectdoorlooptijd
        - ❌ Cash-gap onderaanneming
        """)

    with col3:
        st.markdown("""
        **VOLUME** *(hoeveel)*
        *Budget of run rate*

        - 🔶 Budget/Forecast omzet
        - 🔶 Orderportefeuille
        - ✅ Run rate inkomsten (gewogen)
        - ✅ Run rate uitgaven (gewogen)
        - ❌ Forecast investeringen
        - ❌ Onderaannemingsratio's
        """)

    st.markdown("---")

    # 4. BLENDING
    st.subheader("4. Werking in de Tijd")
    st.markdown("""
    | Horizon | Dominante pilaar | Gewicht |
    |---------|-----------------|---------|
    | **Week 0-3** | Realiteit | 100% harde ERP-feiten |
    | **Week 4-8** | Overgang | Sigmoid blend van Realiteit naar Structuur x Volume |
    | **Week 8+** | Structuur x Volume | 100% patronen + volumes |

    Het model schuift mee en wordt nauwkeuriger naarmate de tijd verstrijkt.
    """)

    st.markdown("---")

    # 5. KASSTROMEN
    st.subheader("5. Kasstromen")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Inkomend:**
        - ✅ Debiteuren + betaalgedrag + seizoen
        - ✅ Salarissen: historisch patroon + pieken
        - ✅ BTW: ritme-detectie
        - 🔶 Projectfacturatie *(deels)*
        """)
    with col2:
        st.markdown("""
        **Uitgaand:**
        - ✅ Crediteuren + betaalgedrag + seizoen
        - ✅ Salarissen: maandelijks met pieken
        - ✅ BTW-afdracht: kwartaal/maandelijks
        - ❌ Onderaanneming cash-gap
        """)

    st.markdown("---")

    # 6. STRUCTUURPROFIEL (als metadata beschikbaar)
    if metadata and 'structuur_profile' in metadata:
        st.subheader("6. Gedetecteerde Patronen (deze klant)")
        sp = metadata['structuur_profile']

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Historie", f"{sp.get('history_months', 0)} maanden")
            st.metric("BTW-ritme", sp.get('btw_frequency', 'onbekend'))
        with col2:
            base = sp.get('salary_base', 0)
            st.metric("Salarisbasis", f"EUR {base:,.0f}/mnd" if base else "Geen data")
            peaks = sp.get('salary_peaks', {})
            if peaks:
                peak_str = ", ".join([f"mnd {m}: {f:.1f}x" for m, f in peaks.items()])
                st.caption(f"Pieken: {peak_str}")
        with col3:
            st.metric("DSO-relaties", sp.get('n_debiteuren_dso', 0))
            st.metric("DPO-relaties", sp.get('n_crediteuren_dpo', 0))

    st.markdown("---")

    # 7. WAT DIT OPLEVERT
    st.subheader("7. Wat dit oplevert")
    st.markdown("""
    - Betrouwbare 6-12 maanden liquiditeitsprognose
    - Inzicht in financieringsbehoefte
    - Zicht op projectmatige kasdruk
    - Scenarioanalyse (groei, krimp, betaalgedrag, investeringen)
    - Minder verrassingen

    > *Een betrouwbare liquiditeitsprognose ontstaat door: budget als volumebron,
    > ERP als feitelijke waarheid, historie als tijdstructuur, transparante aannames,
    > en continue actualisatie.*
    """)


def render_methodology_tab():
    """Render methodology tab explaining how the forecast works."""
    st.header("Prognosemethodiek")
    st.caption("Hoe de cashflow prognose wordt berekend")

    st.markdown("""
    Dit dashboard gebruikt een **Run Rate + Seasonality** model dat is gevalideerd
    over 16+ klanten met een gemiddelde nauwkeurigheid van **88%**.
    """)

    # === SECTIE 1: KERNPRINCIPES ===
    st.subheader("1. Kernprincipes")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Run Rate (Huidig Niveau)**
        - Gebaseerd op laatste 90 dagen
        - Gemiddelde weekomzet/uitgaven
        - Representeert het HUIDIGE activiteitsniveau
        """)

    with col2:
        st.markdown("""
        **Seasonality (Patroon)**
        - Gebaseerd op volledige historie
        - Week-van-de-maand patronen
        - Piek in week 4 (salarissen)
        """)

    st.markdown("---")

    # === SECTIE 2: DE 5 FASEN ===
    st.subheader("2. De 5 Fasen van de Forecast")

    with st.expander("📊 Fase 1: DSO per Debiteur (Betaalgedrag)", expanded=False):
        st.markdown("""
        In plaats van een globale vertraging gebruiken we **historisch betaalgedrag per klant**:

        ```
        Verwachte betaaldatum = Vervaldatum + DSO_correctie[klant]
        ```

        | Klant | Gem. betaaltijd | Betaaltermijn | DSO Correctie |
        |-------|-----------------|---------------|---------------|
        | Klant A | 45 dagen | 30 dagen | +15 dagen |
        | Klant B | 25 dagen | 30 dagen | -5 dagen |
        | Onbekend | 35 dagen | 30 dagen | +5 dagen (fallback) |

        **Voordeel:** Klanten die altijd te laat betalen worden realistisch ingepland.
        """)

    with st.expander("⚖️ Fase 2: Blended Waterfall (ERP + Statistiek)", expanded=False):
        st.markdown("""
        Combineert **bekende ERP data** met **statistische forecast** via geleidelijke overgang:

        | Week | ERP Data | Statistiek | Toelichting |
        |------|----------|------------|-------------|
        | Week 0-2 | 100% | 0% | Facturen zijn bekend |
        | Week 3-5 | 75% → 25% | 25% → 75% | Geleidelijke overgang |
        | Week 6+ | 0% | 100% | Volledig statistisch |

        **Voordeel:** Korte termijn is nauwkeurig (facturen), lange termijn valt terug op patronen.
        """)

    with st.expander("📅 Fase 3: Deterministische Kosten", expanded=False):
        st.markdown("""
        **Voorspelbare kosten worden automatisch gedetecteerd** uit historische patronen:

        | Kostensoort | Detectie | Frequentie |
        |-------------|----------|------------|
        | Salarissen | Week 4 piek (dag 22-28) | Maandelijks |
        | Loonbelasting | ~35% van salarissen | Maandelijks |
        | BTW afdracht | Pieken maart, juni, sept, dec | Kwartaal |

        **Voordeel:** Grote vaste kosten worden nooit "vergeten" in de prognose.
        """)

    with st.expander("📈 Fase 4: Week-van-Maand Patroon", expanded=False):
        st.markdown("""
        Herkent patronen binnen de maand:

        | Week | Dagen | Typisch patroon |
        |------|-------|-----------------|
        | Week 1 | 1-7 | Rustig, begin maand |
        | Week 2 | 8-14 | Normale activiteit |
        | Week 3 | 15-21 | Normale activiteit |
        | Week 4 | 22-28 | **Piek**: salarissen, belastingen |
        | Week 5 | 29-31 | Maandeinde afwikkeling |

        **Voordeel:** Salarisweken worden automatisch hoger ingeschat.
        """)

    with st.expander("🔮 Fase 5: Scenario Analyse", expanded=False):
        st.markdown("""
        Gebruikers kunnen scenario's simuleren via de schuifregelaars:

        | Parameter | Effect |
        |-----------|--------|
        | Omzet wijziging | Inkomsten én kosten proportioneel aanpassen |
        | Klanten betalen eerder/later | Inkomsten verschuiven in tijd |
        | Leveranciers eerder/later | Uitgaven verschuiven in tijd |

        **Voordeel:** "Wat als" analyses zonder de basisprognose te wijzigen.
        """)

    st.markdown("---")

    # === SECTIE 3: FORMULE ===
    st.subheader("3. Cumulatief Saldo Berekening")

    st.code("""
saldo[week] = saldo[week-1] + inkomsten[week] - uitgaven[week]

Waarbij:
- saldo[week 0] = huidige banksaldo
- inkomsten = DSO-gecorrigeerde debiteuren × blend_weight + statistiek × (1 - blend_weight)
- uitgaven = DPO-gecorrigeerde crediteuren × blend_weight + statistiek × (1 - blend_weight)
    """, language="python")

    st.markdown("---")

    # === SECTIE 4: NAUWKEURIGHEID ===
    st.subheader("4. Validatie & Nauwkeurigheid")

    st.markdown("""
    Het model is gevalideerd over meerdere klanten met walk-forward backtesting:

    | Metric | Waarde |
    |--------|--------|
    | Gemiddelde accuracy | 88% |
    | Klanten >= 80% | 14/16 (88%) |
    | Beste performer | 98% |
    | Methodiek | Run Rate (Mean) + Seasonality |

    **Realisatie vs Prognose:** In de grafiek wordt onderscheid gemaakt met:
    - **Donkere kleuren**: Historische realisatie
    - **Lichtere kleuren / gestippeld**: Toekomstige prognose
    """)


def render_datamodel_tab():
    """Render datamodel tab showing the database structure used by this dashboard."""
    st.header("Datamodel")
    st.caption("Overzicht van de database tabellen en relaties die dit dashboard gebruikt")

    # === SECTIE 1: OVERZICHT ===
    st.subheader("1. Database Structuur")

    st.markdown("""
    Dit dashboard haalt data uit de **Syntess DWH** (Data Warehouse). De data is georganiseerd in verschillende schema's:

    | Schema | Doel | Voorbeelden |
    |--------|------|-------------|
    | `notifica` | SSM (Self-Service Model) views | Verkoopfacturen, Inkoopfacturen, Administraties |
    | `financieel` | Financiële boekingen | Journaalregels, Rubrieken |
    | `stam` | Stamgegevens | Documenten, Dagboeken |
    """)

    # === SECTIE 2: ENTITEITEN DIAGRAM ===
    st.subheader("2. Entiteiten & Relaties")

    # Mermaid-achtige visualisatie met Streamlit
    st.markdown("""
    ```
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                           SYNTESS DWH DATAMODEL                              │
    └─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────┐       ┌──────────────────────┐
    │  SSM Administraties  │───────│  SSM Bedrijfseenheden│
    │──────────────────────│  1:N  │──────────────────────│
    │ • AdministratieKey   │       │ • BedrijfseenheidKey │
    │ • Administratie      │       │ • Bedrijfseenheid    │
    └──────────────────────┘       │ • AdministratieKey   │
            │                      └──────────────────────┘
            │ 1:N                           │ 1:N
            ▼                               ▼
    ┌──────────────────────┐       ┌──────────────────────┐
    │    SSM Documenten    │◄──────│ Verkoopfactuur       │
    │──────────────────────│  N:1  │ termijnen            │
    │ • DocumentKey        │       │──────────────────────│
    │ • Document code      │       │ • VerkoopfactuurKey  │
    │ • BedrijfseenheidKey │       │ • Debiteur           │
    └──────────────────────┘       │ • Vervaldatum        │
            │                      │ • Bedrag             │
            │                      │ • Alloc_datum        │
            │                      └──────────────────────┘
            │
            │                      ┌──────────────────────┐
            └─────────────────────►│ Inkoopfactuur        │
                              N:1  │ termijnen            │
                                   │──────────────────────│
                                   │ • InkoopFactuurKey   │
                                   │ • Crediteur          │
                                   │ • Vervaldatum        │
                                   │ • Bedrag             │
                                   │ • Bankafschrift status│
                                   └──────────────────────┘

    ┌──────────────────────┐       ┌──────────────────────┐
    │      Dagboeken       │───────│    Journaalregels    │
    │──────────────────────│  1:N  │──────────────────────│
    │ • DagboekKey         │       │ • JournaalregelKey   │
    │ • Dagboek            │       │ • DocumentKey        │
    │ • AdministratieKey   │       │ • Boekdatum          │
    │ • DagboekRubriekKey  │       │ • Bedrag             │
    └──────────────────────┘       │ • Debet/Credit       │
                                   │ • RubriekKey         │
                                   │ • AdministratieKey   │
                                   └──────────────────────┘
                                           │
                                           │ N:1
                                           ▼
                                   ┌──────────────────────┐
                                   │      Rubrieken       │
                                   │──────────────────────│
                                   │ • RubriekKey         │
                                   │ • Rubriek Code       │
                                   │ • Rubriek            │
                                   └──────────────────────┘
    ```
    """)

    # === SECTIE 3: TABELLEN DETAIL ===
    st.subheader("3. Tabel Details")

    with st.expander("📊 notifica.\"SSM Verkoopfactuur termijnen\"", expanded=False):
        st.markdown("""
        **Doel:** Openstaande debiteuren (verkoopfacturen)

        | Kolom | Type | Beschrijving |
        |-------|------|--------------|
        | `VerkoopfactuurDocumentKey` | bigint | FK naar SSM Documenten |
        | `Debiteur` | varchar | Naam van de debiteur |
        | `Vervaldatum` | date | Verwachte betaaldatum |
        | `Bedrag` | decimal | Factuurbedrag |
        | `Alloc_datum` | date | Datum van allocatie (gebruikt voor standdatum filter) |

        **Filter logica:**
        - `Alloc_datum <= standdatum` - alleen posten t/m de standdatum
        - `HAVING ABS(SUM(Bedrag)) > 0.01` - alleen niet-nul saldi
        """)

    with st.expander("📊 notifica.\"SSM Inkoopfactuur termijnen\"", expanded=False):
        st.markdown("""
        **Doel:** Openstaande crediteuren (inkoopfacturen)

        | Kolom | Type | Beschrijving |
        |-------|------|--------------|
        | `InkoopFactuurKey` | bigint | FK naar SSM Documenten |
        | `Crediteur` | varchar | Naam van de crediteur |
        | `Vervaldatum` | date | Verwachte betaaldatum |
        | `Bedrag` | decimal | Factuurbedrag |
        | `Alloc_datum` | date | Datum van allocatie |
        | `Bankafschrift status` | varchar | 'Openstaand' of 'Betaald' |

        **Filter logica:**
        - `Alloc_datum <= standdatum`
        - `Bankafschrift status = 'Openstaand'` - alleen onbetaalde facturen
        """)

    with st.expander("📊 financieel.\"Journaalregels\"", expanded=False):
        st.markdown("""
        **Doel:** Alle financiële boekingen (basis voor banksaldi en cashflow analyse)

        | Kolom | Type | Beschrijving |
        |-------|------|--------------|
        | `DocumentKey` | bigint | FK naar stam.Documenten |
        | `Boekdatum` | date | Datum van de boeking |
        | `Bedrag` | decimal | Bedrag van de boeking |
        | `Debet/Credit` | char(1) | 'D' = Debet, 'C' = Credit |
        | `RubriekKey` | bigint | FK naar Rubrieken |
        | `AdministratieKey` | bigint | FK naar Administraties |

        **Gebruik:**
        - **Banksaldi:** Filter op `StandaardEntiteitKey = 10` (bankdocumenten)
        - **Terugkerende kosten:** Filter op rubriekcodes (4xxx, 61xx, etc.)
        - **Historische cashflow:** Aggregatie per week/maand
        """)

    with st.expander("📊 stam.\"Dagboeken\"", expanded=False):
        st.markdown("""
        **Doel:** Dagboekdefinities (banken, kas, memoriaal, etc.)

        | Kolom | Type | Beschrijving |
        |-------|------|--------------|
        | `DagboekKey` | bigint | Primary key |
        | `Dagboek` | varchar | Naam van het dagboek (bijv. "ABN Bank") |
        | `AdministratieKey` | bigint | FK naar Administraties |
        | `DagboekRubriekKey` | bigint | Grootboekrekening van het dagboek |

        **Gebruik:**
        - Banksaldi worden berekend per dagboek
        - `DagboekRubriekKey` wordt gebruikt om alleen boekingen OP de bankrekening te selecteren
        """)

    with st.expander("📊 financieel.\"Rubrieken\"", expanded=False):
        st.markdown("""
        **Doel:** Grootboekrekeningen (rubrieken)

        | Kolom | Type | Beschrijving |
        |-------|------|--------------|
        | `RubriekKey` | bigint | Primary key |
        | `Rubriek Code` | varchar | Rekeningnummer (bijv. "1230", "4000") |
        | `Rubriek` | varchar | Omschrijving |

        **Belangrijke rubriekcodes:**
        - `1230` - Voorziening debiteuren
        - `4xxx` - Personeelskosten
        - `61xx` - Huisvestingskosten
        - `62xx` - Machinekosten
        - `65xx` - Autokosten
        """)

    # === SECTIE 4: KEY FILTERS ===
    st.subheader("4. Belangrijke Filters")

    st.markdown("""
    Het dashboard gebruikt de volgende key filters:

    | Filter | Tabel | Kolom | Waarde |
    |--------|-------|-------|--------|
    | Bank documenten | stam.Documenten | `StandaardEntiteitKey` | `= 10` |
    | Alleen bankrekening boekingen | financieel.Journaalregels | `RubriekKey` | `= dag.DagboekRubriekKey` |
    | Openstaande crediteuren | notifica.SSM Inkoopfactuur termijnen | `Bankafschrift status` | `= 'Openstaand'` |
    | Administratie filter | notifica.SSM Administraties | `Administratie` of `AdministratieKey` | Geselecteerde waarde |
    """)



def render_validation_tab(data: dict, customer_code: str, load_timestamp: datetime):
    """Render validation tab met controletotalen en databronnen."""
    st.header("Validatie & Aansluiting")
    st.caption(f"Data geladen op: **{load_timestamp.strftime('%Y-%m-%d %H:%M:%S')}** | Klant: **{customer_code}** (via Notifica API)")

    # === SECTIE 1: CONTROLETOTALEN ===
    st.subheader("1. Controletotalen")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Banksaldi**")
        if not data["banksaldo"].empty:
            totaal_bank = data["banksaldo"]["saldo"].sum()
            st.metric("Totaal liquide middelen", f"EUR {totaal_bank:,.2f}")
            st.dataframe(
                data["banksaldo"][["bank_naam", "rekeningnummer", "saldo"]].style.format({"saldo": "EUR {:,.2f}"}),
                hide_index=True,
                use_container_width=True
            )
        else:
            st.warning("Geen banksaldi gevonden")

    with col2:
        st.markdown("**Openstaande Debiteuren**")
        if not data["debiteuren"].empty:
            totaal_deb = data["debiteuren"]["openstaand"].sum()
            st.metric("Totaal openstaand", f"EUR {totaal_deb:,.2f}")
            st.metric("Aantal posten", f"{len(data['debiteuren'])}")
        else:
            st.warning("Geen openstaande debiteuren")

    with col3:
        st.markdown("**Openstaande Crediteuren**")
        if not data["crediteuren"].empty:
            totaal_cred = data["crediteuren"]["openstaand"].sum()
            st.metric("Totaal openstaand", f"EUR {totaal_cred:,.2f}")
            st.metric("Aantal posten", f"{len(data['crediteuren'])}")
        else:
            st.warning("Geen openstaande crediteuren")

    # === SECTIE 2: DATABRONNEN STATUS ===
    st.markdown("---")
    st.subheader("2. Databronnen Status")

    sources = {
        "Banksaldi": not data.get("banksaldo", pd.DataFrame()).empty,
        "Debiteuren": not data.get("debiteuren", pd.DataFrame()).empty,
        "Crediteuren": not data.get("crediteuren", pd.DataFrame()).empty,
        "Historische cashflow": not data.get("historische_cashflow", pd.DataFrame()).empty,
        "Betaalgedrag debiteuren": not data.get("betaalgedrag_debiteuren", pd.DataFrame()).empty,
        "Betaalgedrag crediteuren": not data.get("betaalgedrag_crediteuren", pd.DataFrame()).empty,
        "BTW aangifteregels": not data.get("btw_aangifteregels", pd.DataFrame()).empty,
        "Salarishistorie": not data.get("salarishistorie", pd.DataFrame()).empty,
        "Budgetten": not data.get("budgetten", pd.DataFrame()).empty,
        "Orderportefeuille": not data.get("orderportefeuille", pd.DataFrame()).empty,
    }

    for name, available in sources.items():
        icon = "✅" if available else "❌"
        st.markdown(f"{icon} {name}")

    st.markdown(f"\n**Verbinding:** Notifica Data API | Klant: `{customer_code}`")


def render_customer_selector():
    """Klant is hardcoded via KLANTNUMMER in .env."""
    st.sidebar.header(f"🏢 {CUSTOMER_NAME}")
    st.sidebar.success(f"Verbonden via Notifica API (klant {CUSTOMER_CODE})")
    return False, CUSTOMER_CODE


def render_data_summary(data: Dict[str, pd.DataFrame], filtered: bool = False):
    """Render samenvatting van de data met aantallen."""
    prefix = "Gefilterd: " if filtered else ""

    col1, col2, col3 = st.columns(3)

    with col1:
        n_deb = len(data["debiteuren"]) if not data["debiteuren"].empty else 0
        st.caption(f"{prefix}{n_deb} openstaande debiteuren")

    with col2:
        n_cred = len(data["crediteuren"]) if not data["crediteuren"].empty else 0
        st.caption(f"{prefix}{n_cred} openstaande crediteuren")

    with col3:
        n_bank = len(data["banksaldo"]) if not data["banksaldo"].empty else 0
        st.caption(f"{prefix}{n_bank} bankrekeningen")


def main():
    """Main application entry point."""
    # Header
    st.title(f"Liquiditeitsprognose - {CUSTOMER_NAME}")
    st.markdown(f"*Datagedreven liquiditeitsprognose: Structuur x Volume x Realiteit*")

    # Sidebar controls - Logo linksboven
    import os
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "notifica-logo.svg")
    if os.path.exists(logo_path):
        st.sidebar.image(logo_path, width=150)
    st.sidebar.markdown("---")

    # Customer selection
    use_mock, customer_code = render_customer_selector()

    st.sidebar.markdown("---")

    # Standdatum selector (BEFORE loading data - affects which data is fetched)
    st.sidebar.header("Peildatum")
    standdatum = st.sidebar.date_input(
        "Standdatum",
        value=datetime.now().date(),
        help="Peildatum voor openstaande posten. Toont facturen die op deze datum nog openstonden."
    )

    # Administratie selectie (voor prognose met vaste lasten)
    selected_admin = None  # Wordt automatisch gedetecteerd uit data

    st.sidebar.markdown("---")

    # Toon actieve database in header
    if not use_mock and customer_code:
        st.caption(f"Database: **{customer_code}** | Standdatum: **{standdatum}**")

    # Load data first (needed for filter options)
    load_timestamp = datetime.now()
    with st.spinner(f"Data laden voor klant {customer_code} per {standdatum}..." if customer_code else "Data laden..."):
        data = load_data(
            use_mock=use_mock,
            customer_code=customer_code,
            standdatum=standdatum,
            administratie=selected_admin
        )

    # Filter controls
    filters = render_filter_sidebar(data)

    st.sidebar.markdown("---")

    # Prognose instellingen (horizon)
    (forecast_weeks, history_weeks) = render_scenario_sidebar()

    # Apply filters to data
    has_active_filters = any([
        filters.get("bankrekeningen"),
        filters.get("administratie") and filters.get("administratie") != "Alle",
        filters.get("bedrijfseenheid") and filters.get("bedrijfseenheid") != "Alle",
    ])

    if has_active_filters:
        filtered_data = apply_data_filters(data, filters)
        st.info("Filters actief - data is gefilterd")
    else:
        filtered_data = data

    # Calculate metrics
    metrics = calculate_liquidity_metrics(
        filtered_data["banksaldo"],
        filtered_data["debiteuren"],
        filtered_data["crediteuren"]
    )

    # =========================================================================
    # FORECAST MODEL V7: Structuur x Volume x Realiteit
    # =========================================================================
    calibrated_dso = filtered_data.get("calibrated_dso")
    calibrated_dpo = filtered_data.get("calibrated_dpo")

    forecast, forecast_start_idx, forecast_metadata = create_forecast_v7(
        data=filtered_data,
        weeks_forecast=forecast_weeks,
        weeks_history=history_weeks,
        reference_date=standdatum,
        calibrated_dso=calibrated_dso,
        calibrated_dpo=calibrated_dpo,
    )

    # Toon model info in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Model V7: Structuur x Volume x Realiteit**")

    if forecast_metadata:
        portfolio_dso = forecast_metadata.get("portfolio_dso", 35)
        dso_calibrated = forecast_metadata.get("dso_calibrated", False)
        avg_income = forecast_metadata.get("avg_weekly_income", 0)
        avg_expense = forecast_metadata.get("avg_weekly_expense", 0)

        dso_label = f"DSO: **{portfolio_dso:.0f} dagen**"
        if dso_calibrated:
            dso_label += " (gecalibreerd)"
        st.sidebar.caption(dso_label)
        st.sidebar.caption(f"Gem. inkomsten: EUR {avg_income:,.0f}/week")
        st.sidebar.caption(f"Gem. uitgaven: EUR {avg_expense:,.0f}/week")

        # V7 extra info
        sp = forecast_metadata.get('structuur_profile', {})
        sources = forecast_metadata.get('sources_used', {})
        active_sources = sum(1 for v in sources.values() if v)
        st.sidebar.caption(f"Databronnen: {active_sources}/{len(sources)} actief")
        if sp.get('history_months'):
            st.sidebar.caption(f"Historie: {sp['history_months']} maanden")

    # === KLANTPROFIEL (optioneel voor insights) ===
    customer_profile = None

    # === TABS ===
    tab_dashboard, tab_insights, tab_methodologie, tab_methodiek, tab_validatie, tab_datamodel = st.tabs([
        "📊 Dashboard",
        "🎯 Klantinzichten",
        "📋 Methodologie",
        "📈 Prognosemethodiek",
        "🔍 Validatie & Aansluiting",
        "🗃️ Datamodel"
    ])

    with tab_dashboard:
        # Alerts section
        st.markdown("---")
        render_alerts(forecast, metrics)

        # KPI Cards
        st.markdown("---")
        render_kpi_cards(metrics)
        render_data_summary(filtered_data, filtered=has_active_filters)

        # Scenario controls (between KPI cards and chart)
        st.markdown("---")
        debiteur_delay, crediteur_delay, omzet_wijziging = render_scenario_controls()

        # Apply scenario adjustments to forecast
        scenario_forecast = forecast.copy()
        if omzet_wijziging != 0 or debiteur_delay != 0 or crediteur_delay != 0:
            multiplier = 1 + (omzet_wijziging / 100)

            # Apply revenue/cost adjustment (proportional for project companies)
            if omzet_wijziging != 0:
                # Alleen prognose aanpassen, niet realisatie
                prognose_mask = scenario_forecast['is_realisatie'] == False
                scenario_forecast.loc[prognose_mask, 'inkomsten_debiteuren'] *= multiplier
                scenario_forecast.loc[prognose_mask, 'uitgaven_crediteuren'] *= multiplier

            # Apply timing delays (shift amounts earlier or later)
            if debiteur_delay != 0 or crediteur_delay != 0:
                weeks_delay_deb = debiteur_delay // 7
                weeks_delay_cred = crediteur_delay // 7

                prognose_mask = scenario_forecast['is_realisatie'] == False

                if weeks_delay_deb != 0:
                    # Shift income: positive = later (prepend zeros), negative = earlier (append zeros)
                    prognose_income = scenario_forecast.loc[prognose_mask, 'inkomsten_debiteuren'].values.copy()
                    n = len(prognose_income)
                    if weeks_delay_deb > 0:
                        # Later: schuif naar rechts (prepend zeros)
                        shift = min(weeks_delay_deb, n)
                        shifted_income = [0] * shift + list(prognose_income[:-shift]) if shift < n else [0] * n
                    else:
                        # Eerder: schuif naar links (append zeros)
                        shift = min(abs(weeks_delay_deb), n)
                        shifted_income = list(prognose_income[shift:]) + [0] * shift if shift < n else [0] * n
                    scenario_forecast.loc[prognose_mask, 'inkomsten_debiteuren'] = shifted_income[:n]

                if weeks_delay_cred != 0:
                    # Shift expenses: positive = later, negative = earlier
                    prognose_expense = scenario_forecast.loc[prognose_mask, 'uitgaven_crediteuren'].values.copy()
                    n = len(prognose_expense)
                    if weeks_delay_cred > 0:
                        # Later: schuif naar rechts (prepend zeros)
                        shift = min(weeks_delay_cred, n)
                        shifted_expense = [0] * shift + list(prognose_expense[:-shift]) if shift < n else [0] * n
                    else:
                        # Eerder: schuif naar links (append zeros)
                        shift = min(abs(weeks_delay_cred), n)
                        shifted_expense = list(prognose_expense[shift:]) + [0] * shift if shift < n else [0] * n
                    scenario_forecast.loc[prognose_mask, 'uitgaven_crediteuren'] = shifted_expense[:n]

            # Recalculate netto and cumulative
            scenario_forecast['netto_cashflow'] = scenario_forecast['inkomsten_debiteuren'] - scenario_forecast['uitgaven_crediteuren'] - scenario_forecast['uitgaven_salarissen'] - scenario_forecast['uitgaven_overig']
            start_balance = filtered_data["banksaldo"]['saldo'].sum() if not filtered_data["banksaldo"].empty and 'saldo' in filtered_data["banksaldo"].columns else 0
            scenario_forecast['cumulatief_saldo'] = start_balance + scenario_forecast['netto_cashflow'].cumsum()

        # Transparency legend
        render_transparency_legend()

        # Main cashflow chart with realisatie/prognose distinction
        st.markdown("---")
        cashflow_fig = render_transparent_cashflow_chart(scenario_forecast, forecast_start_idx, reference_date=standdatum)
        st.plotly_chart(cashflow_fig, key="cashflow_main_chart")

        # Pie charts voor compositie debiteuren/crediteuren (met filter functie)
        st.markdown("---")
        selected_deb, selected_cred = render_pie_charts_with_filter(
            filtered_data["debiteuren"],
            filtered_data["crediteuren"]
        )

        # Aging analysis - gefilterd op geselecteerde relatie
        st.markdown("---")

        # Filter data op geselecteerde relatie voor ouderdomsanalyse
        aging_deb_data = filtered_data["debiteuren"]
        aging_cred_data = filtered_data["crediteuren"]

        if selected_deb and not filtered_data["debiteuren"].empty:
            aging_deb_data = filtered_data["debiteuren"][
                filtered_data["debiteuren"]["debiteur_naam"] == selected_deb
            ]

        if selected_cred and not filtered_data["crediteuren"].empty:
            aging_cred_data = filtered_data["crediteuren"][
                filtered_data["crediteuren"]["crediteur_naam"] == selected_cred
            ]

        aging_deb = calculate_aging_buckets(aging_deb_data, reference_date=standdatum)
        aging_cred = calculate_aging_buckets(aging_cred_data, reference_date=standdatum)
        render_aging_chart(aging_deb, aging_cred, selected_deb, selected_cred)

        # Detailed table
        st.markdown("---")
        render_cashflow_details(forecast)

    with tab_insights:
        st.header("Klantinzichten & Validatie Rapport")

        # Use detected admin if no selected admin
        insights_admin = selected_admin or data.get("detected_admin")

        if customer_code and insights_admin:
            with st.spinner("Klantinzichten genereren..."):
                try:
                    # Genereer insights
                    db = get_database(use_mock=False, customer_code=customer_code)
                    insights = generate_customer_insights(db, customer_code, insights_admin)

                    # Toon confidence badge
                    conf_color = {"hoog": "green", "matig": "orange", "laag": "red"}.get(insights.forecast_confidence, "gray")
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #{conf_color}22, #{conf_color}11);
                                border-left: 4px solid {conf_color}; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                        <h3 style="margin:0; color: {conf_color};">Forecast Betrouwbaarheid: {insights.forecast_confidence.upper()}</h3>
                        <p style="margin: 5px 0 0 0;">Inkomsten {insights.income_accuracy:.0f}% | Uitgaven {insights.expense_accuracy:.0f}% nauwkeurig</p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Data kwaliteit waarschuwing
                    if insights.data_quality_score < 70:
                        st.warning(f"Data kwaliteit: {insights.data_quality_score:.0f}/100 - Meer historische data nodig voor betrouwbare prognose")

                    # Toon markdown rapport
                    st.markdown(insights.summary)

                    # Validatie tabel
                    st.subheader("Validatie tegen Realisatie")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Inkomsten/week", f"EUR {insights.forecast_income_weekly:,.0f}",
                                  f"{insights.income_accuracy:.0f}% nauwkeurig")
                    with col2:
                        st.metric("Uitgaven/week", f"EUR {insights.forecast_expense_weekly:,.0f}",
                                  f"{insights.expense_accuracy:.0f}% nauwkeurig")
                    with col3:
                        st.metric("DSO", f"{insights.avg_dso_days:.0f} dagen",
                                  "gecalibreerd" if insights.data_quality_score > 50 else "default")

                    # Patronen
                    st.subheader("Patronen & Risico's")
                    pcol1, pcol2 = st.columns(2)
                    with pcol1:
                        st.markdown(f"""
                        | Kenmerk | Waarde |
                        |---------|--------|
                        | Seizoenspatroon | {insights.seasonality_strength} (piek week {insights.peak_week_of_month}) |
                        | Betaalgedrag | {insights.payment_behavior} |
                        | Cashflow volatiliteit | {insights.cashflow_volatility:.0f}% |
                        """)
                    with pcol2:
                        st.markdown(f"""
                        | Risico | Waarde |
                        |--------|--------|
                        | Concentratie grootste debiteur | {insights.largest_debtor_concentration:.0f}% |
                        | Weken met negatieve cashflow | {insights.negative_weeks_ratio:.0f}% |
                        | Data kwaliteit | {insights.data_quality_score:.0f}/100 |
                        """)

                    # Aanbevelingen
                    if insights.recommendations:
                        st.subheader("Aanbevelingen")
                        for rec in insights.recommendations:
                            st.markdown(f"- {rec}")

                except Exception as e:
                    st.error(f"Kon klantinzichten niet genereren: {e}")
                    st.info("Controleer of de klant voldoende historische data heeft.")
        else:
            st.info("Geen administratie gevonden. Controleer of de database data bevat.")

    with tab_methodologie:
        render_methodologie_v7_tab(forecast_metadata)

    with tab_methodiek:
        render_methodology_tab()

    with tab_validatie:
        render_validation_tab(data, customer_code or CUSTOMER_CODE, load_timestamp)

    with tab_datamodel:
        render_datamodel_tab()

    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666; font-size: 0.8rem;'>"
        f"Liquiditeitsprognose - {CUSTOMER_NAME} | Notifica - Business Intelligence voor installatiebedrijven<br>"
        "<em>Model V7: Structuur x Volume x Realiteit</em>"
        "</div>",
        unsafe_allow_html=True
    )


def check_password() -> bool:
    """Wachtwoordbeveiliging via Streamlit secrets."""
    try:
        correct_password = st.secrets["auth"]["password"]
    except (KeyError, AttributeError):
        return True  # Geen wachtwoord geconfigureerd = geen beveiliging

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("Liquiditeitsprognose")
    st.markdown("*Voer het wachtwoord in om toegang te krijgen.*")
    password = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if password == correct_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Onjuist wachtwoord.")
    return False


if __name__ == "__main__":
    if check_password():
        main()
