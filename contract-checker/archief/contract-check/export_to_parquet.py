#!/usr/bin/env python3
"""Export werkbonnen data naar Parquet voor de publieke versie.

Dit script exporteert een subset van historische werkbonnen met alle
gerelateerde tabellen naar Parquet bestanden. Deze data kan dan gebruikt
worden in de publieke versie zonder database connectie.

Gebruik:
    python export_to_parquet.py --limit 200 --output ../contract-check-public/data
"""
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Set

import pandas as pd
from sqlalchemy import text

from src.models.database import SessionLocal


def export_werkbonnen_to_parquet(
    limit: int = 200,
    output_dir: str = "../contract-check-public/data",
    debiteur_codes: List[str] = None
):
    """Export werkbonnen en gerelateerde data naar Parquet.

    Args:
        limit: Maximum aantal hoofdwerkbonnen om te exporteren
        output_dir: Output directory voor Parquet bestanden
        debiteur_codes: Optioneel: filter op specifieke debiteuren
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()

    try:
        print(f"Start export van max {limit} historische werkbonnen...")

        # ============================================
        # STAP 1: Haal hoofdwerkbonnen op (Historisch)
        # ============================================
        print("\n[1/7] Hoofdwerkbonnen ophalen...")

        # Filter voor debiteuren (de 3 WVC debiteuren)
        if debiteur_codes is None:
            debiteur_codes = ["007453", "177460", "005102"]

        debiteur_filter = " OR ".join([f"w.\"Debiteur\" LIKE '{code} - %'" for code in debiteur_codes])

        query_hoofdwerkbonnen = text(f"""
            SELECT DISTINCT
                w."HoofdwerkbonDocumentKey" as hoofdwerkbon_key
            FROM werkbonnen."Werkbonnen" w
            WHERE ({debiteur_filter})
              AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
              AND TRIM(w."Status") = 'Uitgevoerd'
              AND TRIM(w."Documentstatus") = 'Historisch'
            ORDER BY w."HoofdwerkbonDocumentKey" DESC
            LIMIT :limit
        """)

        result = db.execute(query_hoofdwerkbonnen, {"limit": limit})
        hoofdwerkbon_keys = [row[0] for row in result.fetchall()]

        print(f"   Gevonden: {len(hoofdwerkbon_keys)} hoofdwerkbonnen")

        if not hoofdwerkbon_keys:
            print("Geen werkbonnen gevonden!")
            return

        # Maak IN clause
        keys_placeholder = ", ".join([str(k) for k in hoofdwerkbon_keys])

        # ============================================
        # STAP 2: Alle werkbonnen in ketens ophalen
        # ============================================
        print("\n[2/7] Werkbonnen (incl. vervolgbonnen) ophalen...")

        query_werkbonnen = text(f"""
            SELECT
                w."WerkbonDocumentKey" as werkbon_key,
                w."HoofdwerkbonDocumentKey" as hoofdwerkbon_key,
                w."ParentWerkbonDocumentKey" as parent_werkbon_key,
                w."Werkbon" as werkbon,
                w."Type" as type,
                w."Status" as status,
                w."Documentstatus" as documentstatus,
                w."Administratieve fase" as administratieve_fase,
                w."Klant" as klant,
                w."Debiteur" as debiteur,
                w."DebiteurRelatieKey" as debiteur_relatie_key,
                w."Postcode" as postcode,
                w."Plaats" as plaats,
                w."MeldDatum" as melddatum,
                w."MeldTijd" as meldtijd,
                w."AfspraakDatum" as afspraakdatum,
                w."Opleverdatum" as opleverdatum,
                w."Monteur" as monteur,
                w."Niveau" as niveau,
                w."Soort" as soort,
                d."Aanmaakdatum" as aanmaakdatum
            FROM werkbonnen."Werkbonnen" w
            LEFT JOIN stam."Documenten" d ON d."DocumentKey" = w."WerkbonDocumentKey"
            WHERE w."HoofdwerkbonDocumentKey" IN ({keys_placeholder})
            ORDER BY w."HoofdwerkbonDocumentKey", w."Niveau"
        """)

        result = db.execute(query_werkbonnen)
        werkbonnen_data = result.fetchall()
        werkbonnen_columns = list(result.keys())

        df_werkbonnen = pd.DataFrame(werkbonnen_data, columns=werkbonnen_columns)
        print(f"   Gevonden: {len(df_werkbonnen)} werkbonnen (hoofd + vervolg)")

        # Verzamel alle werkbon keys voor volgende queries
        alle_werkbon_keys = df_werkbonnen["werkbon_key"].tolist()
        werkbon_keys_str = ", ".join([str(k) for k in alle_werkbon_keys])

        # ============================================
        # STAP 3: Werkbonparagrafen ophalen
        # ============================================
        print("\n[3/7] Werkbonparagrafen ophalen...")

        query_paragrafen = text(f"""
            SELECT
                p."WerkbonparagraafKey" as werkbonparagraaf_key,
                p."WerkbonDocumentKey" as werkbon_key,
                p."Werkbonparagraaf" as naam,
                p."Type" as type,
                p."Factureerwijze" as factureerwijze,
                p."Storing" as storing,
                p."Oorzaak" as oorzaak,
                p."Uitvoeringstatus" as uitvoeringstatus,
                p."Plandatum" as plandatum,
                p."Uitgevoerd op" as uitgevoerd_op,
                p."TijdstipUitgevoerd" as tijdstip_uitgevoerd
            FROM werkbonnen."Werkbonparagrafen" p
            WHERE p."WerkbonDocumentKey" IN ({werkbon_keys_str})
            ORDER BY p."WerkbonDocumentKey", p."WerkbonparagraafKey"
        """)

        result = db.execute(query_paragrafen)
        paragrafen_data = result.fetchall()
        paragrafen_columns = list(result.keys())

        df_paragrafen = pd.DataFrame(paragrafen_data, columns=paragrafen_columns)
        print(f"   Gevonden: {len(df_paragrafen)} paragrafen")

        # Verzamel alle paragraaf keys
        alle_paragraaf_keys = df_paragrafen["werkbonparagraaf_key"].tolist()
        paragraaf_keys_str = ", ".join([str(k) for k in alle_paragraaf_keys])

        # ============================================
        # STAP 4: Kosten ophalen
        # ============================================
        print("\n[4/7] Kosten ophalen...")

        if alle_paragraaf_keys:
            query_kosten = text(f"""
                SELECT
                    k."RegelKey" as kosten_key,
                    k."WerkbonparagraafKey" as werkbonparagraaf_key,
                    k."Omschrijving" as omschrijving,
                    k."Aantal" as aantal,
                    k."Verrekenprijs" as verrekenprijs,
                    k."Kostprijs" as kostprijs,
                    k."Kostenbron" as kostenbron,
                    k."Categorie" as categorie,
                    k."Factureerstatus" as factureerstatus,
                    k."Kostenstatus" as kostenstatus,
                    k."Boekdatum" as boekdatum,
                    k."Arbeidregel Ja / Nee" as is_arbeid,
                    k."Pakbon Status" as pakbon_status,
                    m."Medewerker" as medewerker,
                    t."Taak" as taak
                FROM financieel."Kosten" k
                LEFT JOIN stam."Medewerkers" m ON k."MedewerkerKey" = m."MedewerkerKey"
                LEFT JOIN uren."Taken" t ON k."TaakKey" = t."TaakKey"
                WHERE k."WerkbonparagraafKey" IN ({paragraaf_keys_str})
                ORDER BY k."WerkbonparagraafKey", k."Boekdatum" DESC
            """)

            result = db.execute(query_kosten)
            kosten_data = result.fetchall()
            kosten_columns = list(result.keys())

            df_kosten = pd.DataFrame(kosten_data, columns=kosten_columns)
        else:
            df_kosten = pd.DataFrame()

        print(f"   Gevonden: {len(df_kosten)} kostenregels")

        # ============================================
        # STAP 5: Opbrengsten ophalen
        # ============================================
        print("\n[5/7] Opbrengsten ophalen...")

        if alle_paragraaf_keys:
            query_opbrengsten = text(f"""
                SELECT
                    o."OpbrengstRegelKey" as opbrengst_key,
                    o."WerkbonParagraafKey" as werkbonparagraaf_key,
                    o."Omschrijving" as omschrijving,
                    o."Bedrag" as bedrag,
                    o."Kostensoort" as kostensoort,
                    o."Tarief omschrijving" as tarief,
                    o."Factuurdatum" as factuurdatum
                FROM financieel."Opbrengsten" o
                WHERE o."WerkbonParagraafKey" IN ({paragraaf_keys_str})
                ORDER BY o."WerkbonParagraafKey", o."OpbrengstRegelKey"
            """)

            result = db.execute(query_opbrengsten)
            opbrengsten_data = result.fetchall()
            opbrengsten_columns = list(result.keys())

            df_opbrengsten = pd.DataFrame(opbrengsten_data, columns=opbrengsten_columns)
        else:
            df_opbrengsten = pd.DataFrame()

        print(f"   Gevonden: {len(df_opbrengsten)} opbrengstenregels")

        # ============================================
        # STAP 6: Oplossingen ophalen
        # ============================================
        print("\n[6/7] Oplossingen ophalen...")

        if alle_paragraaf_keys:
            query_oplossingen = text(f"""
                SELECT
                    o."WerkbonparagaafKey" as werkbonparagraaf_key,
                    o."Oplossing" as oplossing,
                    o."Oplossing uitgebreid" as oplossing_uitgebreid,
                    o."Aanmaakdatum" as aanmaakdatum
                FROM werkbonnen."Werkbon oplossingen" o
                WHERE o."WerkbonparagaafKey" IN ({paragraaf_keys_str})
                ORDER BY o."WerkbonparagaafKey", o."Aanmaakdatum" DESC
            """)

            result = db.execute(query_oplossingen)
            oplossingen_data = result.fetchall()
            oplossingen_columns = list(result.keys())

            df_oplossingen = pd.DataFrame(oplossingen_data, columns=oplossingen_columns)
        else:
            df_oplossingen = pd.DataFrame()

        print(f"   Gevonden: {len(df_oplossingen)} oplossingen")

        # ============================================
        # STAP 7: Opvolgingen ophalen
        # ============================================
        print("\n[7/7] Opvolgingen ophalen...")

        if alle_paragraaf_keys:
            query_opvolgingen = text(f"""
                SELECT
                    op."WerkbonparagraafKey" as werkbonparagraaf_key,
                    op."Opvolgsoort" as opvolgsoort,
                    op."Beschrijving" as beschrijving,
                    op."Status" as status,
                    op."Aanmaakdatum" as aanmaakdatum,
                    op."Laatste wijzigdatum" as laatste_wijzigdatum
                FROM werkbonnen."Werkbon opvolgingen" op
                WHERE op."WerkbonparagraafKey" IN ({paragraaf_keys_str})
                ORDER BY op."WerkbonparagraafKey", op."Aanmaakdatum" DESC
            """)

            result = db.execute(query_opvolgingen)
            opvolgingen_data = result.fetchall()
            opvolgingen_columns = list(result.keys())

            df_opvolgingen = pd.DataFrame(opvolgingen_data, columns=opvolgingen_columns)
        else:
            df_opvolgingen = pd.DataFrame()

        print(f"   Gevonden: {len(df_opvolgingen)} opvolgingen")

        # ============================================
        # SCHRIJF NAAR PARQUET
        # ============================================
        print("\n" + "="*50)
        print("Schrijven naar Parquet...")

        # Werkbonnen
        werkbonnen_file = output_path / "werkbonnen.parquet"
        df_werkbonnen.to_parquet(werkbonnen_file, index=False)
        print(f"   ✓ {werkbonnen_file.name}: {len(df_werkbonnen)} rijen")

        # Paragrafen
        paragrafen_file = output_path / "werkbonparagrafen.parquet"
        df_paragrafen.to_parquet(paragrafen_file, index=False)
        print(f"   ✓ {paragrafen_file.name}: {len(df_paragrafen)} rijen")

        # Kosten
        kosten_file = output_path / "kosten.parquet"
        df_kosten.to_parquet(kosten_file, index=False)
        print(f"   ✓ {kosten_file.name}: {len(df_kosten)} rijen")

        # Opbrengsten
        opbrengsten_file = output_path / "opbrengsten.parquet"
        df_opbrengsten.to_parquet(opbrengsten_file, index=False)
        print(f"   ✓ {opbrengsten_file.name}: {len(df_opbrengsten)} rijen")

        # Oplossingen
        oplossingen_file = output_path / "oplossingen.parquet"
        df_oplossingen.to_parquet(oplossingen_file, index=False)
        print(f"   ✓ {oplossingen_file.name}: {len(df_oplossingen)} rijen")

        # Opvolgingen
        opvolgingen_file = output_path / "opvolgingen.parquet"
        df_opvolgingen.to_parquet(opvolgingen_file, index=False)
        print(f"   ✓ {opvolgingen_file.name}: {len(df_opvolgingen)} rijen")

        # ============================================
        # METADATA / SAMENVATTING
        # ============================================
        metadata = {
            "export_timestamp": datetime.now().isoformat(),
            "aantal_hoofdwerkbonnen": len(hoofdwerkbon_keys),
            "aantal_werkbonnen": len(df_werkbonnen),
            "aantal_paragrafen": len(df_paragrafen),
            "aantal_kosten": len(df_kosten),
            "aantal_opbrengsten": len(df_opbrengsten),
            "aantal_oplossingen": len(df_oplossingen),
            "aantal_opvolgingen": len(df_opvolgingen),
            "debiteur_codes": debiteur_codes,
            "status_filter": "Uitgevoerd + Historisch"
        }

        import json
        metadata_file = output_path / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"   ✓ {metadata_file.name}")

        print("\n" + "="*50)
        print("✅ Export voltooid!")
        print(f"   Output: {output_path.absolute()}")
        print(f"   Totaal: {len(hoofdwerkbon_keys)} hoofdwerkbonnen met alle gerelateerde data")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export werkbonnen naar Parquet")
    parser.add_argument("--limit", type=int, default=200, help="Max aantal hoofdwerkbonnen")
    parser.add_argument("--output", type=str, default="../contract-check-public/data",
                        help="Output directory")

    args = parser.parse_args()

    export_werkbonnen_to_parquet(limit=args.limit, output_dir=args.output)
