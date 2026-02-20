"""Direct PostgreSQL DWH reader implementation.

Connects directly to the client's PostgreSQL data warehouse via VPN.
Database name = klantnummer (e.g. 1241 for Beck & v.d. Kroef).
"""

from datetime import date

import psycopg
from psycopg.rows import dict_row

from app.db.dwh_queries import (
    QUERY_BESTEKPARAGRAFEN,
    QUERY_DEELPROJECTEN,
    QUERY_HOOFDPROJECTEN,
    QUERY_PROJECTDATA,
)


class PostgresDWHReader:
    """Read-only DWH access via direct PostgreSQL connection."""

    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        self.conninfo = f"host={host} port={port} dbname={database} user={user} password={password}"

    def _execute_query(self, query: str, params: dict | None = None) -> list[dict]:
        with psycopg.connect(self.conninfo, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or {})
                return [dict(row) for row in cur.fetchall()]

    def get_hoofdprojecten(self, klantnummer: int) -> list[dict]:
        return self._execute_query(QUERY_HOOFDPROJECTEN)

    def get_deelprojecten(self, klantnummer: int, hoofdproject_key: int) -> list[dict]:
        return self._execute_query(
            QUERY_DEELPROJECTEN, {"hoofdproject_key": hoofdproject_key}
        )

    def get_bestekparagrafen(self, klantnummer: int, project_key: int, niveau: int) -> list[dict]:
        return self._execute_query(
            QUERY_BESTEKPARAGRAFEN, {"project_key": project_key, "niveau": niveau}
        )

    def get_projectdata(
        self,
        klantnummer: int,
        hoofdproject_key: int,
        start_boekdatum: date | None = None,
        einde_boekdatum: date | None = None,
    ) -> list[dict]:
        return self._execute_query(
            QUERY_PROJECTDATA, {"hoofdproject_key": hoofdproject_key}
        )


class MockDWHReader:
    """Mock DWH reader for development without VPN access."""

    def get_hoofdprojecten(self, klantnummer: int) -> list[dict]:
        return [
            {
                "project_key": 1001,
                "project_naam": "Nieuwbouw Kantoor A",
                "projectfase": "Uitvoering",
                "projectniveau": 1,
                "start_boekdatum": "2025-01-01",
                "einde_boekdatum": "2026-12-31",
            },
            {
                "project_key": 1002,
                "project_naam": "Renovatie Gebouw B",
                "projectfase": "Voorbereiding",
                "projectniveau": 1,
                "start_boekdatum": "2025-06-01",
                "einde_boekdatum": "2026-06-30",
            },
        ]

    def get_deelprojecten(self, klantnummer: int, hoofdproject_key: int) -> list[dict]:
        return [
            {
                "project_key": 2001,
                "project_naam": "Elektra installatie",
                "projectfase": "Uitvoering",
                "projectniveau": 2,
                "hoofdproject_key": hoofdproject_key,
            },
            {
                "project_key": 2002,
                "project_naam": "W-installatie",
                "projectfase": "Uitvoering",
                "projectniveau": 2,
                "hoofdproject_key": hoofdproject_key,
            },
        ]

    def get_bestekparagrafen(self, klantnummer: int, project_key: int, niveau: int) -> list[dict]:
        return [
            {"bestekparagraaf_key": 3001, "bestekparagraaf": "61 - Elektrische installatie", "bestekparagraafniveau": niveau},
            {"bestekparagraaf_key": 3002, "bestekparagraaf": "62 - Communicatie-installatie", "bestekparagraafniveau": niveau},
            {"bestekparagraaf_key": 3003, "bestekparagraaf": "63 - Transportinstallatie", "bestekparagraafniveau": niveau},
        ]

    def get_projectdata(
        self,
        klantnummer: int,
        hoofdproject_key: int,
        start_boekdatum: date | None = None,
        einde_boekdatum: date | None = None,
    ) -> list[dict]:
        base = {
            "project_key": hoofdproject_key,
            "project_naam": "Nieuwbouw Kantoor A",
            "projectniveau": 1,
            "projectfase": "Uitvoering",
        }
        return [
            {
                **base,
                "bestekparagraaf_key": 3001,
                "bestekparagraaf": "61 - Elektrische installatie",
                "bestekparagraafniveau": 1,
                "calculatie_kostprijs_inkoop": 50000,
                "calculatie_kostprijs_arbeid_montage": 30000,
                "calculatie_kostprijs_arbeid_projectgebonden": 15000,
                "calculatie_verrekenprijs_inkoop": 55000,
                "calculatie_verrekenprijs_arbeid_montage": 35000,
                "calculatie_verrekenprijs_arbeid_projectgebonden": 18000,
                "calculatie_montage_uren": 600,
                "calculatie_projectgebonden_uren": 200,
                "definitieve_kostprijs_inkoop": 25000,
                "definitieve_kostprijs_arbeid_montage": 12000,
                "definitieve_kostprijs_arbeid_projectgebonden": 8000,
                "definitieve_verrekenprijs_inkoop": 27500,
                "definitieve_verrekenprijs_arbeid_montage": 14000,
                "definitieve_verrekenprijs_arbeid_projectgebonden": 9500,
                "onverwerkte_verrekenprijs_inkoop": 2000,
                "onverwerkte_verrekenprijs_arbeid_montage": 1500,
                "onverwerkte_verrekenprijs_arbeid_projectgebonden": 500,
                "montage_uren_definitief": 250,
                "montage_uren_onverwerkt": 30,
                "projectgebonden_uren_definitief": 90,
                "projectgebonden_uren_onverwerkt": 10,
                "historische_verzoeken_inkoop": 5000,
                "historische_verzoeken_montage": 3000,
                "historische_verzoeken_projectgebonden": 1000,
                "historische_verzoeken_montage_uren": 50,
                "historische_verzoeken_projectgebonden_uren": 20,
            },
            {
                **base,
                "bestekparagraaf_key": 3002,
                "bestekparagraaf": "62 - Communicatie-installatie",
                "bestekparagraafniveau": 1,
                "calculatie_kostprijs_inkoop": 20000,
                "calculatie_kostprijs_arbeid_montage": 15000,
                "calculatie_kostprijs_arbeid_projectgebonden": 8000,
                "calculatie_verrekenprijs_inkoop": 22000,
                "calculatie_verrekenprijs_arbeid_montage": 17000,
                "calculatie_verrekenprijs_arbeid_projectgebonden": 9500,
                "calculatie_montage_uren": 300,
                "calculatie_projectgebonden_uren": 100,
                "definitieve_kostprijs_inkoop": 18000,
                "definitieve_kostprijs_arbeid_montage": 10000,
                "definitieve_kostprijs_arbeid_projectgebonden": 5000,
                "definitieve_verrekenprijs_inkoop": 19800,
                "definitieve_verrekenprijs_arbeid_montage": 11500,
                "definitieve_verrekenprijs_arbeid_projectgebonden": 6000,
                "onverwerkte_verrekenprijs_inkoop": 1000,
                "onverwerkte_verrekenprijs_arbeid_montage": 800,
                "onverwerkte_verrekenprijs_arbeid_projectgebonden": 300,
                "montage_uren_definitief": 200,
                "montage_uren_onverwerkt": 15,
                "projectgebonden_uren_definitief": 60,
                "projectgebonden_uren_onverwerkt": 5,
                "historische_verzoeken_inkoop": 2000,
                "historische_verzoeken_montage": 1500,
                "historische_verzoeken_projectgebonden": 500,
                "historische_verzoeken_montage_uren": 25,
                "historische_verzoeken_projectgebonden_uren": 10,
            },
        ]
