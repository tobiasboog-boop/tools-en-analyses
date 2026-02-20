-- Add missing contract_filename column to classifications table
-- This column was added to the model but not in the original setup.sql

ALTER TABLE contract_checker.classifications
ADD COLUMN IF NOT EXISTS contract_filename VARCHAR(255);

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_classifications_contract_filename
ON contract_checker.classifications(contract_filename);

-- Verify the column was added
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'contract_checker'
  AND table_name = 'classifications'
ORDER BY ordinal_position;
