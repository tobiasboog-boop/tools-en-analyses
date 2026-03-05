"""
DAGELIJKSE CASHFLOW FORECAST
============================
-13 tot +13 dagen view
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, Dict


def create_daily_forecast(
    banksaldo: pd.DataFrame,
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    historische_cashflow: pd.DataFrame,
    days_history: int = 13,
    days_forecast: int = 13,
    reference_date=None,
) -> Tuple[pd.DataFrame, int, Dict]:
    """
    Dagelijkse cashflow forecast: -13 tot +13 dagen.

    Args:
        banksaldo: Huidige banksaldi
        debiteuren: Openstaande debiteuren met vervaldatum
        crediteuren: Openstaande crediteuren met vervaldatum
        historische_cashflow: Historische data (optioneel, voor fallback)
        days_history: Aantal dagen historie (-13)
        days_forecast: Aantal dagen forecast (+13)
        reference_date: Referentiedatum (vandaag)

    Returns:
        DataFrame met dagelijkse cashflow, start index, metadata
    """
    if reference_date is None:
        reference_date = datetime.now().date()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    all_rows = []

    # Bereken gemiddelde dagelijkse cashflow uit historie (fallback)
    avg_daily_inkomsten = 0.0
    avg_daily_uitgaven = 0.0

    if not historische_cashflow.empty:
        if "inkomsten" in historische_cashflow.columns:
            avg_daily_inkomsten = historische_cashflow["inkomsten"].mean() / 7  # Week -> dag
        if "uitgaven" in historische_cashflow.columns:
            avg_daily_uitgaven = historische_cashflow["uitgaven"].mean() / 7

    # =========================================================================
    # GROEPEER DEBITEUREN PER DAG
    # =========================================================================
    deb_per_dag = {}
    if not debiteuren.empty and "vervaldatum" in debiteuren.columns:
        deb = debiteuren.copy()
        deb["vervaldatum"] = pd.to_datetime(deb["vervaldatum"]).dt.date

        for _, row in deb.iterrows():
            vervaldatum = row["vervaldatum"]
            bedrag = row["openstaand"]

            if pd.isna(vervaldatum) or pd.isna(bedrag):
                continue

            if vervaldatum not in deb_per_dag:
                deb_per_dag[vervaldatum] = 0
            deb_per_dag[vervaldatum] += bedrag

    # =========================================================================
    # GROEPEER CREDITEUREN PER DAG
    # =========================================================================
    cred_per_dag = {}
    if not crediteuren.empty and "vervaldatum" in crediteuren.columns:
        cred = crediteuren.copy()
        cred["vervaldatum"] = pd.to_datetime(cred["vervaldatum"]).dt.date

        for _, row in cred.iterrows():
            vervaldatum = row["vervaldatum"]
            bedrag = row["openstaand"]

            if pd.isna(vervaldatum) or pd.isna(bedrag):
                continue

            if vervaldatum not in cred_per_dag:
                cred_per_dag[vervaldatum] = 0
            cred_per_dag[vervaldatum] += bedrag

    # =========================================================================
    # GENEREER DAGELIJKSE FORECAST
    # =========================================================================
    forecast_start_idx = days_history

    for day_offset in range(-days_history, days_forecast + 1):
        current_date = reference_date + timedelta(days=day_offset)
        is_realisatie = day_offset < 0
        is_today = day_offset == 0

        # Haal bekende posten voor deze dag
        inkomsten = deb_per_dag.get(current_date, 0)
        uitgaven = cred_per_dag.get(current_date, 0)

        # Voor prognose dagen zonder data: gebruik fallback (maar klein, want dagelijks)
        # Alleen als er helemaal geen data is voor die dag
        if not is_realisatie and inkomsten == 0 and day_offset > 7:
            # Na eerste week, lichte fallback toevoegen
            inkomsten = avg_daily_inkomsten * 0.3  # Conservatief
        if not is_realisatie and uitgaven == 0 and day_offset > 7:
            uitgaven = avg_daily_uitgaven * 0.3

        netto = inkomsten - uitgaven

        # Label
        if is_today:
            label = "Vandaag"
        elif day_offset < 0:
            label = f"Dag {day_offset}"
        else:
            label = f"Dag +{day_offset}"

        # Data type
        if is_realisatie:
            data_type = "Realisatie"
            confidence = 1.0
            methode = "historisch"
        elif is_today:
            data_type = "Vandaag"
            confidence = 0.95
            methode = "actueel"
        else:
            data_type = "Prognose"
            confidence = max(0.5, 0.95 - day_offset * 0.03)
            methode = "verwacht" if inkomsten > 0 or uitgaven > 0 else "geen data"

        all_rows.append({
            "dag_offset": day_offset,
            "dag_label": label,
            "datum": current_date,
            "inkomsten": round(inkomsten, 2),
            "uitgaven": round(uitgaven, 2),
            "netto_cashflow": round(netto, 2),
            "data_type": data_type,
            "is_realisatie": is_realisatie,
            "is_today": is_today,
            "confidence": round(confidence, 2),
            "methode": methode,
        })

    df = pd.DataFrame(all_rows)

    # Bereken cumulatief saldo
    start_balance = banksaldo["saldo"].sum() if not banksaldo.empty else 0
    df["cumulatief_saldo"] = start_balance + df["netto_cashflow"].cumsum()

    metadata = {
        "model": "daily_forecast",
        "days_history": days_history,
        "days_forecast": days_forecast,
        "n_debiteuren_met_vervaldatum": len(deb_per_dag),
        "n_crediteuren_met_vervaldatum": len(cred_per_dag),
        "totaal_verwacht_inkomsten": sum(deb_per_dag.values()),
        "totaal_verwacht_uitgaven": sum(cred_per_dag.values()),
    }

    return df, forecast_start_idx, metadata
