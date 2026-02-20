-- ============================================================
-- VERIFICATION SCRIPT: Compare databases 1190 and 1210
-- Schema: contract_checker
-- ============================================================
-- Run this script to verify that the migration was successful
-- by comparing record counts and data integrity between the two databases.
--
-- Usage:
--   psql -h 10.3.152.9 -U postgres -d 1210 -f verify_migration.sql
-- ============================================================

\echo '============================================================'
\echo 'MIGRATION VERIFICATION REPORT'
\echo '============================================================'

-- Setup foreign connection to 1190
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

DROP SERVER IF EXISTS verify_1190 CASCADE;

CREATE SERVER verify_1190
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host '10.3.152.9', port '5432', dbname '1190');

CREATE USER MAPPING FOR postgres
    SERVER verify_1190
    OPTIONS (user 'postgres', password 'TQwSTtLM9bSaLD');

CREATE SCHEMA IF NOT EXISTS verify_temp;

IMPORT FOREIGN SCHEMA contract_checker
    FROM SERVER verify_1190
    INTO verify_temp;

-- ============================================================
-- 1. RECORD COUNT COMPARISON
-- ============================================================
\echo ''
\echo '1. RECORD COUNT COMPARISON'
\echo '-----------------------------------------------------------'

SELECT
    '1190 (source)' AS database,
    (SELECT COUNT(*) FROM verify_temp.contracts) AS contracts,
    (SELECT COUNT(*) FROM verify_temp.classifications) AS classifications,
    (SELECT COUNT(*) FROM verify_temp.contract_changes) AS contract_changes
UNION ALL
SELECT
    '1210 (target)' AS database,
    (SELECT COUNT(*) FROM contract_checker.contracts) AS contracts,
    (SELECT COUNT(*) FROM contract_checker.classifications) AS classifications,
    (SELECT COUNT(*) FROM contract_checker.contract_changes) AS contract_changes;

-- ============================================================
-- 2. CONTRACTS COMPARISON
-- ============================================================
\echo ''
\echo '2. CONTRACTS COMPARISON'
\echo '-----------------------------------------------------------'

-- Check for missing contracts
\echo 'Missing contracts in 1210 (should be 0):'
SELECT COUNT(*) AS missing_in_target
FROM verify_temp.contracts src
WHERE NOT EXISTS (
    SELECT 1 FROM contract_checker.contracts tgt
    WHERE tgt.id = src.id
);

-- Check for extra contracts
\echo 'Extra contracts in 1210 not in 1190:'
SELECT COUNT(*) AS extra_in_target
FROM contract_checker.contracts tgt
WHERE NOT EXISTS (
    SELECT 1 FROM verify_temp.contracts src
    WHERE src.id = tgt.id
);

-- Sample comparison of contract data
\echo 'Sample contracts comparison (first 5):'
SELECT
    src.id,
    src.filename AS src_filename,
    tgt.filename AS tgt_filename,
    src.client_id AS src_client_id,
    tgt.client_id AS tgt_client_id,
    CASE
        WHEN src.filename = tgt.filename AND src.client_id = tgt.client_id THEN 'OK'
        ELSE 'MISMATCH'
    END AS status
FROM verify_temp.contracts src
FULL OUTER JOIN contract_checker.contracts tgt ON src.id = tgt.id
ORDER BY src.id
LIMIT 5;

-- ============================================================
-- 3. CLASSIFICATIONS COMPARISON
-- ============================================================
\echo ''
\echo '3. CLASSIFICATIONS COMPARISON'
\echo '-----------------------------------------------------------'

-- Check for missing classifications
\echo 'Missing classifications in 1210 (should be 0):'
SELECT COUNT(*) AS missing_in_target
FROM verify_temp.classifications src
WHERE NOT EXISTS (
    SELECT 1 FROM contract_checker.classifications tgt
    WHERE tgt.id = src.id
);

-- Check classification distribution
\echo 'Classification distribution comparison:'
SELECT
    '1190' AS database,
    classificatie,
    COUNT(*) AS count
