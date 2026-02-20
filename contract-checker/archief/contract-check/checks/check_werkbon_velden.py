"""Check available columns on werkbon tables for verhaal enrichment."""
import sys
import os

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from src.models.database import SessionLocal

db = SessionLocal()

tables = [
    ("werkbonnen", "Werkbonnen"),
    ("werkbonnen", "Werkbonparagrafen"),
    ("werkbonnen", "Werkbon opvolgingen"),
    ("werkbonnen", "Werkbon oplossingen"),
]

for schema, table in tables:
    print("=" * 100)
    print(f"TABEL: {schema}.\"{table}\"")
    print("=" * 100)
    result = db.execute(text(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = '{schema}'
          AND table_name = '{table}'
        ORDER BY ordinal_position
    """))
    for row in result:
        # Highlight date/time columns and status-like columns
        col_name = row[0]
        data_type = row[1]
        marker = ""
        if "datum" in col_name.lower() or "date" in col_name.lower() or "time" in data_type:
            marker = " ← DATETIME"
        elif "status" in col_name.lower() or "fase" in col_name.lower():
            marker = " ← STATUS"
        elif "oorzaak" in col_name.lower() or "storing" in col_name.lower() or "oplossing" in col_name.lower():
            marker = " ← CODE/OMSCHRIJVING"
        print(f"  {col_name:<40} {data_type:<30}{marker}")
    print()

db.close()
