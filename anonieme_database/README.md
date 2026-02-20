# Anonieme Demo-database

## Doel

Een kopie van klantdatabase **1225** omzetten naar een geanonimiseerde demo-database, zodat we rapporten en dashboards veilig kunnen demonstreren zonder klantgevoelige data te tonen.

## Hoe werkt het?

### Architectuur

```
┌──────────────────┐     GRIP kloon      ┌──────────────────┐
│  Database 1225   │ ──────────────────►  │  demo_1225       │
│  (origineel)     │                      │  (kopie)         │
└──────────────────┘                      └────────┬─────────┘
                                                   │
                                          Anonimisatie script
                                                   │
                                          ┌────────▼─────────┐
                                          │  demo_1225       │
                                          │  (geanonimiseerd)│
                                          └────────┬─────────┘
                                                   │
                                          ┌────────▼─────────┐
                                          │  Endviews (SSM)  │
                                          │  = views op      │
                                          │  prepare schema  │
                                          └────────┬─────────┘
                                                   │
                                          ┌────────▼─────────┐
                                          │  Power BI        │
                                          │  Semantisch      │
                                          │  Model           │
                                          └──────────────────┘
```

### Stappen

| Stap | Wie | Wat |
|------|-----|-----|
| 1 | **Dolf** | Database 1225 klonen via GRIP naar `demo_1225` |
| 2 | **Tobias** | Anonimisatiescript draaien op `demo_1225` |
| 3 | **Tobias** | Verificatie: steekproef dat alle namen/adressen zijn vervangen |
| 4 | **Tobias** | Power BI semantisch model koppelen aan endviews van `demo_1225` |

## Wat wordt geanonimiseerd?

Alle klantgevoelige **tekstuele** data wordt vervangen door realistische Nederlandse demodata. **Financiele bedragen en datums blijven intact** zodat de rapporten correct werken.

### Overzicht per categorie

| Categorie | Voorbeelden | Aanpak |
|-----------|------------|--------|
| **Relaties** | Klantnamen, leveranciers, debiteuren, crediteuren | → Nederlandse demobedrijfsnamen (bijv. "Bakker & Zonen BV") |
| **Medewerkers** | Monteurs, projectleiders, contactpersonen | → Nederlandse demonamen (bijv. "Jan de Vries") |
| **Adressen** | Straat, huisnummer, postcode, plaats | → Nederlandse demo-adressen (bijv. "Kerkstraat 42, 3511 MN Utrecht") |
| **Contact** | E-mail, telefoon, mobiel | → Demo-contactgegevens (bijv. "info@demo-123.nl") |
| **Identificatie** | KvK-nummer, BTW-nummer, IBAN | → Fictieve nummers |
| **Projecten** | Projectnamen, referenties | → Generieke projectnamen (bijv. "Renovatie Kantoorpand") |
| **Objecten** | Gebouwnamen, locaties | → Genummerde objecten (bijv. "Object 042") |
| **Werkbonnen** | Werkbontitels, meldpersonen | → Genummerde werkbonnen met demonamen |
| **Documenten** | Omschrijvingen in facturen, boekingen, orders | → Generieke omschrijvingen |

### Wat blijft INTACT?

- Alle financiele bedragen (debet, credit, kostprijs, verrekenprijs)
- Alle datums (boekdatum, factuurdatum, vervaldatum)
- Alle numerieke keys en referenties (gc_id, projectkey, etc.)
- Structuurcodes (dagboekcode, rubriekcode, kostensoortcode)
- Statusvelden (documentstatus, projectstatus)
- De volledige endview-structuur (SSM laag)

### Consistentie

Het script gebruikt **deterministische hashing**: dezelfde originele naam wordt altijd naar dezelfde demonaam vertaald. Dit betekent:
- Klant "X" heet overal "Bakker & Zonen BV" (in werkbonnen, facturen, projecten)
- Monteur "Y" heet overal "Jan de Vries" (in werkbonnen, sessies, planning)
- Adres "Z" is overal hetzelfde demo-adres

## Tabellen die worden aangepast

