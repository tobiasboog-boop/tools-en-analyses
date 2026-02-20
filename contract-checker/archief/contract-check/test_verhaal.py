"""Test script to view werkbon keten verhaal output."""
import sys
import os
import json
from datetime import date, timedelta

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from src.models.database import SessionLocal
from src.services.werkbon_keten_service import (
    WerkbonKetenService,
    WerkbonVerhaalBuilder
)

# De 3 debiteuren uit contract_relatie
DEBITEUREN = {
    "1": ("007453", "Stichting Bazalt Wonen"),
    "2": ("177460", "Stichting Thuisvester (Oosterhout)"),
    "3": ("005102", "Trivire"),
}

def main():
    print("=" * 80)
    print("WERKBON KETEN VERHAAL TEST")
    print("=" * 80)

    # Select debiteur
    print("\nSelecteer debiteur:")
    for key, (code, name) in DEBITEUREN.items():
        print(f"  {key}. {code} - {name}")

    choice = input("\nKeuze (1/2/3): ").strip()
    if choice not in DEBITEUREN:
        print("Ongeldige keuze")
        return

    client_code, client_name = DEBITEUREN[choice]
    print(f"\nGeselecteerd: {client_code} - {client_name}")

    # Select period
    print("\nSelecteer periode:")
    print("  1. Laatste week")
    print("  2. Laatste maand")
    print("  3. Laatste 3 maanden")
    print("  4. Custom (YYYY-MM-DD)")

    period_choice = input("\nKeuze (1/2/3/4): ").strip()

    today = date.today()
    if period_choice == "1":
        start_date = today - timedelta(days=7)
        end_date = today
    elif period_choice == "2":
        start_date = today - timedelta(days=30)
        end_date = today
    elif period_choice == "3":
        start_date = today - timedelta(days=90)
        end_date = today
    elif period_choice == "4":
        start_str = input("Start datum (YYYY-MM-DD): ").strip()
        end_str = input("Eind datum (YYYY-MM-DD): ").strip()
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    else:
        print("Ongeldige keuze, gebruik laatste maand")
        start_date = today - timedelta(days=30)
        end_date = today

    print(f"\nPeriode: {start_date} tot {end_date}")

    # Find werkbonnen
    db = SessionLocal()
    query = text("""
        SELECT DISTINCT
            w."HoofdwerkbonDocumentKey" as hoofdwerkbon_key,
            w."Werkbon" as werkbon,
            w."MeldDatum"::date as melddatum,
            w."Status" as status
        FROM werkbonnen."Werkbonnen" w
        WHERE w."Debiteur" LIKE :debiteur_pattern
          AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
          AND w."MeldDatum" >= :start_date
          AND w."MeldDatum" <= :end_date
        ORDER BY w."MeldDatum" DESC
        LIMIT 20
    """)

    result = db.execute(query, {
        "debiteur_pattern": f"{client_code} - %",
        "start_date": start_date,
        "end_date": end_date
    })
    werkbonnen = result.fetchall()
    db.close()

    if not werkbonnen:
        print(f"\nGeen werkbonnen gevonden voor {client_name} in deze periode")
        return

    print(f"\nGevonden: {len(werkbonnen)} hoofdwerkbonnen")
    print("-" * 60)
    for i, wb in enumerate(werkbonnen, 1):
        print(f"  {i}. [{wb[2]}] {wb[1][:50]}...")

    # Select werkbon
    wb_choice = input("\nSelecteer werkbon nummer (of 'all' voor alle): ").strip()

    service = WerkbonKetenService()
    builder = WerkbonVerhaalBuilder()

    if wb_choice.lower() == "all":
        selected = werkbonnen[:5]  # Max 5
    else:
        idx = int(wb_choice) - 1
        if 0 <= idx < len(werkbonnen):
            selected = [werkbonnen[idx]]
        else:
            print("Ongeldige keuze")
            return

    for wb in selected:
        print("\n" + "=" * 80)
        print(f"WERKBON: {wb[1]}")
        print("=" * 80)

        keten = service.get_werkbon_keten(wb[0])
        if not keten:
            print("Kon keten niet laden")
            continue

        # Show verhaal
        print("\n--- VERHAAL (voor LLM) ---\n")
        verhaal = builder.build_verhaal(keten)
        print(verhaal)

        # Show JSON summary
        print("\n--- JSON SUMMARY ---\n")
        summary = builder.build_json_summary(keten)
        print(json.dumps(summary, indent=2, ensure_ascii=False))

        # Ask to continue
        if len(selected) > 1:
            cont = input("\nVolgende? (Enter/n): ").strip().lower()
            if cont == 'n':
                break

    service.close()
    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)


if __name__ == "__main__":
    main()
