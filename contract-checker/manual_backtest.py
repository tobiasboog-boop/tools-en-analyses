#!/usr/bin/env python3
"""
Manual backtest - ik voer zelf de classificaties uit via Claude API
Geen externe dependencies nodig.
"""
import json
from pathlib import Path

# Load sample werkbonnen
json_path = Path("OUD denk ik/contract-check-public/data/werkbonnen_005102_Trivire.json")
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

werkbonnen = data.get('werkbonnen', [])
print(f"Geladen: {len(werkbonnen)} Trivire werkbonnen")

# Select first 3 for manual testing
sample = werkbonnen[:3]

print("\n=== SAMPLE WERKBONNEN VOOR MANUAL BACKTEST ===\n")

for i, wb in enumerate(sample, 1):
    print(f"\n--- Werkbon {i}: {wb.get('werkbon_key')} ---")
    print(f"Klant: {wb.get('debiteur_naam', 'N/A')}")
    print(f"Datum: {wb.get('datum', 'N/A')}")
    print(f"Totaal: €{wb.get('totaal_kosten', 0):.2f}")

    # Show oplossingen
    oplossingen = wb.get('oplossingen', [])
    if oplossingen:
        print(f"\n🔍 OPLOSSINGEN ({len(oplossingen)} stuks):")
        for opl in oplossingen:
            print(f"  - {opl.get('oplossing', 'N/A')}")
            if opl.get('oplossing_uitgebreid'):
                print(f"    Detail: {opl['oplossing_uitgebreid']}")

    # Show kosten
    kosten = wb.get('kosten', [])
    if kosten:
        print(f"\nKOSTENREGELS ({len(kosten)} stuks):")
        for k in kosten[:3]:  # First 3
            print(f"  - {k.get('omschrijving', 'N/A')}: €{k.get('bedrag', 0):.2f}")
        if len(kosten) > 3:
            print(f"  ... en {len(kosten)-3} meer")

    print(f"\n" + "="*70)

print("\n✅ Sample data geladen. Nu kan Claude deze classificeren met V1 en V2.")
