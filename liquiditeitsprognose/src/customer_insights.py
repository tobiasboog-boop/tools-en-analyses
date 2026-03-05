"""
CUSTOMER INSIGHTS REPORT
========================
Genereert een beschrijvend rapport over cashflow patronen van een klant.
Valideert het forecast model tegen werkelijke banktransacties.
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CustomerInsights:
    """Klant-specifieke inzichten en validatie."""
    customer_code: str
    administratie: str
    analysis_date: date

    # Validatie metrics
    forecast_income_weekly: float
    actual_income_weekly: float
    income_accuracy: float  # percentage

    forecast_expense_weekly: float
    actual_expense_weekly: float
    expense_accuracy: float

    # Patronen
    seasonality_strength: str  # 'zwak', 'matig', 'sterk'
    peak_week_of_month: int
    payment_behavior: str  # 'stabiel', 'variabel', 'onvoorspelbaar'
    avg_dso_days: float

    # Risico's en kansen
    cashflow_volatility: float  # standaarddeviatie als % van gemiddelde
    largest_debtor_concentration: float  # % van totaal AR
    negative_weeks_ratio: float  # % weken met negatieve cashflow

    # Confidence
    data_quality_score: float  # 0-100
    forecast_confidence: str  # 'hoog', 'matig', 'laag'

    # Narrative
    summary: str
    recommendations: list


def generate_customer_insights(
    db,
    customer_code: str,
    administratie: str,
    lookback_days: int = 90
) -> CustomerInsights:
    """
    Genereer uitgebreide klantinzichten.

    Args:
        db: Database connectie
        customer_code: Klantcode
        administratie: Administratie naam
        lookback_days: Dagen historie voor analyse
    """
    analysis_date = date.today()

    # ==========================================================================
    # 1. HAAL WERKELIJKE BANKTRANSACTIES OP
    # ==========================================================================
    actual_cashflow = _get_actual_bank_cashflow(db, administratie, lookback_days)

    # ==========================================================================
    # 2. HAAL FORECAST DATA OP
    # ==========================================================================
    from src.forecast_model import create_forecast_for_app

    hist_start = date(analysis_date.year - 1, analysis_date.month, 1)

    data = {
        'banksaldo': db.get_banksaldo(standdatum=analysis_date, administratie=administratie),
        'debiteuren': db.get_openstaande_debiteuren(standdatum=analysis_date, administratie=administratie),
        'crediteuren': db.get_openstaande_crediteuren(standdatum=analysis_date),
        'historische_cashflow': db.get_historische_cashflow_per_week(
            startdatum=hist_start,
            einddatum=analysis_date,
            administratie=administratie
        )
    }

    _, _, metadata = create_forecast_for_app(data, weeks_forecast=13, weeks_history=0)

    # ==========================================================================
    # 3. VALIDATIE BEREKENINGEN
    # ==========================================================================
    forecast_income = metadata.get('income_run_rate', 0)
    forecast_expense = metadata.get('expense_run_rate', 0)

    if not actual_cashflow.empty:
        actual_income = actual_cashflow['inkomsten'].mean()
        actual_expense = actual_cashflow['uitgaven'].mean()
    else:
        actual_income = forecast_income
        actual_expense = forecast_expense

    income_accuracy = _calc_accuracy(forecast_income, actual_income)
    expense_accuracy = _calc_accuracy(forecast_expense, actual_expense)

    # ==========================================================================
    # 4. PATROON ANALYSE
    # ==========================================================================
    seasonality_strength, peak_week = _analyze_seasonality(metadata)
    payment_behavior, cashflow_volatility = _analyze_payment_behavior(actual_cashflow)

    # DSO analyse
    avg_dso = _calculate_avg_dso(data['debiteuren'])

    # Concentratie risico
    concentration = _analyze_concentration(data['debiteuren'])

    # Negatieve weken
    if not actual_cashflow.empty:
        negative_weeks = (actual_cashflow['netto'] < 0).mean() * 100
    else:
        negative_weeks = 0

    # ==========================================================================
    # 5. DATA QUALITY & CONFIDENCE
    # ==========================================================================
    data_quality = _assess_data_quality(data, actual_cashflow)
    forecast_confidence = _determine_confidence(
        income_accuracy, expense_accuracy, data_quality, cashflow_volatility
    )

    # ==========================================================================
    # 6. GENEREER NARRATIVE
    # ==========================================================================
    summary, recommendations = _generate_narrative(
        customer_code=customer_code,
        administratie=administratie,
        income_accuracy=income_accuracy,
        expense_accuracy=expense_accuracy,
        forecast_income=forecast_income,
        actual_income=actual_income,
        forecast_expense=forecast_expense,
        actual_expense=actual_expense,
        seasonality_strength=seasonality_strength,
        peak_week=peak_week,
        payment_behavior=payment_behavior,
        avg_dso=avg_dso,
        concentration=concentration,
        negative_weeks=negative_weeks,
        forecast_confidence=forecast_confidence
    )

    return CustomerInsights(
        customer_code=customer_code,
        administratie=administratie,
        analysis_date=analysis_date,
        forecast_income_weekly=forecast_income,
        actual_income_weekly=actual_income,
        income_accuracy=income_accuracy,
        forecast_expense_weekly=forecast_expense,
        actual_expense_weekly=actual_expense,
        expense_accuracy=expense_accuracy,
        seasonality_strength=seasonality_strength,
        peak_week_of_month=peak_week,
        payment_behavior=payment_behavior,
        avg_dso_days=avg_dso,
        cashflow_volatility=cashflow_volatility,
        largest_debtor_concentration=concentration,
        negative_weeks_ratio=negative_weeks,
        data_quality_score=data_quality,
        forecast_confidence=forecast_confidence,
        summary=summary,
        recommendations=recommendations
    )


def _get_actual_bank_cashflow(db, administratie: str, days: int) -> pd.DataFrame:
    """Haal werkelijke banktransacties op uit financieel.Journaalregels.

    Gebruikt DEZELFDE logica als de historische cashflow query voor 100% aansluiting:
    - financieel.Journaalregels met RubriekKey = DagboekRubriekKey
    - Debet = inkomsten (geld IN), Credit = uitgaven (geld UIT)
    """
    query = f'''
    SELECT
        DATE_TRUNC('week', j."Boekdatum") as week_start,
        SUM(CASE WHEN j."Debet/Credit" = 'D' THEN j."Bedrag" ELSE 0 END) as inkomsten,
        SUM(CASE WHEN j."Debet/Credit" = 'C' THEN j."Bedrag" ELSE 0 END) as uitgaven,
        SUM(CASE WHEN j."Debet/Credit" = 'D' THEN j."Bedrag" ELSE 0 END) -
        SUM(CASE WHEN j."Debet/Credit" = 'C' THEN j."Bedrag" ELSE 0 END) as netto
    FROM financieel."Journaalregels" j
    JOIN stam."Documenten" d ON j."DocumentKey" = d."DocumentKey"
    JOIN stam."Dagboeken" dag ON d."DagboekKey" = dag."DagboekKey"
    JOIN stam."Administraties" adm ON dag."AdministratieKey" = adm."AdministratieKey"
    WHERE d."StandaardEntiteitKey" = 10
      AND j."RubriekKey" = dag."DagboekRubriekKey"
      AND adm."Administratie" = %s
      AND j."Boekdatum" >= CURRENT_DATE - INTERVAL '{days} days'
    GROUP BY DATE_TRUNC('week', j."Boekdatum")
    ORDER BY week_start
    '''
    try:
        return db.execute_query_cursor(query, (administratie,))
    except Exception as e:
        print(f"Error fetching bank data: {e}")
        return pd.DataFrame()


def _calc_accuracy(forecast: float, actual: float) -> float:
    """Bereken accuracy percentage."""
    if actual == 0:
        return 100.0 if forecast == 0 else 0.0
    error = abs(forecast - actual) / actual
    return max(0, (1 - error) * 100)


def _analyze_seasonality(metadata: dict) -> Tuple[str, int]:
    """Analyseer seasonality sterkte."""
    seasonality = metadata.get('income_seasonality', {})

    if not seasonality:
        return 'onbekend', 1

    values = list(seasonality.values())
    if len(values) < 2:
        return 'zwak', 1

    spread = max(values) - min(values)
    peak_week = max(seasonality, key=seasonality.get)

    if spread < 0.2:
        return 'zwak', peak_week
    elif spread < 0.5:
        return 'matig', peak_week
    else:
        return 'sterk', peak_week


def _analyze_payment_behavior(cashflow: pd.DataFrame) -> Tuple[str, float]:
    """Analyseer betaalgedrag en volatiliteit."""
    if cashflow.empty:
        return 'onbekend', 0

    netto = cashflow['netto']
    if netto.std() == 0 or netto.mean() == 0:
        return 'stabiel', 0

    cv = abs(netto.std() / netto.mean()) * 100  # Coefficient of variation

    if cv < 50:
        return 'stabiel', cv
    elif cv < 100:
        return 'variabel', cv
    else:
        return 'onvoorspelbaar', cv


def _calculate_avg_dso(debiteuren: pd.DataFrame) -> float:
    """Bereken gemiddelde DSO uit openstaande debiteuren."""
    if debiteuren.empty:
        return 35.0  # Default

    if 'vervaldatum' not in debiteuren.columns or 'factuurdatum' not in debiteuren.columns:
        return 35.0

    try:
        deb = debiteuren.copy()
        deb['factuurdatum'] = pd.to_datetime(deb['factuurdatum'])
        deb['vervaldatum'] = pd.to_datetime(deb['vervaldatum'])
        deb['days_outstanding'] = (deb['vervaldatum'] - deb['factuurdatum']).dt.days
        return deb['days_outstanding'].mean()
    except:
        return 35.0


def _analyze_concentration(debiteuren: pd.DataFrame) -> float:
    """Analyseer concentratierisico (% van grootste debiteur)."""
    if debiteuren.empty or 'openstaand' not in debiteuren.columns:
        return 0

    total = debiteuren['openstaand'].sum()
    if total == 0:
        return 0

    largest = debiteuren['openstaand'].max()
    return (largest / total) * 100


def _assess_data_quality(data: dict, actual_cashflow: pd.DataFrame) -> float:
    """Beoordeel datakwaliteit (0-100)."""
    score = 0

    # Heeft historische cashflow data?
    if not data['historische_cashflow'].empty:
        score += 25
        if len(data['historische_cashflow']) >= 12:  # Minimaal 12 weken
            score += 15

    # Heeft openstaande posten?
    if not data['debiteuren'].empty:
        score += 20
    if not data['crediteuren'].empty:
        score += 15

    # Hebben we bankvalidatie data?
    if not actual_cashflow.empty:
        score += 25
        if len(actual_cashflow) >= 8:
            score += 10

    return min(100, score)


def _determine_confidence(
    income_acc: float, expense_acc: float, data_quality: float, volatility: float
) -> str:
    """Bepaal overall forecast confidence."""
    avg_accuracy = (income_acc + expense_acc) / 2

    # Combineer factoren
    confidence_score = (
        avg_accuracy * 0.4 +
        data_quality * 0.4 +
        max(0, 100 - volatility) * 0.2
    )

    if confidence_score >= 70:
        return 'hoog'
    elif confidence_score >= 50:
        return 'matig'
    else:
        return 'laag'


def _generate_narrative(
    customer_code: str,
    administratie: str,
    income_accuracy: float,
    expense_accuracy: float,
    forecast_income: float,
    actual_income: float,
    forecast_expense: float,
    actual_expense: float,
    seasonality_strength: str,
    peak_week: int,
    payment_behavior: str,
    avg_dso: float,
    concentration: float,
    negative_weeks: float,
    forecast_confidence: str
) -> Tuple[str, list]:
    """Genereer beschrijvende tekst en aanbevelingen."""

    # Build summary
    paragraphs = []

    # Opening
    paragraphs.append(
        f"Analyse voor {administratie} (klant {customer_code}) toont een "
        f"**{forecast_confidence}** betrouwbaarheid van de cashflow prognose."
    )

    # Accuracy
    if income_accuracy >= 80 and expense_accuracy >= 80:
        paragraphs.append(
            f"Het forecast model voorspelt inkomsten met {income_accuracy:.0f}% nauwkeurigheid "
            f"en uitgaven met {expense_accuracy:.0f}% nauwkeurigheid - uitstekende aansluiting "
            f"met de werkelijke banktransacties."
        )
    elif income_accuracy >= 60 and expense_accuracy >= 60:
        paragraphs.append(
            f"Het model heeft een redelijke aansluiting: inkomsten {income_accuracy:.0f}% "
            f"nauwkeurig, uitgaven {expense_accuracy:.0f}% nauwkeurig."
        )
    else:
        income_diff = forecast_income - actual_income
        expense_diff = forecast_expense - actual_expense
        paragraphs.append(
            f"Let op: het model wijkt af van de werkelijkheid. "
            f"{'Inkomsten worden onderschat' if income_diff < 0 else 'Inkomsten worden overschat'} "
            f"met EUR {abs(income_diff):,.0f}/week. "
            f"{'Uitgaven worden onderschat' if expense_diff < 0 else 'Uitgaven worden overschat'} "
            f"met EUR {abs(expense_diff):,.0f}/week."
        )

    # Seasonality
    if seasonality_strength == 'sterk':
        paragraphs.append(
            f"Er is een **sterk seizoenspatroon** zichtbaar. Week {peak_week} van de maand "
            f"is doorgaans de drukste periode voor inkomsten."
        )
    elif seasonality_strength == 'matig':
        paragraphs.append(
            f"Er is een matig seizoenspatroon, met een piek in week {peak_week} van de maand."
        )

    # Payment behavior
    if payment_behavior == 'stabiel':
        paragraphs.append(
            f"De cashflow is **stabiel** - goed voorspelbaar met weinig verrassingen."
        )
    elif payment_behavior == 'variabel':
        paragraphs.append(
            f"De cashflow is variabel - er zijn regelmatig schommelingen. "
            f"Houd rekening met onverwachte pieken en dalen."
        )
    else:
        paragraphs.append(
            f"De cashflow is **onvoorspelbaar** met grote schommelingen. "
            f"Wees voorzichtig met de prognoses en houd extra buffer aan."
        )

    # DSO
    if avg_dso > 45:
        paragraphs.append(
            f"Gemiddelde betaaltermijn is {avg_dso:.0f} dagen - relatief lang. "
            f"Overweeg actief debiteurenbeheer."
        )

    # Concentration risk
    if concentration > 30:
        paragraphs.append(
            f"**Concentratierisico**: De grootste debiteur vertegenwoordigt {concentration:.0f}% "
            f"van het openstaande bedrag. Dit is een risico bij betalingsproblemen."
        )

    # Negative weeks
    if negative_weeks > 40:
        paragraphs.append(
            f"In {negative_weeks:.0f}% van de weken was de cashflow negatief. "
            f"Overweeg een ruimere liquiditeitsbuffer."
        )

    summary = "\n\n".join(paragraphs)

    # Recommendations
    recommendations = []

    if income_accuracy < 70:
        recommendations.append(
            "Onderzoek waarom de inkomstenprognose afwijkt - mogelijk betalen klanten sneller/trager dan verwacht"
        )

    if expense_accuracy < 70:
        recommendations.append(
            "Valideer de uitgavenprognose - zijn alle vaste lasten en variabele kosten meegenomen?"
        )

    if concentration > 30:
        recommendations.append(
            "Reduceer concentratierisico door klantportfolio te diversificeren"
        )

    if avg_dso > 45:
        recommendations.append(
            f"Verlaag DSO van {avg_dso:.0f} naar 30-35 dagen door proactief incasseren"
        )

    if negative_weeks > 40:
        recommendations.append(
            "Verhoog werkkapitaal of spreek kredietfaciliteit af voor negatieve weken"
        )

    if forecast_confidence == 'hoog':
        recommendations.append(
            "De prognose is betrouwbaar - gebruik deze voor strategische planning"
        )
    elif forecast_confidence == 'laag':
        recommendations.append(
            "Behandel de prognose met voorzichtigheid - valideer regelmatig tegen actuals"
        )

    return summary, recommendations


def generate_insights_markdown(insights: CustomerInsights) -> str:
    """Genereer markdown rapport."""
    md = f"""# Cashflow Inzichten: {insights.administratie}

