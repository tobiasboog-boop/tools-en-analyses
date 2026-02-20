"""Check werkbon opvolgingen to understand workflow status."""
import sys
import os

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from src.models.database import SessionLocal

db = SessionLocal()

# Opvolgsoorten
print("=" * 100)
print("OPVOLGSOORTEN: Wat voor soorten opvolgingen zijn er?")
print("=" * 100)
result = db.execute(text("""
    SELECT
        "Opvolgsoort code",
        "Opvolgsoort",
        "Status",
        COUNT(*) as cnt
    FROM werkbonnen."Werkbon opvolgingen"
    GROUP BY "Opvolgsoort code", "Opvolgsoort", "Status"
    ORDER BY cnt DESC
"""))
print(f"{'Code':<10} | {'Opvolgsoort':<40} | {'Status':<15} | {'Aantal':>10}")
print("-" * 85)
for row in result:
    print(f"{str(row[0] or ''):<10} | {str(row[1] or ''):<40} | {str(row[2] or ''):<15} | {row[3]:>10,}")

# Opvolgingen met status (open/afgehandeld?)
print("\n" + "=" * 100)
print("OPVOLGING STATUS: Zijn er open vs afgehandelde opvolgingen?")
print("=" * 100)
result = db.execute(text("""
    SELECT
        COALESCE(TRIM("Status"), '(leeg)') as status,
        COUNT(*) as cnt
    FROM werkbonnen."Werkbon opvolgingen"
    GROUP BY TRIM("Status")
    ORDER BY cnt DESC
"""))
for row in result:
    print(f"  {row[0]}: {row[1]:,}")

# Sample beschrijvingen
print("\n" + "=" * 100)
print("SAMPLE: Beschrijvingen van opvolgingen")
print("=" * 100)
result = db.execute(text("""
    SELECT DISTINCT "Beschrijving"
    FROM werkbonnen."Werkbon opvolgingen"
    WHERE "Beschrijving" IS NOT NULL AND "Beschrijving" != ''
    LIMIT 20
"""))
for row in result:
    print(f"  - {row[0][:100] if row[0] else ''}")

# Hoeveel werkbonnen (Uitgevoerd+Openstaand) hebben opvolgingen?
print("\n" + "=" * 100)
print("FOCUS: Werkbonnen met Status=Uitgevoerd, Documentstatus=Openstaand")
print("Hebben deze opvolgingen?")
print("=" * 100)
result = db.execute(text("""
    SELECT
        CASE
            WHEN EXISTS (
                SELECT 1 FROM werkbonnen."Werkbon opvolgingen" op
                JOIN werkbonnen."Werkbonparagrafen" wp2 ON op."WerkbonparagraafKey" = wp2."WerkbonparagraafKey"
                WHERE wp2."WerkbonDocumentKey" = w."WerkbonDocumentKey"
            ) THEN 'Met opvolging'
            ELSE 'Zonder opvolging'
        END as heeft_opvolging,
        COUNT(*) as cnt
    FROM werkbonnen."Werkbonnen" w
    WHERE TRIM(w."Status") = 'Uitgevoerd'
      AND TRIM(w."Documentstatus") = 'Openstaand'
    GROUP BY 1
"""))
for row in result:
    print(f"  {row[0]}: {row[1]:,}")

# Bij welke opvolgsoort staan ze?
print("\n" + "=" * 100)
print("OPVOLGSOORTEN bij Uitgevoerd+Openstaand werkbonnen")
print("=" * 100)
result = db.execute(text("""
    SELECT
        op."Opvolgsoort",
        op."Status" as opvolg_status,
        COUNT(*) as cnt
    FROM werkbonnen."Werkbonnen" w
    JOIN werkbonnen."Werkbonparagrafen" wp ON w."WerkbonDocumentKey" = wp."WerkbonDocumentKey"
    JOIN werkbonnen."Werkbon opvolgingen" op ON wp."WerkbonparagraafKey" = op."WerkbonparagraafKey"
    WHERE TRIM(w."Status") = 'Uitgevoerd'
      AND TRIM(w."Documentstatus") = 'Openstaand'
    GROUP BY op."Opvolgsoort", op."Status"
    ORDER BY cnt DESC
"""))
print(f"{'Opvolgsoort':<50} | {'Status':<15} | {'Aantal':>10}")
print("-" * 80)
for row in result:
    print(f"{str(row[0] or ''):<50} | {str(row[1] or ''):<15} | {row[2]:>10,}")

db.close()
