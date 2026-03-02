"""
Funnel Configuratie
===================
Pijlers, weekfasen, KPI targets, week-acties, Top 12, omzetdata.
"""

FUNNEL_CONFIG = {
    "pijlers": ["Rendement", "Liquiditeit", "Resource Planning", "Capaciteitsplanning"],
    "huidige_pijler": 0,  # index: 0=Rendement
    "cyclus_startdatum": "2026-02-02",  # Start pijler Rendement
    "weekfasen": {
        1: {"naam": "Norm", "beschrijving": "Professionele standaard neerzetten. Zelfreflectie triggeren."},
        2: {"naam": "Frictie", "beschrijving": "Spanning zichtbaar maken. Urgentie verhogen."},
        3: {"naam": "Autoriteit", "beschrijving": "Webinar. Bewijzen dat je weet hoe het moet."},
        4: {"naam": "Concretisering", "beschrijving": "Persoonlijk maken. Van theorie naar praktijk."},
    },
    "kpi_targets": {
        "toolgebruikers": (40, 60),
        "webinar_deelnemers": (15, 25),
        "gesprekken": (25, 35),
        "nieuwe_klanten_upsells": (8, 12),
    },
    "top_12": [
        "Castellum", "Unica", "Peters", "Barth", "Zenith",
        "Wassink", "Kremer", "Sankomij", "Beck", "Buijs",
        "PCT", "Megens Installaties",
    ],
    "klant_omzet": {
        "Castellum Security B.V.":                {"consultancy": 34600, "projecten": 34600, "abonnement": 0},
        "Unica Installatietechniek B.V.":         {"consultancy": 0,     "projecten": 54500, "abonnement": 2450},
        "Peters (HDF + Installatietechniek)":     {"consultancy": 15185, "projecten": 2600,  "abonnement": 4328},
        "Barth Groep B.V.":                       {"consultancy": 15446, "projecten": 0,     "abonnement": 0},
        "Installatiebedrijf D.W. Wassink B.V.":   {"consultancy": 8205,  "projecten": 1500,  "abonnement": 6182},
        "Installatietechniek Kremer B.V.":        {"consultancy": 6834,  "projecten": 2500,  "abonnement": 6611},
        "Zenith (Security + Nederland)":          {"consultancy": 13688, "projecten": 0,     "abonnement": 6800},
        "Sankomij Installatietechniek B.V.":      {"consultancy": 7268,  "projecten": 0,     "abonnement": 5514},
        "Beck & v/d Kroef Projecten B.V.":        {"consultancy": 5755,  "projecten": 1500,  "abonnement": 6428},
        "vdBuijsInstall":                         {"consultancy": 8194,  "projecten": -1100, "abonnement": 6800},
        "PCT Koudetechniek":                      {"consultancy": 6336,  "projecten": 550,   "abonnement": 5500},
        "Megens Installaties B.V.":               {"consultancy": 6569,  "projecten": 0,     "abonnement": 6611},
        "Alwako Installaties B.V.":               {"consultancy": 5060,  "projecten": 750,   "abonnement": 3500},
        "DKC Totaaltechniek B.V.":                {"consultancy": 5190,  "projecten": 0,     "abonnement": 6182},
        "Instain Groep B.V.":                     {"consultancy": 4682,  "projecten": 0,     "abonnement": 6611},
        "Hullenaar Balk Installatietechniek":     {"consultancy": 4600,  "projecten": 0,     "abonnement": 6182},
        "Van Abeelen Koeltechniek B.V.":          {"consultancy": 4135,  "projecten": 0,     "abonnement": 4475},
        "Rensen Regeltechniek B.V.":              {"consultancy": 3460,  "projecten": 0,     "abonnement": 2600},
        "Wetec B.V.":                             {"consultancy": 3454,  "projecten": 0,     "abonnement": 5500},
        "Verkade Installatiegroep B.V.":          {"consultancy": 2880,  "projecten": 550,   "abonnement": 4327},
        "Bigbrother B.V.":                        {"consultancy": 2818,  "projecten": 0,     "abonnement": 6182},
        "Grimbergen Installaties B.V.":           {"consultancy": 2735,  "projecten": 0,     "abonnement": 4450},
        "Vink Installatie Groep B.V.":            {"consultancy": 1210,  "projecten": 1500,  "abonnement": 6182},
        "W. Roodenburg Installatie Bedrijf B.V.": {"consultancy": 2599,  "projecten": 0,     "abonnement": 6611},
        "Sanitair-Installatie Hoogendoorn B.V.":  {"consultancy": 2320,  "projecten": 0,     "abonnement": 5131},
    },
    "omzet_totalen": {
        "consultancy": 208484,
        "projecten": 98837,
        "abonnement": 280535,
        "totaal": 585354,
        "klanten": 70,
    },
}

# Interne medewerkers uitsluiten uit Power BI views
INTERNE_MEDEWERKERS = [
    "mark leenders", "tobias boog", "arthur gartz",
    "chloe", "chloë", "notifica",
]

WEEK_ACTIES = {
    1: {  # Norm
        "arthur": [
            "Norm-post kernboodschap formuleren",
            "Maandthema scherp zetten",
            "Klantcase of voorbeeld aanleveren",
        ],
        "tobias": [
            "Webinar-aanmeldingen monitoren",
            "Funnel KPI's checken",
            "Warme leads uit vorige maand opvolgen",
        ],
        "chloe": [
            "LinkedIn post 1 publiceren (norm)",
            "Mail 1 versturen (webinar-uitnodiging)",
            "Contentkalender updaten",
        ],
        "bel_criteria": None,
    },
    2: {  # Frictie
        "arthur": [
            "Frictie-formuleringen aanleveren",
            "Inhoudelijke diepgang bewaken",
            "Content review LinkedIn post",
        ],
        "tobias": [
            "5-10 warme outreach calls (signaal-gebaseerd)",
            "DM's sturen naar geinteresseerden op LinkedIn",
            "Tool-CTA optimaliseren op website",
        ],
        "chloe": [
            "LinkedIn post 2 publiceren (frictie)",
            "Tool-link toevoegen aan content",
            "Rapportage aanmeldingen",
        ],
        "bel_criteria": "warm_outreach",
    },
    3: {  # Autoriteit / Webinar
        "arthur": [
            "Webinar presenteren",
            "Praktijkcases tonen",
            "Top 12 gesprekken voeren",
        ],
        "tobias": [
            "ALLE webinar-deelnemers bellen (binnen 48u!)",
            "Gesprekken plannen met geinteresseerden",
            "Tool-gebruikers en PDF-aanvragers opvolgen",
        ],
        "chloe": [
            "LinkedIn post 3 publiceren (praktijkvoorbeeld)",
            "Reminder-mail versturen",
            "Webinar techniek + logistics regelen",
        ],
        "bel_criteria": "webinar_followup",
    },
    4: {  # Concretisering
        "arthur": [
            "Top 12 architectgesprekken voeren",
            "Beschikbaar voor complexe trajecten",
        ],
        "tobias": [
            "Tool-gebruikers bellen",
            "PDF-aanvragers opvolgen",
            "Deals begeleiden",
            "KPI's rapporteren voor maandafsluiting",
        ],
        "chloe": [
            "LinkedIn post 4 publiceren (tool-CTA)",
            "Optionele warme mail naar engaged leads",
            "Maandrapportage maken",
        ],
        "bel_criteria": "tool_conversie",
    },
}
