# Data Checks - Syntess/WVC Datawarehouse

Dit zijn verificatie scripts om de datastructuur en workflow van Syntess werkbonnen te begrijpen.

## Gebruik

```bash
cd c:\projects\contract-check
venv\Scripts\python.exe checks\<script>.py
```

## Scripts

### Generieke Syntess Checks

| Script | Doel |
|--------|------|
| `check_werkbon_velden.py` | Toon alle kolommen per tabel (Werkbonnen, Werkbonparagrafen, Opvolgingen, Oplossingen) |
| `check_hoofdwerkbon.py` | Verificatie van hoofd/vervolgbon identificatie via keys en kolommen |
| `check_keten_status.py` | Check of status/documentstatus kan verschillen binnen een keten |

### Workflow Checks

| Script | Doel |
|--------|------|
| `check_workflow_status.py` | Analyse van Status + Documentstatus combinaties |
| `check_opvolgingen.py` | Analyse van opvolgingen structuur en soorten |

---

## Bevindingen

### Hoofdwerkbon Identificatie

**Methode 1: Via Keys (betrouwbaar)**
```sql
-- Hoofdwerkbon
WHERE "HoofdwerkbonDocumentKey" = "WerkbonDocumentKey"

-- Vervolgbon
WHERE "HoofdwerkbonDocumentKey" != "WerkbonDocumentKey"
```

**Methode 2: Via Niveau**
- Niveau 1 = Hoofdwerkbon
- Niveau 2+ = Vervolgbon

**Methode 3: Via Kolommen**
- `Werkbon` = eigen titel
- `Hoofdwerkbon` = titel van de hoofdwerkbon (altijd)
- Bij hoofdwerkbon: beide zijn gelijk
- Bij vervolgbon: `Hoofdwerkbon` verwijst naar de hoofdwerkbon titel

### Keten Hiërarchie

```
Hoofdwerkbon (Niveau 1)
├── HoofdwerkbonDocumentKey = eigen key
├── ParentWerkbonDocumentKey = NULL
│
├── Vervolgbon (Niveau 2)
│   ├── HoofdwerkbonDocumentKey = hoofdwerkbon key
│   ├── ParentWerkbonDocumentKey = hoofdwerkbon key
│   │
│   └── Vervolgbon (Niveau 3)
│       ├── HoofdwerkbonDocumentKey = hoofdwerkbon key (altijd!)
│       └── ParentWerkbonDocumentKey = parent vervolgbon key
```

### Status binnen Keten

**Belangrijk: Status KAN verschillen binnen een keten!**

| Situatie | Aantal |
|----------|--------|
| Hoofd + Vervolg beide Historisch | 91.685 |
| Hoofd Historisch, Vervolg Openstaand | 923 |
| Hoofd Openstaand, Vervolg Historisch | 373 |

**Conclusie:** Filter altijd per werkbon, niet per keten.

### Documentstatus Waarden

| Documentstatus | Betekenis |
|----------------|-----------|
| Historisch | Gearchiveerd, volledig afgerond |
| Openstaand | Nog in behandeling |
| Gereed | Zeldzaam (~3 records) |

### Status Waarden

| Status | Betekenis |
|--------|-----------|
| Uitgevoerd | Werk is gedaan |
| In uitvoering | Werk wordt uitgevoerd |
| Aanmaak | Nieuw aangemaakt |
| Vervallen | Geannuleerd |

### Niveau Verdeling (WVC)

| Niveau | Aantal | Type |
|--------|--------|------|
| 1 | 743.691 | Hoofdwerkbon |
| 2 | 65.780 | Vervolgbon |
| 3 | 17.460 | Vervolgbon |
| 4+ | ~10.000 | Vervolgbon (tot niveau 66!) |

---

## WVC-Specifieke Bevindingen

### Administratieve Fase

De administratieve fase is een **workflow indicator**, geen error-state:

