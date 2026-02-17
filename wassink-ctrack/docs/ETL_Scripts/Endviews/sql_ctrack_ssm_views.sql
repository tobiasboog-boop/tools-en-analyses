-- ============================================
-- C-Track Maxx SSM Views
-- Semantic model views voor Power BI
--
-- Pattern: ssm_ctrack."ViewName"
-- Naming: Nederlandse quoted identifiers,
--         consistent met ssm_av conventie
--
-- Data is al geconverteerd in prepare laag:
-- - Afstanden in km
-- - Tijden in minuten
-- - DateTime in Europe/Amsterdam
--
-- Auteur: Notifica
-- Datum: Februari 2026
-- ============================================

CREATE SCHEMA IF NOT EXISTS ssm_ctrack;


-- ============================================
-- 1. VOERTUIGEN VIEW
-- Dimensie: alle voertuigen
-- Bron API: GetVehicleDetailsByIdsRest
-- ============================================

CREATE OR REPLACE VIEW ssm_ctrack."Voertuigen"
AS
SELECT
    v.id                                AS "VoertuigKey",
    v.voertuig_id                       AS "Voertuig ID",
    v.kenteken                          AS "Kenteken",
    v.vlootnummer                       AS "Vlootnummer",
    v.merk                              AS "Merk",
    v.model                             AS "Model",
    v.voertuig_omschrijving             AS "Voertuig omschrijving",
    v.kleur                             AS "Kleur",
    v.chassisnummer                     AS "Chassisnummer",
    v.kilometerstand_km                 AS "Kilometerstand (km)",
    v.gebruiksuren                      AS "Gebruiksuren",
    v.materieelkey                      AS "MaterieelKey"       -- FK naar Syntess SSM Materieel
FROM prepare_ctrack.dim_voertuigen v
WHERE v.date_deleted IS NULL;


-- ============================================
-- 2. BESTUURDERS VIEW
-- Dimensie: alle bestuurders
-- Bron API: GetDriverDetailsByDriverIDRest
-- ============================================

CREATE OR REPLACE VIEW ssm_ctrack."Bestuurders"
AS
SELECT
    b.id                                AS "BestuurderKey",
    b.bestuurder_id                     AS "Bestuurder ID",
    b.volledige_naam                    AS "Bestuurder",
    b.voornaam                          AS "Voornaam",
    b.achternaam                        AS "Achternaam",
    b.kostenplaats_id                   AS "Kostenplaats ID",
    b.rijbewijscategorie                AS "Rijbewijscategorie",
    b.actief                            AS "Actief",
    b.medewerkerkey                     AS "MedewerkerKey"      -- FK naar Syntess SSM Medewerkers
FROM prepare_ctrack.dim_bestuurders b
WHERE b.date_deleted IS NULL;


-- ============================================
-- 3. RITTEN VIEW
-- Feitentabel: alle individuele ritten
-- Bron API: GetBusinessPrivateFullTripSummaryRest
-- ============================================

CREATE OR REPLACE VIEW ssm_ctrack."Ritten"
AS
SELECT
    r.id                                AS "RitKey",
    r.rit_hash                          AS "Rit hash",

    -- Foreign keys
    v.id                                AS "VoertuigKey",
    b.id                                AS "BestuurderKey",

    -- Datum en tijd (al geconverteerd naar CET/CEST)
    r.ritdatum                          AS "Ritdatum",
    r.start_tijdstip                    AS "Start tijdstip",
    r.eind_tijdstip                     AS "Eind tijdstip",
    r.jaar                              AS "Jaar",
    r.maand                             AS "Maand",
    r.dag_van_week                      AS "Dag van week",

    -- Locatie (null bij prive-ritten)
    r.vertreklocatie                    AS "Vertreklocatie",
    r.aankomstlocatie                   AS "Aankomstlocatie",

    -- Metrics (al geconverteerd naar km/minuten)
    r.afstand_km                        AS "Afstand (km)",
    r.rijtijd_minuten                   AS "Rijtijd (min)",
    r.kilometerstand_km                 AS "Kilometerstand (km)",

    -- Categorie
    r.ritcategorie_code                 AS "Ritcategorie code",
    r.ritcategorie                      AS "Ritcategorie",
    r.is_prive                          AS "Is prive"

FROM prepare_ctrack.fct_ritten r

LEFT JOIN prepare_ctrack.dim_voertuigen v
    ON r.voertuig_id = v.voertuig_id
    AND v.date_deleted IS NULL

LEFT JOIN prepare_ctrack.dim_bestuurders b
    ON r.bestuurder_id = b.bestuurder_id
    AND b.date_deleted IS NULL

WHERE r.date_deleted IS NULL;


