import sys
sys.path.insert(0, 'src')
from services.parquet_data_service import ParquetDataService
from typing import List

class VerbeterdeVerhaalBuilder:
    """Build verhaal met oplossingen EERST."""

    def build_verhaal(self, keten) -> str:
        """Build complete verhaal from werkbon keten."""
        lines = []

        if not keten or not keten.werkbonnen:
            return "Geen werkbondata beschikbaar."

        for wb_idx, wb in enumerate(keten.werkbonnen):
            # Hoofdwerkbon header
            if wb.is_hoofdwerkbon:
                lines.append(f"📋 WERKBON: {wb.werkbon_nummer}")
                lines.append(f"📅 Melddatum: {wb.melddatum or 'Onbekend'}")
                if wb.monteur:
                    lines.append(f"👷 Monteur: {wb.monteur}")
                lines.append("")
            else:
                lines.append(f"🔗 VERVOLGBON {wb_idx}: {wb.werkbon_nummer}")
                lines.append("")

            # Paragrafen
            for p_idx, p in enumerate(wb.paragrafen):
                lines.append(f"--- PARAGRAAF {p_idx+1}: {p.naam} ---")
                lines.append(f"- ⚙️ Type: {p.type}")

                # ⭐ NIEUW: Factureerwijze toevoegen
                if p.factureerwijze:
                    lines.append(f"- ⚠️ Factureerwijze: {p.factureerwijze}")

                # ⭐ OPLOSSINGEN EERST (meest betrouwbaar)
                if p.oplossingen:
                    lines.append("")
                    lines.append("💡 WAT HEEFT DE MONTEUR GEDAAN? (Oplossingen)")
                    for opl in p.oplossingen:
                        if opl.oplossing:
                            lines.append(f"   {opl.oplossing}")
                        if opl.oplossing_uitgebreid and opl.oplossing_uitgebreid.strip() and opl.oplossing_uitgebreid != opl.oplossing:
                            lines.append(f"   Uitgebreid: {opl.oplossing_uitgebreid}")
                    lines.append("")

                # Storing + Oorzaak
                if p.storing:
                    lines.append(f"- 🔴 Storing: {p.storing}")
                if p.oorzaak:
                    lines.append(f"- 🔎 Oorzaak: {p.oorzaak}")

                lines.append("")

        return "\n".join(lines)

service = ParquetDataService('data')

# Haal werkbon 2999714 op
keten = service.get_werkbon_keten(
    2999714,
    include_kosten_details=True,
    include_oplossingen=True,
    include_opvolgingen=True
)

if not keten:
    print('Werkbon niet gevonden')
else:
    builder = VerbeterdeVerhaalBuilder()
    verhaal = builder.build_verhaal(keten)

    with open('verhaal_2999714.txt', 'w', encoding='utf-8') as f:
        f.write(verhaal)

    print("Verhaal opgeslagen in verhaal_2999714.txt")
    print()
    print(verhaal)
