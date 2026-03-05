"""
Liquiditeit Dashboard - Calculations
====================================
Business logic voor liquiditeitsberekeningen en cashflow prognoses.

Methoden:
- DSO per debiteur: Adjusted Due Date logica op basis van historisch betaalgedrag
- Fading Weight Ensemble: Glijdende schaal tussen ERP data en statistische forecast
- ML Forecast: Seizoenspatronen, trend en weighted moving average
"""

import pandas as pd
import numpy as np
import math
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict
from dataclasses import dataclass


@dataclass
class LiquidityMetrics:
    """Container for liquidity KPIs."""
    current_ratio: float
    quick_ratio: float
    cash_position: float
    total_receivables: float
    total_payables: float
    net_working_capital: float
    days_cash_on_hand: float


def calculate_liquidity_metrics(
    banksaldo: pd.DataFrame,
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    avg_daily_expenses: float = 5000.0
) -> LiquidityMetrics:
    """
    Calculate key liquidity metrics.

    Args:
        banksaldo: DataFrame with bank balances
        debiteuren: DataFrame with accounts receivable
        crediteuren: DataFrame with accounts payable
        avg_daily_expenses: Average daily operating expenses

    Returns:
        LiquidityMetrics with calculated KPIs
    """
    cash = banksaldo["saldo"].sum() if not banksaldo.empty else 0
    receivables = debiteuren["openstaand"].sum() if not debiteuren.empty else 0
    payables = crediteuren["openstaand"].sum() if not crediteuren.empty else 0

    # Current ratio = Current Assets / Current Liabilities
    current_assets = cash + receivables
    current_liabilities = payables if payables > 0 else 1  # Avoid division by zero

    current_ratio = current_assets / current_liabilities

    # Quick ratio = (Current Assets - Inventory) / Current Liabilities
    # For service companies, quick ratio ≈ current ratio (no inventory)
    quick_ratio = (cash + receivables) / current_liabilities

    # Net working capital
    net_working_capital = current_assets - payables

    # Days cash on hand
    days_cash = cash / avg_daily_expenses if avg_daily_expenses > 0 else 0

    return LiquidityMetrics(
        current_ratio=round(current_ratio, 2),
        quick_ratio=round(quick_ratio, 2),
        cash_position=cash,
        total_receivables=receivables,
        total_payables=payables,
        net_working_capital=net_working_capital,
        days_cash_on_hand=round(days_cash, 1),
    )


# =============================================================================
# FASE 1: DSO PER DEBITEUR - ADJUSTED DUE DATE LOGICA
# =============================================================================

def calculate_dso_adjustment(
    betaalgedrag: pd.DataFrame,
    standaard_betaaltermijn: int = 30,
    fallback_dagen: float = None
) -> Dict[str, float]:
    """
    Bereken de DSO correctie per debiteur.

    Voor elke debiteur berekenen we hoeveel dagen EXTRA (of minder)
    we moeten optellen bij de vervaldatum om de verwachte betaaldatum te krijgen.

    Args:
        betaalgedrag: DataFrame met kolommen:
            - debiteur_code
            - gem_dagen_tot_betaling
            - betrouwbaarheid (0-1)
        standaard_betaaltermijn: Standaard betaaltermijn in dagen (bijv. 30)
        fallback_dagen: Fallback voor onbekende debiteuren (default: gemiddelde)

    Returns:
        Dict met debiteur_code -> extra_dagen (kan negatief zijn voor snelle betalers)
    """
    if betaalgedrag.empty:
        return {"_fallback": 0}

    # Bereken gemiddelde als fallback
    gem_alle = betaalgedrag["gem_dagen_tot_betaling"].mean()
    if fallback_dagen is None:
        fallback_dagen = gem_alle - standaard_betaaltermijn

    adjustments = {"_fallback": round(fallback_dagen, 1)}

    for _, row in betaalgedrag.iterrows():
        debiteur = row["debiteur_code"]
        gem_dagen = row["gem_dagen_tot_betaling"]
        betrouwbaarheid = row.get("betrouwbaarheid", 0.5)

        # Extra dagen = werkelijke betaaltijd - standaard termijn
        # Positief = betaalt later dan termijn
        # Negatief = betaalt eerder dan termijn
        extra_dagen = gem_dagen - standaard_betaaltermijn

        # Weeg de correctie met betrouwbaarheid
        # Lage betrouwbaarheid -> correctie richting gemiddelde
        gewogen_extra = (
            betrouwbaarheid * extra_dagen +
            (1 - betrouwbaarheid) * (gem_alle - standaard_betaaltermijn)
        )

        adjustments[debiteur] = round(gewogen_extra, 1)

    return adjustments


def adjust_receivables_due_dates(
    debiteuren: pd.DataFrame,
    dso_adjustments: Dict[str, float],
    date_column: str = "vervaldatum"
) -> pd.DataFrame:
    """
    Pas de vervaldatums aan op basis van historisch betaalgedrag per debiteur.

    Dit is de kern van de "Adjusted Due Date" methode:
    Verwachte betaaldatum = Vervaldatum + DSO correctie per klant

    Args:
        debiteuren: DataFrame met openstaande debiteuren
        dso_adjustments: Dict van debiteur_code -> extra_dagen
        date_column: Naam van de datum kolom

    Returns:
        DataFrame met extra kolom 'verwachte_betaling'
    """
    if debiteuren.empty:
        return debiteuren

    df = debiteuren.copy()

    # Zorg dat vervaldatum een date is
    df[date_column] = pd.to_datetime(df[date_column]).dt.date

    # Fallback voor onbekende debiteuren
    fallback = dso_adjustments.get("_fallback", 0)

    def get_expected_date(row):
        debiteur = row.get("debiteur_code", row.get("debiteur_naam", ""))
        vervaldatum = row[date_column]

        if pd.isna(vervaldatum):
            return None

        # Zoek DSO correctie voor deze debiteur
        extra_dagen = dso_adjustments.get(debiteur, fallback)

        # Bereken verwachte betaaldatum
        if isinstance(vervaldatum, datetime):
            return (vervaldatum + timedelta(days=extra_dagen)).date()
        else:
            return vervaldatum + timedelta(days=extra_dagen)

    df["verwachte_betaling"] = df.apply(get_expected_date, axis=1)
    df["dso_correctie_dagen"] = df.apply(
        lambda row: dso_adjustments.get(
            row.get("debiteur_code", row.get("debiteur_naam", "")),
            fallback
        ),
        axis=1
    )

    return df


# =============================================================================
# FASE 2: FADING WEIGHT ENSEMBLE MODEL
# =============================================================================

def sigmoid_fading_weight(week: int, midpoint: int = 5, steepness: float = 1.5) -> Tuple[float, float]:
    """
    Bereken fading weights met sigmoid functie voor natuurlijke overgang.

    Week 1-2: ~90-95% ERP data (bekende posten)
    Week 5-6: ~50% ERP, 50% statistiek
    Week 10+: ~10-20% ERP, 80-90% statistiek

    Args:
        week: Week nummer (1 = eerste forecast week)
        midpoint: Week waar 50/50 split is (default: 5)
        steepness: Hoe snel de overgang is (hoger = steilere curve)

    Returns:
        Tuple van (weight_erp, weight_statistiek)
    """
    # Sigmoid: 1 / (1 + e^((week - midpoint) / steepness))
    weight_erp = 1 / (1 + math.exp((week - midpoint) / steepness))

    # Begrens tussen 0.05 en 0.95 (nooit 100% één bron)
    weight_erp = max(0.05, min(0.95, weight_erp))
    weight_stat = 1 - weight_erp

    return round(weight_erp, 3), round(weight_stat, 3)


def calculate_ensemble_forecast_week(
    week_num: int,
    bekende_inkomsten: float,
    bekende_uitgaven: float,
    stat_inkomsten: float,
    stat_uitgaven: float,
    midpoint: int = 5
) -> Tuple[float, float, float, float, str]:
    """
    Bereken de ensemble forecast voor één week.

    Combineert bekende openstaande posten (ERP) met statistische forecast
    met een glijdende schaal gebaseerd op de voorspelhorizon.

    Args:
        week_num: Week nummer (1 = eerste forecast week)
        bekende_inkomsten: Som van openstaande debiteuren met verwachte betaling in deze week
        bekende_uitgaven: Som van openstaande crediteuren met verwachte betaling in deze week
        stat_inkomsten: Statistische forecast inkomsten (ML model output)
        stat_uitgaven: Statistische forecast uitgaven (ML model output)
        midpoint: Week waar 50/50 split is

    Returns:
        Tuple van (forecast_in, forecast_uit, weight_erp, weight_stat, methode_beschrijving)
    """
    w_erp, w_stat = sigmoid_fading_weight(week_num, midpoint)

    # Ensemble berekening
    # Als er bekende posten zijn, gebruik die met w_erp gewicht
    # Anders valt de w_erp component weg en gebruiken we alleen stat

    if bekende_inkomsten > 0 or bekende_uitgaven > 0:
        # We hebben ERP data
        forecast_in = (w_erp * bekende_inkomsten) + (w_stat * stat_inkomsten)
        forecast_uit = (w_erp * bekende_uitgaven) + (w_stat * stat_uitgaven)
        methode = f"ensemble: ERP {w_erp*100:.0f}% + stat {w_stat*100:.0f}%"
    else:
        # Geen ERP data voor deze week - gebruik alleen statistiek
        # maar met lagere confidence (zie create_fading_weight_forecast)
        forecast_in = stat_inkomsten
        forecast_uit = stat_uitgaven
        methode = f"statistisch (geen bekende posten)"

    return forecast_in, forecast_uit, w_erp, w_stat, methode


def create_fading_weight_forecast(
    banksaldo: pd.DataFrame,
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    historische_cashflow: pd.DataFrame,
    betaalgedrag_debiteuren: pd.DataFrame,
    betaalgedrag_crediteuren: pd.DataFrame = None,
    weeks: int = 13,
    weeks_history: int = 4,
    reference_date=None,
    standaard_betaaltermijn: int = 30,
    ensemble_midpoint: int = 5,
) -> Tuple[pd.DataFrame, int, Dict]:
    """
    Creëer cashflow forecast met Fading Weight Ensemble methode.

    Deze methode combineert:
    1. DSO-gecorrigeerde openstaande posten (korte termijn, hoge zekerheid)
    2. Statistische forecast uit ML model (lange termijn, lagere zekerheid)
    3. Sigmoid-based fading weights voor natuurlijke overgang

    Args:
        banksaldo: Huidige banksaldi
        debiteuren: Openstaande debiteuren
        crediteuren: Openstaande crediteuren
        historische_cashflow: Historische wekelijkse cashflow
        betaalgedrag_debiteuren: DSO data per debiteur
        betaalgedrag_crediteuren: DPO data per crediteur (optioneel)
        weeks: Aantal weken forecast
        weeks_history: Aantal weken realisatie data
        reference_date: Standdatum
        standaard_betaaltermijn: Standaard betaaltermijn voor DSO berekening
        ensemble_midpoint: Week waar 50/50 split is

    Returns:
        Tuple van (forecast DataFrame, forecast_start_idx, metadata dict)
    """
    if reference_date is None:
        reference_date = datetime.now().date()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    # =========================================================================
    # STAP 1: Bereken DSO correcties per debiteur
    # =========================================================================
    dso_adjustments = calculate_dso_adjustment(
        betaalgedrag_debiteuren,
        standaard_betaaltermijn=standaard_betaaltermijn
    )

    # Pas vervaldatums aan op basis van DSO
    debiteuren_adjusted = adjust_receivables_due_dates(debiteuren, dso_adjustments)

    # Crediteur DPO (optioneel - vaak betalen we zelf op tijd)
    if betaalgedrag_crediteuren is not None and not betaalgedrag_crediteuren.empty:
        dpo_adjustments = calculate_dso_adjustment(
            betaalgedrag_crediteuren.rename(columns={"crediteur_code": "debiteur_code"}),
            standaard_betaaltermijn=standaard_betaaltermijn
        )
        crediteuren_adjusted = adjust_receivables_due_dates(
            crediteuren.rename(columns={"crediteur_code": "debiteur_code"}),
            dpo_adjustments
        ).rename(columns={"debiteur_code": "crediteur_code"})
    else:
        # Geen DPO data - gebruik vervaldatum direct
        crediteuren_adjusted = crediteuren.copy()
        if not crediteuren_adjusted.empty and "vervaldatum" in crediteuren_adjusted.columns:
            crediteuren_adjusted["verwachte_betaling"] = pd.to_datetime(
                crediteuren_adjusted["vervaldatum"]
            ).dt.date

    # =========================================================================
    # STAP 2: Leer statistisch model uit historische data
    # =========================================================================
    pattern = learn_weekly_pattern(historische_cashflow)

    all_rows = []

    # =========================================================================
    # STAP 3: REALISATIE - Historische weken
    # =========================================================================
    if weeks_history > 0 and not historische_cashflow.empty:
        hist = historische_cashflow.copy()
        hist["week_start"] = pd.to_datetime(hist["week_start"]).dt.date
        hist = hist[hist["week_start"] < reference_date]
        hist = hist.sort_values("week_start", ascending=False).head(weeks_history)
        hist = hist.sort_values("week_start", ascending=True)

        for i, row in enumerate(hist.itertuples()):
            week_num = -(weeks_history - i)
            inkomsten = getattr(row, "inkomsten", 0)
            uitgaven = getattr(row, "uitgaven", 0)
            netto = inkomsten - uitgaven

            all_rows.append({
                "week_nummer": week_num,
                "week_label": f"Week {week_num}",
                "week_start": row.week_start,
                "week_eind": row.week_start + timedelta(days=7),
                "maand": row.week_start.month if hasattr(row.week_start, 'month') else 0,
                "inkomsten_debiteuren": round(inkomsten, 2),
                "uitgaven_crediteuren": round(uitgaven, 2),
                "netto_cashflow": round(netto, 2),
                "data_type": "Realisatie",
                "is_realisatie": True,
                "confidence": 1.0,
                "weight_erp": 1.0,
                "weight_stat": 0.0,
                "methode": "realisatie",
            })

    forecast_start_idx = len(all_rows)

    # =========================================================================
    # STAP 4: PROGNOSE - Fading Weight Ensemble
    # =========================================================================
    week_starts = [reference_date + timedelta(weeks=i) for i in range(weeks + 1)]

    for i in range(weeks):
        week_start = week_starts[i]
        week_end = week_starts[i + 1]
        week_maand = week_start.month
        week_num = i + 1

        # --- Bekende inkomsten uit DSO-gecorrigeerde debiteuren ---
        bekende_in = 0.0
        if not debiteuren_adjusted.empty and "verwachte_betaling" in debiteuren_adjusted.columns:
            mask = (
                (debiteuren_adjusted["verwachte_betaling"] >= week_start) &
                (debiteuren_adjusted["verwachte_betaling"] < week_end)
            )
            bekende_in = debiteuren_adjusted.loc[mask, "openstaand"].sum()

        # --- Bekende uitgaven uit crediteuren ---
        bekende_uit = 0.0
        if not crediteuren_adjusted.empty and "verwachte_betaling" in crediteuren_adjusted.columns:
            mask = (
                (crediteuren_adjusted["verwachte_betaling"] >= week_start) &
                (crediteuren_adjusted["verwachte_betaling"] < week_end)
            )
            bekende_uit = crediteuren_adjusted.loc[mask, "openstaand"].sum()

        # --- Statistische forecast uit ML model ---
        stat_in, stat_uit, ml_conf, ml_methode = predict_week_ml(
            week_idx=i,
            week_maand=week_maand,
            pattern=pattern,
            bekende_in=0,  # Geef 0 mee, we doen zelf de blending
            bekende_uit=0,
            weeks_ahead=week_num
        )

        # --- Ensemble berekening ---
        forecast_in, forecast_uit, w_erp, w_stat, methode = calculate_ensemble_forecast_week(
            week_num=week_num,
            bekende_inkomsten=bekende_in,
            bekende_uitgaven=bekende_uit,
            stat_inkomsten=stat_in,
            stat_uitgaven=stat_uit,
            midpoint=ensemble_midpoint
        )

        # --- Confidence berekening ---
        # Basis: sigmoid weight (hoe meer ERP, hoe hoger confidence)
        base_confidence = w_erp * 0.95 + w_stat * ml_conf

        # Verlaag confidence als geen bekende posten
        if bekende_in == 0 and bekende_uit == 0:
            base_confidence *= 0.8

        confidence = round(min(0.95, max(0.2, base_confidence)), 2)

        netto = forecast_in - forecast_uit

        all_rows.append({
            "week_nummer": week_num,
            "week_label": f"Week {week_num}",
            "week_start": week_start,
            "week_eind": week_end,
            "maand": week_maand,
            "inkomsten_debiteuren": round(forecast_in, 2),
            "uitgaven_crediteuren": round(forecast_uit, 2),
            "inkomsten_bekend": round(bekende_in, 2),
            "uitgaven_bekend": round(bekende_uit, 2),
            "inkomsten_stat": round(stat_in, 2),
            "uitgaven_stat": round(stat_uit, 2),
            "netto_cashflow": round(netto, 2),
            "data_type": "Prognose",
            "is_realisatie": False,
            "confidence": confidence,
            "weight_erp": w_erp,
            "weight_stat": w_stat,
            "methode": methode,
        })

    df = pd.DataFrame(all_rows)

    # Bereken cumulatief saldo
    start_balance = banksaldo["saldo"].sum() if not banksaldo.empty else 0
    df["cumulatief_saldo"] = start_balance + df["netto_cashflow"].cumsum()

    # Metadata voor debugging/rapportage
    metadata = {
        "methode": "fading_weight_ensemble",
        "dso_adjustments": dso_adjustments,
        "ensemble_midpoint": ensemble_midpoint,
        "standaard_betaaltermijn": standaard_betaaltermijn,
        "pattern_has_data": pattern.get("has_pattern", False),
        "n_debiteuren_met_dso": len([k for k in dso_adjustments.keys() if k != "_fallback"]),
    }

    return df, forecast_start_idx, metadata


