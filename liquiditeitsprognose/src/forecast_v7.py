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


@dataclass
class BusinessProfile:
    """Bedrijfstype-classificatie op basis van cashflow-patronen."""
    business_type: str          # 'project_based' | 'stable' | 'mixed'
    income_cv: float            # coefficient of variation (hoe volatiel)
    cost_ratio: float           # uitgaven / inkomsten (historisch)
    avg_invoice_size: float     # gemiddelde factuurgrootte
    income_frequency: float     # gem. aantal inkomstenweken per maand met significante ontvangst
    blend_extension: int        # extra weken Realiteit voor dit bedrijfstype


@dataclass
class ProjectPipeline:
    """Projectpijplijn: verwachte toekomstige inkomsten per week."""
    weekly_income: Dict[int, float]     # week -> verwacht bedrag
    weekly_confidence: Dict[int, float] # week -> betrouwbaarheid 0-1
    sources: Dict[int, str]             # week -> bron ('service_order'|'order'|'pattern')
    total_pipeline_value: float
    coverage_weeks: int                 # hoeveel weken hebben pipeline-data


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
    btw_prognose: pd.DataFrame = None,
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

    # --- SSM Prognose BTW (netto BTW-positie uit DWH) ---
    # Overschrijft de bovenstaande ritme-schatting met werkelijke prognose als beschikbaar
    if btw_prognose is not None and not btw_prognose.empty:
        if 'btw_af_te_dragen' in btw_prognose.columns and 'btw_te_vorderen' in btw_prognose.columns:
            netto_af = pd.to_numeric(btw_prognose['btw_af_te_dragen'], errors='coerce').sum()
            netto_vorderen = pd.to_numeric(btw_prognose['btw_te_vorderen'], errors='coerce').sum()
            netto_btw = max(0, netto_af - netto_vorderen)
            if netto_btw > 0:
                # Verdeel over eerstvolgende BTW-betaalweek (week met maandeinde)
                for w in range(weeks):
                    week_start = reference_date + timedelta(weeks=w)
                    month_end = _week_contains_month_end(week_start)
                    if month_end is not None:
                        # Eerste maandeinde = eerstvolgende BTW-betaling
                        result[w]['btw'] = max(result[w]['btw'], netto_btw)
                        break

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
    service_contract_intake: pd.DataFrame = None,
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

    # --- Recurring revenue uit servicecontracten ---
    recurring_revenue_weekly = 0.0
    if service_contract_intake is not None and not service_contract_intake.empty:
        # Pak de meest recente rij voor actuele jaarwaarde
        if 'jaarbedrag_doorlopend' in service_contract_intake.columns:
            doorlopend = pd.to_numeric(
                service_contract_intake['jaarbedrag_doorlopend'], errors='coerce'
            ).dropna()
            if len(doorlopend) > 0:
                # Meest recente jaarwaarde → wekelijks
                recurring_revenue_weekly += float(doorlopend.iloc[0]) / 52
        if 'jaarbedrag_eindig' in service_contract_intake.columns:
            eindig = pd.to_numeric(
                service_contract_intake['jaarbedrag_eindig'], errors='coerce'
            ).dropna()
            if len(eindig) > 0:
                recurring_revenue_weekly += float(eindig.iloc[0]) / 52

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
            'inkomsten': (weekly_income + order_boost) * combined + recurring_revenue_weekly,
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
# BEDRIJFSTYPE DETECTIE
# =============================================================================

