#!/usr/bin/env python3
"""
Backtest V4 prompt tegen Gerrit's beoordeelde werkbonnen.

Vergelijkt V4 AI classificatie met Gerrit's handmatige beoordeling
om te bepalen of de accuracy verbeterd is t.o.v. V3 (72.5%).
"""
import json
import re
import sys
import time
from pathlib import Path

import anthropic
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.parquet_data_service import ParquetDataService, WerkbonVerhaalBuilder

# === VERBETERDE VERHAAL BUILDER (kopie uit app_v2.py) ===
class VerbeterdeVerhaalBuilder(WerkbonVerhaalBuilder):
    """Verbeterde builder die oplossingen prominenter toont."""

    def build_verhaal(self, keten, chronological: bool = True) -> str:
        lines = []
        lines.append(f"# Werkbonketen voor {keten.relatie_naam}")
        lines.append(f"Relatiecode: {keten.relatie_code}")
        lines.append("")
        lines.append("## Samenvatting")
        lines.append(f"- Aantal werkbonnen in keten: {keten.aantal_werkbonnen}")
        lines.append(f"- Totaal aantal paragrafen: {keten.aantal_paragrafen}")
        lines.append(f"- Totale kosten: €{keten.totaal_kosten:,.2f}")
        lines.append("")

        werkbonnen = sorted(
            keten.werkbonnen,
            key=lambda w: w.melddatum or "",
            reverse=chronological
        )

        for i, wb in enumerate(werkbonnen, 1):
            if wb.is_hoofdwerkbon:
                lines.append(f"## Hoofdwerkbon: {wb.werkbon_nummer}")
            else:
                lines.append(f"## Vervolgbon (niveau {wb.niveau}): {wb.werkbon_nummer}")

            lines.append(f"- **Status: {wb.status}** | Documentstatus: {wb.documentstatus}")
            if wb.administratieve_fase:
                lines.append(f"- Administratieve fase: {wb.administratieve_fase}")
            lines.append(f"- Type: {wb.type}")
            if wb.melddatum:
                melding = wb.melddatum
                if wb.meldtijd:
                    melding += f" {wb.meldtijd}"
                lines.append(f"- Melding: {melding}")
            if wb.afspraakdatum:
                lines.append(f"- Afspraakdatum: {wb.afspraakdatum}")
            if wb.opleverdatum:
                lines.append(f"- Opleverdatum: {wb.opleverdatum}")
            if wb.monteur:
                lines.append(f"- Monteur: {wb.monteur}")
            lines.append(f"- Locatie: {wb.postcode} {wb.plaats}")

            if wb.paragrafen:
                lines.append("### Werkbonparagrafen")
                for p in wb.paragrafen:
                    lines.append(f"\n**{p.naam}** ({p.type})")
                    lines.append(f"- Uitvoeringstatus: {p.uitvoeringstatus}")
                    if p.plandatum:
                        lines.append(f"- Plandatum: {p.plandatum}")
                    if p.uitgevoerd_op:
                        uitvoering = p.uitgevoerd_op
                        if p.tijdstip_uitgevoerd:
                            uitvoering += f" {p.tijdstip_uitgevoerd}"
                        lines.append(f"- Uitgevoerd: {uitvoering}")
                    if p.storing:
                        lines.append(f"- Storingscode: {p.storing}")
                    if p.oorzaak:
                        lines.append(f"- Oorzaakcode: {p.oorzaak}")

                    # OPLOSSINGEN EERST
                    if p.oplossingen:
                        lines.append("")
                        lines.append("🔍 **WAT HEEFT DE MONTEUR GEDAAN? (Oplossingen):**")
                        oplossingen = sorted(
                            p.oplossingen,
                            key=lambda o: o.aanmaakdatum or "",
                            reverse=chronological
                        )
                        for opl in oplossingen:
                            datum = f"[{opl.aanmaakdatum}] " if opl.aanmaakdatum else ""
                            lines.append(f"- {datum}{opl.oplossing}")
                            if opl.oplossing_uitgebreid:
                                lines.append(f"  Toelichting: {opl.oplossing_uitgebreid}")

                    if p.kosten:
                        lines.append("")
                        lines.append("**Kostenregels (arbeid & materiaal):**")
                        for k in p.kosten:
                            lines.append(f"- {k.categorie}: {k.get_volledige_omschrijving()} | "
                                         f"€{k.verrekenprijs:.2f} x {k.aantal} | "
                                         f"Status: {k.factureerstatus}")

                    if p.opvolgingen:
                        lines.append("")
                        lines.append("**Opvolgingen:**")
                        for o in p.opvolgingen:
                            lines.append(f"- [{o.status}] {o.opvolgsoort}: {o.beschrijving}")

            lines.append("")

        return "\n".join(lines)