| Code | Betekenis |
|------|-----------|
| 001 - . | Default/initieel |
| 002 - Gecontroleerd door callcenter-medewerker | Callcenter check |
| 003 - Klaar voor gereedmelden | Algemeen |
| 004 - Klaar voor gereedmelden P6 | P6 systeem |
| 005 - Klaar voor gemelden Trivire | Trivire specifiek |
| 006 - Klaar voor gereedmelden Rhiant | Rhiant specifiek |
| 01-04 | ZZP/inlener workflow |

**Conclusie:** Niet bruikbaar voor filtering op "klaar voor classificatie".

### Opvolgingen

Opvolgingen worden gebruikt voor:
- Monteur → Kantoor communicatie
- Kantoor → Kantoor communicatie
- Workflow tracking

Hebben een eigen `Status` veld (open/afgehandeld).

---

## Factureerstatus Analyse (2025-01-25)

Script: `analyze_factureerstatus.py`

### Training vs Classificatie Data

| Dataset | Filter | Werkbonnen | Kostenregels |
|---------|--------|------------|--------------|
| **Training** | Uitgevoerd + Historisch | 784.586 | 2.5M |
| **Te classificeren** | Uitgevoerd + Openstaand | 4.413 | 39k |

### Factureerstatus per Dataset

#### Training Data (Uitgevoerd + Historisch)
| Factureerstatus | Regels | % | Bedrag |
|-----------------|--------|---|--------|
| Niet Factureren | 2.047.317 | 81% | EUR 6.9M |
| Gefactureerd | 315.939 | 13% | EUR 2.4M |
| Nog te factureren | 164.133 | 6% | EUR 984k |

#### Te Classificeren (Uitgevoerd + Openstaand)
| Factureerstatus | Regels | % | Bedrag |
|-----------------|--------|---|--------|
| Niet Factureren | 34.588 | 87% | EUR 208k |
| Gefactureerd | 3.089 | 8% | EUR 41k |
| Nog te factureren | 1.877 | 5% | EUR 8.7k |

### Factureerstatus Logica

**Niet Factureren (81% van kosten):**
- Default voor "Vaste prijs" (binnen contract)
- Gaat automatisch naar "Niet Factureren"

**Nog te factureren:**
- Ontstaat door factureerwijze om te zetten (naar Regie etc.)
- "Nog te factureren" in Historisch: kosten mogelijk al naar opbrengsten overgezet, maar werkbon nog niet volledig afgehandeld

**Gefactureerd:**
- Kosten zijn overgezet naar opbrengsten en gefactureerd
- "Gefactureerd" in Openstaand (3k regels): kan voorkomen als kosten al zijn overgezet maar werkbon nog niet afgesloten

### Implicaties voor LLM Classificatie

**NIET meegeven aan LLM (geeft antwoord weg):**
- `factureerstatus` - dit is wat we willen voorspellen
- `totaal_opbrengsten` - dit geeft ook het antwoord weg

**WEL meegeven aan LLM:**
- `factureerwijze` - contracttype (Vaste prijs, Regie, etc.)
- `storing` / `oorzaak` codes
- `categorie` (Arbeid, Materiaal, Overig)
- Kostenbedragen en aantallen
- Type werkbon
- Oplossingen en opvolgingen

---

## TODO: "Klaar voor Classificatie" Bepaling

**Vraag:** Hoe bepalen we of een werkbon (Uitgevoerd + Openstaand) klaar is voor classificatie?

### Te Onderzoeken Indicatoren

#### 1. Directe Indicatoren (in werkbon zelf)

| Indicator | Bron | Te analyseren |
|-----------|------|---------------|
| Vervolgbon status | werkbonnen.Werkbonnen | Bon kan "Uitgevoerd" zijn maar vervolgbon nog "In aanmaak" of "In uitvoering" |
| Keten compleetheid | Alle bonnen in keten | Check of ALLE bonnen in keten Uitgevoerd zijn |

#### 2. Opvolgingen (workflow acties)

**TODO: Alle opvolgsoorten ophalen en groeperen**

