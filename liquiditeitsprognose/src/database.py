"""
Liquiditeitsprognose - Database Layer
=====================================
Data-laag via Notifica Data API (NotificaClient SDK).
Vervangt directe psycopg2-verbinding.
"""

import os
import sys
import pandas as pd
from datetime import date, timedelta
from typing import Optional, Union

# SDK import
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_sdk'))
try:
    from notifica_sdk import NotificaClient
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


def _sql_date(d: date) -> str:
    """Format date for SQL injection-safe use (we control all inputs)."""
    return f"'{d.isoformat()}'"


def _sql_str(s: str) -> str:
    """Format string for SQL (escape single quotes)."""
    return f"'{s.replace(chr(39), chr(39)+chr(39))}'"


# =============================================================================
# NotificaDataSource — Alle data via de Notifica API
# =============================================================================

class NotificaDataSource:
    """Data source via Notifica Data API. Vervangt directe DWH-verbinding."""

    def __init__(self, klantnummer: str):
        if not SDK_AVAILABLE:
            raise ImportError("NotificaClient SDK niet gevonden in _sdk/notifica_sdk/")

        # API key ophalen: Streamlit secrets > .env > environment
        api_url = None
        app_key = None
        data_key = None
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'api' in st.secrets:
                api_url = st.secrets["api"].get("url")
                app_key = st.secrets["api"].get("app_key")
                data_key = st.secrets["api"].get("data_key")
        except (ImportError, Exception):
            pass

        self.client = NotificaClient(api_url=api_url, app_key=app_key, data_key=data_key)
        self.klantnummer = int(klantnummer)

    def _query(self, sql: str) -> pd.DataFrame:
        """Execute SQL via Notifica API."""
        return self.client.query(self.klantnummer, sql)

    def test_connection(self) -> bool:
        try:
            self._query("SELECT 1 as test")
            return True
        except Exception as e:
            print(f"API connection failed: {e}")
            return False

    # =========================================================================
    # Bestaande methoden (zelfde SQL als voorheen, nu via API)
    # =========================================================================

    def get_banksaldo(self, standdatum: date = None, administratie: str = None) -> pd.DataFrame:
        if standdatum is None:
            standdatum = date.today()

        adm_filter = f'AND a."Administratie" = {_sql_str(administratie)}' if administratie else ""
        adm_join = 'JOIN notifica."SSM Administraties" a ON dag."AdministratieKey" = a."AdministratieKey"' if administratie else ""

        sql = f"""
        SELECT
            dag."Dagboek" as bank_naam,
            dag."Dagboek" as rekeningnummer,
            SUM(CASE WHEN j."Debet/Credit" = 'D' THEN j."Bedrag" ELSE 0 END) -
            SUM(CASE WHEN j."Debet/Credit" = 'C' THEN j."Bedrag" ELSE 0 END) as saldo,
            CURRENT_DATE as datum
        FROM financieel."Journaalregels" j
        JOIN stam."Documenten" d ON j."DocumentKey" = d."DocumentKey"
        JOIN stam."Dagboeken" dag ON d."DagboekKey" = dag."DagboekKey"
        {adm_join}
        WHERE j."Boekdatum" <= {_sql_date(standdatum)}
          AND d."StandaardEntiteitKey" = 10
          AND j."RubriekKey" = dag."DagboekRubriekKey"
          {adm_filter}
        GROUP BY dag."Dagboek"
        HAVING ABS(SUM(CASE WHEN j."Debet/Credit" = 'D' THEN j."Bedrag" ELSE 0 END) -
                    SUM(CASE WHEN j."Debet/Credit" = 'C' THEN j."Bedrag" ELSE 0 END)) > 0.01
        ORDER BY saldo DESC
        """
        try:
            df = self._query(sql)
            return df if not df.empty else pd.DataFrame({"bank_naam": [], "rekeningnummer": [], "saldo": [], "datum": []})
        except Exception as e:
            print(f"Error fetching bank balances: {e}")
            return pd.DataFrame({"bank_naam": [], "rekeningnummer": [], "saldo": [], "datum": []})

    def get_openstaande_debiteuren(self, standdatum: date = None, administratie: str = None) -> pd.DataFrame:
        if standdatum is None:
            standdatum = date.today()

        adm_filter = f'AND a."Administratie" = {_sql_str(administratie)}' if administratie else ""

        sql = f"""
        SELECT
            vft."Debiteur" as debiteur_code,
            vft."Debiteur" as debiteur_naam,
            'Diverse' as factuurnummer,
            MAX(vft."Alloc_datum") as factuurdatum,
            MAX(vft."Vervaldatum") as vervaldatum,
            SUM(vft."Bedrag") as bedrag_excl_btw,
            NULL::date as betaaldatum,
            0 as betaald,
            SUM(vft."Bedrag") as openstaand,
            30 as betaaltermijn_dagen,
            COALESCE(a."Administratie", 'Onbekend') as administratie,
            COALESCE(be."Bedrijfseenheid", 'Onbekend') as bedrijfseenheid
        FROM notifica."SSM Verkoopfactuur termijnen" vft
        LEFT JOIN notifica."SSM Documenten" d ON vft."VerkoopfactuurDocumentKey" = d."DocumentKey"
        LEFT JOIN notifica."SSM Bedrijfseenheden" be ON d."BedrijfseenheidKey"::bigint = be."BedrijfseenheidKey"
        LEFT JOIN notifica."SSM Administraties" a ON be."AdministratieKey" = a."AdministratieKey"
        WHERE vft."Alloc_datum" <= {_sql_date(standdatum)}
          {adm_filter}
        GROUP BY vft."Debiteur", a."Administratie", be."Bedrijfseenheid"
        HAVING ABS(SUM(vft."Bedrag")) > 0.01
        ORDER BY SUM(vft."Bedrag") DESC
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching receivables: {e}")
            return pd.DataFrame({
                "debiteur_code": [], "debiteur_naam": [], "factuurnummer": [],
                "factuurdatum": [], "vervaldatum": [], "bedrag_excl_btw": [],
                "betaaldatum": [], "betaald": [], "openstaand": [],
                "betaaltermijn_dagen": [], "administratie": [], "bedrijfseenheid": [],
            })

    def get_openstaande_crediteuren(self, standdatum: date = None, administratie: str = None) -> pd.DataFrame:
        if standdatum is None:
            standdatum = date.today()

        adm_filter = f'AND a."Administratie" = {_sql_str(administratie)}' if administratie else ""

        sql = f"""
        SELECT
            ift."Crediteur" as crediteur_code,
            ift."Crediteur" as crediteur_naam,
            COALESCE(d."Document code", CAST(ift."InkoopFactuurKey" AS TEXT)) as factuurnummer,
            ift."Alloc_datum" as factuurdatum,
            ift."Vervaldatum" as vervaldatum,
            ift."Bedrag" as bedrag_excl_btw,
            NULL::date as betaaldatum,
            0 as betaald,
            ift."Bedrag" as openstaand,
            COALESCE(a."Administratie", 'Onbekend') as administratie,
            COALESCE(be."Bedrijfseenheid", 'Onbekend') as bedrijfseenheid
        FROM notifica."SSM Inkoopfactuur termijnen" ift
        LEFT JOIN notifica."SSM Documenten" d ON ift."InkoopFactuurKey" = d."DocumentKey"
        LEFT JOIN notifica."SSM Bedrijfseenheden" be ON d."BedrijfseenheidKey"::bigint = be."BedrijfseenheidKey"
        LEFT JOIN notifica."SSM Administraties" a ON be."AdministratieKey" = a."AdministratieKey"
        WHERE ift."Alloc_datum" <= {_sql_date(standdatum)}
          AND ift."Bankafschrift status" = 'Openstaand'
          {adm_filter}
        ORDER BY ift."Vervaldatum" ASC
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching payables: {e}")
            return pd.DataFrame({
                "crediteur_code": [], "crediteur_naam": [], "factuurnummer": [],
                "factuurdatum": [], "vervaldatum": [], "bedrag_excl_btw": [],
                "betaaldatum": [], "betaald": [], "openstaand": [],
                "administratie": [], "bedrijfseenheid": [],
            })

    def get_historische_cashflow_per_week(
        self, startdatum: date = None, einddatum: date = None,
        administratie: str = None, administratie_key: int = None
    ) -> pd.DataFrame:
        if einddatum is None:
            einddatum = date.today()
        if startdatum is None:
            startdatum = date(einddatum.year - 1, einddatum.month, 1)

        if administratie_key:
            adm_filter = f'AND dag."AdministratieKey" = {int(administratie_key)}'
            adm_join = ""
        elif administratie:
            adm_filter = f'AND adm."Administratie" = {_sql_str(administratie)}'
            adm_join = 'JOIN stam."Administraties" adm ON dag."AdministratieKey" = adm."AdministratieKey"'
        else:
            adm_filter = ""
            adm_join = ""

        sql = f"""
        SELECT
            DATE_TRUNC('week', j."Boekdatum") as week_start,
            EXTRACT(WEEK FROM j."Boekdatum") as week_nummer,
            EXTRACT(MONTH FROM j."Boekdatum") as maand,
            SUM(CASE WHEN j."Debet/Credit" = 'D' THEN j."Bedrag" ELSE 0 END) as inkomsten,
            SUM(CASE WHEN j."Debet/Credit" = 'C' THEN j."Bedrag" ELSE 0 END) as uitgaven,
            SUM(CASE WHEN j."Debet/Credit" = 'D' THEN j."Bedrag" ELSE 0 END) -
            SUM(CASE WHEN j."Debet/Credit" = 'C' THEN j."Bedrag" ELSE 0 END) as netto
        FROM financieel."Journaalregels" j
        JOIN stam."Documenten" d ON j."DocumentKey" = d."DocumentKey"
        JOIN stam."Dagboeken" dag ON d."DagboekKey" = dag."DagboekKey"
        {adm_join}
        WHERE j."Boekdatum" >= {_sql_date(startdatum)}
          AND j."Boekdatum" < {_sql_date(einddatum)}
          AND d."StandaardEntiteitKey" = 10
          AND j."RubriekKey" = dag."DagboekRubriekKey"
          {adm_filter}
        GROUP BY DATE_TRUNC('week', j."Boekdatum"),
                 EXTRACT(WEEK FROM j."Boekdatum"),
                 EXTRACT(MONTH FROM j."Boekdatum")
        ORDER BY week_start
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching historical weekly cashflow: {e}")
            return pd.DataFrame({"week_start": [], "week_nummer": [], "maand": [], "inkomsten": [], "uitgaven": [], "netto": []})

    def get_betaalgedrag_per_debiteur(
        self, startdatum: date = None, einddatum: date = None, administratie: str = None
    ) -> pd.DataFrame:
        if einddatum is None:
            einddatum = date.today()
        if startdatum is None:
            startdatum = date(einddatum.year - 2, einddatum.month, 1)

        adm_filter = f'AND a."Administratie" = {_sql_str(administratie)}' if administratie else ""

        sql = f"""
        WITH betaalde_facturen AS (
            SELECT
                vft."Debiteur" as debiteur_code,
                vft."VerkoopfactuurDocumentKey" as factuur_key,
                MIN(vft."Alloc_datum") as factuurdatum,
                MAX(vft."Alloc_datum") as betaaldatum,
                ABS(SUM(CASE WHEN vft."Bedrag" > 0 THEN vft."Bedrag" ELSE 0 END)) as factuurbedrag
            FROM notifica."SSM Verkoopfactuur termijnen" vft
            LEFT JOIN notifica."SSM Documenten" d ON vft."VerkoopfactuurDocumentKey" = d."DocumentKey"
            LEFT JOIN notifica."SSM Bedrijfseenheden" be ON d."BedrijfseenheidKey"::bigint = be."BedrijfseenheidKey"
            LEFT JOIN notifica."SSM Administraties" a ON be."AdministratieKey" = a."AdministratieKey"
            WHERE vft."Alloc_datum" >= {_sql_date(startdatum)}
              AND vft."Alloc_datum" <= {_sql_date(einddatum)}
              {adm_filter}
            GROUP BY vft."Debiteur", vft."VerkoopfactuurDocumentKey"
            HAVING ABS(SUM(vft."Bedrag")) < 0.01 AND COUNT(*) >= 2
        ),
        debiteur_stats AS (
            SELECT
                debiteur_code,
                COUNT(*) as aantal_facturen,
                AVG(EXTRACT(EPOCH FROM (betaaldatum - factuurdatum)) / 86400) as gem_dagen_tot_betaling,
                STDDEV(EXTRACT(EPOCH FROM (betaaldatum - factuurdatum)) / 86400) as std_dagen_tot_betaling,
                MIN(EXTRACT(EPOCH FROM (betaaldatum - factuurdatum)) / 86400) as min_dagen,
                MAX(EXTRACT(EPOCH FROM (betaaldatum - factuurdatum)) / 86400) as max_dagen,
                SUM(factuurbedrag) as totaal_factuurbedrag,
                MAX(betaaldatum) as laatste_betaling
            FROM betaalde_facturen
            WHERE EXTRACT(EPOCH FROM (betaaldatum - factuurdatum)) / 86400 BETWEEN 0 AND 365
            GROUP BY debiteur_code
            HAVING COUNT(*) >= 2
        )
        SELECT debiteur_code, aantal_facturen,
            ROUND(gem_dagen_tot_betaling::numeric, 1) as gem_dagen_tot_betaling,
            ROUND(COALESCE(std_dagen_tot_betaling, 0)::numeric, 1) as std_dagen_tot_betaling,
            ROUND(min_dagen::numeric, 0) as min_dagen,
            ROUND(max_dagen::numeric, 0) as max_dagen,
            ROUND(totaal_factuurbedrag::numeric, 2) as totaal_factuurbedrag,
            laatste_betaling,
            ROUND(LEAST(1.0, (1.0 - LEAST(1.0, COALESCE(std_dagen_tot_betaling, 30) / 30.0)) * 0.7 +
                LEAST(1.0, aantal_facturen / 10.0) * 0.3)::numeric, 2) as betrouwbaarheid
        FROM debiteur_stats ORDER BY totaal_factuurbedrag DESC
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching debtor payment behavior: {e}")
            return pd.DataFrame({"debiteur_code": [], "aantal_facturen": [], "gem_dagen_tot_betaling": [],
                                 "std_dagen_tot_betaling": [], "min_dagen": [], "max_dagen": [],
                                 "totaal_factuurbedrag": [], "laatste_betaling": [], "betrouwbaarheid": []})

    def get_betaalgedrag_per_crediteur(
        self, startdatum: date = None, einddatum: date = None, administratie: str = None
    ) -> pd.DataFrame:
        if einddatum is None:
            einddatum = date.today()
        if startdatum is None:
            startdatum = date(einddatum.year - 2, einddatum.month, 1)

        adm_filter = f'AND a."Administratie" = {_sql_str(administratie)}' if administratie else ""

        sql = f"""
        WITH betaalde_facturen AS (
            SELECT
                b."Crediteur" as crediteur_code,
                b."Vervaldatum" as vervaldatum,
                b."Betaaldatum" as betaaldatum,
                ABS(b."BetaaldExclBTW") as factuurbedrag
            FROM notifica."SSM Betalingen per inkoopregel" b
            LEFT JOIN notifica."SSM Administraties" a ON b."AdministratieKey" = a."AdministratieKey"
            WHERE b."Betaaldatum" IS NOT NULL
              AND b."Vervaldatum" IS NOT NULL
              AND b."Betaaldatum" >= {_sql_date(startdatum)}
              AND b."Betaaldatum" <= {_sql_date(einddatum)}
              AND ABS(b."BetaaldExclBTW") > 0
              {adm_filter}
        ),
        crediteur_stats AS (
            SELECT
                crediteur_code,
                COUNT(*) as aantal_facturen,
                AVG(EXTRACT(EPOCH FROM (betaaldatum - vervaldatum)) / 86400) as gem_dagen_tot_betaling,
                STDDEV(EXTRACT(EPOCH FROM (betaaldatum - vervaldatum)) / 86400) as std_dagen_tot_betaling,
                SUM(factuurbedrag) as totaal_factuurbedrag,
                MAX(betaaldatum) as laatste_betaling
            FROM betaalde_facturen
            WHERE EXTRACT(EPOCH FROM (betaaldatum - vervaldatum)) / 86400 BETWEEN -90 AND 365
            GROUP BY crediteur_code HAVING COUNT(*) >= 2
        )
        SELECT crediteur_code, aantal_facturen,
            ROUND(gem_dagen_tot_betaling::numeric, 1) as gem_dagen_tot_betaling,
            ROUND(COALESCE(std_dagen_tot_betaling, 0)::numeric, 1) as std_dagen_tot_betaling,
            ROUND(totaal_factuurbedrag::numeric, 2) as totaal_factuurbedrag,
            laatste_betaling,
            ROUND(LEAST(1.0, (1.0 - LEAST(1.0, COALESCE(std_dagen_tot_betaling, 30) / 30.0)) * 0.7 +
                LEAST(1.0, aantal_facturen / 10.0) * 0.3)::numeric, 2) as betrouwbaarheid
        FROM crediteur_stats ORDER BY totaal_factuurbedrag DESC
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching creditor payment behavior: {e}")
            return pd.DataFrame({"crediteur_code": [], "aantal_facturen": [], "gem_dagen_tot_betaling": [],
                                 "std_dagen_tot_betaling": [], "totaal_factuurbedrag": [],
                                 "laatste_betaling": [], "betrouwbaarheid": []})

    def get_terugkerende_kosten(self, startdatum: date = None, einddatum: date = None, administratie: str = None) -> pd.DataFrame:
        if einddatum is None:
            einddatum = date.today()
        if startdatum is None:
            startdatum = date(einddatum.year - 1, einddatum.month, 1)

        adm_filter = f'AND a."Administratie" = {_sql_str(administratie)}' if administratie else ""
        adm_join = 'JOIN notifica."SSM Administraties" a ON j."AdministratieKey" = a."AdministratieKey"' if administratie else ""

        sql = f"""
        SELECT
            DATE_TRUNC('month', j."Boekdatum") as maand,
            CASE
                WHEN rub."Rubriek Code" LIKE '4%%' THEN 'Personeelskosten'
                WHEN rub."Rubriek Code" LIKE '61%%' THEN 'Huisvestingskosten'
                WHEN rub."Rubriek Code" LIKE '62%%' THEN 'Machinekosten'
                WHEN rub."Rubriek Code" LIKE '65%%' THEN 'Autokosten'
                ELSE 'Overige vaste kosten'
            END as kostensoort,
            SUM(CASE WHEN j."Debet/Credit" = 'D' THEN j."Bedrag" ELSE 0 END) -
            SUM(CASE WHEN j."Debet/Credit" = 'C' THEN j."Bedrag" ELSE 0 END) as bedrag
        FROM financieel."Journaalregels" j
        JOIN financieel."Rubrieken" rub ON j."RubriekKey" = rub."RubriekKey"
        {adm_join}
        WHERE j."Boekdatum" >= {_sql_date(startdatum)}
          AND j."Boekdatum" < {_sql_date(einddatum)}
          AND (rub."Rubriek Code" LIKE '4%%' OR rub."Rubriek Code" LIKE '61%%'
               OR rub."Rubriek Code" LIKE '62%%' OR rub."Rubriek Code" LIKE '65%%')
          {adm_filter}
        GROUP BY DATE_TRUNC('month', j."Boekdatum"), kostensoort
        ORDER BY maand
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching recurring costs: {e}")
            return pd.DataFrame({"maand": [], "kostensoort": [], "bedrag": []})

    def get_historisch_betalingsgedrag(self) -> pd.DataFrame:
        sql = """
        SELECT
            DATE_TRUNC('month', j."Boekdatum") as maand,
            30 as gem_betaaltermijn_debiteuren,
            30 as gem_betaaltermijn_crediteuren,
            SUM(CASE WHEN j."Debet/Credit" = 'D' THEN j."Bedrag" ELSE 0 END) as inkomsten,
            SUM(CASE WHEN j."Debet/Credit" = 'C' THEN j."Bedrag" ELSE 0 END) as uitgaven
        FROM financieel."Journaalregels" j
        JOIN stam."Documenten" d ON j."DocumentKey" = d."DocumentKey"
        JOIN stam."Dagboeken" dag ON d."DagboekKey" = dag."DagboekKey"
        WHERE j."Boekdatum" >= CURRENT_DATE - INTERVAL '12 months'
          AND d."StandaardEntiteitKey" = 10
          AND j."RubriekKey" = dag."DagboekRubriekKey"
        GROUP BY DATE_TRUNC('month', j."Boekdatum")
        ORDER BY maand DESC
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching payment history: {e}")
            return pd.DataFrame({"maand": [], "gem_betaaltermijn_debiteuren": [],
                                 "gem_betaaltermijn_crediteuren": [], "inkomsten": [], "uitgaven": []})

    def get_geplande_salarissen(self) -> pd.DataFrame:
        return pd.DataFrame({"betaaldatum": [], "omschrijving": [], "bedrag": []})

    def get_voorziening_debiteuren(self, standdatum: date = None, administratie: str = None) -> float:
        if standdatum is None:
            standdatum = date.today()
        if not administratie:
            return 0.0
        sql = f"""
        SELECT
            SUM(CASE WHEN j."Debet/Credit" = 'D' THEN j."Bedrag" ELSE 0 END) -
            SUM(CASE WHEN j."Debet/Credit" = 'C' THEN j."Bedrag" ELSE 0 END) as voorziening
        FROM financieel."Journaalregels" j
        JOIN financieel."Rubrieken" rub ON j."RubriekKey" = rub."RubriekKey"
        JOIN notifica."SSM Administraties" a ON j."AdministratieKey" = a."AdministratieKey"
        WHERE j."Boekdatum" BETWEEN
              DATE_TRUNC('year', {_sql_date(standdatum)}::date) - INTERVAL '1 year'
              AND DATE_TRUNC('year', {_sql_date(standdatum)}::date) - INTERVAL '1 day'
          AND rub."Rubriek Code" = '1230'
          AND a."Administratie" = {_sql_str(administratie)}
        """
        try:
            df = self._query(sql)
            if df.empty or df['voorziening'].iloc[0] is None:
                return 0.0
            return float(df['voorziening'].iloc[0])
        except Exception:
            return 0.0

    def get_calibrated_dso_dpo(self, administratie: str, lookback_months: int = 12) -> dict:
        result = {'dso': None, 'dpo': None}

        dso_sql = f"""
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY b."Betaaldatum"::date - b."Factuurdatum"::date
        ) as median_dso
        FROM notifica."SSM Betalingen per opbrengstregel" b
        WHERE b."Betaaldatum" IS NOT NULL AND b."Factuurdatum" IS NOT NULL
          AND b."Betaaldatum" >= CURRENT_DATE - INTERVAL '{int(lookback_months)} months'
          AND b."BetaaldExclBTW" > 0
        """
        try:
            df = self._query(dso_sql)
            if not df.empty and df['median_dso'].iloc[0] is not None:
                result['dso'] = float(df['median_dso'].iloc[0])
        except Exception as e:
            print(f"Could not calculate DSO: {e}")

        dpo_sql = f"""
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY b."Betaaldatum"::date - b."Vervaldatum"::date
        ) as median_days_vs_due
        FROM notifica."SSM Betalingen per inkoopregel" b
        JOIN notifica."SSM Administraties" a ON b."AdministratieKey" = a."AdministratieKey"
        WHERE b."Betaaldatum" IS NOT NULL AND b."Vervaldatum" IS NOT NULL
          AND a."Administratie" = {_sql_str(administratie)}
          AND b."Betaaldatum" >= CURRENT_DATE - INTERVAL '{int(lookback_months)} months'
        """
        try:
            df = self._query(dpo_sql)
            if not df.empty and df['median_days_vs_due'].iloc[0] is not None:
                result['dpo'] = float(df['median_days_vs_due'].iloc[0])
        except Exception as e:
            print(f"Could not calculate DPO: {e}")

        return result

    # =========================================================================
    # NIEUWE methoden voor V7 (Structuur x Volume x Realiteit)
    # =========================================================================

    def get_btw_aangifteregels(self, startdatum: date = None, einddatum: date = None) -> pd.DataFrame:
        """BTW aangifteregels voor ritme-detectie (kwartaal/maandelijks)."""
        if einddatum is None:
            einddatum = date.today()
        if startdatum is None:
            startdatum = date(einddatum.year - 2, einddatum.month, 1)

        sql = f"""
        SELECT
            DATE_TRUNC('month', d."Boekdatum") as maand,
            SUM(btw."BTW bedrag") as btw_bedrag,
            COUNT(*) as aantal_regels
        FROM financieel."BTW aangifteregels" btw
        JOIN stam."Documenten" d ON btw."FactuurDocumentKey" = d."DocumentKey"
        WHERE d."Boekdatum" >= {_sql_date(startdatum)}
          AND d."Boekdatum" < {_sql_date(einddatum)}
        GROUP BY DATE_TRUNC('month', d."Boekdatum")
        ORDER BY maand
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching BTW data: {e}")
            return pd.DataFrame({"maand": [], "btw_bedrag": [], "aantal_regels": []})

    def get_salarishistorie(self, startdatum: date = None, einddatum: date = None) -> pd.DataFrame:
        """Salarishistorie per maand via journaalboekingen op personeelskostenrubrieken (4xxx).

        Zenith/Syntess heeft geen apart salarismodule — salaris wordt geboekt
        op rubrieken die beginnen met '4' (personeelskosten).
        """
        if einddatum is None:
            einddatum = date.today()
        if startdatum is None:
            startdatum = date(einddatum.year - 2, einddatum.month, 1)

        sql = f"""
        SELECT
            DATE_TRUNC('month', j."Boekdatum") as maand,
            SUM(CASE WHEN j."Debet/Credit" = 'D' THEN j."Bedrag" ELSE 0 END) -
            SUM(CASE WHEN j."Debet/Credit" = 'C' THEN j."Bedrag" ELSE 0 END) as salaris_bedrag,
            0 as aantal_medewerkers
        FROM financieel."Journaalregels" j
        JOIN financieel."Rubrieken" rub ON j."RubriekKey" = rub."RubriekKey"
        WHERE j."Boekdatum" >= {_sql_date(startdatum)}
          AND j."Boekdatum" < {_sql_date(einddatum)}
          AND rub."Rubriek Code" LIKE '4%%'
        GROUP BY DATE_TRUNC('month', j."Boekdatum")
        ORDER BY maand
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching salary history: {e}")
            return pd.DataFrame({"maand": [], "salaris_bedrag": [], "aantal_medewerkers": []})

    def get_budgetten(self, boekjaar: int = None, administratie: str = None) -> pd.DataFrame:
        """Budgetten uit het semantisch model."""
        if boekjaar is None:
            boekjaar = date.today().year

        adm_filter = f'AND a."Administratie" = {_sql_str(administratie)}' if administratie else ""

        sql = f"""
        SELECT
            b."Begindatum" as datum,
            b."Bedrag" as budget_bedrag,
            rub."Rubriek" as rubriek,
            rub."Rubriek Code" as rubriek_code
        FROM financieel."Budgetten" b
        LEFT JOIN financieel."Rubrieken" rub ON b."RubriekKey" = rub."RubriekKey"
        LEFT JOIN notifica."SSM Administraties" a ON b."AdministratieKey" = a."AdministratieKey"
        WHERE EXTRACT(YEAR FROM b."Begindatum") = {int(boekjaar)}
          {adm_filter}
        ORDER BY b."Begindatum"
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching budgets: {e}")
            return pd.DataFrame({"datum": [], "budget_bedrag": [], "rubriek": [], "rubriek_code": []})

    def get_orderportefeuille(self, administratie: str = None) -> pd.DataFrame:
        """Openstaande orders (orderportefeuille) via eenmalige orderregels + projecten."""
        adm_filter = f'AND a."Administratie" = {_sql_str(administratie)}' if administratie else ""

        sql = f"""
        SELECT
            eor."Document code" as order_code,
            eor."FactureerDatum" as opleverdatum,
            p."Einddatum" as einddatum,
            eor."TotaalRegelbedrag Excl. BTW" as orderbedrag,
            p."Status" as status
        FROM projecten."Eenmalige Orderregels" eor
        LEFT JOIN projecten."Projecten" p ON eor."ProjectKey" = p."ProjectKey"
        LEFT JOIN notifica."SSM Administraties" a ON eor."AdministratieKey" = a."AdministratieKey"
        WHERE eor."TotaalRegelbedrag Excl. BTW" > 0
          {adm_filter}
        ORDER BY eor."FactureerDatum"
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching order portfolio: {e}")
            return pd.DataFrame({"order_code": [], "opleverdatum": [], "einddatum": [],
                                 "orderbedrag": [], "status": []})

    def get_projecten_met_status(self, administratie: str = None) -> pd.DataFrame:
        """Actieve projecten met status en omzet."""
        adm_filter = f'AND a."Administratie" = {_sql_str(administratie)}' if administratie else ""

        sql = f"""
        SELECT
            p."Project code" as project_code,
            p."Project titel" as project_titel,
            p."Projectstatus" as status,
            COALESCE(pk."Kosten", 0) as kosten,
            COALESCE(po."Opbrengsten", 0) as opbrengsten
        FROM projecten."Projecten" p
        LEFT JOIN (
            SELECT "ProjectKey", SUM("Bedrag") as "Kosten"
            FROM projecten."Project Kosten" GROUP BY "ProjectKey"
        ) pk ON p."ProjectKey" = pk."ProjectKey"
        LEFT JOIN (
            SELECT "ProjectKey", SUM("Bedrag") as "Opbrengsten"
            FROM projecten."Project Opbrengsten" GROUP BY "ProjectKey"
        ) po ON p."ProjectKey" = po."ProjectKey"
        LEFT JOIN notifica."SSM Administraties" a ON p."AdministratieKey" = a."AdministratieKey"
        WHERE p."Projectstatus" NOT IN ('Afgerond', 'Vervallen')
          {adm_filter}
        ORDER BY po."Opbrengsten" DESC NULLS LAST
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching projects: {e}")
            return pd.DataFrame({"project_code": [], "project_titel": [], "status": [],
                                 "kosten": [], "opbrengsten": []})

    def get_service_orders_prognose(self, administratie: str = None) -> pd.DataFrame:
        """Service orders prognose (verwachte toekomstige omzet)."""
        adm_filter = f'AND a."Administratie" = {_sql_str(administratie)}' if administratie else ""

        sql = f"""
        SELECT
            sp."Factureerdatum" as verwachte_factuurdatum,
            sp."Factureerbedrag excl. BTW" as verwacht_bedrag,
            sp."document status" as status
        FROM service."Service Orders Prognose" sp
        LEFT JOIN notifica."SSM Administraties" a ON sp."AdministratieKey" = a."AdministratieKey"
        WHERE sp."Factureerdatum" >= CURRENT_DATE
          {adm_filter}
        ORDER BY sp."Factureerdatum"
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching service orders prognose: {e}")
            return pd.DataFrame({"verwachte_factuurdatum": [], "verwacht_bedrag": [], "status": []})

    # =========================================================================
    # NIEUW: Orderregels, Abonnementen, BTW Prognose
    # =========================================================================

    def get_orderregels_periodiek(self, administratie: str = None) -> pd.DataFrame:
        """Periodieke orderregels: terugkerende facturatie per project (huur, onderhoud, etc.)."""
        adm_filter = f'AND por."AdministratieKey" IN (SELECT "AdministratieKey" FROM notifica."SSM Administraties" WHERE "Administratie" = {_sql_str(administratie)})' if administratie else ""

        sql = f"""
        SELECT
            por."OrderDocumentKey",
            por."ProjectKey",
            por."Geplande factureerdatum" as geplande_factuurdatum,
            por."Werkelijk factuurdatum" as werkelijke_factuurdatum,
            por."Brutoprijs per eenheid" as prijs_per_eenheid,
            por."Aantal" as aantal,
            por."Kalendereenheid" as kalendereenheid,
            por."Aantal kalendereenheden" as aantal_periodes,
            por."Ingangsdatum index" as ingangsdatum,
            por."Einddatum" as einddatum,
            por."Omschrijving" as omschrijving,
            (por."Brutoprijs per eenheid" * por."Aantal" * por."Kortingfactor" * por."BTWfactor") as regelbedrag
        FROM projecten."Periodieke Orderregels" por
        WHERE por."Geplande factureerdatum" IS NOT NULL
          AND por."Brutoprijs per eenheid" > 0
          {adm_filter}
        ORDER BY por."Geplande factureerdatum"
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching periodieke orderregels: {e}")
            return pd.DataFrame()

    def get_orderregels_eenmalig(self, administratie: str = None) -> pd.DataFrame:
        """Eenmalige orderregels: projectfacturatie met verwachte factuurdatum."""
        adm_filter = f'AND eor."AdministratieKey" IN (SELECT "AdministratieKey" FROM notifica."SSM Administraties" WHERE "Administratie" = {_sql_str(administratie)})' if administratie else ""

        sql = f"""
        SELECT
            eor."OrderDocumentKey",
            eor."ProjectKey",
            eor."FactureerDatum" as factuurdatum,
            eor."TotaalRegelbedrag Excl. BTW" as totaalbedrag,
            eor."Nog te factureren excl. BTW" as nog_te_factureren,
            eor."Document status" as status,
            eor."Omschrijving" as omschrijving
        FROM projecten."Eenmalige Orderregels" eor
        WHERE eor."Nog te factureren excl. BTW" > 0
          {adm_filter}
        ORDER BY eor."FactureerDatum"
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching eenmalige orderregels: {e}")
            return pd.DataFrame()

    def get_abonnementen(self, administratie: str = None) -> pd.DataFrame:
        """Actieve abonnementen: recurring revenue uit servicecontracten."""
        adm_filter = f'AND ab."AdministratieKey" IN (SELECT "AdministratieKey" FROM notifica."SSM Administraties" WHERE "Administratie" = {_sql_str(administratie)})' if administratie else ""

        sql = f"""
        SELECT
            ab."AbonnementKey",
            ab."Abonnementcode" as code,
            ab."Abonnement omschrijving" as omschrijving,
            ab."Status" as status,
            ab."Facturatie plandatum" as facturatie_plandatum,
            ab."Facturatiebedrag per eenheid" as bedrag_per_eenheid,
            ab."Facturatie Aantal" as facturatie_aantal,
            ab."Fin. aantal kal.eenheden" as aantal_periodes,
            ab."financieel kalendereenheid" as kalendereenheid,
            ab."Ingangsdatum" as ingangsdatum,
            ab."Einddatum" as einddatum,
            (ab."Facturatiebedrag per eenheid" * ab."Facturatie Aantal") as facturatiebedrag
        FROM financieel."Abonnementen" ab
        WHERE ab."Status" NOT IN ('Vervallen', 'Opgezegd', 'Beëindigd')
          AND (ab."Einddatum" IS NULL OR ab."Einddatum" >= CURRENT_DATE)
          {adm_filter}
        ORDER BY ab."Facturatie plandatum"
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching abonnementen: {e}")
            return pd.DataFrame()

    def get_service_contract_intake(self, administratie: str = None) -> pd.DataFrame:
        """Service contract intake: jaarwaarde van lopende servicecontracten."""
        sql = f"""
        SELECT
            sci."Boekdatum" as boekdatum,
            sci."Jaarbedrag zonder einddatum" as jaarbedrag_doorlopend,
            sci."Jaarbedrag met einddatum" as jaarbedrag_eindig
        FROM service."Order Intake Servicecontracten" sci
        WHERE sci."Boekdatum" >= CURRENT_DATE - INTERVAL '12 months'
        ORDER BY sci."Boekdatum" DESC
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching service contract intake: {e}")
            return pd.DataFrame()

    def get_btw_prognose(self, administratie: str = None) -> pd.DataFrame:
        """BTW prognose uit SSM: te vorderen en af te dragen BTW per document."""
        adm_filter = f'AND bp."AdministratieKey" IN (SELECT "AdministratieKey" FROM notifica."SSM Administraties" WHERE "Administratie" = {_sql_str(administratie)})' if administratie else ""

        sql = f"""
        SELECT
            bp."BTW te vorderen" as btw_te_vorderen,
            bp."BTW af te dragen" as btw_af_te_dragen,
            bp."BTW bedrag" as btw_bedrag,
            bp."Debet/Credit" as debet_credit,
            bp."Standaard entiteit" as entiteit,
            bp."Document code" as document_code
        FROM notifica."SSM Prognose BTW" bp
        WHERE bp."BTW bedrag" != 0
          {adm_filter}
        """
        try:
            return self._query(sql)
        except Exception as e:
            print(f"Error fetching BTW prognose: {e}")
            return pd.DataFrame()

    def get_beschikbare_administraties(self) -> list:
        """Haal beschikbare administraties op."""
        sql = """
        SELECT DISTINCT a."Administratie"
        FROM notifica."SSM Administraties" a
        WHERE a."Administratie" IS NOT NULL
        ORDER BY a."Administratie"
        """
        try:
            df = self._query(sql)
            return df["Administratie"].tolist() if not df.empty else []
        except Exception:
            return []


# =============================================================================
# DirectDWHDataSource — Directe Azure SQL verbinding (bypass API)
# =============================================================================

class DirectDWHDataSource(NotificaDataSource):
    """Data source via directe Azure SQL verbinding naar Syntess DWH.

    Gebruikt dezelfde SQL queries als NotificaDataSource, maar connecteert
    direct via pyodbc in plaats van de Notifica API.
    Fallback als de API niet beschikbaar is.
    """

    def __init__(self, klantnummer: str):
        # Skip NotificaDataSource.__init__ — we gebruiken geen API client
        self.klantnummer = int(klantnummer)
        self._conn = None

        password = os.getenv('SYNTESS_DB_PASSWORD', '')
        if not password:
            raise ValueError("SYNTESS_DB_PASSWORD niet gevonden in .env")

        import pyodbc
        self._conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=bisqq.database.windows.net,1433;"
            f"DATABASE={klantnummer}DWH;"
            "UID=server_admin;"
            f"PWD={password};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30;"
        )

    def _query(self, sql: str) -> pd.DataFrame:
        """Execute SQL direct op Azure SQL DWH."""
        import pyodbc
        conn = pyodbc.connect(self._conn_str)
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        conn.close()
        df = pd.DataFrame.from_records(rows, columns=columns)
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='ignore')
        return df

    def test_connection(self) -> bool:
        try:
            self._query("SELECT 1 as test")
            return True
        except Exception as e:
            print(f"Direct DWH connection failed: {e}")
            return False


# =============================================================================
# MockDatabase — Demo modus
# =============================================================================

class MockDatabase:
    """Mock database for demo purposes."""

    def __init__(self):
        import numpy as np
        self.np = np
        self.today = date.today()

    def get_banksaldo(self, standdatum=None, administratie=None):
        return pd.DataFrame({
            "bank_naam": ["ING Zakelijk", "Rabobank"], "rekeningnummer": ["NL91INGB01234", "NL02RABO98765"],
            "saldo": [125000.0, 45000.0], "datum": [self.today] * 2,
        })

    def get_openstaande_debiteuren(self, standdatum=None, administratie=None):
        self.np.random.seed(42)
        n = 15
        return pd.DataFrame({
            "debiteur_code": [f"DEB{i:04d}" for i in range(n)],
            "debiteur_naam": self.np.random.choice(["Bouwbedrijf De Vries", "Installatie Jansen", "Techniek Plus", "Klimaat BV", "Electro NL"], n),
            "factuurnummer": [f"VF2024{i:05d}" for i in range(n)],
            "factuurdatum": pd.date_range(self.today - timedelta(60), periods=n, freq='4D'),
            "vervaldatum": pd.date_range(self.today - timedelta(30), periods=n, freq='4D'),
            "bedrag_excl_btw": self.np.random.uniform(1500, 45000, n).round(2),
            "betaald": self.np.zeros(n), "openstaand": self.np.random.uniform(1500, 45000, n).round(2),
            "betaaltermijn_dagen": self.np.random.choice([14, 30, 45], n),
            "administratie": ["Demo"] * n, "bedrijfseenheid": ["Demo"] * n,
        })

    def get_openstaande_crediteuren(self, standdatum=None, administratie=None):
        self.np.random.seed(43)
        n = 10
        return pd.DataFrame({
            "crediteur_code": [f"CRED{i:04d}" for i in range(n)],
            "crediteur_naam": self.np.random.choice(["Groothandel TA", "Sanitair GH", "Elektro Supplies", "Bouwmat Direct"], n),
            "factuurnummer": [f"INK2024{i:05d}" for i in range(n)],
            "factuurdatum": pd.date_range(self.today - timedelta(30), periods=n, freq='3D'),
            "vervaldatum": pd.date_range(self.today, periods=n, freq='3D'),
            "bedrag_excl_btw": self.np.random.uniform(500, 25000, n).round(2),
            "betaald": self.np.zeros(n), "openstaand": self.np.random.uniform(500, 25000, n).round(2),
            "administratie": ["Demo"] * n, "bedrijfseenheid": ["Demo"] * n,
        })

    def get_historische_cashflow_per_week(self, startdatum=None, einddatum=None, administratie=None, administratie_key=None):
        self.np.random.seed(46)
        weeks = pd.date_range(end=self.today, periods=52, freq='W-MON')
        rows = []
        for w in weeks:
            m = w.month
            sf = 0.85 if m in [6, 7, 8] else (1.15 if m in [11, 12, 1] else 1.0)
            ink = 180000 * sf * self.np.random.uniform(0.8, 1.2)
            uit = 150000 * sf * self.np.random.uniform(0.85, 1.15)
            rows.append({"week_start": w, "week_nummer": w.isocalendar()[1], "maand": m,
                         "inkomsten": round(ink, 2), "uitgaven": round(uit, 2), "netto": round(ink - uit, 2)})
        return pd.DataFrame(rows)

    def get_betaalgedrag_per_debiteur(self, startdatum=None, einddatum=None, administratie=None):
        return pd.DataFrame({
            "debiteur_code": ["DEB0001", "DEB0002", "DEB0003"],
            "aantal_facturen": [12, 8, 5], "gem_dagen_tot_betaling": [25.0, 35.0, 55.0],
            "std_dagen_tot_betaling": [5.0, 10.0, 20.0], "min_dagen": [15, 20, 25],
            "max_dagen": [35, 55, 90], "totaal_factuurbedrag": [120000, 85000, 45000],
            "laatste_betaling": [self.today - timedelta(10)] * 3, "betrouwbaarheid": [0.9, 0.7, 0.4],
        })

    def get_betaalgedrag_per_crediteur(self, startdatum=None, einddatum=None, administratie=None):
        return pd.DataFrame({
            "crediteur_code": ["CRED0001", "CRED0002"],
            "aantal_facturen": [15, 10], "gem_dagen_tot_betaling": [28.0, 32.0],
            "std_dagen_tot_betaling": [5.0, 8.0], "totaal_factuurbedrag": [60000, 40000],
            "laatste_betaling": [self.today - timedelta(5)] * 2, "betrouwbaarheid": [0.85, 0.7],
        })

    def get_geplande_salarissen(self):
        return pd.DataFrame({"betaaldatum": [], "omschrijving": [], "bedrag": []})

    def get_historisch_betalingsgedrag(self):
        self.np.random.seed(44)
        months = pd.date_range(end=self.today, periods=12, freq='ME')
        return pd.DataFrame({
            "maand": months, "gem_betaaltermijn_debiteuren": self.np.random.uniform(28, 45, 12).round(1),
            "gem_betaaltermijn_crediteuren": self.np.random.uniform(25, 35, 12).round(1),
            "inkomsten": self.np.random.uniform(150000, 250000, 12).round(2),
            "uitgaven": self.np.random.uniform(120000, 200000, 12).round(2),
        })

    def get_terugkerende_kosten(self, startdatum=None, einddatum=None, administratie=None):
        self.np.random.seed(45)
        months = pd.date_range(end=self.today, periods=12, freq='ME')
        rows = []
        for d in months:
            for soort, base in [("Personeelskosten", 85000), ("Huisvestingskosten", 12000), ("Autokosten", 8000)]:
                rows.append({"maand": d, "kostensoort": soort, "bedrag": base + self.np.random.uniform(-base * 0.1, base * 0.1)})
        return pd.DataFrame(rows)

    def get_btw_aangifteregels(self, startdatum=None, einddatum=None):
        months = pd.date_range(end=self.today, periods=24, freq='ME')
        return pd.DataFrame({"maand": months, "btw_bedrag": [25000 if m.month in [1,4,7,10] else 0 for m in months],
                             "aantal_regels": [50 if m.month in [1,4,7,10] else 0 for m in months]})

    def get_salarishistorie(self, startdatum=None, einddatum=None):
        months = pd.date_range(end=self.today, periods=24, freq='ME')
        bedragen = [95000 if m.month == 5 else (88000 if m.month == 12 else 82000) for m in months]
        return pd.DataFrame({"maand": months, "salaris_bedrag": bedragen, "aantal_medewerkers": [25] * 24})

    def get_budgetten(self, boekjaar=None, administratie=None):
        return pd.DataFrame({"datum": [], "budget_bedrag": [], "rubriek": [], "rubriek_code": []})

    def get_orderportefeuille(self, administratie=None):
        return pd.DataFrame({"order_code": [], "opleverdatum": [], "einddatum": [], "orderbedrag": [], "status": []})

    def get_projecten_met_status(self, administratie=None):
        return pd.DataFrame({"project_code": [], "project_titel": [], "status": [], "kosten": [], "opbrengsten": []})

    def get_service_orders_prognose(self, administratie=None):
        return pd.DataFrame({"verwachte_factuurdatum": [], "verwacht_bedrag": [], "status": []})

    def get_orderregels_periodiek(self, administratie=None):
        self.np.random.seed(50)
        rows = []
        for i in range(8):
            plan_date = self.today + timedelta(days=self.np.random.randint(7, 90))
            rows.append({
                "OrderDocumentKey": i + 1,
                "ProjectKey": 100 + i,
                "geplande_factuurdatum": plan_date,
                "werkelijke_factuurdatum": None,
                "prijs_per_eenheid": float(self.np.random.uniform(2000, 15000)),
                "aantal": 1.0,
                "kalendereenheid": "Maand",
                "aantal_periodes": 12,
                "ingangsdatum": self.today - timedelta(days=180),
                "einddatum": self.today + timedelta(days=365),
                "omschrijving": f"Onderhoud contract {i+1}",
                "regelbedrag": float(self.np.random.uniform(2500, 18000)),
            })
        return pd.DataFrame(rows)

    def get_orderregels_eenmalig(self, administratie=None):
        self.np.random.seed(51)
        rows = []
        for i in range(5):
            rows.append({
                "OrderDocumentKey": 200 + i,
                "ProjectKey": 200 + i,
                "factuurdatum": self.today + timedelta(days=self.np.random.randint(14, 70)),
                "totaalbedrag": float(self.np.random.uniform(25000, 150000)),
                "nog_te_factureren": float(self.np.random.uniform(10000, 100000)),
                "status": self.np.random.choice(["Opdracht", "Actief", "Offerte"]),
                "omschrijving": f"Project installatie {i+1}",
            })
        return pd.DataFrame(rows)

    def get_abonnementen(self, administratie=None):
        self.np.random.seed(52)
        rows = []
        for i in range(6):
            bedrag = float(self.np.random.uniform(500, 5000))
            rows.append({
                "AbonnementKey": 300 + i,
                "code": f"ABO-{i+1:04d}",
                "omschrijving": f"Servicecontract {['HVAC', 'Elektra', 'Sanitair', 'Beveiliging', 'Lift', 'Brandveiligheid'][i]}",
                "status": "Actief",
                "facturatie_plandatum": self.today + timedelta(days=self.np.random.randint(0, 90)),
                "bedrag_per_eenheid": bedrag,
                "facturatie_aantal": 1.0,
                "aantal_periodes": self.np.random.choice([1, 3, 12]),
                "kalendereenheid": self.np.random.choice(["Maand", "Kwartaal"]),
                "ingangsdatum": self.today - timedelta(days=365),
                "einddatum": None,
                "facturatiebedrag": bedrag,
            })
        return pd.DataFrame(rows)

    def get_service_contract_intake(self, administratie=None):
        self.np.random.seed(53)
        months = pd.date_range(end=self.today, periods=12, freq='ME')
        return pd.DataFrame({
            "boekdatum": months,
            "jaarbedrag_doorlopend": self.np.random.uniform(180000, 220000, 12).round(2),
            "jaarbedrag_eindig": self.np.random.uniform(60000, 80000, 12).round(2),
        })

    def get_btw_prognose(self, administratie=None):
        return pd.DataFrame({
            "btw_te_vorderen": [12500, 8300, 15200],
            "btw_af_te_dragen": [28000, 22000, 31000],
            "btw_bedrag": [15500, 13700, 15800],
            "debet_credit": ["C", "C", "C"],
            "entiteit": ["Verkoopfactuur", "Inkoopfactuur", "Verkoopfactuur"],
            "document_code": ["VF001", "IF001", "VF002"],
        })

    def get_voorziening_debiteuren(self, standdatum=None, administratie=None):
        return 0.0

    def get_calibrated_dso_dpo(self, administratie=None, lookback_months=12):
        return {'dso': 32.0, 'dpo': 5.0}

    def get_beschikbare_administraties(self):
        return ["Demo Administratie"]


# =============================================================================
# FailedConnectionDatabase — Foutmelding
# =============================================================================

class FailedConnectionDatabase:
    """Placeholder when API connection fails."""

    def __init__(self, klantnummer: str, error: str = ""):
        self.klantnummer = klantnummer
        self.error_msg = error or f"Kon niet verbinden met API voor klant {klantnummer}"

    def __getattr__(self, name):
        """Elke methode-aanroep retourneert leeg DataFrame of default waarde."""
        def method(*args, **kwargs):
            if name in ('get_voorziening_debiteuren',):
                return 0.0
            if name in ('get_calibrated_dso_dpo',):
                return {'dso': None, 'dpo': None}
            if name in ('get_beschikbare_administraties',):
                return []
            return pd.DataFrame()
        return method


# =============================================================================
# Factory function
# =============================================================================

def get_database(use_mock: bool = True, customer_code: Optional[str] = None) -> Union[NotificaDataSource, DirectDWHDataSource, MockDatabase, FailedConnectionDatabase]:
    """
    Factory: Notifica API → Direct DWH → MockDatabase.

    SQL queries zijn geschreven voor PostgreSQL (Notifica API).
    DirectDWH (Azure SQL Server) heeft compatibiliteitsproblemen.

    Args:
        use_mock: True = demo data
        customer_code: Klantnummer (bijv. "1229")
    """
    if use_mock:
        return MockDatabase()

    klantnummer = customer_code or os.getenv('KLANTNUMMER', '')
    if not klantnummer:
        print("[WARNING] Geen klantnummer, gebruik demo data")
        return MockDatabase()

    # Primair: Notifica API (PostgreSQL-compatible queries)
    try:
        db = NotificaDataSource(klantnummer)
        if db.test_connection():
            print(f"[SUCCESS] Verbonden via API voor klant {klantnummer}")
            return db
    except Exception as e:
        print(f"[INFO] API niet beschikbaar: {e}")

    # Fallback: Directe DWH-verbinding (Azure SQL Server — SQL syntax kan afwijken)
    if os.getenv('SYNTESS_DB_PASSWORD'):
        try:
            db = DirectDWHDataSource(klantnummer)
            if db.test_connection():
                print(f"[SUCCESS] Verbonden via directe DWH voor klant {klantnummer}")
                return db
        except Exception as e:
            print(f"[INFO] Directe DWH niet beschikbaar: {e}")

    return FailedConnectionDatabase(klantnummer, "Geen verbinding mogelijk (API noch DirectDWH)")


# Backwards compatibility
SyntessDWHConnection = NotificaDataSource
DatabaseConnection = NotificaDataSource
