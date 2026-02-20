# GA4 → BigQuery Export Setup

## Stap 1: BigQuery Koppeling Activeren (in GA4)

### In GA4 Interface:
1. **Admin** → **Property** → **BigQuery Links**
2. Klik **Link** → Kies Google Cloud Project
3. Selecteer:
   - ✅ **Daily export** (dagelijkse volledige export)
   - ✅ **Streaming export** (real-time, optioneel, betaald)
   - ✅ **Include advertising identifiers** (voor remarketing)

### Dataset Naam:
- Standaard: `analytics_<property_id>`
- Bijvoorbeeld: `analytics_273791186`

### Eerste Data:
- **Wachttijd**: ~24-48 uur voor eerste export
- **Historische data**: BigQuery exporteert GEEN oude data, alleen vanaf activatie
- **Oplossing voor oude data**: Zie "Historische Data Ophalen" hieronder

---

## Stap 2: Google Cloud Setup

### A) Maak Service Account:
1. **Google Cloud Console** → **IAM & Admin** → **Service Accounts**
2. **Create Service Account**
   - Naam: `notifica-analytics-reader`
   - Role: **BigQuery Data Viewer** + **BigQuery Job User**
3. **Keys** → **Add Key** → **JSON** → Download

### B) Plaats JSON Key:
```bash
# Bewaar op veilige locatie
C:\projects\tools_en_analyses\funnel_automation\ga4-bigquery-key.json
```

### C) Update .env:
```bash
GA4_BIGQUERY_PROJECT_ID=your-project-id
GA4_BIGQUERY_DATASET=analytics_273791186
GA4_BIGQUERY_CREDENTIALS=C:\projects\tools_en_analyses\funnel_automation\ga4-bigquery-key.json
```

---

## Stap 3: Historische Data Ophalen (Oude Property)

### Optie A: GA4 Data API (12-14 maanden max)
```python
# Via Google Analytics Data API
# Haalt aggregated data op, geen raw events
# Gratis, geen BigQuery nodig
```

### Optie B: Manual Export via UI
1. GA4 → **Explore** → Custom Report
2. Selecteer metrics: sessions, page_views, events
3. Export als CSV
4. Importeer in BigQuery (via Python script)

### Optie C: Toegang vragen tot oude property
- Probeer alsnog eigenaar te achterhalen
- BigQuery link activeren op oude property
- Export draaien voordat je overstapt

---

## Stap 4: Kosten (Belangrijk!)

### BigQuery Prijzen:
- **Opslag**: $0.02 per GB/maand
- **Query**: $6.25 per TB gescanned
- **Streaming**: $0.012 per 200MB

### Geschatte kosten Notifica:
- **Daily export**: ~50MB/dag = 1.5GB/maand
- **Opslag**: $0.03/maand
- **Queries**: ~$0.10/maand (bij 100 queries)

**Totaal: ~$1-2/maand** (vrijwel gratis)

### Gratis Tier:
- **10 GB opslag** gratis
- **1 TB query** gratis per maand

→ **Je blijft binnen gratis tier!**

---

## Stap 5: Nuttige BigQuery Queries

### Query 1: Top Pages (laatste 30 dagen)
```sql
SELECT
  event_date,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') AS page_url,
  COUNT(*) as page_views,
  COUNT(DISTINCT user_pseudo_id) as unique_users
FROM
  `your-project.analytics_273791186.events_*`
WHERE
  _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
    AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())
  AND event_name = 'page_view'
GROUP BY
  event_date, page_url
ORDER BY
  page_views DESC
LIMIT 20
```

### Query 2: User Sessions met Email (lead tracking)
```sql
SELECT
  user_pseudo_id,
  (SELECT value.string_value FROM UNNEST(user_properties) WHERE key = 'email') AS email,
  COUNT(DISTINCT CONCAT(user_pseudo_id,
    CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING))) as sessions,
  COUNT(*) as events,
  MAX(event_timestamp) as last_activity
FROM
  `your-project.analytics_273791186.events_*`
WHERE
  _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY))
    AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())
GROUP BY
  user_pseudo_id, email
HAVING
  email IS NOT NULL
ORDER BY
  sessions DESC
```

### Query 3: High-Intent Pages (prijzen, contact, demo)
```sql
SELECT
  user_pseudo_id,
  (SELECT value.string_value FROM UNNEST(user_properties) WHERE key = 'email') AS email,
  COUNTIF(event_name = 'page_view' AND
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location')
    LIKE '%prijzen%') as pricing_views,
  COUNTIF(event_name = 'page_view' AND
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location')
    LIKE '%contact%') as contact_views,
  COUNTIF(event_name = 'page_view' AND
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location')
    LIKE '%demo%') as demo_views,
  COUNT(*) as total_events
FROM
  `your-project.analytics_273791186.events_*`
WHERE
  _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
    AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())
GROUP BY
  user_pseudo_id, email
HAVING
  email IS NOT NULL
  AND (pricing_views > 0 OR contact_views > 0 OR demo_views > 0)
ORDER BY
  (pricing_views * 3 + contact_views * 5 + demo_views * 10) DESC
```

---

## Volgende Stappen

1. ✅ **Nu**: Maak nieuwe GA4 property aan
2. ⏳ **Direct daarna**: Activeer BigQuery export (wacht 24u)
3. 📊 **Over 2 dagen**: Test queries, verifieer data
4. 🔗 **Over 1 week**: Integreer in lead scoring script
5. 📈 **Over 2 weken**: Historische data importeren (manual export oude property)

---

## Lead Scoring met GA4 Data

Straks kunnen we toevoegen aan scoring:
- **High-intent pages** (prijzen, contact): +10 punten
- **Recent bezoek** (< 7 dagen): +15 punten
- **Meerdere sessies**: +5 punten per sessie
- **Lange sessies** (> 5 min): +10 punten
- **Returning visitors**: +8 punten

**Totaal website score: 0-40 punten**

Nieuwe totaal: **CRM (0-70) + Email (0-30) + Website (0-40) = 140 punten**
(schalen naar 0-100)