| Categorie | Opvolgsoorten | Indicatie "niet klaar" |
|-----------|---------------|------------------------|
| Planning | (te bepalen) | Ja/Nee |
| Materiaal | (te bepalen) | Ja/Nee |
| Administratief | (te bepalen) | Ja/Nee |
| Communicatie | (te bepalen) | Nee (informatief) |

**Analyse nodig:** Welke opvolgingen met status != 'Afgehandeld' betekenen dat bon nog niet klaar is?

#### 3. Administratieve Fases

**TODO: Alle administratieve fases ophalen en groeperen**

| Fase Code | Fase Naam | Indicatie "klaar" |
|-----------|-----------|-------------------|
| (te bepalen) | ... | Ja/Nee |

**Analyse nodig:** Zijn er fases die specifiek aangeven dat bon klaar/niet klaar is?

#### 4. Openstaande Bestellingen (WVC-specifiek)

**Belangrijke WVC situatie:** Monteur is bij klant, materiaal is niet aanwezig, bestelling wordt geplaatst.

| Indicator | Bron | Kolom |
|-----------|------|-------|
| Kostenstatus | financieel.Kosten | "Kostenstatus" != 'Definitief' |
| Pakbon status | financieel.Kosten | "Pakbon Status" |
| Kostenbron | financieel.Kosten | "Kostenbron" = 'Inkoop' of 'Pakbon' |

**Analyse nodig:**
- Welke Kostenstatus waarden zijn er?
- Welke Pakbon Status waarden zijn er?
- Combinatie die aangeeft "bestelling nog niet binnen"

### Voorgestelde Aanpak

1. **Inventarisatie (dit document)**
   - [ ] Alle opvolgsoorten ophalen
   - [ ] Alle administratieve fases ophalen
   - [ ] Alle kostenstatus waarden ophalen
   - [ ] Alle pakbon status waarden ophalen

2. **Classificatie met WVC**
   - [ ] Per opvolgsoort: blokkeert dit classificatie?
   - [ ] Per administratieve fase: is dit "klaar"?
   - [ ] Combinaties die "openstaande bestelling" aangeven

3. **Implementatie**
   - [ ] Functie `is_werkbon_klaar(werkbon_key)` bouwen
   - [ ] Integreren in dagelijkse classificatie flow

---

## Applicatie Architectuur (concept)

### Drie Processen

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. HOOFDPROCES: Werkbon Beoordeling                                │
│  ───────────────────────────────────────────────────────────────    │
│                                                                     │
│  Werkbon laden (Uitgevoerd + Openstaand)                            │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────┐                                                │
│  │ Check: Klaar?   │                                                │
│  └────────┬────────┘                                                │
│           │                                                         │
│     ┌─────┴─────┬──────────────┐                                    │
│     ▼           ▼              ▼                                    │
│  ┌──────┐  ┌──────────┐  ┌───────────────┐                          │
│  │KLAAR │  │NIET KLAAR│  │NIET KLAAR     │                          │
│  │      │  │+ actie   │  │GEEN actie     │  ← BIJVANGST!            │
│  └──┬───┘  └────┬─────┘  └───────┬───────┘                          │
│     │           │                │                                  │
│     ▼           ▼                ▼                                  │
│  LLM:        Wacht op        ⚠️ Signaleer:                          │
│  Factureren? actie           "Hier moet iets                        │
│              (bestelling,     mee gebeuren!"                        │
│              vervolgbon)                                            │
│                                                                     │
│  Output: Classificatie + Uitleg                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  2. TESTPROCES: Historische Validatie                               │
│  ───────────────────────────────────────────────────────────────    │
│                                                                     │
│  Input: Werkbon (Uitgevoerd + Historisch)                           │
│         + Werkelijke factureerstatus (BEKEND, maar niet meegeven)   │
│                                                                     │
│         │                                                           │
│         ▼                                                           │
│  LLM classificeert (zonder factureerstatus te zien)                 │
│         │                                                           │
│         ▼                                                           │
│  Vergelijk: LLM uitkomst vs Werkelijke factureerstatus              │
│         │                                                           │
│         ▼                                                           │
│  Output: "Raak percentage" - hoe vaak zitten we goed?               │
│                                                                     │
│  Doel: Valideren dat onze aanpak werkt                              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  3. BATCH ANALYSE: Patronen Leren (nachtelijk/wekelijks)            │
│  ───────────────────────────────────────────────────────────────    │
│                                                                     │
│  Input: Alle historische werkbonnen (784k)                          │
│                                                                     │
│  Analyse:                                                           │
│  - Per contract: facturatiegedrag                                   │
│  - Per storingscode: correlatie met facturatie                      │
│  - Patronen en vuistregels                                          │
│                                                                     │
│  Output: Contract profielen + WVC regels                            │
│          (voeden proces 1 en 2)                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### "Klaar" Status Logica

