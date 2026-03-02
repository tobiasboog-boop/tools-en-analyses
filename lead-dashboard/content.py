"""
Pijler Content Templates
========================
Norm/frictie formuleringen, LinkedIn posts, mail templates en belscripts per pijler.
Gebaseerd op Arthur's FUNNEL_SAMENVATTING.md.
"""

PIJLER_CONTENT = {
    "Rendement": {
        "norm": "Toegevoegde waarde per uur wordt vooraf vastgesteld.",
        "norm_alt": "Professionele organisaties normeren vooraf.",
        "frictie": "Veel bedrijven weten pas na afronding of een project daadwerkelijk bijdroeg aan de winst.",
        "frictie_alt": "In veel bedrijven worden afwijkingen pas zichtbaar bij jaarafsluiting.",
        "verdieping": "Veel bedrijven ontdekken pas na 9 maanden dat projecten structureel onder norm zijn uitgevoerd.",
        "linkedin_posts": {
            1: (
                "Professionele installatiebedrijven normeren vooraf hun toegevoegde waarde per uur. "
                "Niet achteraf analyseren, maar vooraf bepalen waar je naartoe werkt. "
                "Volgende week organiseren we hierover een online MT-sessie."
            ),
            2: (
                "Rendement hoort vooraf genormeerd te zijn. Veel bedrijven ontdekken pas na 9 maanden "
                "dat projecten structureel onder norm zijn uitgevoerd. Dat vraagt om maandelijkse toetsing "
                "op toegevoegde waarde per uur. Daar gaan we volgende week concreet op in tijdens onze MT-sessie."
            ),
            3: (
                "Een installatiebedrijf met 45 fte dacht 7% rendement te draaien... Na normering bleek "
                "2% marge te verdampen door productiviteit. Door vooraf norm te stellen en maandelijks "
                "bij te sturen... Laatste kans voor onze online MT-sessie."
            ),
            4: (
                "Rendement hoort vooraf genormeerd te zijn. Zonder norm blijft bijsturing reactief. "
                "Met 5 kengetallen zie je direct waar spanning zit."
            ),
        },
        "mail_templates": {
            "leads_week1": (
                "Veel installatiebedrijven analyseren rendement achteraf. Maar professionele "
                "organisaties normeren vooraf. In veel bedrijven worden afwijkingen pas zichtbaar "
                "bij jaarafsluiting. Dat vraagt om maandelijkse normering en bijsturing."
            ),
            "klanten_week1": (
                "Jullie beschikken over inzicht. Zonder expliciete norm blijft rendement een uitkomst. "
                "De volgende stap is normeren en structureel bespreken."
            ),
            "reminder_leads": (
                "Aanstaande [datum] bespreken we hoe professionele installatiebedrijven hun rendement "
                "actief sturen. Concreet gaan we in op: het bepalen van realistische normen, het "
                "zichtbaar maken van afwijkingen, het inrichten van maandelijkse bijsturing."
            ),
            "reminder_klanten": (
                "Aanstaande [datum] zoomen we in op het structureel normeren van rendement en het "
                "borgen van maandelijkse bijsturing binnen de organisatie. Voor MT-leden die verder "
                "willen dan inzicht alleen."
            ),
        },
        "belscripts": {
            "leads_na_webinar": (
                'Goedemorgen [naam], Arthur hier van Notifica. Ik zag dat je bij de sessie over '
                'rendementssturing aanwezig was. Wat was voor jullie het meest herkenbaar?\n\n'
                'Verdieping:\n'
                '- "Hoe sturen jullie hier nu op?"\n'
                '- "Wordt dit maandelijks besproken?"\n'
                '- "Is dit iets wat bij jullie speelt op MT-niveau?"\n\n'
                'Afsluiting: "Zullen we dit eens concreet maken voor jullie situatie?"'
            ),
            "klanten_na_webinar": (
                'Goedemorgen [naam], Arthur hier. Tijdens de sessie ging het over normeren en borging. '
                'Waar zit bij jullie de grootste spanning als je dit vertaalt naar jullie organisatie?\n\n'
                'Verdiepen op:\n'
                '- Wie is verantwoordelijk?\n'
                '- Wordt het structureel besproken?\n'
                '- Zijn normen expliciet vastgelegd?\n\n'
                'Afsluiting: "Zullen we dit samen concreet maken en kijken welke stap logisch is?"'
            ),
            "na_toolgebruik": (
                'Opening: "Wat viel je op bij het doorrekenen?"\n\n'
                'Na gesprek:\n'
                '1. Pijler-PDF sturen\n'
                '2. Verdiepingssessie plannen'
            ),
        },
    },
    "Liquiditeit": {
        "norm": "Liquiditeit wordt 6-12 maanden vooruit gepland.",
        "norm_alt": "Professionele organisaties plannen hun cashflow structureel vooruit.",
        "frictie": "Liquiditeitsspanning wordt vaak pas zichtbaar wanneer banklimieten worden geraakt.",
        "frictie_alt": "Veel bedrijven reageren pas op kasstroomproblemen als het te laat is.",
        "verdieping": "Zonder vooruitkijkend cashflow-overzicht ontstaat er spanning op momenten dat het niet meer te corrigeren is.",
        "linkedin_posts": {
            1: (
                "Professionele installatiebedrijven plannen hun liquiditeit 6-12 maanden vooruit. "
                "Niet reageren op spanning, maar vooruitkijken en financiele ruimte actief bewaken."
            ),
            2: (
                "Liquiditeitsspanning wordt vaak pas zichtbaar wanneer banklimieten worden geraakt. "
                "Dat is te laat. Structureel cashflow-overzicht in het MT voorkomt dit."
            ),
            3: (
                "Bij een installatiebedrijf bleek na 6 maanden dat de liquiditeitspositie structureel "
                "onder druk stond door grote projecten. Met maandelijks cashflow-inzicht had dit voorkomen kunnen worden."
            ),
            4: (
                "Liquiditeit hoort structureel bewaakt te worden, niet reactief. "
                "Met de juiste kengetallen zie je 6 maanden vooruit waar spanning ontstaat."
            ),
        },
        "mail_templates": {
            "leads_week1": (
                "Veel installatiebedrijven hebben geen structureel cashflow-overzicht. "
                "Liquiditeitsspanning wordt pas zichtbaar bij banklimieten. Professionele "
                "organisaties plannen 6-12 maanden vooruit."
            ),
            "klanten_week1": (
                "Jullie hebben inzicht in de financiele positie. De volgende stap is structureel "
                "vooruitkijken: cashflow-planning als vast onderdeel van het MT-overleg."
            ),
            "reminder_leads": (
                "Aanstaande [datum] bespreken we hoe professionele installatiebedrijven hun "
                "liquiditeit structureel bewaken en 6-12 maanden vooruit plannen."
            ),
            "reminder_klanten": (
                "Aanstaande [datum] verdiepen we ons in het structureel borgen van "
                "liquiditeitsplanning binnen de organisatie."
            ),
        },
        "belscripts": {
            "leads_na_webinar": (
                'Goedemorgen [naam], Arthur hier van Notifica. Ik zag dat je bij de sessie over '
                'liquiditeitsplanning aanwezig was. Hoe bewaken jullie op dit moment de cashflow-positie?\n\n'
                'Verdieping:\n'
                '- "Hebben jullie een cashflow-forecast?"\n'
                '- "Wordt dit structureel in het MT besproken?"\n\n'
                'Afsluiting: "Zullen we dit concreet maken voor jullie situatie?"'
            ),
            "klanten_na_webinar": (
                'Goedemorgen [naam], Arthur hier. Waar zit bij jullie de grootste spanning '
                'als het gaat om cashflow en liquiditeitsplanning?\n\n'
                'Afsluiting: "Zullen we samen kijken welke stap logisch is?"'
            ),
            "na_toolgebruik": (
                'Opening: "Wat viel je op bij het doorrekenen van jullie liquiditeitspositie?"\n\n'
                'Na gesprek:\n'
                '1. Pijler-PDF sturen\n'
                '2. Verdiepingssessie plannen'
            ),
        },
    },
    "Resource Planning": {
        "norm": "Capaciteit wordt 3-6 maanden vooruit gepland.",
        "norm_alt": "Professionele organisaties plannen hun bezetting voorspelbaar.",
        "frictie": "Veel organisaties ontdekken te laat dat projecten tegelijk pieken.",
        "frictie_alt": "Zonder capaciteitsoverzicht wordt elke week brandjes blussen.",
        "verdieping": "Projectvalmomenten, onderbezetting en overbezetting zijn pas zichtbaar als het te laat is om bij te sturen.",
        "linkedin_posts": {
            1: (
                "Professionele installatiebedrijven plannen hun capaciteit 3-6 maanden vooruit. "
                "Niet brandjes blussen, maar voorspelbaar plannen en tijdig anticiperen."
            ),
            2: (
                "Veel organisaties ontdekken te laat dat projecten tegelijk pieken. "
                "Dat leidt tot overbelasting, uitloop en frustratie. Structurele capaciteitsplanning voorkomt dit."
            ),
            3: (
                "Een installatiebedrijf met 60 fte had structureel last van pieken en dalen. "
                "Na het inrichten van 3-maands capaciteitsplanning daalde de uitloop met 40%."
            ),
            4: (
                "Capaciteit hoort voorspelbaar gepland te worden. Met de juiste inzichten "
                "zie je 3 maanden vooruit waar spanning ontstaat."
            ),
        },
        "mail_templates": {
            "leads_week1": (
                "Veel installatiebedrijven plannen reactief. Projecten pieken tegelijk, "
                "medewerkers worden overbelast. Professionele organisaties plannen 3-6 maanden vooruit."
            ),
            "klanten_week1": (
                "Jullie hebben inzicht in bezetting. De volgende stap is structureel "
                "vooruitplannen: capaciteit als vast onderdeel van de projectcyclus."
            ),
            "reminder_leads": (
                "Aanstaande [datum] bespreken we hoe professionele installatiebedrijven hun "
                "capaciteit structureel plannen en pieken voorkomen."
            ),
            "reminder_klanten": (
                "Aanstaande [datum] verdiepen we ons in het structureel borgen van "
                "capaciteitsplanning binnen de organisatie."
            ),
        },
        "belscripts": {
            "leads_na_webinar": (
                'Goedemorgen [naam], Arthur hier van Notifica. Ik zag dat je bij de sessie over '
                'capaciteitsplanning aanwezig was. Hoe plannen jullie op dit moment de bezetting?\n\n'
                'Verdieping:\n'
                '- "Hebben jullie een capaciteitsoverzicht?"\n'
                '- "Hoe ver kijken jullie vooruit?"\n\n'
                'Afsluiting: "Zullen we dit concreet maken voor jullie situatie?"'
            ),
            "klanten_na_webinar": (
                'Goedemorgen [naam], Arthur hier. Waar zit bij jullie de grootste spanning '
                'als het gaat om capaciteitsplanning en bezetting?\n\n'
                'Afsluiting: "Zullen we samen kijken welke stap logisch is?"'
            ),
            "na_toolgebruik": (
                'Opening: "Wat viel je op bij het doorrekenen van jullie capaciteit?"\n\n'
                'Na gesprek:\n'
                '1. Pijler-PDF sturen\n'
                '2. Verdiepingssessie plannen'
            ),
        },
    },
    "Capaciteitsplanning": {
        "norm": "Capaciteit wordt 3-6 maanden vooruit gepland.",
        "norm_alt": "Professionele organisaties plannen hun bezetting voorspelbaar.",
        "frictie": "Veel organisaties ontdekken te laat dat projecten tegelijk pieken.",
        "frictie_alt": "Zonder capaciteitsoverzicht wordt elke week brandjes blussen.",
        "verdieping": "Projectvalmomenten, onderbezetting en overbezetting zijn pas zichtbaar als het te laat is.",
        "linkedin_posts": {
            1: "Professionele installatiebedrijven plannen hun capaciteit structureel vooruit.",
            2: "Veel organisaties ontdekken te laat dat projecten tegelijk pieken.",
            3: "Met structurele capaciteitsplanning daalde de uitloop bij een klant met 40%.",
            4: "Met de juiste inzichten zie je 3 maanden vooruit waar spanning ontstaat.",
        },
        "mail_templates": {
            "leads_week1": "Veel installatiebedrijven plannen reactief. Professionele organisaties plannen 3-6 maanden vooruit.",
            "klanten_week1": "De volgende stap is structureel vooruitplannen: capaciteit als vast onderdeel van de projectcyclus.",
            "reminder_leads": "Aanstaande [datum] bespreken we hoe professionele installatiebedrijven hun capaciteit plannen.",
            "reminder_klanten": "Aanstaande [datum] verdiepen we ons in het borgen van capaciteitsplanning.",
        },
        "belscripts": {
            "leads_na_webinar": 'Goedemorgen [naam], hoe plannen jullie op dit moment de bezetting?',
            "klanten_na_webinar": 'Waar zit bij jullie de grootste spanning qua capaciteitsplanning?',
            "na_toolgebruik": 'Wat viel je op bij het doorrekenen van jullie capaciteit?',
        },
    },
}