### Stamtabellen (master data)
- `stamrelaties` - Klant/leverancier/debiteur/crediteur namen, email, KvK, BTW
- `stamadministraties` - Bedrijfs-/administratienamen
- `stammedewerkers` - Alle persoonsgegevens medewerkers
- `stampersonen` - Persoonsgegevens
- `stamadressen` - Alle adressen
- `stambedrijfseenheden` - Bedrijfseenheid namen
- `stamafdelingen` - Afdelingnamen
- `stambestellingen` - Bestel-/leveranciersadressen
- `stammicrosoftauthenticatie` - Email, tenant/client IDs
- `stamdocumenten` - Documenttitels
- `stamoffertes` - Offerte-omschrijvingen
- `stamorders` - Ordertitels
- `stamorderregels` - Orderregelomschrijvingen
- `stamprojecttaken` - Administratienamen

### Dimensietabellen
- `dimobjecten` - Gebouwen, adressen, eigenaar/beheerder, contact
- `dimwerkbonnen` - Klant, monteur, contactpersoon, adres
- `dimprojecten` - Projecttitel, opdrachtgever, projectleider, adres
- `dimabonnementen` - Contactpersoon, serienummers
- `diminstallaties` - Installatienamen, locatie, serienummers
- `diminstallatiecomponenten` - Omschrijvingen, serienummers
- `dimmagazijnen` - Magazijnnamen
- `dimwerkbonparagrafen` - Factuurtekst
- `dimwerkbonoplossingen` - Oplossingstekst
- `dimbestekparagrafen` - Bestekparagraaf omschrijvingen

### Facttabellen
- `factverkoopfactuurtermijnen` - Debiteur + adres
- `factinkoopfactuurtermijnen` - Crediteur
- `factbetalingperopbrengstregel` - Debiteur
- `factbetalingperinkoopregel` - Crediteur
- `factopbrengsten` - Debiteur + adres + omschrijving
- `factjournaalregels` - Omschrijving
- `factkosten` - Omschrijving + documenttitel
- `factbankafschriftboekingregels` - IBAN, omschrijving, documenttitels
- `factbankregels` - Omschrijving
- `facteliminatiejournaalregels` - Administratienamen
- `factacties` - Contactpersoon, telefoon
- `factmobieleuitvoersessies` - Ondertekenaar, email
- `factcalculatiekostenregels` - Calculator, omschrijvingen
- `factdocumentparafeermedewerkers` - Opmerkingen
- `factmedewerkerverzuim` - Omschrijving
- `factsalarishistorie` - Omschrijving
- `factopvolgingen` - Beschrijving
- `factofferteregels` - Omschrijving
- `factwerkbonchecklistregels` - Antwoorden
- `facthandelorders` - Documenttitels, omschrijvingen
- `factorderseenmalig` - Documenttitels, omschrijvingen
- `factserviceordersprognose` - Documenttitels, omschrijvingen
- `factbestelregels` - Omschrijving
- `factbestelverzoekregels` - Omschrijving
- `factmaterieeluitgiftes` - Omschrijving
- `factplanbaremedewerkers` - Volledige persoonsgegevens
- `factplanningurenmedewerkers` - Volledige naam

### Extra tabellen
- `extrabijzondererelaties` - Relatienamen, filepaths
- `extrabudgetverzoeken` - Aanmaker, klantnaam, project, opmerkingen

## Bestanden

| Bestand | Doel |
|---------|------|
| `anonymize_demo.py` | Hoofdscript: verbindt met database, draait anonimisatie, verifieert |
| `anonymization.sql` | Alle UPDATE-statements met Nederlandse demodata |
| `verify_anonymization.sql` | Steekproef-queries om resultaat te controleren |
| `README.md` | Deze documentatie |

## Gebruik

### Vereisten
- Python 3.8+
- `psycopg2-binary` (`pip install psycopg2-binary`)
- Optioneel: `python-dotenv` voor .env bestand

### Commando

```bash
python anonymize_demo.py \
    --host 10.3.152.9 \
    --port 5432 \
    --database demo_1225 \
    --user postgres \
    --password <wachtwoord>
```

Of met `.env` bestand:

```bash
python anonymize_demo.py --env .env
```

### Verwachte doorlooptijd
Afhankelijk van databasegrootte, geschat 5-15 minuten voor een volledige anonimisatie.