| Status | Beschrijving | Actie |
|--------|--------------|-------|
| **KLAAR** | Geen open opvolgingen, geen openstaande bestellingen, keten compleet | → LLM classificatie |
| **NIET KLAAR + actie** | Bestelling gedaan, vervolgbon ingepland, opvolging open | → Wachten |
| **NIET KLAAR + GEEN actie** | Lijkt niet klaar, maar er staat niets uit | → ⚠️ Signaleren! |

### UI Flows in Applicatie

| Use Case | Beschrijving |
|----------|--------------|
| **Dagelijkse beoordeling** | Laad Uitgevoerd+Openstaand → toon "klaar" status → classificeer |
| **Handmatig laden** | Gebruiker laadt specifieke bon (ook historisch) → LLM analyse |
| **Bulk test** | Laad N historische bonnen → vergelijk LLM vs werkelijk |
| **Analyse dashboard** | Toon patronen uit batch analyse |

---

## Begrippen: Classificatie vs Validatie

> **Dit is belangrijk om te begrijpen!**

### Classificatie = Het AI Oordeel

```
┌─────────────────────────────────────────────────────────────────┐
│  CLASSIFICATIE                                                  │
│  ─────────────────────────────────────────────                  │
│                                                                 │
│  Input:   Werkbon verhaal + Contract tekst                      │
│           (GEEN factureerstatus!)                               │
│                                                                 │
│  Proces:  AI leest werkbon en contract                          │
│           AI beoordeelt: past dit binnen het contract?          │
│                                                                 │
│  Output:  JA     = binnen contract (niet factureren)            │
│           NEE    = buiten contract (wel factureren)             │
│           ONZEKER = twijfel, handmatige review nodig            │
│                                                                 │
│  Dit is wat de AI DENKT dat het antwoord is.                    │
└─────────────────────────────────────────────────────────────────┘
```

Classificatie kan je uitvoeren op:
- **Historische werkbonnen** (al afgerond)
- **Openstaande werkbonnen** (nog niet gefactureerd)

### Validatie = Classificatie + Vergelijking

