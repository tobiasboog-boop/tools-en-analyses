-- WVC Contract Checker - Database Setup Script
-- Run this on the WVC production database with admin privileges
--
-- Usage:
--   psql -h <host> -U <admin_user> -d <database> -f setup.sql
--
-- After running, update .env with:
--   DB_USER=contract_checker_user
--   DB_PASSWORD=<the password you set below>

-- ============================================================
-- 1. CREATE DEDICATED USER
-- ============================================================
-- Change the password before running!
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'contract_checker_user') THEN
        CREATE USER contract_checker_user WITH PASSWORD 'CHANGE_THIS_PASSWORD';
    END IF;
END
$$;

-- ============================================================
-- 2. CREATE PILOT SCHEMA
-- ============================================================
CREATE SCHEMA IF NOT EXISTS contract_checker;

-- ============================================================
-- 3. GRANT READ ACCESS TO ALL SCHEMAS (except system schemas)
-- ============================================================
-- Grant USAGE and SELECT on all user schemas for reading werkbonnen
DO $$
DECLARE
    schema_record RECORD;
BEGIN
    FOR schema_record IN
        SELECT nspname FROM pg_namespace
        WHERE nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        AND nspname NOT LIKE 'pg_temp%'
        AND nspname NOT LIKE 'pg_toast_temp%'
        AND nspname != 'contract_checker'
    LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO contract_checker_user',
            schema_record.nspname);
        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO contract_checker_user',
            schema_record.nspname);
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT ON TABLES TO contract_checker_user',
            schema_record.nspname);
    END LOOP;
END
$$;

-- ============================================================
-- 4. GRANT FULL ACCESS TO PILOT SCHEMA ONLY
-- ============================================================
GRANT ALL PRIVILEGES ON SCHEMA contract_checker TO contract_checker_user;

-- Grant on existing objects
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA contract_checker
    TO contract_checker_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA contract_checker
    TO contract_checker_user;

-- Grant on future objects (important!)
ALTER DEFAULT PRIVILEGES IN SCHEMA contract_checker
    GRANT ALL ON TABLES TO contract_checker_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA contract_checker
    GRANT ALL ON SEQUENCES TO contract_checker_user;

-- ============================================================
-- 5. CREATE TABLES
-- ============================================================

-- Contracts metadata table: link contracts to clients
-- Populated via CSV import from WVC template
-- NOTE: One contract file can cover multiple clients (group contracts)
-- The combination (filename, client_id) is unique, not filename alone
CREATE TABLE IF NOT EXISTS contract_checker.contracts (
    id SERIAL PRIMARY KEY,

    -- Required fields (from WVC template)
    filename VARCHAR(255) NOT NULL,      -- Exact SharePoint filename (.docx/.xlsx)
    client_id VARCHAR(50) NOT NULL,      -- Syntess client ID (must match werkbon)

    -- Optional fields (from WVC template)
    client_name VARCHAR(255),
    contract_number VARCHAR(50),
    start_date DATE,                     -- Contract start date
    end_date DATE,                       -- Contract end date
    contract_type VARCHAR(50),           -- Standaard, Premium, Basis, etc.
    notes TEXT,

    -- System fields
    filepath TEXT,

    -- Audit trail
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    file_modified_at TIMESTAMP,
    last_synced_at TIMESTAMP,

    -- Soft delete
    active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP,

    -- Version tracking
    version INT DEFAULT 1,
    checksum VARCHAR(64),

    -- Unique constraint: same file can cover multiple clients
    UNIQUE(filename, client_id)
);

CREATE INDEX IF NOT EXISTS idx_contracts_client_id
    ON contract_checker.contracts(client_id);
CREATE INDEX IF NOT EXISTS idx_contracts_active
    ON contract_checker.contracts(active);
CREATE INDEX IF NOT EXISTS idx_contracts_filename
    ON contract_checker.contracts(filename);

-- Classifications table: store AI classification results
CREATE TABLE IF NOT EXISTS contract_checker.classifications (
    id SERIAL PRIMARY KEY,
    werkbon_id VARCHAR(50) NOT NULL,
    contract_id INTEGER REFERENCES contract_checker.contracts(id),
    timestamp TIMESTAMP DEFAULT NOW(),
    classificatie VARCHAR(20) NOT NULL
        CHECK (classificatie IN ('JA', 'NEE', 'ONZEKER')),
    mapping_score DECIMAL(3,2),
    artikel_referentie TEXT,
    toelichting TEXT,
    werkbon_bedrag DECIMAL(10,2),
    werkelijke_classificatie VARCHAR(20),
    contract_filename VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_classifications_werkbon_id
    ON contract_checker.classifications(werkbon_id);
CREATE INDEX IF NOT EXISTS idx_classifications_contract_id
    ON contract_checker.classifications(contract_id);
CREATE INDEX IF NOT EXISTS idx_classifications_classificatie
    ON contract_checker.classifications(classificatie);
CREATE INDEX IF NOT EXISTS idx_classifications_timestamp
    ON contract_checker.classifications(timestamp);
CREATE INDEX IF NOT EXISTS idx_classifications_contract_filename
    ON contract_checker.classifications(contract_filename);

-- Contract changes audit log: tracks all changes to contract metadata
CREATE TABLE IF NOT EXISTS contract_checker.contract_changes (
    id SERIAL PRIMARY KEY,
    contract_id INTEGER REFERENCES contract_checker.contracts(id),
    filename VARCHAR(255) NOT NULL,
    change_type VARCHAR(20) NOT NULL,  -- INSERT, UPDATE, DEACTIVATE, REACTIVATE
    old_client_id VARCHAR(50),
    new_client_id VARCHAR(50),
    changed_fields TEXT[],             -- Array of changed field names
    changed_at TIMESTAMP DEFAULT NOW(),
    changed_by VARCHAR(100) DEFAULT CURRENT_USER
);

CREATE INDEX IF NOT EXISTS idx_contract_changes_contract_id
    ON contract_checker.contract_changes(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_changes_changed_at
    ON contract_checker.contract_changes(changed_at);

-- ============================================================
-- 6. CREATE VIEW FOR WERKBONNEN
-- ============================================================
-- Adjust this view to match your actual DWH structure.
-- This abstracts the source, making it easy to change later.

-- Example: uncomment and modify to match your DWH
-- CREATE OR REPLACE VIEW contract_checker.v_werkbonnen AS
-- SELECT
--     werkbon_id,
--     datum,
--     klant_naam,
--     adres,
--     omschrijving,
--     uitgevoerde_werkzaamheden,
--     materialen,
--     monteur,
--     bedrag,
--     contract_type
-- FROM dwh.werkbonnen;  -- <-- adjust schema.table

-- ============================================================
-- 7. VERIFY SETUP
-- ============================================================
SELECT 'User' AS type, usename AS name
FROM pg_user WHERE usename = 'contract_checker_user';

SELECT 'Schema' AS type, schema_name AS name
FROM information_schema.schemata
WHERE schema_name = 'contract_checker';

SELECT 'Table' AS type, table_name AS name
FROM information_schema.tables
WHERE table_schema = 'contract_checker';

-- Show all schema permissions
SELECT DISTINCT 'Schema access' AS type, nspname AS name
FROM pg_namespace n
JOIN pg_roles r ON has_schema_privilege(r.oid, n.oid, 'USAGE')
WHERE r.rolname = 'contract_checker_user'
AND nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY name;
