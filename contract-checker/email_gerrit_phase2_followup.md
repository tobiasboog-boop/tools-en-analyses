# Email naar Gerrit - Phase 2 Implementatie Plan

**Aan:** Gerrit (WVC)
**Van:** Tobias
**Onderwerp:** RE: Contract Checker V2 - Garantie & Contract filters uitwerking

---

Hoi Gerrit,

Top, bedankt voor je uitgebreide antwoorden! Ik snap nu veel beter hoe jullie garantie en contracten structuur in elkaar zit.

## ✅ WAT IK BEGRIJP:

### 1. Garantie classificatie:
- Elke werkbon is gekoppeld aan een besteksparagraaf in Syntess
- Besteksparagraaf bevat garantieperiode (van ... tm)
- Duur verschilt per besteksparagraaf/installatie
- Werkbonnen binnen garantie moeten WEL geclassificeerd worden, maar met label **"GARANTIE"**
- Deze gevallen worden intern gefactureerd aan jullie installatie afdeling

### 2. Contract-type onderscheid:
- "Contractvoorwaarden diverse WBV.xlsx" bevat ALLEEN individuele contracten
- Alles wat niet in dat bestand staat = collectief contract (incl. Thuisvester en Bazalt)
- Of een werkbon individueel of collectief is hangt af van het gekoppelde contract

## 🔨 WAT IK KAN IMPLEMENTEREN:

### Fase 2A - Contract-type filter (direct implementeerbaar):
Ik kan nu direct bouwen:

1. **Excel inlezen**: "Contractvoorwaarden diverse WBV.xlsx" → lijst individuele contracten
2. **Matching logica**: Match werkbonparagraaf naam tegen contractnamen in Excel
3. **Filter dropdown**: "Toon alleen individueel / collectief / beide"
4. **Resultaat**: Werkbonnen filteren op basis van contract-type

**Aanname:** De "naam" kolom in werkbonparagrafen komt overeen met contract namen in jullie Excel. Klopt dat?

Voorbeelden uit jullie data:
- "OH contract aanvulling 1/3/2023 Trivire"
- "Viessmann Vitodens 100 WB1C"
- "awb 23.29 wt"

**Vraag:** Hoe match ik deze namen precies met jullie Excel contractnamen? Is er een exacte match, of zit er logica in (bijv. eerste deel van de naam)?

### Fase 2B - Garantie classificatie (extra data nodig):
Voor garantie heb ik nog **één ontbrekend puzzelstukje**:

De garantieperiode "van...tm" staat in de besteksparagraaf in Syntess, maar **niet in de geëxporteerde werkbonparagrafen data** die ik nu heb.

**Huidige werkbonparagrafen data bevat:**
- `werkbon_key` (koppeling met werkbon)
- `naam` (bijv. "OH contract aanvulling 1/3/2023 Trivire")
- `factureerwijze` (bijv. "Vaste prijs (binnen contract)")
- `uitgevoerd_op` (uitvoerdatum)

**Wat ik nodig heb:**
- Garantie startdatum (of installatiedatum)
- Garantie einddatum
- OF: koppeltabel besteksparagraaf → garantieperiode

**Vragen:**
1. Kunnen we de garantieperiode toevoegen aan de werkbonparagrafen export?
2. Of is er een aparte tabel/Excel met besteksparagraaf → garantie van/tm?
3. Anders: kunnen we pragmatisch een vaste termijn aanhouden per factureerwijze? (bijv. "Vaste prijs (binnen contract)" = 12 maanden garantie vanaf melddatum?)

## 🚀 VOORSTEL VERVOLGSTAPPEN:

**Optie A - Snelle start (deze week):**
- Ik implementeer eerst **Contract-type filter** (als de matching logica helder is)
- Voor garantie gebruiken we tijdelijk een pragmatische aanpak (vaste termijn vanaf melddatum)
- Jullie kunnen alvast testen en feedback geven
- Garantie-verfijning volgt daarna zodra data beschikbaar is

**Optie B - Compleet (2-3 weken):**
- Jullie leveren garantieperiode data aan (export of koppeltabel)
- Ik implementeer beide filters volledig
- Eén keer testen, direct productie-rijp

Wat heeft jullie voorkeur?

## ❓ SAMENVATTING VRAGEN:

1. **Contract matching:** Hoe match ik werkbonparagraaf.naam exact met contract namen in jullie Excel?
2. **Garantie data:** Kunnen we garantieperiode (van/tm) toevoegen aan werkbonparagrafen export, of is er een aparte bron?
3. **Vervolgaanpak:** Voorkeur voor snelle iteratieve aanpak (Optie A) of compleet in één keer (Optie B)?

Laat maar weten wat jullie voorkeur heeft, dan pak ik het direct op!

Groet,
Tobias

---

**PS:** De huidige V2 met verbeterde ketelonderdelen-logica draait al op dezelfde URL voor jullie tests:
**URL:** https://tools-en-analyses-fsysjwn7jqdcvgwbxgqhuk.streamlit.app/
**Wachtwoord:** `Xk9#mP2$vL7nQ4wR`