# V6 SYSTEM PROMPT: Generiek, contracttekst-gestuurd
SYSTEM_PROMPT_V6 = """Je bent een expert in het analyseren van servicecontracten voor verwarmingssystemen.

Je taak is om te bepalen of een werkbon binnen of buiten een servicecontract valt.
Het CONTRACT dat je meekrijgt bevat het BASISPRINCIPE en de BELANGRIJKE UITZONDERINGEN voor deze specifieke woningbouwvereniging. Lees dit EERST en volg de contractregels nauwkeurig.

⭐ BELANGRIJKSTE ANALYSE PUNT: Lees daarna de "WAT HEEFT DE MONTEUR GEDAAN? (Oplossingen)" sectie.
Dit is een vrij tekstveld waar de monteur beschrijft wat er aan de hand was en wat hij heeft gedaan.
Deze informatie is CRUCIAAL en weegt ZWAARDER dan storingscodes of kostenregels.

🔍 UNIVERSELE REGELS (gelden voor ALLE contracten, op volgorde van prioriteit):

📌 REGEL 0 - HOOGSTE PRIORITEIT (ALTIJD NEE, ongeacht andere regels):
- **Oorzaakcode 900 / "Probleem door derde"** → ALTIJD NEE (factureren aan derden)
  Dit geldt OOK als de storingscode iets anders suggereert (bijv. lekkage onder ketel + probleem derden = NEE)
- **Tapwaterboiler / geiser / moederhaard** → ALTIJD NEE (regie)
- **Vloerverwarming (verdelers, pompen, regelingen)** → ALTIJD NEE (buiten contract)
- **Verstopping** → ALTIJD NEE (buiten contract)

📌 REGEL 1 - OPLOSSING GAAT VOOR OP STORINGSCODE:
- Als de OPLOSSING van de monteur is "installatie gevuld en ontlucht" / "bijgevuld" / "ontlucht" → ALTIJD JA
  Dit geldt OOK als de storingscode iets anders suggereert (bijv. "GEEN CV en WW" + oplossing gevuld/ontlucht = JA)
- Als de OPLOSSING een ander verhaal vertelt dan de storingscode, volg dan de OPLOSSING

📌 REGEL 2 - CONTRACTTEKST IS LEIDEND:
Volg het CONTRACT voor contractspecifieke regels over:
- Welke onderdelen/locaties wel of niet gedekt zijn
- Of er een afstandsgrens geldt (bijv. "2 meter van de ketel")
- Hoe radiatoren, radiatorkranen, WTW-units, RGA/LTV behandeld worden
- Deze regels VERSCHILLEN per woningbouwvereniging — lees het contract!

📌 REGEL 3 - STORINGSCODES (universeel, Syntess-systeemcodes):
- **Storingscode 006.1 "Lekkage ONDER de ketel"** = lekkage dichtbij/onder de ketel (binnen de mantel)
- **Storingscode 006.2 "Lekkage aan de installatie"** = lekkage op AFSTAND van de ketel (buiten de mantel) → NEE
  LET OP: 006.1 ≠ 006.2! Dit is een CRUCIAAL onderscheid.
  006.2 betekent dat de lekkage NIET aan de ketel zelf zit maar aan de installatie op afstand → classificeer als NEE.

📌 REGEL 4 - BIJ TWIJFEL:
- **Radiatoren vervangen** → classificeer als NEE (medewerker kan dit beter beoordelen dan AI)
- **CV-leiding niet in het zicht (reparatie)** → classificeer als NEE (moeilijk te beoordelen door AI)
- **Niet thuis geweest** → JA met lage confidence (werk niet uitgevoerd maar geen regie)

Analyseer vervolgens:
- Type werkzaamheden (onderhoud, reparatie, storing, modificatie)
- Locatie: binnen ketelkast/mantel vs buiten ketel
- Gebruikte materialen en onderdelen
- Arbeidsuren en kostenposten
- Oorzaak: wie/wat veroorzaakt het probleem
- Storingscodes en oorzaken

Geef je antwoord ALLEEN in het volgende JSON formaat:
{
    "classificatie": "JA" of "NEE",
    "confidence": 0.0-1.0,
    "contract_referentie": "Verwijzing naar relevant contract artikel of -regel",
    "toelichting": "Korte uitleg: vermeld EXPLICIET wat de monteur deed en welke contractregel van toepassing is"
}

Classificatie:
- JA: Werkzaamheden vallen volledig binnen het contract (niet factureren aan klant)
- NEE: Werkzaamheden vallen buiten het contract (wel factureren aan klant)

confidence: Je zekerheid over de classificatie (0.0 = zeer onzeker, 1.0 = zeer zeker)

BELANGRIJK:
- Geef ALTIJD een classificatie (JA of NEE), ook als je onzeker bent
- Bij twijfel over locatie → kijk naar wat de monteur schrijft in oplossingen
- Ketelonderdelen (binnen de mantel) zijn BINNEN contract, ook als ze "duur" zijn
- OORZAAK "PROBLEEM DOOR DERDE" → ALTIJD NEE, ook bij lekkage onder ketel
- OPLOSSING "gevuld en ontlucht" → ALTIJD JA, ook als storingscode iets anders suggereert
- Volg het CONTRACT voor contractspecifieke regels over radiatorkranen, WTW-units, afstandsgrenzen etc."""


