#!/usr/bin/env python3
"""
Backtest V1 vs V2 op Gerrit's Trivire data
Run beide versies en vergelijk met Gerrit's handmatige labels.
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import anthropic
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.parquet_data_service import ParquetDataService, WerkbonVerhaalBuilder
from app_v2 import VerbeterdeVerhaalBuilder


class GerritBacktest:
    """Backtest specifically for Gerrit's feedback data."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.data_service = ParquetDataService(data_dir="data")
        self.contracts = self._load_contracts()

        # Builders
        self.v1_builder = WerkbonVerhaalBuilder()
        self.v2_builder = VerbeterdeVerhaalBuilder()

        # Anthropic client
        self.client = anthropic.Anthropic(api_key=api_key)

        # Load Gerrit's ground truth
        self.ground_truth = self._load_gerrit_data()

    def _load_contracts(self):
        """Load contracts."""
        contracts_dir = Path("contracts")
        contracts = {}

        meta_path = contracts_dir / "contracts_metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            for c in meta.get("contracts", []):
                contract_file = contracts_dir / c["filename"]
                if contract_file.exists():
                    content = contract_file.read_text(encoding="utf-8")
                    contracts[c["id"]] = {
                        "id": c["id"],
                        "filename": c["filename"],
                        "content": content,
                        "clients": c.get("clients", [])
                    }

        return contracts

    def _load_gerrit_data(self):
        """Load Gerrit's steekproef data."""
        excel_path = Path("C:/projects/contract-check-public/feedback Gerrit/Steekproef bonnen Trivire.xlsx")

        df = pd.read_excel(excel_path, sheet_name='classificatie_geschiedenis')
        df = df[df['werkbon_key'].notna()].copy()

        print(f"✅ Geladen: {len(df)} werkbonnen uit Gerrit's steekproef")
        print(f"   - Goed: {len(df[df['eind'] == 'goed'])}")
        print(f"   - Fout: {len(df[df['eind'] == 'fout'])}")

        return df

    def _get_contract_for_debiteur(self, debiteur_code: str):
        """Get contract for debiteur."""
        code = debiteur_code.split(" - ")[0].strip() if " - " in debiteur_code else debiteur_code

        for contract in self.contracts.values():
            if code in contract.get("clients", []):
                return contract
        return None

    def classify_werkbon(self, werkbon_key: int, contract_text: str, version: str) -> dict:
        """Classify with V1 or V2."""
        keten = self.data_service.get_werkbon_keten(
            werkbon_key,
            include_kosten_details=True,
            include_oplossingen=True,
            include_opvolgingen=True
        )

        if not keten:
            return {
                "error": "Werkbon niet gevonden",
                "werkbon_key": werkbon_key,
                "version": version
            }

        # Choose builder and prompt
        if version == "v1":
            builder = self.v1_builder
            system_prompt = """Je bent een expert in het analyseren van servicecontracten voor verwarmingssystemen.

Je taak is om te bepalen of een werkbon binnen of buiten een servicecontract valt.

Analyseer het werkbon verhaal en vergelijk met de contractvoorwaarden. Let op:
- Type werkzaamheden (onderhoud, reparatie, storing, modificatie)
- Gebruikte materialen en onderdelen
- Arbeidsuren en kostenposten
- Specifieke uitsluitingen in het contract
- Storingscodes en oorzaken

Geef je antwoord ALLEEN in het volgende JSON formaat:
{
    "classificatie": "JA" of "NEE",
    "confidence": 0.0-1.0,
    "contract_referentie": "Verwijzing naar relevant contract artikel",
    "toelichting": "Korte uitleg van je redenering"
}

Classificatie:
- JA: Werkzaamheden vallen volledig binnen het contract (niet factureren aan klant)
- NEE: Werkzaamheden vallen buiten het contract (wel factureren aan klant)

confidence: Je zekerheid over de classificatie (0.0 = zeer onzeker, 1.0 = zeer zeker)

BELANGRIJK: Geef ALTIJD een classificatie (JA of NEE), ook als je onzeker bent.
De confidence score geeft aan hoe zeker je bent."""

        else:  # v2
            builder = self.v2_builder
            system_prompt = """Je bent een expert in het analyseren van servicecontracten voor verwarmingssystemen.

Je taak is om te bepalen of een werkbon binnen of buiten een servicecontract valt.

⭐ BELANGRIJKSTE ANALYSE PUNT: Lees EERST de "WAT HEEFT DE MONTEUR GEDAAN? (Oplossingen)" sectie.
Dit is een vrij tekstveld waar de monteur beschrijft wat er aan de hand was en wat hij heeft gedaan.
Deze informatie is CRUCIAAL en weegt ZWAARDER dan de automatische kostenregels.

🔍 KRITISCHE DEFINITIES:

**"BINNEN DE MANTEL" (< 2 meter van cv-ketel):**
Dit betekent: onderdelen DIE DEEL UITMAKEN VAN DE CV-KETEL ZELF, ook wel "binnen de ketelkast":
- ✅ BINNEN CONTRACT: Ventilator, gasklep, expansievat, warmtewisselaar, ontstekingselektrode,
  pakking, printplaat, sensor, drukmeter, ontluchter, pomp van de ketel, waterdrukschakelaar
- ✅ BINNEN CONTRACT: "Ketel lek", "onderdeel in/aan de ketel", "lekkage aan ketel"
- ❌ BUITEN CONTRACT: Radiatoren, leidingen, thermostaatkranen (tenzij binnen 2m van ketel)
- ❌ BUITEN CONTRACT: "Lekkage ONDER de ketel" = buiten de ketelkast

**VEELVOORKOMENDE GEVALLEN:**
1. **Storing + ketelonderdeel vervangen** → JA (binnen contract)
   - "Ventilator vervangen", "Pakking ververst", "Expansievat defect"
2. **Storing + radiator/leiding** → NEE (buiten contract, tenzij expliciet binnen 2m)
   - "Radiator vervangen", "Leiding gerepareerd"
3. **Niet thuis geweest** → TWIJFEL (lastig te bepalen of terecht)
4. **Verstopping** → NEE (valt meestal buiten contract)

Analyseer vervolgens:
- Type werkzaamheden (onderhoud, reparatie, storing, modificatie)
- Locatie: binnen ketelkast vs buiten ketel
- Gebruikte materialen en onderdelen
- Arbeidsuren en kostenposten
- Specifieke uitsluitingen in het contract
- Storingscodes en oorzaken

Geef je antwoord ALLEEN in het volgende JSON formaat:
{
    "classificatie": "JA" of "NEE",
    "confidence": 0.0-1.0,
    "contract_referentie": "Verwijzing naar relevant contract artikel",
    "toelichting": "Korte uitleg: vermeld EXPLICIET wat de monteur deed en of het binnen/buiten de ketelkast was"
}

Classificatie:
- JA: Werkzaamheden vallen volledig binnen het contract (niet factureren aan klant)
- NEE: Werkzaamheden vallen buiten het contract (wel factureren aan klant)

confidence: Je zekerheid over de classificatie (0.0 = zeer onzeker, 1.0 = zeer zeker)

BELANGRIJK:
- Geef ALTIJD een classificatie (JA of NEE), ook als je onzeker bent
- Bij twijfel over locatie → kijk naar wat de monteur schrijft in oplossingen
- Ketelonderdelen zijn BINNEN contract, ook als ze "duur" zijn (ventilator, gasklep, etc.)"""

        verhaal = builder.build_verhaal(keten)

        contract_truncated = contract_text[:15000] if len(contract_text) > 15000 else contract_text

        user_message = f"""### CONTRACT ###
{contract_truncated}

### WERKBON VERHAAL ###
{verhaal}

Classificeer deze werkbon. {"Let VOORAL op de 'WAT HEEFT DE MONTEUR GEDAAN?' sectie." if version == "v2" else ""}
Geef je antwoord in JSON formaat."""

        # Call Claude API
        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )

            response_text = response.content[0].text

            # Parse JSON
            text = response_text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            result = json.loads(text.strip())

            confidence = float(result.get("confidence", 0.5))
            base_classificatie = result.get("classificatie", "NEE").upper()

            # Apply thresholds
            threshold_ja = 0.85
            threshold_nee = 0.85

            if base_classificatie == "JA":
                final = "JA" if confidence >= threshold_ja else "TWIJFEL"
            else:
                final = "NEE" if confidence >= threshold_nee else "TWIJFEL"

            return {
                "werkbon_key": werkbon_key,
                "version": version,
                "classificatie": final,
                "basis_classificatie": base_classificatie,
                "confidence": confidence,
                "contract_referentie": result.get("contract_referentie", ""),
                "toelichting": result.get("toelichting", ""),
                "totaal_kosten": keten.totaal_kosten,
            }

        except Exception as e:
            return {
                "werkbon_key": werkbon_key,
                "version": version,
                "error": str(e),
                "classificatie": "ERROR",
                "confidence": 0.0,
                "toelichting": f"API fout: {str(e)}"
            }

    def run_backtest(self):
        """Run backtest on Gerrit's data."""
        print(f"\n{'='*70}")
        print("BACKTEST: V1 vs V2 op Gerrit's Trivire werkbonnen")
        print(f"{'='*70}\n")

        results = []
        werkbon_keys = self.ground_truth['werkbon_key'].tolist()

        # Get Trivire contract
        trivire_contract = self._get_contract_for_debiteur("005102 - Trivire")
        if not trivire_contract:
            print("ERROR: Trivire contract niet gevonden!")
            return

        print(f"Contract: {trivire_contract['filename']}")
        print(f"Te classificeren: {len(werkbon_keys)} werkbonnen")
        print(f"\nStart classificeren...\n")

        for i, werkbon_key in enumerate(werkbon_keys):
            print(f"[{i+1}/{len(werkbon_keys)}] Werkbon {werkbon_key}...")

            # Get Gerrit's beoordeling
            gerrit_row = self.ground_truth[self.ground_truth['werkbon_key'] == werkbon_key].iloc[0]
            gerrit_class = gerrit_row['classificatie']
            gerrit_correct = gerrit_row['eind']  # 'goed' of 'fout'
            gerrit_opmerking = gerrit_row['opmerkingen WVc']

            # Classify with V1
            print(f"  🔵 V1...", end=" ")
            v1_result = self.classify_werkbon(werkbon_key, trivire_contract["content"], "v1")
            print(f"{v1_result.get('classificatie', 'ERROR')}")

            # Classify with V2
            print(f"  🟢 V2...", end=" ")
            v2_result = self.classify_werkbon(werkbon_key, trivire_contract["content"], "v2")
            print(f"{v2_result.get('classificatie', 'ERROR')}")

            # Determine correct answer based on Gerrit's original label + his correction
            if gerrit_correct == 'goed':
                # AI was correct - Gerrit agreed
                correct_label = gerrit_class
            else:
                # AI was wrong - invert
                correct_label = "NEE" if gerrit_class == "JA" else "JA"

            # Check if V1/V2 match Gerrit's correct answer
            v1_correct = v1_result.get('classificatie') == correct_label
            v2_correct = v2_result.get('classificatie') == correct_label

            result = {
                "werkbon_key": werkbon_key,
                "gerrit_original": gerrit_class,
                "gerrit_correct": gerrit_correct,
                "gerrit_opmerking": gerrit_opmerking,
                "correct_label": correct_label,
                "v1_classificatie": v1_result.get("classificatie", "ERROR"),
                "v1_confidence": v1_result.get("confidence", 0),
                "v1_match": "✅" if v1_correct else "❌",
                "v2_classificatie": v2_result.get("classificatie", "ERROR"),
                "v2_confidence": v2_result.get("confidence", 0),
                "v2_match": "✅" if v2_correct else "❌",
                "verbetering": "🎯" if (v2_correct and not v1_correct) else ("➖" if v2_correct == v1_correct else "⬇️")
            }

            results.append(result)

            print(f"  Correct label: {correct_label} | V1: {result['v1_match']} | V2: {result['v2_match']} | {result['verbetering']}")
            print()

        # Save results
        df_results = pd.DataFrame(results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"backtest_gerrit_trivire_{timestamp}.csv"
        df_results.to_csv(output_file, index=False)

        # Statistics
        print(f"\n{'='*70}")
        print("RESULTATEN")
        print(f"{'='*70}\n")

        v1_correct_count = len(df_results[df_results['v1_match'] == '✅'])
        v2_correct_count = len(df_results[df_results['v2_match'] == '✅'])
        total = len(df_results)

        print(f"Totaal werkbonnen: {total}")
        print(f"\nV1 (Origineel):")
        print(f"  Correct: {v1_correct_count}/{total} = {v1_correct_count/total*100:.1f}%")

        print(f"\nV2 (Verbeterd):")
        print(f"  Correct: {v2_correct_count}/{total} = {v2_correct_count/total*100:.1f}%")

        verbetering = v2_correct_count - v1_correct_count
        if verbetering > 0:
            print(f"\n✅ VERBETERING: +{verbetering} werkbonnen (+{verbetering/total*100:.1f}%)")
        elif verbetering < 0:
            print(f"\n❌ VERSLECHTERING: {verbetering} werkbonnen ({verbetering/total*100:.1f}%)")
        else:
            print(f"\n➖ Geen verschil")

        # Show improvements
        verbeterd = df_results[df_results['verbetering'] == '🎯']
        if len(verbeterd) > 0:
            print(f"\n{'='*70}")
            print(f"VERBETERDE CLASSIFICATIES ({len(verbeterd)} stuks):")
            print(f"{'='*70}\n")

            for idx, row in verbeterd.head(10).iterrows():
                print(f"Werkbon {row['werkbon_key']}:")
                print(f"  Gerrit: {row['gerrit_opmerking']}")
                print(f"  Correct: {row['correct_label']}")
                print(f"  V1 zei: {row['v1_classificatie']} (fout)")
                print(f"  V2 zei: {row['v2_classificatie']} (goed!)")
                print()

        # Show where V2 made it worse
        verslechterd = df_results[df_results['verbetering'] == '⬇️']
        if len(verslechterd) > 0:
            print(f"\n{'='*70}")
            print(f"VERSLECHTERDE CLASSIFICATIES ({len(verslechterd)} stuks):")
            print(f"{'='*70}\n")

            for idx, row in verslechterd.head(5).iterrows():
                print(f"Werkbon {row['werkbon_key']}:")
                print(f"  Gerrit: {row['gerrit_opmerking']}")
                print(f"  Correct: {row['correct_label']}")
                print(f"  V1 zei: {row['v1_classificatie']} (goed)")
                print(f"  V2 zei: {row['v2_classificatie']} (fout)")
                print()

        print(f"{'='*70}")
        print(f"Resultaten opgeslagen: {output_file}")
        print(f"{'='*70}\n")

        return df_results


def main():
    """Run backtest."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        return

    runner = GerritBacktest(api_key=api_key)
    results = runner.run_backtest()

    print("✅ Backtest voltooid!")


if __name__ == "__main__":
    main()
