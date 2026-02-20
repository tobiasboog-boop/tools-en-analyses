# Top-10 Checks & Balances — Dagelijkse DWH Data-integriteit

**Datum:** 20-02-2026
**Doel:** Dagelijks automatisch de data-integriteit valideren per klant-database, zodat afwijkingen proactief worden gesignaleerd voordat klanten ze melden.

---

## Architectuur-context

```
Syntess (Firebird)
    ↓  nachtelijke full load (GRIP ETL ~00:27)
prepare.stage1_*          ← 23 brontabellen (9 kostenbronnen + dimensies)
    ↓  GRIP prepare fase 2-5
prepare.factkosten        ← centraal: UNION van stage1 kostenbronnen (782K regels WETEC)
    ↓  views
uren."Geboekte Uren"      ← factkosten WHERE taak_gc_id IS NOT NULL
werkbonnen."Werkbon kosten" ← factkosten WHERE werkbon_gc_id IS NOT NULL
    ↓  GRIP endview fase 1-3
notifica."SSM *"          ← 103 SSM views (Power BI thin reports)
```

**Kritiek inzicht:** `factkosten` is de single source of truth. Alle downstream data is een gefilterde/geaggregeerde weergave. Problemen ontstaan als:
- De Firebird-export incomplete data levert (SSM ≠ Syntess app)
- De GRIP ETL faalt of niet draait
- De JOIN-logica in views wezen kwijtraakt door NULL keys

---

## Check 1: ETL Completion — Heeft de nachtelijke load gedraaid?

**Prioriteit:** KRITIEK
**Frequentie:** Dagelijks, 's ochtends vroeg (na verwachte ETL ~00:27-00:40)

```sql
-- Check: is er vandaag een succesvolle ETL-run geweest?
SELECT
    MAX(start_dt) as laatste_run,
    COUNT(*) as stappen_vandaag,
    COUNT(*) FILTER (WHERE error_msg != 'Success' AND error_msg != 'running ..') as fouten
FROM grip.grip_aud
WHERE start_dt::date = CURRENT_DATE;
```

**Alert als:**
- `laatste_run IS NULL` → ETL heeft vandaag niet gedraaid
- `fouten > 0` → ETL heeft fouten gehad

**Drempel:** Geen tolerantie. ETL moet elke dag draaien.

---

## Check 2: ETL Errors — Zijn er fouten in de GRIP log?

**Prioriteit:** KRITIEK
**Frequentie:** Dagelijks

```sql
-- Alle GRIP fouten van de laatste 7 dagen
SELECT
    start_dt,
    source,
    target,
    error_msg,
    flow
FROM grip.grip_log
WHERE error_msg IS NOT NULL
  AND error_msg NOT IN ('Success', 'running ..')
  AND start_dt > CURRENT_DATE - INTERVAL '7 days'
ORDER BY start_dt DESC;
```

**Alert als:** Resultaat > 0 rijen.

---

## Check 3: Table Freshness — Zijn de prepare-tabellen actueel?

**Prioriteit:** HOOG
**Frequentie:** Dagelijks

```sql
-- Wanneer zijn de kritieke prepare-tabellen voor het laatst ververst?
SELECT
    relname as tabel,
    n_live_tup as rijen,
    last_autoanalyze as laatste_analyze,
    EXTRACT(EPOCH FROM (NOW() - last_autoanalyze)) / 3600 as uren_oud
FROM pg_stat_user_tables
WHERE schemaname = 'prepare'
  AND relname IN (
      'factkosten',
      'stage1_arbeidkosten',
      'stage1_inkoopkosten',
      'stage1_magazijnuitgiftekosten',
      'stage1_vrijekosten',
      'stage1_afschrijvingkosten'
  )
ORDER BY last_autoanalyze ASC NULLS FIRST;
```

**Alert als:**
- `uren_oud > 30` → Tabel is meer dan 30 uur oud (gemiste nachtload)
- `last_autoanalyze IS NULL` → Tabel is nooit geanalyseerd

---

## Check 4: factkosten Row Count Trend — Plotselinge afwijkingen?

**Prioriteit:** HOOG
**Frequentie:** Dagelijks