def classify_werkbon(client, verhaal, contract_text, threshold_ja=0.7, threshold_nee=0.7):
    """Classify a single werkbon using V4 prompt."""
    contract_truncated = contract_text[:15000] if len(contract_text) > 15000 else contract_text

    user_message = f"""### CONTRACT ###
{contract_truncated}

### WERKBON VERHAAL ###
{verhaal}

Classificeer deze werkbon. Let VOORAL op de "WAT HEEFT DE MONTEUR GEDAAN?" sectie.
Geef je antwoord in JSON formaat."""

    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            temperature=0,
            system=SYSTEM_PROMPT_V6,
            messages=[{"role": "user", "content": user_message}]
        )

        response_text = response.content[0].text
        text = response_text.strip()

        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        # Clean control characters
        text_clean = re.sub(r'[\x00-\x1f\x7f]', ' ', text.strip())

        try:
            result = json.loads(text_clean)
        except json.JSONDecodeError:
            # Regex fallback
            class_match = re.search(r'"classificatie"\s*:\s*"(JA|NEE)"', text, re.IGNORECASE)
            conf_match = re.search(r'"confidence"\s*:\s*([\d.]+)', text)

            if class_match:
                result = {
                    "classificatie": class_match.group(1).upper(),
                    "confidence": float(conf_match.group(1)) if conf_match else 0.8,
                    "toelichting": "Regex fallback"
                }
            else:
                return "PARSE_ERROR", 0.0, "Kon niet parsen"

        confidence = float(result.get("confidence", 0.5))
        base = result.get("classificatie", "NEE").upper()

        if base == "JA":
            final = "JA" if confidence >= threshold_ja else "TWIJFEL"
        else:
            final = "NEE" if confidence >= threshold_nee else "TWIJFEL"

        return final, confidence, result.get("toelichting", "")

    except Exception as e:
        return "ERROR", 0.0, str(e)


