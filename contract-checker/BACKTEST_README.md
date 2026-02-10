# Contract Checker V1 vs V2 - Backtest Guide

## Wat is het verschil?

### V1 (Origineel)
- Standaard volgorde: eerst werkbon info, dan kosten, dan oplossingen onderaan
- Geen speciale nadruk op wat de monteur heeft gedaan
- Prompt focust algemeen op alle aspecten

### V2 (Verbeterd)
- **Oplossingen staan EERST** in het verhaal (krijgen meer gewicht)
- Emoji marker: 🔍 "WAT HEEFT DE MONTEUR GEDAAN?"
- AI prompt instrueert expliciet: "Lees EERST de oplossingen sectie - dit is CRUCIAAL"
- Toelichting moet expliciet vermelden wat de monteur heeft gedaan

## Backtest uitvoeren

### Stap 1: Setup API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Stap 2: Run backtest

```bash
python backtest_v1_v2.py
```

Dit draait met de standaard instellingen:
- Debiteur: 005102 (Trivire)
- Periode: 2024
- Max 50 werkbonnen

### Stap 3: Pas parameters aan

Edit `backtest_v1_v2.py` onderaan:

```python
results = runner.run_backtest(
    debiteur_filter=["005102"],      # Wijzig naar andere debiteur codes
    date_start="2024-01-01",         # Startdatum
    date_end="2024-12-31",           # Einddatum
    max_werkbonnen=50,               # Aantal werkbonnen te testen
    ground_truth_csv=None            # Optioneel: pad naar CSV met labels
)
```

## Ground Truth toevoegen

Voor nauwkeurige accuracy meting heb je handmatige labels nodig.

### Template CSV maken

```csv
werkbon_key,label,notities
123456,JA,Regulier onderhoud
123457,NEE,Materiaal vervangen buiten contract
123458,JA,Storing binnen garantie
```

Kolommen:
- `werkbon_key`: De werkbon ID (integer)
- `label`: JA, NEE, of TWIJFEL
- `notities`: (optioneel) Waarom dit label?

### Backtest met ground truth

```python
results = runner.run_backtest(
    debiteur_filter=["005102"],
    max_werkbonnen=50,
    ground_truth_csv="trivire_labels.csv"  # Je handmatige labels
)
```

Output toont dan:
```
ACCURACY (vs Ground Truth)
V1 accuracy: 22/44 = 50.0%
V2 accuracy: 35/44 = 79.5%

✅ V2 is 13 werkbonnen beter (+29.5%)
```

## Resultaten analyseren

Het script maakt een CSV aan: `backtest_results_YYYYMMDD_HHMMSS.csv`

Kolommen:
- `werkbon_key`, `debiteur`, `contract`
- `v1_classificatie`, `v1_confidence`, `v1_toelichting`
- `v2_classificatie`, `v2_confidence`, `v2_toelichting`
- `verschil`: ✅ Gelijk of ❌ Verschillend
- `ground_truth`, `v1_correct`, `v2_correct` (als ground truth aanwezig)

### Hoe te interpreteren?

1. **Kijk naar verschillen**: Werkbonnen waar V1 en V2 anders classificeren
   - Check handmatig: welke is correct?
   - Wat staat er in de "oplossing" tekst?

2. **Let op confidence scores**:
   - Hoge confidence + verkeerd = prompt probleem
   - Lage confidence + goed = prompt kan explicieter

3. **TWIJFEL analyse**:
   - Worden onduidelijke werkbonnen correct als TWIJFEL geclassificeerd?
   - Of misclassificeert V1 meer werkbonnen als TWIJFEL (te voorzichtig)?

## Snelle test zonder backtest script

### Optie A: Gebruik de apps direct

1. Open **app.py** (V1) in browser
2. Classificeer batch Trivire werkbonnen, export CSV
3. Open **app_v2.py** (V2) in browser
4. Classificeer DEZELFDE batch, export CSV
5. Vergelijk in Excel/Google Sheets

### Optie B: Sample steekproef

1. Kies 10-20 werkbonnen handmatig
2. Run beide versies
3. Check elk resultaat: welke is juist?
4. Simpele telling: V1 correct = 6/10, V2 correct = 9/10 → V2 wint

## Verwachte verbetering

Based op feedback Gerrit (steekproef Trivire):
- **V1**: 22/44 correct = 50%
- **V2**: Verwachting 70-80%

Waarom?
- Monteurs schrijven in oplossingen cruciale info zoals:
  - "Condensafvoer vervangen" → NEE (materiaal)
  - "Reset cv-ketel na storing" → JA (binnen onderhoud)
  - "Nieuwe pomp geplaatst" → NEE (kapitaalgoed)

V1 zag deze teksten wel, maar gaf ze minder gewicht.
V2 analyseert deze EERST en EXPLICIET.

## Deploy naar Streamlit Cloud

### V2 deployen als aparte app:

1. Commit beide apps naar GitHub:
   ```bash
   git add app_v2.py backtest_v1_v2.py
   git commit -m "Add V2 with improved oplossingen focus + backtest"
   git push
   ```

2. Ga naar Streamlit Cloud Dashboard
3. Create New App → Selecteer je repo
4. **Belangrijk**: Stel in:
   - Main file path: `contract-checker/app_v2.py`
   - App URL: `...-v2.streamlit.app`

5. Zelfde wachtwoord gebruiken (in secrets)

Nu heb je twee apps live:
- V1: Origineel (blijft draaien voor referentie)
- V2: Verbeterd (nieuwe classificaties)

WVC kan beide gebruiken en vergelijken!

## Vragen?

- Werkt V2 niet zoals verwacht? Check de prompt in `app_v2.py` regel 285-310
- API errors? Check rate limits Anthropic (Haiku heeft hoge limits)
- Wil je andere verbeteringen? Overweeg:
  - Finetuning op WVC data
  - Prompt engineering met few-shot examples
  - Gebruik Claude Sonnet (accurater maar duurder)
