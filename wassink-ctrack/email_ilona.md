# E-mail Ilona - Vlootbeheer Dashboard Wassink

**Aan:** Ilona
**Onderwerp:** Prototype Vlootbeheer Dashboard op basis van C-Track data

---

Hoi Ilona,

Goed nieuws: we hebben een eerste prototype van het Vlootbeheer Dashboard klaar op basis van jullie C-Track data. Hieronder vind je de link en een korte toelichting.

## Dashboard bekijken

**Link:** https://tools-en-analyses-7mgqsyomdninewudrskup8.streamlit.app/
**Wachtwoord:** WLGt9pLJbgBVO7@L

Het dashboard bevat:
- **Home** – KPI's, dagelijkse kilometers, top voertuigen en bestuurders
- **Vlootoverzicht** – Statistieken per voertuig met detailweergave
- **Kilometerregistratie** – Per voertuig of bestuurder, met heatmap en CSV-export
- **Rijgedrag** – Snelheidsovertredingen en stationair draaien per bestuurder
- **Kaart** – Bestemmingen en ritpatronen op een interactieve kaart

## Waar staan we nu

Het ontsluiten van de C-Track data heeft meer tijd gekost dan verwacht. De API van C-Track bleek in eerste instantie niet toereikend, waardoor Dolf drie dagen extra technisch werk heeft moeten verrichten om de voertuig- en ritdata op de juiste manier beschikbaar te krijgen. Die vertraging lag dus aan de C-Track kant.

Het dashboard werkt nu op een momentopname van de data (1-12 februari, ruim 3.100 ritten, 62 voertuigen, 59 bestuurders). In een productieversie wordt dit uiteraard automatisch bijgewerkt.

De data komt op dit moment stand-alone uit C-Track. De echte meerwaarde ontstaat wanneer we dit gaan koppelen aan de Syntess ERP-data. Dan worden inzichten mogelijk als:
- **Reistijd vs. productieve tijd** – Klopt de geboekte reistijd met wat GPS laat zien?
- **Werkbon-verificatie** – Is een monteur daadwerkelijk op de werklocatie geweest?
- **Reisafstand validatie** – Komen de vastgelegde reisafstanden overeen met de werkelijkheid?

## Vervolgstappen

| Fase | Omschrijving | Inspanning |
|------|-------------|------------|
| ~~Fase 0~~ | ~~Technische ontsluiting C-Track API~~ | ~~Afgerond (3 dagen)~~ |
| ~~Fase 1~~ | ~~Dashboard prototype bouwen en delen~~ | ~~Afgerond~~ |
| **Fase 2** | Automatische data-verversing vanuit C-Track | 1 dag |
| **Fase 3** | Koppeling met Syntess (medewerkers, werkbonnen, uren) | 2 dagen |
| **Fase 4** | Productie-inrichting en oplevering | 1 dag |

Resterende inspanning: **4 dagen**

We raden aan om te starten met fase 2 en 3 gecombineerd, zodat het dashboard niet alleen actuele data toont maar ook direct de koppeling met Syntess laat zien.

Mocht je het interessant vinden, dan kunnen we op korte termijn even een half uurtje via Teams inplannen om het prototype samen door te lopen en de vervolgstappen te bespreken.

Met vriendelijke groet,
Tobias
