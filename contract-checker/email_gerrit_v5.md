# Email naar Gerrit - V5 klaar voor hertest

**Aan:** Gerrit (WVC)
**Van:** Tobias
**Onderwerp:** RE: Contract Checker - V5 klaar, graag hertesten met dezelfde bonnen

---

Hoi Gerrit,

Goed nieuws: ik heb de AI flink verbeterd. In mijn eigen backtest (tegen jouw 39 beoordeelde bonnen) ging de nauwkeurigheid van **74% naar 90%**.

## WAT HEB IK VERBETERD:

| # | Probleem | Oplossing |
|---|----------|-----------|
| 1 | "Lekkage onder de ketel" fout geclassificeerd | Storingscode 006.1 (onder ketel) = JA, 006.2 (aan installatie) = NEE. Dat onderscheid miste. |
| 2 | "Probleem door derde" werd genegeerd | Oorzaakcode 900 is nu hoogste prioriteit → altijd NEE, ook bij lekkage onder ketel |
| 3 | Lekkage slk/wk werd als JA gezien | Locatie slaapkamer/woonkamer/badkamer/keuken nu expliciet als NEE |
| 4 | AI gaf wisselende antwoorden | Temperature op 0 gezet → zelfde werkbon = altijd zelfde antwoord |
| 5 | Bug in mijn testomgeving | Mijn backtest laadde minder data dan de live app. Opgelost. |

## WAT KAN DE AI NOG NIET:

Er zijn 2 bonnen die de AI structureel fout heeft:
- **Radiatorkraan vs verstopping** (W2546414): De storingscode zegt "radiatorkraan defect" maar in de oplossing staat "radiator gedemonteerd ivm verstopping". De oplossingsdata ontbreekt helaas in de dataset → de AI kan het niet weten.
- **Oplossing niet in data** (W2547118): Jij zei "oplossing niet goed gelezen, moet TWIJFEL zijn". De monteurnotities zitten niet in de data-export. Dat is een punt voor de volgende fase.

## HERTEST:

Klik op **"Reset verwerkte bonnen"** in de app, dan kun je dezelfde werkbonnen opnieuw classificeren en 1-op-1 vergelijken.

**URL:** https://tools-en-analyses-fsysjwn7jqdcvgwbxgqhuk.streamlit.app/
**Wachtwoord:** `Xk9#mP2$vL7nQ4wR`

Groet,
Tobias
