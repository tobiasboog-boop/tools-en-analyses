"""
XML Parser voor Zenith Security Urenregels

Dit script parsed de INGELEVERDE_URENREGELS.txt bestanden
die XML-gestructureerde urenregistratie bevatten.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
import re


@dataclass
class Uurregel:
    """Dataclass voor een enkele uurregel."""
    datum: Optional[str] = None
    begintijd: Optional[str] = None
    eindtijd: Optional[str] = None
    aantal: Optional[float] = None
    taakcode: Optional[str] = None
    regelomschrijving: Optional[str] = None
    tariefsoort: Optional[str] = None
    projectcode: Optional[str] = None
    bestparcode: Optional[str] = None
    bestpar_omschrijving: Optional[str] = None


@dataclass
class UrenRegistratie:
    """Dataclass voor complete urenregistratie van een werkbon."""
    werkbon_id: str
    uurregels: List[Uurregel]
    totaal_uren: float = 0.0

    def __post_init__(self):
        self.totaal_uren = sum(
            regel.aantal or 0 for regel in self.uurregels
        )


def clean_xml_content(content: str) -> str:
    """
    Schoon XML content op voor parsing.
    Sommige bestanden hebben RTF wrapper of andere vervuiling.
    """
    # Verwijder eventuele RTF wrapper
    if '{\\rtf' in content:
        # Probeer XML te extraheren uit RTF
        xml_match = re.search(r'<\?xml.*?\?>\s*<.*?>', content, re.DOTALL)
        if xml_match:
            # Zoek de complete XML structuur
            start = content.find('<?xml')
            if start == -1:
                start = content.find('<Uurregels')
            if start == -1:
                start = content.find('<uurregels')
            if start >= 0:
                content = content[start:]
                # Zoek het einde
                end_tags = ['</Uurregels>', '</uurregels>', '</root>']
                for end_tag in end_tags:
                    end = content.find(end_tag)
                    if end >= 0:
                        content = content[:end + len(end_tag)]
                        break

    # Verwijder null bytes en andere ongeldige karakters
    content = content.replace('\x00', '')

    return content.strip()


def parse_uurregels_xml(xml_content: str) -> List[Uurregel]:
    """
    Parse XML content met uurregels.

    Args:
        xml_content: XML string met uurregels

    Returns:
        Lijst van Uurregel objecten
    """
    uurregels = []

    try:
        xml_content = clean_xml_content(xml_content)

        if not xml_content:
            return uurregels

        # Parse XML
        root = ET.fromstring(xml_content)

        # Zoek uurregels (case-insensitive tags)
        regel_tags = ['Uurregel', 'uurregel', 'Uuregel', 'uuregel', 'regel', 'Regel']

        for tag in regel_tags:
            for regel_elem in root.iter(tag):
                regel = Uurregel()

                # Map van mogelijke tag namen naar velden
                field_mapping = {
                    'datum': ['Datum', 'datum', 'Date', 'date'],
                    'begintijd': ['Begintijd', 'begintijd', 'BeginTijd', 'StartTime'],
                    'eindtijd': ['Eindtijd', 'eindtijd', 'EindTijd', 'EndTime'],
                    'aantal': ['Aantal', 'aantal', 'Hours', 'hours', 'Uren', 'uren'],
                    'taakcode': ['Taakcode', 'taakcode', 'TaakCode', 'TaskCode'],
                    'regelomschrijving': ['Regelomschrijving', 'regelomschrijving', 'Omschrijving', 'omschrijving', 'Description'],
                    'tariefsoort': ['Tariefsoort', 'tariefsoort', 'TariefSoort', 'RateType'],
                    'projectcode': ['Projectcode', 'projectcode', 'ProjectCode', 'Project'],
                    'bestparcode': ['Bestparcode', 'bestparcode', 'BestparCode', 'BESTPARCODE'],
                    'bestpar_omschrijving': ['BestparOmschrijving', 'bestpar_omschrijving', 'Bestparomschrijving']
                }

                for field, possible_tags in field_mapping.items():
                    for possible_tag in possible_tags:
                        elem = regel_elem.find(possible_tag)
                        if elem is not None and elem.text:
                            value = elem.text.strip()
                            if field == 'aantal':
                                try:
                                    value = float(value.replace(',', '.'))
                                except ValueError:
                                    value = 0.0
                            setattr(regel, field, value)
                            break

                uurregels.append(regel)

        # Als geen regels gevonden, probeer alternatieve structuur
        if not uurregels:
            # Sommige bestanden hebben een plattere structuur
            for child in root:
                if any(tag.lower() in child.tag.lower() for tag in ['uur', 'regel', 'row']):
                    regel = Uurregel()
                    for elem in child:
                        tag_lower = elem.tag.lower()
                        if 'datum' in tag_lower or 'date' in tag_lower:
                            regel.datum = elem.text
                        elif 'begin' in tag_lower or 'start' in tag_lower:
                            regel.begintijd = elem.text
                        elif 'eind' in tag_lower or 'end' in tag_lower:
                            regel.eindtijd = elem.text
                        elif 'aantal' in tag_lower or 'hour' in tag_lower or 'uren' in tag_lower:
                            try:
                                regel.aantal = float(elem.text.replace(',', '.'))
                            except (ValueError, AttributeError):
                                pass
                        elif 'omschrijving' in tag_lower or 'desc' in tag_lower:
                            regel.regelomschrijving = elem.text
                        elif 'project' in tag_lower:
                            regel.projectcode = elem.text
                        elif 'taak' in tag_lower or 'task' in tag_lower:
                            regel.taakcode = elem.text
                    uurregels.append(regel)

    except ET.ParseError as e:
        print(f"XML parse error: {e}")
    except Exception as e:
        print(f"Fout bij verwerken XML: {e}")

    return uurregels


def parse_uurregels_file(file_path: Path) -> Optional[UrenRegistratie]:
    """
    Lees en parse een urenregels bestand.

    Args:
        file_path: Pad naar het urenregels bestand

    Returns:
        UrenRegistratie object of None bij fout
    """
    try:
        # Extraheer werkbon ID uit bestandsnaam
        # Format: [ID].INGELEVERDE_URENREGELS.txt
        werkbon_id = file_path.stem.split('.')[0]

        # Lees bestand met verschillende encodings
        content = None
        for encoding in ['utf-8', 'cp1252', 'latin-1', 'utf-16']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            with open(file_path, 'rb') as f:
                content = f.read().decode('utf-8', errors='replace')

        uurregels = parse_uurregels_xml(content)

        return UrenRegistratie(
            werkbon_id=werkbon_id,
            uurregels=uurregels
        )

    except Exception as e:
        print(f"Fout bij lezen {file_path}: {e}")
        return None


def batch_parse_uurregels(folder_path: Path, pattern: str = "*URENREGELS*.txt") -> Dict[str, UrenRegistratie]:
    """
    Parse alle urenregels bestanden in een map.

    Args:
        folder_path: Pad naar de map
        pattern: Glob pattern voor bestanden

    Returns:
        Dictionary met {werkbon_id: UrenRegistratie}
    """
    results = {}
    folder = Path(folder_path)

    if not folder.exists():
        print(f"Map bestaat niet: {folder_path}")
        return results

    files = list(folder.glob(pattern))
    total = len(files)

    print(f"Verwerken van {total} urenregels bestanden...")

    for i, file_path in enumerate(files, 1):
        if i % 100 == 0:
            print(f"  Voortgang: {i}/{total} ({100*i/total:.1f}%)")

        registratie = parse_uurregels_file(file_path)
        if registratie and registratie.uurregels:
            results[registratie.werkbon_id] = registratie

    print(f"Klaar: {len(results)} bestanden met uurregels verwerkt")
    return results


def summarize_uurregels(registratie: UrenRegistratie) -> str:
    """
    Maak een tekstuele samenvatting van de urenregistratie.

    Args:
        registratie: UrenRegistratie object

    Returns:
        Samenvatting als string
    """
    if not registratie.uurregels:
        return "Geen uurregels gevonden"

    lines = [f"Totaal: {registratie.totaal_uren:.1f} uur"]

    # Groepeer per project
    projects = {}
    for regel in registratie.uurregels:
        project = regel.projectcode or "Onbekend"
        if project not in projects:
            projects[project] = []
        projects[project].append(regel)

    for project, regels in projects.items():
        uren = sum(r.aantal or 0 for r in regels)
        lines.append(f"  - {project}: {uren:.1f} uur")

        # Voeg omschrijvingen toe
        omschrijvingen = set(r.regelomschrijving for r in regels if r.regelomschrijving)
        for omschr in list(omschrijvingen)[:3]:  # Max 3 omschrijvingen
            lines.append(f"    * {omschr}")

    return "\n".join(lines)


# Test functie
if __name__ == "__main__":
    # Voorbeeld XML content
    test_xml = """<?xml version="1.0" encoding="utf-8"?>
