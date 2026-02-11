# C-Track Maxx Ritregistratie

## Overzicht

C-Track Maxx is een standalone fleet tracking / ritregistratiesysteem. Dit subproject integreert C-Track data in het Syntess Data Warehouse via de C-Track Maxx WCF API (REST variant).

**API versie:** 4.0.4.271
**API docs:** https://uk2-fleet.ctrack.com/CtrackAPI/docs/index.html

## Architectuur

```
C-Track Maxx API (WCF/REST)
    ↓  GetVehicleDetailsByIdsRest
    ↓  GetDriverDetailsByDriverIDRest
    ↓  GetBusinessPrivateFullTripSummaryRest (max 48u per request)
Staging (stg.stg_ctrack_*)          ← sql_ctrack_staging.sql
    ↓  Conversie: meters→km, sec→min, UTC→CET
Prepare (prepare_ctrack.*)          ← sql_ctrack_prepare.sql
    ↓
SSM Views (ssm_ctrack.*)            ← sql_ctrack_ssm_views.sql
    ↓
Power BI Report (Ritregistratie)
```

## Kritieke conversies

| API eenheid | DWH eenheid | Factor |
|-------------|-------------|--------|
| Afstand: **meters** | km | / 1000 |
| Duur: **seconden** | minuten | / 60 |
| Kmstand: **meters** | km | / 1000 |
| Tijd: **UTC** | CET/CEST | AT TIME ZONE 'Europe/Amsterdam' |

## Schema's

| Schema | Doel | Objecten |
|--------|------|----------|
| `stg.stg_ctrack_*` | Ruwe API data | `stg_ctrack_voertuigen`, `stg_ctrack_bestuurders`, `stg_ctrack_ritten` |
| `prepare_ctrack.*` | Dimensies en feiten | `dim_voertuigen`, `dim_bestuurders`, `fct_ritten` |
| `ssm_ctrack.*` | SSM views voor Power BI | `"Voertuigen"`, `"Bestuurders"`, `"Ritten"`, `"Ritten samenvatting per maand"` |

## API Kenmerken

- **Authenticatie:** Token-based (verloopt na 10 min inactiviteit)
- **Max datum-range:** 48 uur per request (ritten)
- **Prive-ritten:** Locatie/coords worden null (privacy)
- **Geen trip ID:** API retourneert geen uniek rit-ID → surrogate key via `vehicle_id + start_datetime`
- **Business/Private:** Twee categorien ("Business" en "Private")

## Relatie met Syntess SSM

| C-Track | Syntess | Koppelveld |
|---------|---------|------------|
| Bestuurders | Medewerkers | `MedewerkerKey` (via naam of kostenplaats) |
| Voertuigen | Materieel | `MaterieelKey` (via genormaliseerd kenteken) |
| Ritten | Kalender | `Ritdatum` (datum join) |

## Bestanden

```
C_Track/
├── README.md                              ← dit bestand
├── API_Documentation/
│   └── C_Track_REST_API.md                ← Volledige API docs met alle endpoints
├── Source_Data_Schema/
│   └── C_Track_Datastructuur.md           ← Data contracts, conversies, privacy
└── ETL_Scripts/
    ├── ODS/
    │   └── sql_ctrack_staging.sql         ← Staging tabellen (echte API veldnamen)
    ├── Prepare/
    │   └── sql_ctrack_prepare.sql         ← Dimensies, feiten + conversies
    └── Endviews/
        └── sql_ctrack_ssm_views.sql       ← SSM views voor Power BI
```

## Checklist Nieuwe Klant

- [ ] C-Track API credentials ontvangen (username + password)
- [ ] `AcquireSecurityTokenRest` testen
- [ ] `GetBusinessGroupsRest` → business group ID bepalen
- [ ] `GetVehicleDetailsByIdsRest` → voertuigen laden
- [ ] `GetAllDriversByBusinessGroupIDRest` + details → bestuurders laden
- [ ] `GetBusinessPrivateFullTripSummaryRest` → ritten laden (48u blokken)
- [ ] Eenheden-conversie valideren (meters→km, seconden→minuten)
- [ ] UTC→CET/CEST tijdconversie valideren
- [ ] SSM views testen in Power BI
- [ ] Koppeling Bestuurders ↔ Syntess Medewerkers configureren
- [ ] Koppeling Voertuigen ↔ Syntess Materieel via kenteken verif.
