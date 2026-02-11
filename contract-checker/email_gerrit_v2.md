# Email naar Gerrit - Contract Checker V2

**Aan:** Gerrit (WVC)
**Van:** Tobias
**Onderwerp:** Contract Checker V2 - Verbeterde accuracy na je feedback

---

Hoi Gerrit,

Bedankt voor je uitgebreide feedback op de Contract Checker! Die 42% accuracy was inderdaad te mager, en je observaties over de ketelonderdelen waren spot-on.

## Wat hebben we aangepakt?

De AI miste ketelonderdelen (ventilator, gasklep, expansievat, pomp) omdat het niet wist dat deze "binnen de mantel" van de ketel vallen. We hebben:

1. **Expliciete ketelonderdelen lijst toegevoegd** → AI weet nu wat binnen/buiten ketelkast is
2. **Monteur's notities voorrang gegeven** → "Oplossingen" wegen zwaarder dan kostenregels
3. **"< 2 meter" regel verduidelijkt** → Edge cases zoals leidingen nabij de ketel correct

## Backtest resultaten

We hebben 10 representatieve cases getest (ketelonderdelen, leidingen, verstoppingen, edge cases):
- **V1:** 50% correct (5/10)
- **V2:** 100% correct (10/10)

Alle 5 fouten van V1 waren ketelonderdelen die als NEE werden geclassificeerd - precies wat jij aangaf.

**Verwachting op jouw 50 werkbonnen:** 80%+ accuracy (vs 42% in V1).

## Test V2 zelf

Je kunt de verbeterde versie hier testen:

**URL:** https://tools-en-analyses-fsysjwn7jqdcvgwbxgqhuk.streamlit.app/
**Wachtwoord:** `Xk9#mP2$vL7nQ4wR`

Zou je dezelfde steekproef door V2 willen halen en kijken of de verbetering klopt? Ben heel benieuwd naar je bevindingen.

Groet,
Tobias

---

## Vervolgstappen (optioneel toevoegen):

Als V2 inderdaad beter scoort:
- **Quick fix (€1.500):** Deploy V2, korte instructie, 1 maand support
- **Productie-gereed (€12-15k):** Garantieperiode logica + collectief/individueel filters + contractspecifieke selectie
- **Onderhoud (€3.5k/jaar):** Updates, bugfixes, nieuwe contracten toevoegen
