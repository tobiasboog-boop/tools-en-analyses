# Email naar Gerrit - Phase 2 Contract Filter Geïmplementeerd

**Aan:** Gerrit (WVC)
**Van:** Tobias
**Onderwerp:** Contract Checker V2 - Contract-type filter werkend

---

Hoi Gerrit,

Bedankt voor je duidelijke feedback! Op basis van je antwoorden heb ik direct het contract-type filter geïmplementeerd.

## ✅ WAT IS GEÏMPLEMENTEERD:

### Contract-type filter (WERKEND)
De app kan nu filteren op individueel vs collectief:

**HOE HET WERKT:**
1. **Radio buttons** boven werkbonnen lijst: "Alle / Alleen individueel / Alleen collectief"
2. **Matching logica**: App leest bestand `individuele_contracten.txt` met lijst individuele contracten
3. **Filtering**: Werkbonparagraaf naam wordt gematcht tegen lijst:
   - Match gevonden → Individueel contract
   - Geen match → Collectief contract (incl. Thuisvester & Bazalt)
4. **Werkbonnen filtering**: Alleen geselecteerde type wordt getoond

**VOORBEELD MATCHING:**
- Bestand bevat: "OH contract"
- Werkbon met paragraaf "OH contract aanvulling 1/3/2023 Trivire" → match → INDIVIDUEEL
- Werkbon met paragraaf "Viessmann collectief" → geen match → COLLECTIEF

**WAT JULLIE NOG MOETEN DOEN:**
Het bestand `/data/individuele_contracten.txt` bevat nu placeholder data. Jullie moeten de volledige lijst uit "Contractvoorwaarden diverse WBV.xlsx" hierin zetten (één contract naam per regel). Het bestand zelf bevat uitgebreide instructies.

## 📋 VOOR VOLGENDE FASE (na pilot):

### Garantie classificatie
Op basis van je feedback begrijp ik:
- Garantieperiode staat in besteksparagraaf in Syntess (van...tm datums)
- Werkbonnen binnen garantie moeten classificatie krijgen met label "GARANTIE"
- Intern factureren aan installatie afdeling

**WAT NODIG IS:**
De garantie van/tm datums staan **niet in de huidige werkbonparagrafen export**. Om dit te implementeren hebben we nodig:

**Optie A**: Garantie velden toevoegen aan werkbonparagrafen export
  - Kolommen: `garantie_van`, `garantie_tm` per paragraaf

**Optie B**: Aparte koppeltabel besteksparagraaf → garantieperiode
  - Format: `besteksparagraaf_naam, garantie_van, garantie_tm`

Zodra deze data beschikbaar is kan ik:
- "GARANTIE" als 4e classificatie optie toevoegen (naast JA/NEE/TWIJFEL)
- Automatische check: werkbon binnen garantie → classificeer als "GARANTIE"
- Aparte export garantie gevallen

**Schatting:** €1.5-2k voor garantie classificatie implementatie (na data beschikbaar)

---

## 🚀 TEST DE NIEUWE FILTER:

**URL:** https://tools-en-analyses-fsysjwn7jqdcvgwbxgqhuk.streamlit.app/
**Wachtwoord:** `Xk9#mP2$vL7nQ4wR`

**Testen:**
1. Open de app
2. Zie nieuwe "Contract-type filter" boven de werkbonnen lijst
3. Selecteer "Alleen individueel" of "Alleen collectief"
4. Werkbonnen lijst wordt direct gefilterd
5. (Let op: lijst individuele contracten moet je nog aanvullen voor accurate filtering)

Laat weten hoe dit werkt voor jullie, en of jullie de individuele contracten lijst kunnen aanleveren!

Groet,
Tobias
