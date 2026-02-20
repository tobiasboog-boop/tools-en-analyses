# WVC Contract Check - Pilot

Automatische classificatie van werkbonnen voor Werkendamse Verwarming Centrale (WVC).

## Project Doel

Proof of Concept (POC) om te valideren of AI-gestuurde classificatie van werkbonnen haalbaar en betrouwbaar is. Het systeem bepaalt automatisch of een werkbon binnen of buiten een servicecontract valt.

**Dit is Fase 1: Pilot op historische data - geen operationele tool.**

## Classificatie Logica

Elke werkbon wordt geclassificeerd als:
- **JA**: Volledig binnen contract (mapping score >= 0.85)
- **NEE**: Volledig buiten contract (mapping score >= 0.85)
- **ONZEKER**: Twijfelgeval, handmatige review nodig (score < 0.85)

## Technische Opzet

```
contract-checker/
├── run_pilot.py              # CLI entry point
├── sync_contracts.py         # Sync contracts metadata from CSV
├── sql/setup.sql             # Database schema
├── templates/                # CSV templates
│   └── contracts_template.csv
├── .env.example              # Config template
├── requirements.txt
└── src/
    ├── config/               # Environment config
    ├── models/               # SQLAlchemy models
    └── services/
        ├── contract_loader.py    # Load .docx/.xlsx
        ├── classifier.py         # Claude API integration
        └── werkbon_service.py    # Datawarehouse queries
```

### Stack
- **CLI**: Python script (geen web interface)
- **Database**: Postgres (schema: `contract_checker`)
- **AI Model**: Claude Sonnet 4 via Anthropic API
- **Contracten**: Word (.docx) en Excel (.xlsx) bestanden

### Geen RAG/Vector Database
Contracten worden direct ingelezen en volledig meegestuurd naar Claude. Geen embeddings, geen vector search - bewust eenvoudig gehouden voor de pilot.

## Setup

### Prerequisites
- Python 3.9+
- Access to WVC Postgres datawarehouse
- Anthropic API key
- Contracts folder (OneDrive sync of lokaal)

### Installation

```bash
# Clone repository
git clone <repo-url>
cd contract-checker

# Create virtual environment
python -m venv venv
source venv/bin/activate  # of: venv\Scripts\activate (Windows)

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Database Setup

```bash
# Run SQL setup script on your database
psql -h <host> -U <user> -d <database> -f sql/setup.sql
```

### Configuration (.env)

```
# Database
DB_HOST=your-datawarehouse-host
DB_PORT=5432
DB_NAME=your-database-name
DB_USER=your-username
DB_PASSWORD=your-password
DB_SCHEMA=contract_checker

# Anthropic API
ANTHROPIC_API_KEY=your-api-key

# Contracts folder
CONTRACTS_FOLDER=C:/path/to/contracts

# Classification
CONFIDENCE_THRESHOLD=0.85
```

## Usage

### From CSV file

```bash
python run_pilot.py --input werkbonnen.csv --output results.csv
```

### From datawarehouse

```bash
python run_pilot.py --start-date 2024-01-01 --end-date 2024-03-31
```

### Options

```
--input, -i      Input CSV file with werkbonnen
--start-date     Start date for DB query (YYYY-MM-DD)
--end-date       End date for DB query (YYYY-MM-DD)
--output, -o     Output CSV file for results
--limit          Max werkbonnen to process (default: 100)
--no-db          Do not save results to database
```

### Sync Contracts Metadata

Before running classification, sync the contracts metadata table from a CSV file.
The **filename** is the unique key - it must match the exact SharePoint/OneDrive filename.

```bash
# Dry run (show what would change without committing)
python sync_contracts.py templates/contracts_template.csv --dry-run

# Actual sync
python sync_contracts.py contracts.csv
```

The sync script:
- **Inserts** new contracts (filename not in DB)
- **Updates** existing contracts (filename already in DB)
- **Soft-deletes** removed contracts (filename in DB but not in CSV)
- **Reactivates** previously deleted contracts (if they reappear in CSV)

See [templates/contracts_template.csv](templates/contracts_template.csv) for the expected format.

### Example Output

```
Loading contracts from C:/path/to/contracts...
Loaded 3 contract(s):
  - Servicecontract_2024.docx (12450 chars)
  - Prijslijst.xlsx (3200 chars)
  - Voorwaarden.docx (8900 chars)

Loading werkbonnen from werkbonnen.csv...
Processing 50 werkbonnen...

[  1/50] WB-2024-001... JA      (0.92)
[  2/50] WB-2024-002... NEE     (0.88)
[  3/50] WB-2024-003... ONZEKER (0.72)
...

