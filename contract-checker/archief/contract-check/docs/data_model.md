# Data Model - Contract Checker

Dit document beschrijft de datastructuur van werkbonnen en contracten in de WVC datawarehouse.

---

## De Grote Lijn

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SYNTESS STRUCTUUR                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Relaties (stam.Relaties) ──────────────────────────────────────────────────│
│      │                                                                       │
│      ├── Op Project: Opdrachtgever, Klant, Debiteur                         │
│      ├── Op Werkbon: Klant, Debiteur, Onderaannemer                         │
│      └── Op Object:  Eigenaar, Debiteur, Beheerder, Gebruiker               │
│                                                                              │
│  ───────────────────────────────────────────────────────────────────────────│
│                                                                              │
│  Object (gebouw, boot, vrachtwagen)                                          │
│      │   ├── Eigenaar (relatie)                                             │
│      │   ├── Debiteur (relatie)                                             │
│      │   ├── Beheerder (relatie)                                            │
│      │   └── Gebruiker (relatie)                                            │
│      │                                                                       │
│      └── Installaties (apparaten)                                            │
│              ├── CV ketel                                                    │
│              ├── Warmtepomp                                                  │
│              └── Airconditioning, etc.                                       │
│                                                                              │
│  ───────────────────────────────────────────────────────────────────────────│
│                                                                              │
│  Onderhoudscontract (Periodiek Project)                                      │
│      │   ├── Opdrachtgever (relatie) ← altijd gevuld                        │
│      │   ├── Klant (relatie) ← kan afwijken                                 │
│      │   └── Debiteur (relatie) ← hoeft niet gevuld                         │
│      │                                                                       │
│      └── Bestek (1:1 met project)                                            │
│              │                                                               │
│              └── Bestekparagrafen (1:N) ← HIER LEES JE HET CONTRACT          │
│                      │                                                       │
│                      ├── Object (welk gebouw/installatie)                   │
│                      ├── Installatie (welk apparaat)                        │
│                      ├── Onderhoudsfrequentie + plandatum                   │
│                      ├── Werkvoorbereiding (geschatte uren)                 │
│                      ├── Cyclus (zwaar/licht afwisselen)                    │
│                      └── Factureerwijzen (onderhoud + storing)              │
│                              │                                               │
│                              ├── Vaste prijs                                │
│                              ├── Regie                                      │
│                              └── Hybride (arbeid/materiaal)                 │
│                                                                              │
│                                      │                                       │
│                                      ▼                                       │
│                           Werkbonparagraaf                                   │
│                           (erft factureerwijze)                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Overzicht

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATAWAREHOUSE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  stam.Relaties ─────────────────┐                                           │
│  (alle klanten/leveranciers)    │                                           │
│                                 │                                           │
│                                 ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        werkbonnen.Werkbonnen                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Hoofdwerkbon                                                     │ │   │
│  │  │  - KlantrelatieKey      → stam.Relaties (bewoner/opdrachtgever) │ │   │
│  │  │  - DebiteurRelatieKey   → stam.Relaties (wie betaalt = CONTRACT)│ │   │
│  │  │  - OnderaannemerRelatieKey → stam.Relaties (uitvoerder)         │ │   │
│  │  │                                                                  │ │   │
│  │  │  ┌─────────────────────────────────────────────────────────┐    │ │   │
│  │  │  │ Vervolgbon 1                                            │    │ │   │
│  │  │  │  (ParentWerkbonDocumentKey → Hoofdwerkbon)              │    │ │   │
│  │  │  └─────────────────────────────────────────────────────────┘    │ │   │
│  │  │  ┌─────────────────────────────────────────────────────────┐    │ │   │
│  │  │  │ Vervolgbon 2                                            │    │ │   │
│  │  │  │  (ParentWerkbonDocumentKey → Vervolgbon 1)              │    │ │   │
│  │  │  └─────────────────────────────────────────────────────────┘    │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Relaties (stam.Relaties)

Centrale tabel met alle partijen: klanten, leveranciers, aannemers, etc.

| Kolom | Type | Beschrijving |
|-------|------|--------------|
| RelatieKey | bigint | Primary key (intern) |
| Relatie Code | varchar | **Identificatie** (bijv. "177460") |
| Relatie | varchar | Volledige naam (bijv. "Stichting Thuisvester (Oosterhout)") |
| Korte naam | varchar | Afkorting |
| Status | text | Actief/Inactief |

