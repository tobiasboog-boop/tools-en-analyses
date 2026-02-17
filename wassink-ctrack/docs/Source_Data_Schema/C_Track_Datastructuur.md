# C-Track Maxx Data Structuur

## API Data Contracts

Documentatie van de C-Track Maxx API data contracts en hun mapping naar het DWH.
Bron: https://uk2-fleet.ctrack.com/CtrackAPI/docs/index.html

### BusinessPrivateFullTripSummary (primair voor ritregistratie)

| Veld | Type | Nullable | Beschrijving | Eenheid |
|------|------|----------|-------------|---------|
| `VehicleID` | int | Nee | Uniek voertuig ID in Ctrack | - |
| `VehicleIdentifier` | string | Nee | Maxx identifier | - |
| `VehicleName` | string | Nee | Voertuignaam | - |
| `DriverID` | int | Nee | Uniek bestuurder ID in Ctrack | - |
| `DriverName` | string | Ja | Naam bestuurder | - |
| `DriverIdentifier` | string | Ja | Maxx identifier bestuurder | - |
| `StartDateTime` | string | Nee | Start rit (UTC) | `YYYY-MM-DD HH:MM:SS` |
| `StopDateTime` | string | Nee | Einde rit (UTC) | `YYYY-MM-DD HH:MM:SS` |
| `BusinessPrivateTripStatus` | string | Nee | "Business" of "Private" | - |
| `TripDuration` | int | Nee | Ritduur | **seconden** |
| `StartLatitude` | decimal? | Ja | Breedtegraad vertrek (null bij prive) | 5 decimalen |
| `StartLongitude` | decimal? | Ja | Lengtegraad vertrek (null bij prive) | 5 decimalen |
| `StopLatitude` | decimal? | Ja | Breedtegraad aankomst (null bij prive) | 5 decimalen |
| `StopLongitude` | decimal? | Ja | Lengtegraad aankomst (null bij prive) | 5 decimalen |
| `Distance` | decimal | Nee | Afgelegde afstand | **meters** |
| `StopOdoMeterValue` | decimal | Ja | Kilometerstand bij einde rit | **meters** |
| `StartLocation` | string | Ja | Vertreklocatie (leeg bij prive) | - |
| `StopLocation` | string | Ja | Aankomstlocatie (leeg bij prive) | - |

### VehicleDetails

| Veld | Type | Nullable | Beschrijving | Max lengte |
|------|------|----------|-------------|-----------|
| `Id` | int | Nee | Uniek voertuig ID | - |
| `Registration` | string | Ja | Kenteken | 20 |
| `FleetNumber` | string | Ja | Vlootnummer (niet uniek!) | 20 |
| `Description` | string | Ja | Omschrijving | 50 |
| `Make` | string | Ja | Merk (niet gestandaardiseerd!) | 50 |
| `Model` | string | Ja | Model | 50 |
| `Colour` | string | Ja | Kleur | 50 |
| `VinNumber` | string | Ja | Chassisnummer | 50 |
| `EngineNumber` | string | Ja | Motornummer | 50 |
| `Odometer` | int? | Ja | Kilometerstand | **meters** |
| `Hours` | int? | Ja | Gebruiksuren | **seconden** |
| `ProfileID` | int? | Ja | Profiel ID | - |
| `SerialNumber` | string | Ja | Tracking unit serienummer | - |
| `UnitTypeId` | int | Nee | Tracking unit type | - |

### DriverDetails

| Veld | Type | Nullable | Beschrijving |
|------|------|----------|-------------|
| `DriverId` | int | Nee | Uniek bestuurder ID (read-only) |
| `DriverFirstName` | string | Nee | Voornaam |
| `DriverLastName` | string | Nee | Achternaam |
| `DriverFullName` | string | Nee | Volledige naam |
| `DriverName` | string | Ja | Naam (display) |
| `AssignedVehicleId` | int | Nee | Toegewezen voertuig (0 = geen) |
| `AssignedVehicleRegistration` | string | Ja | Kenteken toegewezen voertuig |
| `AssignedVehicleDescription` | string | Ja | Omschrijving toegewezen voertuig |
| `DriverKey` | string | Ja | Dallas Key (hex) |
| `CellNumber` | string | Ja | Mobiel nummer |
| `DriverTelephoneNumber` | string | Ja | Telefoon |
| `DriverHomeAddress` | string | Ja | Thuisadres |
| `DriverPostalCode` | string | Ja | Postcode |
| `CostCentreID` | int | Nee | Kostenplaats ID |
| `DriverLicenceType` | string | Ja | Rijbewijscategorie |
| `DriverIsInUser` | bool | Nee | Actief ja/nee |

## Eenheden-conversie (KRITIEK)

| API eenheid | DWH eenheid | Conversie |
|-------------|-------------|-----------|
| Distance: **meters** | `afstand_km`: **km** | `/ 1000.0` |
| TripDuration: **seconden** | `rijtijd_minuten`: **minuten** | `/ 60.0` |
| Odometer: **meters** | `kilometerstand_km`: **km** | `/ 1000.0` |
| Hours: **seconden** | `gebruiksuren`: **uren** | `/ 3600.0` |
| DateTime: **UTC** | lokale tijd: **CET/CEST** | `AT TIME ZONE 'Europe/Amsterdam'` |

## Relatie met Syntess

| C-Track entiteit | Syntess entiteit | Koppelveld | Opmerking |
|-----------------|-----------------|------------|-----------|
| Driver | Medewerker | `DriverFullName` <-> medewerker naam | Fuzzy match nodig, of CostCentreID mapping |
| Vehicle | Materieel | `Registration` <-> kenteken | Normaliseer: streepjes/spaties verwijderen |

## Prive-ritten (privacy)

Bij `BusinessPrivateTripStatus = "Private"`:
- `StartDateTime` bevat alleen datum (geen tijd)
- `StartLatitude/Longitude` = null
- `StopLatitude/Longitude` = null
- `StartLocation` = leeg
- `StopLocation` = leeg
- `Distance` en `TripDuration` zijn WEL beschikbaar

## Geen Trip ID

De C-Track API retourneert **geen uniek trip ID**. Een surrogate key moet gegenereerd worden op basis van:
- `VehicleID` + `StartDateTime` (combinatie is uniek per rit)

## Verwachte volumes

| Entiteit | Geschat aantal | Groeisnelheid | API calls nodig |
|----------|---------------|---------------|-----------------|
| Voertuigen | ~20-50 | Laag | 1 call |
| Bestuurders | ~20-100 | Laag | 1 call + N detail calls |
| Ritten | ~100-500/dag | Hoog | Dag/48u blokken |
