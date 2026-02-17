# Contract Checker — Intake nieuwe klant

> Dit document gebruiken we om per woningbouwvereniging de juiste context op te halen.
> Vul dit in samen met de contactpersoon van de klant, **voordat** we de AI gaan configureren.

---

## 1. Basisgegevens

| Veld | Invullen |
|------|----------|
| Woningbouwvereniging | |
| Contactpersoon | |
| Debiteurcode(s) in Syntess | |
| Type installaties | ☐ Individueel (eigen ketel) ☐ Collectief (ketelhuis/stadsverwarming) ☐ Beide |

---

## 2. Contracttabel

Upload of kopieer de contracttabel (Excel/PDF) met daarin:
- Welke werkzaamheden **wel** onder contract vallen
- Welke werkzaamheden **niet** onder contract vallen (factureren)
- Eventuele vaste prijsafspraken

> **Let op:** de contracttabel alleen is niet genoeg. De vragen hieronder zijn minstens zo belangrijk.

---

## 3. Basisprincipe van het contract

*Beschrijf in eigen woorden hoe het contract werkt. Wat is het uitgangspunt?*

Voorbeelden van wat we zoeken:
- "Alles binnen 2 meter van de ketel is contract, daarbuiten meerwerk"
- "Alles binnen de mantel van de ketel is contract"
- "Alleen de uitsluitingslijst is meerwerk, de rest valt eronder"

```
Beschrijving:


```

---

## 4. Uitzonderingen en bijzonderheden

*Welke regels wijken af van het basisprincipe? Dit zijn vaak de regels die niet in de tabel staan maar die jullie wel altijd toepassen.*

Per uitzondering graag invullen:

| # | Situatie | Regel | Waarom? |
|---|----------|-------|---------|
| 1 | *Voorbeeld: Radiatorkranen* | *Altijd contract, ook op afstand* | *Vallen onder appendages* |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

---

## 5. Prioriteitsregels

*Soms zijn er conflicterende signalen. Welke regel wint dan?*

Voorbeelden:
- "Probleem veroorzaakt door derde → altijd meerwerk, ook als het een ketelonderdeel is"
- "Huurdersgedrag → altijd factureren"
- "Lekkage onder de ketel maar oorzaak is bevriezing → toch meerwerk"

```
Prioriteitsregels:


```

---

## 6. Veelvoorkomende twijfelgevallen

*Welke werkbonnen leiden intern tot discussie? Situaties waar je even moet nadenken of het contract of meerwerk is.*

| # | Situatie | Hoe beoordelen jullie dit? |
|---|----------|---------------------------|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |

---

## 7. Storingscodes en oorzaakcodes

*Zijn er specifieke codes die altijd een bepaalde uitkomst hebben?*

| Code | Omschrijving | Altijd contract of altijd meerwerk? | Toelichting |
|------|-------------|-------------------------------------|-------------|
| | | | |
| | | | |
| | | | |

Voorbeeld uit de praktijk (Trivire):
- Storingscode 006.1 "Lekkage onder de ketel" → altijd contract
- Storingscode 006.2 "Lekkage aan de installatie" → altijd meerwerk
- Oorzaakcode 900 "Probleem door derde" → altijd meerwerk, gaat voor op alles

---

## 8. Locatieregels

*Maakt het uit waar in de woning het probleem zich voordoet?*

| Locatie | Binnen contract? | Opmerking |
|---------|-----------------|-----------|
| Ketelkast / meterkast | | |
| Keuken | | |
| Badkamer | | |
| Slaapkamer / woonkamer | | |
| Kruipruimte / vloer | | |
| Dak / gevel | | |

---

## 9. Speciale apparatuur

*Hoe worden deze typen behandeld?*

| Apparaat | In contract? | Bijzonderheden |
|----------|-------------|----------------|
| CV-ketel | | |
| WTW-unit | | |
| Warmtepomp | | |
| Boiler (gas/elektrisch) | | |
| Zonnecollector / zonneboiler | | |
| Geiser / moederhaard | | |
| Vloerverwarming | | |
| Gevelkachel / luchtverhitter | | |

---

## 10. Steekproef werkbonnen

> Na het configureren van de AI hebben we een steekproef nodig om te testen.

**Wat we vragen:**
- Beoordeel 30-40 werkbonnen in de tool
- Geef per bon aan: **JA** (contract), **NEE** (meerwerk), of **TWIJFEL**
- Exporteer het resultaat als CSV

Wij vergelijken jouw beoordeling met die van de AI en sturen bij waar nodig.

---

## Intern gebruik (niet delen met klant)

### Checklist configuratie

- [ ] Contracttabel ontvangen en verwerkt naar `contracts/{klant}.txt`
- [ ] Debiteurcode(s) toegevoegd aan `metadata.json`
- [ ] Individuele contracten bijgewerkt in `individuele_contracten.txt`
- [ ] Collectieve patronen gecontroleerd in `collectieve_patronen.txt`
- [ ] AI-prompt getest met klantspecifieke context
- [ ] Steekproef ontvangen en backtest uitgevoerd
- [ ] Accuracy ≥ 90% behaald
- [ ] Klant gevalideerd en akkoord