**Let op:** Een relatie kan meerdere rollen hebben op verschillende niveaus:

### Op Project niveau
| Rol | Verplicht | Beschrijving |
|-----|-----------|--------------|
| **Opdrachtgever** | Ja | Wie geeft de opdracht |
| Klant | Nee | Kan afwijken van opdrachtgever |
| Debiteur | Nee | Wie betaalt (hoeft niet gevuld) |

### Op Werkbon niveau
| Rol | Beschrijving |
|-----|--------------|
| **Klant** | Opdrachtgever/bewoner |
| **Debiteur** | Wie betaalt → **dit matcht met contract** |
| Onderaannemer | Wie voert het werk uit |

### Op Object niveau
Een object (gebouw, boot, vrachtwagen) kan meerdere relaties hebben:

| Rol | Beschrijving |
|-----|--------------|
| Eigenaar | Wie bezit het object |
| Debiteur | Wie betaalt voor onderhoud |
| Beheerder | Wie beheert het object |
| Gebruiker | Wie gebruikt het object |

### Installatie
Een **installatie** is een apparaat binnen een object:
- CV ketel
- Warmte-terugwinunit
- Warmtepomp
- Airconditioning
- etc.

```
Object (gebouw)
    ├── Eigenaar (relatie)
    ├── Debiteur (relatie)
    ├── Beheerder (relatie)
    ├── Gebruiker (relatie)
    │
    └── Installaties
            ├── CV ketel
            ├── Warmtepomp
            └── Airconditioning
```

---

## 2. Bestek & Bestekparagrafen (Contract in Syntess)

### 2.1 Onderhoudscontract = Periodiek Project

In Syntess wordt een onderhoudscontract opgezet als een **periodiek project**:
- Kan doorlopend zijn (over meerdere jaren)
- Of per jaar (voor jaarlijkse kosten/opbrengsten overzicht)

### 2.2 Bestek

Het bestek is een document met een **1:1 relatie** met het project. Het bestek zelf bevat weinig, maar de bestekparagrafen bevatten de echte contractinformatie.

### 2.3 Bestekparagrafen ← HIER LEES JE HET CONTRACT

De bestekparagrafen definiëren wat er onder het contract valt:

| Onderdeel | Beschrijving |
|-----------|--------------|
| **Installatie** | Welk type installatie (CV, Warmwater, Ventilatie, etc.) |
| **Object** | Waar - gebouw, boot, vrachtwagen, etc. |
| **Onderhoudsfrequentie** | Hoe vaak onderhoud (1x per jaar, 2x per jaar, etc.) |
| **Plandatum** | Wanneer gepland |
| **Werkvoorbereiding** | Geschatte arbeid (uren) voor onderhoud |
| **Cyclus** | Afwisseling zwaar/licht onderhoud |

### 2.4 Factureerwijzen

Per bestekparagraaf wordt vastgelegd hoe er gefactureerd wordt, zowel voor **onderhoud** als voor **storingen**:

| Factureerwijze | Betekenis |
|----------------|-----------|
| **Vaste prijs** | Alles zit in het contract, niets factureren |
| **Regie** | Alles factureren (arbeid + materiaal) |
| **Alleen arbeid factureren** | Materiaal in contract, arbeid factureren |
| **Alleen materiaal factureren** | Arbeid in contract, materiaal factureren |

### 2.5 Factureervoorwaarden

Naast de factureerwijze kunnen **factureervoorwaarden** specifiek bepalen:
- Welke materialen wel/niet factureren
- Welke uren wel/niet factureren
- Specifieke uitsluitingen of toevoegingen

### 2.6 Link naar Werkbonparagraaf

De werkbonparagraaf erft van de bestekparagraaf:
- `BestekparagraafKey` → link naar de bestekparagraaf
- `Factureerwijze` → overgenomen van bestekparagraaf

```
Bestekparagraaf (contract definitie)
        │
        │ bepaalt
        ▼
Werkbonparagraaf (uitvoering)
        │
        │ genereert
        ▼
Kosten + eventueel Opbrengsten
```

