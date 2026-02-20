#!/usr/bin/env python3
"""Analyse werkbonnen voor batch export.

Toont:
1. Debiteuren met actieve contracten
2. Aantal werkbonnen per debiteur die voldoen aan criteria:
   - Status = Uitgevoerd
   - Documentstatus = Historisch
   - Type (paragraaf) = Storing
   - Gereedmelddatum in laatste 4 maanden
"""
import sys
from pathlib import Path
from datetime import date, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.models.database import SessionLocal


def main():
    db = SessionLocal()

    print("=" * 70)
    print("ANALYSE: Werkbonnen voor Pilot Batch Export")
    print("=" * 70)

    # 1. Haal debiteuren met actieve contracten op
    print("\n## 1. Debiteuren met actieve contracten\n")

    query_contracts = text("""
        SELECT
            cr.client_id as debiteur_code,
            cr.client_name as debiteur_naam,
            c.filename as contract_bestand
        FROM contract_checker.contract_relatie cr
        JOIN contract_checker.contracts c ON c.id = cr.contract_id
        WHERE c.active = true
        ORDER BY cr.client_id
    """)

    result = db.execute(query_contracts)
    debiteuren = []
    for row in result:
        debiteur_code, debiteur_naam, contract_bestand = row
        debiteuren.append({
            "code": debiteur_code,
            "naam": debiteur_naam,
            "contract": contract_bestand
        })
        print(f"  {debiteur_code} - {debiteur_naam}")
        print(f"    Contract: {contract_bestand}")

    print(f"\n  Totaal: {len(debiteuren)} debiteuren met contract")

    if not debiteuren:
        print("\nGeen debiteuren met contracten gevonden!")
        db.close()
        return

    # 2. Bepaal datum range (laatste 4 maanden)
    end_date = date.today()
    start_date = end_date - timedelta(days=120)  # ~4 maanden

    print(f"\n## 2. Datum range voor Gereedmelddatum\n")
    print(f"  Van: {start_date}")
    print(f"  Tot: {end_date}")

    # 3. Analyseer werkbonnen per debiteur
    print(f"\n## 3. Werkbonnen analyse per debiteur\n")
    print("  Criteria:")
    print("  - Status = 'Uitgevoerd'")
    print("  - Documentstatus = 'Historisch'")
    print("  - Paragraaf Type = 'Storing'")
    print(f"  - Gereedmelddatum >= {start_date}")
    print()

    totaal_werkbonnen = 0

    for deb in debiteuren:
        # Query werkbonnen count per debiteur
        query_count = text("""
            SELECT COUNT(DISTINCT w."HoofdwerkbonDocumentKey")
            FROM werkbonnen."Werkbonnen" w
            INNER JOIN werkbonnen."Werkbonparagrafen" wp
                ON w."WerkbonDocumentKey" = wp."WerkbonDocumentKey"
            INNER JOIN stam."Documenten" d
                ON d."DocumentKey" = w."WerkbonDocumentKey"
            WHERE w."Debiteur" LIKE :debiteur_pattern
              AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
              AND TRIM(w."Status") = 'Uitgevoerd'
              AND TRIM(w."Documentstatus") = 'Historisch'
              AND TRIM(wp."Type") = 'Storing'
              AND d."Gereedmelddatum"::date >= :start_date
              AND d."Gereedmelddatum"::date <= :end_date
        """)

        result = db.execute(query_count, {
            "debiteur_pattern": f"{deb['code']} - %",
            "start_date": start_date,
            "end_date": end_date
        })
        count = result.scalar() or 0
        totaal_werkbonnen += count

        print(f"  {deb['code']} - {deb['naam']}: {count} werkbonnen")

    print(f"\n  {'=' * 50}")
    print(f"  TOTAAL: {totaal_werkbonnen} werkbonnen")

    # 4. Extra info: verdeling over maanden
    print(f"\n## 4. Verdeling over maanden (alle debiteuren)\n")

    # Build debiteur filter
    debiteur_patterns = [f"w.\"Debiteur\" LIKE '{d['code']} - %'" for d in debiteuren]
    debiteur_filter = " OR ".join(debiteur_patterns)

    query_months = text(f"""
        SELECT
            DATE_TRUNC('month', d."Gereedmelddatum")::date as maand,
            COUNT(DISTINCT w."HoofdwerkbonDocumentKey") as aantal
        FROM werkbonnen."Werkbonnen" w
        INNER JOIN werkbonnen."Werkbonparagrafen" wp
            ON w."WerkbonDocumentKey" = wp."WerkbonDocumentKey"
        INNER JOIN stam."Documenten" d
            ON d."DocumentKey" = w."WerkbonDocumentKey"
        WHERE ({debiteur_filter})
          AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
          AND TRIM(w."Status") = 'Uitgevoerd'
          AND TRIM(w."Documentstatus") = 'Historisch'
          AND TRIM(wp."Type") = 'Storing'
          AND d."Gereedmelddatum"::date >= :start_date
          AND d."Gereedmelddatum"::date <= :end_date
        GROUP BY DATE_TRUNC('month', d."Gereedmelddatum")
        ORDER BY maand DESC
    """)

    result = db.execute(query_months, {
        "start_date": start_date,
        "end_date": end_date
    })

    for row in result:
        maand, aantal = row
        print(f"  {maand}: {aantal} werkbonnen")

    # 5. Check of 500 haalbaar is
    print(f"\n## 5. Conclusie\n")
    if totaal_werkbonnen >= 500:
        print(f"  ✓ Er zijn {totaal_werkbonnen} werkbonnen beschikbaar.")
        print(f"    Een batch van 500 is haalbaar.")
    else:
        print(f"  ⚠ Er zijn slechts {totaal_werkbonnen} werkbonnen beschikbaar.")
        print(f"    Overweeg de datum range te vergroten.")

    db.close()


if __name__ == "__main__":
    main()