def create_weekly_cashflow_forecast(
    banksaldo: pd.DataFrame,
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    salarissen: pd.DataFrame,
    weeks: int = 13,
    debiteur_delay_days: int = 0,
    crediteur_delay_days: int = 0,
) -> pd.DataFrame:
    """
    Create a weekly cashflow forecast for the specified number of weeks.

    Args:
        banksaldo: Current bank balances
        debiteuren: Outstanding receivables with due dates
        crediteuren: Outstanding payables with due dates
        salarissen: Planned salary payments
        weeks: Number of weeks to forecast
        debiteur_delay_days: Scenario: extra days before customers pay
        crediteur_delay_days: Scenario: extra days before we pay suppliers

    Returns:
        DataFrame with weekly cashflow forecast
    """
    today = datetime.now().date()

    # Create weekly buckets
    week_starts = [today + timedelta(weeks=i) for i in range(weeks + 1)]
    week_labels = [f"Week {i+1}" for i in range(weeks)]

    # Initialize result DataFrame
    forecast = pd.DataFrame({
        "week_nummer": range(1, weeks + 1),
        "week_label": week_labels,
        "week_start": week_starts[:-1],
        "week_eind": week_starts[1:],
        "inkomsten_debiteuren": 0.0,
        "uitgaven_crediteuren": 0.0,
        "uitgaven_salarissen": 0.0,
        "uitgaven_overig": 0.0,
        "netto_cashflow": 0.0,
        "cumulatief_saldo": 0.0,
    })

    # Aggregate debiteuren per week (with optional delay scenario)
    if not debiteuren.empty and "vervaldatum" in debiteuren.columns:
        deb = debiteuren.copy()
        deb["vervaldatum"] = pd.to_datetime(deb["vervaldatum"]).dt.date
        deb["verwachte_betaling"] = deb["vervaldatum"] + timedelta(days=debiteur_delay_days)

        for idx, row in forecast.iterrows():
            week_start = row["week_start"]
            week_end = row["week_eind"]
            mask = (deb["verwachte_betaling"] >= week_start) & (deb["verwachte_betaling"] < week_end)
            forecast.loc[idx, "inkomsten_debiteuren"] = deb.loc[mask, "openstaand"].sum()

    # Aggregate crediteuren per week (with optional delay scenario)
    if not crediteuren.empty and "vervaldatum" in crediteuren.columns:
        cred = crediteuren.copy()
        cred["vervaldatum"] = pd.to_datetime(cred["vervaldatum"]).dt.date
        cred["verwachte_betaling"] = cred["vervaldatum"] + timedelta(days=crediteur_delay_days)

        for idx, row in forecast.iterrows():
            week_start = row["week_start"]
            week_end = row["week_eind"]
            mask = (cred["verwachte_betaling"] >= week_start) & (cred["verwachte_betaling"] < week_end)
            forecast.loc[idx, "uitgaven_crediteuren"] = cred.loc[mask, "openstaand"].sum()

    # Add salary payments
    if not salarissen.empty and "betaaldatum" in salarissen.columns:
        sal = salarissen.copy()
        sal["betaaldatum"] = pd.to_datetime(sal["betaaldatum"]).dt.date

        for idx, row in forecast.iterrows():
            week_start = row["week_start"]
            week_end = row["week_eind"]
            mask = (sal["betaaldatum"] >= week_start) & (sal["betaaldatum"] < week_end)
            forecast.loc[idx, "uitgaven_salarissen"] = sal.loc[mask, "bedrag"].sum()

    # Calculate net cashflow per week
    forecast["netto_cashflow"] = (
        forecast["inkomsten_debiteuren"]
        - forecast["uitgaven_crediteuren"]
        - forecast["uitgaven_salarissen"]
        - forecast["uitgaven_overig"]
    )

    # Calculate cumulative balance starting from current bank balance
    start_balance = banksaldo["saldo"].sum() if not banksaldo.empty else 0
    forecast["cumulatief_saldo"] = start_balance + forecast["netto_cashflow"].cumsum()

    return forecast


def calculate_aging_buckets(
    df: pd.DataFrame,
    date_column: str = "vervaldatum",
    amount_column: str = "openstaand",
    reference_date: Optional[datetime] = None
) -> pd.DataFrame:
    """
    Calculate aging buckets (ouderdomsanalyse) for receivables or payables.

    Args:
        df: DataFrame with due dates and amounts
        date_column: Name of the due date column
        amount_column: Name of the amount column
        reference_date: Reference date for aging (default: today)

    Returns:
        DataFrame with aging bucket summary
    """
    if df.empty:
        return pd.DataFrame({
            "bucket": ["Niet vervallen", "1-30 dagen", "31-60 dagen", "61-90 dagen", "> 90 dagen"],
            "bedrag": [0.0] * 5,
            "percentage": [0.0] * 5,
        })

    if reference_date is None:
        reference_date = datetime.now().date()

    df = df.copy()
    # Convert to datetime first, then to date - keep NaT handling robust
    date_series = pd.to_datetime(df[date_column], errors='coerce')

    # Calculate days overdue - handle NaT values before .dt.date conversion
    def calc_days(dt_val):
        if pd.isna(dt_val):
            return 0
        try:
            return (reference_date - dt_val.date()).days
        except (AttributeError, TypeError):
            return 0

    df["dagen_vervallen"] = date_series.apply(calc_days)

    # Define buckets
    def assign_bucket(days):
        if days <= 0:
            return "Niet vervallen"
        elif days <= 30:
            return "1-30 dagen"
        elif days <= 60:
            return "31-60 dagen"
        elif days <= 90:
            return "61-90 dagen"
        else:
            return "> 90 dagen"

    df["bucket"] = df["dagen_vervallen"].apply(assign_bucket)

    # Aggregate by bucket
    bucket_order = ["Niet vervallen", "1-30 dagen", "31-60 dagen", "61-90 dagen", "> 90 dagen"]
    summary = df.groupby("bucket")[amount_column].sum().reset_index()
    summary.columns = ["bucket", "bedrag"]

    # Ensure all buckets are present
    all_buckets = pd.DataFrame({"bucket": bucket_order})
    summary = all_buckets.merge(summary, on="bucket", how="left").fillna(0)

    # Calculate percentages
    total = summary["bedrag"].sum()
    summary["percentage"] = (summary["bedrag"] / total * 100).round(1) if total > 0 else 0

    return summary


def predict_payment_date(
    historical_behavior: pd.DataFrame,
    invoice_due_date: datetime,
    customer_id: Optional[str] = None
) -> Tuple[datetime, float]:
    """
    Predict when a payment will actually be received based on historical behavior.

    Args:
        historical_behavior: Historical payment data
        invoice_due_date: The official due date
        customer_id: Optional customer ID for customer-specific prediction

    Returns:
        Tuple of (predicted_date, confidence_score)
    """
    if historical_behavior.empty:
        # Default: assume payment on due date
        return invoice_due_date, 0.5

    # Calculate average delay from historical data
    avg_delay = historical_behavior["gem_betaaltermijn_debiteuren"].mean()
    std_delay = historical_behavior["gem_betaaltermijn_debiteuren"].std()

    # Assume invoices are sent with 30-day terms
    standard_terms = 30
    extra_days = int(avg_delay - standard_terms)

    if isinstance(invoice_due_date, datetime):
        predicted_date = invoice_due_date + timedelta(days=max(0, extra_days))
    else:
        predicted_date = datetime.combine(invoice_due_date, datetime.min.time()) + timedelta(days=max(0, extra_days))

    # Confidence based on consistency (lower std = higher confidence)
    confidence = max(0.3, min(0.95, 1 - (std_delay / 30))) if std_delay else 0.7

    return predicted_date, round(confidence, 2)


def calculate_seasonality_factors(
    historische_cashflow: pd.DataFrame,
) -> dict:
    """
    Bereken seizoensgebonden factoren per maand op basis van historische cashflow.

    Args:
        historische_cashflow: DataFrame met week_start, maand, inkomsten, uitgaven, netto

    Returns:
        Dict met per maand (1-12) de gemiddelde inkomsten, uitgaven en netto
    """
    if historische_cashflow.empty or "maand" not in historische_cashflow.columns:
        return {}

    # Groepeer per maand en bereken gemiddelden
    monthly = historische_cashflow.groupby("maand").agg({
        "inkomsten": "mean",
        "uitgaven": "mean",
        "netto": "mean"
    }).to_dict(orient="index")

    return monthly


def calculate_recurring_costs_per_week(
    terugkerende_kosten: pd.DataFrame,
) -> dict:
    """
    Bereken gemiddelde terugkerende kosten per week, gegroepeerd per kostensoort.

    Args:
        terugkerende_kosten: DataFrame met maand, kostensoort, bedrag

    Returns:
        Dict met per kostensoort het gemiddelde bedrag per week
    """
    if terugkerende_kosten.empty or "kostensoort" not in terugkerende_kosten.columns:
        return {"totaal_per_week": 0.0}

    # Tel totaal per kostensoort over alle maanden
    by_soort = terugkerende_kosten.groupby("kostensoort")["bedrag"].sum()

    # Bepaal aantal maanden in de dataset
    n_maanden = terugkerende_kosten["maand"].nunique() if "maand" in terugkerende_kosten.columns else 12

    result = {}
    totaal = 0.0
    for soort, totaal_bedrag in by_soort.items():
        gem_per_maand = totaal_bedrag / n_maanden if n_maanden > 0 else 0
        gem_per_week = gem_per_maand / 4.33  # ~4.33 weken per maand
        result[soort] = round(gem_per_week, 2)
        totaal += gem_per_week

    result["totaal_per_week"] = round(totaal, 2)
    return result