FROM verify_temp.classifications
GROUP BY classificatie
UNION ALL
SELECT
    '1210' AS database,
    classificatie,
    COUNT(*) AS count
FROM contract_checker.classifications
GROUP BY classificatie
ORDER BY database, classificatie;

-- ============================================================
-- 4. CONTRACT CHANGES COMPARISON
-- ============================================================
\echo ''
\echo '4. CONTRACT CHANGES COMPARISON'
\echo '-----------------------------------------------------------'

-- Check for missing contract changes
\echo 'Missing contract changes in 1210 (should be 0):'
SELECT COUNT(*) AS missing_in_target
FROM verify_temp.contract_changes src
WHERE NOT EXISTS (
    SELECT 1 FROM contract_checker.contract_changes tgt
    WHERE tgt.id = src.id
);

-- Check change type distribution
\echo 'Change type distribution comparison:'
SELECT
    '1190' AS database,
    change_type,
    COUNT(*) AS count
FROM verify_temp.contract_changes
GROUP BY change_type
UNION ALL
SELECT
    '1210' AS database,
    change_type,
    COUNT(*) AS count
FROM contract_checker.contract_changes
GROUP BY change_type
ORDER BY database, change_type;

-- ============================================================
-- 5. DATA INTEGRITY CHECKS
-- ============================================================
\echo ''
\echo '5. DATA INTEGRITY CHECKS IN 1210'
\echo '-----------------------------------------------------------'

-- Check for orphaned contract_changes
\echo 'Orphaned contract_changes (should be 0):'
SELECT COUNT(*) AS orphaned_changes
FROM contract_checker.contract_changes cc
WHERE cc.contract_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM contract_checker.contracts c WHERE c.id = cc.contract_id
);

-- Check for orphaned classifications
\echo 'Orphaned classifications (should be 0):'
SELECT COUNT(*) AS orphaned_classifications
FROM contract_checker.classifications cl
WHERE cl.contract_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM contract_checker.contracts c WHERE c.id = cl.contract_id
);

-- Check active contracts
\echo 'Active vs Inactive contracts in 1210:'
SELECT
    active,
    COUNT(*) AS count
FROM contract_checker.contracts
GROUP BY active;

-- ============================================================
-- 6. SEQUENCE VALUES
-- ============================================================
\echo ''
\echo '6. SEQUENCE VALUES IN 1210'
\echo '-----------------------------------------------------------'

SELECT
    'contracts_id_seq' AS sequence_name,
    last_value AS current_value,
    (SELECT MAX(id) FROM contract_checker.contracts) AS max_table_id
FROM contract_checker.contracts_id_seq
UNION ALL
SELECT
    'classifications_id_seq' AS sequence_name,
    last_value AS current_value,
    (SELECT MAX(id) FROM contract_checker.classifications) AS max_table_id
FROM contract_checker.classifications_id_seq
UNION ALL
SELECT
    'contract_changes_id_seq' AS sequence_name,
    last_value AS current_value,
    (SELECT MAX(id) FROM contract_checker.contract_changes) AS max_table_id
FROM contract_checker.contract_changes_id_seq;

-- ============================================================
-- 7. INDEXES AND CONSTRAINTS
-- ============================================================
\echo ''
\echo '7. INDEXES IN 1210'
\echo '-----------------------------------------------------------'

SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'contract_checker'
ORDER BY tablename, indexname;

-- ============================================================
-- CLEANUP
-- ============================================================
DROP SCHEMA verify_temp CASCADE;
DROP USER MAPPING FOR postgres SERVER verify_1190;
DROP SERVER verify_1190;

\echo ''
\echo '============================================================'
\echo 'VERIFICATION COMPLETE'
\echo '============================================================'
\echo 'Review the results above to ensure migration was successful.'
\echo 'All missing/extra/orphaned counts should be 0.'
\echo 'All record counts should match between 1190 and 1210.'
\echo '============================================================'
