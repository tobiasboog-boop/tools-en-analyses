# Blobvelden Analyse - Zenith Security (Klant 1229)

**Datum:** 31 januari 2026
**Project:** Pilot werkbon-blobvelden voor semantisch model
**Klant:** Zenith Security (klantnummer 1229)

---

## 1. Samenvatting

Zenith Security wil werkboninformatie uitbreiden in het semantisch model van SynthesAnalyse. Specifiek gaat het om **blobvelden**: vrije tekstvelden in Syntess waarin ongestructureerde maar waardevolle informatie staat, vaak ingevuld door monteurs, planning of andere afdelingen.

Deze analyse identificeert welke blobvelden relevant zijn voor werkbonrapportage en welke inzichten daaruit te halen zijn.

---

## 2. Dataset Overzicht

**Locatie blobvelden:**
```
C:\Users\tobia\OneDrive - Notifica B.V\Documenten - Sharepoint Notifica intern\106. Development\GRIP\AI\1229\
```

**Totaal aantal bestanden:** 72.482
**Aantal submappen:** 30 (waarvan 13 leeg)

### 2.1 Volumeverdeling

| Map | Bestanden | Percentage |
|-----|-----------|------------|
| AT_MWBSESS | 29.283 | 40,4% |
| AT_DOCUMENT | 24.720 | 34,1% |
| AT_UITVBEST | 12.446 | 17,2% |
| AT_INSTALL | 2.517 | 3,5% |
| AT_BESTPAR | 1.099 | 1,5% |
| AT_WERK | 561 | 0,8% |
| AT_GEBOUW | 353 | 0,5% |
| AT_OPVSRT | 2 | <0,1% |
| **Totaal** | **72.482** | **100%** |

---

## 3. Relevante Blobvelden voor Werkbonrapportage

Na analyse zijn **4 blobvelden** geidentificeerd als relevant voor werkbonrapportage:

### 3.1 NOTITIE.txt (AT_MWBSESS)

| Kenmerk | Waarde |
|---------|--------|
| **Aantal bestanden** | 16.521 |
| **Formaat** | RTF (Rich Text Format) |
| **Bron** | Monteurs / uitvoerders |
| **Relevantie** | HOOG |

**Inhoud:** Vrije notities van monteurs over uitgevoerde werkzaamheden.

**Voorbeeldinhoud:**
```
"Nog niet klaar geen patchingen gemaakt enzzz verdere info bij Tim bekend"
```

**Mogelijke inzichten:**
- Status van werkzaamheden
- Openstaande punten
- Communicatie tussen monteurs
- Problemen tijdens uitvoering

---

### 3.2 TEKST.txt (AT_UITVBEST)

| Kenmerk | Waarde |
|---------|--------|
| **Aantal bestanden** | 12.446 |
| **Formaat** | RTF (Rich Text Format) |
| **Bron** | Meldingen / planning |
| **Relevantie** | HOOG |

**Inhoud:** Storingsmeldingen en werkbeschrijvingen.

**Voorbeeldinhoud:**
```
"Twan Lakerveld 15-03-2021 10:47:
Klant: Storing:
STORING
12-03-2021 15:15 KF373: Beschrijving Melding
- Het alarm geeft weer diverse foutmeldingen bij het inschakelen. graag controle."
```

**Mogelijke inzichten:**
- Type storing
- Urgentie/prioriteit
- Klantcommunicatie
- Tijdstip van melding
- Contactpersonen

---

### 3.3 INGELEVERDE_URENREGELS.txt (AT_MWBSESS)

| Kenmerk | Waarde |
|---------|--------|
| **Aantal bestanden** | 1.015 |
| **Formaat** | XML |
| **Bron** | Urenregistratie monteurs |
| **Relevantie** | HOOG |

**Inhoud:** Gestructureerde urenregistratie met projectcodes en taakbeschrijvingen.

**Voorbeeldstructuur:**
```xml
<Uurregels>
  <Uuregel>
    <Datum>2021-03-15</Datum>
    <Begintijd>08:00</Begintijd>
    <Eindtijd>12:00</Eindtijd>
    <Aantal>4</Aantal>
    <Taakcode>10</Taakcode>
    <Regelomschrijving>Preventiecoach werkzaamheden Amsterdam</Regelomschrijving>
    <Tariefsoort>STD</Tariefsoort>
    <Projectcode>R000002.14</Projectcode>
  </Uuregel>
</Uurregels>
```

**Mogelijke inzichten:**
- Gewerkte uren per taak
- Projecttoewijzing
- Type werkzaamheden
- Tariefsoorten

---

### 3.4 GC_INFORMATIE.txt (AT_WERK)

| Kenmerk | Waarde |
|---------|--------|
| **Aantal bestanden** | 561 |
| **Formaat** | RTF (Rich Text Format) |
| **Bron** | Werkopdrachten / cases |
| **Relevantie** | HOOG |

