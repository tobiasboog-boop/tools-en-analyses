"""Check workflow status combinations to find 'ready for classification' werkbonnen."""
import sys
import os

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from src.models.database import SessionLocal

db = SessionLocal()

# Query: alle combinaties van Status + Documentstatus
print("=" * 100)
print("ALLE STATUS + DOCUMENTSTATUS COMBINATIES")
print("=" * 100)
result = db.execute(text("""
    SELECT
        TRIM("Status") as status,
        TRIM("Documentstatus") as doc_status,
        COUNT(*) as cnt
    FROM werkbonnen."Werkbonnen"
    GROUP BY TRIM("Status"), TRIM("Documentstatus")
    ORDER BY cnt DESC
"""))

print(f"{'Status':<20} | {'Documentstatus':<15} | {'Aantal':>12}")
print("-" * 60)
for row in result:
    print(f"{row[0]:<20} | {row[1]:<15} | {row[2]:>12,}")

# Focus op niet-Historisch maar wel Uitgevoerd
print("\n" + "=" * 100)
print("FOCUS: Uitgevoerd maar NIET Historisch (mogelijk 'klaar voor beoordeling')")
print("=" * 100)
result = db.execute(text("""
    SELECT
        TRIM("Status") as status,
        TRIM("Documentstatus") as doc_status,
        COALESCE(TRIM("Administratieve fase"), '(leeg)') as admin_fase,
        COUNT(*) as cnt
    FROM werkbonnen."Werkbonnen"
    WHERE TRIM("Status") = 'Uitgevoerd'
      AND TRIM("Documentstatus") != 'Historisch'
    GROUP BY TRIM("Status"), TRIM("Documentstatus"), TRIM("Administratieve fase")
    ORDER BY cnt DESC
"""))

print(f"{'Status':<15} | {'DocStatus':<12} | {'Admin Fase':<45} | {'Aantal':>10}")
print("-" * 100)
for row in result:
    print(f"{row[0]:<15} | {row[1]:<12} | {row[2]:<45} | {row[3]:>10,}")

# Kijk naar "Gereed" documentstatus specifiek
print("\n" + "=" * 100)
print("DOCUMENTSTATUS = 'Gereed' (mogelijk de 'klaar voor facturatie' status?)")
print("=" * 100)
result = db.execute(text("""
    SELECT
        TRIM("Status") as status,
        COALESCE(TRIM("Administratieve fase"), '(leeg)') as admin_fase,
        COUNT(*) as cnt
    FROM werkbonnen."Werkbonnen"
    WHERE TRIM("Documentstatus") = 'Gereed'
    GROUP BY TRIM("Status"), TRIM("Administratieve fase")
    ORDER BY cnt DESC
"""))

print(f"{'Status':<20} | {'Admin Fase':<45} | {'Aantal':>10}")
print("-" * 85)
for row in result:
    print(f"{row[0]:<20} | {row[1]:<45} | {row[2]:>10,}")

# Kijk naar "Openstaand" documentstatus
print("\n" + "=" * 100)
print("DOCUMENTSTATUS = 'Openstaand' + Status = 'Uitgevoerd'")
print("(werk gedaan, nog niet gearchiveerd - mogelijk nog in facturatie proces)")
print("=" * 100)
result = db.execute(text("""
    SELECT
        COALESCE(TRIM("Administratieve fase"), '(leeg)') as admin_fase,
        COUNT(*) as cnt
    FROM werkbonnen."Werkbonnen"
    WHERE TRIM("Documentstatus") = 'Openstaand'
      AND TRIM("Status") = 'Uitgevoerd'
    GROUP BY TRIM("Administratieve fase")
    ORDER BY cnt DESC
"""))

print(f"{'Admin Fase':<50} | {'Aantal':>10}")
print("-" * 65)
for row in result:
    print(f"{row[0]:<50} | {row[1]:>10,}")

db.close()
