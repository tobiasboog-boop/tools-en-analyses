-- Add contract_files table for storing contract file binaries
-- Migration Date: 2026-01-30
-- Purpose: Separate contract source files from contract metadata
--          One file can contain multiple contracts (per client)

-- ============================================================
-- 1. CREATE CONTRACT_FILES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS contract_checker.contract_files (
    id SERIAL PRIMARY KEY,

    -- File identification
    filename VARCHAR(255) NOT NULL UNIQUE,

    -- File storage
    file_content BYTEA NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    checksum VARCHAR(64) NOT NULL,

    -- Extracted data
    extracted_text TEXT,

    -- Metadata
    uploaded_at TIMESTAMP DEFAULT NOW(),
    uploaded_by VARCHAR(100) DEFAULT CURRENT_USER,
    last_processed_at TIMESTAMP,

    -- Soft delete
    active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- 2. CREATE INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_contract_files_filename
    ON contract_checker.contract_files(filename);

CREATE INDEX IF NOT EXISTS idx_contract_files_checksum
    ON contract_checker.contract_files(checksum);

CREATE INDEX IF NOT EXISTS idx_contract_files_active
    ON contract_checker.contract_files(active);

CREATE INDEX IF NOT EXISTS idx_contract_files_uploaded_at
    ON contract_checker.contract_files(uploaded_at DESC);

-- ============================================================
-- 3. ADD COMMENTS
-- ============================================================
COMMENT ON TABLE contract_checker.contract_files IS
    'Stores binary content of contract source files. One file can contain multiple contracts for different clients.';

COMMENT ON COLUMN contract_checker.contract_files.file_content IS
    'Binary content of the original contract file (PDF/DOCX/XLSX)';

COMMENT ON COLUMN contract_checker.contract_files.file_size IS
    'File size in bytes';

COMMENT ON COLUMN contract_checker.contract_files.mime_type IS
    'MIME type of the file (application/pdf, application/vnd.openxmlformats-officedocument.*, etc.)';

COMMENT ON COLUMN contract_checker.contract_files.checksum IS
    'SHA256 checksum for duplicate detection and integrity verification';

COMMENT ON COLUMN contract_checker.contract_files.extracted_text IS
    'Plain text extracted from the document for analysis and search';

-- ============================================================
-- 4. ADD FOREIGN KEY TO CONTRACTS TABLE
-- ============================================================
ALTER TABLE contract_checker.contracts
    ADD COLUMN IF NOT EXISTS file_id INTEGER
    REFERENCES contract_checker.contract_files(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_contracts_file_id
    ON contract_checker.contracts(file_id);

COMMENT ON COLUMN contract_checker.contracts.file_id IS
    'Foreign key to contract_files table - links contract metadata to source file';

-- ============================================================
-- 5. VERIFY MIGRATION
-- ============================================================
SELECT
    'contract_files table' AS verification,
    COUNT(*) AS record_count
FROM contract_checker.contract_files;

SELECT
    'contracts.file_id column' AS verification,
    COUNT(*) FILTER (WHERE file_id IS NOT NULL) AS with_file_id,
    COUNT(*) AS total_contracts
FROM contract_checker.contracts;

-- Show table structure
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'contract_checker'
  AND table_name = 'contract_files'
ORDER BY ordinal_position;
