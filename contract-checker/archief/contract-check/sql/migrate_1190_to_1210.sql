-- ============================================================
-- MIGRATION: Database 1190 -> Database 1210
-- Schema: contract_checker
-- ============================================================
-- This script migrates the contract_checker schema from database 1190
-- to database 1210 using a dump and restore approach with postgres_fdw.
--
-- Prerequisites:
-- 1. You have admin access to both databases
-- 2. Extension postgres_fdw is available
-- 3. Database 1210 schema is already set up (run setup.sql first)
--
-- Usage:
--   psql -h 10.3.152.9 -U postgres -d 1210 -f migrate_1190_to_1210.sql
-- ============================================================

\echo '============================================================'
\echo 'Starting migration from database 1190 to 1210'
\echo 'Schema: contract_checker'
\echo '============================================================'

-- ============================================================
-- STEP 1: Setup Foreign Data Wrapper to connect to source DB
-- ============================================================
\echo 'Setting up connection to source database 1190...'

-- Enable postgres_fdw extension if not already enabled
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

-- Drop existing server/user mapping if they exist
DROP SERVER IF EXISTS db_1190 CASCADE;

-- Create foreign server pointing to database 1190
CREATE SERVER db_1190
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host '10.3.152.9', port '5432', dbname '1190');

-- Create user mapping (use the actual password for postgres user)
-- IMPORTANT: Change this password to match your actual postgres password
CREATE USER MAPPING FOR postgres
    SERVER db_1190
    OPTIONS (user 'postgres', password 'TQwSTtLM9bSaLD');

-- ============================================================
-- STEP 2: Import foreign schema for reading
-- ============================================================
\echo 'Importing foreign schema from database 1190...'

-- Create a temporary schema to import the foreign tables
CREATE SCHEMA IF NOT EXISTS temp_1190_import;

-- Import the contract_checker schema from database 1190
IMPORT FOREIGN SCHEMA contract_checker
    FROM SERVER db_1190
    INTO temp_1190_import;

-- ============================================================
-- STEP 3: Count records in source database
-- ============================================================
\echo 'Counting records in source database 1190...'

\echo 'Contracts:'
SELECT COUNT(*) AS source_contracts_count FROM temp_1190_import.contracts;

\echo 'Classifications:'
SELECT COUNT(*) AS source_classifications_count FROM temp_1190_import.classifications;

\echo 'Contract Changes:'
SELECT COUNT(*) AS source_contract_changes_count FROM temp_1190_import.contract_changes;

-- ============================================================
-- STEP 4: Check if target schema exists and has tables
-- ============================================================
\echo 'Checking target schema in database 1210...'

SELECT 'Target schema exists' AS status
FROM information_schema.schemata
WHERE schema_name = 'contract_checker';

\echo 'Target tables:'
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'contract_checker'
ORDER BY table_name;

-- ============================================================
-- STEP 5: Backup any existing data in 1210 (if needed)
-- ============================================================
\echo 'Checking for existing data in target database 1210...'

\echo 'Current contracts in 1210:'
SELECT COUNT(*) AS target_contracts_count FROM contract_checker.contracts;

\echo 'Current classifications in 1210:'
SELECT COUNT(*) AS target_classifications_count FROM contract_checker.classifications;

\echo 'Current contract changes in 1210:'
SELECT COUNT(*) AS target_contract_changes_count FROM contract_checker.contract_changes;

-- ============================================================
-- STEP 6: Copy data from 1190 to 1210
-- ============================================================
\echo '============================================================'
\echo 'Starting data migration...'
\echo '============================================================'

-- Start transaction
BEGIN;

-- Copy contracts (parent table first due to foreign keys)
\echo 'Copying contracts...'
INSERT INTO contract_checker.contracts (
    id, filename, client_id, client_name, contract_number,
    start_date, end_date, contract_type, notes, filepath,
    created_at, updated_at, file_modified_at, last_synced_at,
    active, deleted_at, version, checksum
)
SELECT
    id, filename, client_id, client_name, contract_number,
    start_date, end_date, contract_type, notes, filepath,
    created_at, updated_at, file_modified_at, last_synced_at,
    active, deleted_at, version, checksum