---

## 3. Werkbon Hiërarchie

### 3.1 Werkbonnen (werkbonnen.Werkbonnen)

```
Hoofdwerkbon (Niveau=1, HoofdwerkbonDocumentKey = eigen key)
    │
    ├── Vervolgbon 1 (ParentWerkbonDocumentKey → Hoofdwerkbon)
    │       │
    │       └── Vervolgbon 1a (ParentWerkbonDocumentKey → Vervolgbon 1)
    │
    └── Vervolgbon 2 (ParentWerkbonDocumentKey → Hoofdwerkbon)
```

**Belangrijke kolommen:**

| Kolom | Beschrijving |
|-------|--------------|
| WerkbonDocumentKey | Primary key |
| HoofdwerkbonDocumentKey | Altijd de key van de hoofdwerkbon in de keten |
| ParentWerkbonDocumentKey | Directe parent (NULL voor hoofdwerkbon) |
| Niveau | Diepte in hiërarchie (1 = hoofdwerkbon) |

**Relatie-kolommen op werkbon:**

| Kolom | Relatie | Betekenis |
|-------|---------|-----------|
| Klant | KlantrelatieKey | Opdrachtgever/bewoner - wie meldt de storing |
| **Debiteur** | DebiteurRelatieKey | **Wie betaalt = contracthouder** |
| Onderaannemer | OnderaannemerRelatieKey | Wie voert het werk uit |

> **BELANGRIJK:** Voor contract matching gebruiken we **Debiteur**, niet Klant!
> De Debiteur is de woningcorporatie die het contract heeft.

---

### 3.2 Werkbonparagrafen (werkbonnen.Werkbonparagrafen)

Elke werkbon (hoofd én vervolg) heeft eigen paragrafen.

```
Werkbon
    ├── Paragraaf 1 (CV installatie)
    │       ├── Kosten (1:N)
    │       ├── Opbrengsten (1:N) ← gefactureerd = BUITEN CONTRACT
    │       ├── Oplossingen (1:N)
    │       └── Opvolgingen (1:N)
    │
    └── Paragraaf 2 (Warmwater)
            ├── Kosten (1:N)
            └── ...
```

**Belangrijke kolommen:**

| Kolom | Beschrijving |
|-------|--------------|
| WerkbonparagraafKey | Primary key |
| WerkbonDocumentKey | FK naar werkbon |
| Werkbonparagraaf | Naam/omschrijving |
| **Factureerwijze** | "Vaste prijs (binnen contract)", "Regie (alles factureren)", etc. |
| Storing | Wat was het probleem |
| Oorzaak | Waarom ontstond het |
| Uitvoeringstatus | Uitgevoerd/Gepland/etc. |

---

### 3.3 Kosten (werkbonnen."Werkbon kosten")

Kostenregels per paragraaf.

| Kolom | Beschrijving |
|-------|--------------|
| WerkbonparagraafKey | FK naar paragraaf |
| Omschrijving | Wat |
| Aantal | Hoeveelheid |
| Verrekenprijs | Prijs per eenheid |
| Kostprijs | Inkoopprijs |
| Kostenbron | "Inkoop", "Arbeid", etc. |
| Arbeidregel Ja/Nee | Is dit arbeidskosten? |

---

### 3.4 Opbrengsten (financieel.Opbrengsten)

**Dit is de sleutel voor "buiten contract" detectie!**

Als een werkbonparagraaf opbrengsten heeft → er is gefactureerd → buiten contract.

| Kolom | Beschrijving |
|-------|--------------|
| WerkbonParagraafKey | FK naar paragraaf |
| Bedrag | Gefactureerd bedrag |
| Kostensoort | "Omzet buiten contract", etc. |
| Debiteur | Wie is gefactureerd |
| Factuurdatum | Wanneer |

> **Regel:** `SUM(Opbrengsten.Bedrag) > 0` → werk is gefactureerd → buiten contract

---

### 3.5 Oplossingen (werkbonnen."Werkbon oplossingen")

Wat is er gedaan om het probleem op te lossen.

| Kolom | Beschrijving |
|-------|--------------|
| WerkbonparagraafKey | FK naar paragraaf |
| Oplossing | Omschrijving van de oplossing |

---

