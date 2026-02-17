-- ============================================
-- C-Track Maxx Staging Tables
-- Bron: C-Track Maxx REST API (WCF)
-- Doel: stg schema - ruwe API data opslag
--
-- API docs: https://uk2-fleet.ctrack.com/CtrackAPI/docs/index.html
--
-- LET OP:
-- - Afstanden in METERS (niet km!)
-- - Tijdsduren in SECONDEN
-- - DateTimes in UTC
-- - Geen trip_id in API → surrogate key nodig
--
-- Auteur: Notifica
-- Datum: Februari 2026
-- ============================================

CREATE SCHEMA IF NOT EXISTS stg;


-- ============================================
-- 1. VOERTUIGEN
-- Bron: GetVehicleDetailsByIdsRest
-- ============================================

DROP TABLE IF EXISTS stg.stg_ctrack_voertuigen CASCADE;

CREATE TABLE stg.stg_ctrack_voertuigen (
    -- VehicleDetails contract
    vehicle_id          INTEGER         NOT NULL,       -- Id
    registration        VARCHAR(20),                    -- Registration (kenteken)
    fleet_number        VARCHAR(20),                    -- FleetNumber (niet uniek!)
    description         VARCHAR(50),                    -- Description
    make                VARCHAR(50),                    -- Make (merk, niet gestandaardiseerd)
    model               VARCHAR(50),                    -- Model
    colour              VARCHAR(50),                    -- Colour
    vin_number          VARCHAR(50),                    -- VinNumber (chassisnummer)
    engine_number       VARCHAR(50),                    -- EngineNumber
    odometer_m          INTEGER,                        -- Odometer (in METERS)
    hours_sec           INTEGER,                        -- Hours (in SECONDEN)
    profile_id          INTEGER,                        -- ProfileID
    serial_number       VARCHAR(50),                    -- SerialNumber (tracking unit)
    unit_type_id        INTEGER,                        -- UnitTypeId

    -- Audit velden
    _loaded_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (vehicle_id)
);


-- ============================================
-- 2. BESTUURDERS
-- Bron: GetDriverDetailsByDriverIDRest
-- (eerst IDs ophalen via GetAllDriversByBusinessGroupIDRest)
-- ============================================

DROP TABLE IF EXISTS stg.stg_ctrack_bestuurders CASCADE;

CREATE TABLE stg.stg_ctrack_bestuurders (
    -- DriverDetails contract
    driver_id           INTEGER         NOT NULL,       -- DriverId
    driver_name         VARCHAR(200),                   -- DriverName
    driver_first_name   VARCHAR(100),                   -- DriverFirstName
    driver_last_name    VARCHAR(100),                   -- DriverLastName
    driver_full_name    VARCHAR(200),                   -- DriverFullName
    assigned_vehicle_id INTEGER,                        -- AssignedVehicleId (0 = geen)
    assigned_vehicle_registration VARCHAR(20),           -- AssignedVehicleRegistration
    driver_key          VARCHAR(100),                   -- DriverKey (Dallas Key hex)
    cell_number         VARCHAR(50),                    -- CellNumber
    home_address        VARCHAR(500),                   -- DriverHomeAddress
    postal_code         VARCHAR(20),                    -- DriverPostalCode
    cost_centre_id      INTEGER,                        -- CostCentreID
    licence_type        VARCHAR(50),                    -- DriverLicenceType
    is_active           BOOLEAN,                        -- DriverIsInUser

    -- Audit velden
    _loaded_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (driver_id)
);


-- ============================================
-- 3. RITTEN
-- Bron: GetBusinessPrivateFullTripSummaryRest
--
-- LET OP: API retourneert GEEN trip ID!
-- Surrogate key: vehicle_id + start_datetime
-- Max 48 uur per request
-- Prive-ritten: coords/locatie = null
-- ============================================

DROP TABLE IF EXISTS stg.stg_ctrack_ritten CASCADE;

CREATE TABLE stg.stg_ctrack_ritten (
    -- BusinessPrivateFullTripSummary contract
    vehicle_id          INTEGER         NOT NULL,       -- VehicleID
    vehicle_identifier  VARCHAR(50),                    -- VehicleIdentifier
    vehicle_name        VARCHAR(100),                   -- VehicleName
    driver_id           INTEGER,                        -- DriverID
    driver_name         VARCHAR(200),                   -- DriverName
    driver_identifier   VARCHAR(50),                    -- DriverIdentifier
    start_datetime      TIMESTAMP       NOT NULL,       -- StartDateTime (UTC)
    stop_datetime       TIMESTAMP,                      -- StopDateTime (UTC)
    trip_status         VARCHAR(20),                    -- BusinessPrivateTripStatus ("Business"/"Private")
    trip_duration_sec   INTEGER,                        -- TripDuration (in SECONDEN)
    start_lat           NUMERIC(10,5),                  -- StartLatitude (null bij prive)
    start_lon           NUMERIC(10,5),                  -- StartLongitude (null bij prive)
    stop_lat            NUMERIC(10,5),                  -- StopLatitude (null bij prive)
    stop_lon            NUMERIC(10,5),                  -- StopLongitude (null bij prive)
    distance_m          NUMERIC(12,2),                  -- Distance (in METERS)
    stop_odometer_m     NUMERIC(12,2),                  -- StopOdoMeterValue (in meters)
    start_location      VARCHAR(500),                   -- StartLocation (leeg bij prive)
    stop_location       VARCHAR(500),                   -- StopLocation (leeg bij prive)

    -- Audit velden
    _loaded_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,

    -- Surrogate key: combinatie vehicle + starttijd is uniek per rit
    PRIMARY KEY (vehicle_id, start_datetime)
);

-- Index voor datum-range queries
CREATE INDEX idx_stg_ritten_datetime ON stg.stg_ctrack_ritten(start_datetime);
CREATE INDEX idx_stg_ritten_status ON stg.stg_ctrack_ritten(trip_status);


-- ============================================
-- STATISTIEKEN
-- ============================================

SELECT 'stg_ctrack_voertuigen' AS tabel, COUNT(*) AS aantal FROM stg.stg_ctrack_voertuigen
UNION ALL
SELECT 'stg_ctrack_bestuurders', COUNT(*) FROM stg.stg_ctrack_bestuurders
UNION ALL
SELECT 'stg_ctrack_ritten', COUNT(*) FROM stg.stg_ctrack_ritten;