```sql
-- Vergelijk vandaag's factkosten count met de grip_aud historische inserts
-- voor factkosten over de afgelopen 14 dagen
SELECT
    start_dt::date as datum,
    ins as rijen_geladen,
    LAG(ins) OVER (ORDER BY start_dt) as vorige_dag,
    CASE
        WHEN LAG(ins) OVER (ORDER BY start_dt) > 0
        THEN ROUND(((ins - LAG(ins) OVER (ORDER BY start_dt))::numeric
             / LAG(ins) OVER (ORDER BY start_dt) * 100), 1)
        ELSE NULL
    END as pct_verschil
FROM grip.grip_aud
WHERE LOWER(target) = 'factkosten'
  AND start_dt > CURRENT_DATE - INTERVAL '14 days'
ORDER BY start_dt DESC;
```

**Alert als:** `ABS(pct_verschil) > 10` → Meer dan 10% afwijking in factkosten volume dag-op-dag.

**Context:** Een plotselinge daling kan duiden op een gefaalde Firebird-export. Een plotselinge stijging kan duiden op dubbele data.

---

## Check 5: Stage1 → factkosten Reconciliation — Tellen de bronnen op?

**Prioriteit:** HOOG
**Frequentie:** Dagelijks

```sql
-- De 6 actieve kostenbronnen moeten optellen tot factkosten
WITH bronnen AS (
    SELECT 'arbeidkosten' as bron, COUNT(*) as rijen FROM prepare.stage1_arbeidkosten
    UNION ALL
    SELECT 'inkoopkosten', COUNT(*) FROM prepare.stage1_inkoopkosten
    UNION ALL
    SELECT 'magazijnuitgiftekosten', COUNT(*) FROM prepare.stage1_magazijnuitgiftekosten
    UNION ALL
    SELECT 'vrijekosten', COUNT(*) FROM prepare.stage1_vrijekosten
    UNION ALL
    SELECT 'afschrijvingkosten', COUNT(*) FROM prepare.stage1_afschrijvingkosten
    UNION ALL
    SELECT 'bankafschriftkosten', COUNT(*) FROM prepare.stage1_bankafschriftkosten
),
totaal_bronnen AS (
    SELECT SUM(rijen) as som_bronnen FROM bronnen
),
totaal_fk AS (
    SELECT COUNT(*) as factkosten_rijen FROM prepare.factkosten
)
SELECT
    tb.som_bronnen,
    tf.factkosten_rijen,
    tf.factkosten_rijen - tb.som_bronnen as verschil
FROM totaal_bronnen tb, totaal_fk tf;
```

**Alert als:** `verschil != 0` → factkosten bevat meer of minder rijen dan de som van de stage1 bronnen.

**Let op:** factkosten kan meer rijen bevatten als er extra bronnen actief zijn (intercompany, materieel, etc.). Stel de verwachte bronnen per klant in.

---

## Check 6: Debit/Credit — Geboekte uren vs Werkbonkosten

**Prioriteit:** KRITIEK (dit is het issue dat Arthur meldde)
**Frequentie:** Dagelijks

```sql
-- Vergelijk totaal uren vanuit twee perspectieven op factkosten
WITH uren_per_taak AS (
    -- Uren met taak-koppeling (= "Geboekte Uren" view)
    SELECT
        medew_gc_id,
        DATE_TRUNC('month', uitvoeringsdatum)::date as maand,
        SUM(aantal) as uren
    FROM prepare.factkosten
    WHERE taak_gc_id IS NOT NULL
    GROUP BY medew_gc_id, DATE_TRUNC('month', uitvoeringsdatum)::date
),
uren_per_werkbon AS (
    -- Uren op werkbonnen (= "Werkbon kosten" view, alleen arbeid)
    SELECT
        medew_gc_id,
        DATE_TRUNC('month', boekdatum)::date as maand,
        SUM(aantal) as uren
    FROM prepare.factkosten
    WHERE werkbon_gc_id IS NOT NULL
      AND taak_gc_id IS NOT NULL  -- alleen arbeidsregels
    GROUP BY medew_gc_id, DATE_TRUNC('month', boekdatum)::date
)
SELECT
    t.maand,
    COUNT(DISTINCT t.medew_gc_id) as medewerkers,
    SUM(t.uren) as geboekte_uren,
    COALESCE(SUM(w.uren), 0) as wb_uren,
    SUM(t.uren) - COALESCE(SUM(w.uren), 0) as verschil,
    ROUND(((SUM(t.uren) - COALESCE(SUM(w.uren), 0)) / NULLIF(SUM(t.uren), 0) * 100)::numeric, 1) as pct
FROM uren_per_taak t
LEFT JOIN uren_per_werkbon w ON t.medew_gc_id = w.medew_gc_id AND t.maand = w.maand
WHERE t.maand >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '3 months'
GROUP BY t.maand
ORDER BY t.maand DESC;
```

