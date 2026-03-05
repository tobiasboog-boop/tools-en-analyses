"""
SIMPELE CASHFLOW FORECAST
=========================
Geen complexe lagen, gewoon:
1. Openstaande posten voor korte termijn
2. Historisch gemiddelde voor lange termijn
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, Dict


def create_simple_forecast(
    banksaldo: pd.DataFrame,
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    historische_cashflow: pd.DataFrame,
    weeks: int = 26,
    weeks_history: int = 4,
    reference_date=None,
) -> Tuple[pd.DataFrame, int, Dict]:
    """
    Simpele cashflow forecast.

    Strategie:
    - Korte termijn (week 1-6): Openstaande posten met vervaldatum
    - Lange termijn (week 7+): Historisch gemiddelde
    - Geleidelijke overgang tussen beide
    """
    if reference_date is None:
        reference_date = datetime.now().date()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    # Bereken historisch gemiddelde
    avg_inkomsten = 0.0
    avg_uitgaven = 0.0

    if not historische_cashflow.empty:
        if "inkomsten" in historische_cashflow.columns:
            avg_inkomsten = historische_cashflow["inkomsten"].mean()
        elif "omzet" in historische_cashflow.columns:
            avg_inkomsten = historische_cashflow["omzet"].mean()

        if "uitgaven" in historische_cashflow.columns:
            avg_uitgaven = historische_cashflow["uitgaven"].mean()

    all_rows = []

    # =========================================================================
    # REALISATIE (historische weken)
    # =========================================================================
    if weeks_history > 0 and not historische_cashflow.empty:
        hist = historische_cashflow.copy()
        hist["week_start"] = pd.to_datetime(hist["week_start"]).dt.date
        hist = hist[hist["week_start"] < reference_date]
        hist = hist.sort_values("week_start", ascending=False).head(weeks_history)
        hist = hist.sort_values("week_start", ascending=True)

        for i, row in enumerate(hist.itertuples()):
            week_num = -(weeks_history - i)
            inkomsten = getattr(row, "inkomsten", getattr(row, "omzet", 0))
            uitgaven = getattr(row, "uitgaven", 0)
            netto = inkomsten - uitgaven

            all_rows.append({
                "week_nummer": week_num,
                "week_label": f"Week {week_num}",
                "week_start": row.week_start,
                "week_eind": row.week_start + timedelta(days=7),
                "inkomsten_debiteuren": round(inkomsten, 2),
                "uitgaven_crediteuren": round(uitgaven, 2),
                "netto_cashflow": round(netto, 2),
                "data_type": "Realisatie",
                "is_realisatie": True,
                "confidence": 1.0,
                "methode": "realisatie",
            })

    forecast_start_idx = len(all_rows)

    # =========================================================================
    # PROGNOSE
    # =========================================================================
    # Bereid debiteuren voor
    deb_per_week = {}
    if not debiteuren.empty and "vervaldatum" in debiteuren.columns:
        deb = debiteuren.copy()
        deb["vervaldatum"] = pd.to_datetime(deb["vervaldatum"]).dt.date

        for _, row in deb.iterrows():
            vervaldatum = row["vervaldatum"]
            bedrag = row["openstaand"]

            if pd.isna(vervaldatum) or pd.isna(bedrag):
                continue

            days_from_ref = (vervaldatum - reference_date).days
            week_idx = days_from_ref // 7

            if week_idx not in deb_per_week:
                deb_per_week[week_idx] = 0
            deb_per_week[week_idx] += bedrag

    # Bereid crediteuren voor
    cred_per_week = {}
    if not crediteuren.empty and "vervaldatum" in crediteuren.columns:
        cred = crediteuren.copy()
        cred["vervaldatum"] = pd.to_datetime(cred["vervaldatum"]).dt.date

        for _, row in cred.iterrows():
            vervaldatum = row["vervaldatum"]
            bedrag = row["openstaand"]

            if pd.isna(vervaldatum) or pd.isna(bedrag):
                continue

            days_from_ref = (vervaldatum - reference_date).days
            week_idx = days_from_ref // 7

            if week_idx not in cred_per_week:
                cred_per_week[week_idx] = 0
            cred_per_week[week_idx] += bedrag

    # Genereer forecast per week
    for week_idx in range(weeks):
        week_num = week_idx + 1
        week_start = reference_date + timedelta(weeks=week_idx)
        week_end = week_start + timedelta(days=7)

        # Openstaande posten voor deze week
        bekend_in = deb_per_week.get(week_idx, 0)
        bekend_uit = cred_per_week.get(week_idx, 0)

        # Blend factor: hoe verder in de toekomst, hoe meer historisch gemiddelde
        # Week 1-4: 90% openstaand, 10% historisch
        # Week 5-8: geleidelijke overgang
        # Week 9+: 20% openstaand, 80% historisch
        if week_num <= 4:
            blend_openstaand = 0.9
        elif week_num <= 8:
            blend_openstaand = 0.9 - (week_num - 4) * 0.175  # 0.9 -> 0.2
        else:
            blend_openstaand = 0.2

        blend_historisch = 1 - blend_openstaand

        # Bereken inkomsten
        if bekend_in > 0:
            inkomsten = blend_openstaand * bekend_in + blend_historisch * avg_inkomsten
        else:
            inkomsten = avg_inkomsten

        # Bereken uitgaven
        if bekend_uit > 0:
            uitgaven = blend_openstaand * bekend_uit + blend_historisch * avg_uitgaven
        else:
            uitgaven = avg_uitgaven

        netto = inkomsten - uitgaven

        # Confidence aflopend met tijd
        confidence = max(0.3, 0.95 - week_num * 0.03)

        # Methode beschrijving
        if bekend_in > 0 or bekend_uit > 0:
            methode = f"blend: {blend_openstaand*100:.0f}% openstaand + {blend_historisch*100:.0f}% historisch"
        else:
            methode = "historisch gemiddelde"

        all_rows.append({
            "week_nummer": week_num,
            "week_label": f"Week {week_num}",
            "week_start": week_start,
            "week_eind": week_end,
            "inkomsten_debiteuren": round(inkomsten, 2),
            "uitgaven_crediteuren": round(uitgaven, 2),
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

    metadata = {
        "model": "simple_blend",
        "avg_inkomsten": avg_inkomsten,
        "avg_uitgaven": avg_uitgaven,
    }

    return df, forecast_start_idx, metadata