-- ============================================
-- 4. RITTEN SAMENVATTING PER MAAND VIEW
-- Geaggregeerde view per voertuig/bestuurder/maand
-- ============================================

CREATE OR REPLACE VIEW ssm_ctrack."Ritten samenvatting per maand"
AS
SELECT
    ROW_NUMBER() OVER (
        ORDER BY r.jaar, r.maand, r.voertuig_id, r.bestuurder_id
    )                                   AS "SamenvattingKey",

    -- Foreign keys
    v.id                                AS "VoertuigKey",
    b.id                                AS "BestuurderKey",

    -- Periode
    r.jaar                              AS "Jaar",
    r.maand                             AS "Maand",
    MAKE_DATE(r.jaar, r.maand, 1)       AS "Periode datum",

    -- Totalen
    COUNT(*)                            AS "Aantal ritten",
    SUM(r.afstand_km)                   AS "Totale afstand (km)",
    SUM(r.rijtijd_minuten)              AS "Totale rijtijd (min)",

    -- Per categorie (Business = Zakelijk, Private = Prive)
    SUM(CASE WHEN r.ritcategorie = 'Zakelijk'
        THEN r.afstand_km ELSE 0 END)  AS "Zakelijke km",
    SUM(CASE WHEN r.ritcategorie = 'Prive'
        THEN r.afstand_km ELSE 0 END)  AS "Prive km",

    -- Tellingen per categorie
    SUM(CASE WHEN r.ritcategorie = 'Zakelijk'
        THEN 1 ELSE 0 END)             AS "Aantal zakelijke ritten",
    SUM(CASE WHEN r.ritcategorie = 'Prive'
        THEN 1 ELSE 0 END)             AS "Aantal prive ritten"

FROM prepare_ctrack.fct_ritten r

LEFT JOIN prepare_ctrack.dim_voertuigen v
    ON r.voertuig_id = v.voertuig_id
    AND v.date_deleted IS NULL

LEFT JOIN prepare_ctrack.dim_bestuurders b
    ON r.bestuurder_id = b.bestuurder_id
    AND b.date_deleted IS NULL

WHERE r.date_deleted IS NULL

GROUP BY
    v.id, b.id,
    r.voertuig_id, r.bestuurder_id,
    r.jaar, r.maand;


-- ============================================
-- VALIDATIE QUERIES
-- ============================================

-- Check: Aantal records per view
SELECT 'Voertuigen' AS view_name, COUNT(*) AS records FROM ssm_ctrack."Voertuigen"
UNION ALL
SELECT 'Bestuurders', COUNT(*) FROM ssm_ctrack."Bestuurders"
UNION ALL
SELECT 'Ritten', COUNT(*) FROM ssm_ctrack."Ritten"
UNION ALL
SELECT 'Ritten samenvatting per maand', COUNT(*) FROM ssm_ctrack."Ritten samenvatting per maand";

-- Check: Ritten per categorie
SELECT
    "Ritcategorie",
    COUNT(*) AS aantal_ritten,
    SUM("Afstand (km)") AS totale_km,
    ROUND(AVG("Afstand (km)"), 1) AS gem_km_per_rit,
    ROUND(AVG("Rijtijd (min)"), 1) AS gem_minuten_per_rit
FROM ssm_ctrack."Ritten"
GROUP BY "Ritcategorie"
ORDER BY totale_km DESC;

-- Check: Ritten per voertuig
SELECT
    v."Kenteken",
    v."Voertuig omschrijving",
    COUNT(r."RitKey") AS aantal_ritten,
    SUM(r."Afstand (km)") AS totale_km
FROM ssm_ctrack."Voertuigen" v
LEFT JOIN ssm_ctrack."Ritten" r ON v."VoertuigKey" = r."VoertuigKey"
GROUP BY v."Kenteken", v."Voertuig omschrijving"
ORDER BY totale_km DESC;

-- Check: Orphaned ritten (zonder voertuig of bestuurder)
SELECT
    SUM(CASE WHEN "VoertuigKey" IS NULL THEN 1 ELSE 0 END) AS ritten_zonder_voertuig,
    SUM(CASE WHEN "BestuurderKey" IS NULL THEN 1 ELSE 0 END) AS ritten_zonder_bestuurder
FROM ssm_ctrack."Ritten";

-- Check: Prive-ritten zonder locatiedata (verwacht)
SELECT
    "Ritcategorie",
    COUNT(*) AS totaal,
    SUM(CASE WHEN "Vertreklocatie" IS NULL OR "Vertreklocatie" = '' THEN 1 ELSE 0 END) AS zonder_locatie
FROM ssm_ctrack."Ritten"
GROUP BY "Ritcategorie";
