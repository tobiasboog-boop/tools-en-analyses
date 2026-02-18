"""
Hoofdscript voor extractie van Zenith Security Blobvelden

Dit script extraheert alle relevante blobvelden en combineert ze
tot een dataset die gebruikt kan worden voor analyse en het semantisch model.
"""

import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
import sys

# Importeer de parsers
from rtf_parser import parse_rtf_file, batch_parse_rtf_files
from xml_parser import parse_uurregels_file, batch_parse_uurregels, summarize_uurregels


# Configuratie
BASE_PATH = Path(r"C:\Users\tobia\OneDrive - Notifica B.V\Documenten - Sharepoint Notifica intern\106. Development\GRIP\AI\1229")

# Relevante blobveld locaties
BLOBVELD_CONFIG = {
    "monteur_notitie": {
        "path": BASE_PATH / "AT_MWBSESS",
        "pattern": "*.NOTITIE.txt",
        "type": "rtf",
        "beschrijving": "Notities van monteurs over uitgevoerde werkzaamheden"
    },
    "storing_melding": {
        "path": BASE_PATH / "AT_UITVBEST",
        "pattern": "*.TEKST.txt",
        "type": "rtf",
        "beschrijving": "Storingsmeldingen en werkbeschrijvingen"
    },
    "werk_context": {
        "path": BASE_PATH / "AT_WERK",
        "pattern": "*.GC_INFORMATIE.txt",
        "type": "rtf",
        "beschrijving": "Casebeschrijvingen en werkbon-context"
    },
    "uren_registratie": {
        "path": BASE_PATH / "AT_MWBSESS",
        "pattern": "*.INGELEVERDE_URENREGELS.txt",
        "type": "xml",
        "beschrijving": "Gestructureerde urenregistratie"
    }
}


@dataclass
class WerkbonBlobData:
    """Gecombineerde blobveld data voor een werkbon."""
    werkbon_id: str
    monteur_notitie: Optional[str] = None
    storing_melding: Optional[str] = None
    werk_context: Optional[str] = None
    uren_samenvatting: Optional[str] = None
    uren_totaal: Optional[float] = None
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())