def create_enhanced_cashflow_forecast(
    banksaldo: pd.DataFrame,
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    terugkerende_kosten: pd.DataFrame,
    historische_cashflow: pd.DataFrame,
    weeks: int = 13,
    weeks_history: int = 4,
    debiteur_delay_days: int = 0,
    crediteur_delay_days: int = 0,
    reference_date = None,
    include_recurring_costs: bool = True,
    use_seasonality: bool = True,
) -> Tuple[pd.DataFrame, int]:
    """
    Verbeterde cashflow prognose gebaseerd op historisch profiel + bekende posten.
    Inclusief realisatie data (historische weken voor de standdatum).

    Methodiek:
    1. Week 1-4: Primair gebaseerd op openstaande posten (hoge zekerheid)
    2. Week 5+: Geleidelijke overgang naar historisch profiel (afnemende zekerheid)
    3. Confidence indicator per week voor transparantie

    Returns:
        Tuple van (DataFrame, forecast_start_idx) - net als create_transparent_cashflow_forecast
    """
    if reference_date is None:
        reference_date = datetime.now().date()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    # Bereken seizoensfactoren (historisch gemiddelde per maand)
    seasonality = calculate_seasonality_factors(historische_cashflow)

    # Bereken overall gemiddelden als fallback
    if not historische_cashflow.empty:
        overall_gem_in = historische_cashflow["inkomsten"].mean()
        overall_gem_uit = historische_cashflow["uitgaven"].mean()
        overall_gem_netto = historische_cashflow["netto"].mean() if "netto" in historische_cashflow.columns else overall_gem_in - overall_gem_uit
    else:
        overall_gem_in = 0
        overall_gem_uit = 0
        overall_gem_netto = 0

    all_rows = []

    # =========================================================================
    # DEEL 1: REALISATIE - Historische weken uit de echte cashflow data
    # =========================================================================
    if weeks_history > 0 and not historische_cashflow.empty:
        hist = historische_cashflow.copy()
        hist["week_start"] = pd.to_datetime(hist["week_start"]).dt.date

        # Filter op weken voor de reference_date
        hist = hist[hist["week_start"] < reference_date]
        hist = hist.sort_values("week_start", ascending=False).head(weeks_history)
        hist = hist.sort_values("week_start", ascending=True)  # Terug naar chronologisch

        for i, row in enumerate(hist.itertuples()):
            week_num = -(weeks_history - i)
            inkomsten = getattr(row, "inkomsten", 0)
            uitgaven = getattr(row, "uitgaven", 0)
            netto = inkomsten - uitgaven

            all_rows.append({
                "week_nummer": week_num,
                "week_label": f"Week {week_num}",
                "week_start": row.week_start,
                "week_eind": row.week_start + timedelta(days=7),
                "maand": row.week_start.month if hasattr(row.week_start, 'month') else 0,
                "inkomsten_debiteuren": round(inkomsten, 2),
                "uitgaven_crediteuren": round(uitgaven, 2),
                "netto_cashflow": round(netto, 2),
                "data_type": "Realisatie",
                "is_realisatie": True,
                "confidence": 1.0,  # 100% zekerheid voor realisatie
                "bron_inkomsten": "realisatie",
                "bron_uitgaven": "realisatie",
            })

    forecast_start_idx = len(all_rows)

    # =========================================================================
    # DEEL 2: PROGNOSE - Toekomstige weken met slimme combinatie
    # =========================================================================
    week_starts = [reference_date + timedelta(weeks=i) for i in range(weeks + 1)]

    # Bereken totaal bekende openstaande posten voor confidence berekening
    totaal_bekende_deb = debiteuren["openstaand"].sum() if not debiteuren.empty else 0
    totaal_bekende_cred = crediteuren["openstaand"].sum() if not crediteuren.empty else 0

    for i in range(weeks):
        week_start = week_starts[i]
        week_end = week_starts[i + 1]
        week_maand = week_start.month

        # === STAP 1: Haal historisch profiel voor deze maand ===
        if use_seasonality and week_maand in seasonality:
            hist_in = seasonality[week_maand].get("inkomsten", overall_gem_in)
            hist_uit = seasonality[week_maand].get("uitgaven", overall_gem_uit)
        else:
            hist_in = overall_gem_in
            hist_uit = overall_gem_uit

        # === STAP 2: Bekende inkomsten uit openstaande debiteuren ===
        bekende_in = 0.0
        if not debiteuren.empty and "vervaldatum" in debiteuren.columns:
            deb = debiteuren.copy()
            deb["vervaldatum"] = pd.to_datetime(deb["vervaldatum"]).dt.date
            deb["verwachte_betaling"] = deb["vervaldatum"].apply(
                lambda x: x + timedelta(days=debiteur_delay_days) if pd.notna(x) else None
            )
            mask = (deb["verwachte_betaling"] >= week_start) & (deb["verwachte_betaling"] < week_end)
            bekende_in = deb.loc[mask, "openstaand"].sum()

        # === STAP 3: Bekende uitgaven uit openstaande crediteuren ===
        bekende_uit = 0.0
        if not crediteuren.empty and "vervaldatum" in crediteuren.columns:
            cred = crediteuren.copy()
            cred["vervaldatum"] = pd.to_datetime(cred["vervaldatum"]).dt.date
            cred["verwachte_betaling"] = cred["vervaldatum"].apply(
                lambda x: x + timedelta(days=crediteur_delay_days) if pd.notna(x) else None
            )
            mask = (cred["verwachte_betaling"] >= week_start) & (cred["verwachte_betaling"] < week_end)
            bekende_uit = cred.loc[mask, "openstaand"].sum()

        # === STAP 4: Bereken blend factor (0-1) ===
        # Week 1-4: veel gewicht op bekende posten
        # Week 5+: geleidelijk meer gewicht op historisch profiel
        if i < 4:
            # Eerste 4 weken: 90% bekende posten, 10% historisch (als aanvulling)
            blend_factor = 0.9
        else:
            # Week 5+: lineair aflopend naar 30% bekende posten
            # Week 5: 70%, Week 6: 60%, ... Week 13: 30%
            blend_factor = max(0.3, 0.9 - (i - 3) * 0.1)

        # === STAP 5: Combineer bronnen met blend factor ===
        # Als er bekende posten zijn, gebruik die met blend_factor gewicht
        # Vul aan met historisch profiel voor het resterende deel

        if bekende_in > 0:
            # Er zijn bekende inkomsten - combineer met historisch
            forecast_in = (blend_factor * bekende_in) + ((1 - blend_factor) * hist_in)
            bron_in = f"openstaand ({blend_factor*100:.0f}%) + historisch ({(1-blend_factor)*100:.0f}%)"
        elif hist_in > 0:
            # Geen bekende inkomsten - gebruik volledig historisch profiel
            forecast_in = hist_in
            bron_in = "historisch profiel"
        else:
            # Geen data beschikbaar
            forecast_in = 0
            bron_in = "geen data"

        if bekende_uit > 0:
            forecast_uit = (blend_factor * bekende_uit) + ((1 - blend_factor) * hist_uit)
            bron_uit = f"openstaand ({blend_factor*100:.0f}%) + historisch ({(1-blend_factor)*100:.0f}%)"
        elif hist_uit > 0:
            forecast_uit = hist_uit
            bron_uit = "historisch profiel"
        else:
            forecast_uit = 0
            bron_uit = "geen data"

        # === STAP 6: Bereken confidence score ===
        # Gebaseerd op: (1) hoeveel is bekend vs geschat, (2) hoe ver in de toekomst
        week_confidence = blend_factor  # Basis: blend factor
        if bekende_in == 0 and bekende_uit == 0:
            # Volledig gebaseerd op historie - lagere confidence
            week_confidence *= 0.6
        elif bekende_in == 0 or bekende_uit == 0:
            # Deels gebaseerd op historie
            week_confidence *= 0.8

        # Netto cashflow
        netto = forecast_in - forecast_uit

        all_rows.append({
            "week_nummer": i + 1,
            "week_label": f"Week {i + 1}",
            "week_start": week_start,
            "week_eind": week_end,
            "maand": week_maand,
            "inkomsten_debiteuren": round(forecast_in, 2),
            "uitgaven_crediteuren": round(forecast_uit, 2),
            "inkomsten_bekend": round(bekende_in, 2),
            "uitgaven_bekend": round(bekende_uit, 2),
            "inkomsten_historisch": round(hist_in, 2),
            "uitgaven_historisch": round(hist_uit, 2),
            "netto_cashflow": round(netto, 2),
            "data_type": "Prognose",
            "is_realisatie": False,
            "confidence": round(week_confidence, 2),
            "bron_inkomsten": bron_in,
            "bron_uitgaven": bron_uit,
        })

    df = pd.DataFrame(all_rows)

    # Bereken cumulatief saldo
    start_balance = banksaldo["saldo"].sum() if not banksaldo.empty else 0
    df["cumulatief_saldo"] = start_balance + df["netto_cashflow"].cumsum()

    return df, forecast_start_idx


# =============================================================================
# ML-GEBASEERDE FORECAST MET BACKTESTING
# =============================================================================

@dataclass
class ForecastModelMetrics:
    """Container voor model performance metrics."""
    mape_inkomsten: float  # Mean Absolute Percentage Error voor inkomsten
    mape_uitgaven: float   # Mean Absolute Percentage Error voor uitgaven
    mape_netto: float      # Mean Absolute Percentage Error voor netto cashflow
    rmse_netto: float      # Root Mean Square Error voor netto cashflow
    bias: float            # Systematische over/onderschatting
    n_test_weeks: int      # Aantal weken in test set
    model_type: str        # Type model gebruikt


def learn_weekly_pattern(
    historische_cashflow: pd.DataFrame,
    min_weeks: int = 8
) -> dict:
    """
    Leer het wekelijkse cashflow patroon uit historische data.

    Berekent:
    - Gemiddelde per maand (seizoenspatroon)
    - Trend (stijgend/dalend)
    - Volatiliteit (standaarddeviatie)

    Args:
        historische_cashflow: DataFrame met week_start, maand, inkomsten, uitgaven, netto
        min_weeks: Minimum aantal weken data nodig

    Returns:
        Dict met geleerde parameters
    """
    if historische_cashflow.empty or len(historische_cashflow) < min_weeks:
        return {
            "has_pattern": False,
            "reason": f"Te weinig data ({len(historische_cashflow)} weken, minimum {min_weeks})"
        }

    df = historische_cashflow.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.sort_values("week_start")

    # === 1. SEIZOENSPATROON PER MAAND ===
    monthly_pattern = df.groupby("maand").agg({
        "inkomsten": ["mean", "std", "count"],
        "uitgaven": ["mean", "std", "count"],
        "netto": ["mean", "std"]
    })

    # Flatten column names
    monthly_pattern.columns = [
        "inkomsten_mean", "inkomsten_std", "inkomsten_count",
        "uitgaven_mean", "uitgaven_std", "uitgaven_count",
        "netto_mean", "netto_std"
    ]

    # === 2. TREND DETECTIE (linear regression) ===
    df["week_idx"] = range(len(df))

    # Inkomsten trend
    if df["inkomsten"].std() > 0:
        x = df["week_idx"].values
        y = df["inkomsten"].values
        slope_in, intercept_in = np.polyfit(x, y, 1)
    else:
        slope_in, intercept_in = 0, df["inkomsten"].mean()

    # Uitgaven trend
    if df["uitgaven"].std() > 0:
        x = df["week_idx"].values
        y = df["uitgaven"].values
        slope_uit, intercept_uit = np.polyfit(x, y, 1)
    else:
        slope_uit, intercept_uit = 0, df["uitgaven"].mean()

    # === 3. VOLATILITEIT ===
    volatility_in = df["inkomsten"].std() / df["inkomsten"].mean() if df["inkomsten"].mean() > 0 else 0
    volatility_uit = df["uitgaven"].std() / df["uitgaven"].mean() if df["uitgaven"].mean() > 0 else 0

    # === 4. WEIGHTED MOVING AVERAGE (recente weken belangrijker) ===
    # Exponentiële weights: recentste week heeft hoogste weight
    n = len(df)
    alpha = 0.3  # Smoothing factor
    weights = np.array([(1 - alpha) ** (n - 1 - i) for i in range(n)])
    weights = weights / weights.sum()

    wma_inkomsten = np.average(df["inkomsten"].values, weights=weights)
    wma_uitgaven = np.average(df["uitgaven"].values, weights=weights)

    return {
        "has_pattern": True,
        "monthly_pattern": monthly_pattern.to_dict(orient="index"),
        "trend": {
            "inkomsten_slope": slope_in,
            "inkomsten_intercept": intercept_in,
            "uitgaven_slope": slope_uit,
            "uitgaven_intercept": intercept_uit,
        },
        "volatility": {
            "inkomsten": volatility_in,
            "uitgaven": volatility_uit,
        },
        "weighted_avg": {
            "inkomsten": wma_inkomsten,
            "uitgaven": wma_uitgaven,
        },
        "overall_avg": {
            "inkomsten": df["inkomsten"].mean(),
            "uitgaven": df["uitgaven"].mean(),
            "netto": df["netto"].mean() if "netto" in df.columns else df["inkomsten"].mean() - df["uitgaven"].mean(),
        },
        "n_weeks": len(df),
        "last_week_idx": n - 1,
    }


def predict_week_ml(
    week_idx: int,
    week_maand: int,
    pattern: dict,
    bekende_in: float = 0,
    bekende_uit: float = 0,
    weeks_ahead: int = 1,
) -> Tuple[float, float, float, str]:
    """
    Voorspel cashflow voor een specifieke week met ML-gebaseerd model.

    Combineert:
    1. Bekende openstaande posten (als beschikbaar)
    2. Seizoenspatroon voor de maand
    3. Trend extrapolatie
    4. Weighted moving average

    Args:
        week_idx: Index van de week (vanaf laatste bekende week)
        week_maand: Maand nummer (1-12)
        pattern: Geleerde patronen uit learn_weekly_pattern()
        bekende_in: Bekende inkomsten uit openstaande debiteuren
        bekende_uit: Bekende uitgaven uit openstaande crediteuren
        weeks_ahead: Hoeveel weken vooruit we voorspellen

    Returns:
        Tuple van (voorspelde_inkomsten, voorspelde_uitgaven, confidence, methode_beschrijving)
    """
    if not pattern.get("has_pattern", False):
        # Geen patroon geleerd - gebruik alleen bekende posten
        return bekende_in, bekende_uit, 0.3, "alleen bekende posten (geen historie)"

    # === Component 1: Seizoenspatroon ===
    monthly = pattern["monthly_pattern"]
    if week_maand in monthly:
        seasonal_in = monthly[week_maand].get("inkomsten_mean", 0)
        seasonal_uit = monthly[week_maand].get("uitgaven_mean", 0)
        seasonal_count = monthly[week_maand].get("inkomsten_count", 0)
    else:
        seasonal_in = pattern["overall_avg"]["inkomsten"]
        seasonal_uit = pattern["overall_avg"]["uitgaven"]
        seasonal_count = 0

    # === Component 2: Trend extrapolatie ===
    future_idx = pattern["last_week_idx"] + week_idx + 1
    trend_in = pattern["trend"]["inkomsten_slope"] * future_idx + pattern["trend"]["inkomsten_intercept"]
    trend_uit = pattern["trend"]["uitgaven_slope"] * future_idx + pattern["trend"]["uitgaven_intercept"]

    # Begrens trend om extreme extrapolaties te voorkomen
    avg_in = pattern["overall_avg"]["inkomsten"]
    avg_uit = pattern["overall_avg"]["uitgaven"]
    trend_in = np.clip(trend_in, avg_in * 0.5, avg_in * 1.5)
    trend_uit = np.clip(trend_uit, avg_uit * 0.5, avg_uit * 1.5)

    # === Component 3: Weighted Moving Average ===
    wma_in = pattern["weighted_avg"]["inkomsten"]
    wma_uit = pattern["weighted_avg"]["uitgaven"]

    # === Combineer componenten met gewichten ===
    # Gewichten afhankelijk van beschikbare data en voorspelhorizon

    if weeks_ahead <= 4:
        # Korte termijn: meer gewicht op bekende posten en WMA
        w_bekend = 0.5 if (bekende_in > 0 or bekende_uit > 0) else 0.0
        w_seasonal = 0.2
        w_trend = 0.1
        w_wma = 0.3 if w_bekend == 0 else 0.2
    else:
        # Lange termijn: meer gewicht op seizoen en trend
        w_bekend = 0.2 if (bekende_in > 0 or bekende_uit > 0) else 0.0
        w_seasonal = 0.4
        w_trend = 0.2
        w_wma = 0.4 if w_bekend == 0 else 0.2

    # Normaliseer gewichten
    total_w = w_bekend + w_seasonal + w_trend + w_wma
    w_bekend /= total_w
    w_seasonal /= total_w
    w_trend /= total_w
    w_wma /= total_w

    # Bereken gewogen voorspelling
    pred_in = (
        w_bekend * bekende_in +
        w_seasonal * seasonal_in +
        w_trend * trend_in +
        w_wma * wma_in
    )

    pred_uit = (
        w_bekend * bekende_uit +
        w_seasonal * seasonal_uit +
        w_trend * trend_uit +
        w_wma * wma_uit
    )

    # === Bereken confidence ===
    # Basis confidence aflopend met voorspelhorizon
    base_confidence = max(0.3, 1.0 - (weeks_ahead * 0.05))

    # Verhoog confidence als we veel seizoensdata hebben
    if seasonal_count >= 4:
        base_confidence *= 1.1

    # Verlaag confidence bij hoge volatiliteit
    vol = max(pattern["volatility"]["inkomsten"], pattern["volatility"]["uitgaven"])
    if vol > 0.5:
        base_confidence *= 0.8

    # Verhoog confidence als bekende posten overeenkomen met patroon
    if bekende_in > 0 and abs(bekende_in - seasonal_in) / max(seasonal_in, 1) < 0.3:
        base_confidence *= 1.05

    confidence = min(0.95, max(0.2, base_confidence))

    # Beschrijving
    methode = f"ML ensemble: bekend({w_bekend*100:.0f}%) + seizoen({w_seasonal*100:.0f}%) + trend({w_trend*100:.0f}%) + WMA({w_wma*100:.0f}%)"

    return pred_in, pred_uit, confidence, methode