<Uurregels>
  <Uurregel>
    <Datum>2021-03-15</Datum>
    <Begintijd>08:00</Begintijd>
    <Eindtijd>12:00</Eindtijd>
    <Aantal>4</Aantal>
    <Taakcode>10</Taakcode>
    <Regelomschrijving>Preventiecoach werkzaamheden Amsterdam</Regelomschrijving>
    <Tariefsoort>STD</Tariefsoort>
    <Projectcode>R000002.14</Projectcode>
  </Uurregel>
  <Uurregel>
    <Datum>2021-03-15</Datum>
    <Begintijd>13:00</Begintijd>
    <Eindtijd>17:00</Eindtijd>
    <Aantal>4</Aantal>
    <Taakcode>20</Taakcode>
    <Regelomschrijving>Observatie winkelcentrum</Regelomschrijving>
    <Tariefsoort>STD</Tariefsoort>
    <Projectcode>R000009</Projectcode>
  </Uurregel>
</Uurregels>"""

    print("Test XML parsing:")
    print("-" * 40)

    uurregels = parse_uurregels_xml(test_xml)
    print(f"Gevonden: {len(uurregels)} uurregels")

    for regel in uurregels:
        print(f"\n  Datum: {regel.datum}")
        print(f"  Tijd: {regel.begintijd} - {regel.eindtijd}")
        print(f"  Uren: {regel.aantal}")
        print(f"  Omschrijving: {regel.regelomschrijving}")
        print(f"  Project: {regel.projectcode}")

    print("\n" + "-" * 40)
    print("Samenvatting:")
    registratie = UrenRegistratie(werkbon_id="TEST001", uurregels=uurregels)
    print(summarize_uurregels(registratie))
