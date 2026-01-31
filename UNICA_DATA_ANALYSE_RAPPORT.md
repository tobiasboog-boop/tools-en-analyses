# Unica Data Analyse Rapport

## Fit/Gap Analyse: Syntess Data Beschikbaarheid

**Datum:** 29 januari 2026
**Doel:** Toetsing van Unica's data requirements aan beschikbare Syntess data
**Gebruik:** Voorbereiding meeting Unica (vrijdag)

---

## DEEL 1: FINANCE VRAGEN (E-mail Frederik)

### 1.1 Oneliner Vragen

| # | Vraag | Status | Toelichting |
|---|-------|--------|-------------|
| 1 | **Op welke categorieën wordt er per Syntess implementatie gebudgetteerd?** | **BESCHIKBAAR** | Tabel `factbudgetten` bevat: `rubriek_gc_id`, `kostplts_gc_id` (kostenplaats), `periode_gc_id`. Rubrieken in `stamrubrieken` met `rubriekgroep`, `rubriektype`. |
| 2 | **Op welke categorieën worden de actuals vastgelegd?** | **BESCHIKBAAR** | Tabel `factkosten` bevat: `kostensoortcode`, `kostensoort`, `categorie`, `kostplts_gc_id`. Tabel `factopbrengsten` voor omzet. |
| 3 | **Op welke categorieën wordt er geprognotiseerd?** | **BEPERKT** | Geen aparte prognose-tabel. Budget (`factbudgetten`) kan als prognose dienen. Service orders hebben `factserviceordersprognose`. |
| 4 | **Kennen de actuals een boekingsperiode?** | **BESCHIKBAAR** | Tabel `factjournaalregels` bevat: `boekdatum`, `periodecode`, `typeperiode`, `doorboekdatum`. Kosten hebben ook `boekdatum`. |
| 5 | **Koppeling sub-administratie ↔ hoofdadministratie via project als dimensie?** | **BESCHIKBAAR** | `factjournaalregels` bevat `werk_gc_id` (project-koppeling). `factkosten` en `factopbrengsten` hebben ook project-koppelingen. |
| 6 | **Hoe ziet het grootboekschema eruit?** | **BESCHIKBAAR** | Tabel `dimgrootboekrekeningen` met: `grootboekrekening_code`, `grootboekrekening_omschrijving`, `type_grootboekrekening`, `status_grootboekrekening`. Rekeningschema's via `stamrubrieken`. |
| 7 | **Welke projecttypes zijn er per systeem?** | **BESCHIKBAAR** | Tabel `dimprojecten` kolom `soort` bevat projecttypes (bijv. Regie, Fixed Price). Ook `factureerwijze_code` en `factureerwijze`. |
| 8 | **Hoe wordt winstneming per project gedaan?** | **ONDERZOEK NODIG** | Niet direct zichtbaar in standaard tabellen. Mogelijk klant-specifieke configuratie. Kan via `percentagegereed` in `dimprojecten` + kostenvergelijking worden berekend. |

### 1.2 IKB Vragen (uit e-mail)

| # | Vraag | Status | Toelichting |
|---|-------|--------|-------------|
| 1 | **KVK-vestigingsnummers per klant** | **GEDEELTELIJK** | `stamrelaties` bevat `kvknummer` (8 cijfers). **Vestigingsnummer (12 cijfers) is NIET standaard beschikbaar.** Dit moet mogelijk handmatig worden toegevoegd of via externe koppeling (Company.info). |
| 2 | **Relatie projecten → spin-off naar services** | **BEPERKT** | Geen directe koppeling. Kan afgeleid worden via `contract_gc_id` in `dimprojecten` en `dimabonnementen` met dezelfde `relatiekey`. Vereist maatwerk query. |
| 3 | **Spin-off binnen contract zichtbaar (modificaties)** | **BEPERKT** | Geen expliciete "modificatie" tracking. Contractwijzigingen kunnen via document-historie worden afgeleid (`stamoffertes` → `werk_gc_id`). |
| 4 | **Commerciële pijplijn (leads, kansen, MMW)** | **WORKAROUND MOGELIJK** | Syntess heeft `stamoffertes` met `scoringskans`, `offerte_status`, `urgentie`. **Workaround:** Project aanmaken met status "Lead" en calculatie op hoofdlijn toevoegen. Zo kan sales pipeline toch worden gevolgd. |

---

## DEEL 2: SAMENVATTING COMMERCIEEL (64 Requirements)

Zie Excel tabblad "Commercieel - 64 Requirements" voor volledige details.

### Telling per status:

| Status | Aantal | Betekenis |
|--------|--------|-----------|
| BESCHIKBAAR | 19 | Direct beschikbaar in Syntess DWH |
| WORKAROUND | 10 | Mogelijk via alternatieve werkwijze |
| BEPERKT | 15 | Gedeeltelijk beschikbaar of vereist maatwerk |
| NIET BESCHIKBAAR | 20 | Niet aanwezig - externe bron nodig |

---

## DEEL 3: KRITIEKE GAPS

| Gap | Impact | Oplossing |
|-----|--------|-----------|
| **Leads** | Geen CRM in Syntess | Workaround: project met status "Lead" + calculatie |
| **KVK-vestigingsnummer** | Alleen 8-cijferig KVK | Company.info koppeling |
| **Marktsegment klant** | Niet in Syntess | Via SBI-code of handmatig |
| **Forecast modellen** | S-curves niet beschikbaar | CE/BIS functionaliteit |
| **Business Unit** | Niet in Syntess | Unica mapping nodig |

---

## Bijlage: Relevante Syntess Tabellen

### Financieel
- `factbudgetten` - Budgetregels
- `factkosten` - Kostenregistraties
- `factopbrengsten` - Omzetregistraties
- `factjournaalregels` - Journaal entries
- `dimgrootboekrekeningen` - GLaccounts

### Projecten
- `dimprojecten` - Project master (soort, status, fases)
- `dimbestekparagrafen` - WBS elementen
- `factcalculatiekostenregels` - Calculaties

### Relaties
- `stamrelaties` - Klant/leverancier master (incl. KVK)
- `stamadressen` - Adresgegevens

### Contracten
- `dimabonnementen` - Contract/abonnement master
- `dimcontractsoorten` - Contract types

### Commercieel
- `stamoffertes` - Offerte master (met scoringskans)
- `factofferteregels` - Offerte bedragen
