#!/usr/bin/env python3
"""
Backtest script: Vergelijk V1 vs V2 classificaties
Run beide versies op dezelfde werkbonnen en vergelijk de resultaten.

Optioneel: als je een CSV hebt met handmatige labels, vergelijk dan ook met die ground truth.
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import anthropic
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.parquet_data_service import ParquetDataService, WerkbonVerhaalBuilder

# Import V2 builder
from app_v2 import VerbeterdeVerhaalBuilder


class BacktestRunner:
    """Run backtest comparing V1 and V2."""

    def __init__(self, api_key: str, data_dir: str = "data", contracts_dir: str = "contracts"):
        self.api_key = api_key
        self.data_service = ParquetDataService(data_dir=data_dir)
        self.contracts = self._load_contracts(contracts_dir)

        # Builders
        self.v1_builder = WerkbonVerhaalBuilder()
        self.v2_builder = VerbeterdeVerhaalBuilder()

        # Anthropic client
        self.client = anthropic.Anthropic(api_key=api_key)

    def _load_contracts(self, contracts_dir: str):
        """Load contracts from directory."""
        contracts_path = Path(contracts_dir)
        contracts = {}

        meta_path = contracts_path / "contracts_metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            for c in meta.get("contracts", []):
                contract_file = contracts_path / c["filename"]
                if contract_file.exists():
                    content = contract_file.read_text(encoding="utf-8")
                    contracts[c["id"]] = {
                        "id": c["id"],
                        "filename": c["filename"],
                        "content": content,
                        "clients": c.get("clients", [])
                    }

        return contracts

    def _get_contract_for_debiteur(self, debiteur_code: str):
        """Get contract for a specific debiteur."""
        code = debiteur_code.split(" - ")[0].strip() if " - " in debiteur_code else debiteur_code

        for contract in self.contracts.values():
            if code in contract.get("clients", []):
                return contract
        return None

    def classify_with_version(
        self,
        werkbon_key: int,
        contract_text: str,
        version: str,
        threshold_ja: float = 0.85,
        threshold_nee: float = 0.85
    ) -> dict:
        """Classify a werkbon with V1 or V2."""
        # Get werkbon keten
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

        # Build verhaal based on version
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

Analyseer vervolgens:
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
    "toelichting": "Korte uitleg van je redenering, vermeld EXPLICIET wat de monteur heeft gedaan"
}

Classificatie:
- JA: Werkzaamheden vallen volledig binnen het contract (niet factureren aan klant)
- NEE: Werkzaamheden vallen buiten het contract (wel factureren aan klant)

confidence: Je zekerheid over de classificatie (0.0 = zeer onzeker, 1.0 = zeer zeker)

BELANGRIJK: Geef ALTIJD een classificatie (JA of NEE), ook als je onzeker bent.
De confidence score geeft aan hoe zeker je bent."""

        verhaal = builder.build_verhaal(keten)

        # Truncate contract if too long
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
                "raw_response": response_text
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

    def run_backtest(
        self,
        debiteur_filter: list = None,
        date_start: str = None,
        date_end: str = None,
        max_werkbonnen: int = 50,
        ground_truth_csv: str = None
    ):
        """Run backtest on selected werkbonnen."""
        print(f"\n{'='*60}")
        print("BACKTEST: V1 vs V2 Contract Checker")
        print(f"{'='*60}\n")

        # Load werkbonnen
        df = self.data_service.df_werkbonnen.copy()
        df = df[df["werkbon_key"] == df["hoofdwerkbon_key"]]

        # Filters
        if debiteur_filter:
            mask = df["debiteur"].apply(
                lambda x: any(code in str(x) for code in debiteur_filter)
            )
            df = df[mask]

        if date_start or date_end:
            df["melddatum_str"] = df["melddatum"].fillna("").astype(str).str[:10]
            if date_start:
                df = df[df["melddatum_str"] >= date_start]
            if date_end:
                df = df[df["melddatum_str"] <= date_end]

        df = df.sort_values("melddatum", ascending=False).head(max_werkbonnen)

        werkbon_keys = df["werkbon_key"].tolist()
        print(f"Geselecteerd: {len(werkbon_keys)} werkbonnen")

        if debiteur_filter:
            print(f"Debiteur filter: {debiteur_filter}")
        if date_start or date_end:
            print(f"Datum filter: {date_start or '...'} tot {date_end or '...'}")

        # Load ground truth if provided
        ground_truth = {}
        if ground_truth_csv and Path(ground_truth_csv).exists():
            gt_df = pd.read_csv(ground_truth_csv)
            if "werkbon_key" in gt_df.columns and "label" in gt_df.columns:
                ground_truth = dict(zip(gt_df["werkbon_key"], gt_df["label"]))
                print(f"\n✅ Ground truth geladen: {len(ground_truth)} gelabelde werkbonnen")

        print(f"\n{'='*60}")
        print("Start classificeren...")
        print(f"{'='*60}\n")

        results = []

        for i, row in df.iterrows():
            werkbon_key = int(row["werkbon_key"])
            debiteur = row["debiteur"]

            print(f"[{len(results)+1}/{len(werkbon_keys)}] Werkbon {werkbon_key} - {debiteur[:30]}...")

            # Get contract
            contract = self._get_contract_for_debiteur(debiteur)
            if not contract:
                print(f"  ⚠️  Geen contract gevonden, skip")
                continue

            # Classify with V1
            print(f"  🔵 V1 classificeren...")
            v1_result = self.classify_with_version(werkbon_key, contract["content"], "v1")

            # Classify with V2
            print(f"  🟢 V2 classificeren...")
            v2_result = self.classify_with_version(werkbon_key, contract["content"], "v2")

            # Combine results
            combined = {
                "werkbon_key": werkbon_key,
                "debiteur": debiteur,
                "contract": contract["filename"],
                "v1_classificatie": v1_result.get("classificatie", "ERROR"),
                "v1_confidence": v1_result.get("confidence", 0),
                "v1_toelichting": v1_result.get("toelichting", ""),
                "v2_classificatie": v2_result.get("classificatie", "ERROR"),
                "v2_confidence": v2_result.get("confidence", 0),
                "v2_toelichting": v2_result.get("toelichting", ""),
                "verschil": "✅ Gelijk" if v1_result.get("classificatie") == v2_result.get("classificatie") else "❌ Verschillend",
                "totaal_kosten": v1_result.get("totaal_kosten", 0),
            }

            # Add ground truth if available
            if werkbon_key in ground_truth:
                gt = ground_truth[werkbon_key].upper()
                combined["ground_truth"] = gt
                combined["v1_correct"] = "✅" if v1_result.get("classificatie") == gt else "❌"
                combined["v2_correct"] = "✅" if v2_result.get("classificatie") == gt else "❌"

            results.append(combined)

            print(f"  📊 V1: {v1_result.get('classificatie')} ({v1_result.get('confidence', 0):.0%})")
            print(f"  📊 V2: {v2_result.get('classificatie')} ({v2_result.get('confidence', 0):.0%})")
            if werkbon_key in ground_truth:
                print(f"  ✅ Ground truth: {ground_truth[werkbon_key]} | V1: {combined['v1_correct']} | V2: {combined['v2_correct']}")
            print()

        # Save results
        df_results = pd.DataFrame(results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"backtest_results_{timestamp}.csv"
        df_results.to_csv(output_file, index=False)

        print(f"\n{'='*60}")
        print("RESULTATEN")
        print(f"{'='*60}\n")

        # Statistics
        total = len(df_results)
        v1_ja = len(df_results[df_results["v1_classificatie"] == "JA"])
        v1_nee = len(df_results[df_results["v1_classificatie"] == "NEE"])
        v1_twijfel = len(df_results[df_results["v1_classificatie"] == "TWIJFEL"])

        v2_ja = len(df_results[df_results["v2_classificatie"] == "JA"])
        v2_nee = len(df_results[df_results["v2_classificatie"] == "NEE"])
        v2_twijfel = len(df_results[df_results["v2_classificatie"] == "TWIJFEL"])

        verschillen = len(df_results[df_results["verschil"] == "❌ Verschillend"])

        print(f"Totaal werkbonnen: {total}")
        print(f"\nV1 verdeling:")
        print(f"  JA:      {v1_ja} ({v1_ja/total*100:.1f}%)")
        print(f"  NEE:     {v1_nee} ({v1_nee/total*100:.1f}%)")
        print(f"  TWIJFEL: {v1_twijfel} ({v1_twijfel/total*100:.1f}%)")

        print(f"\nV2 verdeling:")
        print(f"  JA:      {v2_ja} ({v2_ja/total*100:.1f}%)")
        print(f"  NEE:     {v2_nee} ({v2_nee/total*100:.1f}%)")
        print(f"  TWIJFEL: {v2_twijfel} ({v2_twijfel/total*100:.1f}%)")

        print(f"\nVerschillen: {verschillen} ({verschillen/total*100:.1f}%)")

        # Ground truth analysis
        if ground_truth:
            v1_correct = len(df_results[df_results["v1_correct"] == "✅"])
            v2_correct = len(df_results[df_results["v2_correct"] == "✅"])
            gt_total = len(df_results[df_results["ground_truth"].notna()])

            print(f"\n{'='*60}")
            print("ACCURACY (vs Ground Truth)")
            print(f"{'='*60}\n")
            print(f"V1 accuracy: {v1_correct}/{gt_total} = {v1_correct/gt_total*100:.1f}%")
            print(f"V2 accuracy: {v2_correct}/{gt_total} = {v2_correct/gt_total*100:.1f}%")

            verbetering = v2_correct - v1_correct
            if verbetering > 0:
                print(f"\n✅ V2 is {verbetering} werkbonnen beter (+{verbetering/gt_total*100:.1f}%)")
            elif verbetering < 0:
                print(f"\n❌ V2 is {abs(verbetering)} werkbonnen slechter ({verbetering/gt_total*100:.1f}%)")
            else:
                print(f"\n➖ V1 en V2 presteren gelijk")

        print(f"\n{'='*60}")
        print(f"Resultaten opgeslagen in: {output_file}")
        print(f"{'='*60}\n")

        return df_results


def main():
    """Run backtest from command line."""
    import os

    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        print("Export je API key: export ANTHROPIC_API_KEY=sk-ant-...")
        return

    runner = BacktestRunner(api_key=api_key)

    # Run backtest - pas deze parameters aan naar wens
    results = runner.run_backtest(
        debiteur_filter=["005102"],  # Trivire
        date_start="2024-01-01",
        date_end="2024-12-31",
        max_werkbonnen=50,  # Test op 50 werkbonnen
        ground_truth_csv=None  # Optioneel: pad naar CSV met handmatige labels
    )

    print("✅ Backtest voltooid!")


if __name__ == "__main__":
    main()
