# C-Track Maxx API (v4.0.4.271)

## Overzicht

De Ctrack Maxx API is gebouwd met Windows Communication Foundation (WCF) en ondersteunt zowel SOAP 1.2 (XML) als JSON/REST. Voor integratie gebruiken we de **REST variant**.

## Base URLs

| Service | SOAP | REST |
|---------|------|------|
| Membership | `../Membership.svc` | `../Membership.svc/Rest/` |
| TrackingUnit | `../TrackingUnit.svc` | `../TrackingUnit.svc/Rest/` |
| Drivers | `../Drivers.svc` | `../Drivers.svc/Rest/` |

**Productie:** `https://uk2-fleet.ctrack.com/CtrackAPI/`
**Documentatie:** https://uk2-fleet.ctrack.com/CtrackAPI/docs/index.html

## Authenticatie

Token-based authenticatie:

```
POST Membership.svc/Rest/AcquireSecurityTokenRest?username={user}&password={pass}
→ Returns: Validation object met token
```

- Token verloopt na **10 minuten** inactiviteit
- Gebruik `ValidateTokenRest` om timer te resetten
- `ReleaseSecurityToken` om token vrij te geven
- Max **3600 calls/uur** voor token-operaties

## Standaarden & Limieten

| Aspect | Waarde |
|--------|--------|
| Afstanden | **Meters** (niet km!) |
| Snelheden | km/u |
| Tijdsduur | **Seconden** |
| Coordinaten | Decimaal, 5 decimalen |
| DateTime formaat | `YYYY-MM-DD HH:MM:SS` (UTC) |
| Max datum-range | **48 uur** per request |
| Max batch grootte | **2.000 vehicle/driver IDs** |
| TLS | v1.2 |

---

## Endpoints - Membership Service

### AcquireSecurityTokenRest
- **URL:** `Membership.svc/Rest/AcquireSecurityTokenRest?username={user}&password={pass}`
- **Returns:** `Validation` (bevat token)
- **Rate limit:** Max 3600/uur

### ValidateTokenRest
- **URL:** `Membership.svc/Rest/ValidateTokenRest?token={token}`
- **Returns:** `ValidToken`

### GetBusinessGroupsRest
- **URL:** `Membership.svc/Rest/GetBusinessGroupsRest?token={token}`
- **Returns:** `List<BusinessGroup>`
- **Rate limit:** Max 60/uur

### GetUserDetailsRest
- **URL:** `Membership.svc/Rest/GetUserDetailsRest?token={token}&username={user}`
- **Returns:** `User`
- **Rate limit:** Max 60/uur (alleen eigen account)

---

## Endpoints - TrackingUnit Service (KERN voor ritregistratie)

### GetBusinessPrivateFullTripSummaryRest (PRIMAIR)
- **URL:** `TrackingUnit.svc/Rest/GetBusinessPrivateFullTripSummaryRest?token={token}&vehicleIds={ids}&startdatetime={start}&enddatetime={end}`
- **Returns:** `List<BusinessPrivateFullTripSummary>`
- **Max range:** 48 uur
- **LET OP:** Prive-ritten retourneren beperkte data (alleen datum, geen coords/locatie)

**Response velden:**

| Veld | Type | Beschrijving | DWH mapping |
|------|------|-------------|-------------|
| `VehicleID` | int | Ctrack voertuig ID | `vehicle_id` |
| `VehicleIdentifier` | string | Maxx identifier | `vehicle_identifier` |
| `VehicleName` | string | Voertuignaam | `vehicle_name` |
| `DriverID` | int | Ctrack bestuurder ID | `driver_id` |
| `DriverName` | string | Naam bestuurder | `driver_name` |
| `DriverIdentifier` | string | Maxx identifier | `driver_identifier` |
| `StartDateTime` | string | Start UTC `YYYY-MM-DD HH:MM:SS` | `start_datetime` |
| `StopDateTime` | string | Einde UTC `YYYY-MM-DD HH:MM:SS` | `stop_datetime` |
| `BusinessPrivateTripStatus` | string | `"Business"` / `"Private"` | `trip_status` |
| `TripDuration` | int | Duur in **seconden** | `trip_duration_sec` |
| `StartLatitude` | decimal? | Start breedtegraad (null bij prive) | `start_lat` |
| `StartLongitude` | decimal? | Start lengtegraad (null bij prive) | `start_lon` |
| `StopLatitude` | decimal? | Eind breedtegraad (null bij prive) | `stop_lat` |
| `StopLongitude` | decimal? | Eind lengtegraad (null bij prive) | `stop_lon` |
| `Distance` | decimal | Afstand in **meters** | `distance_m` |
| `StopOdoMeterValue` | decimal | Kilometerstand bij einde | `stop_odometer_m` |
| `StartLocation` | string | Vertreklocatie (leeg bij prive) | `start_location` |
| `StopLocation` | string | Aankomstlocatie (leeg bij prive) | `stop_location` |

### GetFullTripSummaryRest
- Zelfde als boven maar **zonder** Business/Private status
- Gebruik `GetBusinessPrivateFullTripSummaryRest` als zakelijk/prive onderscheid nodig is

### GetTripSummaryByIdRest
- **URL:** `TrackingUnit.svc/Rest/GetTripSummaryByIdRest?token={token}&vehicleid={id}&startdatetime={start}&enddatetime={end}`
- **Returns:** `List<TripSummary>` (beperkte velden)

**TripSummary velden:**

