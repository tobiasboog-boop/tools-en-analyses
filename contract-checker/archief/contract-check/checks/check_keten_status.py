"""Check how status/documentstatus relates between hoofdwerkbon and vervolgbonnen."""
import sys
import os

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from src.models.database import SessionLocal

db = SessionLocal()

# Vraag 1: Kunnen hoofd en vervolg verschillende documentstatus hebben?
print("=" * 100)
print("VRAAG 1: Hebben hoofd- en vervolgbonnen altijd dezelfde Documentstatus?")
print("=" * 100)
result = db.execute(text("""
    SELECT
        TRIM(h."Documentstatus") as hoofd_docstatus,
        TRIM(v."Documentstatus") as vervolg_docstatus,
        COUNT(*) as aantal_ketens
    FROM werkbonnen."Werkbonnen" h
    JOIN werkbonnen."Werkbonnen" v
        ON v."HoofdwerkbonDocumentKey" = h."WerkbonDocumentKey"
        AND v."WerkbonDocumentKey" != h."WerkbonDocumentKey"  -- alleen vervolgbonnen
    WHERE h."HoofdwerkbonDocumentKey" = h."WerkbonDocumentKey"  -- alleen hoofdwerkbonnen
    GROUP BY TRIM(h."Documentstatus"), TRIM(v."Documentstatus")
    ORDER BY aantal_ketens DESC
"""))
print(f"{'Hoofd DocStatus':<20} | {'Vervolg DocStatus':<20} | {'Aantal':>10}")
print("-" * 60)
for row in result:
    print(f"{row[0]:<20} | {row[1]:<20} | {row[2]:>10,}")

# Vraag 2: Kunnen hoofd en vervolg verschillende Status hebben?
print("\n" + "=" * 100)
print("VRAAG 2: Hebben hoofd- en vervolgbonnen altijd dezelfde Status?")
print("=" * 100)
result = db.execute(text("""
    SELECT
        TRIM(h."Status") as hoofd_status,
        TRIM(v."Status") as vervolg_status,
        COUNT(*) as aantal_ketens
    FROM werkbonnen."Werkbonnen" h
    JOIN werkbonnen."Werkbonnen" v
        ON v."HoofdwerkbonDocumentKey" = h."WerkbonDocumentKey"
        AND v."WerkbonDocumentKey" != h."WerkbonDocumentKey"
    WHERE h."HoofdwerkbonDocumentKey" = h."WerkbonDocumentKey"
    GROUP BY TRIM(h."Status"), TRIM(v."Status")
    ORDER BY aantal_ketens DESC
"""))
print(f"{'Hoofd Status':<20} | {'Vervolg Status':<20} | {'Aantal':>10}")
print("-" * 60)
for row in result:
    print(f"{row[0]:<20} | {row[1]:<20} | {row[2]:>10,}")

# Vraag 3: Hoeveel ketens hebben gemixte statussen?
print("\n" + "=" * 100)
print("VRAAG 3: Ketens waar NIET alle bonnen dezelfde Documentstatus hebben")
print("=" * 100)
result = db.execute(text("""
    WITH keten_status AS (
        SELECT
            "HoofdwerkbonDocumentKey",
            COUNT(DISTINCT TRIM("Documentstatus")) as aantal_statussen,
            STRING_AGG(DISTINCT TRIM("Documentstatus"), ', ') as statussen
        FROM werkbonnen."Werkbonnen"
        GROUP BY "HoofdwerkbonDocumentKey"
        HAVING COUNT(DISTINCT TRIM("Documentstatus")) > 1
    )
    SELECT statussen, COUNT(*) as aantal_ketens
    FROM keten_status
    GROUP BY statussen
    ORDER BY aantal_ketens DESC
"""))
total_mixed = 0
print(f"{'Gemixte statussen':<40} | {'Aantal ketens':>15}")
print("-" * 60)
for row in result:
    print(f"{row[0]:<40} | {row[1]:>15,}")
    total_mixed += row[1]
print(f"\nTotaal ketens met gemixte Documentstatus: {total_mixed:,}")

# Vraag 4: Voorbeeld van gemixte keten
print("\n" + "=" * 100)
print("VOORBEELD: Een keten met gemixte Documentstatus")
print("=" * 100)
result = db.execute(text("""
    WITH keten_status AS (
        SELECT "HoofdwerkbonDocumentKey"
        FROM werkbonnen."Werkbonnen"
        GROUP BY "HoofdwerkbonDocumentKey"
        HAVING COUNT(DISTINCT TRIM("Documentstatus")) > 1
        LIMIT 1
    )
    SELECT
        w."Werkbon",
        w."Niveau",
        CASE WHEN w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey" THEN 'HOOFD' ELSE 'VERVOLG' END as type,
        TRIM(w."Status") as status,
        TRIM(w."Documentstatus") as docstatus,
        TRIM(w."Administratieve fase") as admin_fase,
        w."MeldDatum"::date as melddatum
    FROM werkbonnen."Werkbonnen" w
    WHERE w."HoofdwerkbonDocumentKey" IN (SELECT "HoofdwerkbonDocumentKey" FROM keten_status)
    ORDER BY w."Niveau", w."MeldDatum"
"""))
print(f"{'Werkbon':<30} | {'Niv':>3} | {'Type':<7} | {'Status':<15} | {'DocStatus':<12} | {'Admin Fase':<30}")
print("-" * 120)
for row in result:
    print(f"{str(row[0])[:30]:<30} | {row[1]:>3} | {row[2]:<7} | {row[3]:<15} | {row[4]:<12} | {str(row[5] or '')[:30]:<30}")

db.close()
