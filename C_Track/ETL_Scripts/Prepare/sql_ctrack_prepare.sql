-- ============================================
-- C-Track Maxx Prepare Scripts
-- Bron: stg.stg_ctrack_*
-- Doel: prepare_ctrack schema met dimensies en feiten
--
-- Pattern: Volgt AccountView prepare aanpak
-- (CREATE TABLE AS SELECT + indexen)
--
-- CONVERSIES (kritiek!):
-- - Distance: meters → km (/ 1000.0)
-- - Duration: seconden → minuten (/ 60.0)
-- - Odometer: meters → km (/ 1000.0)
-- - DateTime: UTC → Europe/Amsterdam
--
-- Auteur: Notifica
-- Datum: Februari 2026
-- ============================================

CREATE SCHEMA IF NOT EXISTS prepare_ctrack;


-- ============================================
-- 1. DIM_VOERTUIGEN
-- Bron: stg.stg_ctrack_voertuigen
-- API: GetVehicleDetailsByIdsRest
-- ============================================

DROP TABLE IF EXISTS prepare_ctrack.dim_voertuigen CASCADE;

CREATE TABLE prepare_ctrack.dim_voertuigen AS
SELECT
    ROW_NUMBER() OVER (ORDER BY vehicle_id) AS id,

    -- Ctrack identificatie
    vehicle_id::integer                 AS voertuig_id,
    registration::varchar(20)           AS kenteken,
    fleet_number::varchar(20)           AS vlootnummer,
    description::varchar(50)            AS omschrijving,
    make::varchar(50)                   AS merk,
    model::varchar(50)                  AS model,
    colour::varchar(50)                 AS kleur,
    vin_number::varchar(50)             AS chassisnummer,

    -- Afgeleide velden
    CONCAT(make, ' ', model)::varchar(100) AS voertuig_omschrijving,

    -- Genormaliseerd kenteken (zonder streepjes/spaties, hoofdletters) voor matching
    UPPER(REPLACE(REPLACE(registration, '-', ''), ' ', ''))::varchar(20) AS kenteken_norm,

    -- Kilometerstand (conversie meters → km)
    ROUND(COALESCE(odometer_m, 0) / 1000.0, 0)::integer AS kilometerstand_km,

    -- Gebruiksuren (conversie seconden → uren)
    ROUND(COALESCE(hours_sec, 0) / 3600.0, 1)::numeric(10,1) AS gebruiksuren,

    -- Tracking unit
    serial_number::varchar(50)          AS tracking_serienummer,

    -- Koppeling met Syntess materieel
    -- TODO: JOIN met Syntess prepare.stam_materieel op kenteken_norm
    NULL::integer                       AS materieelkey,

    -- Audit velden
    CURRENT_TIMESTAMP                   AS date_created,
    NULL::timestamp                     AS date_deleted

FROM stg.stg_ctrack_voertuigen
WHERE vehicle_id IS NOT NULL;

-- Indexen
CREATE INDEX idx_dim_voertuigen_id ON prepare_ctrack.dim_voertuigen(voertuig_id);
CREATE INDEX idx_dim_voertuigen_kenteken ON prepare_ctrack.dim_voertuigen(kenteken);
CREATE INDEX idx_dim_voertuigen_kenteken_norm ON prepare_ctrack.dim_voertuigen(kenteken_norm);


-- ============================================
-- 2. DIM_BESTUURDERS
-- Bron: stg.stg_ctrack_bestuurders
-- API: GetDriverDetailsByDriverIDRest
-- ============================================

DROP TABLE IF EXISTS prepare_ctrack.dim_bestuurders CASCADE;

CREATE TABLE prepare_ctrack.dim_bestuurders AS
SELECT
    ROW_NUMBER() OVER (ORDER BY driver_id) AS id,

    -- Ctrack identificatie
    driver_id::integer                  AS bestuurder_id,
    driver_first_name::varchar(100)     AS voornaam,
    driver_last_name::varchar(100)      AS achternaam,
    driver_full_name::varchar(200)      AS volledige_naam,
    cell_number::varchar(50)            AS mobiel,
    home_address::varchar(500)          AS thuisadres,
    postal_code::varchar(20)            AS postcode,
    cost_centre_id::integer             AS kostenplaats_id,
    licence_type::varchar(50)           AS rijbewijscategorie,
    is_active::boolean                  AS actief,

    -- Huidig toegewezen voertuig
    CASE WHEN assigned_vehicle_id = 0 THEN NULL
         ELSE assigned_vehicle_id
    END::integer                        AS toegewezen_voertuig_id,

    -- Koppeling met Syntess medewerkers
    -- TODO: Matching strategie bepalen (naam, kostenplaats, of handmatige mapping)
    NULL::integer                       AS medewerkerkey,

    -- Audit velden
    CURRENT_TIMESTAMP                   AS date_created,
    NULL::timestamp                     AS date_deleted