```
┌─────────────────────────────────────────────────────────────────┐
│  VALIDATIE                                                      │
│  ─────────────────────────────────────────────                  │
│                                                                 │
│  Stap 1: CLASSIFICATIE (zie hierboven)                          │
│          AI geeft oordeel: JA / NEE / ONZEKER                   │
│                                                                 │
│  Stap 2: WERKELIJKE FACTUREERSTATUS OPHALEN                     │
│          ════════════════════════════════════                   │
│          Kijk in database: is deze werkbon gefactureerd?        │
│          - Opbrengsten > 0  →  "werkelijk = NEE" (gefactureerd) │
│          - Opbrengsten = 0  →  "werkelijk = JA"  (niet gefact.) │
│                                                                 │
│          ⚠️ Dit gebeurt PAS NA de classificatie!                │
│          ⚠️ De AI ziet deze info NIET tijdens classificatie!    │
│                                                                 │
│  Stap 3: VERGELIJKEN                                            │
│          ════════════════════════════════════                   │
│          AI zegt: JA    Werkelijk: JA   → ✅ Correct            │
│          AI zegt: NEE   Werkelijk: NEE  → ✅ Correct            │
│          AI zegt: JA    Werkelijk: NEE  → ❌ False negative     │
│          AI zegt: NEE   Werkelijk: JA   → ❌ False positive     │
│                                                                 │
│  Output: HIT RATE = % correcte classificaties                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Validatie kan ALLEEN op historische werkbonnen!**
(want alleen daar kennen we de werkelijke factureerstatus)

### Waarom dit onderscheid?

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  VALIDATIE is om te TESTEN of de aanpak werkt                   │
│  ─────────────────────────────────────────────                  │
│  "Hebben we de AI goed geïnstrueerd?"                           │
│  "Zijn de contract teksten duidelijk genoeg?"                   │
│  "Zit de AI er vaak goed?"                                      │
│                                                                 │
│  CLASSIFICATIE is om PRODUCTIE werk te doen                     │
│  ─────────────────────────────────────────────                  │
│  "Adviseer mij over deze openstaande werkbon"                   │
│  "Moet ik dit factureren of niet?"                              │
│                                                                 │
│  Je doet eerst VALIDATIE (pilot fase)                           │
│  └─ totdat hit rate >80%                                        │
│                                                                 │
│  Dan pas CLASSIFICATIE op openstaande bonnen (productie)        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Samenvatting

| Aspect | Classificatie | Validatie |
|--------|---------------|-----------|
| **Wat** | AI oordeel | AI oordeel + vergelijking |
| **Wanneer** | Altijd | Alleen bij historische data |
| **Doel** | Advies geven | Testen of het werkt |
| **Output** | JA/NEE/ONZEKER | Hit rate + foutanalyse |
| **Database velden** | `classificatie` | `classificatie` + `werkelijke_classificatie` |

---

## Pilot Scope (Januari 2026)

### Historische Data: Twee Doelen

```
┌─────────────────────────────────────────────────────────────────────┐
│  HISTORISCHE DATA (Uitgevoerd + Historisch)                         │
│  ─────────────────────────────────────────                          │
│                                                                     │
│  Doel 1: VALIDATIE (pilot)                                          │
│  ─────────────────────────                                          │
│  - Steekproef van ~100-500 werkbonnen                               │
│  - AI classificeert ZONDER factureerstatus te zien                  │
│  - Vergelijk met werkelijke factureerstatus                         │
│  - Bereken hit rate: "zitten we vaak goed?"                         │
│  - Itereren tot hit rate acceptabel is                              │
│                                                                     │
│  Doel 2: TRAINING / ML (fase 2 - out of scope pilot)                │
│  ─────────────────────────────────────────────────                  │
│  - Analyse van 784k werkbonnen                                      │
│  - Patronen leren (storingscode → facturatie)                       │
│  - Contract profielen genereren                                     │
│  - Machine learning / clustering                                    │
│  - Verrijken van contract context                                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Belangrijk onderscheid:**
- **Validatie** = "werkt onze aanpak?" → Pilot scope
- **Training** = "leer automatisch patronen" → Fase 2

### Wat WEL in de Pilot

| Component | Beschrijving |
|-----------|--------------|
| Contract import | Word/Excel → tekst → database |
| Contract koppeling | Fuzzy matching + handmatige correctie |
| "Klaar" check | Drie-state logic (KLAAR / WACHT / BIJVANGST) |
| AI classificatie | Per kostenregel: JA / NEE / ONZEKER |
| **Validatie** | Hit rate meten tegen historische data (steekproef) |
| Export | CSV met resultaten |

### Wat NIET in de Pilot

| Component | Reden | Fase |
|-----------|-------|------|
| **Training / ML** | Eerst valideren dat basis werkt | 2 |
| Batch analyse (784k) | Complexiteit, niet nodig voor pilot | 2 |
| Automatische patronen | Eerst hit rate bewijzen | 2 |
| Systeem integratie | Pilot is standalone | 2 |
| Real-time verwerking | Batch is voldoende voor pilot | 2 |

