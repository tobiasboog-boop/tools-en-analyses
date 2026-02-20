"""Check how hoofdwerkbon is identified in the data."""
import sys
import os

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from src.models.database import SessionLocal

db = SessionLocal()

# Bekijk een voorbeeld keten met alle identificerende velden
print("=" * 120)
print("VOORBEELD: Keten met hoofdwerkbon en vervolgbonnen - alle ID velden")
print("=" * 120)
result = db.execute(text("""
    SELECT
        w."WerkbonDocumentKey" as eigen_key,
        w."HoofdwerkbonDocumentKey" as hoofdwerkbon_key,
        w."ParentWerkbonDocumentKey" as parent_key,
        w."Niveau" as niveau,
        CASE
            WHEN w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey" THEN '>>> HOOFD <<<'
            ELSE 'Vervolg'
        END as type,
        w."Werkbon" as werkbon_titel,
        w."Hoofdwerkbon" as hoofdwerkbon_veld,
        TRIM(w."Status") as status,
        w."MeldDatum"::date as melddatum
    FROM werkbonnen."Werkbonnen" w
    WHERE w."HoofdwerkbonDocumentKey" IN (
        SELECT "HoofdwerkbonDocumentKey"
        FROM werkbonnen."Werkbonnen"
        GROUP BY "HoofdwerkbonDocumentKey"
        HAVING COUNT(*) >= 3  -- ketens met minstens 3 bonnen
        LIMIT 1
    )
    ORDER BY w."Niveau", w."MeldDatum"
"""))

print(f"{'Eigen Key':>12} | {'Hoofd Key':>12} | {'Parent Key':>12} | {'Niv':>3} | {'Type':<15} | {'Werkbon Titel':<40} | {'Hoofdwerkbon veld':<40}")
print("-" * 160)
for row in result:
    print(f"{row[0]:>12} | {row[1]:>12} | {str(row[2] or ''):>12} | {row[3]:>3} | {row[4]:<15} | {str(row[5])[:40]:<40} | {str(row[6] or '')[:40]:<40}")

# Check: is er een "Hoofdwerkbon" kolom die verwijst naar de titel?
print("\n" + "=" * 120)
print("KOLOM 'Hoofdwerkbon': Wat staat hier in bij vervolgbonnen?")
print("=" * 120)
result = db.execute(text("""
    SELECT
        CASE
            WHEN w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey" THEN 'Hoofdwerkbon'
            ELSE 'Vervolgbon'
        END as type,
        w."Werkbon" as eigen_titel,
        w."Hoofdwerkbon" as hoofdwerkbon_kolom,
        CASE
            WHEN w."Werkbon" = w."Hoofdwerkbon" THEN 'ZELFDE'
            ELSE 'ANDERS'
        END as vergelijking
    FROM werkbonnen."Werkbonnen" w
    WHERE w."HoofdwerkbonDocumentKey" IN (
        SELECT "HoofdwerkbonDocumentKey"
        FROM werkbonnen."Werkbonnen"
        GROUP BY "HoofdwerkbonDocumentKey"
        HAVING COUNT(*) >= 2
        LIMIT 3
    )
    ORDER BY w."HoofdwerkbonDocumentKey", w."Niveau"
"""))

print(f"{'Type':<12} | {'Eigen Titel':<45} | {'Hoofdwerkbon kolom':<45} | {'Match':<8}")
print("-" * 120)
for row in result:
    print(f"{row[0]:<12} | {str(row[1])[:45]:<45} | {str(row[2] or '')[:45]:<45} | {row[3]:<8}")

# Check de Niveau waarde
print("\n" + "=" * 120)
print("NIVEAU: Welke waarden komen voor?")
print("=" * 120)
result = db.execute(text("""
    SELECT
        "Niveau",
        CASE
            WHEN "HoofdwerkbonDocumentKey" = "WerkbonDocumentKey" THEN 'Hoofdwerkbon'
            ELSE 'Vervolgbon'
        END as type,
        COUNT(*) as aantal
    FROM werkbonnen."Werkbonnen"
    GROUP BY "Niveau",
        CASE WHEN "HoofdwerkbonDocumentKey" = "WerkbonDocumentKey" THEN 'Hoofdwerkbon' ELSE 'Vervolgbon' END
    ORDER BY "Niveau", type
"""))

print(f"{'Niveau':>8} | {'Type':<15} | {'Aantal':>12}")
print("-" * 45)
for row in result:
    print(f"{row[0]:>8} | {row[1]:<15} | {row[2]:>12,}")

db.close()
