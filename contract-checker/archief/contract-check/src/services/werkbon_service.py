from datetime import date, datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from src.models.database import SessionLocal
from src.config import config


class WerkbonService:
    """Service to fetch werkbonnen from the datawarehouse."""

    def __init__(self):
        self.db = SessionLocal()

    def get_werkbonnen(
        self,
        start_date: date,
        end_date: date,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Fetch werkbonnen from datawarehouse for given date range.

        Note: This query needs to be adapted to match WVC's actual schema.
        """
        query = text("""
            SELECT
                werkbon_id,
                datum,
                klant_naam,
                adres,
                omschrijving,
                uitgevoerde_werkzaamheden,
                materialen,
                monteur,
                bedrag,
                contract_type
            FROM werkbonnen
            WHERE datum BETWEEN :start_date AND :end_date
            ORDER BY datum DESC
            LIMIT :limit OFFSET :offset
        """)

        try:
            result = self.db.execute(
                query,
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "limit": limit,
                    "offset": offset,
                }
            )
            rows = result.fetchall()
            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"Error fetching werkbonnen: {e}")
            return []

    def get_werkbon_count(self, start_date: date, end_date: date) -> int:
        """Get total count of werkbonnen in date range."""
        query = text("""
            SELECT COUNT(*)
            FROM werkbonnen
            WHERE datum BETWEEN :start_date AND :end_date
        """)

        try:
            result = self.db.execute(
                query, {"start_date": start_date, "end_date": end_date}
            )
            return result.scalar() or 0
        except Exception as e:
            print(f"Error counting werkbonnen: {e}")
            return 0

    def get_werkbon_by_id(self, werkbon_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single werkbon by ID."""
        query = text("""
            SELECT
                werkbon_id,
                datum,
                klant_naam,
                adres,
                omschrijving,
                uitgevoerde_werkzaamheden,
                materialen,
                monteur,
                bedrag,
                contract_type
            FROM werkbonnen
            WHERE werkbon_id = :werkbon_id
        """)

        try:
            result = self.db.execute(query, {"werkbon_id": werkbon_id})
            row = result.fetchone()
            if row:
                columns = result.keys()
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"Error fetching werkbon {werkbon_id}: {e}")
            return None

    def close(self):
        """Close database connection."""
        self.db.close()