### Pilot Stappen

```
1. Contracten ────────────────────────────────────────────────────────
   WVC levert contracten → Notifica verwerkt → WVC controleert koppelingen

2. Validatie (HIT RATE) ──────────────────────────────────────────────
   Laad ~100 HISTORISCHE werkbonnen
   │
   ├─ AI classificeert (zonder factureerstatus te zien)
   │
   └─ Vergelijk met werkelijke factureerstatus
      │
      └─ Bereken hit rate: % correct geclassificeerd
         - Doel: >80% correct
         - < 5% false negatives (gemiste facturatie)

3. Iteratie ──────────────────────────────────────────────────────────
   Bij lage hit rate:
   - Verbeter contract teksten (LLM Ready)
   - Voeg context toe
   - Herhaal validatie

4. Classificatie OPENSTAAND ──────────────────────────────────────────
   Na validatie:
   │
   ├─ Laad ~4.400 OPENSTAANDE werkbonnen
   │
   ├─ Per werkbon: "Klaar" check
   │   ├─ KLAAR ────────────────→ AI classificatie
   │   ├─ NIET KLAAR + actie ───→ Wachten (toon reden)
   │   └─ NIET KLAAR geen actie → BIJVANGST! (signaleer)
   │
   └─ Output: classificatie per kostenregel + uitleg

5. WVC Review ────────────────────────────────────────────────────────
   - Bekijk classificaties
   - Valideer steekproef
   - Beoordeel bijvangst werkbonnen
   - Feedback voor verbetering

6. Evaluatie ─────────────────────────────────────────────────────────
   Hit rate >80% + positieve feedback → Go voor fase 2
```

### Success Criteria

| Metric | Doel | Toelichting |
|--------|------|-------------|
| Hit rate | >80% | % correcte classificaties op historische data |
| False negatives | <5% | Gemiste facturatie-kansen |
| Onzeker | <15% | Acceptabel % voor handmatige review |
| WVC feedback | Positief | Bruikbaar in dagelijkse praktijk |

---

## Retroactieve Validatie (fase 2 - concept)

> **Niet in pilot, wel op de roadmap**

### Het Idee

Openstaande werkbonnen die vandaag geclassificeerd worden, worden later historisch.
Dan kunnen we achteraf valideren of de AI gelijk had.

```
┌─────────────────────────────────────────────────────────────────┐
│  RETROACTIEVE VALIDATIE                                         │
│  ─────────────────────────────────────────────                  │
│                                                                 │
│  Vandaag (januari 2026):                                        │
│  ─────────────────────────────────────────────                  │
│  Werkbon X is OPENSTAAND                                        │
│  └─ AI classificeert: "NEE" (moet gefactureerd worden)          │
│  └─ Opslaan in database: classificatie = "NEE", modus = "class" │
│                                                                 │
│  Over 1 maand (februari 2026):                                  │
│  ─────────────────────────────────────────────                  │
│  Werkbon X is nu HISTORISCH geworden                            │
│  └─ Factureerstatus bekend: wel/niet gefactureerd               │
│  └─ We kunnen nu valideren:                                     │
│     ├─ Ophalen oude classificatie uit database                  │
│     ├─ Ophalen werkelijke factureerstatus                       │
│     └─ Vergelijken: was AI goed?                                │
│                                                                 │
│  Output:                                                        │
│  ─────────────────────────────────────────────                  │
│  - Continue feedback loop                                       │
│  - Hit rate over tijd meten                                     │
│  - Trends zien: wordt AI beter/slechter?                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Database Vereisten

Om dit later mogelijk te maken, slaan we nu al op:

| Veld | Doel |
|------|------|
| `werkbon_id` | Identificatie voor terugvinden |
| `hoofdwerkbon_key` | Link naar datawarehouse |
| `modus` | "validatie" of "classificatie" |
| `classificatie` | AI oordeel (JA/NEE/ONZEKER) |
| `werkelijke_classificatie` | Leeg bij classificatie, later in te vullen |
| `created_at` | Wanneer geclassificeerd |

### Toekomstige Flow

```
1. Periodiek (wekelijks/maandelijks):
   └─ Zoek classificaties waar:
      ├─ modus = "classificatie"
      ├─ werkelijke_classificatie IS NULL
      └─ werkbon nu HISTORISCH is in datawarehouse