def backtest_forecast_model(
    historische_cashflow: pd.DataFrame,
    test_weeks: int = 8,
    forecast_horizon: int = 4,
) -> Tuple[ForecastModelMetrics, pd.DataFrame]:
    """
    Voer walk-forward backtesting uit om model nauwkeurigheid te meten.

    Methodiek:
    1. Train op eerste N-test_weeks weken
    2. Voorspel de volgende forecast_horizon weken
    3. Vergelijk met werkelijke waarden
    4. Schuif 1 week op en herhaal

    Args:
        historische_cashflow: Volledige historische data
        test_weeks: Aantal weken om te testen
        forecast_horizon: Hoeveel weken vooruit voorspellen per test

    Returns:
        Tuple van (ForecastModelMetrics, DataFrame met alle voorspellingen vs actuals)
    """
    if historische_cashflow.empty or len(historische_cashflow) < test_weeks + 8:
        return ForecastModelMetrics(
            mape_inkomsten=999,
            mape_uitgaven=999,
            mape_netto=999,
            rmse_netto=999,
            bias=0,
            n_test_weeks=0,
            model_type="insufficient_data"
        ), pd.DataFrame()

    df = historische_cashflow.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.sort_values("week_start").reset_index(drop=True)

    results = []

    # Walk-forward validation
    for test_start_idx in range(len(df) - test_weeks, len(df) - forecast_horizon + 1):
        # Training data: alles tot test_start_idx
        train_data = df.iloc[:test_start_idx].copy()

        # Leer patroon van training data
        pattern = learn_weekly_pattern(train_data)

        if not pattern.get("has_pattern", False):
            continue

        # Voorspel de volgende forecast_horizon weken
        for h in range(min(forecast_horizon, len(df) - test_start_idx)):
            actual_idx = test_start_idx + h
            actual_row = df.iloc[actual_idx]

            week_maand = int(actual_row["maand"])

            # Voorspel (zonder bekende posten - pure ML test)
            pred_in, pred_uit, conf, methode = predict_week_ml(
                week_idx=h,
                week_maand=week_maand,
                pattern=pattern,
                bekende_in=0,  # Geen bekende posten voor pure ML test
                bekende_uit=0,
                weeks_ahead=h + 1
            )

            actual_in = actual_row["inkomsten"]
            actual_uit = actual_row["uitgaven"]
            actual_netto = actual_in - actual_uit
            pred_netto = pred_in - pred_uit

            results.append({
                "test_date": actual_row["week_start"],
                "horizon": h + 1,
                "pred_inkomsten": pred_in,
                "actual_inkomsten": actual_in,
                "pred_uitgaven": pred_uit,
                "actual_uitgaven": actual_uit,
                "pred_netto": pred_netto,
                "actual_netto": actual_netto,
                "confidence": conf,
                "error_in": pred_in - actual_in,
                "error_uit": pred_uit - actual_uit,
                "error_netto": pred_netto - actual_netto,
            })

    if not results:
        return ForecastModelMetrics(
            mape_inkomsten=999,
            mape_uitgaven=999,
            mape_netto=999,
            rmse_netto=999,
            bias=0,
            n_test_weeks=0,
            model_type="no_results"
        ), pd.DataFrame()

    results_df = pd.DataFrame(results)

    # Bereken metrics
    def safe_mape(pred, actual):
        """MAPE met bescherming tegen deling door 0."""
        mask = actual != 0
        if mask.sum() == 0:
            return 0
        return np.mean(np.abs((pred[mask] - actual[mask]) / actual[mask])) * 100

    mape_in = safe_mape(results_df["pred_inkomsten"].values, results_df["actual_inkomsten"].values)
    mape_uit = safe_mape(results_df["pred_uitgaven"].values, results_df["actual_uitgaven"].values)
    mape_netto = safe_mape(results_df["pred_netto"].values, results_df["actual_netto"].values)

    rmse_netto = np.sqrt(np.mean(results_df["error_netto"] ** 2))
    bias = results_df["error_netto"].mean()  # Positief = overschatting, negatief = onderschatting

    metrics = ForecastModelMetrics(
        mape_inkomsten=round(mape_in, 1),
        mape_uitgaven=round(mape_uit, 1),
        mape_netto=round(mape_netto, 1),
        rmse_netto=round(rmse_netto, 2),
        bias=round(bias, 2),
        n_test_weeks=len(results_df),
        model_type="ml_ensemble"
    )

    return metrics, results_df


def create_ml_forecast(
    banksaldo: pd.DataFrame,
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    historische_cashflow: pd.DataFrame,
    weeks: int = 13,
    weeks_history: int = 4,
    debiteur_delay_days: int = 0,
    crediteur_delay_days: int = 0,
    reference_date=None,
) -> Tuple[pd.DataFrame, int, ForecastModelMetrics]:
    """
    ML-gebaseerde cashflow forecast met automatische backtesting.

    Combineert:
    1. Geleerde patronen uit historische data (seizoen, trend, WMA)
    2. Bekende openstaande posten met vervaldatums
    3. Automatische weging gebaseerd op voorspelhorizon

    Returns:
        Tuple van (forecast DataFrame, forecast_start_idx, model metrics)
    """
    if reference_date is None:
        reference_date = datetime.now().date()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    # === STAP 1: Leer patroon uit historische data ===
    pattern = learn_weekly_pattern(historische_cashflow)

    # === STAP 2: Backtest het model ===
    metrics, backtest_results = backtest_forecast_model(
        historische_cashflow,
        test_weeks=8,
        forecast_horizon=4
    )

    all_rows = []

    # === STAP 3: REALISATIE - Historische weken ===
    if weeks_history > 0 and not historische_cashflow.empty:
        hist = historische_cashflow.copy()
        hist["week_start"] = pd.to_datetime(hist["week_start"]).dt.date
        hist = hist[hist["week_start"] < reference_date]
        hist = hist.sort_values("week_start", ascending=False).head(weeks_history)
        hist = hist.sort_values("week_start", ascending=True)

        for i, row in enumerate(hist.itertuples()):
            week_num = -(weeks_history - i)
            inkomsten = getattr(row, "inkomsten", 0)
            uitgaven = getattr(row, "uitgaven", 0)
            netto = inkomsten - uitgaven

            all_rows.append({
                "week_nummer": week_num,
                "week_label": f"Week {week_num}",
                "week_start": row.week_start,
                "week_eind": row.week_start + timedelta(days=7),
                "maand": row.week_start.month if hasattr(row.week_start, 'month') else 0,
                "inkomsten_debiteuren": round(inkomsten, 2),
                "uitgaven_crediteuren": round(uitgaven, 2),
                "netto_cashflow": round(netto, 2),
                "data_type": "Realisatie",
                "is_realisatie": True,
                "confidence": 1.0,
                "methode": "realisatie",
            })

    forecast_start_idx = len(all_rows)

    # === STAP 4: PROGNOSE - ML-gebaseerd ===
    week_starts = [reference_date + timedelta(weeks=i) for i in range(weeks + 1)]

    for i in range(weeks):
        week_start = week_starts[i]
        week_end = week_starts[i + 1]
        week_maand = week_start.month

        # Bekende inkomsten uit openstaande debiteuren
        bekende_in = 0.0
        if not debiteuren.empty and "vervaldatum" in debiteuren.columns:
            deb = debiteuren.copy()
            deb["vervaldatum"] = pd.to_datetime(deb["vervaldatum"]).dt.date
            deb["verwachte_betaling"] = deb["vervaldatum"].apply(
                lambda x: x + timedelta(days=debiteur_delay_days) if pd.notna(x) else None
            )
            mask = (deb["verwachte_betaling"] >= week_start) & (deb["verwachte_betaling"] < week_end)
            bekende_in = deb.loc[mask, "openstaand"].sum()

        # Bekende uitgaven uit openstaande crediteuren
        bekende_uit = 0.0
        if not crediteuren.empty and "vervaldatum" in crediteuren.columns:
            cred = crediteuren.copy()
            cred["vervaldatum"] = pd.to_datetime(cred["vervaldatum"]).dt.date
            cred["verwachte_betaling"] = cred["vervaldatum"].apply(
                lambda x: x + timedelta(days=crediteur_delay_days) if pd.notna(x) else None
            )
            mask = (cred["verwachte_betaling"] >= week_start) & (cred["verwachte_betaling"] < week_end)
            bekende_uit = cred.loc[mask, "openstaand"].sum()

        # ML voorspelling
        pred_in, pred_uit, confidence, methode = predict_week_ml(
            week_idx=i,
            week_maand=week_maand,
            pattern=pattern,
            bekende_in=bekende_in,
            bekende_uit=bekende_uit,
            weeks_ahead=i + 1
        )

        netto = pred_in - pred_uit

        all_rows.append({
            "week_nummer": i + 1,
            "week_label": f"Week {i + 1}",
            "week_start": week_start,
            "week_eind": week_end,
            "maand": week_maand,
            "inkomsten_debiteuren": round(pred_in, 2),
            "uitgaven_crediteuren": round(pred_uit, 2),
            "inkomsten_bekend": round(bekende_in, 2),
            "uitgaven_bekend": round(bekende_uit, 2),
            "netto_cashflow": round(netto, 2),
            "data_type": "Prognose",
            "is_realisatie": False,
            "confidence": round(confidence, 2),
            "methode": methode,
        })

    df = pd.DataFrame(all_rows)

    # Bereken cumulatief saldo
    start_balance = banksaldo["saldo"].sum() if not banksaldo.empty else 0
    df["cumulatief_saldo"] = start_balance + df["netto_cashflow"].cumsum()

    return df, forecast_start_idx, metrics


# =============================================================================
# FASE 3: DETERMINISTISCHE KOSTEN ISOLEREN (SALARISSEN + BELASTINGEN)
# =============================================================================

@dataclass
class DeterministicCost:
    """Een voorspelbare, terugkerende kost."""
    naam: str
    bedrag: float
    dag_van_maand: int  # 1-31, waarbij 31 = laatste dag
    type: str  # 'salaris', 'belasting', 'huur', 'verzekering', etc.
    maanden: list = None  # None = elke maand, of lijst zoals [1, 4, 7, 10] voor kwartaal

    def __post_init__(self):
        if self.maanden is None:
            self.maanden = list(range(1, 13))  # Elke maand


@dataclass
class DeterministicCostConfig:
    """Configuratie voor deterministische kosten."""
    salarissen: float = 0.0  # Totale maandelijkse salariskosten
    salaris_dag: int = 25  # Dag waarop salarissen worden betaald
    btw_kwartaal: float = 0.0  # Kwartaal BTW afdracht
    btw_dag: int = 28  # Dag waarop BTW wordt afgedragen (eind van kwartaalmaand)
    loonbelasting: float = 0.0  # Maandelijkse loonbelasting
    loonbelasting_dag: int = 28  # Dag waarop loonbelasting wordt afgedragen
    huur: float = 0.0  # Maandelijkse huur
    huur_dag: int = 1  # Dag waarop huur wordt betaald
    extra_kosten: list = None  # Lijst van DeterministicCost objecten

    def __post_init__(self):
        if self.extra_kosten is None:
            self.extra_kosten = []


def get_week_of_month(date) -> int:
    """
    Bepaal de week van de maand (1-5) voor een gegeven datum.

    Week 1: dag 1-7
    Week 2: dag 8-14
    Week 3: dag 15-21
    Week 4: dag 22-28
    Week 5: dag 29-31 (laatste dagen)
    """
    if isinstance(date, datetime):
        day = date.day
    else:
        day = date.day

    if day <= 7:
        return 1
    elif day <= 14:
        return 2
    elif day <= 21:
        return 3
    elif day <= 28:
        return 4
    else:
        return 5


def estimate_deterministic_costs_from_history(
    historische_cashflow: pd.DataFrame,
    min_months: int = 3
) -> DeterministicCostConfig:
    """
    Schat deterministische kosten uit historische cashflow data.

    Zoekt naar:
    - Grote uitgaven rond de 25e (salarissen)
    - Terugkerende bedragen op vaste dagen
    - Kwartaalpieken (BTW)

    Args:
        historische_cashflow: DataFrame met week_start, uitgaven kolommen
        min_months: Minimaal aantal maanden data nodig

    Returns:
        DeterministicCostConfig met geschatte waarden
    """
    if historische_cashflow.empty:
        return DeterministicCostConfig()

    df = historische_cashflow.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])

    # Check of we genoeg data hebben
    date_range = (df["week_start"].max() - df["week_start"].min()).days
    if date_range < min_months * 30:
        return DeterministicCostConfig()

    # Analyseer uitgaven per week-van-maand
    df["week_of_month"] = df["week_start"].apply(get_week_of_month)
    df["month"] = df["week_start"].dt.month

    week_analysis = df.groupby("week_of_month").agg({
        "uitgaven": ["mean", "std", "count"]
    }).round(2)

    # Week 4 (dag 22-28) typisch salarisweek
    if 4 in week_analysis.index:
        week4_mean = week_analysis.loc[4, ("uitgaven", "mean")]
        overall_mean = df["uitgaven"].mean()

        # Als week 4 significant hoger is, is dat waarschijnlijk salaris
        if week4_mean > overall_mean * 1.3:
            estimated_salaris = (week4_mean - overall_mean) * 4  # Maandbedrag schatten
        else:
            estimated_salaris = 0
    else:
        estimated_salaris = 0

    # Analyseer kwartaalpieken voor BTW
    quarterly_months = [3, 6, 9, 12]
    df["is_quarter_end"] = df["month"].isin(quarterly_months)

    quarter_end_avg = df[df["is_quarter_end"]]["uitgaven"].mean() if df["is_quarter_end"].any() else 0
    non_quarter_avg = df[~df["is_quarter_end"]]["uitgaven"].mean() if (~df["is_quarter_end"]).any() else 0

    if quarter_end_avg > non_quarter_avg * 1.2:
        estimated_btw = (quarter_end_avg - non_quarter_avg) * 4  # Kwartaalbedrag
    else:
        estimated_btw = 0

    return DeterministicCostConfig(
        salarissen=round(estimated_salaris, 2),
        salaris_dag=25,
        btw_kwartaal=round(estimated_btw, 2),
        btw_dag=28,
        loonbelasting=round(estimated_salaris * 0.35, 2),  # ~35% loonbelasting
        loonbelasting_dag=28,
    )


def calculate_deterministic_costs_for_week(
    week_start,
    week_end,
    config: DeterministicCostConfig
) -> Tuple[float, list]:
    """
    Bereken de deterministische kosten voor een specifieke week.

    Args:
        week_start: Start datum van de week
        week_end: Eind datum van de week
        config: DeterministicCostConfig met kostenparameters

    Returns:
        Tuple van (totaal_bedrag, lijst_van_kosten_details)
    """
    if isinstance(week_start, datetime):
        week_start = week_start.date()
    if isinstance(week_end, datetime):
        week_end = week_end.date()

    totaal = 0.0
    details = []

    # Check elke dag in de week
    current_date = week_start
    while current_date < week_end:
        dag = current_date.day
        maand = current_date.month

        # Salarissen (rond dag 25)
        if config.salarissen > 0 and dag == config.salaris_dag:
            totaal += config.salarissen
            details.append({
                "datum": current_date,
                "type": "salaris",
                "naam": "Salarissen",
                "bedrag": config.salarissen
            })

        # Loonbelasting (maandelijks)
        if config.loonbelasting > 0 and dag == config.loonbelasting_dag:
            totaal += config.loonbelasting
            details.append({
                "datum": current_date,
                "type": "belasting",
                "naam": "Loonbelasting",
                "bedrag": config.loonbelasting
            })

        # BTW (kwartaal: maart, juni, september, december)
        btw_maanden = [3, 6, 9, 12]
        if config.btw_kwartaal > 0 and dag == config.btw_dag and maand in btw_maanden:
            totaal += config.btw_kwartaal
            details.append({
                "datum": current_date,
                "type": "belasting",
                "naam": "BTW kwartaal",
                "bedrag": config.btw_kwartaal
            })

        # Huur (maandelijks op dag 1)
        if config.huur > 0 and dag == config.huur_dag:
            totaal += config.huur
            details.append({
                "datum": current_date,
                "type": "huur",
                "naam": "Huur",
                "bedrag": config.huur
            })

        # Extra kosten
        for extra in config.extra_kosten:
            if dag == extra.dag_van_maand and maand in extra.maanden:
                totaal += extra.bedrag
                details.append({
                    "datum": current_date,
                    "type": extra.type,
                    "naam": extra.naam,
                    "bedrag": extra.bedrag
                })

        current_date += timedelta(days=1)

    return totaal, details


# =============================================================================
# FASE 4: PROPHET INTEGRATIE (OPTIONEEL)
# =============================================================================

# Check of Prophet beschikbaar is
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False


