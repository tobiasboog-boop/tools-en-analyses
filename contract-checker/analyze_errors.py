#!/usr/bin/env python3
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from src.services.parquet_data_service import ParquetDataService, WerkbonVerhaalBuilder

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


# V3-FIXED SYSTEM PROMPT: V3 prompt (74% accuracy) + alleen lekkage-fix


WERKBON_CODES = [
    ("W2548345", "V3=NEE, expected=NEE, but lekkage fix makes it JA - conflict with Gerrit"),
    ("W2547870", "lekkage installatie slk/wk - should be NEE but AI says JA"),
    ("W2546414", "radiatorkraan storingscode but oplossing=radiator gedemonteerd verstopping - should be NEE"),
    ("W2546402", "gevuld en ontlucht - should be JA but AI says NEE"),
    ("W2547634", "zonneboiler - keeps getting wrong"),
    ("W2548272", "GEEN CV en WW - should be JA but AI often says NEE"),
    ("W2547442", "often gets PARSE_ERROR or NEE, should be JA"),
    ("W2548293", "GEEN CV en WW - should be JA"),
]


def main():
    excel_path = Path(__file__).parent / "contract-check-public" / "feedback Gerrit" / "Steekproef bonnen Trivire V2.1.xlsx"
    print(f"Loading Excel: {excel_path}")
    df_truth = pd.read_excel(excel_path, engine="openpyxl", sheet_name="classificatie_geschiedenis_v2 (")
    df_truth = df_truth[df_truth["werkbon_code"].notna() & (df_truth["werkbon_code"] != "NaT")]
    print(f"  Total rows: {len(df_truth)}")
    print(f"  Columns: {list(df_truth.columns)}")
    print()
    print("Sample werkbon_code values:")
    print(df_truth["werkbon_code"].head(10).tolist())
    print()

    code_to_key = {}
    code_to_row = {}
    for code, desc in WERKBON_CODES:
        code_clean = code.replace("W", "")
        mask = df_truth["werkbon_code"].astype(str).str.contains(code_clean, na=False)
        matches = df_truth[mask]
        if len(matches) > 0:
            row = matches.iloc[0]
            wk = int(row["werkbon_key"])
            code_to_key[code] = wk
            code_to_row[code] = row
            wc = row["werkbon_code"]
            print(f"  {code} -> werkbon_key={wk} (Excel: {wc})")
        else:
            print(f"  {code} -> NOT FOUND")
            code_to_key[code] = None
    print()

    data_dir = Path(__file__).parent / "data"
    data_service = ParquetDataService(data_dir=str(data_dir))
    builder = VerbeterdeVerhaalBuilder()
    print()

    for code, description in WERKBON_CODES:
        werkbon_key = code_to_key.get(code)
        print("=" * 100)
        print(f"WERKBON: {code} | Key: {werkbon_key}")
        print(f"ISSUE: {description}")
        if code in code_to_row:
            row = code_to_row[code]
            c = row.get("classificatie", "?")
            b = row.get("bevinding WVC", "?")
            o = row.get("opmerking", "?")
            print(f"  Excel: classificatie={c} bevinding={b} opmerking={o}")
        print("-" * 100)

        if werkbon_key is None:
            print("  SKIPPED")
            print()
            continue

        keten = data_service.get_werkbon_keten(
            werkbon_key,
            include_kosten_details=True,
            include_kostenregels_details=True,
            include_opvolgingen=True,
            include_oplossingen=True,
        )
        if not keten:
            print(f"  SKIPPED: No keten for {werkbon_key}")
            print()
            continue

        verhaal = builder.build_verhaal(keten)
        has_opl = "WAT HEEFT DE MONTEUR GEDAAN?" in verhaal
        tag = "YES" if has_opl else "*** NO ***"
        print(f"  Oplossingen section: {tag}")

        for wb in keten.werkbonnen:
            for p in wb.paragrafen:
                si = f"Storingscode: {p.storing}" if p.storing else "Storingscode: (none)"
                oi = f"Oorzaakcode: {p.oorzaak}" if p.oorzaak else "Oorzaakcode: (none)"
                print(f"  Paragraaf [{p.naam}]: {si} | {oi}")
                if p.oplossingen:
                    for opl in p.oplossingen:
                        print(f"    -> Oplossing: {opl.oplossing}")
                        if opl.oplossing_uitgebreid:
                            print(f"       Uitgebreid: {opl.oplossing_uitgebreid}")
                else:
                    print("    -> NO oplossingen")
                if p.kosten:
                    for k in p.kosten:
                        print(f"    -> Kost: [{k.categorie}] {k.omschrijving} | EUR {k.verrekenprijs:.2f} x {k.aantal}")
                else:
                    print("    -> NO kosten")

        print("  --- FULL VERHAAL (truncated to 2000 chars) ---")
        if len(verhaal) > 2000:
            opl_idx = verhaal.find("WAT HEEFT DE MONTEUR GEDAAN?")
            if opl_idx > 0:
                start = max(0, opl_idx - 200)
                end = min(len(verhaal), opl_idx + 800)
                print(f"  [... first {start} chars omitted ...]")
                print(verhaal[start:end])
                print(f"  [... remaining {len(verhaal) - end} chars omitted ...]")
            else:
                print(verhaal[:2000])
                print(f"  [... {len(verhaal) - 2000} chars omitted ...]")
        else:
            print(verhaal)
        print(f"  Total verhaal length: {len(verhaal)} chars")

        keten_nd = data_service.get_werkbon_keten(werkbon_key)
        if keten_nd:
            v_nd = builder.build_verhaal(keten_nd)
            has_nd = "WAT HEEFT DE MONTEUR GEDAAN?" in v_nd
            nd_tag = "YES" if has_nd else "*** NO - MISSING ***"
            print("  *** BACKTEST BUG CHECK ***")
            print(f"  Oplossingen in no-flags verhaal: {nd_tag}")
            print(f"  With: {len(verhaal)} | Without: {len(v_nd)} | Diff: {len(verhaal) - len(v_nd)}")
        print()

    print("=" * 100)
    print("CRITICAL FINDING: BACKTEST BUG CHECK")
    print("=" * 100)
    print()
    print("backtest_v4.py calls get_werkbon_keten(werkbon_key) WITHOUT include flags.")
    print("VerbeterdeVerhaalBuilder never sees oplossingen or kosten details")
    print()

    test_key = next((k for k in code_to_key.values() if k is not None), None)
    if test_key:
        kw = data_service.get_werkbon_keten(test_key, include_kosten_details=True, include_oplossingen=True, include_opvolgingen=True)
        kwo = data_service.get_werkbon_keten(test_key)
        if kw and kwo:
            vw = builder.build_verhaal(kw)
            vwo = builder.build_verhaal(kwo)
            ow = vw.count("WAT HEEFT DE MONTEUR GEDAAN?")
            owo = vwo.count("WAT HEEFT DE MONTEUR GEDAAN?")
            print(f"Verification werkbon_key={test_key}:")
            print(f"  With flags: {ow} Oplossingen, {len(vw)} chars")
            print(f"  Without flags: {owo} Oplossingen, {len(vwo)} chars")


if __name__ == "__main__":
    main()