2. Voor elke gevonden classificatie:
   └─ Haal factureerstatus op uit datawarehouse
   └─ Vul werkelijke_classificatie in
   └─ Markeer als "gevalideerd"

3. Rapportage:
   └─ Hit rate per periode
   └─ Trends over tijd
   └─ Welke type fouten maken we?
```

### Waarom niet in pilot?

- Vereist wachttijd (werkbonnen moeten eerst historisch worden)
- Extra complexiteit in UI
- Pilot focus = basis werkend krijgen

**Wel belangrijk:** Database model moet dit ondersteunen (doet het al).

---

## Training Data Strategie (fase 2 - concept)

### Twee-lagen Architectuur

```
┌─────────────────────────────────────────────────────────────┐
│  BATCH ANALYSE (nachtelijk/wekelijks)                       │
│  ─────────────────────────────────────────                  │
│  Input: Uitgevoerd + Historisch (784k werkbonnen)           │
│                                                             │
│  Leert:                                                     │
│  1. WVC werkwijze patronen                                  │
│  2. Per-contract facturatiegedrag                           │
│  3. Storing→Facturatie correlaties                          │
│                                                             │
│  Output: "Contract Profielen" + "WVC Regels"                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  DAGELIJKSE CLASSIFICATIE                                   │
│  ─────────────────────────────────────────                  │
│  Input:                                                     │
│  - Werkbon verhaal (nieuwe bon)                             │
│  - Contract tekst (llm_ready)                               │
│  - Contract profiel (uit batch analyse)                     │
│  - WVC regels (uit batch analyse)                           │
│                                                             │
│  Output: Classificatie + Uitleg                             │
└─────────────────────────────────────────────────────────────┘
```

### Batch Analyse: Wat Leren We?

#### 1. WVC Werkwijze Patronen
| Patroon | Analyse |
|---------|---------|
| Welke storingscodes leiden vaak tot "buiten contract"? | Correlatie storing → factureerstatus |
| Welke oplossingscodes? | Correlatie oplossing → factureerstatus |
| Combinaties van codes? | Multi-factor analyse |
| Seizoensgebonden? | Tijd-analyse |

#### 2. Per-Contract Facturatiegedrag
| Vraag | Analyse |
|-------|---------|
| Hoeveel % wordt gefactureerd bij dit contract? | Ratio binnen/buiten |
| Welke werkbon-types worden gefactureerd? | Type → facturatie mapping |
| Grensbedragen? | Bedrag-analyse |
| Uitzonderingspatronen? | Outlier detectie |

**Voorbeeld output per contract:**
```json
{
  "contract_id": 123,
  "profiel": {
    "facturatie_ratio": 0.15,
    "vaak_gefactureerd": ["storing X", "oorzaak Y"],
    "nooit_gefactureerd": ["storing A", "storing B"],
    "grens_bedrag": 500,
    "opmerkingen": "Materiaal boven €500 vaak buiten contract"
  }
}
```

### Output van Batch Analyse

De batch analyse verrijkt twee dingen:

#### 1. WVC Werkwijze (globaal)
Opgeslagen als configuratie/regels die voor alle classificaties gelden.

#### 2. Contract Historisch Profiel (per contract)
```
┌─────────────────────────────────────────────────────────────┐
│  Contract tabel                                             │
│  ─────────────────────────────────────────                  │
│                                                             │
│  id | name | content | llm_context | llm_ready | history    │
│  ───┼──────┼─────────┼─────────────┼───────────┼─────────── │
│     │      │ platte  │ handmatige  │ LLM       │ batch      │
│     │      │ tekst   │ instructies │ vertaling │ analyse    │
│                                                             │
│  llm_ready  = LLM vertaling van content + llm_context       │
│  history    = Historische analyse uit batch (NIEUW)         │
└─────────────────────────────────────────────────────────────┘
```

**Nieuwe kolom `history` bevat:**
```json
{
  "analyse_datum": "2025-01-25",
  "werkbonnen_geanalyseerd": 1234,
  "facturatie_ratio": 0.15,
  "vaak_gefactureerd": ["storing X", "oorzaak Y"],
  "nooit_gefactureerd": ["storing A"],
  "opmerkingen": "Materiaal boven €500 vaak buiten contract"
}
```

**Voordeel:** `llm_ready` blijft puur de contract vertaling, `history` is de data-driven verrijking.

### Kosten-Efficiëntie: Waar LLM, Waar Lokaal?

```
┌─────────────────────────────────────────────────────────────┐
│  LOKAAL (Python/SQL - geen tokens)                          │
│  ─────────────────────────────────────────                  │
│                                                             │
│  Batch analyse (week/maand):                                │
│  - pandas: data aggregatie                                  │
│  - SQL: correlaties, group by's                             │
│  - scikit-learn: patronen, clustering                       │
│                                                             │
│  Output: Contract profielen (JSON), WVC statistieken        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  LLM (tokens - alleen waar nodig)                           │
│  ─────────────────────────────────────────                  │
│                                                             │
│  1. Dagelijkse classificatie:                               │
│     Contract + Werkbon + Profiel → Beslissing               │
│                                                             │
│  2. (Optioneel) Profiel interpretatie:                      │
│     Ruwe statistieken → Leesbare regels                     │
│     "Bij storingscode X wordt 85% gefactureerd"             │
│                                                             │
│  3. (Eenmalig) ML pipeline bouwen:                          │
│     Claude helpt code schrijven, niet data verwerken        │
└─────────────────────────────────────────────────────────────┘
```

**Conclusie:** Batch analyse = Python/SQL lokaal, LLM alleen voor classificatie.

### Lokale Batch Analyse Stack

| Component | Tool | Taak |
|-----------|------|------|
| Data ophalen | SQLAlchemy | Query's naar datawarehouse |
| Aggregatie | pandas | Group by, pivot, correlaties |
| Patronen | scikit-learn | Clustering, feature importance |
| Opslag | JSON/database | Contract profielen |

**Voorbeeld analyse (geen LLM nodig):**
```python
# Per contract: facturatie ratio
df.groupby('contract_id').agg({
    'gefactureerd': 'sum',
    'totaal_kosten': 'sum'
})

# Correlatie storing → facturatie
pd.crosstab(df['storingscode'], df['is_gefactureerd'], normalize='index')

# Top storingscodes die leiden tot facturatie
df[df['is_gefactureerd']].groupby('storingscode').size().nlargest(10)
```

### Implementatie Opties

| Optie | Beschrijving | LLM tokens | Aanbevolen |
|-------|--------------|------------|------------|
| **A: Pure Python/SQL** | Lokale analyse → JSON profielen | 0 | ✅ Ja |
| **B: + LLM interpretatie** | Lokaal + LLM maakt leesbare regels | Laag | Optioneel |
| **C: LLM batch** | LLM analyseert data direct | Hoog | ❌ Nee |

### Vraag aan WVC

**Klopt dit mentale model?**
- Sommige storingscodes zijn "altijd binnen contract"
- Sommige zijn "altijd buiten contract"
- Sommige zijn "afhankelijk van..." (wat?)

**Hebben jullie al interne regels/vuistregels?**
- "Lekkage boven X uur is buiten contract"
- "Materiaal type Y is altijd binnen contract"
- etc.

Dit zou de batch analyse kunnen valideren of versnellen.