**Inhoud:** Casebeschrijvingen, werkbon-verwijzingen en onderzoeksinstructies.

**Voorbeeldinhoud:**
```
"Wordt gefactureerd volgens de werkbon"

"Beeldverslag maken van de vermoedelijke diefstal en verklaring medewerkster opnemen"
"Albert Heijn 1527, Vondellaan 200 Utrecht"
"ASM: Nadia Hidraoui te bereiken via 06-57147244"
```

**Mogelijke inzichten:**
- Werkbon-facturatiecontext
- Casusdetails en onderzoeksopdrachten
- Locatiegegevens
- Contactpersonen
- Opdrachtomschrijvingen

---

## 4. Niet-relevante Blobvelden

De volgende blobvelden zijn geanalyseerd maar **niet relevant** voor werkbonrapportage:

| Blobveld | Reden niet relevant |
|----------|---------------------|
| HANDTEKENING.jpg (AT_MWBSESS) | Afbeeldingen, geen tekstuele data |
| GC_INFORMATIE.txt (AT_DOCUMENT) | Administratieve notities, geen werkbon-context |
| GC_INFORMATIE.txt (AT_INSTALL) | Technische installatie-info, vaak leeg |
| GC_INFORMATIE.txt (AT_GEBOUW) | Minimale locatie-info, beperkte waarde |
| NOTITIE.bin (AT_MWBSESS) | Binair formaat, moeilijk te parsen |
| AFBEELDING.jpg (diverse) | Afbeeldingen, geen tekstuele data |

---

## 5. Bestaand Semantisch Model (SynthesAnalyse)

Het huidige semantisch model bevat al werkbon-tabellen:

### 5.1 Tabel: Werkbonnen
- WerkbonDocumentKey (PK)
- Werkboncode, Werkbon titel
- Documentstatus, Uitvoeringstatus
- Monteur, Klant, Debiteur
- Datums (aanmaak, melding, afspraak, oplevering)
- Prioriteit, Type, Soort
- ProjectKey, KostenplaatsKey

### 5.2 Tabel: Werkbonparagrafen
- WerkbonparagraafKey (PK)
- WerkbonDocumentKey (FK)
- Storing, Oorzaak, Oplossing
- Plandatum, Uitgevoerd op
- Factureerwijze

### 5.3 Wat ontbreekt
De ongestructureerde blobveld-data is **niet** opgenomen in het huidige model. Dit zijn juist de vrije tekstvelden met waardevolle operationele informatie.

---

## 6. Voorstel: Extra Tabel voor Semantisch Model

Op basis van de analyse wordt voorgesteld een extra tabel toe te voegen:

### Tabel: WerkbonBlobvelden

| Kolom | Bron | Beschrijving |
|-------|------|--------------|
| WerkbonDocumentKey | Koppeling | Foreign key naar Werkbonnen |
| MonteurNotitie | AT_MWBSESS/NOTITIE.txt | Vrije notitie van monteur |
| StoringMelding | AT_UITVBEST/TEKST.txt | Storingsomschrijving |
| WerkContext | AT_WERK/GC_INFORMATIE.txt | Casebeschrijving/opdracht |
| UrenToelichting | AT_MWBSESS/INGELEVERDE_URENREGELS.txt | Samenvatting uren |
| AICategorie | AI-analyse | Door AI bepaalde classificatie |
| AISamenvatting | AI-analyse | AI-gegenereerde samenvatting |

---

## 7. Vervolgstappen

### Stap 1: Data-extractie (Scripts)
- RTF naar tekst conversie
- XML parsing voor urenregels
- Koppeling met werkbon-ID's

### Stap 2: Prototype Streamlit App
- Zoeken in blobvelden
- AI-analyse en categorisatie
- Samenvatten van ongestructureerde data

### Stap 3: Integratie Semantisch Model
- Extra tabel definie voor klant 1229
- ETL-proces voor blobveld-extractie
- Power BI rapportage-uitbreiding

---

## 8. Technische Details

### 8.1 Bestandsnaamconventie
```
[ID].[VELDTYPE].[EXTENSIE]
Voorbeeld: 256826.NOTITIE.txt
```

### 8.2 RTF Parsing
De meeste tekstbestanden zijn RTF-encoded. Voorbeeld:
```
{\rtf1\ansi\deff0{\fonttbl{\f0 Verdana;}}
\viewkind4\uc1\pard\lang1043\f0\fs17 Dit is de tekst\par}
```

### 8.3 Locatie bronbestanden
```
Base path: C:\Users\tobia\OneDrive - Notifica B.V\Documenten - Sharepoint Notifica intern\106. Development\GRIP\AI\1229\

Relevante submappen:
- AT_MWBSESS\        (NOTITIE.txt, INGELEVERDE_URENREGELS.txt)
- AT_UITVBEST\       (TEKST.txt)
- AT_WERK\           (GC_INFORMATIE.txt)
```

---

*Document gegenereerd t.b.v. pilot werkbon-blobvelden Zenith Security*