class BlobveldExtractor:
    """Hoofdclass voor extractie van blobvelden."""

    def __init__(self, base_path: Path = BASE_PATH):
        self.base_path = base_path
        self.data: Dict[str, WerkbonBlobData] = {}

    def extract_rtf_blobveld(self, config_name: str) -> Dict[str, str]:
        """Extraheer RTF blobvelden."""
        config = BLOBVELD_CONFIG[config_name]
        print(f"\n{'='*60}")
        print(f"Extractie: {config['beschrijving']}")
        print(f"Locatie: {config['path']}")
        print(f"Pattern: {config['pattern']}")
        print(f"{'='*60}")

        return batch_parse_rtf_files(config['path'], config['pattern'])

    def extract_xml_blobveld(self, config_name: str):
        """Extraheer XML blobvelden (urenregels)."""
        config = BLOBVELD_CONFIG[config_name]
        print(f"\n{'='*60}")
        print(f"Extractie: {config['beschrijving']}")
        print(f"Locatie: {config['path']}")
        print(f"Pattern: {config['pattern']}")
        print(f"{'='*60}")

        return batch_parse_uurregels(config['path'], config['pattern'])

    def run_extraction(self, sample_size: Optional[int] = None):
        """
        Voer volledige extractie uit.

        Args:
            sample_size: Optioneel - limiteer tot N records per blobveld (voor testing)
        """
        print("\n" + "="*60)
        print("BLOBVELD EXTRACTIE - ZENITH SECURITY (1229)")
        print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        # 1. Extraheer monteur notities
        monteur_notities = self.extract_rtf_blobveld("monteur_notitie")
        for werkbon_id, tekst in monteur_notities.items():
            if werkbon_id not in self.data:
                self.data[werkbon_id] = WerkbonBlobData(werkbon_id=werkbon_id)
            self.data[werkbon_id].monteur_notitie = tekst

        # 2. Extraheer storingsmeldingen
        storing_meldingen = self.extract_rtf_blobveld("storing_melding")
        for werkbon_id, tekst in storing_meldingen.items():
            if werkbon_id not in self.data:
                self.data[werkbon_id] = WerkbonBlobData(werkbon_id=werkbon_id)
            self.data[werkbon_id].storing_melding = tekst

        # 3. Extraheer werk context
        werk_context = self.extract_rtf_blobveld("werk_context")
        for werkbon_id, tekst in werk_context.items():
            if werkbon_id not in self.data:
                self.data[werkbon_id] = WerkbonBlobData(werkbon_id=werkbon_id)
            self.data[werkbon_id].werk_context = tekst

        # 4. Extraheer urenregistraties
        uren_registraties = self.extract_xml_blobveld("uren_registratie")
        for werkbon_id, registratie in uren_registraties.items():
            if werkbon_id not in self.data:
                self.data[werkbon_id] = WerkbonBlobData(werkbon_id=werkbon_id)
            self.data[werkbon_id].uren_samenvatting = summarize_uurregels(registratie)
            self.data[werkbon_id].uren_totaal = registratie.totaal_uren

        print("\n" + "="*60)
        print("EXTRACTIE VOLTOOID")
        print(f"Totaal unieke werkbon IDs: {len(self.data)}")
        print("="*60)

        # Statistieken
        stats = self.get_statistics()
        print("\nStatistieken per blobveld:")
        for field, count in stats.items():
            print(f"  - {field}: {count} records")

    def get_statistics(self) -> Dict[str, int]:
        """Bereken statistieken over de geëxtraheerde data."""
        return {
            "monteur_notitie": sum(1 for d in self.data.values() if d.monteur_notitie),
            "storing_melding": sum(1 for d in self.data.values() if d.storing_melding),
            "werk_context": sum(1 for d in self.data.values() if d.werk_context),
            "uren_registratie": sum(1 for d in self.data.values() if d.uren_samenvatting),
            "totaal_werkbonnen": len(self.data)
        }

    def export_to_json(self, output_path: Path):
        """Exporteer data naar JSON."""
        output = {
            "metadata": {
                "klant": "Zenith Security",
                "klant_id": "1229",
                "extracted_at": datetime.now().isoformat(),
                "total_records": len(self.data),
                "statistics": self.get_statistics()
            },
            "werkbonnen": {
                werkbon_id: asdict(data)
                for werkbon_id, data in self.data.items()
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\nJSON export: {output_path}")
        print(f"  Bestandsgrootte: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

    def export_to_csv(self, output_path: Path):
        """Exporteer data naar CSV."""
        fieldnames = [
            'werkbon_id',
            'monteur_notitie',
            'storing_melding',
            'werk_context',
            'uren_samenvatting',
            'uren_totaal',
            'extracted_at'
        ]

        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for werkbon_id, data in self.data.items():
                row = asdict(data)
                # Trunceer lange teksten voor CSV leesbaarheid
                for field in ['monteur_notitie', 'storing_melding', 'werk_context']:
                    if row[field] and len(row[field]) > 500:
                        row[field] = row[field][:497] + "..."
                writer.writerow(row)

        print(f"\nCSV export: {output_path}")
        print(f"  Bestandsgrootte: {output_path.stat().st_size / 1024:.2f} KB")

    def get_sample(self, n: int = 10) -> List[WerkbonBlobData]:
        """Haal een sample van N werkbonnen met data."""
        # Prioriteer werkbonnen die meerdere velden hebben ingevuld
        def completeness_score(data: WerkbonBlobData) -> int:
            score = 0
            if data.monteur_notitie:
                score += 1
            if data.storing_melding:
                score += 1
            if data.werk_context:
                score += 1
            if data.uren_samenvatting:
                score += 1
            return score

        sorted_data = sorted(
            self.data.values(),
            key=completeness_score,
            reverse=True
        )

        return sorted_data[:n]


def main():
    """Hoofdfunctie voor command-line gebruik."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extraheer blobvelden voor Zenith Security werkbonnen"
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path(__file__).parent.parent / 'output',
        help='Output directory voor exports'
    )
    parser.add_argument(
        '--sample',
        type=int,
        help='Limiteer extractie tot N records per blobveld (voor testing)'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'csv', 'both'],
        default='both',
        help='Export formaat'
    )

    args = parser.parse_args()

    # Maak output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Run extractie
    extractor = BlobveldExtractor()
    extractor.run_extraction(sample_size=args.sample)

    # Export
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if args.format in ['json', 'both']:
        json_path = args.output_dir / f'blobvelden_zenith_{timestamp}.json'
        extractor.export_to_json(json_path)

    if args.format in ['csv', 'both']:
        csv_path = args.output_dir / f'blobvelden_zenith_{timestamp}.csv'
        extractor.export_to_csv(csv_path)

    # Toon sample
    print("\n" + "="*60)
    print("SAMPLE WERKBONNEN (meest complete records)")
    print("="*60)

    for i, sample in enumerate(extractor.get_sample(5), 1):
        print(f"\n--- Werkbon {sample.werkbon_id} ---")
        if sample.monteur_notitie:
            print(f"  Notitie: {sample.monteur_notitie[:100]}...")
        if sample.storing_melding:
            print(f"  Storing: {sample.storing_melding[:100]}...")
        if sample.werk_context:
            print(f"  Context: {sample.werk_context[:100]}...")
        if sample.uren_totaal:
            print(f"  Uren: {sample.uren_totaal:.1f}")


if __name__ == "__main__":
    main()