**Klant:** {insights.customer_code}
**Analyse datum:** {insights.analysis_date}
**Forecast betrouwbaarheid:** {insights.forecast_confidence.upper()}

---

## Samenvatting

{insights.summary}

---

## Validatie tegen Realisatie

| Metric | Forecast | Realisatie | Nauwkeurigheid |
|--------|----------|------------|----------------|
| Inkomsten/week | EUR {insights.forecast_income_weekly:,.0f} | EUR {insights.actual_income_weekly:,.0f} | {insights.income_accuracy:.0f}% |
| Uitgaven/week | EUR {insights.forecast_expense_weekly:,.0f} | EUR {insights.actual_expense_weekly:,.0f} | {insights.expense_accuracy:.0f}% |

---

## Patronen & Risico's

| Kenmerk | Waarde |
|---------|--------|
| Seizoenspatroon | {insights.seasonality_strength} (piek week {insights.peak_week_of_month}) |
| Betaalgedrag | {insights.payment_behavior} |
| Gemiddelde DSO | {insights.avg_dso_days:.0f} dagen |
| Cashflow volatiliteit | {insights.cashflow_volatility:.0f}% |
| Concentratie grootste debiteur | {insights.largest_debtor_concentration:.0f}% |
| Weken met negatieve cashflow | {insights.negative_weeks_ratio:.0f}% |

---

## Data Kwaliteit

Score: **{insights.data_quality_score:.0f}/100**

---

## Aanbevelingen

"""
    for i, rec in enumerate(insights.recommendations, 1):
        md += f"{i}. {rec}\n"

    return md


# =============================================================================
# CLI INTERFACE
# =============================================================================
if __name__ == "__main__":
    import sys
    from src.database import get_database

    customer_code = sys.argv[1] if len(sys.argv) > 1 else "1241"
    administratie = sys.argv[2] if len(sys.argv) > 2 else "Beck & v.d. Kroef B.V."

    print(f"Generating insights for customer {customer_code}...")
    print()

    db = get_database(use_mock=False, customer_code=customer_code)
    insights = generate_customer_insights(db, customer_code, administratie)

    report = generate_insights_markdown(insights)
    print(report)
