-- Migration: Add kostenregel-level classification support
-- Date: 2026-01-28
--
-- This migration:
-- 1. Adds missing columns to classifications table (contract_referentie, hoofdwerkbon_key, modus)
-- 2. Updates CHECK constraint to allow 'GEDEELTELIJK' classification
-- 3. Creates new classification_kostenregels table for per-line classifications

-- ============================================================
-- 1. ADD MISSING COLUMNS TO CLASSIFICATIONS TABLE
-- ============================================================

-- Add contract_referentie column (replaces artikel_referentie conceptually)
ALTER TABLE contract_checker.classifications
ADD COLUMN IF NOT EXISTS contract_referentie TEXT;

-- Add hoofdwerkbon_key for linking to datawarehouse
ALTER TABLE contract_checker.classifications
ADD COLUMN IF NOT EXISTS hoofdwerkbon_key INTEGER;

CREATE INDEX IF NOT EXISTS idx_classifications_hoofdwerkbon_key
ON contract_checker.classifications(hoofdwerkbon_key);

-- Add modus column (validatie or classificatie)
ALTER TABLE contract_checker.classifications
ADD COLUMN IF NOT EXISTS modus VARCHAR(20) DEFAULT 'classificatie';

CREATE INDEX IF NOT EXISTS idx_classifications_modus
ON contract_checker.classifications(modus);

-- ============================================================
-- 2. UPDATE CHECK CONSTRAINT FOR GEDEELTELIJK
-- ============================================================

-- Drop existing constraint
ALTER TABLE contract_checker.classifications
DROP CONSTRAINT IF EXISTS valid_classificatie;

-- Add new constraint with GEDEELTELIJK
ALTER TABLE contract_checker.classifications
ADD CONSTRAINT valid_classificatie
CHECK (classificatie IN ('JA', 'NEE', 'ONZEKER', 'GEDEELTELIJK'));

-- Add modus constraint
ALTER TABLE contract_checker.classifications
DROP CONSTRAINT IF EXISTS valid_modus;

ALTER TABLE contract_checker.classifications
ADD CONSTRAINT valid_modus
CHECK (modus IN ('validatie', 'classificatie'));

-- ============================================================
-- 3. CREATE CLASSIFICATION_KOSTENREGELS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS contract_checker.classification_kostenregels (
    id SERIAL PRIMARY KEY,

    -- Link to parent classification
    classification_id INTEGER NOT NULL
        REFERENCES contract_checker.classifications(id) ON DELETE CASCADE,

    -- Reference to source data (for traceability)
    kostenregel_key INTEGER,              -- Key from financieel.Kosten
    werkbonparagraaf_key INTEGER,         -- Parent paragraaf

    -- Kostenregel details (snapshot at classification time)
    omschrijving TEXT,
    aantal DECIMAL(10,2),
    verrekenprijs DECIMAL(10,2),
    bedrag DECIMAL(10,2),                 -- aantal * verrekenprijs
    categorie VARCHAR(50),                -- Arbeid, Materiaal, Overig, Materieel
    kostenbron VARCHAR(100),              -- Inkoop, Urenstaat, Materiaaluitgifte

    -- Classification result
    classificatie VARCHAR(20) NOT NULL
        CHECK (classificatie IN ('JA', 'NEE', 'ONZEKER')),
    reden TEXT,                           -- Explanation for this specific line

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_classification_kostenregels_classification_id
ON contract_checker.classification_kostenregels(classification_id);

CREATE INDEX IF NOT EXISTS idx_classification_kostenregels_kostenregel_key
ON contract_checker.classification_kostenregels(kostenregel_key);

CREATE INDEX IF NOT EXISTS idx_classification_kostenregels_classificatie
ON contract_checker.classification_kostenregels(classificatie);

-- ============================================================
-- 4. GRANT PERMISSIONS
-- ============================================================

GRANT ALL PRIVILEGES ON contract_checker.classification_kostenregels
TO contract_checker_user;

GRANT USAGE, SELECT ON SEQUENCE contract_checker.classification_kostenregels_id_seq
TO contract_checker_user;

-- ============================================================
-- 5. VERIFY MIGRATION
-- ============================================================

-- Show classifications table structure
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_schema = 'contract_checker'
  AND table_name = 'classifications'
ORDER BY ordinal_position;

-- Show new kostenregels table structure
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_schema = 'contract_checker'
  AND table_name = 'classification_kostenregels'
ORDER BY ordinal_position;

-- Show all tables
SELECT table_name,
       (SELECT COUNT(*) FROM information_schema.columns c
        WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'contract_checker'
ORDER BY table_name;
