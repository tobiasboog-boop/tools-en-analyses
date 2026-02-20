# E-mail 2: Voorstel vervolgstappen

**Aan:** Ilona
**Onderwerp:** Voorstel: Vlootbeheer Dashboard – van prototype naar productie

---

Hoi Ilona,

Hierbij een overzicht van wat we tot nu toe hebben gedaan en een voorstel voor de vervolgstappen om het Vlootbeheer Dashboard productiewaardig te maken.

## Wat is er gedaan

Het ontsluiten van de C-Track data is technisch niet triviaal gebleken. Dolf heeft **drie dagen** besteed aan het realiseren van de koppeling met de C-Track API en het verzamelen van de voertuig- en ritdata. De API bleek in eerste instantie niet toereikend, waardoor er extra technisch werk nodig was om de data op de juiste manier beschikbaar te krijgen.

Op basis van de verzamelde data hebben wij een prototype dashboard gebouwd dat de volgende inzichten biedt:

- Vlootoverzicht met real-time kilometerstanden en activiteit
- Kilometerregistratie per voertuig en per bestuurder
- Rijgedraganalyse (snelheidsovertredingen, stationair draaien)
- Kaartweergave met locaties en ritpatronen

**De huidige data is stand-alone uit C-Track gehaald.** Het dashboard werkt op een momentopname van de ritdata (1-12 februari, 3.117 ritten, 62 voertuigen, 59 bestuurders).

## Waar zit de echte waarde

De grootste meerwaarde ontstaat wanneer we de C-Track GPS-data gaan **koppelen aan de Syntess ERP-data**. Daarmee worden inzichten mogelijk die nu niet beschikbaar zijn:

1. **Reistijd vs. productieve tijd** – GPS-rijuren vergelijken met geboekte uren in Syntess. Hoeveel tijd gaat er werkelijk op aan reizen, en klopt dat met wat er wordt geschreven?

2. **Werkbon-verificatie** – Automatisch controleren of een monteur daadwerkelijk op de werklocatie is geweest, door GPS-eindlocaties te matchen met werkbonadressen.

3. **Route-optimalisatie** – Op basis van historische ritpatronen en werkbonplanningen slimmere routes voorstellen.

4. **Reisafstand validatie** – De in Syntess vastgelegde reisafstand per project vergelijken met de werkelijke GPS-afstanden.

## Overzicht inspanning en vervolgstappen

| Fase | Omschrijving | Inspanning |
|------|-------------|------------|
| **Fase 0** | Technische ontsluiting C-Track API (data verzamelen) | **Afgerond** (3 dagen) |
| **Fase 1** | Dashboard prototype bouwen en delen | **Afgerond** |
| **Fase 2** | Automatische data-verversing | 1 dag |
|  | Dagelijkse verversing van ritdata vanuit C-Track | |
| **Fase 3** | Syntess-koppeling | 2 dagen |
|  | Medewerkers en werkbonnen koppelen aan GPS-ritten | |
|  | Verrijkte analyses: reistijd vs. productieve tijd | |
| **Fase 4** | Productie-inrichting en oplevering | 1 dag |
|  | Beveiliging, documentatie en overdracht | |

**Reeds besteed:** 3 dagen (technische ontsluiting C-Track)
**Resterende inspanning fase 2-4:** 4 dagen

## Aanbeveling

We stellen voor om te starten met **fase 2 en 3 gecombineerd**: automatische verversing en de Syntess-koppeling. Daar zit de grootste zakelijke waarde – dan wordt zichtbaar hoeveel tijd er werkelijk opgaat aan reizen versus productief werk, en of monteurs daadwerkelijk op de werklocatie zijn geweest.

Graag plannen we een kort overleg in om het prototype samen door te lopen en de vervolgstappen te bespreken.

Met vriendelijke groet,
Tobias
