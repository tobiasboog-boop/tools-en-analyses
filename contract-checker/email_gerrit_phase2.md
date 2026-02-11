# Email naar Gerrit - Phase 2 Features Toegevoegd

**Aan:** Gerrit (WVC)
**Van:** Tobias
**Onderwerp:** Contract Checker V2 - Garantie & Contract filters toegevoegd

---

Hoi Gerrit,

Bedankt voor je feedback op V2! Ik heb direct de twee extra features toegevoegd die je noemde:

## ✅ WAT IS TOEGEVOEGD:

### 1. **Garantie termijn filter**
Je app heeft nu een garantie filter waarmee je werkbonnen binnen garantie kunt overslaan:
- ⏳ Checkbox "Skip werkbonnen binnen garantie"
- Instelbaar aantal maanden (default 12)
- Werkbonnen jonger dan X maanden worden automatisch overgeslagen

Dit voorkomt dat je garantie gevallen classificeert die intern aan jullie installatie afdeling gefactureerd moeten worden.

### 2. **Contract-type filter (basis)**
Er is nu een contract selectie dropdown toegevoegd:
- 📋 Multiselect met alle beschikbare contracten
- Voorbereiding voor individueel/collectief onderscheid
- UI is klaar, maar koppeling vereist nog jullie input (zie hieronder)

## ❓ WAT NOG ONDUIDELIJK IS:

### Garantie termijn logica:
- **Vraag:** Klopt het dat je garantie termijn berekent vanaf melddatum werkbon?
- **Vraag:** Is 12 maanden de standaard termijn, of verschilt dit per contract?
- **Vraag:** Moet de classificatie wel plaatsvinden maar met een label "GARANTIE", of helemaal overslaan?

Huidige implementatie: Skip werkbonnen < 12 maanden oud (geen classificatie).

### Contract-type mapping:
- **Vraag:** Hoe weet de app welke werkbon bij welk contract hoort?
  - Nu: Via debiteur → koppel naar 1 contract
  - Probleem: Trivire heeft meerdere contracten (individueel + collectief)

- **Vraag:** Staat in "Contractvoorwaarden diverse WBV.xlsx" welk contract individueel/collectief is?

- **Vraag:** Hoe herken je of een werkbon voor collectief vs individueel is?
  - Via adres/locatie?
  - Via een veld in de werkbon data?
  - Via koppeltabel?

## 🔧 VOLGENDE STAPPEN (na pilot):

Als de garantie logica klopt en je de contract mapping specificeert, kunnen we toevoegen:

1. **Garantie verfijningen** (€0.5-1k):
   - Contract-specifieke garantie termijnen
   - Label "GARANTIE" in plaats van skip
   - Export garantie gevallen apart

2. **Contract-type filtering** (€1.5-2.5k):
   - Volledige contract → werkbon mapping
   - Dropdown: "Selecteer contract-type" (individueel/collectief/beide)
   - Automatische filtering op basis van mapping

3. **Combinatie features** (in bovenstaande prijs):
   - Garantie + contract-type in één filter
   - Export per contract-type
   - Dashboard per contract

---

## 🚀 TEST V2 MET NIEUWE FILTERS:

De update is live op dezelfde URL:

**URL:** https://tools-en-analyses-fsysjwn7jqdcvgwbxgqhuk.streamlit.app/
**Wachtwoord:** `Xk9#mP2$vL7nQ4wR`

Test de nieuwe filters en laat weten:
1. Of garantie filter zo werkt zoals gewenst
2. Welke contracten individueel vs collectief zijn
3. Hoe je de koppeling contract → werkbon wilt zien

Dan werk ik dit uit voor productie-rijpe implementatie.

Groet,
Tobias