def create_prophet_forecast(
    historische_cashflow: pd.DataFrame,
    weeks_ahead: int = 13,
    include_seasonality: bool = True
) -> Optional[pd.DataFrame]:
    """
    Maak een forecast met Facebook Prophet (indien beschikbaar).

    Prophet is goed in:
    - Automatische seizoensdetectie
    - Omgaan met ontbrekende data
    - Confidence intervals

    Args:
        historische_cashflow: DataFrame met week_start, inkomsten, uitgaven
        weeks_ahead: Hoeveel weken vooruit voorspellen
        include_seasonality: Of seizoenseffecten moeten worden meegenomen

    Returns:
        DataFrame met Prophet forecast of None als Prophet niet beschikbaar
    """
    if not PROPHET_AVAILABLE:
        return None

    if historische_cashflow.empty or len(historische_cashflow) < 12:
        return None

    df = historische_cashflow.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])

    results = {}

    # Forecast voor zowel inkomsten als uitgaven
    for column in ["inkomsten", "uitgaven"]:
        if column not in df.columns:
            continue

        # Prophet verwacht 'ds' en 'y' kolommen
        prophet_df = df[["week_start", column]].rename(
            columns={"week_start": "ds", column: "y"}
        )
        prophet_df = prophet_df.dropna()

        if len(prophet_df) < 12:
            continue

        # Configureer Prophet model
        model = Prophet(
            yearly_seasonality=include_seasonality,
            weekly_seasonality=False,  # We werken met wekelijkse data
            daily_seasonality=False,
            seasonality_mode="multiplicative"
        )

        # Voeg maandelijkse seizoenseffecten toe
        if include_seasonality:
            model.add_seasonality(
                name="monthly",
                period=30.5,
                fourier_order=5
            )

        # Train het model (suppress logging)
        import logging
        logging.getLogger('prophet').setLevel(logging.WARNING)
        model.fit(prophet_df)

        # Maak toekomstige datums
        future = model.make_future_dataframe(periods=weeks_ahead, freq="W")

        # Voorspel
        forecast = model.predict(future)

        # Bewaar alleen toekomstige voorspellingen
        future_mask = forecast["ds"] > prophet_df["ds"].max()
        results[column] = forecast[future_mask][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        results[column] = results[column].rename(columns={
            "yhat": f"{column}_prophet",
            "yhat_lower": f"{column}_lower",
            "yhat_upper": f"{column}_upper"
        })

    # Combineer resultaten
    if "inkomsten" in results and "uitgaven" in results:
        combined = results["inkomsten"].merge(
            results["uitgaven"],
            on="ds",
            how="outer"
        )
        combined = combined.rename(columns={"ds": "week_start"})
        return combined

    return None


def blend_with_prophet(
    base_forecast: pd.DataFrame,
    prophet_forecast: Optional[pd.DataFrame],
    prophet_weight: float = 0.3
) -> pd.DataFrame:
    """
    Combineer de basis forecast met Prophet voorspellingen.

    Args:
        base_forecast: DataFrame met basis forecast
        prophet_forecast: DataFrame met Prophet forecast (kan None zijn)
        prophet_weight: Gewicht voor Prophet (0-1)

    Returns:
        DataFrame met gecombineerde forecast
    """
    if prophet_forecast is None or prophet_forecast.empty:
        return base_forecast

    df = base_forecast.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])

    prophet_forecast = prophet_forecast.copy()
    prophet_forecast["week_start"] = pd.to_datetime(prophet_forecast["week_start"])

    # Merge op week_start (alleen datum, geen tijd)
    df["week_start_date"] = df["week_start"].dt.date
    prophet_forecast["week_start_date"] = prophet_forecast["week_start"].dt.date

    merged = df.merge(
        prophet_forecast[["week_start_date", "inkomsten_prophet", "uitgaven_prophet"]],
        on="week_start_date",
        how="left"
    )

    # Blend alleen voor prognose rijen (niet realisatie)
    prognose_mask = ~merged["is_realisatie"]

    if "inkomsten_prophet" in merged.columns:
        merged.loc[prognose_mask, "inkomsten_debiteuren"] = (
            (1 - prophet_weight) * merged.loc[prognose_mask, "inkomsten_debiteuren"] +
            prophet_weight * merged.loc[prognose_mask, "inkomsten_prophet"].fillna(
                merged.loc[prognose_mask, "inkomsten_debiteuren"]
            )
        )

    if "uitgaven_prophet" in merged.columns:
        merged.loc[prognose_mask, "uitgaven_crediteuren"] = (
            (1 - prophet_weight) * merged.loc[prognose_mask, "uitgaven_crediteuren"] +
            prophet_weight * merged.loc[prognose_mask, "uitgaven_prophet"].fillna(
                merged.loc[prognose_mask, "uitgaven_crediteuren"]
            )
        )

    # Herbereken netto en cumulatief
    merged["netto_cashflow"] = merged["inkomsten_debiteuren"] - merged["uitgaven_crediteuren"]

    # Update methode beschrijving
    merged.loc[prognose_mask, "methode"] = merged.loc[prognose_mask, "methode"].apply(
        lambda x: f"{x} + Prophet({prophet_weight*100:.0f}%)" if pd.notna(x) else f"Prophet({prophet_weight*100:.0f}%)"
    )

    # Verwijder tijdelijke kolommen
    cols_to_drop = ["week_start_date", "inkomsten_prophet", "uitgaven_prophet",
                    "inkomsten_lower", "inkomsten_upper", "uitgaven_lower", "uitgaven_upper"]
    merged = merged.drop(columns=[c for c in cols_to_drop if c in merged.columns], errors="ignore")

    return merged


# =============================================================================
# FASE 5: WEEK-VAN-MAAND FEATURE VOOR MAANDPATRONEN
# =============================================================================

def learn_week_of_month_pattern(
    historische_cashflow: pd.DataFrame,
    min_samples: int = 3
) -> Dict[int, Dict[str, float]]:
    """
    Leer het cashflow patroon per week-van-de-maand.

    Week 1 (dag 1-7): Typisch rustig, begin van maand
    Week 2 (dag 8-14): Normale activiteit
    Week 3 (dag 15-21): Normale activiteit
    Week 4 (dag 22-28): Vaak salarissen, hogere uitgaven
    Week 5 (dag 29-31): Maandeinde, mogelijk BTW/belastingen

    Returns:
        Dict per week_of_month met gemiddelden en multipliers
    """
    if historische_cashflow.empty:
        return {}

    df = historische_cashflow.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["week_of_month"] = df["week_start"].apply(get_week_of_month)

    patterns = {}
    overall_in = df["inkomsten"].mean() if "inkomsten" in df.columns else 0
    overall_uit = df["uitgaven"].mean() if "uitgaven" in df.columns else 0

    for wom in range(1, 6):
        week_data = df[df["week_of_month"] == wom]

        if len(week_data) < min_samples:
            # Niet genoeg data, gebruik overall gemiddelde
            patterns[wom] = {
                "inkomsten_mean": overall_in,
                "uitgaven_mean": overall_uit,
                "inkomsten_multiplier": 1.0,
                "uitgaven_multiplier": 1.0,
                "sample_count": len(week_data),
                "reliable": False
            }
        else:
            in_mean = week_data["inkomsten"].mean() if "inkomsten" in week_data.columns else 0
            uit_mean = week_data["uitgaven"].mean() if "uitgaven" in week_data.columns else 0

            patterns[wom] = {
                "inkomsten_mean": round(in_mean, 2),
                "uitgaven_mean": round(uit_mean, 2),
                "inkomsten_multiplier": round(in_mean / overall_in, 3) if overall_in > 0 else 1.0,
                "uitgaven_multiplier": round(uit_mean / overall_uit, 3) if overall_uit > 0 else 1.0,
                "sample_count": len(week_data),
                "reliable": True
            }

    return patterns


def apply_week_of_month_adjustment(
    base_inkomsten: float,
    base_uitgaven: float,
    week_start,
    wom_pattern: Dict[int, Dict[str, float]],
    adjustment_strength: float = 0.5
) -> Tuple[float, float]:
    """
    Pas week-van-maand correctie toe op de basisvoorspelling.

    Args:
        base_inkomsten: Basisvoorspelling inkomsten
        base_uitgaven: Basisvoorspelling uitgaven
        week_start: Start datum van de week
        wom_pattern: Geleerde week-of-month patronen
        adjustment_strength: Hoe sterk de correctie (0-1)

    Returns:
        Tuple van (gecorrigeerde_inkomsten, gecorrigeerde_uitgaven)
    """
    if not wom_pattern:
        return base_inkomsten, base_uitgaven

    wom = get_week_of_month(week_start)

    if wom not in wom_pattern:
        return base_inkomsten, base_uitgaven

    pattern = wom_pattern[wom]

    if not pattern.get("reliable", False):
        return base_inkomsten, base_uitgaven

    # Pas multiplier toe met gekozen sterkte
    in_mult = pattern["inkomsten_multiplier"]
    uit_mult = pattern["uitgaven_multiplier"]

    # Blend met adjustment_strength
    adjusted_in = base_inkomsten * (1 + adjustment_strength * (in_mult - 1))
    adjusted_uit = base_uitgaven * (1 + adjustment_strength * (uit_mult - 1))

    return round(adjusted_in, 2), round(adjusted_uit, 2)


# =============================================================================
# GECOMBINEERDE FORECAST MET ALLE FASEN
# =============================================================================

# =============================================================================
# NIEUW 4-LAGEN MODEL: OMZET-FIRST APPROACH
# =============================================================================
#
# ARCHITECTUUR:
# Laag 1 - Korte Termijn (Week 0-6):   Openstaande facturen met Adjusted Due Date
# Laag 2 - Middellange Termijn (4-10): Orderboek/OHW → verwachte facturen → cash
# Laag 3 - Lange Termijn (Week 10+):   Ghost Invoices (omzet forecast → +DSO → cash)
# Laag 4 - Overlay (altijd):           Deterministische kosten (salarissen, belastingen)
#
# CRUCIALE INSIGHT:
# - Oude aanpak: Voorspel CASHFLOW uit historische cashflow → faalt (cashflow is grillig)
# - Nieuwe aanpak: Voorspel OMZET (stabieler) → time-shift met DSO → cash
# =============================================================================

@dataclass
class GhostInvoice:
    """Een fictieve toekomstige factuur gebaseerd op omzetvoorspelling."""
    week_verwacht: int  # Week waarin omzet verwacht wordt
    week_cash: int      # Week waarin cash binnenkomt (na DSO)
    bedrag: float       # Verwacht bedrag
    bron: str           # 'layer1_ar', 'layer2_orderbook', 'layer3_forecast'
    confidence: float   # Betrouwbaarheid 0-1


@dataclass
class LayeredForecastResult:
    """Resultaat van de 4-lagen forecast."""
    weekly_cashflow: pd.DataFrame
    ghost_invoices: list
    layer_contributions: Dict[str, pd.DataFrame]
    portfolio_dso: float
    forecast_metrics: Dict[str, float]


