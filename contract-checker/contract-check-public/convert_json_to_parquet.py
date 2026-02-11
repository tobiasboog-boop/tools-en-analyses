#!/usr/bin/env python3
"""Converteer JSON werkbonnen exports naar Parquet bestanden."""
import json
from pathlib import Path
from datetime import datetime

import pandas as pd


def convert_json_to_parquet(data_dir: str = "data"):
    """Converteer alle JSON bestanden in data_dir naar Parquet."""
    data_path = Path(data_dir)

    # Verzamel alle JSON bestanden
    json_files = list(data_path.glob("werkbonnen_*.json"))

    if not json_files:
        print("Geen JSON bestanden gevonden!")
        return

    print(f"Gevonden: {len(json_files)} JSON bestanden")

    # Verzamel alle data
    all_werkbonnen = []
    all_paragrafen = []
    all_kosten = []
    all_opbrengsten = []
    all_oplossingen = []
    all_opvolgingen = []
    all_metadata = []

    for json_file in json_files:
        print(f"\nVerwerken: {json_file.name}")

        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        metadata = data.get("metadata", {})
        all_metadata.append(metadata)

        werkbonnen = data.get("werkbonnen", [])
        print(f"  {len(werkbonnen)} werkbonketens")

        for wb_entry in werkbonnen:
            keten = wb_entry.get("keten", {})
            hoofdwerkbon_key = keten.get("hoofdwerkbon_key")

            for wb in keten.get("werkbonnen", []):
                # Werkbon record
                all_werkbonnen.append({
                    "werkbon_key": wb.get("werkbon_key"),
                    "hoofdwerkbon_key": hoofdwerkbon_key,
                    "werkbon": wb.get("werkbon_nummer"),
                    "type": wb.get("type"),
                    "status": wb.get("status"),
                    "documentstatus": wb.get("documentstatus"),
                    "administratieve_fase": wb.get("administratieve_fase"),
                    "klant": wb.get("klant"),
                    "debiteur": wb.get("debiteur"),
                    "debiteur_relatie_key": keten.get("relatie_key"),
                    "postcode": wb.get("postcode"),
                    "plaats": wb.get("plaats"),
                    "melddatum": wb.get("melddatum"),
                    "meldtijd": wb.get("meldtijd"),
                    "afspraakdatum": wb.get("afspraakdatum"),
                    "opleverdatum": wb.get("opleverdatum"),
                    "monteur": wb.get("monteur"),
                    "niveau": wb.get("niveau"),
                    "soort": wb.get("soort"),
                    "aanmaakdatum": wb.get("melddatum"),  # Gebruik melddatum als fallback
                })

                for p in wb.get("paragrafen", []):
                    paragraaf_key = p.get("werkbonparagraaf_key")

                    # Paragraaf record
                    all_paragrafen.append({
                        "werkbonparagraaf_key": paragraaf_key,
                        "werkbon_key": wb.get("werkbon_key"),
                        "naam": p.get("naam"),
                        "type": p.get("type"),
                        "factureerwijze": p.get("factureerwijze"),
                        "storing": p.get("storing"),
                        "oorzaak": p.get("oorzaak"),
                        "uitvoeringstatus": p.get("uitvoeringstatus"),
                        "plandatum": p.get("plandatum"),
                        "uitgevoerd_op": p.get("uitgevoerd_op"),
                        "tijdstip_uitgevoerd": p.get("tijdstip_uitgevoerd"),
                    })

                    # Kosten records
                    for k in p.get("kosten", []):
                        all_kosten.append({
                            "werkbonparagraaf_key": paragraaf_key,
                            "omschrijving": k.get("omschrijving"),
                            "aantal": k.get("aantal"),
                            "verrekenprijs": k.get("verrekenprijs"),
                            "kostprijs": k.get("kostprijs"),
                            "kostenbron": k.get("kostenbron"),
                            "categorie": k.get("categorie"),
                            "factureerstatus": k.get("factureerstatus"),
                            "kostenstatus": k.get("kostenstatus"),
                            "boekdatum": k.get("boekdatum"),
                            "is_arbeid": "Ja" if k.get("categorie") == "Arbeid" else "Nee",
                            "pakbon_status": k.get("pakbon_status"),
                            "medewerker": k.get("medewerker"),
                            "taak": k.get("taak"),
                        })

                    # Opbrengsten records
                    for o in p.get("opbrengsten", []):
                        all_opbrengsten.append({
                            "werkbonparagraaf_key": paragraaf_key,
                            "omschrijving": o.get("omschrijving"),
                            "bedrag": o.get("bedrag"),
                            "kostensoort": o.get("kostensoort"),
                            "tarief": o.get("tarief"),
                            "factuurdatum": o.get("factuurdatum"),
                        })

                    # Oplossingen records
                    for opl in p.get("oplossingen", []):
                        all_oplossingen.append({
                            "werkbonparagraaf_key": paragraaf_key,
                            "oplossing": opl.get("oplossing"),
                            "oplossing_uitgebreid": opl.get("oplossing_uitgebreid"),
                            "aanmaakdatum": opl.get("aanmaakdatum"),
                        })

                    # Opvolgingen records
                    for opv in p.get("opvolgingen", []):
                        all_opvolgingen.append({
                            "werkbonparagraaf_key": paragraaf_key,
                            "opvolgsoort": opv.get("opvolgsoort"),
                            "beschrijving": opv.get("beschrijving"),
                            "status": opv.get("status"),
                            "aanmaakdatum": opv.get("aanmaakdatum"),
                            "laatste_wijzigdatum": opv.get("laatste_wijzigdatum"),
                        })

    # Maak DataFrames
    print("\n" + "="*50)
    print("Converteren naar Parquet...")

    df_werkbonnen = pd.DataFrame(all_werkbonnen)
    df_paragrafen = pd.DataFrame(all_paragrafen)
    df_kosten = pd.DataFrame(all_kosten) if all_kosten else pd.DataFrame()
    df_opbrengsten = pd.DataFrame(all_opbrengsten) if all_opbrengsten else pd.DataFrame()
    df_oplossingen = pd.DataFrame(all_oplossingen) if all_oplossingen else pd.DataFrame()
    df_opvolgingen = pd.DataFrame(all_opvolgingen) if all_opvolgingen else pd.DataFrame()

    # Schrijf Parquet bestanden
    df_werkbonnen.to_parquet(data_path / "werkbonnen.parquet", index=False)
    print(f"  werkbonnen.parquet: {len(df_werkbonnen)} rijen")

    df_paragrafen.to_parquet(data_path / "werkbonparagrafen.parquet", index=False)
    print(f"  werkbonparagrafen.parquet: {len(df_paragrafen)} rijen")

    df_kosten.to_parquet(data_path / "kosten.parquet", index=False)
    print(f"  kosten.parquet: {len(df_kosten)} rijen")

    df_opbrengsten.to_parquet(data_path / "opbrengsten.parquet", index=False)
    print(f"  opbrengsten.parquet: {len(df_opbrengsten)} rijen")

    df_oplossingen.to_parquet(data_path / "oplossingen.parquet", index=False)
    print(f"  oplossingen.parquet: {len(df_oplossingen)} rijen")

    df_opvolgingen.to_parquet(data_path / "opvolgingen.parquet", index=False)
    print(f"  opvolgingen.parquet: {len(df_opvolgingen)} rijen")

    # Maak metadata
    # Tel unieke hoofdwerkbonnen
    hoofdwerkbon_keys = set(df_werkbonnen[
        df_werkbonnen["werkbon_key"] == df_werkbonnen["hoofdwerkbon_key"]
    ]["werkbon_key"].tolist())

    # Verzamel debiteur codes
    debiteur_codes = [m.get("debiteur_code") for m in all_metadata if m.get("debiteur_code")]

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
        "status_filter": "Uitgevoerd + Historisch",
        "bron_bestanden": [f.name for f in json_files],
    }

    with open(data_path / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  metadata.json")

    print("\n" + "="*50)
    print(f"Conversie voltooid!")
    print(f"  {len(hoofdwerkbon_keys)} hoofdwerkbonnen")
    print(f"  {len(df_werkbonnen)} werkbonnen totaal")
    print(f"  Debiteuren: {', '.join(debiteur_codes)}")


if __name__ == "__main__":
    convert_json_to_parquet()
