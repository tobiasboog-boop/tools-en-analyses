# Contract Checker - Handleiding

## Wat doet deze tool?

De Contract Checker analyseert automatisch of uitgevoerde werkbonnen binnen of buiten het servicecontract vallen. Dit helpt bij het bepalen welke werkzaamheden gefactureerd moeten worden aan de klant.

---

## Gebruiksaanwijzing

### Stap 1: Werkbonnen laden
Klik op **"Laad werkbonnen"** om de volgende batch werkbonnen op te halen. De app toont alleen werkbonnen:
- Met status "Uitgevoerd" en "Openstaand"
- Van de afgelopen 30 dagen
- Waarvoor een contract bekend is

### Stap 2: Classificeren
Klik op **"Classificeer batch"** om de werkbonnen te laten analyseren. Per werkbon zie je:

| Resultaat | Betekenis |
|-----------|-----------|
| **JA** (groen) | Valt binnen contract - niet factureren |
| **NEE** (rood) | Valt buiten contract - wel factureren |
| **TWIJFEL** (oranje) | Handmatig controleren |

### Stap 3: Resultaten beoordelen
Klik op een werkbon om de details te zien:
- **Toelichting**: Waarom deze classificatie
- **Contract referentie**: Welk artikel van toepassing is
- **Confidence**: Hoe zeker het model is (0-100%)

### Stap 4: Exporteren
Download de resultaten als CSV voor verdere verwerking.

---

## Instellingen

### Drempelwaardes
In de zijbalk kun je de drempelwaardes aanpassen:

- **JA drempel** (standaard 85%): Minimale zekerheid voor "binnen contract"
- **NEE drempel** (standaard 85%): Minimale zekerheid voor "buiten contract"

Bij lagere zekerheid wordt het resultaat "TWIJFEL" - deze werkbonnen verdienen handmatige controle.

### Batch grootte
Bepaal hoeveel werkbonnen per keer worden geladen (1-50).

---

## Veelgestelde vragen

**Waarom zie ik sommige werkbonnen niet?**
De app toont alleen werkbonnen waarvoor een contract gekoppeld is in het systeem. Werkbonnen zonder contractkoppeling worden overgeslagen.

**Hoe betrouwbaar is de classificatie?**
De AI analyseert de werkbon tegen het volledige contract. Bij twijfel geeft het systeem "TWIJFEL" - controleer deze handmatig.

**Kan ik een classificatie corrigeren?**
De resultaten zijn adviserend. Je kunt de CSV exporteren en handmatig aanpassingen doen.

---

## Technische achtergrond

*Voor de liefhebber*

### Architectuur

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Streamlit UI   │────▶│  WerkbonKeten    │────▶│  PostgreSQL │
│                 │     │  Service         │     │  Database   │
└────────┬────────┘     └──────────────────┘     └─────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  Classificatie  │────▶│  Claude API      │
│  Service        │     │  (Haiku model)   │
└─────────────────┘     └──────────────────┘
```

### Data flow

1. **Werkbon ophalen**: De WerkbonKetenService haalt alle relevante data op:
   - Hoofdwerkbon + eventuele vervolgbonnen
   - Werkbonparagrafen met type werkzaamheden
   - Kostenregels (arbeid, materiaal, overig)
   - Storingscodes en oorzaken

2. **Verhaal bouwen**: De VerhaalBuilder zet de ruwe data om in een leesbaar narratief dat de AI kan analyseren.

3. **Contract matchen**: Het systeem zoekt het juiste contract via de debiteur-contract koppeling.

4. **AI classificatie**: Claude Haiku analyseert:
   - Type werkzaamheden vs. contractdekking
   - Gebruikte materialen vs. uitsluitingen
   - Storingscodes vs. contractvoorwaarden

5. **Confidence scoring**: Het model geeft een zekerheidspercentage. Bij lage zekerheid wordt "TWIJFEL" geretourneerd.

### Model details

- **Model**: Claude 3 Haiku (Anthropic)
- **Kosten**: ~$0.25 per miljoen input tokens
- **Snelheid**: 2-5 seconden per werkbon
- **Context**: Tot 15.000 karakters contract + werkbon verhaal

### Database schema

De app leest uit de volgende tabellen:
- `werkbonnen.Werkbonnen` - Hoofdwerkbonnen en vervolgbonnen
- `werkbonnen.Werkbonparagrafen` - Werkzaamheden per werkbon
- `werkbonnen.Werkbon kosten` - Kostenregels
- `stam.Relaties` - Klant/debiteur informatie
- `contract_checker.contracts` - Contractteksten
- `contract_checker.contract_relatie` - Debiteur-contract koppelingen

---

*Ontwikkeld door Notifica B.V. - Powered by Claude AI*