| Veld | Type | Beschrijving |
|------|------|-------------|
| `VehicleName` | string | Voertuignaam |
| `StartDateTime` | string | Start UTC |
| `EndDateTime` | string | Einde UTC |
| `Distance` | int | Afstand in **meters** |
| `Duration` | int | Duur in **seconden** |

### GetVehicleDetailsByIdsRest
- **URL:** `TrackingUnit.svc/Rest/GetVehicleDetailsByIdsRest?token={token}&vehicleids={ids}`
- **Returns:** `List<VehicleDetails>`

**VehicleDetails velden:**

| Veld | Type | Beschrijving | DWH mapping |
|------|------|-------------|-------------|
| `Id` | int | Ctrack voertuig ID | `vehicle_id` |
| `Registration` | string | Kenteken (max 20) | `registration` |
| `FleetNumber` | string | Vlootnummer (max 20) | `fleet_number` |
| `Description` | string | Omschrijving (max 50) | `description` |
| `Make` | string | Merk (max 50) | `make` |
| `Model` | string | Model (max 50) | `model` |
| `Colour` | string | Kleur (max 50) | `colour` |
| `VinNumber` | string | Chassisnummer (max 50) | `vin_number` |
| `EngineNumber` | string | Motornummer (max 50) | `engine_number` |
| `Odometer` | int? | Kmstand in **meters** | `odometer_m` |
| `Hours` | int? | Gebruiksuren in **seconden** | `hours_sec` |
| `ProfileID` | int? | Profiel ID | `profile_id` |
| `SerialNumber` | string | Tracking unit serienummer | `serial_number` |
| `UnitTypeId` | int | Tracking unit type | `unit_type_id` |

### GetVehicleMappingsByVehicleRegistrationsRest
- **URL:** `TrackingUnit.svc/Rest/GetVehicleMappingsByVehicleRegistrationsRest?token={token}&vehicleregs={regs}`
- **Returns:** `List<VehicleMapping>`
- Handig om VehicleID op te zoeken via kenteken

### GetLatestVehicleStatesByIdRest
- **URL:** `TrackingUnit.svc/Rest/GetLatestVehicleStatesByIdRest?token={token}&vehicleids={ids}`
- **Returns:** `List<VehicleState>`

### GetVehicleOdometerByIdAndDatetimeRest
- **URL:** `TrackingUnit.svc/Rest/GetVehicleOdometerByIdAndDatetimeRest?token={token}&vehicleid={id}&datetime={dt}`
- **Returns:** `VehicleOdo`

---

## Endpoints - Drivers Service

### GetAllDriversByBusinessGroupIDRest
- **URL:** `Drivers.svc/Rest/GetAllDriversByBusinessGroupIDRest?token={token}&bgid={id}`
- **Returns:** `List<DriverMapping>` (alle bestuurders in business group + subgroepen)

### GetDriverDetailsByDriverIDRest
- **URL:** `Drivers.svc/Rest/GetDriverDetailsByDriverIDRest?token={token}&driverid={id}`
- **Returns:** `DriverDetails`

**DriverDetails velden:**

| Veld | Type | Beschrijving | DWH mapping |
|------|------|-------------|-------------|
| `DriverId` | int | Uniek bestuurder ID (read-only) | `driver_id` |
| `DriverName` | string | Naam | `driver_name` |
| `DriverFirstName` | string | Voornaam | `driver_first_name` |
| `DriverLastName` | string | Achternaam | `driver_last_name` |
| `DriverFullName` | string | Volledige naam | `driver_full_name` |
| `AssignedVehicleId` | int | Toegewezen voertuig (0 = geen) | `assigned_vehicle_id` |
| `AssignedVehicleRegistration` | string | Kenteken toegewezen voertuig | - |
| `AssignedVehicleDescription` | string | Voertuig omschrijving | - |
| `DriverKey` | string | Dallas Key (hex) | `driver_key` |
| `CellNumber` | string | Mobiel nummer | `cell_number` |
| `DriverHomeAddress` | string | Thuisadres | `home_address` |
| `DriverPostalCode` | string | Postcode | `postal_code` |
| `CostCentreID` | int | Kostenplaats ID | `cost_centre_id` |
| `DriverLicenceType` | string | Rijbewijscategorie | `licence_type` |
| `DriverIsInUser` | bool | Actief ja/nee | `is_active` |

---

## Aanbevolen ETL Strategie

### Dagelijkse sync flow:
1. `AcquireSecurityTokenRest` -> token ophalen
2. `GetBusinessGroupsRest` -> business group ID ophalen
3. `GetAllDriversByBusinessGroupIDRest` -> alle bestuurders ophalen
4. Per bestuurder: `GetDriverDetailsByDriverIDRest` -> details
5. `GetVehicleDetailsByIdsRest` -> alle voertuigen ophalen
6. Per 48-uur blok: `GetBusinessPrivateFullTripSummaryRest` -> ritten ophalen
7. `ReleaseSecurityToken` -> token vrijgeven

### Belangrijke aandachtspunten:
- **48-uur limiet**: Ritten moeten in blokken van max 48 uur opgehaald worden
- **Rate limits**: Max 3600 calls/uur voor auth, overige endpoints varieren
- **Meters -> km**: Distance velden zijn in METERS, converteren naar km in prepare laag
- **Seconden -> minuten**: TripDuration is in SECONDEN, converteren in prepare laag
- **UTC tijden**: Alle tijden in UTC, converteren naar CET/CEST in prepare laag
- **Prive-ritten**: Bij BusinessPrivate variant worden coords/locatie null voor prive-ritten
- **Geen trip_id**: De API retourneert GEEN uniek trip ID - genereer een surrogate key