**Alert als:** `ABS(pct) > 2.0` → Meer dan 2% afwijking tussen uren op taken en uren op werkbonnen.

**Toelichting:** Dit detecteert het exacte probleem van de WETEC case. Normaal is ~1% verschil acceptabel (timing doorberekenen), maar > 2% duidt op achterstallig doorberekenen in Syntess.

---

## Check 7: Medewerker-level Debit/Credit — Wie wijkt af?

**Prioriteit:** HOOG
**Frequentie:** Dagelijks (als check 6 alert geeft)

```sql
-- Detailniveau: welke medewerkers hebben de grootste afwijking?
WITH uren_taak AS (
    SELECT medew_gc_id, DATE_TRUNC('month', uitvoeringsdatum)::date as maand,
           SUM(aantal) as uren
    FROM prepare.factkosten
    WHERE taak_gc_id IS NOT NULL
    GROUP BY medew_gc_id, DATE_TRUNC('month', uitvoeringsdatum)
),
uren_wb AS (
    SELECT medew_gc_id, DATE_TRUNC('month', boekdatum)::date as maand,
           SUM(aantal) as uren
    FROM prepare.factkosten
    WHERE werkbon_gc_id IS NOT NULL AND taak_gc_id IS NOT NULL
    GROUP BY medew_gc_id, DATE_TRUNC('month', boekdatum)
)
SELECT
    t.medew_gc_id,
    m."Medewerker Code" as code,
    m."Medewerker" as naam,
    t.maand,
    t.uren as geboekt,
    COALESCE(w.uren, 0) as op_werkbon,
    t.uren - COALESCE(w.uren, 0) as verschil
FROM uren_taak t
LEFT JOIN uren_wb w ON t.medew_gc_id = w.medew_gc_id AND t.maand = w.maand
LEFT JOIN prepare.stammedewerkers m ON t.medew_gc_id = m.gc_id
WHERE t.maand >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '2 months'
  AND ABS(t.uren - COALESCE(w.uren, 0)) > 2
ORDER BY ABS(t.uren - COALESCE(w.uren, 0)) DESC
LIMIT 20;
```

**Alert als:** Er medewerkers zijn met > 8u verschil in de lopende maand.

---

## Check 8: Orphan Keys — Verwijzen fact-regels naar bestaande dimensies?

**Prioriteit:** MIDDEL
**Frequentie:** Dagelijks

```sql
-- Check: zijn er factkosten-regels met een medew_gc_id die niet in stammedewerkers staat?
SELECT 'medewerker' as dimensie,
       COUNT(*) as orphans
FROM prepare.factkosten f
LEFT JOIN prepare.stammedewerkers m ON f.medew_gc_id = m.gc_id
WHERE f.medew_gc_id IS NOT NULL AND m.gc_id IS NULL

UNION ALL

SELECT 'taak',
       COUNT(*)
FROM prepare.factkosten f
LEFT JOIN prepare.stamtaken t ON f.taak_gc_id = t.gc_id
WHERE f.taak_gc_id IS NOT NULL AND t.gc_id IS NULL

UNION ALL

SELECT 'werkbon',
       COUNT(*)
FROM prepare.factkosten f
WHERE f.werkbon_gc_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM prepare.factkosten f2
      WHERE f2.werkbon_gc_id = f.werkbon_gc_id
      AND f2.taak_gc_id IS NOT NULL
  )
  AND f.taak_gc_id IS NOT NULL;
```