def forecast_revenue_holt_winters(
    historische_omzet: pd.DataFrame,
    weeks_ahead: int = 26,
    seasonal_periods: int = 52,  # Jaarlijkse seizoenseffecten
) -> pd.DataFrame:
    """
    Voorspel OMZET (niet cashflow!) met Holt-Winters Exponential Smoothing.

    Dit is de kern van de nieuwe aanpak: we voorspellen eerst stabielere omzet,
    daarna converteren we naar cash met DSO-lag.

    Args:
        historische_omzet: DataFrame met kolommen 'week_start', 'omzet'
        weeks_ahead: Aantal weken vooruit voorspellen
        seasonal_periods: Periode voor seizoenseffecten (52 = jaar)

    Returns:
        DataFrame met week_start, omzet_forecast, omzet_lower, omzet_upper
    """
    if historische_omzet.empty or len(historische_omzet) < 12:
        return pd.DataFrame()

    df = historische_omzet.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.sort_values("week_start")

    # Gebruik statsmodels Holt-Winters als beschikbaar
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        # Bereid data voor
        series = df.set_index("week_start")["omzet"].asfreq("W-MON")
        series = series.fillna(method="ffill").fillna(0)

        # Bepaal of we genoeg data hebben voor seizoenseffecten
        if len(series) >= seasonal_periods * 2:
            model = ExponentialSmoothing(
                series,
                seasonal_periods=min(seasonal_periods, len(series) // 2),
                trend="add",
                seasonal="add",
                damped_trend=True,
            )
        else:
            # Niet genoeg data voor seizoenseffecten, gebruik alleen trend
            model = ExponentialSmoothing(
                series,
                trend="add",
                seasonal=None,
                damped_trend=True,
            )

        fit = model.fit(optimized=True)

        # Voorspel
        forecast = fit.forecast(weeks_ahead)

        # Confidence intervals (geschat via residuals)
        residuals = fit.resid
        std_resid = residuals.std() if len(residuals) > 0 else series.std()

        # Maak result DataFrame
        last_date = series.index[-1]
        future_dates = pd.date_range(
            start=last_date + timedelta(weeks=1),
            periods=weeks_ahead,
            freq="W-MON"
        )

        result = pd.DataFrame({
            "week_start": future_dates,
            "omzet_forecast": forecast.values,
            "omzet_lower": forecast.values - 1.96 * std_resid,
            "omzet_upper": forecast.values + 1.96 * std_resid,
        })

        # Zorg dat forecast niet negatief is
        result["omzet_forecast"] = result["omzet_forecast"].clip(lower=0)
        result["omzet_lower"] = result["omzet_lower"].clip(lower=0)

        return result

    except ImportError:
        # Fallback: simpele weighted moving average met trend
        return _forecast_revenue_fallback(df, weeks_ahead)


def _forecast_revenue_fallback(
    historische_omzet: pd.DataFrame,
    weeks_ahead: int = 26
) -> pd.DataFrame:
    """
    Fallback omzet forecast zonder statsmodels.
    Gebruikt decomposition: trend + seizoen + noise.
    """
    df = historische_omzet.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.sort_values("week_start")

    if len(df) < 8:
        return pd.DataFrame()

    # Bereken trend via linear regression
    df["week_idx"] = range(len(df))
    x = df["week_idx"].values
    y = df["omzet"].values

    # Linear trend
    slope, intercept = np.polyfit(x, y, 1)

    # Bereken seizoensindex per week-van-maand
    df["week_of_month"] = df["week_start"].dt.day.apply(
        lambda d: min(5, (d - 1) // 7 + 1)
    )
    seasonal_factors = df.groupby("week_of_month")["omzet"].mean()
    overall_mean = df["omzet"].mean()
    seasonal_index = (seasonal_factors / overall_mean).to_dict() if overall_mean > 0 else {}

    # Maak forecast
    last_date = df["week_start"].max()
    last_idx = df["week_idx"].max()

    results = []
    for i in range(1, weeks_ahead + 1):
        future_date = last_date + timedelta(weeks=i)
        future_idx = last_idx + i

        # Trend component
        trend_value = slope * future_idx + intercept

        # Seasonal component
        wom = min(5, (future_date.day - 1) // 7 + 1)
        seasonal_mult = seasonal_index.get(wom, 1.0)

        # Combined forecast
        forecast = max(0, trend_value * seasonal_mult)

        # Simple confidence interval
        std = df["omzet"].std()

        results.append({
            "week_start": future_date,
            "omzet_forecast": round(forecast, 2),
            "omzet_lower": max(0, round(forecast - 1.5 * std, 2)),
            "omzet_upper": round(forecast + 1.5 * std, 2),
        })

    return pd.DataFrame(results)


def calculate_portfolio_dso(
    betaalgedrag: pd.DataFrame,
    debiteuren: pd.DataFrame = None
) -> float:
    """
    Bereken de gewogen gemiddelde DSO voor de hele portfolio.

    Dit wordt gebruikt om Ghost Invoices te time-shiften:
    Week met voorspelde omzet → +DSO dagen → Week met verwachte cash

    Args:
        betaalgedrag: DataFrame met DSO per debiteur
        debiteuren: Optioneel - voor weging naar openstaand bedrag

    Returns:
        Gewogen gemiddelde DSO in dagen
    """
    if betaalgedrag.empty:
        return 35.0  # Default DSO voor installatiebedrijven

    if debiteuren is not None and not debiteuren.empty:
        # Weeg DSO naar openstaand bedrag per debiteur
        merged = betaalgedrag.merge(
            debiteuren.groupby("debiteur_code")["openstaand"].sum().reset_index(),
            on="debiteur_code",
            how="left"
        )
        merged["openstaand"] = merged["openstaand"].fillna(0)

        total_openstaand = merged["openstaand"].sum()
        if total_openstaand > 0:
            weighted_dso = (
                merged["gem_dagen_tot_betaling"] * merged["openstaand"]
            ).sum() / total_openstaand
            return round(weighted_dso, 1)

    # Simpel gemiddelde als fallback
    return round(betaalgedrag["gem_dagen_tot_betaling"].mean(), 1)


def create_ghost_invoices(
    omzet_forecast: pd.DataFrame,
    portfolio_dso: float,
    reference_date,
) -> list:
    """
    Converteer omzet forecast naar Ghost Invoices.

    CRUCIALE STAP: Time-shift van omzet naar cash.

    Voorbeeld:
    - Week 12: Voorspelde omzet €100k
    - DSO = 35 dagen
    - Week 17: Verwachte cash-instroom €100k

    Args:
        omzet_forecast: DataFrame met week_start, omzet_forecast
        portfolio_dso: Gemiddelde DSO in dagen
        reference_date: Referentiedatum

    Returns:
        Lijst van GhostInvoice objecten
    """
    if omzet_forecast.empty:
        return []

    ghost_invoices = []

    if isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    for _, row in omzet_forecast.iterrows():
        week_start = row["week_start"]
        if isinstance(week_start, pd.Timestamp):
            week_start = week_start.date()

        # Bereken welke week dit is vanaf reference_date
        days_from_ref = (week_start - reference_date).days
        week_verwacht = days_from_ref // 7

        # Bereken wanneer cash binnenkomt: +DSO dagen
        cash_date = week_start + timedelta(days=int(portfolio_dso))
        days_to_cash = (cash_date - reference_date).days
        week_cash = days_to_cash // 7

        # Confidence aflopend met horizon
        base_confidence = 0.7 - (week_verwacht * 0.02)
        confidence = max(0.2, min(0.8, base_confidence))

        ghost_invoices.append(GhostInvoice(
            week_verwacht=week_verwacht,
            week_cash=week_cash,
            bedrag=row["omzet_forecast"],
            bron="layer3_forecast",
            confidence=confidence,
        ))

    return ghost_invoices


def create_layered_cashflow_forecast(
    banksaldo: pd.DataFrame,
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    historische_omzet: pd.DataFrame,
    betaalgedrag_debiteuren: pd.DataFrame,
    orderboek: pd.DataFrame = None,
    historische_uitgaven: pd.DataFrame = None,
    weeks: int = 26,
    weeks_history: int = 4,
    reference_date=None,
    standaard_betaaltermijn: int = 30,
) -> Tuple[pd.DataFrame, int, Dict]:
    """
    NIEUW 4-LAGEN CASHFLOW FORECAST MODEL.

    Dit model lost het fundamentele probleem op: in plaats van cashflow direct
    te voorspellen (grillig), voorspellen we eerst OMZET (stabieler) en
    converteren dan naar cash met DSO-lag.

    LAGEN:
    1. Korte Termijn (Week 0-6):   Openstaande AR/AP met Adjusted Due Date
    2. Middellange Termijn (4-10): Orderboek → verwachte facturen → cash
    3. Lange Termijn (Week 10+):   Ghost Invoices (omzet forecast → +DSO → cash)
    4. Overlay (altijd):           Deterministische kosten (vast en zeker)

    Args:
        banksaldo: Huidige banksaldi
        debiteuren: Openstaande debiteuren
        crediteuren: Openstaande crediteuren
        historische_omzet: Historische OMZET (niet cashflow!) per week
        betaalgedrag_debiteuren: DSO data per debiteur
        orderboek: Optioneel - openstaande orders/OHW
        historische_uitgaven: Optioneel - voor uitgaven forecast
        weeks: Aantal weken forecast
        weeks_history: Aantal weken realisatie
        reference_date: Referentiedatum
        standaard_betaaltermijn: Standaard betaaltermijn

    Returns:
        Tuple van (forecast DataFrame, forecast_start_idx, metadata dict)
    """
    if reference_date is None:
        reference_date = datetime.now().date()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    # =========================================================================
    # STAP 0: Bereken portfolio DSO en DSO adjustments
    # =========================================================================
    portfolio_dso = calculate_portfolio_dso(betaalgedrag_debiteuren, debiteuren)

    dso_adjustments = calculate_dso_adjustment(
        betaalgedrag_debiteuren,
        standaard_betaaltermijn=standaard_betaaltermijn
    )

    # Adjust debiteuren met DSO per klant
    debiteuren_adjusted = adjust_receivables_due_dates(debiteuren, dso_adjustments)

    # =========================================================================
    # STAP 1: Initialiseer weekstructuur
    # =========================================================================
    all_rows = []
    week_starts = [reference_date + timedelta(weeks=i) for i in range(-weeks_history, weeks + 1)]

    # Layer tracking per week
    layer_data = {
        "layer1_ar": [0.0] * (weeks_history + weeks),
        "layer1_ap": [0.0] * (weeks_history + weeks),
        "layer2_orders": [0.0] * (weeks_history + weeks),
        "layer3_ghost": [0.0] * (weeks_history + weeks),
        "layer4_deterministic": [0.0] * (weeks_history + weeks),
    }

    # =========================================================================
    # LAAG 1: KORTE TERMIJN - Openstaande Posten (Week 0-6)
    # =========================================================================
    # Dit is de meest betrouwbare laag: we weten precies welke facturen openstaan

    if not debiteuren_adjusted.empty and "verwachte_betaling" in debiteuren_adjusted.columns:
        for idx, deb_row in debiteuren_adjusted.iterrows():
            verwachte_datum = deb_row["verwachte_betaling"]
            bedrag = deb_row["openstaand"]

            if pd.isna(verwachte_datum) or pd.isna(bedrag):
                continue

            # Bereken in welke week deze betaling valt
            days_from_ref = (verwachte_datum - reference_date).days
            week_idx = days_from_ref // 7 + weeks_history

            if 0 <= week_idx < len(layer_data["layer1_ar"]):
                layer_data["layer1_ar"][week_idx] += bedrag

    # Crediteuren (uitgaven)
    if not crediteuren.empty and "vervaldatum" in crediteuren.columns:
        cred = crediteuren.copy()
        cred["vervaldatum"] = pd.to_datetime(cred["vervaldatum"]).dt.date

        for idx, cred_row in cred.iterrows():
            vervaldatum = cred_row["vervaldatum"]
            bedrag = cred_row["openstaand"]

            if pd.isna(vervaldatum) or pd.isna(bedrag):
                continue

            days_from_ref = (vervaldatum - reference_date).days
            week_idx = days_from_ref // 7 + weeks_history

            if 0 <= week_idx < len(layer_data["layer1_ap"]):
                layer_data["layer1_ap"][week_idx] += bedrag

    # =========================================================================
    # LAAG 2: MIDDELLANGE TERMIJN - Orderboek/OHW (Week 4-10)
    # =========================================================================
    # Orders die nog niet gefactureerd zijn, maar waarvan we weten dat ze komen

    if orderboek is not None and not orderboek.empty:
        # Verwacht: orderboek met kolommen: leverdatum, bedrag, klant
        for idx, order_row in orderboek.iterrows():
            leverdatum = order_row.get("leverdatum")
            bedrag = order_row.get("bedrag", 0)

            if pd.isna(leverdatum) or pd.isna(bedrag):
                continue

            if isinstance(leverdatum, str):
                leverdatum = pd.to_datetime(leverdatum).date()

            # Facturatievertraging (typisch 7 dagen na levering)
            facturatie_vertraging = 7
            factuur_datum = leverdatum + timedelta(days=facturatie_vertraging)

            # Cash datum = factuur + DSO
            cash_datum = factuur_datum + timedelta(days=int(portfolio_dso))

            days_from_ref = (cash_datum - reference_date).days
            week_idx = days_from_ref // 7 + weeks_history

            if 0 <= week_idx < len(layer_data["layer2_orders"]):
                layer_data["layer2_orders"][week_idx] += bedrag

    # =========================================================================
    # LAAG 3: LANGE TERMIJN - Ghost Invoices (Week 10+)
    # =========================================================================
    # Dit is waar de magie gebeurt: voorspel OMZET, shift naar CASH

    if not historische_omzet.empty:
        # Voorspel omzet met Holt-Winters
        omzet_forecast = forecast_revenue_holt_winters(
            historische_omzet,
            weeks_ahead=weeks + 10  # Extra weken voor DSO buffer
        )

        if not omzet_forecast.empty:
            # Converteer naar Ghost Invoices
            ghost_invoices = create_ghost_invoices(
                omzet_forecast,
                portfolio_dso,
                reference_date
            )

            # Voeg Ghost Invoices toe aan Layer 3
            for ghost in ghost_invoices:
                week_idx = ghost.week_cash + weeks_history

                # Ghost invoices alleen waar Layer 1+2 niet dominant zijn
                # Dit voorkomt dubbeltelling
                if 0 <= week_idx < len(layer_data["layer3_ghost"]):
                    # Check of deze week al gevuld is door Layer 1 of 2
                    layer1_total = layer_data["layer1_ar"][week_idx]
                    layer2_total = layer_data["layer2_orders"][week_idx]

                    # Fade in: Layer 3 krijgt meer gewicht naarmate 1+2 afnemen
                    if layer1_total + layer2_total < ghost.bedrag * 0.3:
                        # Bijna geen Layer 1+2 data, gebruik Layer 3 volledig
                        layer_data["layer3_ghost"][week_idx] += ghost.bedrag * ghost.confidence
                    elif layer1_total + layer2_total < ghost.bedrag * 0.7:
                        # Gedeeltelijk Layer 1+2, vul aan met Layer 3
                        gap = ghost.bedrag - (layer1_total + layer2_total)
                        layer_data["layer3_ghost"][week_idx] += max(0, gap * ghost.confidence)
                    # Anders: Layer 1+2 is voldoende, geen Layer 3 nodig

    # =========================================================================
    # LAAG 4: UITGAVEN FORECAST (historisch gemiddelde)
    # =========================================================================
    # Net als Ghost Invoices voor inkomsten, gebruiken we historisch gemiddelde
    # voor uitgaven wanneer er geen openstaande crediteuren zijn.

    # Bereken gemiddelde wekelijkse uitgaven uit historie
    avg_weekly_expenses = 0.0
    if historische_uitgaven is not None and not historische_uitgaven.empty:
        if "uitgaven" in historische_uitgaven.columns:
            avg_weekly_expenses = historische_uitgaven["uitgaven"].mean()

    # Vul Layer 4 met historisch gemiddelde waar Layer 1 (AP) leeg is
    for week_idx in range(len(layer_data["layer4_deterministic"])):
        # Alleen voor forecast weken (niet historie)
        if week_idx >= weeks_history:
            layer1_ap = layer_data["layer1_ap"][week_idx]

            # Als er weinig/geen crediteuren zijn, gebruik historisch gemiddelde
            if layer1_ap < avg_weekly_expenses * 0.3:
                # Vul het gat aan met historisch gemiddelde
                gap = avg_weekly_expenses - layer1_ap
                # Confidence aflopend met de tijd (verder = minder zeker)
                weeks_ahead = week_idx - weeks_history
                confidence = max(0.5, 0.9 - weeks_ahead * 0.02)
                layer_data["layer4_deterministic"][week_idx] = gap * confidence

    # =========================================================================
    # COMBINEER ALLE LAGEN
    # =========================================================================
    for i in range(weeks_history + weeks):
        week_idx = i - weeks_history
        week_start = reference_date + timedelta(weeks=week_idx)
        week_end = week_start + timedelta(days=7)
        is_realisatie = week_idx < 0

        # Inkomsten: Layer 1 (AR) + Layer 2 (Orders) + Layer 3 (Ghost)
        inkomsten_l1 = layer_data["layer1_ar"][i]
        inkomsten_l2 = layer_data["layer2_orders"][i]
        inkomsten_l3 = layer_data["layer3_ghost"][i]
        totaal_inkomsten = inkomsten_l1 + inkomsten_l2 + inkomsten_l3

        # Uitgaven: Layer 1 (AP) + Layer 4 (Deterministic)
        uitgaven_l1 = layer_data["layer1_ap"][i]
        uitgaven_l4 = layer_data["layer4_deterministic"][i]
        totaal_uitgaven = uitgaven_l1 + uitgaven_l4

        # Netto
        netto = totaal_inkomsten - totaal_uitgaven

        # Confidence: hoger als meer uit Layer 1+2, lager als meer uit Layer 3
        if totaal_inkomsten > 0:
            confidence = (inkomsten_l1 + inkomsten_l2) / totaal_inkomsten
            confidence = max(0.3, min(0.95, confidence * 0.9 + 0.1))
        else:
            confidence = 0.5

        # Data type en methode
        if is_realisatie:
            data_type = "Realisatie"
            methode = "realisatie"
            confidence = 1.0
        else:
            data_type = "Prognose"
            # Beschrijf welke lagen actief zijn
            active_layers = []
            if inkomsten_l1 > 0:
                active_layers.append(f"AR({inkomsten_l1/totaal_inkomsten*100:.0f}%)" if totaal_inkomsten > 0 else "AR")
            if inkomsten_l2 > 0:
                active_layers.append(f"Orders({inkomsten_l2/totaal_inkomsten*100:.0f}%)" if totaal_inkomsten > 0 else "Orders")
            if inkomsten_l3 > 0:
                active_layers.append(f"Ghost({inkomsten_l3/totaal_inkomsten*100:.0f}%)" if totaal_inkomsten > 0 else "Ghost")
            methode = " + ".join(active_layers) if active_layers else "geen data"

        all_rows.append({
            "week_nummer": week_idx + 1 if week_idx >= 0 else week_idx,
            "week_label": f"Week {week_idx + 1}" if week_idx >= 0 else f"Week {week_idx}",
            "week_start": week_start,
            "week_eind": week_end,
            "maand": week_start.month,
            "inkomsten_debiteuren": round(totaal_inkomsten, 2),
            "inkomsten_layer1": round(inkomsten_l1, 2),
            "inkomsten_layer2": round(inkomsten_l2, 2),
            "inkomsten_layer3": round(inkomsten_l3, 2),
            "uitgaven_crediteuren": round(totaal_uitgaven, 2),
            "uitgaven_layer1": round(uitgaven_l1, 2),
            "uitgaven_layer4": round(uitgaven_l4, 2),
            "netto_cashflow": round(netto, 2),
            "data_type": data_type,
            "is_realisatie": is_realisatie,
            "confidence": round(confidence, 2),
            "methode": methode,
        })

    df = pd.DataFrame(all_rows)

    # Bereken cumulatief saldo
    start_balance = banksaldo["saldo"].sum() if not banksaldo.empty else 0
    df["cumulatief_saldo"] = start_balance + df["netto_cashflow"].cumsum()

    # Metadata
    metadata = {
        "model": "layered_4_phase",
        "portfolio_dso": portfolio_dso,
        "dso_adjustments": dso_adjustments,
        "n_debiteuren_met_dso": len([k for k in dso_adjustments.keys() if k != "_fallback"]),
        "layers_used": ["layer1_ar", "layer1_ap", "layer3_ghost", "layer4_deterministic"],
        "avg_weekly_expenses": avg_weekly_expenses,
    }

    forecast_start_idx = weeks_history

    return df, forecast_start_idx, metadata


# =============================================================================
# BACKTESTING FRAMEWORK MET KLANTSPECIFIEKE INZICHTEN
# =============================================================================

@dataclass
class CustomerInsight:
    """Een inzicht over het gedrag van een specifieke klant."""
    categorie: str      # 'betaalgedrag', 'seizoen', 'trend', 'volatiliteit', 'risico'
    titel: str          # Korte titel
    beschrijving: str   # Beschrijvende tekst
    impact: str         # 'positief', 'neutraal', 'negatief'
    confidence: float   # Betrouwbaarheid van dit inzicht 0-1
    data_support: Dict  # Onderliggende data die dit inzicht ondersteunt


@dataclass
class BacktestResult:
    """Resultaat van walk-forward backtesting."""
    # Accuracy metrics
    mape_per_horizon: Dict[int, float]  # MAPE per week vooruit
    overall_mape: float
    bias: float  # Positief = overschatting, negatief = onderschatting
    rmse: float

    # Layer-specifieke metrics
    layer1_accuracy: float  # Hoe goed presteerde Layer 1 (AR)?
    layer3_accuracy: float  # Hoe goed presteerden Ghost Invoices?

    # Model learnings
    learnings: list  # Lijst van strings met geleerde inzichten

    # Test details
    n_cutoff_dates: int
    test_period_start: str
    test_period_end: str

    # Per-cutoff resultaten (voor visualisatie)
    detailed_results: pd.DataFrame


@dataclass
class CustomerProfile:
    """Compleet profiel van een klant gebaseerd op data-analyse."""
    # Identificatie
    klant_code: str
    analyse_datum: str

    # Betaalgedrag
    portfolio_dso: float
    dso_trend: str  # 'verbeterend', 'stabiel', 'verslechterend'
    betaal_discipline: str  # 'goed', 'gemiddeld', 'slecht'

    # Seizoenspatronen
    seizoen_sterkte: float  # 0-1, hoe sterk zijn seizoenseffecten?
    piek_maanden: list  # Maanden met boven-gemiddelde omzet
    dal_maanden: list  # Maanden met onder-gemiddelde omzet

    # Volatiliteit en risico
    omzet_volatiliteit: float  # Standaarddeviatie / gemiddelde
    cashflow_voorspelbaarheid: str  # 'hoog', 'gemiddeld', 'laag'

    # Inzichten
    inzichten: list  # Lijst van CustomerInsight objecten

    # Backtesting resultaten
    backtest_result: Optional[BacktestResult]


def analyze_customer_payment_behavior(
    betaalgedrag: pd.DataFrame,
    historische_facturen: pd.DataFrame = None
) -> list:
    """
    Analyseer betaalgedrag en genereer klantspecifieke inzichten.

    Returns:
        Lijst van CustomerInsight objecten
    """
    inzichten = []

    if betaalgedrag.empty:
        return inzichten

    # === INZICHT 1: Portfolio DSO ===
    avg_dso = betaalgedrag["gem_dagen_tot_betaling"].mean()
    dso_std = betaalgedrag["gem_dagen_tot_betaling"].std()

    if avg_dso <= 30:
        inzichten.append(CustomerInsight(
            categorie="betaalgedrag",
            titel="Snelle betalers",
            beschrijving=f"Gemiddelde betaaltijd is {avg_dso:.0f} dagen. "
                        f"Dit is beter dan de standaard betaaltermijn van 30 dagen.",
            impact="positief",
            confidence=0.9 if dso_std < 10 else 0.7,
            data_support={"avg_dso": avg_dso, "std_dso": dso_std}
        ))
    elif avg_dso <= 45:
        inzichten.append(CustomerInsight(
            categorie="betaalgedrag",
            titel="Gemiddeld betaalgedrag",
            beschrijving=f"Gemiddelde betaaltijd is {avg_dso:.0f} dagen. "
                        f"Dit is iets boven de standaard termijn, maar acceptabel.",
            impact="neutraal",
            confidence=0.9 if dso_std < 15 else 0.7,
            data_support={"avg_dso": avg_dso, "std_dso": dso_std}
        ))
    else:
        inzichten.append(CustomerInsight(
            categorie="betaalgedrag",
            titel="Trage betalers",
            beschrijving=f"Gemiddelde betaaltijd is {avg_dso:.0f} dagen. "
                        f"Dit is significant boven de standaard termijn van 30 dagen. "
                        f"Overweeg actief debiteurenbeheer.",
            impact="negatief",
            confidence=0.9,
            data_support={"avg_dso": avg_dso, "std_dso": dso_std}
        ))

    # === INZICHT 2: Betaalgedrag spreiding ===
    if dso_std > 20:
        # Identificeer probleemklanten
        slow_payers = betaalgedrag[betaalgedrag["gem_dagen_tot_betaling"] > avg_dso + dso_std]
        if len(slow_payers) > 0:
            inzichten.append(CustomerInsight(
                categorie="risico",
                titel="Inconsistent betaalgedrag",
                beschrijving=f"Er is grote variatie in betaalgedrag (σ = {dso_std:.0f} dagen). "
                            f"{len(slow_payers)} debiteuren betalen significant later dan gemiddeld.",
                impact="negatief",
                confidence=0.85,
                data_support={
                    "std_dso": dso_std,
                    "n_slow_payers": len(slow_payers),
                    "slow_payer_codes": slow_payers["debiteur_code"].tolist()[:5]
                }
            ))

    # === INZICHT 3: Top betalers vs slechtste betalers ===
    top_5_fast = betaalgedrag.nsmallest(5, "gem_dagen_tot_betaling")
    top_5_slow = betaalgedrag.nlargest(5, "gem_dagen_tot_betaling")

    if len(top_5_fast) >= 3:
        fast_avg = top_5_fast["gem_dagen_tot_betaling"].mean()
        slow_avg = top_5_slow["gem_dagen_tot_betaling"].mean()

        if slow_avg - fast_avg > 30:
            inzichten.append(CustomerInsight(
                categorie="betaalgedrag",
                titel="Grote spreiding in betaalgedrag",
                beschrijving=f"Beste betalers betalen in {fast_avg:.0f} dagen, "
                            f"slechtste in {slow_avg:.0f} dagen. "
                            f"Verschil van {slow_avg - fast_avg:.0f} dagen.",
                impact="neutraal",
                confidence=0.8,
                data_support={
                    "fast_avg": fast_avg,
                    "slow_avg": slow_avg,
                    "fast_payers": top_5_fast["debiteur_code"].tolist(),
                    "slow_payers": top_5_slow["debiteur_code"].tolist()
                }
            ))

    return inzichten


def analyze_seasonality(
    historische_omzet: pd.DataFrame
) -> list:
    """
    Analyseer seizoenspatronen en genereer inzichten.

    Returns:
        Lijst van CustomerInsight objecten
    """
    inzichten = []

    if historische_omzet.empty or len(historische_omzet) < 52:
        return inzichten

    df = historische_omzet.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["maand"] = df["week_start"].dt.month

    # Bereken gemiddelde omzet per maand
    monthly_avg = df.groupby("maand")["omzet"].mean()
    overall_avg = df["omzet"].mean()

    if overall_avg == 0:
        return inzichten

    # Bereken seizoensindex per maand
    seasonal_index = monthly_avg / overall_avg

    # Identificeer piek- en dalmaanden
    piek_maanden = seasonal_index[seasonal_index > 1.15].index.tolist()
    dal_maanden = seasonal_index[seasonal_index < 0.85].index.tolist()

    maand_namen = {
        1: "januari", 2: "februari", 3: "maart", 4: "april",
        5: "mei", 6: "juni", 7: "juli", 8: "augustus",
        9: "september", 10: "oktober", 11: "november", 12: "december"
    }

    # === INZICHT: Seizoenspatroon ===
    if piek_maanden or dal_maanden:
        piek_str = ", ".join([maand_namen[m] for m in piek_maanden]) if piek_maanden else "geen"
        dal_str = ", ".join([maand_namen[m] for m in dal_maanden]) if dal_maanden else "geen"

        # Bereken seizoenssterkte
        seizoen_sterkte = seasonal_index.std()

        if seizoen_sterkte > 0.2:
            inzichten.append(CustomerInsight(
                categorie="seizoen",
                titel="Sterk seizoenspatroon",
                beschrijving=f"De omzet vertoont duidelijke seizoenseffecten. "
                            f"Piekmaanden: {piek_str}. Dalmaanden: {dal_str}. "
                            f"Dit is belangrijk voor de cashflow planning.",
                impact="neutraal",
                confidence=0.85,
                data_support={
                    "piek_maanden": piek_maanden,
                    "dal_maanden": dal_maanden,
                    "seizoen_sterkte": seizoen_sterkte,
                    "seasonal_index": seasonal_index.to_dict()
                }
            ))
        elif seizoen_sterkte > 0.1:
            inzichten.append(CustomerInsight(
                categorie="seizoen",
                titel="Matig seizoenspatroon",
                beschrijving=f"Er zijn lichte seizoenseffecten zichtbaar. "
                            f"Piekmaanden: {piek_str}. Dalmaanden: {dal_str}.",
                impact="neutraal",
                confidence=0.7,
                data_support={
                    "seizoen_sterkte": seizoen_sterkte,
                    "seasonal_index": seasonal_index.to_dict()
                }
            ))
    else:
        inzichten.append(CustomerInsight(
            categorie="seizoen",
            titel="Stabiele omzet",
            beschrijving="De omzet is relatief stabiel door het jaar heen, "
                        "zonder duidelijke seizoenseffecten.",
            impact="positief",
            confidence=0.8,
            data_support={"seizoen_sterkte": seasonal_index.std()}
        ))

    # === INZICHT: Trend ===
    # Lineaire regressie voor trend
    df = df.sort_values("week_start")
    df["week_idx"] = range(len(df))

    if len(df) >= 26:
        x = df["week_idx"].values
        y = df["omzet"].values
        slope, intercept = np.polyfit(x, y, 1)

        # Bereken procentuele trend per jaar (52 weken)
        yearly_trend_pct = (slope * 52) / overall_avg * 100 if overall_avg > 0 else 0

        if yearly_trend_pct > 10:
            inzichten.append(CustomerInsight(
                categorie="trend",
                titel="Groeiende omzet",
                beschrijving=f"De omzet groeit met ongeveer {yearly_trend_pct:.0f}% per jaar. "
                            f"Dit is positief voor de cashflow.",
                impact="positief",
                confidence=0.75,
                data_support={"yearly_trend_pct": yearly_trend_pct, "slope": slope}
            ))
        elif yearly_trend_pct < -10:
            inzichten.append(CustomerInsight(
                categorie="trend",
                titel="Dalende omzet",
                beschrijving=f"De omzet daalt met ongeveer {abs(yearly_trend_pct):.0f}% per jaar. "
                            f"Dit is een aandachtspunt voor de cashflow planning.",
                impact="negatief",
                confidence=0.75,
                data_support={"yearly_trend_pct": yearly_trend_pct, "slope": slope}
            ))

    return inzichten


def analyze_volatility(
    historische_omzet: pd.DataFrame
) -> list:
    """
    Analyseer volatiliteit en voorspelbaarheid.

    Returns:
        Lijst van CustomerInsight objecten
    """
    inzichten = []

    if historische_omzet.empty:
        return inzichten

    df = historische_omzet.copy()

    # Coefficient of variation (CV)
    cv = df["omzet"].std() / df["omzet"].mean() if df["omzet"].mean() > 0 else 0

    if cv < 0.2:
        voorspelbaarheid = "hoog"
        inzichten.append(CustomerInsight(
            categorie="volatiliteit",
            titel="Hoge voorspelbaarheid",
            beschrijving=f"De omzet is zeer consistent (CV = {cv:.2f}). "
                        f"Dit maakt cashflow forecasting betrouwbaar.",
            impact="positief",
            confidence=0.9,
            data_support={"cv": cv}
        ))
    elif cv < 0.4:
        voorspelbaarheid = "gemiddeld"
        inzichten.append(CustomerInsight(
            categorie="volatiliteit",
            titel="Gemiddelde volatiliteit",
            beschrijving=f"De omzet heeft normale variatie (CV = {cv:.2f}). "
                        f"Forecasts zijn redelijk betrouwbaar.",
            impact="neutraal",
            confidence=0.8,
            data_support={"cv": cv}
        ))
    else:
        voorspelbaarheid = "laag"
        inzichten.append(CustomerInsight(
            categorie="volatiliteit",
            titel="Hoge volatiliteit",
            beschrijving=f"De omzet varieert sterk (CV = {cv:.2f}). "
                        f"Forecasts hebben grotere onzekerheidsmarges.",
            impact="negatief",
            confidence=0.85,
            data_support={"cv": cv}
        ))

    return inzichten


def run_walk_forward_backtest(
    historische_omzet: pd.DataFrame,
    historische_cashflow: pd.DataFrame,
    betaalgedrag: pd.DataFrame,
    n_cutoff_dates: int = 12,
    forecast_horizon: int = 12,
) -> BacktestResult:
    """
    Voer walk-forward backtesting uit op het 4-lagen model.

    METHODIEK (De Tijdmachine):
    1. Kies 12 cutoff dates in het verleden
    2. Voor elke cutoff: maskeer alle data NA die datum
    3. Draai het model op de gemaskeerde data
    4. Vergelijk forecast met werkelijke uitkomsten
    5. Bereken accuracy metrics per horizon

    Args:
        historische_omzet: Historische omzet per week
        historische_cashflow: Historische cashflow per week (actuals)
        betaalgedrag: DSO per debiteur
        n_cutoff_dates: Aantal test momenten
        forecast_horizon: Hoeveel weken vooruit testen

    Returns:
        BacktestResult met alle metrics en learnings
    """
    if historische_omzet.empty or len(historische_omzet) < 52:
        return BacktestResult(
            mape_per_horizon={},
            overall_mape=999,
            bias=0,
            rmse=999,
            layer1_accuracy=0,
            layer3_accuracy=0,
            learnings=["Onvoldoende data voor backtesting (minimaal 52 weken nodig)"],
            n_cutoff_dates=0,
            test_period_start="",
            test_period_end="",
            detailed_results=pd.DataFrame()
        )

    df_omzet = historische_omzet.copy()
    df_omzet["week_start"] = pd.to_datetime(df_omzet["week_start"])
    df_omzet = df_omzet.sort_values("week_start")

    df_cash = historische_cashflow.copy() if not historische_cashflow.empty else df_omzet.copy()
    if "inkomsten" in df_cash.columns:
        df_cash["actuals"] = df_cash["inkomsten"]
    else:
        df_cash["actuals"] = df_cash["omzet"]
    df_cash["week_start"] = pd.to_datetime(df_cash["week_start"])

    # Bepaal cutoff dates
    min_date = df_omzet["week_start"].min()
    max_date = df_omzet["week_start"].max()

    # We hebben minimaal forecast_horizon weken NA de laatste cutoff nodig
    last_valid_cutoff = max_date - timedelta(weeks=forecast_horizon)
    first_valid_cutoff = min_date + timedelta(weeks=26)  # Minimaal 26 weken training

    if first_valid_cutoff >= last_valid_cutoff:
        return BacktestResult(
            mape_per_horizon={},
            overall_mape=999,
            bias=0,
            rmse=999,
            layer1_accuracy=0,
            layer3_accuracy=0,
            learnings=["Onvoldoende data range voor backtesting"],
            n_cutoff_dates=0,
            test_period_start=str(first_valid_cutoff.date()),
            test_period_end=str(last_valid_cutoff.date()),
            detailed_results=pd.DataFrame()
        )

    # Genereer cutoff dates (maandelijks)
    cutoff_dates = pd.date_range(
        start=first_valid_cutoff,
        end=last_valid_cutoff,
        periods=min(n_cutoff_dates, 12)
    )

    all_results = []
    errors_per_horizon = {h: [] for h in range(1, forecast_horizon + 1)}

    for cutoff in cutoff_dates:
        cutoff_date = cutoff.date()

        # === DATA MASKING ===
        # Alleen data VOOR de cutoff gebruiken voor training
        train_omzet = df_omzet[df_omzet["week_start"] < cutoff].copy()

        if len(train_omzet) < 12:
            continue

        # === GENEREER FORECAST ===
        omzet_forecast = forecast_revenue_holt_winters(
            train_omzet.rename(columns={"omzet": "omzet"}) if "omzet" not in train_omzet.columns else train_omzet,
            weeks_ahead=forecast_horizon
        )

        if omzet_forecast.empty:
            continue

        # Portfolio DSO voor time-shift
        portfolio_dso = calculate_portfolio_dso(betaalgedrag, None)

        # === VERGELIJK MET ACTUALS ===
        for h in range(1, forecast_horizon + 1):
            forecast_week = cutoff + timedelta(weeks=h)

            # Zoek forecast waarde
            forecast_row = omzet_forecast[
                omzet_forecast["week_start"].dt.date == forecast_week.date()
            ]

            if forecast_row.empty:
                continue

            forecast_value = forecast_row["omzet_forecast"].values[0]

            # Zoek actual waarde
            actual_row = df_cash[
                (df_cash["week_start"].dt.date >= forecast_week.date()) &
                (df_cash["week_start"].dt.date < (forecast_week + timedelta(weeks=1)).date())
            ]

            if actual_row.empty:
                continue

            actual_value = actual_row["actuals"].values[0]

            # Bereken error
            if actual_value != 0:
                pct_error = (forecast_value - actual_value) / actual_value * 100
                abs_error = abs(forecast_value - actual_value)

                errors_per_horizon[h].append(pct_error)

                all_results.append({
                    "cutoff_date": cutoff_date,
                    "horizon": h,
                    "forecast": forecast_value,
                    "actual": actual_value,
                    "error": forecast_value - actual_value,
                    "pct_error": pct_error,
                    "abs_pct_error": abs(pct_error)
                })

    # === BEREKEN METRICS ===
    if not all_results:
        return BacktestResult(
            mape_per_horizon={},
            overall_mape=999,
            bias=0,
            rmse=999,
            layer1_accuracy=0,
            layer3_accuracy=0,
            learnings=["Geen bruikbare backtest resultaten"],
            n_cutoff_dates=0,
            test_period_start=str(cutoff_dates[0].date()) if len(cutoff_dates) > 0 else "",
            test_period_end=str(cutoff_dates[-1].date()) if len(cutoff_dates) > 0 else "",
            detailed_results=pd.DataFrame()
        )

    results_df = pd.DataFrame(all_results)

    # MAPE per horizon
    mape_per_horizon = {}
    for h in range(1, forecast_horizon + 1):
        if errors_per_horizon[h]:
            mape_per_horizon[h] = np.mean([abs(e) for e in errors_per_horizon[h]])

    # Overall metrics
    overall_mape = results_df["abs_pct_error"].mean()
    bias = results_df["error"].mean()
    rmse = np.sqrt((results_df["error"] ** 2).mean())

    # Layer accuracy (geschat)
    # Layer 1 (korte termijn, horizon 1-4) vs Layer 3 (lange termijn, horizon 8+)
    layer1_results = results_df[results_df["horizon"] <= 4]
    layer3_results = results_df[results_df["horizon"] >= 8]

    layer1_accuracy = 100 - layer1_results["abs_pct_error"].mean() if len(layer1_results) > 0 else 0
    layer3_accuracy = 100 - layer3_results["abs_pct_error"].mean() if len(layer3_results) > 0 else 0

    # === GENEREER LEARNINGS ===
    learnings = []

    # Learning 1: Overall performance
    if overall_mape < 15:
        learnings.append(f"✅ Model presteert goed: gemiddelde afwijking {overall_mape:.1f}%")
    elif overall_mape < 30:
        learnings.append(f"⚠️ Model presteert acceptabel: gemiddelde afwijking {overall_mape:.1f}%")
    else:
        learnings.append(f"❌ Model presteert matig: gemiddelde afwijking {overall_mape:.1f}%")

    # Learning 2: Bias
    if bias > 0:
        learnings.append(f"📈 Model overschat systematisch met €{bias:,.0f}/week. "
                        "Overweeg conservatievere forecasts.")
    elif bias < 0:
        learnings.append(f"📉 Model onderschat systematisch met €{abs(bias):,.0f}/week. "
                        "De werkelijkheid is vaak beter dan verwacht.")

    # Learning 3: Accuracy decay
    if len(mape_per_horizon) >= 4:
        week1_mape = mape_per_horizon.get(1, 0)
        week4_mape = mape_per_horizon.get(4, 0)
        week8_mape = mape_per_horizon.get(8, 0) if 8 in mape_per_horizon else None

        if week4_mape > week1_mape * 1.5:
            learnings.append(f"📊 Accuracy daalt snel: week 1 ({week1_mape:.0f}%) → "
                           f"week 4 ({week4_mape:.0f}%). "
                           "Focus op korte termijn forecasts.")
        else:
            learnings.append(f"📊 Accuracy blijft stabiel over tijd: "
                           f"week 1 ({week1_mape:.0f}%) → week 4 ({week4_mape:.0f}%).")

        if week8_mape:
            learnings.append(f"🔮 Ghost Invoices (week 8+) hebben {week8_mape:.0f}% afwijking. "
                           "Dit is de lange termijn onzekerheid.")

    # Learning 4: Layer performance
    if layer1_accuracy > 0:
        learnings.append(f"📋 Laag 1 (openstaande posten): {layer1_accuracy:.0f}% nauwkeurig")
    if layer3_accuracy > 0:
        learnings.append(f"👻 Laag 3 (Ghost Invoices): {layer3_accuracy:.0f}% nauwkeurig")

    return BacktestResult(
        mape_per_horizon=mape_per_horizon,
        overall_mape=round(overall_mape, 1),
        bias=round(bias, 2),
        rmse=round(rmse, 2),
        layer1_accuracy=round(layer1_accuracy, 1),
        layer3_accuracy=round(layer3_accuracy, 1),
        learnings=learnings,
        n_cutoff_dates=len(cutoff_dates),
        test_period_start=str(cutoff_dates[0].date()) if len(cutoff_dates) > 0 else "",
        test_period_end=str(cutoff_dates[-1].date()) if len(cutoff_dates) > 0 else "",
        detailed_results=results_df
    )


def create_customer_profile(
    klant_code: str,
    historische_omzet: pd.DataFrame,
    historische_cashflow: pd.DataFrame,
    betaalgedrag: pd.DataFrame,
    run_backtest: bool = True
) -> CustomerProfile:
    """
    Maak een compleet klantprofiel met inzichten en backtesting.

    Dit is de hoofdfunctie die alle analyses combineert tot een
    beschrijvend profiel van de klant.

    Args:
        klant_code: Identificatie van de klant
        historische_omzet: Historische omzet per week
        historische_cashflow: Historische cashflow per week
        betaalgedrag: DSO per debiteur
        run_backtest: Of backtesting moet worden uitgevoerd

    Returns:
        CustomerProfile met alle inzichten en metrics
    """
    analyse_datum = datetime.now().strftime("%Y-%m-%d %H:%M")
    inzichten = []

    # === BETAALGEDRAG ANALYSE ===
    betaal_inzichten = analyze_customer_payment_behavior(betaalgedrag)
    inzichten.extend(betaal_inzichten)

    # Portfolio DSO
    portfolio_dso = calculate_portfolio_dso(betaalgedrag, None)

    # DSO trend (zou uit historische DSO data komen, hier geschat)
    dso_trend = "stabiel"

    # Betaaldiscipline
    if portfolio_dso <= 30:
        betaal_discipline = "goed"
    elif portfolio_dso <= 45:
        betaal_discipline = "gemiddeld"
    else:
        betaal_discipline = "slecht"

    # === SEIZOENSANALYSE ===
    # Converteer omzet kolom als nodig
    omzet_df = historische_omzet.copy()
    if "omzet" not in omzet_df.columns and "inkomsten" in omzet_df.columns:
        omzet_df["omzet"] = omzet_df["inkomsten"]

    seizoen_inzichten = analyze_seasonality(omzet_df)
    inzichten.extend(seizoen_inzichten)

    # Haal seizoensdata uit inzichten
    seizoen_sterkte = 0.0
    piek_maanden = []
    dal_maanden = []
    for inzicht in seizoen_inzichten:
        if inzicht.categorie == "seizoen":
            seizoen_sterkte = inzicht.data_support.get("seizoen_sterkte", 0.0)
            piek_maanden = inzicht.data_support.get("piek_maanden", [])
            dal_maanden = inzicht.data_support.get("dal_maanden", [])

    # === VOLATILITEIT ANALYSE ===
    volatiliteit_inzichten = analyze_volatility(omzet_df)
    inzichten.extend(volatiliteit_inzichten)

    # Haal volatiliteit uit inzichten
    omzet_volatiliteit = 0.0
    cashflow_voorspelbaarheid = "gemiddeld"
    for inzicht in volatiliteit_inzichten:
        if inzicht.categorie == "volatiliteit":
            omzet_volatiliteit = inzicht.data_support.get("cv", 0.0)
            if omzet_volatiliteit < 0.2:
                cashflow_voorspelbaarheid = "hoog"
            elif omzet_volatiliteit > 0.4:
                cashflow_voorspelbaarheid = "laag"

    # === BACKTESTING ===
    backtest_result = None
    if run_backtest and not omzet_df.empty:
        backtest_result = run_walk_forward_backtest(
            historische_omzet=omzet_df,
            historische_cashflow=historische_cashflow,
            betaalgedrag=betaalgedrag,
            n_cutoff_dates=12,
            forecast_horizon=12
        )

        # Voeg backtest learnings toe aan inzichten
        for learning in backtest_result.learnings:
            inzichten.append(CustomerInsight(
                categorie="backtest",
                titel="Model Learning",
                beschrijving=learning,
                impact="neutraal",
                confidence=0.9,
                data_support={"bron": "backtesting"}
            ))

    return CustomerProfile(
        klant_code=klant_code,
        analyse_datum=analyse_datum,
        portfolio_dso=portfolio_dso,
        dso_trend=dso_trend,
        betaal_discipline=betaal_discipline,
        seizoen_sterkte=seizoen_sterkte,
        piek_maanden=piek_maanden,
        dal_maanden=dal_maanden,
        omzet_volatiliteit=omzet_volatiliteit,
        cashflow_voorspelbaarheid=cashflow_voorspelbaarheid,
        inzichten=inzichten,
        backtest_result=backtest_result
    )


# =============================================================================
# LEGACY: OUDE ENHANCED FORECAST (BEHOUDEN VOOR BACKWARDS COMPATIBILITY)
# =============================================================================

def create_enhanced_forecast(
    banksaldo: pd.DataFrame,
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    historische_cashflow: pd.DataFrame,
    weeks: int = 13,
    weeks_history: int = 4,
    debiteur_delay_days: int = 0,
    crediteur_delay_days: int = 0,
    reference_date=None,
    deterministic_config: Optional[DeterministicCostConfig] = None,
    use_prophet: bool = False,
    prophet_weight: float = 0.3,
    use_week_of_month: bool = True,
    wom_strength: float = 0.5,
) -> Tuple[pd.DataFrame, int, ForecastModelMetrics, Dict]:
    """
    Verbeterde cashflow forecast die alle fasen combineert:

    - Fase 1: DSO per debiteur (via debiteur_delay_days of aparte aanroep)
    - Fase 2: Fading Weight ensemble model (basis)
    - Fase 3: Deterministische kosten isoleren
    - Fase 4: Prophet integratie (optioneel)
    - Fase 5: Week-van-maand patroon correctie

    Args:
        banksaldo: DataFrame met banksaldi
        debiteuren: DataFrame met openstaande debiteuren
        crediteuren: DataFrame met openstaande crediteuren
        historische_cashflow: DataFrame met historische cashflow
        weeks: Aantal weken vooruit
        weeks_history: Aantal historische weken in output
        debiteur_delay_days: Globale DSO correctie (of 0 als per-debiteur)
        crediteur_delay_days: Globale DPO correctie
        reference_date: Referentiedatum (default: vandaag)
        deterministic_config: Configuratie voor deterministische kosten
        use_prophet: Of Prophet moet worden gebruikt
        prophet_weight: Gewicht voor Prophet blend
        use_week_of_month: Of week-van-maand correctie moet worden toegepast
        wom_strength: Sterkte van week-van-maand correctie

    Returns:
        Tuple van (forecast DataFrame, forecast_start_idx, metrics, extra_info)
    """
    # Stap 1: Maak basis forecast met ML model
    base_forecast, forecast_start_idx, metrics = create_ml_forecast(
        banksaldo=banksaldo,
        debiteuren=debiteuren,
        crediteuren=crediteuren,
        historische_cashflow=historische_cashflow,
        weeks=weeks,
        weeks_history=weeks_history,
        debiteur_delay_days=debiteur_delay_days,
        crediteur_delay_days=crediteur_delay_days,
        reference_date=reference_date,
    )

    extra_info = {
        "deterministic_costs": [],
        "prophet_used": False,
        "wom_pattern": {},
    }

    if base_forecast.empty:
        return base_forecast, forecast_start_idx, metrics, extra_info

    df = base_forecast.copy()

    # Stap 2: Leer week-van-maand patroon
    if use_week_of_month and not historische_cashflow.empty:
        wom_pattern = learn_week_of_month_pattern(historische_cashflow)
        extra_info["wom_pattern"] = wom_pattern

        # Pas toe op prognose rijen
        for idx, row in df.iterrows():
            if row.get("is_realisatie", True):
                continue

            adj_in, adj_uit = apply_week_of_month_adjustment(
                row["inkomsten_debiteuren"],
                row["uitgaven_crediteuren"],
                row["week_start"],
                wom_pattern,
                adjustment_strength=wom_strength
            )
            df.at[idx, "inkomsten_debiteuren"] = adj_in
            df.at[idx, "uitgaven_crediteuren"] = adj_uit

    # Stap 3: Voeg deterministische kosten toe
    if deterministic_config is None:
        # Probeer te schatten uit historische data
        deterministic_config = estimate_deterministic_costs_from_history(historische_cashflow)

    all_det_costs = []
    for idx, row in df.iterrows():
        if row.get("is_realisatie", True):
            continue

        det_costs, det_details = calculate_deterministic_costs_for_week(
            row["week_start"],
            row["week_eind"],
            deterministic_config
        )

        if det_costs > 0:
            # Voeg deterministische kosten toe aan uitgaven (100% zekerheid)
            # Deze worden NIET vermenigvuldigd met fading weights - ze zijn zeker
            df.at[idx, "uitgaven_crediteuren"] = row["uitgaven_crediteuren"] + det_costs
            df.at[idx, "deterministische_kosten"] = det_costs
            all_det_costs.extend(det_details)

    extra_info["deterministic_costs"] = all_det_costs

    # Herbereken netto cashflow na aanpassingen
    df["netto_cashflow"] = df["inkomsten_debiteuren"] - df["uitgaven_crediteuren"]

    # Stap 4: Prophet integratie (optioneel)
    if use_prophet and PROPHET_AVAILABLE and not historische_cashflow.empty:
        prophet_forecast = create_prophet_forecast(
            historische_cashflow,
            weeks_ahead=weeks
        )

        if prophet_forecast is not None:
            df = blend_with_prophet(df, prophet_forecast, prophet_weight)
            extra_info["prophet_used"] = True

    # Herbereken cumulatief saldo
    start_balance = banksaldo["saldo"].sum() if not banksaldo.empty else 0
    df["cumulatief_saldo"] = start_balance + df["netto_cashflow"].cumsum()

    return df, forecast_start_idx, metrics, extra_info
