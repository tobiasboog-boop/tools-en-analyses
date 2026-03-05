"""
BACKTESTING FRAMEWORK
=====================
Walk-Forward Validation voor Forecast Models (V6 + V7).

Methodiek:
1. Kies N cutoff dates (1e van elke maand)
2. Mask alle data NA de cutoff (tijdmachine)
3. Reconstrueer openstaande posten zoals ze TOEN waren
4. Genereer forecast voor 12 weken vooruit
5. Vergelijk met realisatie
6. Bereken metrics: MAPE, Bias, Accuracy Decay

V7 toevoegingen:
- model_version parameter ('v6' of 'v7')
- Extra data masking voor BTW, salaris, budgetten
- ComparisonReport voor V6 vs V7 vergelijking
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class BacktestResult:
    """Resultaat van een backtest run."""
    cutoff_date: date
    forecast_df: pd.DataFrame
    actuals_df: pd.DataFrame
    mape_per_week: Dict[int, float]
    bias_per_week: Dict[int, float]
    total_mape: float
    total_bias: float
    ghost_invoice_accuracy: float
    model_version: str = 'v6'


@dataclass
class BacktestReport:
    """Samenvatting van alle backtest runs."""
    results: List[BacktestResult]
    overall_mape: float
    overall_bias: float
    accuracy_decay: Dict[int, float]
    layer3_accuracy: float
    recommendations: List[str]
    model_version: str = 'v6'


@dataclass
class ComparisonReport:
    """V6 vs V7 vergelijking."""
    v6_report: BacktestReport
    v7_report: BacktestReport
    improvement_mape: float          # positief = V7 beter
    improvement_bias: float          # positief = V7 beter
    per_horizon_comparison: Dict[int, Tuple[float, float]]  # week -> (v6_mape, v7_mape)
    recommendation: str


class BacktestFramework:
    """
    Walk-Forward Validation Framework.

    Simuleert het model op historische momenten en vergelijkt met realisatie.
    Ondersteunt zowel V6 (Ghost Invoice) als V7 (Structuur x Volume x Realiteit).
    """

    def __init__(self, db_connection, administratie: str, model_version: str = 'v6'):
        """
        Args:
            db_connection: Database connectie (NotificaDataSource)
            administratie: Administratie naam voor filtering
            model_version: 'v6' of 'v7'
        """
        self.db = db_connection
        self.administratie = administratie
        self.model_version = model_version
        self.forecast_horizon = 12  # Weken vooruit

    def generate_cutoff_dates(self, n_months: int = 12) -> List[date]:
        """
        Genereer cutoff dates: 1e van elke maand voor de afgelopen N maanden.
        """
        today = date.today()
        cutoffs = []

        for i in range(1, n_months + 1):
            # Ga i maanden terug
            year = today.year
            month = today.month - i

            while month <= 0:
                month += 12
                year -= 1

            cutoffs.append(date(year, month, 1))

        return sorted(cutoffs)  # Oudste eerst

    def mask_data_at_cutoff(self, cutoff: date) -> Dict[str, pd.DataFrame]:
        """
        TIJDMACHINE: Haal data op alsof we op de cutoff date leven.

        Cruciale logica:
        - Alleen transacties met CreatieDatum < cutoff
        - Openstaande post = FactuurDatum < cutoff EN (BetaalDatum > cutoff OF BetaalDatum IS NULL)
        """
        # Historische periode voor patroonanalyse (12 maanden voor cutoff)
        hist_start = date(cutoff.year - 1, cutoff.month, 1)

        # Haal historische cashflow op (alleen data VAN VOOR de cutoff)
        historische_cashflow = self._get_historical_cashflow_before_cutoff(
            hist_start, cutoff
        )

        # Reconstrueer openstaande posten ZOALS ZE TOEN WAREN
        debiteuren = self._reconstruct_open_ar_at_cutoff(cutoff)
        crediteuren = self._reconstruct_open_ap_at_cutoff(cutoff)

        # Banksaldo op de cutoff date
        banksaldo = self._get_balance_at_cutoff(cutoff)

        result = {
            'historische_cashflow': historische_cashflow,
            'debiteuren': debiteuren,
            'crediteuren': crediteuren,
            'banksaldo': banksaldo,
        }

        # V7: extra databronnen ophalen
        if self.model_version == 'v7':
            hist_start_24m = date(cutoff.year - 2, cutoff.month, 1)

            try:
                result['btw_aangifteregels'] = self.db.get_btw_aangifteregels(
                    startdatum=hist_start_24m, einddatum=cutoff)
            except Exception:
                result['btw_aangifteregels'] = pd.DataFrame()

            try:
                result['salarishistorie'] = self.db.get_salarishistorie(
                    startdatum=hist_start_24m, einddatum=cutoff)
            except Exception:
                result['salarishistorie'] = pd.DataFrame()

            try:
                result['budgetten'] = self.db.get_budgetten(
                    boekjaar=cutoff.year, administratie=self.administratie)
            except Exception:
                result['budgetten'] = pd.DataFrame()

            try:
                result['orderportefeuille'] = self.db.get_orderportefeuille(
                    administratie=self.administratie)
            except Exception:
                result['orderportefeuille'] = pd.DataFrame()

            try:
                result['betaalgedrag_debiteuren'] = self.db.get_betaalgedrag_per_debiteur(
                    startdatum=hist_start_24m, einddatum=cutoff,
                    administratie=self.administratie)
            except Exception:
                result['betaalgedrag_debiteuren'] = pd.DataFrame()

            try:
                result['betaalgedrag_crediteuren'] = self.db.get_betaalgedrag_per_crediteur(
                    startdatum=hist_start_24m, einddatum=cutoff,
                    administratie=self.administratie)
            except Exception:
                result['betaalgedrag_crediteuren'] = pd.DataFrame()

            result['geplande_salarissen'] = pd.DataFrame()

        return result

    def _get_historical_cashflow_before_cutoff(
        self, start: date, cutoff: date
    ) -> pd.DataFrame:
        """Haal historische cashflow op voor de periode VOOR de cutoff."""
        return self.db.get_historische_cashflow_per_week(
            startdatum=start,
            einddatum=cutoff,
            administratie=self.administratie
        )

    def _reconstruct_open_ar_at_cutoff(self, cutoff: date) -> pd.DataFrame:
        """
        Reconstrueer openstaande debiteuren ZOALS ZE OP DE CUTOFF WAREN.

        Logica:
        - FactuurDatum < cutoff (factuur bestond al)
        - BetaalDatum > cutoff OF BetaalDatum IS NULL (nog niet betaald op dat moment)
        """
        # Haal alle debiteuren data op met standdatum = cutoff
        # Dit zou de database moeten ondersteunen met de juiste query
        return self.db.get_openstaande_debiteuren(
            standdatum=cutoff,
            administratie=self.administratie
        )

    def _reconstruct_open_ap_at_cutoff(self, cutoff: date) -> pd.DataFrame:
        """Reconstrueer openstaande crediteuren op de cutoff date."""
        return self.db.get_openstaande_crediteuren(standdatum=cutoff)

    def _get_balance_at_cutoff(self, cutoff: date) -> pd.DataFrame:
        """Haal banksaldo op per cutoff date."""
        return self.db.get_banksaldo(
            standdatum=cutoff,
            administratie=self.administratie
        )

    def get_actuals_after_cutoff(
        self, cutoff: date, weeks: int = 12
    ) -> pd.DataFrame:
        """
        Haal de ECHTE cashflow op voor de periode NA de cutoff.
        Dit is de 'waarheid' waarmee we vergelijken.
        """
        end_date = cutoff + timedelta(weeks=weeks)

        actuals = self.db.get_historische_cashflow_per_week(
            startdatum=cutoff,
            einddatum=end_date,
            administratie=self.administratie
        )

        if actuals.empty:
            return pd.DataFrame({
                'week_nummer': range(weeks),
                'inkomsten': [0] * weeks,
                'uitgaven': [0] * weeks,
                'netto': [0] * weeks,
            })

        # Voeg week_nummer toe relatief aan cutoff
        actuals = actuals.copy()

        # Zoek de juiste datum kolom
        date_col = None
        for col in ['week_start', 'date', 'datum', 'maand']:
            if col in actuals.columns:
                date_col = col
                break

        if date_col is None:
            return actuals

        # Converteer naar datetime
        actuals[date_col] = pd.to_datetime(actuals[date_col])

        # Bereken week_nummer (dagen sinds cutoff / 7)
        actuals['week_nummer'] = actuals[date_col].apply(
            lambda x: (x.date() - cutoff).days // 7 if pd.notna(x) else -1
        )

        return actuals

    def run_forecast_at_cutoff(
        self, masked_data: Dict[str, pd.DataFrame], cutoff: date
    ) -> pd.DataFrame:
        """
        Draai het forecast model op de masked data.
        Genereert forecast voor 12 weken vanaf cutoff.
        """
        if self.model_version == 'v7':
            from src.forecast_v7 import create_forecast_v7
            forecast_df, _, metadata = create_forecast_v7(
                data=masked_data,
                weeks_forecast=self.forecast_horizon,
                weeks_history=0,
                reference_date=cutoff,
            )
        else:
            from src.forecast_model import create_forecast_for_app
            forecast_df, _, metadata = create_forecast_for_app(
                data=masked_data,
                weeks_forecast=self.forecast_horizon,
                weeks_history=0,
                reference_date=cutoff,
            )

        # Filter alleen forecast weken (niet historie)
        forecast_df = forecast_df[forecast_df['data_type'] != 'Realisatie'].copy()
        forecast_df['week_nummer'] = range(len(forecast_df))

        return forecast_df

    def calculate_metrics(
        self, forecast: pd.DataFrame, actuals: pd.DataFrame
    ) -> Tuple[Dict[int, float], Dict[int, float], float, float]:
        """
        Bereken MAPE en Bias per week.

        Returns:
            mape_per_week, bias_per_week, total_mape, total_bias
        """
        mape_per_week = {}
        bias_per_week = {}

        all_errors = []
        all_pct_errors = []

        for week in range(self.forecast_horizon):
            # Haal forecast voor deze week
            fc_row = forecast[forecast['week_nummer'] == week]
            ac_row = actuals[actuals['week_nummer'] == week]

            if fc_row.empty or ac_row.empty:
                continue

            # Netto cashflow vergelijken
            fc_value = fc_row['netto_cashflow'].values[0]

            # Actuals kunnen 'netto' of 'netto_cashflow' hebben
            if 'netto_cashflow' in ac_row.columns:
                ac_value = ac_row['netto_cashflow'].values[0]
            elif 'netto' in ac_row.columns:
                ac_value = ac_row['netto'].values[0]
            else:
                continue

            # Bereken error
            error = fc_value - ac_value
            bias_per_week[week] = error
            all_errors.append(error)

            # MAPE (alleen als actual != 0)
            if abs(ac_value) > 100:  # Minimum threshold
                pct_error = abs(error / ac_value) * 100
                mape_per_week[week] = pct_error
                all_pct_errors.append(pct_error)
            else:
                mape_per_week[week] = np.nan

        total_mape = np.nanmean(all_pct_errors) if all_pct_errors else np.nan
        total_bias = sum(all_errors) if all_errors else 0

        return mape_per_week, bias_per_week, total_mape, total_bias

    def calculate_ghost_invoice_accuracy(
        self, forecast: pd.DataFrame, actuals: pd.DataFrame
    ) -> float:
        """
        LAYER 3 TEST: Vergelijk Ghost Invoice voorspellingen met realisatie.

        Focus op weken 5-12 waar Ghost Invoices dominant zijn.
        """
        ghost_weeks = range(5, min(12, self.forecast_horizon))

        fc_total = 0
        ac_total = 0

        for week in ghost_weeks:
            fc_row = forecast[forecast['week_nummer'] == week]
            ac_row = actuals[actuals['week_nummer'] == week]

            if not fc_row.empty:
                fc_total += fc_row['inkomsten_debiteuren'].values[0]

            if not ac_row.empty:
                if 'inkomsten' in ac_row.columns:
                    ac_total += ac_row['inkomsten'].values[0]
                elif 'inkomsten_debiteuren' in ac_row.columns:
                    ac_total += ac_row['inkomsten_debiteuren'].values[0]

        if ac_total > 0:
            accuracy = 100 - abs((fc_total - ac_total) / ac_total * 100)
            return max(0, accuracy)

        return np.nan

    def run_single_backtest(self, cutoff: date) -> BacktestResult:
        """Voer backtest uit voor een cutoff date."""
        print(f"  [{self.model_version.upper()}] Backtest voor cutoff: {cutoff}")

        masked_data = self.mask_data_at_cutoff(cutoff)
        forecast = self.run_forecast_at_cutoff(masked_data, cutoff)
        actuals = self.get_actuals_after_cutoff(cutoff)

        mape_per_week, bias_per_week, total_mape, total_bias = self.calculate_metrics(
            forecast, actuals
        )
        ghost_accuracy = self.calculate_ghost_invoice_accuracy(forecast, actuals)

        return BacktestResult(
            cutoff_date=cutoff,
            forecast_df=forecast,
            actuals_df=actuals,
            mape_per_week=mape_per_week,
            bias_per_week=bias_per_week,
            total_mape=total_mape,
            total_bias=total_bias,
            ghost_invoice_accuracy=ghost_accuracy,
            model_version=self.model_version,
        )

    def run_full_backtest(self, n_months: int = 12) -> BacktestReport:
        """Voer volledige Walk-Forward Validation uit."""
        print(f"[{self.model_version.upper()}] Walk-Forward Validation ({n_months} cutoff dates)")
        print("=" * 60)

        cutoffs = self.generate_cutoff_dates(n_months)
        results = []

        for cutoff in cutoffs:
            try:
                result = self.run_single_backtest(cutoff)
                results.append(result)
            except Exception as e:
                print(f"  ERROR bij cutoff {cutoff}: {e}")
                continue

        if not results:
            print("Geen succesvolle backtests!")
            return None

        overall_mape = np.nanmean([r.total_mape for r in results])
        overall_bias = np.nanmean([r.total_bias for r in results])

        accuracy_decay = {}
        for week in range(self.forecast_horizon):
            week_mapes = [r.mape_per_week.get(week, np.nan) for r in results]
            accuracy_decay[week] = np.nanmean(week_mapes)

        layer3_accuracy = np.nanmean([r.ghost_invoice_accuracy for r in results])
        recommendations = self._generate_recommendations(
            overall_mape, overall_bias, accuracy_decay, layer3_accuracy
        )

        print(f"\n{'='*60}")
        print(f"[{self.model_version.upper()}] COMPLEET: {len(results)} runs")
        print(f"Overall MAPE: {overall_mape:.1f}%")
        print(f"Overall Bias: EUR {overall_bias:,.0f}")
        print(f"Layer 3 Accuracy: {layer3_accuracy:.1f}%")

        return BacktestReport(
            results=results,
            overall_mape=overall_mape,
            overall_bias=overall_bias,
            accuracy_decay=accuracy_decay,
            layer3_accuracy=layer3_accuracy,
            recommendations=recommendations,
            model_version=self.model_version,
        )

    def run_comparison_backtest(self, n_months: int = 6) -> ComparisonReport:
        """
        Draai V6 en V7 naast elkaar op dezelfde cutoff dates.

        Returns:
            ComparisonReport met MAPE/bias vergelijking per horizon
        """
        print("COMPARISON BACKTEST: V6 vs V7")
        print("=" * 60)

        # V6
        self.model_version = 'v6'
        v6_report = self.run_full_backtest(n_months)

        # V7
        self.model_version = 'v7'
        v7_report = self.run_full_backtest(n_months)

        if v6_report is None or v7_report is None:
            print("Kon vergelijking niet uitvoeren")
            return None

        # MAPE verbetering (positief = V7 beter)
        improvement_mape = v6_report.overall_mape - v7_report.overall_mape
        improvement_bias = abs(v6_report.overall_bias) - abs(v7_report.overall_bias)

        # Per-horizon vergelijking
        per_horizon = {}
        for week in range(self.forecast_horizon):
            v6_m = v6_report.accuracy_decay.get(week, np.nan)
            v7_m = v7_report.accuracy_decay.get(week, np.nan)
            per_horizon[week] = (v6_m, v7_m)

        # Aanbeveling
        if improvement_mape > 5:
            recommendation = f"V7 is significant beter (MAPE -{improvement_mape:.1f}%). Overstappen aanbevolen."
        elif improvement_mape > 0:
            recommendation = f"V7 is marginaal beter (MAPE -{improvement_mape:.1f}%). Verdere validatie nodig."
        elif improvement_mape > -5:
            recommendation = f"V6 en V7 presteren vergelijkbaar. V7 biedt meer inzicht."
        else:
            recommendation = f"V6 presteert beter (MAPE +{abs(improvement_mape):.1f}%). V7 model tuning nodig."

        print(f"\n{'='*60}")
        print("VERGELIJKING")
        print(f"V6 MAPE: {v6_report.overall_mape:.1f}%  |  V7 MAPE: {v7_report.overall_mape:.1f}%")
        print(f"Verbetering: {improvement_mape:+.1f}% MAPE")
        print(f"Aanbeveling: {recommendation}")

        return ComparisonReport(
            v6_report=v6_report,
            v7_report=v7_report,
            improvement_mape=improvement_mape,
            improvement_bias=improvement_bias,
            per_horizon_comparison=per_horizon,
            recommendation=recommendation,
        )

    def _generate_recommendations(
        self, mape: float, bias: float, decay: Dict[int, float], l3_acc: float
    ) -> List[str]:
        """Genereer aanbevelingen op basis van resultaten."""
        recs = []

        if mape < 15:
            recs.append("✅ Model heeft goede algehele nauwkeurigheid (MAPE < 15%)")
        elif mape < 30:
            recs.append("⚠️ Model heeft acceptabele nauwkeurigheid (MAPE 15-30%)")
        else:
            recs.append("❌ Model nauwkeurigheid moet verbeteren (MAPE > 30%)")

        if bias > 50000:
            recs.append("📈 Model overschat systematisch - overweeg conservatievere run rate")
        elif bias < -50000:
            recs.append("📉 Model onderschat systematisch - overweeg hogere run rate")
        else:
            recs.append("✅ Geen significante systematische bias")

        # Check accuracy decay
        week1_acc = 100 - decay.get(1, 50)
        week8_acc = 100 - decay.get(8, 50)

        if week8_acc < week1_acc * 0.5:
            recs.append("⚠️ Sterke accuracy decay - overweeg kortere forecast horizon")

        if l3_acc > 70:
            recs.append("✅ Ghost Invoice extrapolatie werkt goed")
        else:
            recs.append("⚠️ Ghost Invoice extrapolatie heeft verbetering nodig")

        return recs


def create_backtest_visualizations(report: BacktestReport) -> Dict:
    """
    Maak visualisatie data voor het backtest rapport.

    Returns dict met data voor Plotly grafieken.
    """
    # 1. Accuracy Decay grafiek
    accuracy_decay_data = {
        'week': list(report.accuracy_decay.keys()),
        'mape': list(report.accuracy_decay.values()),
        'accuracy': [100 - m if not np.isnan(m) else 0 for m in report.accuracy_decay.values()]
    }

    # 2. Forecast vs Actuals per cutoff
    comparison_data = []
    for result in report.results[-3:]:  # Laatste 3 cutoffs
        for week in range(12):
            fc_row = result.forecast_df[result.forecast_df['week_nummer'] == week]
            ac_row = result.actuals_df[result.actuals_df['week_nummer'] == week]

            if not fc_row.empty and not ac_row.empty:
                comparison_data.append({
                    'cutoff': result.cutoff_date.strftime('%Y-%m-%d'),
                    'week': week,
                    'forecast': fc_row['netto_cashflow'].values[0],
                    'actual': ac_row['netto'].values[0] if 'netto' in ac_row.columns else 0,
                })

    # 3. MAPE trend over cutoffs
    mape_trend = {
        'cutoff': [r.cutoff_date.strftime('%Y-%m') for r in report.results],
        'mape': [r.total_mape for r in report.results],
    }

    return {
        'accuracy_decay': accuracy_decay_data,
        'comparison': comparison_data,
        'mape_trend': mape_trend,
    }


def run_backtest_for_customer(
    customer_code: str,
    administratie: str,
    n_months: int = 6,
    model_version: str = 'v7',
) -> Optional[BacktestReport]:
    """
    Helper functie om backtest te draaien voor een klant.

    Args:
        customer_code: Klantcode (bijv. "1229")
        administratie: Administratie naam
        n_months: Aantal maanden terug te testen
        model_version: 'v6' of 'v7'
    """
    from src.database import get_database

    db = get_database(use_mock=False, customer_code=customer_code)
    framework = BacktestFramework(db, administratie, model_version=model_version)
    return framework.run_full_backtest(n_months)


def run_comparison_for_customer(
    customer_code: str,
    administratie: str,
    n_months: int = 6,
) -> Optional[ComparisonReport]:
    """Draai V6 vs V7 vergelijking voor een klant."""
    from src.database import get_database

    db = get_database(use_mock=False, customer_code=customer_code)
    framework = BacktestFramework(db, administratie)
    return framework.run_comparison_backtest(n_months)


# =============================================================================
# CLI INTERFACE
# =============================================================================
if __name__ == "__main__":
    import sys

    customer_code = sys.argv[1] if len(sys.argv) > 1 else "1229"
    administratie = sys.argv[2] if len(sys.argv) > 2 else ""
    n_months = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    mode = sys.argv[4] if len(sys.argv) > 4 else "compare"  # 'v6', 'v7', 'compare'

    print(f"Backtest voor klant {customer_code}")
    print(f"Administratie: {administratie or '(alle)'}")
    print(f"Maanden: {n_months}, Mode: {mode}")
    print()

    if mode == 'compare':
        report = run_comparison_for_customer(customer_code, administratie, n_months)
        if report:
            print(f"\nV6 MAPE: {report.v6_report.overall_mape:.1f}%")
            print(f"V7 MAPE: {report.v7_report.overall_mape:.1f}%")
            print(f"Verbetering: {report.improvement_mape:+.1f}%")
            print(f"\nAanbeveling: {report.recommendation}")
    else:
        report = run_backtest_for_customer(
            customer_code, administratie, n_months, model_version=mode)
        if report:
            print(f"\n[{report.model_version.upper()}] MAPE: {report.overall_mape:.1f}%")
            print(f"Bias: EUR {report.overall_bias:,.0f}")
            print("\nAccuracy per week:")
            for week, mape in report.accuracy_decay.items():
                acc = 100 - mape if not np.isnan(mape) else 0
                print(f"  Week {week}: {acc:.0f}% (MAPE: {mape:.1f}%)")
            for rec in report.recommendations:
                print(f"  {rec}")
