# Zenith Werkbonnen Rapport - Veld Mapping

Overzicht van alle 37 kolommen in het rapport en hun databronnen.

## Basisgegevens (1-11)

| # | Veld | Bron Tabel | Bron Kolom | Transformatie |
|---|------|------------|------------|---------------|
| 1 | **Werkbon nummer** | `notifica.SSM Werkbonnen` | `Werkboncode` | Direct |
| 2 | **Gerelateerde werkbon** | `werkbonnen.Werkbonnen` | `ParentWerkbonDocumentKey` | Fill "-" als leeg |
| 3 | **Datum aanmaak** | `werkbonnen.Werkbonnen` | `MeldDatum` | `.dt.date` (alleen datum) |
| 4 | **Tijd aanmaak** | `werkbonnen.Werkbonnen` | `MeldTijd` | `.dt.time` |
| 5 | **Locatie naam** | `werkbonnen.Werkbonnen` | `Klant` | Direct |
| 6 | **Titel** | `notifica.SSM Werkbonnen` | `Werkbon titel` | Direct |
| 7 | **Storing omschrijving** | `maatwerk.stg_at_mwbsess_clobs` + 2 andere BLOB tabellen | `notitie` | Intelligente extractie: skip metadata, eerste betekenisvolle zin (max 200 chars) |
| 8 | **Locatie soort** | ❌ Niet in database | - | Heuristic: retail chains + nummers → "Store", DC/warehouse keywords → "Warehouse" |
| 9 | **Installatie soort** | `notifica.SSM Installaties` | `Installatiesoort` | Mapping: "Inbraak" → "Inbraakdetectie", etc. |
| 10 | **Onderaannemer** | `werkbonnen.Werkbonnen` | `Betreft onderaannemer` | Direct (Ja/Nee) |
| 11 | **Welke onderaannemer?** | `werkbonnen.Werkbonnen` | `Onderaannemer` | Filter Zenith, fill "Niet van toepassing" als Nee |

## SLA & Reactie (12-16)

| # | Veld | Bron Tabel | Bron Kolom | Transformatie |
|---|------|------------|------------|---------------|
| 12 | **Prio volgens SLA** | `werkbonnen.Werkbonnen` | `Prioriteit` | Mapping: "12UUR"/"4UUR" → Urgent, "NBD" → Low, rest → Medium |
| 13 | **Reactie datum** | `notifica.SSM Logboek werkbonfases` | `MIN(Datum en tijd)` WHERE Waarde LIKE '%In uitvoering%' | `.dt.date` |
| 14 | **Reactie tijd** | `notifica.SSM Logboek werkbonfases` | `MIN(Datum en tijd)` WHERE Waarde LIKE '%In uitvoering%' | `.dt.time` |
| 15 | **Contact CB** | ❌ Niet in database | - | **Leeg (handmatig invullen)** |
| 16 | **Prio na overleg CB** | `werkbonnen.Werkbonnen` | `Prioriteit` | Assumptie: zelfde als Prio volgens SLA |

## Oplossing & Status (17-21)

| # | Veld | Bron Tabel | Bron Kolom | Transformatie |
|---|------|------------|------------|---------------|
| 17 | **Datum oplossing** | `werkbonnen.Werkbonparagrafen` | `Uitgevoerd op` | `.dt.date` |
| 18 | **Tijd oplossing** | `werkbonnen.Werkbonparagrafen` | `TijdstipUitgevoerd` | `.dt.time` |
| 19 | **Geannuleerd?** | `werkbonnen.Werkbonnen` | `Status` | "Ja" als Status bevat "Geannuleerd", anders "Nee" |
| 20 | **Toelichting** | `maatwerk.stg_at_mwbsess_clobs`<br>`maatwerk.stg_at_uitvbest_clobs`<br>`maatwerk.stg_at_document_clobs` | `notitie` / `tekst` / `gc_notitie_extern`/`gc_informatie` | RTF stripped, volledige tekst (Unicode escapes converted) |
| 21 | **Ouderdom systeem** | ❌ Niet in database | - | **Leeg (handmatig invullen)** |

## Berekende Velden (22-37)