### 3.6 Opvolgingen (werkbonnen."Werkbon opvolgingen")

Vervolgacties of aantekeningen.

| Kolom | Beschrijving |
|-------|--------------|
| WerkbonparagraafKey | FK naar paragraaf |
| Opvolging | Omschrijving |

---

## 4. Contract Structuur (contract_checker schema)

### 4.1 Contracts

| Kolom | Beschrijving |
|-------|--------------|
| id | Primary key |
| filename | Bestandsnaam (bijv. "Thuisvester.txt") |
| content | Platte tekst van contract |
| source_file | Origineel bestand |
| llm_context | Instructies voor LLM |
| llm_ready | Door LLM gestructureerde versie |

### 4.2 Contract_Relatie (1:N koppeling)

Een contract kan voor meerdere relaties gelden.

| Kolom | Beschrijving |
|-------|--------------|
| contract_id | FK naar contracts |
| client_id | Relatie Code (bijv. "177460") |
| client_name | Naam voor display |

```
Contract "Thuisvester.txt"
    └── contract_relatie
            └── 177460 - Stichting Thuisvester (Oosterhout)

Contract "Bazalt.txt"
    └── contract_relatie
            └── 007453 - Stichting Bazalt Wonen
```

---

## 4. Classificatie Flow

```
1. Selecteer Contract
       │
       ▼
2. Haal gekoppelde relaties op (contract_relatie.client_id)
       │
       ▼
3. Zoek werkbonnen waar Debiteur LIKE '{client_id} - %'
       │
       ▼
4. Per hoofdwerkbon: bouw keten (hoofd + vervolgbonnen)
       │
       ▼
5. Per werkbon in keten: haal paragrafen + kosten + opbrengsten
       │
       ▼
6. Genereer "verhaal" voor LLM
       │
       ▼
7. LLM classificeert: binnen/buiten contract per paragraaf
```

---

## 5. Voorbeeld Werkbon Keten (JSON)

```json
{
  "keten_id": 3041469,
  "relatie": {
    "code": "177460",
    "naam": "Stichting Thuisvester (Oosterhout)"
  },
  "totalen": {
    "kosten": 1892.40,
    "gefactureerd": 395.14,
    "binnen_contract": 1497.26
  },
  "werkbonnen": [
    {
      "nummer": "W2603415 - Storing expansieautomaat",
      "type": "Losse regiebon",
      "is_hoofdwerkbon": true,
      "paragrafen": [
        {
          "naam": "Warmte opwekkings installatie",
          "factureerwijze": "Regie (alles factureren)",
          "storing": "025 - Storing expansieautomaat",
          "kosten": {
            "totaal": 1892.40,
            "arbeid": 1892.40,
            "materiaal": 0.00
          },
          "gefactureerd": 395.14
        }
      ]
    }
  ]
}
```

---

## 6. Database Views Overzicht

### Bestek & Contract definitie
| Schema | View | Beschrijving |
|--------|------|--------------|
| stam | Bestekken | Bestekken (1:1 met project) |
| projecten | Bestekparagrafen | **Bestekparagrafen (contract definitie)** |

### Werkbonnen & Uitvoering
| Schema | View | Beschrijving |
|--------|------|--------------|
| werkbonnen | Werkbonnen | Hoofdtabel werkbonnen |
| werkbonnen | Werkbonparagrafen | Paragrafen per werkbon |
| werkbonnen | Werkbon kosten | Kostenregels |
| werkbonnen | Werkbon oplossingen | Oplossingen |
| werkbonnen | Werkbon opvolgingen | Opvolgingen |

### Financieel & Stamgegevens
| Schema | View | Beschrijving |
|--------|------|--------------|
| financieel | Opbrengsten | Gefactureerde bedragen (buiten contract indicator) |
| stam | Relaties | Alle klanten/leveranciers |

---

## 7. Huidige Contracten

| Contract | Relatie Code | Relatie Naam | Werkbonnen (Debiteur) |
|----------|--------------|--------------|----------------------|
| Bazalt.txt | 007453 | Stichting Bazalt Wonen | 40.149 |
| Thuisvester.txt | 177460 | Stichting Thuisvester (Oosterhout) | 50.477 |
| Trivire_Tablis_rhiant.txt | 005102 | Trivire | 157.348 |

