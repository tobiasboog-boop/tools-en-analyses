# Contract Bestanden

Deze map bevat de contractteksten voor de demo versie.

## Bestandsformaat

Plaats hier `.txt` bestanden met contractvoorwaarden. De bestandsnaam moet overeenkomen met de debiteur code of een beschrijvende naam.

Voorbeeld:
- `005102_WVC.txt` - Contract voor debiteur 005102 (WVC)
- `default.txt` - Standaard contract (fallback)

## Export vanuit database

Om contracten te exporteren vanuit de pilot database:

```sql
SELECT
    c.id,
    c.filename,
    c.llm_ready,
    cr.client_id
FROM contract_checker.contracts c
LEFT JOIN contract_checker.contract_relatie cr ON cr.contract_id = c.id
WHERE c.active = true;
```

Kopieer de `llm_ready` tekst naar een .txt bestand.
