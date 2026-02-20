# Email naar Gerrit - V4 klaar voor hertest

**Aan:** Gerrit (WVC)
**Van:** Tobias
**Onderwerp:** RE: Contract Checker - V4 klaar, dezelfde bonnen opnieuw testen

---

Hoi Gerrit,

Bedankt, weer waardevolle feedback! Ik heb alle 10 fouten geanalyseerd en de AI flink aangescherpt.

## WAT GING ER FOUT:

| # | Fout (4x) | Oorzaak | Oplossing |
|---|-----------|---------|-----------|
| 1 | "Lekkage onder de ketel" als NEE | **Mijn fout** - ik had de regel verkeerd ingevoerd | Gecorrigeerd: lekkage onder de ketel = BINNEN contract |
| 2 | Oplossing "gevuld en ontlucht" genegeerd | AI las de oplossing niet goed | Prompt herstructureerd: oplossing nu expliciet STAP 1 |
| 3 | Bewoner niet thuis als NEE | Ontbrekende regel | Toegevoegd: niet thuis = BINNEN contract |
| 4 | Radiator verstopping als JA | AI verwarde radiatorkraan met radiator | Onderscheid verduidelijkt: radiator ≠ radiatorkraan |
| 5 | 2x PARSE_ERROR → TWIJFEL | Technisch: AI gaf onleesbaar antwoord | Robustere JSON parsing met fallback |

**Grootste fout was van mij:** Ik had "lekkage onder de ketel" als BUITEN contract ingevoerd. Dat veroorzaakte 4 van de 10 fouten. Nu gecorrigeerd.

## WAT IS ANDERS IN V4:

1. **Oplossing is nu LEIDEND** - De AI leest de oplossingsomschrijving als eerste stap, vóór alles
2. **Lekkage-regels gecorrigeerd** - "onder de ketel" = JA, "installatie keuken/slk/wk" = NEE
3. **Technische fix** - Minder PARSE_ERRORs door robuustere verwerking
4. **Contract-type filter** - Echte contractlijst ingevoerd (STAND-27, STAND-28, etc.)

## HERTEST MET DEZELFDE BONNEN:

Ja, dat kan! Klik op **"Reset verwerkte bonnen"** in de app, dan kun je exact dezelfde 40 werkbonnen opnieuw classificeren. Zo kun je 1-op-1 vergelijken of het echt verbetert.

**URL:** https://tools-en-analyses-fsysjwn7jqdcvgwbxgqhuk.streamlit.app/
**Wachtwoord:** `Xk9#mP2$vL7nQ4wR`

Groet,
Tobias