---

## 8. Bekende Complexiteit & Aandachtspunten

### 8.1 Werkbon vs Werkbonparagraaf Type

**Probleem:** In de volksmond wordt gesproken over "storingsbonnen" en "onderhoudsbonnen", maar dit is een oversimplificatie.

**Realiteit:**
- Een werkbon kan **meerdere werkbonparagrafen** hebben
- Elke paragraaf heeft een eigen **Type**: `Storing`, `Onderhoud`, `Onderhoud en Storing`, of `Onbekend (regie/project)`
- Een werkbon kan dus zowel Storing als Onderhoud paragrafen bevatten

**Voorbeeld scenario:**
```
Hoofdwerkbon (start als Onderhoud)
    ├── Paragraaf 1: Onderhoud (jaarlijks onderhoud CV)
    │
    └── Vervolgbon (ontstaat tijdens onderhoud)
            └── Paragraaf 2: Storing (defect geconstateerd tijdens onderhoud)
```

**Typen in database (werkbonnen.Werkbonparagrafen.Type):**

| Type | Aantal | Relevant voor classificatie |
|------|--------|----------------------------|
| Storing | ~491k | ✅ Ja - te classificeren |
| Onderhoud | ~325k | ❌ Nee - altijd binnen contract |
| Onderhoud en Storing | ~857 | ✅ Ja - te classificeren |
| Onbekend (regie/project) | ~54k | ❌ Nee - geen contract context |

**Onze aanpak:**

1. **Selectie:** Werkbon wordt geselecteerd als ≥1 paragraaf van type "Storing" of "Onderhoud en Storing"
2. **Verhaal:** Alle paragrafen worden getoond (voor context)
3. **Classificatie:** Alleen Storing/Onderhoud+Storing paragrafen worden door LLM beoordeeld
4. **Onderhoud paragrafen:** Worden genegeerd voor classificatie (zijn per definitie binnen contract)

### 8.2 Debiteur vs Klant op Werkbon

**Probleem:** Op een werkbon staan zowel "Klant" als "Debiteur" velden.

**Verschil:**
- **Klant**: De bewoner/opdrachtgever die de melding doet
- **Debiteur**: Wie betaalt = de contracthouder (woningcorporatie)

**Regel:** Voor contract matching gebruiken we altijd **Debiteur**, niet Klant.

```
Werkbon W2603414
├── Klant: "Jansen, Azaleastraat 26"     ← bewoner
├── Debiteur: "007453 - Stichting Bazalt Wonen"  ← contracthouder ✓
```

### 8.3 Factureerwijze Interpretatie

De factureerwijze op werkbonparagraaf bepaalt wat "binnen contract" betekent:

| Factureerwijze | Binnen contract | Buiten contract |
|----------------|-----------------|-----------------|
| Vaste prijs | Alles | Niets |
| Regie | Niets | Alles (arbeid + materiaal) |
| Alleen arbeid factureren | Materiaal | Arbeid |
| Alleen materiaal factureren | Arbeid | Materiaal |

**Verificatie:** `SUM(Opbrengsten.Bedrag) > 0` = er is gefactureerd = buiten contract

### 8.4 Vervolgbonnen Keten

**Probleem:** Kosten kunnen verspreid zijn over meerdere bonnen in een keten.

**Oplossing:** Altijd de hele keten analyseren via `HoofdwerkbonDocumentKey`:
- Hoofdwerkbon: `HoofdwerkbonDocumentKey = WerkbonDocumentKey`
- Vervolgbonnen: `HoofdwerkbonDocumentKey ≠ WerkbonDocumentKey`

```sql
-- Alle bonnen in een keten
SELECT * FROM werkbonnen."Werkbonnen"
WHERE "HoofdwerkbonDocumentKey" = :hoofdwerkbon_key
ORDER BY "Niveau", "MeldDatum"
```

### 8.5 Status, Documentstatus en Administratieve Fase

**Drie verschillende statusvelden op werkbonnen:**

| Veld | Functie | Waarden |
|------|---------|---------|
| **Status** | Operationele status | Uitgevoerd, Vervallen, Aanmaak, In uitvoering |
| **Documentstatus** | Archief status | Historisch, Openstaand, Gereed |
| **Administratieve fase** | Workflow positie | 001 - ., 002 - Gecontroleerd, 003 - Klaar voor gereedmelden, etc. |

