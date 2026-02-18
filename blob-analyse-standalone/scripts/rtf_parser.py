"""
RTF Parser voor Zenith Security Blobvelden

Dit script converteert RTF-bestanden naar platte tekst.
Wordt gebruikt voor: NOTITIE.txt, TEKST.txt, GC_INFORMATIE.txt
"""

import re
from pathlib import Path
from typing import Optional


def strip_rtf(rtf_content: str) -> str:
    """
    Converteer RTF content naar platte tekst.

    Args:
        rtf_content: De ruwe RTF string

    Returns:
        Platte tekst zonder RTF opmaak
    """
    if not rtf_content:
        return ""

    # Check of het daadwerkelijk RTF is
    if not rtf_content.strip().startswith('{\\rtf'):
        return rtf_content.strip()

    # Verwijder RTF header en control words
    text = rtf_content

    # Verwijder geneste groepen (fonts, colors, etc.)
    # Dit is een vereenvoudigde parser - complexe RTF kan speciale behandeling nodig hebben

    # Verwijder font tables, color tables, etc.
    text = re.sub(r'\{\\fonttbl[^}]*\}', '', text)
    text = re.sub(r'\{\\colortbl[^}]*\}', '', text)
    text = re.sub(r'\{\\stylesheet[^}]*\}', '', text)
    text = re.sub(r'\{\\info[^}]*\}', '', text)
    text = re.sub(r'\{\\\*\\[^}]*\}', '', text)

    # Vervang speciale RTF karakters
    text = re.sub(r'\\par\s?', '\n', text)  # Paragraph breaks
    text = re.sub(r'\\line\s?', '\n', text)  # Line breaks
    text = re.sub(r'\\tab\s?', '\t', text)  # Tabs
    text = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), text)  # Hex chars

    # Verwijder control words (bijv. \fs17, \lang1043, \f0, etc.)
    text = re.sub(r'\\[a-z]+\d*\s?', '', text)

    # Verwijder backslashes voor speciale karakters
    text = text.replace('\\{', '{')
    text = text.replace('\\}', '}')
    text = text.replace('\\\\', '\\')

    # Verwijder overgebleven accolades
    text = re.sub(r'[{}]', '', text)

    # Opschonen
    text = text.strip()

    # Verwijder meerdere spaties/newlines
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)

    return text


def parse_rtf_file(file_path: Path) -> Optional[str]:
    """
    Lees en parse een RTF bestand.

    Args:
        file_path: Pad naar het RTF bestand

    Returns:
        Geëxtraheerde tekst of None bij fout
    """
    try:
        # Probeer verschillende encodings
        encodings = ['utf-8', 'cp1252', 'latin-1', 'utf-16']

        content = None
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            # Fallback: lees als bytes en decode met errors='replace'
            with open(file_path, 'rb') as f:
                content = f.read().decode('utf-8', errors='replace')

        return strip_rtf(content)

    except Exception as e:
        print(f"Fout bij lezen {file_path}: {e}")
        return None


def batch_parse_rtf_files(folder_path: Path, pattern: str = "*.txt") -> dict:
    """
    Parse alle RTF bestanden in een map.

    Args:
        folder_path: Pad naar de map met RTF bestanden
        pattern: Glob pattern voor bestanden (default: *.txt)

    Returns:
        Dictionary met {bestandsnaam: geëxtraheerde_tekst}
    """
    results = {}
    folder = Path(folder_path)

    if not folder.exists():
        print(f"Map bestaat niet: {folder_path}")
        return results

    files = list(folder.glob(pattern))
    total = len(files)

    print(f"Verwerken van {total} bestanden in {folder_path}...")

    for i, file_path in enumerate(files, 1):
        if i % 1000 == 0:
            print(f"  Voortgang: {i}/{total} ({100*i/total:.1f}%)")

        text = parse_rtf_file(file_path)
        if text:
            # Gebruik bestandsnaam zonder extensie als key
            # Format: [ID].[VELDTYPE].txt -> extraheer ID
            file_id = file_path.stem.split('.')[0]
            results[file_id] = text

    print(f"Klaar: {len(results)} bestanden succesvol verwerkt")
    return results


# Test functie
if __name__ == "__main__":
    # Voorbeeld RTF content
    test_rtf = r'''{\rtf1\ansi\deff0{\fonttbl{\f0 Verdana;}}
\viewkind4\uc1\pard\lang1043\f0\fs17 Dit is een test notitie van de monteur.\par
Tweede regel met meer informatie.\par}'''

    print("Test RTF parsing:")
    print("-" * 40)
    print("Input RTF:")
    print(test_rtf[:100] + "...")
    print("-" * 40)
    print("Output tekst:")
    print(strip_rtf(test_rtf))
