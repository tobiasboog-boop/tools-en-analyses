# Email naar Gerrit - V3 Verbeteringen

**Aan:** Gerrit (WVC)
**Van:** Tobias
**Onderwerp:** RE: Contract Checker - Feedback verwerkt, V3 staat klaar

---

Hoi Gerrit,

Top, bedankt voor je test! 40 bonnen is een mooie steekproef. Ik heb alle bevindingen geanalyseerd en direct verwerkt.

## RESULTATEN V2 TEST:
- **23 goed, 10 fout, 7 niet van toepassing (individueel contract)**
- Accuracy: **70%** (excl. individueel contract bonnen)

## WAT IK HEB AANGEPAST (V3):

Op basis van jouw feedback heb ik 6 nieuwe regels toegevoegd aan de AI:

| # | Wat ging fout | Nieuwe regel |
|---|---------------|-------------|
| 1 | Radiatorkranen als NEE geclassificeerd | **Radiatorkranen ALTIJD JA**, ook > 2 meter van ketel |
| 2 | Bijvullen/ontluchten als TWIJFEL | **Installatie vullen/ontluchten ALTIJD JA** |
| 3 | Probleem derden als TWIJFEL | **Oorzaak derden/electricien = NEE** (factureren) |
| 4 | Vloerverwarming als JA | **Vloerverwarming ALTIJD NEE** |
| 5 | Lekkage keuken als JA | **Lekkage leiding buiten ketelkast = NEE** |
| 6 | Tapwaterboiler als JA | **Tapwaterboiler ALTIJD NEE** (regie) |

Dit sluit precies aan bij de contractregels uit jullie "Contractvoorwaarden diverse WBV.xlsx" die ik nu ook heb ingezien.

## 7 BONNEN INDIVIDUEEL CONTRACT:

Die 7 bonnen vielen allemaal onder **centraal ketelhuis** of **HVC stadsverwarming**. Het contract-type filter herkent nu automatisch:
- **Collectief** = centraal ketelhuis, HVC, stadsverwarming
- **Individueel** = alle overige (eigen ketel)

Je kunt nu filteren: "Alle / Alleen individuele installaties / Alleen collectieve systemen"

## VOLGENDE STAP:

V3 staat klaar op dezelfde URL. Zou je nog een test willen doen met een nieuwe set bonnen? Dan kunnen we zien of de accuracy richting 85-90% gaat.

**URL:** https://tools-en-analyses-fsysjwn7jqdcvgwbxgqhuk.streamlit.app/
**Wachtwoord:** `Xk9#mP2$vL7nQ4wR`

Groet,
Tobias