==================================================
CLASSIFICATION SUMMARY
==================================================
Total werkbonnen:    50
JA (in contract):    28 ( 56.0%)
NEE (factureren):    15 ( 30.0%)
ONZEKER (review):     7 ( 14.0%)
Avg mapping score:   0.84
==================================================
```

## Database Schema

```sql
-- Schema with dedicated user (read on all schemas, write on contract_checker)
CREATE SCHEMA contract_checker;
CREATE USER contract_checker_user WITH PASSWORD '...';

-- Classifications table
CREATE TABLE contract_checker.classifications (
    id SERIAL PRIMARY KEY,
    werkbon_id VARCHAR(50) NOT NULL,
    classificatie VARCHAR(20) NOT NULL CHECK (classificatie IN ('JA', 'NEE', 'ONZEKER')),
    mapping_score DECIMAL(3,2),
    artikel_referentie TEXT,
    toelichting TEXT,
    werkbon_bedrag DECIMAL(10,2),
    werkelijke_classificatie VARCHAR(20),  -- for validation
    created_at TIMESTAMP DEFAULT NOW()
);

-- View for werkbonnen (template - adjust to your DWH)
CREATE VIEW contract_checker.v_werkbonnen AS
SELECT ... FROM dwh.werkbonnen;
```

See [sql/setup.sql](sql/setup.sql) for the complete setup script.

## CSV Formats

### Contracts CSV (voor sync)

De contracts CSV koppelt contractbestanden aan klanten. Kolommen (`;` gescheiden):

| Kolom | Verplicht | Beschrijving |
|-------|-----------|--------------|
| filename | Ja | Exacte bestandsnaam in SharePoint/OneDrive |
| client_id | Ja | Syntess klant ID (moet matchen met werkbon) |
| client_name | Nee | Klantnaam |
| contract_number | Nee | Contractnummer |
| start_date | Nee | Startdatum (YYYY-MM-DD) |
| end_date | Nee | Einddatum (YYYY-MM-DD) |
| contract_type | Nee | Type (Standaard, Premium, Basis) |
| notes | Nee | Opmerkingen |

### Werkbon CSV (voor classificatie)

Input CSV moet minimaal deze kolommen bevatten:

| Kolom | Beschrijving |
|-------|--------------|
| werkbon_id | Unieke identifier |
| omschrijving | Beschrijving werkzaamheden |
| uitgevoerde_werkzaamheden | Details van het werk |
| materialen | Gebruikte materialen |
| bedrag | Factuurbedrag |

## Deliverables (Einde Pilot)

1. Eindrapport met confusion matrix en kwaliteitsmetrics
2. Volledig classificatie-logbestand (CSV + database)
3. Analyse van false positives/negatives
4. Go/no-go advies voor Fase 2 (operationaliseren)

## Success Metrics

- **False Negative Rate**: < 5% (gemiste facturatie)
- **False Positive Rate**: < 3% (onjuiste contract coverage)
- **ONZEKER percentage**: 15-25% (handmatige review)

## Team

- **Notifica**: Technische implementatie, data pipeline, AI integratie
- **WVC**: Contracten, domeinkennis, validatie

## Roadmap

Mogelijke uitbreidingen na succesvolle pilot:

### Fase 2: Operationaliseren
- [ ] REST API layer voor integratie met andere systemen
- [ ] Web interface voor handmatige review van ONZEKER cases
- [ ] Scheduled batch processing (cron/Airflow)
- [ ] Alerting bij hoge ONZEKER percentages

### Data & Storage
- [ ] Contracts opslaan in database (i.p.v. direct van disk lezen)
- [ ] Contract versioning en history tracking
- [ ] Pre-processing: contracts converteren naar plain text
- [ ] Caching van contract content voor snellere verwerking

### AI & Models
- [ ] Lokale LLM ondersteuning (Mistral via Ollama)
- [ ] Model vergelijking: Claude vs Mistral vs GPT-4
- [ ] Fine-tuning op WVC-specifieke contracttaal
- [ ] RAG/vector search voor grote contracten
- [ ] Confidence calibration op basis van validatie data

### Analyse & Reporting
- [ ] Dashboard met realtime metrics
- [ ] Automatische confusion matrix generatie
- [ ] Trend analyse over tijd
- [ ] Export naar Excel met formatting

### Integraties
- [ ] Koppeling met facturatiesysteem
- [ ] Webhook notificaties
- [ ] SSO/LDAP authenticatie

## License

Internal project - Notifica B.V.
