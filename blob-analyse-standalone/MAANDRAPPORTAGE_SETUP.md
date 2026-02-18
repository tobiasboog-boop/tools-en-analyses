# Maandrapportage Setup - Zenith Security

## Wat is er veranderd?

De blob-analyse app is vereenvoudigd voor **één specifiek doel: maandrapportage**.

### Oude versie (gearchiveerd)
- **Bestand:** `app_full_version.py`
- **Inhoud:** 4 business cases + documentatie tab
  - Meerwerk Scanner
  - Contract Checker
  - Terugkeer Analyse
  - Rapportage
  - Data Model

### Nieuwe versie (actief)
- **Bestand:** `app.py`
- **Inhoud:** **Alleen maandrapportage**
- **Databron:** Live database connectie naar CLOB tabellen (geen JSON files meer)

## Database Connectie

De nieuwe app haalt data rechtstreeks uit de database:

```python
DB_CONFIG = {
    "host": "217.160.16.105",
    "port": 5432,
    "database": "1229",
    "user": "steamlit_1229",
    "password": "steamlit_1229"
}
```

### CLOB Tabellen
De blobvelden worden opgehaald uit:
- `maatwerk.stg_AT_DOCUMENT_CLOBS`
- `maatwerk.stg_AT_UITVBEST_CLOBS`
- `maatwerk.stg_AT_WERK_CLOBS`
- `maatwerk.stg_AT_MWBSESS_CLOBS`

### DWH Tabellen
Werkbon data komt uit:
- `werkbonnen."Documenten"`
- `werkbonnen."Mobiele uitvoersessies"` (koppeltabel)

## Installatie

```bash
# Installeer dependencies
pip install -r requirements.txt

# Run de app
streamlit run app.py
```

## Database Structuur Inspecteren

Gebruik het inspector script om te zien welke kolommen in de CLOB tabellen zitten:

```bash
cd scripts
python inspect_clob_tables.py
```

Dit script toont:
- Alle kolommen per tabel
- Data types
- Sample data (eerste 3 rijen)
- Aantal rijen per tabel

## TODO: CLOB Data Integratie

**⚠️ BELANGRIJK:** De huidige `app.py` heeft placeholder logica voor CLOB data integratie.

Om de volledige integratie werkend te krijgen:

1. **Run het inspector script:**
   ```bash
   python scripts/inspect_clob_tables.py
   ```

2. **Identificeer de juiste kolommen:**
   - Welke kolom bevat de CLOB tekst (notities)?
   - Welke kolom is de primary key (ID)?
   - Hoe koppel je aan `MobieleuitvoersessieRegelKey`?

3. **Pas `combine_data_for_rapport()` aan in `app.py`:**
   - Update de join logica
   - Map de CLOB kolommen naar het rapport formaat
   - Test met echte data

## Data Flow

```
CLOB Tabellen (maatwerk schema)
    ↓
    | ID kolom = MobieleuitvoersessieRegelKey
    ↓
werkbonnen."Mobiele uitvoersessies"
    ↓
    | DocumentKey
    ↓
werkbonnen."Documenten"
    ↓
Maandrapportage Tabel
```

## Voorbeeld Query

Zo zou de volledige join eruit moeten zien:

```sql
SELECT
    d."Werkboncode",
    d."Klantnaam",
    s."Medewerker",
    s."Datum",
    d."Status",
    c."<CLOB_TEKST_KOLOM>" as notitie  -- Pas aan!
FROM werkbonnen."Documenten" d
LEFT JOIN werkbonnen."Mobiele uitvoersessies" s
    ON d."DocumentKey" = s."DocumentKey"
LEFT JOIN maatwerk.stg_AT_MWBSESS_CLOBS c
    ON s."MobieleuitvoersessieRegelKey" = c."<ID_KOLOM>"  -- Pas aan!
WHERE d."Melddatum" >= '2024-01-01'
ORDER BY d."Melddatum" DESC
```

## Test Plan

1. ✅ Database connectie testen
2. ✅ CLOB tabellen inspecteren
3. ⏳ Join logica implementeren
4. ⏳ Sample data valideren
5. ⏳ Filters testen
6. ⏳ Export functie testen

## Support

Bij vragen of problemen:
- Check het inspector script output
- Kijk in `app_full_version.py` voor de originele implementatie
- Test queries handmatig in een SQL client (DBeaver, pgAdmin)

---

**Versie:** 1.0
**Laatst bijgewerkt:** 2026-02-10
**Contact:** Notifica B.V.