# ============================================================
#  CONCRETE WEEK-ACTIES PER PIJLER
# ============================================================
# Per pijler, per week, per rol: wat moet je concreet doen?
# Gebaseerd op Arthur's FUNNEL_SAMENVATTING.md rollen-verdeling.

WEEK_ACTIES_PIJLER = {
    "Rendement": {
        1: {  # Norm
            "arthur": [
                "Norm-formulering bepalen: 'Toegevoegde waarde per uur wordt vooraf vastgesteld'",
                "Kernboodschap LinkedIn post aanleveren aan Chloe (norm, geen verkoop)",
                "Maandthema 'Rendement' scherp zetten - wat is de norm, wat is de frictie?",
            ],
            "tobias": [
                "Webinar-landingspagina checken en CTA's optimaliseren",
                "Warme leads uit vorige maand opvolgen (zie bellijst)",
                "Conversie vorige maand evalueren - wat werkte, wat niet?",
            ],
            "chloe": [
                "LinkedIn post 1 schrijven en publiceren: Norm neerzetten (geen tool, geen verkoop)",
                "Mail 1 versturen: webinar-uitnodiging + lichte frictie (leads via EmailOctopus)",
                "Mail 1 versturen: webinar-uitnodiging + verdiepingstaal (klanten via Pipedrive)",
                "Contentkalender deze maand invullen (4 posts, 2 mails, 1 webinar)",
            ],
        },
        2: {  # Frictie
            "arthur": [
                "Frictie-formuleringen aanleveren: 'Veel bedrijven weten pas na afronding of een project bijdroeg'",
                "Inhoudelijke review LinkedIn post 2 (check: herkenbaar, concreet, niet beschuldigend)",
                "Herkenbare praktijkvoorbeelden uit klantgesprekken verzamelen",
            ],
            "tobias": [
                "5-10 warme accounts bellen of DM'en (zie bellijst - hoogste engagement)",
                "Tool-CTA op website optimaliseren (subtiel, onderaan content)",
                "Leads met websitebezoek + email opens opvolgen",
            ],
            "chloe": [
                "LinkedIn post 2 schrijven en publiceren: Frictie + subtiele tool-CTA onderaan",
                "Webinar-uitnodiging mail 2 versturen (reminder, meer urgentie)",
                "Rapportage: open rates, clicks, aanmeldingen tot nu toe naar Tobias",
            ],
        },
        3: {  # Autoriteit / Webinar
            "arthur": [
                "Webinar presenteren: Norm > Frictie > Hoe richten professionele bedrijven dit in? > Tool",
                "Praktijkcases klaarzetten (geen klantnamen, wel herkenbare situaties)",
                "Top 12 klanten persoonlijk benaderen: 'Dit thema raakt jullie situatie'",
            ],
            "tobias": [
                "ALLE webinar-deelnemers bellen binnen 48 uur (grootste hefboom!)",
                "Gesprekken plannen - belscript: bedanken + 'Zullen we dit concreet maken?'",
                "Tool-gebruikers en PDF-aanvragers opvolgen",
            ],
            "chloe": [
                "LinkedIn post 3 schrijven: Praktijkvoorbeeld ('Bij een klant met 45 fte zagen we...')",
                "Reminder-mail versturen naar leads (concreter) en klanten (verdiepingstaal)",
                "Webinar techniek + logistics regelen (Teams link, registratie check)",
            ],
        },
        4: {  # Concretisering
            "arthur": [
                "Top 12 architectgesprekken voeren: 'Waar zit bij jullie de grootste spanning?'",
                "Beschikbaar zijn voor complexe verdiepingstrajecten na tool/webinar",
                "Pijler-PDF Rendement reviewen en klaarleggen voor na-gesprek",
            ],
            "tobias": [
                "Tool-gebruikers bellen: 'Wat viel je op bij het doorrekenen?'",
                "Webinar-deelnemers die nog niet gebeld zijn alsnog opvolgen",
                "Deals begeleiden: pijler-PDF sturen + verdiepingssessie plannen",
                "Maandrapportage: conversie, gesprekken, nieuwe klanten",
            ],
            "chloe": [
                "LinkedIn post 4 schrijven en publiceren: Tool-CTA ('Wil je zien wat dit betekent?')",
                "Optionele warme mail naar engaged leads: 'Wil je dit doorrekenen?'",
                "Maandrapportage maken: opens, clicks, aanmeldingen, toolgebruik",
                "Volgende maand voorbereiden: pijler Liquiditeit content plannen",
            ],
        },
    },
    "Liquiditeit": {
        1: {
            "arthur": [
                "Norm-formulering bepalen: 'Liquiditeit wordt 6-12 maanden vooruit gepland'",
                "Kernboodschap LinkedIn post aanleveren (cashflow-normering)",
                "Maandthema 'Liquiditeit' scherp zetten",
            ],
            "tobias": [
                "Webinar-landingspagina updaten voor thema Liquiditeit",
                "Warme leads uit vorige maand opvolgen",
                "Liquiditeit-tool CTA's voorbereiden",
            ],
            "chloe": [
                "LinkedIn post 1: Norm cashflow-planning (geen tool, geen verkoop)",
                "Mail 1: webinar-uitnodiging + frictie over banklimieten (leads)",
                "Mail 1: verdiepingsuitnodiging cashflow (klanten)",
                "Contentkalender Liquiditeit-maand invullen",
            ],
        },
        2: {
            "arthur": [
                "Frictie-formuleringen: 'Liquiditeitsspanning pas zichtbaar bij banklimieten'",
                "Review LinkedIn post 2 op inhoudelijke diepgang",
                "Praktijkvoorbeelden cashflow-problemen verzamelen",
            ],
            "tobias": [
                "5-10 warme accounts bellen/DM'en (zie bellijst)",
                "Liquiditeit-tool CTA op website plaatsen",
                "Engaged leads opvolgen",
            ],
            "chloe": [
                "LinkedIn post 2: Frictie cashflow + subtiele tool-CTA",
                "Webinar-reminder mail versturen",
                "Rapportage aanmeldingen naar Tobias",
            ],
        },
        3: {
            "arthur": [
                "Webinar Liquiditeit presenteren",
                "Praktijkcases cashflow-planning tonen",
                "Top 12 benaderen over liquiditeitsthema",
            ],
            "tobias": [
                "ALLE webinar-deelnemers bellen binnen 48 uur",
                "Gesprekken plannen uit webinar",
                "Tool-gebruikers opvolgen",
            ],
            "chloe": [
                "LinkedIn post 3: Praktijkvoorbeeld liquiditeit",
                "Reminder-mail leads + klanten versturen",
                "Webinar techniek regelen",
            ],
        },
        4: {
            "arthur": [
                "Top 12 architectgesprekken over cashflow-structuur",
                "Pijler-PDF Liquiditeit klaarleggen",
            ],
            "tobias": [
                "Tool-gebruikers bellen over liquiditeitsanalyse",
                "Resterende webinar-deelnemers opvolgen",
                "Deals begeleiden + pijler-PDF sturen",
                "Maandrapportage Liquiditeit",
            ],
            "chloe": [
                "LinkedIn post 4: Tool-CTA liquiditeitsanalyse",
                "Optionele warme mail naar engaged leads",
                "Maandrapportage + volgende maand (Resource Planning) voorbereiden",
            ],
        },
    },
    "Resource Planning": {
        1: {
            "arthur": [
                "Norm-formulering: 'Capaciteit wordt 3-6 maanden vooruit gepland'",
                "Kernboodschap LinkedIn post aanleveren (planning-normering)",
                "Maandthema 'Resource Planning' scherp zetten",
            ],
            "tobias": [
                "Webinar-landingspagina updaten voor Resource Planning",
                "Warme leads opvolgen",
                "Planning-tool CTA's voorbereiden",
            ],
            "chloe": [
                "LinkedIn post 1: Norm capaciteitsplanning",
                "Mail 1: webinar-uitnodiging + frictie pieken/dalen (leads)",
                "Mail 1: verdieping planning (klanten)",
                "Contentkalender Resource Planning-maand invullen",
            ],
        },
        2: {
            "arthur": [
                "Frictie: 'Veel organisaties ontdekken te laat dat projecten tegelijk pieken'",
                "Review LinkedIn post 2",
            ],
            "tobias": [
                "5-10 warme accounts bellen/DM'en",
                "Planning-tool CTA live zetten",
            ],
            "chloe": [
                "LinkedIn post 2: Frictie planning + tool-CTA",
                "Webinar-reminder mail",
                "Rapportage aanmeldingen",
            ],
        },
        3: {
            "arthur": [
                "Webinar Resource Planning presenteren",
                "Praktijkcases bezetting/pieken tonen",
                "Top 12 benaderen",
            ],
            "tobias": [
                "ALLE webinar-deelnemers bellen binnen 48u",
                "Gesprekken plannen",
                "Tool-gebruikers opvolgen",
            ],
            "chloe": [
                "LinkedIn post 3: Praktijkvoorbeeld planning",
                "Reminder-mail versturen",
                "Webinar techniek regelen",
            ],
        },
        4: {
            "arthur": [
                "Top 12 architectgesprekken over planning-structuur",
                "Pijler-PDF Resource Planning klaarleggen",
            ],
            "tobias": [
                "Tool-gebruikers bellen over planningsanalyse",
                "Resterende deelnemers opvolgen",
                "Deals begeleiden + PDF sturen",
                "Maandrapportage",
            ],
            "chloe": [
                "LinkedIn post 4: Tool-CTA planningsanalyse",
                "Warme mail naar engaged leads",
                "Maandrapportage + volgende maand voorbereiden",
            ],
        },
    },
    "Capaciteitsplanning": {
        1: {
            "arthur": [
                "Norm-formulering capaciteit bepalen",
                "Kernboodschap LinkedIn post aanleveren",
                "Maandthema scherp zetten",
            ],
            "tobias": [
                "Webinar-landingspagina updaten",
                "Warme leads opvolgen",
            ],
            "chloe": [
                "LinkedIn post 1: Norm capaciteitsplanning",
                "Mail 1: webinar-uitnodiging + frictie",
                "Contentkalender invullen",
            ],
        },
        2: {
            "arthur": ["Frictie-formuleringen aanleveren", "Review LinkedIn post"],
            "tobias": ["5-10 warme accounts bellen", "Tool-CTA optimaliseren"],
            "chloe": ["LinkedIn post 2: Frictie + tool-CTA", "Rapportage aanmeldingen"],
        },
        3: {
            "arthur": ["Webinar presenteren", "Top 12 benaderen"],
            "tobias": ["Webinar-deelnemers bellen binnen 48u", "Gesprekken plannen"],
            "chloe": ["LinkedIn post 3: Praktijkvoorbeeld", "Reminder-mail + webinar techniek"],
        },
        4: {
            "arthur": ["Top 12 architectgesprekken", "Pijler-PDF klaarleggen"],
            "tobias": ["Tool-gebruikers bellen", "Deals begeleiden", "Maandrapportage"],
            "chloe": ["LinkedIn post 4: Tool-CTA", "Maandrapportage + volgende maand voorbereiden"],
        },
    },
}
