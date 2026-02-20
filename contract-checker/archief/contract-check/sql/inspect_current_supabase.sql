-- SQL queries to inspect current Supabase database structure
-- Run these in Supabase SQL Editor and share the output

-- =============================================================================
-- 1. List all tables in public schema
-- =============================================================================
SELECT
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- =============================================================================
-- 2. Get detailed column information for all tables
-- =============================================================================
SELECT
    table_name,
    column_name,
    data_type,
    character_maximum_length,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

-- =============================================================================
-- 3. List all foreign key relationships
-- =============================================================================
SELECT
    tc.table_name AS source_table,
    kcu.column_name AS source_column,
    ccu.table_name AS target_table,
    ccu.column_name AS target_column,
    tc.constraint_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;

-- =============================================================================
-- 4. List all indexes
-- =============================================================================
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- =============================================================================
-- 5. Check if RLS (Row Level Security) is enabled
-- =============================================================================
SELECT
    schemaname,
    tablename,
    rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- =============================================================================
-- 6. List all RLS policies (if any)
-- =============================================================================
SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- =============================================================================
-- 7. Get table row counts
-- =============================================================================
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup AS row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;

-- =============================================================================
-- 8. Check for existing LLM-related tables (if any)
-- =============================================================================
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
    AND (
        table_name LIKE '%llm%'
        OR table_name LIKE '%ai%'
        OR table_name LIKE '%model%'
        OR table_name LIKE '%config%'
        OR table_name LIKE '%usage%'
    )
ORDER BY table_name;
