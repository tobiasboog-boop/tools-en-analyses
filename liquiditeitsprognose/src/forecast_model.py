"""
GHOST INVOICE FORECAST MODEL V6
================================
Run Rate + Seasonality + Calibrated DSO + Volatility-Aware:
- Laatste 90 dagen bepaalt HUIDIG niveau (run rate)
- Volle historie bepaalt alleen PATROON (seasonality index)
- DSO wordt berekend uit werkelijk betaalgedrag (niet vaste 35 dagen)

V6 verbeteringen:
- Dynamische IQR multiplier: bij hoge volatiliteit (CV > 0.8) minder agressief filteren
- PCT-type detectie: income ≈ expense exact = data anomalie
- Uitgebreide data quality flags met volatility warnings
- 'very_low' confidence voor projectmatige bedrijven (CV > 1.0)
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

FORECAST_WEEKS = 26
DEFAULT_DSO_DAYS = 35  # Fallback als geen data beschikbaar
DEFAULT_DPO_DAYS = 0   # Uitgaven op vervaldatum

# Blending configuratie (geen harde cutoff meer)
BLEND_START = 2   # Vanaf week 2 beginnen we ghost bij te mengen
BLEND_END = 6     # Bij week 6 is ghost volledig dominant


def create_forecast_for_app(
    data: Dict[str, pd.DataFrame],
    weeks_forecast: int = 13,
    weeks_history: int = 13,
    reference_date=None,
    calibrated_dso: Optional[float] = None,
    calibrated_dpo: Optional[float] = None
) -> Tuple[pd.DataFrame, int, Dict]:
    """Genereer forecast voor de app.

    Args:
        data: Dict met DataFrames (historische_cashflow, debiteuren, crediteuren, banksaldo)
        weeks_forecast: Aantal weken vooruit te forecasen
        weeks_history: Aantal weken historie te tonen
        reference_date: Peildatum (default: vandaag)
        calibrated_dso: Gecalibreerde DSO in dagen (uit betaalgedrag). None = default 35
        calibrated_dpo: Gecalibreerde DPO in dagen. None = default 0 (op vervaldatum)
    """

    if reference_date is None:
        reference_date = datetime.now().date()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    df_history = data.get('historische_cashflow', pd.DataFrame())
    df_debiteuren = data.get('debiteuren', pd.DataFrame())
    df_crediteuren = data.get('crediteuren', pd.DataFrame())
    df_banksaldo = data.get('banksaldo', pd.DataFrame())

    start_balance = df_banksaldo['saldo'].sum() if not df_banksaldo.empty and 'saldo' in df_banksaldo.columns else 0

    # Gebruik gecalibreerde DSO/DPO of defaults
    dso_days = calibrated_dso if calibrated_dso is not None else DEFAULT_DSO_DAYS
    dpo_days = calibrated_dpo if calibrated_dpo is not None else DEFAULT_DPO_DAYS

    # =========================================================================
    # STAP 1+2: RUN RATE + SEASONALITY INDEX (V6: met volatility stats)
    # =========================================================================
    income_run_rate, income_seasonality, income_volatility = _calculate_runrate_seasonality(df_history, 'income')
    expense_run_rate, expense_seasonality, expense_volatility = _calculate_runrate_seasonality(df_history, 'expense')

    # =========================================================================
    # STAP 3: PROJECTEER TOEKOMST (met gecalibreerde DSO)
    # =========================================================================
    ghost_income = _project_with_runrate(income_run_rate, income_seasonality, reference_date, weeks_forecast, dso_days)
    ghost_expense = _project_with_runrate(expense_run_rate, expense_seasonality, reference_date, weeks_forecast, dpo_days)

    # =========================================================================
    # STAP 4: HARDE DATA UIT ERP
    # =========================================================================
    real_income = _get_real_data(df_debiteuren)
    real_expense = _get_real_data(df_crediteuren)

    # =========================================================================
    # BOUW OUTPUT
    # =========================================================================
    rows = []

    # Historie (realisatie)
    hist_rows = _build_history_rows(df_history, weeks_history)
    rows.extend(hist_rows)
    forecast_start_idx = len(hist_rows)

    # Forecast weken
    for week_idx in range(weeks_forecast):
        week_start = reference_date + timedelta(weeks=week_idx)
        week_end = week_start + timedelta(days=6)

        # Harde data uit ERP
        real_inc = _sum_in_week(real_income, week_start, week_end)
        real_exp = _sum_in_week(real_expense, week_start, week_end)

        # Ghost data (geprojecteerd)
        ghost_inc = ghost_income.get(week_idx, 0)
        ghost_exp = ghost_expense.get(week_idx, 0)

        # BLENDED WATERFALL LOGICA
        # Geen harde cutoff, maar geleidelijke overgang
        if week_idx <= BLEND_START:
            # Week 0-2: Real domineert, ghost alleen als fallback
            real_weight = 1.0
        elif week_idx >= BLEND_END:
            # Week 6+: Ghost domineert volledig
            real_weight = 0.0
        else:
            # Week 3-5: Geleidelijke blend (linear)
            real_weight = 1.0 - (week_idx - BLEND_START) / (BLEND_END - BLEND_START)

        ghost_weight = 1.0 - real_weight

        # Blend inkomsten
        if real_inc > 0:
            total_income = real_inc * real_weight + ghost_inc * ghost_weight
        else:
            total_income = ghost_inc  # Geen real data, gebruik ghost

        # Blend uitgaven
        if real_exp > 0:
            total_expense = real_exp * real_weight + ghost_exp * ghost_weight
        else:
            total_expense = ghost_exp

        netto = total_income - total_expense

        rows.append({
            'week_nummer': week_idx,
            'week_label': 'Vandaag' if week_idx == 0 else f'Week {week_idx}',
            'week_start': week_start,
            'week_eind': week_end,
            'inkomsten_debiteuren': total_income,
            'uitgaven_crediteuren': total_expense,
            'uitgaven_salarissen': 0,
            'uitgaven_overig': 0,
            'netto_cashflow': netto,
            'is_realisatie': False,
            'data_type': 'Vandaag' if week_idx == 0 else 'Prognose',
        })

    df = pd.DataFrame(rows)
    df['cumulatief_saldo'] = start_balance + df['netto_cashflow'].cumsum()

    # V6: Data quality validation met volatility info
    data_quality = _validate_data_quality(
        income_run_rate, expense_run_rate,
        income_volatility, expense_volatility
    )

    metadata = {
        'portfolio_dso': dso_days,
        'portfolio_dpo': dpo_days,
        'dso_calibrated': calibrated_dso is not None,
        'income_run_rate': income_run_rate,
        'expense_run_rate': expense_run_rate,
        'income_seasonality': income_seasonality,
        'expense_seasonality': expense_seasonality,
        'avg_weekly_income': income_run_rate,
        'avg_weekly_expense': expense_run_rate,
        'n_debiteuren_met_dso': 0,
        # V6: Extended data quality info
        'data_quality': data_quality,
        'income_volatility': income_volatility,
        'expense_volatility': expense_volatility,
        'model_version': 'V6',
    }

    return df, forecast_start_idx, metadata


def _calculate_runrate_seasonality(df_history, data_type: str) -> Tuple[float, Dict[int, float], Dict]:
    """
    STAP 1+2: Bereken RUN RATE (laatste 90 dagen) en SEASONALITY INDEX (volle historie).

    Run Rate = huidige niveau (met outlier filtering en volatility-aware selectie)
    Seasonality Index = patroon per week-van-de-maand (uit volle historie)

    V6 verbeteringen:
    - Dynamische IQR multiplier: bij hoge volatiliteit minder agressief filteren
    - Return volatility stats voor data quality checks
    - Alternatieve run rate voor extreme volatiliteit (75e percentiel)

    Returns:
        Tuple[run_rate, seasonality_index, volatility_stats]
    """
    # Defaults
    default_run_rate = 150000 if data_type == 'income' else 100000
    default_seasonality = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.3, 5: 1.1}
    default_volatility = {'cv': 0.0, 'n_weeks': 0, 'n_outliers_filtered': 0}

    if df_history is None or df_history.empty:
        return default_run_rate, default_seasonality, default_volatility

    # Zoek kolommen
    date_col = next((c for c in ['week_start', 'date', 'datum', 'maand'] if c in df_history.columns), None)
    if data_type == 'income':
        amt_col = next((c for c in ['inkomsten', 'omzet', 'amount', 'revenue'] if c in df_history.columns), None)
    else:
        amt_col = next((c for c in ['uitgaven', 'expenses'] if c in df_history.columns), None)

    if not date_col or not amt_col:
        return default_run_rate, default_seasonality, default_volatility

    df = df_history.copy()
    df['date'] = pd.to_datetime(df[date_col])
    df['amount'] = df[amt_col].fillna(0)

    # =========================================================================
    # STAP 1: RUN RATE (laatste 90 dagen) - V6: dynamische IQR multiplier
    # =========================================================================
    max_date = df['date'].max()
    last_90_days = df[df['date'] > (max_date - timedelta(days=90))]

    volatility_stats = {'cv': 0.0, 'n_weeks': 0, 'n_outliers_filtered': 0}

    if not last_90_days.empty:
        # Groepeer per week, filter weken met 0 eruit
        weekly_sums = last_90_days.groupby(pd.Grouper(key='date', freq='W-MON'))['amount'].sum()
        non_zero_weeks = weekly_sums[weekly_sums > 0]

        if len(non_zero_weeks) > 0:
            volatility_stats['n_weeks'] = len(non_zero_weeks)

            # Bereken CV EERST om IQR multiplier te bepalen
            raw_cv = non_zero_weeks.std() / non_zero_weeks.mean() if non_zero_weeks.mean() > 0 else 0
            volatility_stats['cv'] = float(raw_cv)

            # V6: Dynamische IQR multiplier gebaseerd op volatiliteit
            # Bij hoge CV (projectmatig bedrijf) minder agressief filteren
            if raw_cv > 1.0:
                # Extreem volatiel: gebruik 2.5x IQR (behoud meer grote facturen)
                iqr_multiplier = 2.5
            elif raw_cv > 0.8:
                # Hoog volatiel: gebruik 2.0x IQR
                iqr_multiplier = 2.0
            else:
                # Normaal: standaard 1.5x IQR
                iqr_multiplier = 1.5

            q1 = non_zero_weeks.quantile(0.25)
            q3 = non_zero_weeks.quantile(0.75)
            iqr = q3 - q1

            upper_bound = q3 + iqr_multiplier * iqr
            filtered_weeks = non_zero_weeks[non_zero_weeks <= upper_bound]
            volatility_stats['n_outliers_filtered'] = len(non_zero_weeks) - len(filtered_weeks)

            # V6: Run rate selectie gebaseerd op volatiliteit
            if len(filtered_weeks) >= 3:
                cv = filtered_weeks.std() / filtered_weeks.mean() if filtered_weeks.mean() > 0 else 0

                if raw_cv > 1.0:
                    # Extreem volatiel (projectmatig): gebruik 75e percentiel
                    # Dit vangt grote facturen beter op dan median
                    run_rate = non_zero_weeks.quantile(0.75)
                elif cv > 0.5:
                    # Hoge volatiliteit: gebruik median (robuuster)
                    run_rate = filtered_weeks.median()
                else:
                    # Stabiel patroon: gebruik mean
                    run_rate = filtered_weeks.mean()
            elif len(non_zero_weeks) > 0:
                # Te weinig data na filtering, gebruik median van origineel
                run_rate = non_zero_weeks.median()
            else:
                run_rate = default_run_rate
        else:
            run_rate = default_run_rate
    else:
        run_rate = default_run_rate

    # =========================================================================
    # STAP 2: SEASONALITY INDEX (volle historie, alleen voor patroon)
    # =========================================================================
    df['week_of_month'] = np.ceil(df['date'].dt.day / 7).astype(int).clip(1, 5)

    # Groepeer per week, dan gemiddelde per week-type
    weekly_data = df.groupby([pd.Grouper(key='date', freq='W-MON'), 'week_of_month'])['amount'].sum().reset_index()
    avg_per_type = weekly_data.groupby('week_of_month')['amount'].mean()

    if len(avg_per_type) > 0:
        overall_avg = avg_per_type.mean()
        if overall_avg > 0:
            seasonality_index = (avg_per_type / overall_avg).to_dict()
        else:
            seasonality_index = default_seasonality
    else:
        seasonality_index = default_seasonality

    # Vul ontbrekende weken aan
    for w in range(1, 6):
        if w not in seasonality_index or pd.isna(seasonality_index.get(w)):
            seasonality_index[w] = 1.0

    return float(run_rate), seasonality_index, volatility_stats


def _validate_data_quality(
    income_run_rate: float,
    expense_run_rate: float,
    income_volatility: Dict = None,
    expense_volatility: Dict = None
) -> Dict:
    """
    V6: Valideer datakwaliteit en detecteer anomalieën.

    Returns dict met:
    - is_valid: bool - of de data betrouwbaar genoeg is
    - warnings: list - waarschuwingen over mogelijke problemen
    - confidence: str - 'high', 'medium', 'low', 'very_low'
    - business_type: str - 'stable', 'volatile', 'project_based', 'data_anomaly'
    """
    warnings = []
    confidence = 'high'
    business_type = 'stable'

    income_cv = income_volatility.get('cv', 0) if income_volatility else 0
    expense_cv = expense_volatility.get('cv', 0) if expense_volatility else 0
    max_cv = max(income_cv, expense_cv)

    # Check 1: PCT-type detectie - Income ≈ Expense EXACT is data anomalie
    if income_run_rate > 0 and expense_run_rate > 0:
        ratio = income_run_rate / expense_run_rate
        if 0.98 < ratio < 1.02:
            # Bijna exact gelijk = vrijwel zeker data anomalie (holding/intercompany)
            warnings.append("DATA_ANOMALY: Income = Expense exact - waarschijnlijk holding/intercompany administratie")
            confidence = 'very_low'
            business_type = 'data_anomaly'
        elif 0.95 < ratio < 1.05:
            warnings.append("ANOMALY: Income ≈ Expense - ongebruikelijk patroon, mogelijk data-issue")
            if confidence == 'high':
                confidence = 'low'

    # Check 2: Volatility-based business type detectie (V6)
    if max_cv > 1.0:
        warnings.append(f"PROJECT_BASED: Extreem volatiele cashflow (CV={max_cv:.2f}) - projectmatig bedrijf, forecast minder betrouwbaar")
        if confidence in ['high', 'medium']:
            confidence = 'very_low'
        business_type = 'project_based'
    elif max_cv > 0.8:
        warnings.append(f"HIGH_VOLATILITY: Volatiele cashflow (CV={max_cv:.2f}) - onregelmatig betalingspatroon")
        if confidence == 'high':
            confidence = 'medium'
        business_type = 'volatile'

    # Check 3: Extreem lage waarden kunnen duiden op incomplete data
    if income_run_rate < 1000 and expense_run_rate < 1000:
        warnings.append("LOW_DATA: Zeer lage run rates - mogelijk onvoldoende data")
        confidence = 'very_low'

    # Check 4: Negatieve marge (expense > income * 1.5) is verdacht
    if expense_run_rate > income_run_rate * 1.5 and income_run_rate > 0:
        warnings.append("HIGH_EXPENSE: Uitgaven significant hoger dan inkomsten")
        if confidence == 'high':
            confidence = 'medium'

    # Check 5: Weinig datapunten
    n_weeks = min(
        income_volatility.get('n_weeks', 0) if income_volatility else 0,
        expense_volatility.get('n_weeks', 0) if expense_volatility else 0
    )
    if n_weeks < 6 and n_weeks > 0:
        warnings.append(f"LIMITED_DATA: Slechts {n_weeks} weken data beschikbaar")
        if confidence == 'high':
            confidence = 'medium'

    return {
        'is_valid': len(warnings) == 0,
        'warnings': warnings,
        'confidence': confidence,
        'business_type': business_type,
        'income_cv': income_cv,
        'expense_cv': expense_cv
    }


def _project_with_runrate(run_rate: float, seasonality: Dict[int, float], start_date, weeks: int, dso_days: int) -> Dict[int, float]:
    """
    STAP 3: Projecteer toekomstige weken met Run Rate * Seasonality.
    """
    result = {}

    for week_idx in range(weeks + 8):  # Extra buffer voor DSO
        week_date = start_date + timedelta(weeks=week_idx)
        week_of_month = min(int(np.ceil(week_date.day / 7)), 5)

        # Formule: Run Rate * Seasonality Factor
        season_factor = seasonality.get(week_of_month, 1.0)
        projected_amount = run_rate * season_factor

        # Time shift voor DSO
        shifted_week = week_idx + (dso_days // 7)

        if shifted_week < weeks:
            result[shifted_week] = result.get(shifted_week, 0) + projected_amount

    return result


def _get_real_data(df) -> list:
    """Haal harde data uit openstaande posten."""
    if df is None or df.empty:
        return []

    date_col = next((c for c in ['vervaldatum', 'expected_pay_date'] if c in df.columns), None)
    amt_col = next((c for c in ['openstaand', 'amount', 'bedrag'] if c in df.columns), None)

    if not date_col or not amt_col:
        return []

    result = []
    for _, row in df.iterrows():
        d, a = row[date_col], row[amt_col]
        if pd.notna(d) and pd.notna(a) and a > 0:
            if isinstance(d, str):
                d = pd.to_datetime(d).date()
            elif hasattr(d, 'date'):
                d = d.date()
            result.append((d, float(a)))
    return result


def _sum_in_week(data: list, week_start, week_end) -> float:
    """Sommeer bedragen die in een bepaalde week vallen."""
    return sum(amt for d, amt in data if week_start <= d <= week_end)


def _build_history_rows(df_history, weeks_history) -> list:
    """Bouw historie rijen (realisatie)."""
    if df_history is None or df_history.empty:
        return []

    date_col = next((c for c in ['week_start', 'date', 'datum'] if c in df_history.columns), None)
    income_col = next((c for c in ['inkomsten', 'omzet', 'amount'] if c in df_history.columns), None)

    if not date_col or not income_col:
        return []

    df = df_history.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col, ascending=False).head(weeks_history)
    df = df.sort_values(date_col, ascending=True)

    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        week_offset = -(weeks_history - i)
        ws = row[date_col]
        if hasattr(ws, 'date'):
            ws = ws.date()

        income = float(row[income_col]) if pd.notna(row[income_col]) else 0
        expense = float(row.get('uitgaven', 0)) if pd.notna(row.get('uitgaven', 0)) else 0
        netto = income - expense

        rows.append({
            'week_nummer': week_offset,
            'week_label': f'Week {week_offset}',
            'week_start': ws,
            'week_eind': ws + timedelta(days=6),
            'inkomsten_debiteuren': income,
            'uitgaven_crediteuren': expense,
            'uitgaven_salarissen': 0,
            'uitgaven_overig': 0,
            'netto_cashflow': netto,
            'is_realisatie': True,
            'data_type': 'Realisatie',
        })

    return rows


def run_walk_forward_backtest(*args, **kwargs):
    return {'overall_mape': None, 'bias': None}