FROM temp_1190_import.contracts
ON CONFLICT (filename, client_id) DO NOTHING;

\echo 'Contracts copied!'

-- Copy contract_changes (references contracts via FK)
\echo 'Copying contract changes...'
INSERT INTO contract_checker.contract_changes (
    id, contract_id, filename, change_type,
    old_client_id, new_client_id, changed_fields,
    changed_at, changed_by
)
SELECT
    id, contract_id, filename, change_type,
    old_client_id, new_client_id, changed_fields,
    changed_at, changed_by
FROM temp_1190_import.contract_changes
ON CONFLICT DO NOTHING;

\echo 'Contract changes copied!'

-- Copy classifications
\echo 'Copying classifications...'
INSERT INTO contract_checker.classifications (
    id, werkbon_id, contract_id, timestamp, classificatie,
    mapping_score, artikel_referentie, toelichting,
    werkbon_bedrag, werkelijke_classificatie, created_at
)
SELECT
    id, werkbon_id, contract_id, timestamp, classificatie,
    mapping_score, artikel_referentie, toelichting,
    werkbon_bedrag, werkelijke_classificatie, created_at
FROM temp_1190_import.classifications
ON CONFLICT DO NOTHING;

\echo 'Classifications copied!'

-- Update sequences to match the max IDs
\echo 'Updating sequences...'

SELECT setval('contract_checker.contracts_id_seq',
    (SELECT COALESCE(MAX(id), 1) FROM contract_checker.contracts));

SELECT setval('contract_checker.contract_changes_id_seq',
    (SELECT COALESCE(MAX(id), 1) FROM contract_checker.contract_changes));

SELECT setval('contract_checker.classifications_id_seq',
    (SELECT COALESCE(MAX(id), 1) FROM contract_checker.classifications));

\echo 'Sequences updated!'

-- Commit the transaction
COMMIT;

-- ============================================================
-- STEP 7: Verify migration
-- ============================================================
\echo '============================================================'
\echo 'Verifying migration...'
\echo '============================================================'

\echo 'Source counts (1190):'
SELECT
    (SELECT COUNT(*) FROM temp_1190_import.contracts) AS source_contracts,
    (SELECT COUNT(*) FROM temp_1190_import.classifications) AS source_classifications,
    (SELECT COUNT(*) FROM temp_1190_import.contract_changes) AS source_contract_changes;

\echo 'Target counts (1210):'
SELECT
    (SELECT COUNT(*) FROM contract_checker.contracts) AS target_contracts,
    (SELECT COUNT(*) FROM contract_checker.classifications) AS target_classifications,
    (SELECT COUNT(*) FROM contract_checker.contract_changes) AS target_contract_changes;

-- Check for data integrity
\echo 'Checking data integrity...'

-- Verify no orphaned contract_changes
SELECT COUNT(*) AS orphaned_contract_changes
FROM contract_checker.contract_changes cc
WHERE NOT EXISTS (
    SELECT 1 FROM contract_checker.contracts c WHERE c.id = cc.contract_id
);

-- ============================================================
-- STEP 8: Cleanup
-- ============================================================
\echo 'Cleaning up temporary objects...'

DROP SCHEMA temp_1190_import CASCADE;
DROP USER MAPPING FOR postgres SERVER db_1190;
DROP SERVER db_1190;

\echo '============================================================'
\echo 'Migration completed successfully!'
\echo '============================================================'
\echo ''
\echo 'Next steps:'
\echo '1. Verify the migrated data in database 1210'
\echo '2. Test your application against database 1210'
\echo '3. Once verified, you can drop the schema from database 1190'
\echo ''
\echo 'To drop the old schema from 1190 (CAREFUL!):'
\echo '  psql -h 10.3.152.9 -U postgres -d 1190 -c "DROP SCHEMA contract_checker CASCADE;"'
\echo '============================================================'