def main():
    # Load data
    data_dir = Path(__file__).parent / "data"
    data_service = ParquetDataService(data_dir=str(data_dir))
    builder = VerbeterdeVerhaalBuilder()

    # Load contract
    contract_path = Path(__file__).parent / "contracts" / "Trivire_Tablis_rhiant.txt"
    contract_text = contract_path.read_text(encoding="utf-8")

    # Load ground truth from Gerrit's V2.1 steekproef
    excel_path = Path(__file__).parent / "contract-check-public" / "feedback Gerrit" / "Steekproef bonnen Trivire V2.1.xlsx"
    df_truth = pd.read_excel(excel_path, engine="openpyxl", sheet_name="classificatie_geschiedenis_v2 (")
    df_truth = df_truth[df_truth["werkbon_code"].notna() & (df_truth["werkbon_code"] != "NaT")]

    # Filter only werkbonnen with bevinding (goed/fout), skip nvt and nan
    df_test = df_truth[df_truth["bevinding WVC"].isin(["goed", "fout"])].copy()

    print(f"=== BACKTEST V4 ===")
    print(f"Werkbonnen met bevinding: {len(df_test)}")
    print(f"Contract: Trivire_Tablis_rhiant.txt")
    print()

    # Determine what the "correct" answer should be
    # If bevinding = goed, then V3 classificatie was correct → correct = V3 classificatie
    # If bevinding = fout, then we need Gerrit's opmerking to determine correct answer
    # For simplicity: we compare V4 result against V3 + Gerrit's correction

    # API client
    api_key = "***REMOVED***"
    client = anthropic.Anthropic(api_key=api_key)

    results = []
    for i, (_, row) in enumerate(df_test.iterrows()):
        werkbon_key = int(row["werkbon_key"])
        werkbon_code = row["werkbon_code"]
        v3_classificatie = row["classificatie"]
        bevinding = row["bevinding WVC"]
        opmerking = str(row["opmerking"]) if pd.notna(row["opmerking"]) else ""

        # Determine expected answer
        if bevinding == "goed":
            expected = v3_classificatie  # V3 was correct
        else:
            # V3 was wrong - determine correct from opmerking
            if "binnen contract" in opmerking.lower() or "gevuld en ontlucht" in opmerking.lower() or "niet thuis" in opmerking.lower():
                expected = "JA"
            elif "buiten" in opmerking.lower() or "regie" in opmerking.lower() or "factureren" in opmerking.lower():
                expected = "NEE"
            elif "twijfel" in opmerking.lower() or "moet twijfel" in opmerking.lower():
                expected = "TWIJFEL"
            else:
                # Try to infer from V3 classification being wrong
                if v3_classificatie in ["JA"]:
                    expected = "NEE"
                elif v3_classificatie in ["NEE"]:
                    expected = "JA"
                else:
                    expected = "JA"  # Default assumption

        # Build verhaal - INCLUSIEF kosten en oplossingen (zelfde als live app!)
        keten = data_service.get_werkbon_keten(
            werkbon_key,
            include_kosten_details=True,
            include_oplossingen=True,
            include_opvolgingen=True
        )
        if not keten:
            print(f"  [{i+1}/{len(df_test)}] {werkbon_code}: SKIP (geen data)")
            continue

        verhaal = builder.build_verhaal(keten)

        # Classify
        v4_classificatie, confidence, toelichting = classify_werkbon(client, verhaal, contract_text)

        # Compare
        v4_correct = (v4_classificatie == expected) or (v4_classificatie == "TWIJFEL" and expected == "TWIJFEL")
        # Also count as "roughly correct" if base direction matches (JA vs NEE)
        v4_direction_ok = (v4_classificatie in ["JA", "TWIJFEL"] and expected in ["JA", "TWIJFEL"]) or \
                          (v4_classificatie in ["NEE", "TWIJFEL"] and expected in ["NEE", "TWIJFEL"])

        status = "OK" if v4_correct else ("~" if v4_direction_ok else "FOUT")
        print(f"  [{i+1}/{len(df_test)}] {werkbon_code}: V3={v3_classificatie} -> V4={v4_classificatie} (verwacht: {expected}) {status}")
        if not v4_correct:
            print(f"           Toelichting: {toelichting[:120].encode('ascii', 'replace').decode()}")
            if opmerking:
                print(f"           Gerrit: {opmerking[:120].encode('ascii', 'replace').decode()}")

        results.append({
            "werkbon_code": werkbon_code,
            "werkbon_key": werkbon_key,
            "v3_classificatie": v3_classificatie,
            "v3_bevinding": bevinding,
            "expected": expected,
            "v4_classificatie": v4_classificatie,
            "v4_confidence": confidence,
            "v4_correct": v4_correct,
            "opmerking_gerrit": opmerking
        })

        # Rate limiting
        time.sleep(0.5)

    # Summary
    print("\n" + "="*60)
    print("=== RESULTATEN ===")
    print("="*60)

    total = len(results)
    v3_goed = sum(1 for r in results if r["v3_bevinding"] == "goed")
    v4_goed = sum(1 for r in results if r["v4_correct"])

    print(f"\nTotaal werkbonnen: {total}")
    print(f"V3 accuracy: {100*v3_goed/total:.1f}% ({v3_goed}/{total})")
    print(f"V4 accuracy: {100*v4_goed/total:.1f}% ({v4_goed}/{total})")
    print(f"Verbetering: {v4_goed - v3_goed:+d} werkbonnen")

    # Detail: which errors did V4 fix?
    print("\n--- V3 fouten die V4 WEL goed heeft: ---")
    for r in results:
        if r["v3_bevinding"] == "fout" and r["v4_correct"]:
            print(f"  OK {r['werkbon_code']}: {r['v3_classificatie']} -> {r['v4_classificatie']} (verwacht: {r['expected']})")

    print("\n--- V3 fouten die V4 NOG STEEDS fout heeft: ---")
    for r in results:
        if r["v3_bevinding"] == "fout" and not r["v4_correct"]:
            print(f"  FOUT {r['werkbon_code']}: {r['v3_classificatie']} -> {r['v4_classificatie']} (verwacht: {r['expected']})")
            if r["opmerking_gerrit"]:
                print(f"     Gerrit: {r['opmerking_gerrit'][:100]}")

    print("\n--- V3 goed, maar V4 nu FOUT (regressie!): ---")
    for r in results:
        if r["v3_bevinding"] == "goed" and not r["v4_correct"]:
            print(f"  REGRESSIE {r['werkbon_code']}: {r['v3_classificatie']} -> {r['v4_classificatie']} (was goed!)")

    # Save results
    df_results = pd.DataFrame(results)
    output_path = Path(__file__).parent / "backtest_v4_results.csv"
    df_results.to_csv(output_path, index=False)
    print(f"\nResultaten opgeslagen in: {output_path}")


if __name__ == "__main__":
    main()