def _detect_business_type(hist_cf: pd.DataFrame, debiteuren: pd.DataFrame) -> BusinessProfile:
    """
    Classificeer bedrijfstype op basis van cashflow-patronen.

    Project-based: hoge volatiliteit, grote pieken, onregelmatige facturatie
    Stable: lage volatiliteit, regelmatige inkomsten
    Mixed: tussenin
    """
    default = BusinessProfile(
        business_type='mixed', income_cv=0.5, cost_ratio=0.85,
        avg_invoice_size=0.0, income_frequency=3.0, blend_extension=0,
    )

    if hist_cf is None or hist_cf.empty:
        return default

    income_col = next((c for c in ['inkomsten', 'omzet'] if c in hist_cf.columns), None)
    expense_col = next((c for c in ['uitgaven', 'expenses'] if c in hist_cf.columns), None)
    if not income_col:
        return default

    incomes = pd.to_numeric(hist_cf[income_col], errors='coerce').fillna(0)
    incomes_pos = incomes[incomes > 0]

    if len(incomes_pos) < 4:
        return default

    # Coefficient of variation
    cv = float(incomes_pos.std() / incomes_pos.mean()) if incomes_pos.mean() > 0 else 0.5

    # Kostenratio
    cost_ratio = 0.85
    if expense_col and expense_col in hist_cf.columns:
        expenses = pd.to_numeric(hist_cf[expense_col], errors='coerce').fillna(0)
        total_exp = expenses.sum()
        total_inc = incomes.sum()
        if total_inc > 0:
            cost_ratio = min(1.2, max(0.3, total_exp / total_inc))

    # Gemiddelde factuurgrootte uit debiteuren
    avg_invoice = 0.0
    if not debiteuren.empty:
        amt_col = next((c for c in ['openstaand', 'bedrag_excl_btw'] if c in debiteuren.columns), None)
        if amt_col:
            amounts = pd.to_numeric(debiteuren[amt_col], errors='coerce').dropna()
            avg_invoice = float(amounts.mean()) if len(amounts) > 0 else 0.0

    # Facturatiefrequentie: hoeveel weken per maand hebben significante inkomsten?
    threshold = incomes_pos.median() * 0.3 if len(incomes_pos) > 0 else 0
    significant_weeks = (incomes > threshold).sum()
    total_weeks = len(incomes)
    freq = (significant_weeks / total_weeks) * 4.33 if total_weeks > 0 else 3.0

    # Classificatie
    # CV > 0.5 duidt op significante volatiliteit (projectmatig)
    # Frequentie < 3.5 betekent niet elke week significante inkomsten
    if cv > 0.5:
        btype = 'project_based'
        blend_ext = 4  # Extra 4 weken Realiteit
    elif cv < 0.25 and freq > 3.5:
        btype = 'stable'
        blend_ext = 0
    else:
        btype = 'mixed'
        blend_ext = 2

    return BusinessProfile(
        business_type=btype,
        income_cv=cv,
        cost_ratio=cost_ratio,
        avg_invoice_size=avg_invoice,
        income_frequency=freq,
        blend_extension=blend_ext,
    )


# =============================================================================
# PROJECTPIJPLIJN (Facturering prioriteitshierarchie v3)
# =============================================================================