FROM stg.stg_ctrack_bestuurders
WHERE driver_id IS NOT NULL;

-- Indexen
CREATE INDEX idx_dim_bestuurders_id ON prepare_ctrack.dim_bestuurders(bestuurder_id);
CREATE INDEX idx_dim_bestuurders_naam ON prepare_ctrack.dim_bestuurders(volledige_naam);
CREATE INDEX idx_dim_bestuurders_actief ON prepare_ctrack.dim_bestuurders(actief);


-- ============================================
-- 3. FCT_RITTEN
-- Bron: stg.stg_ctrack_ritten
-- API: GetBusinessPrivateFullTripSummaryRest
--
-- CONVERSIES:
-- - distance_m → afstand_km (/ 1000)
-- - trip_duration_sec → rijtijd_minuten (/ 60)
-- - UTC → Europe/Amsterdam
-- ============================================

DROP TABLE IF EXISTS prepare_ctrack.fct_ritten CASCADE;

CREATE TABLE prepare_ctrack.fct_ritten AS
SELECT
    ROW_NUMBER() OVER (ORDER BY start_datetime, vehicle_id) AS id,

    -- Surrogate key (API heeft geen trip ID)
    MD5(vehicle_id::text || '|' || start_datetime::text)::varchar(32) AS rit_hash,

    -- Foreign keys (bron IDs)
    vehicle_id::integer                 AS voertuig_id,
    driver_id::integer                  AS bestuurder_id,

    -- Datum en tijd (conversie UTC → lokale tijd)
    start_datetime AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Amsterdam' AS start_tijdstip,
    stop_datetime AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Amsterdam'  AS eind_tijdstip,
    (start_datetime AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Amsterdam')::date AS ritdatum,
    EXTRACT(YEAR FROM start_datetime AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Amsterdam')::integer AS jaar,
    EXTRACT(MONTH FROM start_datetime AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Amsterdam')::integer AS maand,
    EXTRACT(DOW FROM start_datetime AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Amsterdam')::integer AS dag_van_week,

    -- Locatie (null bij prive-ritten)
    start_location::varchar(500)        AS vertreklocatie,
    stop_location::varchar(500)         AS aankomstlocatie,
    start_lat::numeric(10,5)            AS vertrek_lat,
    start_lon::numeric(10,5)            AS vertrek_lon,
    stop_lat::numeric(10,5)             AS aankomst_lat,
    stop_lon::numeric(10,5)             AS aankomst_lon,

    -- Afstand (conversie meters → km)
    ROUND(COALESCE(distance_m, 0) / 1000.0, 2)::numeric(10,2) AS afstand_km,

    -- Rijtijd (conversie seconden → minuten)
    ROUND(COALESCE(trip_duration_sec, 0) / 60.0, 1)::numeric(10,1) AS rijtijd_minuten,

    -- Kilometerstand bij einde rit (conversie meters → km)
    ROUND(COALESCE(stop_odometer_m, 0) / 1000.0, 0)::integer AS kilometerstand_km,

    -- Zakelijk/Prive status
    trip_status::varchar(20)            AS ritcategorie_code,
    CASE trip_status
        WHEN 'Business' THEN 'Zakelijk'
        WHEN 'Private'  THEN 'Prive'
        ELSE COALESCE(trip_status, 'Onbekend')
    END::varchar(50)                    AS ritcategorie,

    -- Is dit een prive-rit? (handig voor filtering)
    (trip_status = 'Private')::boolean  AS is_prive,

    -- Audit velden
    CURRENT_TIMESTAMP                   AS date_created,
    NULL::timestamp                     AS date_deleted

FROM stg.stg_ctrack_ritten
WHERE vehicle_id IS NOT NULL
  AND start_datetime IS NOT NULL;

-- Indexen voor performance
CREATE INDEX idx_fct_ritten_datum ON prepare_ctrack.fct_ritten(ritdatum);
CREATE INDEX idx_fct_ritten_jaar_maand ON prepare_ctrack.fct_ritten(jaar, maand);
CREATE INDEX idx_fct_ritten_voertuig ON prepare_ctrack.fct_ritten(voertuig_id);
CREATE INDEX idx_fct_ritten_bestuurder ON prepare_ctrack.fct_ritten(bestuurder_id);
CREATE INDEX idx_fct_ritten_categorie ON prepare_ctrack.fct_ritten(ritcategorie_code);
CREATE INDEX idx_fct_ritten_hash ON prepare_ctrack.fct_ritten(rit_hash);


-- ============================================
-- STATISTIEKEN
-- ============================================

SELECT 'dim_voertuigen' AS tabel, COUNT(*) AS aantal FROM prepare_ctrack.dim_voertuigen
UNION ALL
SELECT 'dim_bestuurders', COUNT(*) FROM prepare_ctrack.dim_bestuurders
UNION ALL
SELECT 'fct_ritten', COUNT(*) FROM prepare_ctrack.fct_ritten;