**Voor "afgeronde trajecten" gebruiken we:**

```sql
WHERE TRIM("Status") = 'Uitgevoerd'
  AND TRIM("Documentstatus") = 'Historisch'
```

**Waarom beide?**
- `Status = 'Uitgevoerd'` → werk is gedaan
- `Documentstatus = 'Historisch'` → administratief afgerond en gearchiveerd

**Tellingen (januari 2025):**

| Combinatie | Aantal |
|------------|--------|
| Uitgevoerd + Historisch | ~784.000 |
| Uitgevoerd + Openstaand | ~4.400 |
| Uitgevoerd + Gereed | ~3 |

**Administratieve fase - niet relevant voor filtering:**

De administratieve fase is een workflow-indicator, geen error-state:
- `001 - .` → Default/initieel
- `002 - Gecontroleerd door callcenter-medewerker`
- `003/004/005/006 - Klaar voor gereedmelden` → Varianten per klant
- `01-04` → ZZP/inlener workflow

Voor selectie van te classificeren werkbonnen is alleen `Documentstatus = 'Historisch'` nodig.

### 8.6 Status binnen Werkbon Keten

**Belangrijk: Status KAN verschillen binnen een keten!**

Hoofd- en vervolgbonnen hebben elk hun eigen Status en Documentstatus:

| Situatie | Aantal ketens |
|----------|---------------|
| Hoofd + Vervolg beide Historisch | 91.685 |
| Hoofd Historisch, Vervolg **nog Openstaand** | 923 |
| Hoofd Openstaand, Vervolg **al Historisch** | 373 |
| Beide Openstaand | 722 |

**Voorbeeld van gemixte keten:**
```
Hoofdwerkbon W1200260
├── Status: Uitgevoerd | DocStatus: Openstaand | Admin: Klaar voor gereedmelden

Vervolgbon W1204258
├── Status: Uitgevoerd | DocStatus: Historisch | Admin: (leeg)  ← al klaar!

Vervolgbon W1208473
├── Status: Uitgevoerd | DocStatus: Openstaand | Admin: Klaar voor gereedmelden
```

**Conclusies:**
1. Filter altijd **per werkbon**, niet per keten
2. Toon status per werkbon in het verhaal
3. Een keten is pas "volledig afgerond" als ALLE bonnen Historisch zijn

### 8.7 Hoofdwerkbon Identificatie

**Methode 1: Via Keys (primair)**
```sql
-- Hoofdwerkbon
WHERE "HoofdwerkbonDocumentKey" = "WerkbonDocumentKey"

-- Vervolgbon
WHERE "HoofdwerkbonDocumentKey" != "WerkbonDocumentKey"
```

**Methode 2: Via Niveau**
- Niveau 1 = Hoofdwerkbon (743k records)
- Niveau 2+ = Vervolgbon (tot niveau 66!)

**Methode 3: Via Kolommen**
- `Werkbon` = eigen titel
- `Hoofdwerkbon` = titel van de hoofdwerkbon
- Bij hoofdwerkbon: beide zijn gelijk
- Bij vervolgbon: `Hoofdwerkbon` verwijst naar hoofdwerkbon titel

**Parent relatie:**
- Hoofdwerkbon: `ParentWerkbonDocumentKey = NULL`
- Vervolgbon: `ParentWerkbonDocumentKey` = directe parent

---

## 9. Verificatie Checks

Er zijn verificatie scripts beschikbaar in de `checks/` folder om de datastructuur te valideren:

```bash
# Uitvoeren
cd c:\projects\contract-check
venv\Scripts\python.exe checks\<script>.py
```

| Script | Doel |
|--------|------|
| `check_werkbon_velden.py` | Alle kolommen per tabel tonen |
| `check_hoofdwerkbon.py` | Hoofd/vervolgbon identificatie verificatie |
| `check_keten_status.py` | Status verschillen binnen keten |
| `check_workflow_status.py` | Status + Documentstatus combinaties |
| `check_opvolgingen.py` | Opvolgingen structuur |

Zie `checks/README.md` voor bevindingen en WVC-specifieke details.