| # | Veld | Berekening | Bron |
|---|------|------------|------|
| 22 | **Maand** | `MONTH(Datum aanmaak)` | Datum aanmaak |
| 23 | **aanmaak d+t** | `Datum aanmaak + Tijd aanmaak` | Kolom 3 + 4 |
| 24 | **reactie d+t** | `Reactie datum + Reactie tijd` | Kolom 13 + 14 |
| 25 | **response d+t** | `Datum oplossing + Tijd oplossing` | Kolom 17 + 18 |
| 26 | **reactietijd** | `reactie d+t - aanmaak d+t` | Kolom 24 - 23 |
| 27 | **response tijd** | `response d+t - aanmaak d+t` | Kolom 25 - 23 |
| 28 | **Prio** | Mapping: Urgent=1, Medium=2, Low=3 | Kolom 12 |
| 29 | **reasponsetijd uren** | `CEILING(reactietijd.total_seconds() / 3600)` | Kolom 26 |
| 30 | **restoretijd uren** | `CEILING(response tijd.total_seconds() / 3600)` | Kolom 27 |
| 31 | **KPI response** | Lookup: Urgent=12u, Medium=24u, Low=48u | Kolom 28 |
| 32 | **KPI restore** | Lookup: Urgent=24u, Medium=48u, Low=72u | Kolom 28 |
| 33 | **SLA response** | "Behaald" als `reasponsetijd uren <= KPI response` | Kolom 29 vs 31 |
| 34 | **SLA restore** | "Behaald" als `restoretijd uren <= KPI restore` | Kolom 30 vs 32 |
| 35 | **responsetijd range** | Categorisatie: 0-4u, 4-8u, 8-12u, 12-24u, >24u | Kolom 29 |
| 36 | **Dag binnenkomst** | `WEEKDAY(Datum aanmaak)` (1=Ma, 7=Zo) | Kolom 3 |
| 37 | **Toelichting bij Niet Behaald** | "-" als beide SLA's behaald, anders leeg (handmatig) | Kolom 33 + 34 |

## Database Schema Overzicht

### Hoofdtabellen

```
werkbonnen.Werkbonnen
├── WerkbonDocumentKey (PK)
├── Werkbon
├── MeldDatum
├── MeldTijd
├── Klant
├── Debiteur
├── Prioriteit
├── Betreft onderaannemer
├── Onderaannemer
├── ParentWerkbonDocumentKey
└── Status

notifica.SSM Werkbonnen
├── WerkbonDocumentKey (FK)
├── Werkboncode
└── Werkbon titel

werkbonnen.Werkbonparagrafen
├── WerkbonDocumentKey (FK)
├── Uitgevoerd op
├── TijdstipUitgevoerd
└── InstallatieKey (FK)

notifica.SSM Installaties
├── InstallatieKey (PK)
└── Installatiesoort

notifica.SSM Logboek werkbonfases
├── WerkbonDocumentKey (FK)
├── Datum en tijd
└── Waarde (bijv. "In uitvoering")

werkbonnen.Mobiele uitvoersessies
├── DocumentKey (= WerkbonDocumentKey)
└── MobieleuitvoersessieRegelKey (FK naar BLOB tabellen)
```

### BLOB Tabellen (Monteur Notities)

```
maatwerk.stg_at_mwbsess_clobs
├── gc_id (= MobieleuitvoersessieRegelKey)
└── notitie (CLOB)

maatwerk.stg_at_uitvbest_clobs
├── gc_id (= MobieleuitvoersessieRegelKey)
└── tekst (CLOB)

maatwerk.stg_at_document_clobs
├── gc_id (= MobieleuitvoersessieRegelKey)
├── gc_notitie_extern (CLOB)
└── gc_informatie (CLOB)
```

## Filters Toegepast

Het rapport bevat **alleen werkbonnen die**:
1. ✅ **Gestart** zijn (hebben reactie_datetime in logboek)
2. ✅ **Afgerond** zijn (hebben datum_oplossing in paragrafen)
3. ✅ **BLOB notities** hebben (voor Storing omschrijving + Toelichting)

**Resultaat:** 94.4% data completeness, gemiddeld 2.1 lege velden per werkbon.

## Data Transformaties

### RTF Stripping (Kolom 7, 20)
- Remove RTF headers (`\rtf1`, `\ansi`, etc.)
- Remove font tables, color tables
- Convert Unicode escapes: `\'e9` → `é`, `\'e8` → `è`
- Remove escape backslashes: `\ ` → ` `
- Clean whitespace and semicolons

### Storing Omschrijving Extractie (Kolom 7)
**Intelligente extractie** die metadata skippt:
- Skip namen + datums (bijv. "Patrick Dutour Geerling 16-07-2024")
- Skip "Vervolg op:" referenties
- Skip zeer korte zinnen (< 20 chars)
- Vind eerste betekenisvolle zin (max 200 chars)

### Locatie Soort Heuristic (Kolom 8)
```python
if retail_chain_name in location_name and has_digits:
    return "Store"
elif "dc" or "distributie" or "warehouse" in location_name:
    return "Warehouse"
elif "kantoor" or "office" in location_name:
    return "Office"
```

### Installatie Soort Mapping (Kolom 9)
- "Inbraak" → "Inbraakdetectie"
- "Video" → "Camera"
- "TGC" → "Toegangscontrole"

## Excel Opmaak

- **Datum kolommen**: `dd-mm-yyyy` (zonder tijd)
- **Tijd kolommen**: `hh:mm:ss`
- **Datetime kolommen**: `dd-mm-yyyy hh:mm:ss`
- **🔴 Rood**: Niet in database (Contact CB, Ouderdom systeem)
- **🟡 Geel**: Automatisch afgeleid (Locatie soort)