**Alert als:** `orphans > 0` voor medewerker of taak → Dimensie-data ontbreekt, views zullen incomplete joins hebben.

---

## Check 9: NULL Key Percentage — Hoeveel regels missen kritieke koppelingen?

**Prioriteit:** MIDDEL
**Frequentie:** Wekelijks

```sql
-- Hoeveel % van de factkosten mist een werkbon- of taak-koppeling?
SELECT
    COUNT(*) as totaal,
    COUNT(*) FILTER (WHERE werkbon_gc_id IS NULL) as geen_werkbon,
    COUNT(*) FILTER (WHERE taak_gc_id IS NULL) as geen_taak,
    COUNT(*) FILTER (WHERE medew_gc_id IS NULL) as geen_medewerker,
    COUNT(*) FILTER (WHERE werkbon_gc_id IS NULL AND taak_gc_id IS NOT NULL) as uren_zonder_werkbon,
    ROUND(100.0 * COUNT(*) FILTER (WHERE werkbon_gc_id IS NULL AND taak_gc_id IS NOT NULL) / NULLIF(COUNT(*) FILTER (WHERE taak_gc_id IS NOT NULL), 0), 1) as pct_uren_zonder_werkbon
FROM prepare.factkosten;
```

**Alert als:** `pct_uren_zonder_werkbon > 5` → Meer dan 5% van de arbeidsregels heeft geen werkbon-koppeling.

**Toelichting:** Uren zonder werkbon-koppeling zijn exact het probleem dat Arthur signaleerde: de uren bestaan wel (Geboekte Uren view), maar verschijnen niet op de juiste werkbon (Werkbon kosten view).

---

## Check 10: Multi-Client Freshness Dashboard

**Prioriteit:** HOOG
**Frequentie:** Dagelijks

```sql
-- Draai dit op elke klant-database (via loop in Python)
SELECT
    current_database() as klant,
    (SELECT MAX(start_dt) FROM grip.grip_aud) as laatste_etl,
    (SELECT COUNT(*) FROM prepare.factkosten) as factkosten_rijen,
    (SELECT MAX(last_autoanalyze) FROM pg_stat_user_tables
     WHERE schemaname = 'prepare' AND relname = 'factkosten') as factkosten_freshness,
    EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(start_dt) FROM grip.grip_aud))) / 3600 as etl_uren_geleden
;
```

**Alert als:** `etl_uren_geleden > 30` → ETL heeft meer dan 30 uur niet gedraaid voor deze klant.

---

## Implementatie-volgorde

| Fase | Checks | Inspanning |
|------|--------|------------|
| **Week 1** | Check 1 (ETL completion) + Check 2 (ETL errors) + Check 10 (multi-client) | Laag — alleen grip-tabellen lezen |
| **Week 2** | Check 3 (freshness) + Check 4 (row count trend) + Check 5 (stage1→factkosten) | Middel — prepare-tabellen tellen |
| **Week 3** | Check 6 (debit/credit) + Check 7 (medewerker-detail) | Middel — de checks die het WETEC-issue detecteren |
| **Week 4** | Check 8 (orphan keys) + Check 9 (NULL keys) | Laag — eenmalige joins |

## Alert-kanalen

| Ernst | Actie |
|-------|-------|
| KRITIEK (check 1, 2, 6) | Direct e-mail + Slack/Teams melding |
| HOOG (check 3, 4, 5, 7, 10) | Dagelijkse samenvatting per klant |
| MIDDEL (check 8, 9) | Wekelijkse rapportage |

---

## Beperkingen

Deze checks detecteren problemen **binnen het DWH**. Het fundamentele probleem van de WETEC-case (SSM-export ≠ Syntess applicatie) zit **vóór** het DWH en is alleen op te lossen door:
1. Het doorberekenen in Syntess frequenter te draaien
2. Een directe export uit Syntess transactietabellen (buiten SSM om)
3. Een controle-totaal uit Syntess zelf als referentie

Check 6 en 7 zijn de beste proxy: ze detecteren het **symptoom** (uren op taken vs uren op werkbonnen lopen uiteen) waardoor we weten dat het doorberekenen achterloopt.
