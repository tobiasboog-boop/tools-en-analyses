# Contract Check - Publieke Demo Versie

AI-gedreven classificatie van werkbonnen voor contract analyse.

Deze versie werkt met lokale Parquet data bestanden in plaats van een database connectie,
waardoor het geschikt is voor demo's en externe deployment.

## Installatie

```bash
# Maak een virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# of: venv\Scripts\activate  # Windows

# Installeer dependencies
pip install -r requirements.txt
```

## Data

Deze app verwacht Parquet bestanden in de `data/` map:
- `werkbonnen.parquet`
- `werkbonparagrafen.parquet`
- `kosten.parquet`
- `opbrengsten.parquet`
- `oplossingen.parquet`
- `opvolgingen.parquet`
- `metadata.json`

De data wordt gegenereerd met het export script in de pilot versie:
```bash
cd ../contract-check
python export_to_parquet.py --limit 200 --output ../contract-check-public/data
```

## Configuratie

Kopieer `.env.example` naar `.env` en vul je Anthropic API key in:
```bash
cp .env.example .env
```

## Starten

```bash
streamlit run Home.py --server.port 8508
```

Open [http://localhost:8508](http://localhost:8508) in je browser.

## Gebruik

1. **Werkbon Selectie** - Bekijk en selecteer werkbonnen uit de dataset
2. **Classificatie** - Laat de AI bepalen of werkbonnen binnen of buiten contract vallen

## Beperkingen

- Geen live database connectie
- Statische dataset (geen nieuwe werkbonnen)
- Contract bestanden moeten lokaal aanwezig zijn (of via tekstinvoer)
