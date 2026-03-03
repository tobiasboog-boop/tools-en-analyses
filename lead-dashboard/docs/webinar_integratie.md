# Webinar Integratie — Fix & Documentatie

**Datum:** 3 maart 2026
**Status:** Gerepareerd en backfill uitgevoerd

---

## Wat was er mis?

Webinar-aanmelders werden niet als koopsignaal herkend in het lead-dashboard, ondanks dat ze via Formspree / Cloudflare Worker werden verwerkt.

### Root causes

| Probleem | Oorzaak | Gevolg |
|----------|---------|--------|
| **Geen Pipedrive deal** | `webinar-register.js` maakte wel een persoon en notitie aan, maar GEEN deal | Geen "Webinar aangemeld" fase zichtbaar in dashboard |
| **LEADSTATUS niet gelezen** | Dashboard las EmailOctopus tags (altijd leeg). Worker zet `LEADSTATUS` veld, geen tag | Webinar-flag werd nooit opgepakt |
| **Bestaande contacten niet geüpdatet** | EmailOctopus v1.6 heeft geen search-by-email endpoint. Worker kon bestaande contacten niet vinden | LEADSTATUS niet gezet voor reeds geregistreerde abonnees |
| **Pipedrive stage ontbrak** | Stage "Webinar aangemeld" bestond niet in Pipedrive | Kon niet als deal-fase worden gebruikt |

---

## Wat is er gerepareerd?

### 1. Pipedrive — Stage aangemaakt

Via de Pipedrive API is een nieuwe stage aangemaakt:

| Veld | Waarde |
|------|--------|
| Naam | Webinar aangemeld |
| Pipeline | Basisabonnement (ID 1) |
| Stage ID | **70** |

### 2. `webinar-register.js` — Deal aanmaken bij registratie

Toegevoegd: `pipedriveCreateDeal()` functie die een deal aanmaakt in stage 70.

**Aangepast gedrag:**
- Nieuwe registrant → persoon aangemaakt + notitie + **deal aangemaakt**
- Bestaande registrant → notitie toegevoegd + **deal aangemaakt**
- EmailOctopus → `LEADSTATUS: 'Webinar'` blijft (update van bestaande contacten via backfill)

### 3. `data.py` — `is_webinar` lezen uit EmailOctopus

`fetch_emailoctopus_subscribers()` leest nu het `LEADSTATUS` veld:

```python
leadstatus = (fields.get("LEADSTATUS") or "").strip()
"is_webinar": leadstatus.lower() == "webinar",
```

`_build_lead()` gebruikt dit als fallback als er geen Pipedrive deal is:

```python
webinar_bonus = 15 if (is_webinar and deal_bonus < 15) else 0
```

### 4. `_DEAL_STAGE_BONUS` — Webinar toegevoegd

```python
_DEAL_STAGE_BONUS = {
    "Webinar aangemeld": 15,   # nieuw
    "Offerte verstuurd": 10,   # was 20 → nu 10
    ...
}
```

### 5. Backfill — Historische aanmelders verwerkt

Script: `lead-dashboard/backfill_webinar.py`

Verwerkt alle bekende aanmelders (webinar 3 + 4 + eerdere stuurinformatie):

- **27 unieke e-mailadressen** verwerkt
- EmailOctopus: LEADSTATUS='Webinar' gezet (update bestaand / aanmaken nieuw)
- Pipedrive: deals aangemaakt (IDs 379–403) in stage "Webinar aangemeld"

Volledig rapport: [backfill_webinar_resultaat.md](backfill_webinar_resultaat.md)

---

## Scoring impact

Webinar-aanmelding telt nu als signaal:

| Signal | Punten | Bron |
|--------|--------|------|
| Webinar aangemeld (Pipedrive deal) | +15 | Pipedrive stage bonus |
| Webinar aangemeld (EmailOctopus LEADSTATUS) | +15 | Fallback als geen deal |

Een lead met webinar-aanmelding + enkele email-opens springt direct naar **HOT** (≥18 punten).

---

## Toekomstige aanmelders

Worden automatisch verwerkt via de gerepareerde `webinar-register.js`:

1. Formspree-formulier → Cloudflare Pages Function
2. EmailOctopus → contact aangemaakt/bijgewerkt met `LEADSTATUS: 'Webinar'`
3. Pipedrive → persoon + notitie + deal in stage "Webinar aangemeld" (ID 70)
4. Resend → bevestigingsmail met ICS-bijlage

### Bekende beperking — EmailOctopus bestaande contacten

EmailOctopus v1.6 API heeft geen `GET /contacts?search=email` endpoint. Toekomstige aanmelders die al in de lijst staan krijgen geen LEADSTATUS-update via de Worker. Dit wordt afgevangen door:
- Pipedrive deal (altijd aangemaakt, ook voor bestaanden) → dashboard pikt dit op via deal-fase
- Eventueel opnieuw uitvoeren van backfill script bij volgend webinar

---

## Bestanden

| Bestand | Wijziging |
|---------|-----------|
| `notifica_site/functions/api/webinar-register.js` | `pipedriveCreateDeal()` toegevoegd; deal altijd aanmaken |
| `lead-dashboard/data.py` | `is_webinar` lezen uit LEADSTATUS; `_build_lead()` webinar_bonus; stage bonus +15 |
| `lead-dashboard/app.py` | Glossary bijgewerkt met webinar-uitleg |
| `lead-dashboard/backfill_webinar.py` | Eenmalig backfill script |
| `lead-dashboard/docs/backfill_webinar_resultaat.md` | Resultaten backfill |

---

## Volgende stap bij nieuw webinar

1. Voeg aanmelders toe aan `WEBINAR_REGISTRATIONS` lijst in `backfill_webinar.py`
2. Voer het script opnieuw uit (idempotent: "al deal aanwezig" wordt overgeslagen)
3. Of: aanmelders komen automatisch binnen via het gerepareerde formulier
