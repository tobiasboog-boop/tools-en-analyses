"""Analyze factureerstatus patterns for training vs classification data."""
import sys
sys.path.insert(0, ".")
from src.models.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print("=" * 60)
print("ANALYSE: Factureerstatus per Document status")
print("=" * 60)

# Use the kosten table's own Document status field
result = db.execute(text('''
    SELECT
        k."Document status",
        k."Factureerstatus",
        COUNT(*) as aantal,
        ROUND(SUM(k."Regelbedrag")::numeric, 0) as totaal
    FROM financieel."Kosten" k
    WHERE k."WerkbonparagraafKey" IS NOT NULL
    GROUP BY k."Document status", k."Factureerstatus"
    ORDER BY k."Document status", aantal DESC
'''))

current_status = None
status_totals = {}
for row in result:
    doc_status = row[0]
    fact_status = row[1]
    aantal = row[2]
    totaal = row[3]

    if doc_status not in status_totals:
        status_totals[doc_status] = {"regels": 0, "bedrag": 0}
    status_totals[doc_status]["regels"] += aantal or 0
    status_totals[doc_status]["bedrag"] += totaal or 0

    if doc_status != current_status:
        current_status = doc_status
        print(f"\n=== {current_status} ===")
    print(f"  {fact_status}: {aantal:,} regels | EUR {totaal or 0:,.0f}")

print("\n" + "=" * 60)
print("SAMENVATTING per Document status:")
print("=" * 60)
for status, totals in status_totals.items():
    print(f"{status}: {totals['regels']:,} regels | EUR {totals['bedrag']:,}")

# Now link to werkbon status
print("\n" + "=" * 60)
print("WERKBON niveau analyse (Status + Documentstatus)")
print("=" * 60)

result = db.execute(text('''
    SELECT
        TRIM(w."Status") as werkbon_status,
        TRIM(w."Documentstatus") as werkbon_docstatus,
        k."Factureerstatus",
        COUNT(*) as aantal,
        ROUND(SUM(k."Regelbedrag")::numeric, 0) as totaal
    FROM financieel."Kosten" k
    JOIN werkbonnen."Werkbonnen" w ON k."WerkbonKey" = w."WerkbonDocumentKey"
    GROUP BY TRIM(w."Status"), TRIM(w."Documentstatus"), k."Factureerstatus"
    ORDER BY TRIM(w."Status"), TRIM(w."Documentstatus"), aantal DESC
'''))

current_combo = None
for row in result:
    combo = f"{row[0]} | {row[1]}"
    if combo != current_combo:
        current_combo = combo
        print(f"\n=== {combo} ===")
    print(f"  {row[2]}: {row[3]:,} regels | EUR {row[4] or 0:,.0f}")

db.close()
