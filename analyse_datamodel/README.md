# DWH Analyse Tools

Analyse tools voor het Syntess datawarehouse (alle klanten) en C-Track DWH.

## Databases

### Syntess DWH (alle klanten)
- **Host**: `10.3.152.9` (intern netwerk)
- **User**: `postgres` (superuser - alle databases)
- **Database**: klantnummer (bijv. `1264` = WETEC)
- **Schema's per klant**: `notifica` (SSM bron), `uren`, `werkbonnen`, `stam`, `prepare` (Power BI), etc.

### C-Track DWH (Wassink 1225)
- **Host**: `10.3.152.9`
- **Database**: `DATAWAREHOUSE`
- **User**: `ctrack_kijker` (read-only)
- **Schema's**: `stg`, `grip`

## Bekende klanten

| Klantnummer | Naam |
|-------------|------|
| 1264 | WETEC |
| 1225 | Wassink |
| 1241 | Liquiditeit Demo |
| 1256 | Van den Buijs |

## Setup

```bash
pip install psycopg2-binary python-dotenv
python test_connection.py
```

## Gebruik

```python
from db_connection import syntess_connection, syntess_query

# Query uitvoeren op WETEC DWH
rows = syntess_query(1264, """
    SELECT "MedewerkerKey", "Aantal", "TaakKey"
    FROM uren."Geboekte Uren"
    WHERE "WerkbonKey" = %s
""", (681566,))

# Of directe connectie
conn = syntess_connection(1264)
cur = conn.cursor()
cur.execute("SELECT * FROM stam.\"Medewerkers\" LIMIT 5")
```

## Schema structuur Syntess DWH

| Schema | Inhoud |
|--------|--------|
| `notifica` | SSM brontabellen (ruwe Syntess export) |
| `stam` | Stamdata (medewerkers, relaties, taken, etc.) |
| `uren` | Geboekte uren, taken, tarieven |
| `werkbonnen` | Werkbonnen, paraggrafen, kosten |
| `prepare` | Getransformeerde data (voeding Power BI) |
| `financieel` | Financiele data |
| `projecten` | Projectdata |

## Notities

- Alleen bereikbaar vanaf intern Notifica netwerk
- Nachtelijke full load vanuit Syntess
- `notifica.SSM *` tabellen = ruwe Syntess export
- `prepare.*` tabellen = getransformeerd voor Power BI