def _build_project_pipeline(
    service_orders: pd.DataFrame,
    orderportefeuille: pd.DataFrame,
    dso_days: float,
    reference_date: date,
    weeks: int,
    orderregels_periodiek: pd.DataFrame = None,
    orderregels_eenmalig: pd.DataFrame = None,
    abonnementen: pd.DataFrame = None,
) -> ProjectPipeline:
    """
    Bouw projectpijplijn: verwachte inkomsten per week uit bekende toekomstige facturatie.

    Facturering prioriteitshiërarchie (v3 document, uitgebreid):
    1. Service orders met verwachte_factuurdatum (hoogste betrouwbaarheid, 0.85)
    2. Eenmalige orderregels met FactureerDatum + status Opdracht (0.80)
    3. Periodieke orderregels met geplande_factuurdatum (0.90 — contractueel)
    4. Abonnementen met facturatie_plandatum (0.92 — doorlopend contract)
    5. Orders met opleverdatum bij status Opdracht/Actief (0.70)
    6. Overige orders → gespreid over doorlooptijd (0.40)
    """
    weekly_income = {w: 0.0 for w in range(weeks)}
    weekly_confidence = {w: 0.0 for w in range(weeks)}
    sources = {}
    total_value = 0.0
    coverage = 0

    def _add_to_week(w_idx: int, amount: float, conf: float, source: str):
        """Helper: voeg bedrag toe aan week, track confidence en bron."""
        nonlocal total_value
        if 0 <= w_idx < weeks and amount > 0:
            weekly_income[w_idx] += amount
            weekly_confidence[w_idx] = max(weekly_confidence[w_idx], conf)
            sources.setdefault(w_idx, source)
            total_value += amount

    def _parse_date(d):
        """Parse date naar date object."""
        if pd.isna(d):
            return None
        if isinstance(d, str):
            return pd.to_datetime(d).date()
        elif hasattr(d, 'date'):
            return d.date()
        return d

    # --- PRIORITEIT 1: Service Orders Prognose (verwachte factuurdatum) ---
    if service_orders is not None and not service_orders.empty:
        date_col = next((c for c in ['verwachte_factuurdatum'] if c in service_orders.columns), None)
        amt_col = next((c for c in ['verwacht_bedrag'] if c in service_orders.columns), None)

        if date_col and amt_col:
            for _, row in service_orders.iterrows():
                d = _parse_date(row[date_col])
                a = row[amt_col]
                if d is None or pd.isna(a) or float(a) <= 0:
                    continue
                cash_date = d + timedelta(days=max(0, dso_days))
                w_idx = (cash_date - reference_date).days // 7
                _add_to_week(w_idx, float(a), 0.85, 'service_order')

    # --- PRIORITEIT 2: Eenmalige Orderregels (projectfacturatie met datum) ---
    if orderregels_eenmalig is not None and not orderregels_eenmalig.empty:
        for _, row in orderregels_eenmalig.iterrows():
            d = _parse_date(row.get('factuurdatum'))
            bedrag = row.get('nog_te_factureren', 0)
            if d is None or pd.isna(bedrag) or float(bedrag) <= 0:
                continue

            status = str(row.get('status', '')).lower()
            bedrag_f = float(bedrag)

            if status in ('opdracht', 'actief', 'in uitvoering', 'lopend'):
                # Harde toezegging: factuurdatum + DSO
                cash_date = d + timedelta(days=max(0, dso_days))
                w_idx = (cash_date - reference_date).days // 7
                _add_to_week(w_idx, bedrag_f, 0.80, 'orderregel_eenmalig')
            else:
                # Offerte/concept: 40% kans, op factuurdatum
                cash_date = d + timedelta(days=max(0, dso_days))
                w_idx = (cash_date - reference_date).days // 7
                _add_to_week(w_idx, bedrag_f * 0.4, 0.40, 'orderregel_eenmalig_soft')

    # --- PRIORITEIT 3: Periodieke Orderregels (contractuele facturatie) ---
    if orderregels_periodiek is not None and not orderregels_periodiek.empty:
        for _, row in orderregels_periodiek.iterrows():
            d = _parse_date(row.get('geplande_factuurdatum'))
            bedrag = row.get('regelbedrag', 0)
            if d is None or pd.isna(bedrag) or float(bedrag) <= 0:
                continue

            # Periodiek = contractueel vastgelegd, hoge betrouwbaarheid
            cash_date = d + timedelta(days=max(0, dso_days))
            w_idx = (cash_date - reference_date).days // 7
            _add_to_week(w_idx, float(bedrag), 0.90, 'orderregel_periodiek')

    # --- PRIORITEIT 4: Abonnementen (recurring revenue, hoogste zekerheid) ---
    if abonnementen is not None and not abonnementen.empty:
        for _, row in abonnementen.iterrows():
            d = _parse_date(row.get('facturatie_plandatum'))
            bedrag = row.get('facturatiebedrag', 0)
            if d is None or pd.isna(bedrag) or float(bedrag) <= 0:
                continue

            # Abonnement = doorlopend contract, zeer hoge betrouwbaarheid
            cash_date = d + timedelta(days=max(0, dso_days))
            w_idx = (cash_date - reference_date).days // 7
            _add_to_week(w_idx, float(bedrag), 0.92, 'abonnement')

            # Projecteer volgende factureermomenten als kalendereenheid bekend
            kal = str(row.get('kalendereenheid', '')).lower()
            einddatum = _parse_date(row.get('einddatum'))
            if kal in ('maand',):
                interval_days = 30
            elif kal in ('kwartaal',):
                interval_days = 91
            else:
                continue

            # Voeg toekomstige factuurmomenten toe (tot einde forecast)
            next_d = d + timedelta(days=interval_days)
            max_date = reference_date + timedelta(weeks=weeks)
            while next_d <= max_date and (einddatum is None or next_d <= einddatum):
                cash_date = next_d + timedelta(days=max(0, dso_days))
                w_idx = (cash_date - reference_date).days // 7
                _add_to_week(w_idx, float(bedrag), 0.92, 'abonnement')
                next_d += timedelta(days=interval_days)

    # --- PRIORITEIT 5: Orders met opleverdatum (status Opdracht/Actief) ---
    if orderportefeuille is not None and not orderportefeuille.empty:
        status_col = next((c for c in ['status', 'projectstatus'] if c in orderportefeuille.columns), None)
        date_col = next((c for c in ['opleverdatum', 'einddatum'] if c in orderportefeuille.columns), None)
        amt_col = next((c for c in ['orderbedrag'] if c in orderportefeuille.columns), None)

        if date_col and amt_col:
            for _, row in orderportefeuille.iterrows():
                bedrag = row.get(amt_col, 0)
                if pd.isna(bedrag) or float(bedrag) <= 0:
                    continue

                oplever = _parse_date(row.get(date_col))
                if oplever is None:
                    continue

                status = str(row.get(status_col, '') if status_col else '').lower()
                bedrag_f = float(bedrag)

                if status in ('opdracht', 'actief', 'in uitvoering', 'lopend'):
                    cash_date = oplever + timedelta(days=max(0, dso_days))
                    w_idx = (cash_date - reference_date).days // 7
                    if 0 <= w_idx < weeks:
                        # Niet dubbel tellen als orderregels al afgedekt
                        existing = weekly_income[w_idx]
                        if existing < bedrag_f * 0.5:
                            _add_to_week(w_idx, bedrag_f, 0.70, 'order_firm')
                else:
                    # Zachte toezegging: verspreid over doorlooptijd (conservatief 50%)
                    days_to = (oplever - reference_date).days
                    if days_to > 7:
                        weeks_to = max(1, days_to // 7)
                        weekly_amount = bedrag_f * 0.5 / weeks_to
                        for w in range(min(weeks_to, weeks)):
                            weekly_income[w] += weekly_amount
                            weekly_confidence[w] = max(weekly_confidence[w], 0.40)
                            sources.setdefault(w, 'order_soft')
                        total_value += bedrag_f * 0.5

    # Coverage: hoeveel weken hebben pipeline data?
    coverage = sum(1 for w in range(weeks) if weekly_income[w] > 0)

    return ProjectPipeline(
        weekly_income=weekly_income,
        weekly_confidence=weekly_confidence,
        sources=sources,
        total_pipeline_value=total_value,
        coverage_weeks=coverage,
    )


# =============================================================================
# TERUGKERENDE KOSTEN
# =============================================================================

def _build_recurring_costs(
    terugkerende_kosten: pd.DataFrame,
    reference_date: date,
    weeks: int,
) -> Dict[int, float]:
    """
    Modelleer vaste terugkerende kosten per week uit historische kostendata.
    Bron: personeelskosten, huisvesting, auto, machines etc.
    """
    result = {w: 0.0 for w in range(weeks)}

    if terugkerende_kosten is None or terugkerende_kosten.empty:
        return result

    if 'maand' not in terugkerende_kosten.columns or 'bedrag' not in terugkerende_kosten.columns:
        return result

    df = terugkerende_kosten.copy()
    df['bedrag'] = pd.to_numeric(df['bedrag'], errors='coerce').fillna(0).abs()

    # Bereken gemiddelde maandelijkse vaste kosten
    df['maand'] = pd.to_datetime(df['maand'])
    monthly_costs = df.groupby(df['maand'].dt.to_period('M'))['bedrag'].sum()

    if monthly_costs.empty:
        return result

    # Gebruik mediaan (robuust tegen uitschieters)
    avg_monthly = float(monthly_costs.median())
    avg_weekly = avg_monthly / 4.33  # ~4.33 weken per maand

    # Verdeel gelijkmatig over forecast weken (vaste kosten zijn per definitie regelmatig)
    for w in range(weeks):
        result[w] = avg_weekly

    return result


# =============================================================================
# INKOMSTEN-PATROONHERKENNING (fallback voor als pipeline leeg is)
# =============================================================================

def _estimate_income_pattern(
    hist_cf: pd.DataFrame,
    reference_date: date,
    weeks: int,
) -> Dict[int, float]:
    """
    Schat toekomstige inkomsten op basis van historisch patroon.
    In plaats van platte run rate, modelleer de TIMING van grote inkomsten.

    Voor projectbedrijven: detecteer de typische facturatie-cadans
    (bijv. elke 3-4 weken een grote factuur) en projecteer dit voort.
    """
    if hist_cf is None or hist_cf.empty:
        return {w: 0.0 for w in range(weeks)}

    income_col = next((c for c in ['inkomsten', 'omzet'] if c in hist_cf.columns), None)
    if not income_col:
        return {w: 0.0 for w in range(weeks)}

    df = hist_cf.copy()
    incomes = pd.to_numeric(df[income_col], errors='coerce').fillna(0).values

    if len(incomes) < 8:
        # Te weinig data, gebruik gewoon gemiddelde
        avg = float(np.mean(incomes[incomes > 0])) if np.any(incomes > 0) else 0.0
        return {w: avg for w in range(weeks)}

    # Detecteer facturatie-cadans: wanneer komen grote bedragen binnen?
    median_income = float(np.median(incomes[incomes > 0])) if np.any(incomes > 0) else 0.0
    threshold = median_income * 1.5  # "Groot" = 1.5x mediaan

    # Analyseer het patroon van grote inkomstenweken
    big_weeks = np.where(incomes > threshold)[0]

    if len(big_weeks) >= 2:
        # Bereken gemiddelde interval tussen grote weken
        intervals = np.diff(big_weeks)
        avg_interval = float(np.median(intervals))
        avg_big_amount = float(np.mean(incomes[big_weeks]))

        # Bereken gemiddeld bedrag voor "kleine" weken
        small_weeks_mask = incomes <= threshold
        avg_small = float(np.mean(incomes[small_weeks_mask])) if np.any(small_weeks_mask) else 0.0

        # Projecteer het patroon vooruit
        # Laatste grote week in historie → volgende verwachte grote week
        last_big = big_weeks[-1]
        next_big_offset = avg_interval - (len(incomes) - 1 - last_big)

        result = {}
        for w in range(weeks):
            # Bereken afstand tot dichtstbijzijnde verwachte "grote" week
            adjusted_w = w + (len(incomes) - 1 - last_big)
            cycle_position = adjusted_w % avg_interval if avg_interval > 0 else 0

            if abs(cycle_position) < 1.0 or abs(cycle_position - avg_interval) < 1.0:
                # Dit is een verwachte "grote" week
                # Exponentiële demping: minder vertrouwen naarmate verder weg
                decay = np.exp(-0.05 * w)
                result[w] = avg_big_amount * decay + avg_small * (1 - decay)
            else:
                result[w] = avg_small

        return result
    else:
        # Geen duidelijk patroon, gebruik gewogen run rate (bestaande methode)
        weights = np.exp(-0.05 * np.arange(len(incomes))[::-1])
        weights /= weights.sum()
        avg = max(float(np.dot(incomes, weights)), 0)
        return {w: avg for w in range(weeks)}


# =============================================================================
# BLEND — Prioriteitshierarchie
# =============================================================================

def _adaptive_sigmoid_blend(week_idx: int, blend_extension: int = 0) -> float:
    """
    Adaptieve sigmoid blend met uitbreiding voor projectbedrijven.

    blend_extension: extra weken dat Realiteit dominant blijft.
    Voor project_based: +4 weken (totaal week 0-7 ipv 0-3)
    """
    real_end = BLEND_REAL_END + blend_extension
    trans_end = BLEND_TRANSITION_END + blend_extension

    if week_idx <= real_end:
        return 1.0
    if week_idx >= trans_end:
        return 0.0
    t = (week_idx - real_end) / (trans_end - real_end)
    return 1.0 / (1.0 + np.exp(6 * (t - 0.5)))


def _blend_pillars(
    realiteit: Dict[int, Dict[str, float]],
    volume: Dict[int, Dict[str, float]],
    structuur: StructuurProfile,
    reference_date: date,
    weeks: int,
    pipeline: Optional[ProjectPipeline] = None,
    recurring_costs: Optional[Dict[int, float]] = None,
    business_profile: Optional[BusinessProfile] = None,
    income_pattern: Optional[Dict[int, float]] = None,
) -> Dict[int, Dict[str, float]]:
    """
    Blend alle pilaren met projectpijplijn-prioriteit.

    Prioriteitshiërarchie (v3 document):
    1. Realiteit: harde ERP-feiten (open AR/AP, bekende salarissen, BTW)
    2. Pijplijn: verwachte facturatie uit service orders en orderportefeuille
    3. Structuur x Volume: historische patronen x budget/run rate

    Inkomsten per week =
      Realiteit-gewicht × Realiteit-inkomsten
      + Pijplijn (altijd meegenomen, gewogen naar confidence)
      + Volume-gewicht × Volume-inkomsten (alleen het GAP dat niet door pijplijn gedekt is)
    """
    result = {}
    blend_ext = business_profile.blend_extension if business_profile else 0

    # Pipeline totalen voor gap-berekening
    has_pipeline = pipeline is not None and pipeline.total_pipeline_value > 0

    for w in range(weeks):
        real_w = _adaptive_sigmoid_blend(w, blend_ext)
        sv_w = 1.0 - real_w

        real = realiteit.get(w, {'inkomsten': 0, 'uitgaven': 0, 'salarissen': 0, 'btw': 0})
        vol = volume.get(w, {'inkomsten': 0, 'uitgaven': 0})

        # === INKOMSTEN: 3-laags prioriteit ===
        # KERNPRINCIPE: als Realiteit GEEN inkomsten heeft voor deze week,
        # dan moet Volume/Pijplijn/Patroon altijd bijdragen — ongeacht blend-gewicht.
        # De blend-gewichten gelden alleen voor het BALANCEREN van bronnen die
        # beide data hebben, niet voor het onderdrukken van de enige beschikbare bron.
        r_inc = real.get('inkomsten', 0)
        v_inc = vol.get('inkomsten', 0)
        p_inc = pipeline.weekly_income.get(w, 0) if has_pipeline else 0
        p_conf = pipeline.weekly_confidence.get(w, 0) if has_pipeline else 0
        pat_inc = income_pattern.get(w, 0) if income_pattern else 0

        # NIEUW INVOICING GEWICHT:
        # Realiteit toont alleen BEKENDE debiteuren. Maar bedrijven genereren
        # continu nieuwe facturen die ook betaald worden tijdens de forecast.
        # min_new_invoice_w = minimaal gewicht voor nieuwe facturatie-schattingen.
        if business_profile and business_profile.business_type == 'project_based':
            min_new_invoice_w = 0.40  # 40% — veel nieuwe projectfacturatie
        elif business_profile and business_profile.business_type == 'mixed':
            min_new_invoice_w = 0.25
        else:
            min_new_invoice_w = 0.15  # stabiel bedrijf: weinig nieuwe facturatie

        effective_sv_w = max(sv_w, min_new_invoice_w)

        if r_inc > 0:
            # Realiteit = bekende debiteurenbetalingen
            # Volume = run rate (incl. toekomstige facturatie)
            # Nieuwe facturatie = gap tussen run rate en bekende betalingen
            new_invoice_gap = max(0, v_inc - r_inc)
            base_income = r_inc + new_invoice_gap * effective_sv_w
            # Pijplijn als aanvulling
            pipeline_extra = max(0, p_inc - r_inc) * p_conf * effective_sv_w
            inkomsten = base_income + pipeline_extra
        elif p_inc > 0:
            # Geen realiteit maar WEL pijplijn: pijplijn is leidend
            gap_fill = v_inc * max(effective_sv_w, 1 - p_conf)
            inkomsten = p_inc * p_conf + gap_fill
        elif pat_inc > 0 and business_profile and business_profile.business_type in ('project_based', 'mixed'):
            # Projectbedrijf: gebruik patroonherkenning ipv platte run rate
            inkomsten = pat_inc
        else:
            # Fallback: volume altijd meenemen
            inkomsten = v_inc

        # === UITGAVEN: realiteit + terugkerende kosten + volume ===
        r_exp = real.get('uitgaven', 0)
        v_exp = vol.get('uitgaven', 0)
        rec_exp = recurring_costs.get(w, 0) if recurring_costs else 0

        if r_exp > 0:
            # Realiteit = bekende crediteurenbetalingen
            # Volume = run rate uitgaven
            new_expense_gap = max(0, v_exp - r_exp)
            base_expense = r_exp + new_expense_gap * effective_sv_w
            # Terugkerende kosten als minimum vloer
            uitgaven = max(base_expense, rec_exp)
        elif rec_exp > 0:
            # Geen realiteit maar wel bekende vaste kosten: altijd meenemen
            uitgaven = max(rec_exp, v_exp)
        else:
            # Fallback: volume altijd meenemen
            uitgaven = v_exp

        # === SALARISSEN: realiteit of structuurprofiel ===
        salarissen = real.get('salarissen', 0)
        if salarissen == 0 and structuur.salary_profile.monthly_base > 0:
            week_start = reference_date + timedelta(weeks=w)
            month_end = _week_contains_month_end(week_start)
            if month_end is not None:
                month = month_end.month
                peak = structuur.salary_profile.peak_months.get(month, 1.0)
                salarissen = structuur.salary_profile.monthly_base * peak

        # === BTW: realiteit of structuurritme ===
        btw = real.get('btw', 0)
        if btw == 0 and structuur.btw_rhythm.avg_amount > 0:
            week_start = reference_date + timedelta(weeks=w)
            month_end = _week_contains_month_end(week_start)
            if month_end is not None and month_end.month in structuur.btw_rhythm.payment_months:
                btw = structuur.btw_rhythm.avg_amount

        # Pipeline-gewicht in metadata
        p_weight = p_conf * (1 - real_w) if has_pipeline and p_inc > 0 else 0.0

        result[w] = {
            'inkomsten': inkomsten,
            'uitgaven': uitgaven,
            'salarissen': salarissen,
            'btw': btw,
            'pilaar_realiteit': real_w,
            'pilaar_pijplijn': p_weight,
            'pilaar_structuur': sv_w * (1 - p_weight) * 0.5,
            'pilaar_volume': sv_w * (1 - p_weight) * 0.5,
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

    # Extract data (bestaande bronnen)
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

    # NIEUW: extra databronnen voor projectpijplijn
    service_orders = data.get('service_orders_prognose', pd.DataFrame())
    terugkerende_kosten_data = data.get('terugkerende_kosten', pd.DataFrame())

    # NIEUW: orderregels, abonnementen, BTW prognose
    orderregels_periodiek = data.get('orderregels_periodiek', pd.DataFrame())
    orderregels_eenmalig = data.get('orderregels_eenmalig', pd.DataFrame())
    abonnementen = data.get('abonnementen', pd.DataFrame())
    service_contract_intake = data.get('service_contract_intake', pd.DataFrame())
    btw_prognose = data.get('btw_prognose', pd.DataFrame())

    # Startsaldo
    start_balance = 0.0
    if isinstance(banksaldo, (int, float)):
        start_balance = float(banksaldo)
    elif isinstance(banksaldo, pd.DataFrame) and not banksaldo.empty and 'saldo' in banksaldo.columns:
        start_balance = float(banksaldo['saldo'].sum())

    # DSO/DPO
    dso_days = calibrated_dso if calibrated_dso is not None else 35.0
    dpo_days = calibrated_dpo if calibrated_dpo is not None else 0.0

    # =========================================================================
    # BEDRIJFSTYPE DETECTIE (bepaalt blending-strategie)
    # =========================================================================
    business_profile = _detect_business_type(hist_cf, debiteuren)

    # =========================================================================
    # PILAAR 1: REALITEIT (harde ERP-feiten)
    # =========================================================================
    realiteit = _build_realiteit(
        debiteuren, crediteuren, salarissen, btw_data,
        dso_days, dpo_days, reference_date, weeks_forecast,
        btw_prognose=btw_prognose,
    )

    # =========================================================================
    # PILAAR 2: STRUCTUUR (historische timing-patronen)
    # =========================================================================
    structuur = _build_structuur(
        hist_cf, btw_data, salaris_data, betaalgedrag_deb, betaalgedrag_cred,
    )

    # =========================================================================
    # PILAAR 3: VOLUME (hoeveel, uit budget of run rate)
    # =========================================================================
    volume = _build_volume(
        hist_cf, budgetten, orders, structuur, reference_date, weeks_forecast,
        service_contract_intake=service_contract_intake,
    )

    # =========================================================================
    # NIEUW: PROJECTPIJPLIJN (facturering prioriteitshiërarchie v3)
    # =========================================================================
    pipeline = _build_project_pipeline(
        service_orders, orders, dso_days, reference_date, weeks_forecast,
        orderregels_periodiek=orderregels_periodiek,
        orderregels_eenmalig=orderregels_eenmalig,
        abonnementen=abonnementen,
    )

    # =========================================================================
    # NIEUW: TERUGKERENDE KOSTEN (deterministische uitgaven)
    # =========================================================================
    recurring_costs = _build_recurring_costs(
        terugkerende_kosten_data, reference_date, weeks_forecast,
    )

    # =========================================================================
    # NIEUW: INKOMSTEN-PATROONHERKENNING (voor projectbedrijven)
    # =========================================================================
    income_pattern = None
    if business_profile.business_type == 'project_based':
        income_pattern = _estimate_income_pattern(
            hist_cf, reference_date, weeks_forecast,
        )

    # =========================================================================
    # BLEND (met projectpijplijn, terugkerende kosten, adaptieve blending)
    # =========================================================================
    blended = _blend_pillars(
        realiteit, volume, structuur, reference_date, weeks_forecast,
        pipeline=pipeline,
        recurring_costs=recurring_costs,
        business_profile=business_profile,
        income_pattern=income_pattern,
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
            'pilaar_pijplijn': wd.get('pilaar_pijplijn', 0),
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
        'business_profile': {
            'type': business_profile.business_type,
            'income_cv': round(business_profile.income_cv, 3),
            'cost_ratio': round(business_profile.cost_ratio, 3),
            'blend_extension': business_profile.blend_extension,
            'income_frequency': round(business_profile.income_frequency, 1),
        },
        'project_pipeline': {
            'total_value': pipeline.total_pipeline_value,
            'coverage_weeks': pipeline.coverage_weeks,
            'has_service_orders': not service_orders.empty,
            'has_orders': not orders.empty,
            'has_orderregels_periodiek': not orderregels_periodiek.empty,
            'has_orderregels_eenmalig': not orderregels_eenmalig.empty,
            'has_abonnementen': not abonnementen.empty,
        },
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
            'banksaldo': isinstance(banksaldo, (int, float)) and banksaldo != 0 or isinstance(banksaldo, pd.DataFrame) and not banksaldo.empty,
            'btw_aangifteregels': not btw_data.empty,
            'salarishistorie': not salaris_data.empty,
            'budgetten': not budgetten.empty,
            'orderportefeuille': not orders.empty,
            'service_orders_prognose': not service_orders.empty,
            'terugkerende_kosten': not terugkerende_kosten_data.empty,
            'betaalgedrag_debiteuren': not betaalgedrag_deb.empty,
            'betaalgedrag_crediteuren': not betaalgedrag_cred.empty,
            'orderregels_periodiek': not orderregels_periodiek.empty,
            'orderregels_eenmalig': not orderregels_eenmalig.empty,
            'abonnementen': not abonnementen.empty,
            'service_contract_intake': not service_contract_intake.empty,
            'btw_prognose': not btw_prognose.empty,
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

    missing_core = [k for k in ['historische_cashflow', 'debiteuren', 'crediteuren']
                    if isinstance(data.get(k), pd.DataFrame) and data[k].empty or data.get(k) is None]
    if isinstance(data.get('banksaldo'), (int, float)) and data['banksaldo'] == 0:
        missing_core.append('banksaldo')
    elif isinstance(data.get('banksaldo'), pd.DataFrame) and data['banksaldo'].empty:
        missing_core.append('banksaldo')
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
