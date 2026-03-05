"""
FORECAST MODEL V7 — Structuur x Volume x Realiteit
====================================================
3-pilaren liquiditeitsprognose gebaseerd op het document
"Datagedreven Liquiditeitsprognose v3".

Pilaren:
1. REALITEIT (week 0-3): Harde ERP-feiten domineren
   - Open debiteuren + DSO-correctie per relatie
   - Open crediteuren + DPO-correctie
   - Banksaldo
   - Geplande salarissen
   - Bekende BTW-verplichtingen

2. STRUCTUUR (timing uit 12+ maanden historie):
   - Maand-seizoensindex (12 datapunten)
   - Week-van-maand patroon (5 datapunten)
   - BTW-ritme (kwartaal/maandelijks)
   - Loonkosten-seizoen (vakantiegeld piek)
   - DSO/DPO distributie per relatie

3. VOLUME (hoeveel, uit budget of run rate):
   - Budget/forecast omzet (als beschikbaar)
   - Run rate inkomsten (12 mnd gewogen)
   - Run rate uitgaven (12 mnd gewogen)
   - Orderportefeuille waarde

Blending:
  Week 0-3:  Realiteit 100%
  Week 4-8:  Sigmoid blend Realiteit -> Structuur x Volume
  Week 8+:   Structuur x Volume 100%
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import calendar


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class BTWRhythm:
    """BTW-aangifteritme."""
    frequency: str              # 'monthly' | 'quarterly'
    avg_amount: float
    payment_months: List[int]   # maanden waarin BTW betaald wordt
    confidence: float


@dataclass
class SalaryProfile:
    """Salarispatroon met pieken (vakantiegeld, 13e maand)."""
    monthly_base: float
    peak_months: Dict[int, float]   # {5: 2.0, 12: 1.5}
    total_annual: float


@dataclass
class StructuurProfile:
    """Volledig structuurprofiel uit historische data."""
    season_month_index: Dict[int, float]    # maand 1-12
    season_week_index: Dict[int, float]     # week-van-maand 1-5
    btw_rhythm: BTWRhythm
    salary_profile: SalaryProfile
    dso_distribution: Dict[str, float]      # debiteur -> gem DSO dagen
    dpo_distribution: Dict[str, float]      # crediteur -> gem DPO dagen
    order_to_invoice_days: Optional[float]
    history_months: int


# =============================================================================
# Blending
# =============================================================================

BLEND_REAL_END = 3          # Week 0-3: 100% realiteit
BLEND_TRANSITION_END = 8    # Week 8+:  100% structuur x volume


def _sigmoid_blend(week_idx: int) -> float:
    """Sigmoid blend: 1.0 = full realiteit, 0.0 = full struct x vol."""
    if week_idx <= BLEND_REAL_END:
        return 1.0
    if week_idx >= BLEND_TRANSITION_END:
        return 0.0
    t = (week_idx - BLEND_REAL_END) / (BLEND_TRANSITION_END - BLEND_REAL_END)
    return 1.0 / (1.0 + np.exp(6 * (t - 0.5)))


def _week_contains_month_end(week_start: date) -> Optional[date]:
    """Check of een week het einde van de maand bevat, geef die datum terug."""
    for d in range(7):
        check = week_start + timedelta(days=d)
        last_day = calendar.monthrange(check.year, check.month)[1]
        if check.day == last_day:
            return check
    return None


# =============================================================================
# PILAAR 1: REALITEIT
# =============================================================================

def _build_realiteit(
    debiteuren: pd.DataFrame,
    crediteuren: pd.DataFrame,
    salarissen: pd.DataFrame,
    btw_data: pd.DataFrame,
    dso_days: float,
    dpo_days: float,
    reference_date: date,
    weeks: int,
) -> Dict[int, Dict[str, float]]:
    """Harde ERP-feiten per week: open AR/AP met DSO/DPO correctie."""
    result = {w: {'inkomsten': 0.0, 'uitgaven': 0.0, 'salarissen': 0.0, 'btw': 0.0}
              for w in range(weeks)}

    # --- Debiteuren: open facturen + DSO shift ---
    if not debiteuren.empty:
        date_col = next((c for c in ['vervaldatum', 'expected_pay_date'] if c in debiteuren.columns), None)
        amt_col = next((c for c in ['openstaand', 'bedrag_excl_btw'] if c in debiteuren.columns), None)

        if date_col and amt_col:
            for _, row in debiteuren.iterrows():
                d, a = row[date_col], row[amt_col]
                if pd.isna(d) or pd.isna(a) or float(a) <= 0:
                    continue
                if isinstance(d, str):
                    d = pd.to_datetime(d).date()
                elif hasattr(d, 'date'):
                    d = d.date()

                expected = d + timedelta(days=max(0, dso_days))
                w_idx = (expected - reference_date).days // 7
                if 0 <= w_idx < weeks:
                    result[w_idx]['inkomsten'] += float(a)

    # --- Crediteuren: open facturen + DPO shift ---
    if not crediteuren.empty:
        date_col = next((c for c in ['vervaldatum'] if c in crediteuren.columns), None)
        amt_col = next((c for c in ['openstaand', 'bedrag_excl_btw'] if c in crediteuren.columns), None)

        if date_col and amt_col:
            for _, row in crediteuren.iterrows():
                d, a = row[date_col], row[amt_col]
                if pd.isna(d) or pd.isna(a) or float(a) <= 0:
                    continue
                if isinstance(d, str):
                    d = pd.to_datetime(d).date()
                elif hasattr(d, 'date'):
                    d = d.date()

                expected = d + timedelta(days=max(0, dpo_days))
                w_idx = (expected - reference_date).days // 7
                if 0 <= w_idx < weeks:
                    result[w_idx]['uitgaven'] += float(a)

    # --- Geplande salarissen (als bekend) ---
    if not salarissen.empty and 'betaaldatum' in salarissen.columns:
        for _, row in salarissen.iterrows():
            bd = row['betaaldatum']
            if pd.isna(bd):
                continue
            if isinstance(bd, str):
                bd = pd.to_datetime(bd).date()
            elif hasattr(bd, 'date'):
                bd = bd.date()
            w_idx = (bd - reference_date).days // 7
            if 0 <= w_idx < weeks:
                result[w_idx]['salarissen'] += float(row.get('bedrag', 0))

    # --- Bekende BTW-verplichtingen (recente maanden met bedrag) ---
    if not btw_data.empty and 'maand' in btw_data.columns:
        df_btw = btw_data.copy()
        df_btw['maand'] = pd.to_datetime(df_btw['maand'])
        df_btw['btw_bedrag'] = pd.to_numeric(df_btw['btw_bedrag'], errors='coerce').fillna(0)
        # Alleen toekomstige BTW-verplichtingen
        future_btw = df_btw[df_btw['maand'] >= pd.Timestamp(reference_date)]
        for _, row in future_btw.iterrows():
            btw_date = row['maand']
            if hasattr(btw_date, 'date'):
                btw_date = btw_date.date()
            w_idx = (btw_date - reference_date).days // 7
            if 0 <= w_idx < weeks and abs(row['btw_bedrag']) > 0:
                result[w_idx]['btw'] += abs(float(row['btw_bedrag']))

    return result


# =============================================================================
# PILAAR 2: STRUCTUUR
# =============================================================================

def _build_structuur(
    hist_cashflow: pd.DataFrame,
    btw_history: pd.DataFrame,
    salaris_history: pd.DataFrame,
    betaalgedrag_deb: pd.DataFrame,
    betaalgedrag_cred: pd.DataFrame,
) -> StructuurProfile:
    """Analyseer 12+ maanden historie, extraheer timing-patronen."""
    season_month = _calc_month_seasonality(hist_cashflow)
    season_week = _calc_week_of_month_pattern(hist_cashflow)
    btw_rhythm = _detect_btw_rhythm(btw_history)
    salary_profile = _detect_salary_seasonality(salaris_history)

    # DSO distributie per debiteur
    dso_dist = {}
    if not betaalgedrag_deb.empty and 'debiteur_code' in betaalgedrag_deb.columns:
        for _, row in betaalgedrag_deb.iterrows():
            dso_dist[row['debiteur_code']] = float(row.get('gem_dagen_tot_betaling', 35))

    # DPO distributie per crediteur
    dpo_dist = {}
    if not betaalgedrag_cred.empty and 'crediteur_code' in betaalgedrag_cred.columns:
        for _, row in betaalgedrag_cred.iterrows():
            dpo_dist[row['crediteur_code']] = float(row.get('gem_dagen_tot_betaling', 30))

    # Historie-lengte bepalen
    history_months = 0
    if not hist_cashflow.empty:
        date_col = next((c for c in ['week_start', 'date', 'datum'] if c in hist_cashflow.columns), None)
        if date_col:
            dates = pd.to_datetime(hist_cashflow[date_col])
            history_months = max(1, (dates.max() - dates.min()).days // 30)

    return StructuurProfile(
        season_month_index=season_month,
        season_week_index=season_week,
        btw_rhythm=btw_rhythm,
        salary_profile=salary_profile,
        dso_distribution=dso_dist,
        dpo_distribution=dpo_dist,
        order_to_invoice_days=None,
        history_months=history_months,
    )


def _calc_month_seasonality(hist_cf: pd.DataFrame) -> Dict[int, float]:
    """Maand-seizoensindex (12 datapunten) uit historische cashflow."""
    default = {m: 1.0 for m in range(1, 13)}
    if hist_cf is None or hist_cf.empty:
        return default

    date_col = next((c for c in ['week_start', 'date', 'datum'] if c in hist_cf.columns), None)
    income_col = next((c for c in ['inkomsten', 'omzet', 'netto'] if c in hist_cf.columns), None)
    if not date_col or not income_col:
        return default

    df = hist_cf.copy()
    df['_date'] = pd.to_datetime(df[date_col])
    df['_month'] = df['_date'].dt.month
    df['_amount'] = pd.to_numeric(df[income_col], errors='coerce').fillna(0)

    monthly_avg = df.groupby('_month')['_amount'].mean()
    overall_avg = monthly_avg.mean()
    if overall_avg <= 0:
        return default

    result = {}
    for m in range(1, 13):
        result[m] = float(monthly_avg.get(m, overall_avg) / overall_avg) if m in monthly_avg.index else 1.0
    return result


def _calc_week_of_month_pattern(hist_cf: pd.DataFrame) -> Dict[int, float]:
    """Week-van-maand patroon (5 datapunten)."""
    default = {w: 1.0 for w in range(1, 6)}
    if hist_cf is None or hist_cf.empty:
        return default

    date_col = next((c for c in ['week_start', 'date', 'datum'] if c in hist_cf.columns), None)
    income_col = next((c for c in ['inkomsten', 'omzet', 'netto'] if c in hist_cf.columns), None)
    if not date_col or not income_col:
        return default

    df = hist_cf.copy()
    df['_date'] = pd.to_datetime(df[date_col])
    df['_wom'] = np.ceil(df['_date'].dt.day / 7).astype(int).clip(1, 5)
    df['_amount'] = pd.to_numeric(df[income_col], errors='coerce').fillna(0)

    wom_avg = df.groupby('_wom')['_amount'].mean()
    overall_avg = wom_avg.mean()
    if overall_avg <= 0:
        return default

    return {w: float(wom_avg.get(w, overall_avg) / overall_avg) for w in range(1, 6)}


def _detect_btw_rhythm(btw_data: pd.DataFrame) -> BTWRhythm:
    """Detecteer BTW-ritme: maandelijks of kwartaal."""
    default = BTWRhythm(frequency='quarterly', avg_amount=0.0,
                        payment_months=[1, 4, 7, 10], confidence=0.0)
    if btw_data is None or btw_data.empty:
        return default
    if 'maand' not in btw_data.columns or 'btw_bedrag' not in btw_data.columns:
        return default

    df = btw_data.copy()
    df['maand'] = pd.to_datetime(df['maand'])
    df['month_num'] = df['maand'].dt.month
    df['btw_bedrag'] = pd.to_numeric(df['btw_bedrag'], errors='coerce').fillna(0)

    active = df[df['btw_bedrag'].abs() > 100]
    if active.empty:
        return default

    month_counts = active['month_num'].value_counts()
    # Kwartaal: BTW wordt betaald in de maand NA het kwartaal
    quarterly_months = {1, 4, 7, 10}
    q_count = sum(1 for m in month_counts.index if m in quarterly_months)
    o_count = sum(1 for m in month_counts.index if m not in quarterly_months)

    if q_count > o_count and len(active) <= 12:
        frequency = 'quarterly'
        payment_months = sorted(quarterly_months)
    else:
        frequency = 'monthly'
        payment_months = list(range(1, 13))

    avg_amount = float(active['btw_bedrag'].abs().mean())
    confidence = min(1.0, len(active) / 8)

    return BTWRhythm(frequency=frequency, avg_amount=avg_amount,
                     payment_months=payment_months, confidence=confidence)


def _detect_salary_seasonality(salaris_data: pd.DataFrame) -> SalaryProfile:
    """Detecteer salarisprofiel: basis + pieken (vakantiegeld, 13e maand)."""
    default = SalaryProfile(monthly_base=0.0, peak_months={}, total_annual=0.0)
    if salaris_data is None or salaris_data.empty:
        return default
    if 'maand' not in salaris_data.columns or 'salaris_bedrag' not in salaris_data.columns:
        return default

    df = salaris_data.copy()
    df['maand'] = pd.to_datetime(df['maand'])
    df['month_num'] = df['maand'].dt.month
    df['bedrag'] = pd.to_numeric(df['salaris_bedrag'], errors='coerce').fillna(0).abs()

    if df['bedrag'].sum() == 0:
        return default

    monthly_avg = df.groupby('month_num')['bedrag'].mean()
    if monthly_avg.empty:
        return default

    # Basis = mediaan (robuust tegen pieken)
    base = float(monthly_avg.median())

    # Pieken: maanden met > 1.3x basis
    peak_months = {}
    for m, val in monthly_avg.items():
        ratio = val / base if base > 0 else 1.0
        if ratio > 1.3:
            peak_months[int(m)] = round(float(ratio), 2)

    return SalaryProfile(
        monthly_base=base,
        peak_months=peak_months,
        total_annual=float(monthly_avg.sum()),
    )


# =============================================================================
# PILAAR 3: VOLUME
# =============================================================================

def _build_volume(
    hist_cashflow: pd.DataFrame,
    budgetten: pd.DataFrame,
    orderportefeuille: pd.DataFrame,
    structuur: StructuurProfile,
    reference_date: date,
    weeks: int,
) -> Dict[int, Dict[str, float]]:
    """Bouw wekelijkse volume-schattingen uit budget of gewogen run rate."""
    result = {}

    # --- Probeer budget eerst ---
    weekly_income, weekly_expense = 0.0, 0.0
    has_budget = False

    if budgetten is not None and not budgetten.empty:
        if 'rubriek_code' in budgetten.columns and 'budget_bedrag' in budgetten.columns:
            bud = budgetten.copy()
            bud['budget_bedrag'] = pd.to_numeric(bud['budget_bedrag'], errors='coerce').fillna(0)
            rc = bud['rubriek_code'].astype(str)

            income_budget = bud[rc.str.startswith(('8', '9'))]['budget_bedrag'].sum()
            expense_budget = bud[rc.str.startswith(('4', '5', '6', '7'))]['budget_bedrag'].sum()

            if income_budget > 0:
                weekly_income = income_budget / 52
                has_budget = True
            if expense_budget > 0:
                weekly_expense = abs(expense_budget) / 52
                has_budget = True

    # --- Fallback: gewogen run rate 12 maanden ---
    if not has_budget:
        weekly_income, weekly_expense = _calc_weighted_run_rate(hist_cashflow)

    # --- Orderportefeuille boost ---
    order_boost = 0.0
    if orderportefeuille is not None and not orderportefeuille.empty:
        if 'orderbedrag' in orderportefeuille.columns:
            total = pd.to_numeric(orderportefeuille['orderbedrag'], errors='coerce').sum()
            order_boost = total / max(weeks, 1) * 0.1  # conservatief 10%

    # --- Pas structuur-patronen toe op volume ---
    for w in range(weeks):
        week_date = reference_date + timedelta(weeks=w)
        month = week_date.month
        wom = min(int(np.ceil(week_date.day / 7)), 5)

        m_factor = structuur.season_month_index.get(month, 1.0)
        w_factor = structuur.season_week_index.get(wom, 1.0)
        # Gedempt combineren (sqrt) om extreme uitschieters te voorkomen
        combined = np.sqrt(m_factor * w_factor)

        result[w] = {
            'inkomsten': (weekly_income + order_boost) * combined,
            'uitgaven': weekly_expense * combined,
        }

    return result


def _calc_weighted_run_rate(hist_cf: pd.DataFrame) -> Tuple[float, float]:
    """Exponentieel gewogen run rate uit historische cashflow (recent weegt zwaarder)."""
    if hist_cf is None or hist_cf.empty:
        return (0.0, 0.0)

    date_col = next((c for c in ['week_start', 'date', 'datum'] if c in hist_cf.columns), None)
    income_col = next((c for c in ['inkomsten', 'omzet'] if c in hist_cf.columns), None)
    expense_col = next((c for c in ['uitgaven', 'expenses'] if c in hist_cf.columns), None)
    if not date_col:
        return (0.0, 0.0)

    df = hist_cf.copy()
    df['_date'] = pd.to_datetime(df[date_col])
    df = df.sort_values('_date')
    n = len(df)
    if n == 0:
        return (0.0, 0.0)

    # Half-life ~13 weken: recent data weegt ~2x meer dan 6 maanden geleden
    weights = np.exp(-0.05 * np.arange(n)[::-1])
    weights /= weights.sum()

    inc = 0.0
    exp = 0.0
    if income_col and income_col in df.columns:
        vals = pd.to_numeric(df[income_col], errors='coerce').fillna(0).values
        inc = max(float(np.dot(vals, weights)), 0)
    if expense_col and expense_col in df.columns:
        vals = pd.to_numeric(df[expense_col], errors='coerce').fillna(0).values
        exp = max(float(np.dot(vals, weights)), 0)

    return inc, exp


# =============================================================================
# BLEND — Prioriteitshierarchie
# =============================================================================

def _blend_pillars(
    realiteit: Dict[int, Dict[str, float]],
    volume: Dict[int, Dict[str, float]],
    structuur: StructuurProfile,
    reference_date: date,
    weeks: int,
) -> Dict[int, Dict[str, float]]:
    """Blend realiteit en structuur x volume per week via sigmoid."""
    result = {}

    for w in range(weeks):
        real_w = _sigmoid_blend(w)
        sv_w = 1.0 - real_w

        real = realiteit.get(w, {'inkomsten': 0, 'uitgaven': 0, 'salarissen': 0, 'btw': 0})
        vol = volume.get(w, {'inkomsten': 0, 'uitgaven': 0})

        # Blend inkomsten: alleen als realiteit data heeft
        r_inc = real.get('inkomsten', 0)
        v_inc = vol.get('inkomsten', 0)
        inkomsten = (r_inc * real_w + v_inc * sv_w) if r_inc > 0 else v_inc

        # Blend uitgaven
        r_exp = real.get('uitgaven', 0)
        v_exp = vol.get('uitgaven', 0)
        uitgaven = (r_exp * real_w + v_exp * sv_w) if r_exp > 0 else v_exp

        # --- Salarissen: realiteit of structuurprofiel ---
        salarissen = real.get('salarissen', 0)
        if salarissen == 0 and structuur.salary_profile.monthly_base > 0:
            week_start = reference_date + timedelta(weeks=w)
            month_end = _week_contains_month_end(week_start)
            if month_end is not None:
                month = month_end.month
                peak = structuur.salary_profile.peak_months.get(month, 1.0)
                salarissen = structuur.salary_profile.monthly_base * peak

        # --- BTW: realiteit of structuurritme ---
        btw = real.get('btw', 0)
        if btw == 0 and structuur.btw_rhythm.avg_amount > 0:
            week_start = reference_date + timedelta(weeks=w)
            month_end = _week_contains_month_end(week_start)
            if month_end is not None and month_end.month in structuur.btw_rhythm.payment_months:
                btw = structuur.btw_rhythm.avg_amount

        result[w] = {
            'inkomsten': inkomsten,
            'uitgaven': uitgaven,
            'salarissen': salarissen,
            'btw': btw,
            'pilaar_realiteit': real_w,
            'pilaar_structuur': sv_w * 0.5,
            'pilaar_volume': sv_w * 0.5,
        }

    return result


# =============================================================================
# HOOFDFUNCTIE
# =============================================================================

def create_forecast_v7(
    data: Dict[str, pd.DataFrame],
    weeks_forecast: int = 13,
    weeks_history: int = 13,
    reference_date=None,
    calibrated_dso: Optional[float] = None,
    calibrated_dpo: Optional[float] = None,
) -> Tuple[pd.DataFrame, int, Dict]:
    """
    V7 forecast: Structuur x Volume x Realiteit.

    Args:
        data: Dict met DataFrames (zie keys hieronder)
        weeks_forecast: Weken vooruit
        weeks_history: Weken historie
        reference_date: Peildatum (default: vandaag)
        calibrated_dso: Gecalibreerde DSO in dagen
        calibrated_dpo: Gecalibreerde DPO in dagen

    Returns:
        (forecast_df, forecast_start_idx, metadata)
        Backward compatible met V6. Extra kolommen: pilaar_realiteit/structuur/volume
    """
    if reference_date is None:
        reference_date = datetime.now().date()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    # Extract data
    hist_cf = data.get('historische_cashflow', pd.DataFrame())
    debiteuren = data.get('debiteuren', pd.DataFrame())
    crediteuren = data.get('crediteuren', pd.DataFrame())
    banksaldo = data.get('banksaldo', pd.DataFrame())
    btw_data = data.get('btw_aangifteregels', pd.DataFrame())
    salaris_data = data.get('salarishistorie', pd.DataFrame())
    budgetten = data.get('budgetten', pd.DataFrame())
    orders = data.get('orderportefeuille', pd.DataFrame())
    betaalgedrag_deb = data.get('betaalgedrag_debiteuren', pd.DataFrame())
    betaalgedrag_cred = data.get('betaalgedrag_crediteuren', pd.DataFrame())
    salarissen = data.get('geplande_salarissen', pd.DataFrame())

    # Startsaldo
    start_balance = 0.0
    if not banksaldo.empty and 'saldo' in banksaldo.columns:
        start_balance = float(banksaldo['saldo'].sum())

    # DSO/DPO
    dso_days = calibrated_dso if calibrated_dso is not None else 35.0
    dpo_days = calibrated_dpo if calibrated_dpo is not None else 0.0

    # =========================================================================
    # PILAAR 1: REALITEIT
    # =========================================================================
    realiteit = _build_realiteit(
        debiteuren, crediteuren, salarissen, btw_data,
        dso_days, dpo_days, reference_date, weeks_forecast,
    )

    # =========================================================================
    # PILAAR 2: STRUCTUUR
    # =========================================================================
    structuur = _build_structuur(
        hist_cf, btw_data, salaris_data, betaalgedrag_deb, betaalgedrag_cred,
    )

    # =========================================================================
    # PILAAR 3: VOLUME
    # =========================================================================
    volume = _build_volume(
        hist_cf, budgetten, orders, structuur, reference_date, weeks_forecast,
    )

    # =========================================================================
    # BLEND
    # =========================================================================
    blended = _blend_pillars(
        realiteit, volume, structuur, reference_date, weeks_forecast,
    )

    # =========================================================================
    # OUTPUT (backward compatible met V6)
    # =========================================================================
    rows = []

    # Historie (realisatie)
    hist_rows = _build_history_rows(hist_cf, weeks_history)
    rows.extend(hist_rows)
    forecast_start_idx = len(hist_rows)

    # Forecast weken
    for week_idx in range(weeks_forecast):
        week_start = reference_date + timedelta(weeks=week_idx)
        week_end = week_start + timedelta(days=6)

        wd = blended.get(week_idx, {})
        inkomsten = wd.get('inkomsten', 0)
        uitgaven = wd.get('uitgaven', 0)
        salarissen_w = wd.get('salarissen', 0)
        btw_w = wd.get('btw', 0)
        netto = inkomsten - (uitgaven + salarissen_w + btw_w)

        rows.append({
            'week_nummer': week_idx,
            'week_label': 'Vandaag' if week_idx == 0 else f'Week {week_idx}',
            'week_start': week_start,
            'week_eind': week_end,
            'inkomsten_debiteuren': inkomsten,
            'uitgaven_crediteuren': uitgaven,
            'uitgaven_salarissen': salarissen_w,
            'uitgaven_overig': btw_w,
            'netto_cashflow': netto,
            'is_realisatie': False,
            'data_type': 'Vandaag' if week_idx == 0 else 'Prognose',
            'pilaar_realiteit': wd.get('pilaar_realiteit', 0),
            'pilaar_structuur': wd.get('pilaar_structuur', 0),
            'pilaar_volume': wd.get('pilaar_volume', 0),
        })

    df = pd.DataFrame(rows)
    if 'netto_cashflow' in df.columns:
        df['cumulatief_saldo'] = start_balance + df['netto_cashflow'].cumsum()

    # Metadata
    income_rate, expense_rate = _calc_weighted_run_rate(hist_cf)
    data_quality = _validate_v7_quality(data, structuur)

    metadata = {
        'portfolio_dso': dso_days,
        'portfolio_dpo': dpo_days,
        'dso_calibrated': calibrated_dso is not None,
        'income_run_rate': income_rate,
        'expense_run_rate': expense_rate,
        'avg_weekly_income': income_rate,
        'avg_weekly_expense': expense_rate,
        'n_debiteuren_met_dso': len(structuur.dso_distribution),
        'model_version': 'V7',
        'data_quality': data_quality,
        'structuur_profile': {
            'history_months': structuur.history_months,
            'btw_frequency': structuur.btw_rhythm.frequency,
            'btw_avg_amount': structuur.btw_rhythm.avg_amount,
            'btw_confidence': structuur.btw_rhythm.confidence,
            'salary_base': structuur.salary_profile.monthly_base,
            'salary_peaks': structuur.salary_profile.peak_months,
            'salary_annual': structuur.salary_profile.total_annual,
            'n_debiteuren_dso': len(structuur.dso_distribution),
            'n_crediteuren_dpo': len(structuur.dpo_distribution),
            'season_month': structuur.season_month_index,
            'season_week': structuur.season_week_index,
        },
        'sources_used': {
            'historische_cashflow': not hist_cf.empty,
            'debiteuren': not debiteuren.empty,
            'crediteuren': not crediteuren.empty,
            'banksaldo': not banksaldo.empty,
            'btw_aangifteregels': not btw_data.empty,
            'salarishistorie': not salaris_data.empty,
            'budgetten': not budgetten.empty,
            'orderportefeuille': not orders.empty,
            'betaalgedrag_debiteuren': not betaalgedrag_deb.empty,
            'betaalgedrag_crediteuren': not betaalgedrag_cred.empty,
        },
    }

    return df, forecast_start_idx, metadata


# =============================================================================
# Data quality
# =============================================================================

def _validate_v7_quality(data: Dict[str, pd.DataFrame], structuur: StructuurProfile) -> Dict:
    """Valideer datakwaliteit voor V7."""
    warnings = []
    confidence = 'high'

    if structuur.history_months < 6:
        warnings.append(f"LIMITED_HISTORY: {structuur.history_months} maanden (min 12 aanbevolen)")
        confidence = 'low'
    elif structuur.history_months < 12:
        warnings.append(f"SHORT_HISTORY: {structuur.history_months} maanden (12+ aanbevolen)")
        if confidence == 'high':
            confidence = 'medium'

    missing_core = [k for k in ['historische_cashflow', 'debiteuren', 'crediteuren', 'banksaldo']
                    if data.get(k, pd.DataFrame()).empty]
    if missing_core:
        warnings.append(f"MISSING_CORE: {', '.join(missing_core)}")
        confidence = 'very_low'

    missing_v7 = [k for k in ['btw_aangifteregels', 'salarishistorie']
                  if data.get(k, pd.DataFrame()).empty]
    if missing_v7:
        warnings.append(f"OPTIONAL_MISSING: {', '.join(missing_v7)}")

    if structuur.btw_rhythm.confidence < 0.5:
        warnings.append("LOW_BTW_CONFIDENCE: BTW-ritme niet betrouwbaar")

    return {
        'is_valid': not any('MISSING_CORE' in w for w in warnings),
        'warnings': warnings,
        'confidence': confidence,
        'history_months': structuur.history_months,
    }


# =============================================================================
# Historie rijen (identiek aan V6 voor compatibiliteit)
# =============================================================================

def _build_history_rows(df_history: pd.DataFrame, weeks_history: int) -> list:
    """Bouw historie-rijen (realisatie)."""
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
            'pilaar_realiteit': 1.0,
            'pilaar_structuur': 0.0,
            'pilaar_volume': 0.0,
        })

    return rows
