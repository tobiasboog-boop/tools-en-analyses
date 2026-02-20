"""Dagelijkse DWH data-integriteit checks per klant.

Draait de top-10 checks uit checks_and_balances.md en geeft een samenvatting.

Gebruik:
    python daily_checks.py              # Alle klanten
    python daily_checks.py 1264         # Alleen WETEC
    python daily_checks.py --verbose    # Met detail per check
"""
import sys
import os
from datetime import datetime
from db_connection import syntess_connection, KLANTEN


def run_check(conn, name, query, alert_fn, verbose=False):
    """Draai een check en geef status terug."""
    cur = conn.cursor()
    try:
        cur.execute(query)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        alert = alert_fn(rows)
        status = "ALERT" if alert else "OK"
        if verbose or alert:
            print(f"  {'!!' if alert else 'OK'} {name}")
            if alert and rows:
                for row in rows[:5]:
                    print(f"     {row}")
        return {"name": name, "status": status, "rows": rows, "alert": alert}
    except Exception as e:
        conn.rollback()
        print(f"  !! {name}: FOUT - {e}")
        return {"name": name, "status": "ERROR", "rows": [], "alert": str(e)}
    finally:
        cur.close()


def check_etl_completion(conn, verbose=False):
    """Check 1: Heeft de nachtelijke ETL vandaag gedraaid?"""
    return run_check(conn, "ETL Completion", """
        SELECT
            MAX(start_dt) as laatste_run,
            COUNT(*) as stappen_vandaag
        FROM grip.grip_aud
        WHERE start_dt::date = CURRENT_DATE
    """, lambda rows: not rows or rows[0]["laatste_run"] is None, verbose)


def check_etl_errors(conn, verbose=False):
    """Check 2: Zijn er GRIP fouten in de laatste 7 dagen?"""
    return run_check(conn, "ETL Errors (7d)", """
        SELECT start_dt, source, target, error_msg
        FROM grip.grip_log
        WHERE error_msg IS NOT NULL
          AND error_msg NOT IN ('Success', 'running ..')
          AND start_dt > CURRENT_DATE - INTERVAL '7 days'
        ORDER BY start_dt DESC
        LIMIT 10
    """, lambda rows: len(rows) > 0, verbose)


def check_table_freshness(conn, verbose=False):
    """Check 3: Zijn de prepare-tabellen actueel?"""
    return run_check(conn, "Table Freshness", """
        SELECT relname as tabel,
               n_live_tup as rijen,
               last_autoanalyze,
               EXTRACT(EPOCH FROM (NOW() - last_autoanalyze)) / 3600 as uren_oud
        FROM pg_stat_user_tables
        WHERE schemaname = 'prepare'
          AND relname IN ('factkosten', 'stage1_arbeidkosten', 'stage1_inkoopkosten')
        ORDER BY last_autoanalyze ASC NULLS FIRST
    """, lambda rows: any(
        r["uren_oud"] is None or r["uren_oud"] > 30 for r in rows
    ), verbose)


def check_factkosten_trend(conn, verbose=False):
    """Check 4: Plotselinge afwijking in factkosten volume?"""
    return run_check(conn, "factkosten Trend (14d)", """
        SELECT start_dt::date as datum, ins as rijen
        FROM grip.grip_aud
        WHERE LOWER(target) = 'factkosten'
          AND start_dt > CURRENT_DATE - INTERVAL '14 days'
        ORDER BY start_dt DESC
        LIMIT 7
    """, lambda rows: (
        len(rows) >= 2
        and rows[1]["rijen"] > 0
        and abs(rows[0]["rijen"] - rows[1]["rijen"]) / rows[1]["rijen"] > 0.10
    ), verbose)


def check_stage1_reconciliation(conn, verbose=False):
    """Check 5: Tellen stage1 bronnen op tot factkosten?"""
    return run_check(conn, "Stage1 -> factkosten", """
        WITH bronnen AS (
            SELECT 'arbeidkosten' as bron, COUNT(*) as rijen
            FROM prepare.stage1_arbeidkosten
            UNION ALL SELECT 'inkoopkosten', COUNT(*) FROM prepare.stage1_inkoopkosten
            UNION ALL SELECT 'magazijnuitgifte', COUNT(*) FROM prepare.stage1_magazijnuitgiftekosten
            UNION ALL SELECT 'vrijekosten', COUNT(*) FROM prepare.stage1_vrijekosten
            UNION ALL SELECT 'afschrijving', COUNT(*) FROM prepare.stage1_afschrijvingkosten
            UNION ALL SELECT 'bankafschrift', COUNT(*) FROM prepare.stage1_bankafschriftkosten
        ),
        totalen AS (
            SELECT SUM(rijen) as som_bronnen FROM bronnen
        )
        SELECT t.som_bronnen,
               (SELECT COUNT(*) FROM prepare.factkosten) as factkosten,
               (SELECT COUNT(*) FROM prepare.factkosten) - t.som_bronnen as verschil
        FROM totalen t
    """, lambda rows: rows and rows[0]["verschil"] != 0, verbose)


def check_debit_credit(conn, verbose=False):
    """Check 6: Geboekte uren vs werkbonkosten per maand."""
    return run_check(conn, "Debit/Credit uren", """
        WITH uren_taak AS (
            SELECT DATE_TRUNC('month', uitvoeringsdatum)::date as maand,
                   SUM(aantal) as uren
            FROM prepare.factkosten
            WHERE taak_gc_id IS NOT NULL
            GROUP BY DATE_TRUNC('month', uitvoeringsdatum)
        ),
        uren_wb AS (
            SELECT DATE_TRUNC('month', boekdatum)::date as maand,
                   SUM(aantal) as uren
            FROM prepare.factkosten
            WHERE werkbon_gc_id IS NOT NULL AND taak_gc_id IS NOT NULL
            GROUP BY DATE_TRUNC('month', boekdatum)
        )
        SELECT t.maand,
               ROUND(t.uren::numeric, 1) as geboekt,
               ROUND(COALESCE(w.uren, 0)::numeric, 1) as werkbon,
               ROUND((t.uren - COALESCE(w.uren, 0))::numeric, 1) as verschil,
               ROUND(((t.uren - COALESCE(w.uren, 0)) / NULLIF(t.uren, 0) * 100)::numeric, 1) as pct
        FROM uren_taak t
        LEFT JOIN uren_wb w ON t.maand = w.maand
        WHERE t.maand >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '3 months'
          AND t.maand <= DATE_TRUNC('month', CURRENT_DATE)
        ORDER BY t.maand DESC
    """, lambda rows: any(
        r["pct"] is not None and abs(float(r["pct"])) > 2.0 for r in rows
    ), verbose)


def check_medewerker_debit_credit(conn, verbose=False):
    """Check 7: Welke medewerkers wijken het meest af?"""
    return run_check(conn, "Medewerker verschil", """
        WITH uren_taak AS (
            SELECT medew_gc_id, DATE_TRUNC('month', uitvoeringsdatum)::date as maand,
                   SUM(aantal) as uren
            FROM prepare.factkosten WHERE taak_gc_id IS NOT NULL
            GROUP BY medew_gc_id, DATE_TRUNC('month', uitvoeringsdatum)
        ),
        uren_wb AS (
            SELECT medew_gc_id, DATE_TRUNC('month', boekdatum)::date as maand,
                   SUM(aantal) as uren
            FROM prepare.factkosten WHERE werkbon_gc_id IS NOT NULL AND taak_gc_id IS NOT NULL
            GROUP BY medew_gc_id, DATE_TRUNC('month', boekdatum)
        )
        SELECT t.medew_gc_id,
               m.medewerkercode as code,
               m.medewerker as naam,
               t.maand,
               ROUND(t.uren::numeric, 1) as geboekt,
               ROUND(COALESCE(w.uren, 0)::numeric, 1) as werkbon,
               ROUND((t.uren - COALESCE(w.uren, 0))::numeric, 1) as verschil
        FROM uren_taak t
        LEFT JOIN uren_wb w ON t.medew_gc_id = w.medew_gc_id AND t.maand = w.maand
        LEFT JOIN prepare.stammedewerkers m ON t.medew_gc_id = m.medewerkerkey
        WHERE t.maand >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
          AND t.maand <= DATE_TRUNC('month', CURRENT_DATE)
          AND ABS(t.uren - COALESCE(w.uren, 0)) > 2
        ORDER BY ABS(t.uren - COALESCE(w.uren, 0)) DESC
        LIMIT 10
    """, lambda rows: any(
        abs(float(r["verschil"])) > 8 for r in rows
    ), verbose)


def check_orphan_keys(conn, verbose=False):
    """Check 8: Verwijzen fact-regels naar bestaande dimensies?"""
    return run_check(conn, "Orphan Keys", """
        SELECT 'medewerker' as dimensie, COUNT(*) as orphans
        FROM prepare.factkosten f
        LEFT JOIN prepare.stammedewerkers m ON f.medew_gc_id = m.medewerkerkey
        WHERE f.medew_gc_id IS NOT NULL AND m.medewerkerkey IS NULL
        UNION ALL
        SELECT 'taak', COUNT(*)
        FROM prepare.factkosten f
        LEFT JOIN prepare.stamtaken t ON f.taak_gc_id = t.gc_id
        WHERE f.taak_gc_id IS NOT NULL AND t.taak IS NULL
    """, lambda rows: any(r["orphans"] > 0 for r in rows), verbose)


def check_null_keys(conn, verbose=False):
    """Check 9: Hoeveel regels missen kritieke koppelingen?"""
    return run_check(conn, "NULL Key %", """
        SELECT
            COUNT(*) as totaal,
            COUNT(*) FILTER (WHERE werkbon_gc_id IS NULL AND taak_gc_id IS NOT NULL) as uren_zonder_wb,
            ROUND(100.0 * COUNT(*) FILTER (WHERE werkbon_gc_id IS NULL AND taak_gc_id IS NOT NULL)
                  / NULLIF(COUNT(*) FILTER (WHERE taak_gc_id IS NOT NULL), 0), 1) as pct_uren_zonder_wb
        FROM prepare.factkosten
    """, lambda rows: (
        rows and rows[0]["pct_uren_zonder_wb"] is not None
        and float(rows[0]["pct_uren_zonder_wb"]) > 5
    ), verbose)


ALL_CHECKS = [
    check_etl_completion,
    check_etl_errors,
    check_table_freshness,
    check_factkosten_trend,
    check_stage1_reconciliation,
    check_debit_credit,
    check_medewerker_debit_credit,
    check_orphan_keys,
    check_null_keys,
]


def run_all_checks(klantnummer, verbose=False):
    """Draai alle checks voor een klant."""
    naam = KLANTEN.get(klantnummer, f"Klant {klantnummer}")
    print(f"\n{'='*60}")
    print(f"  {naam} ({klantnummer})  - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    conn = syntess_connection(klantnummer)
    results = []
    alerts = 0

    for check_fn in ALL_CHECKS:
        result = check_fn(conn, verbose)
        results.append(result)
        if result["alert"]:
            alerts += 1

    conn.close()

    print(f"\n  Samenvatting: {len(results) - alerts}/{len(results)} OK, {alerts} alerts")
    if alerts:
        print(f"  Alerts:")
        for r in results:
            if r["alert"]:
                print(f"    - {r['name']}")

    return results


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    if args:
        klanten = [int(a) for a in args]
    else:
        klanten = list(KLANTEN.keys())

    print(f"DWH Data-integriteit Checks  - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Klanten: {', '.join(KLANTEN.get(k, str(k)) for k in klanten)}")

    all_results = {}
    for klantnummer in klanten:
        try:
            all_results[klantnummer] = run_all_checks(klantnummer, verbose)
        except Exception as e:
            print(f"\n!! {KLANTEN.get(klantnummer, klantnummer)}: CONNECTIE FOUT - {e}")

    # Eindoverzicht
    print(f"\n{'='*60}")
    print(f"  EINDOVERZICHT")
    print(f"{'='*60}")
    for klantnr, results in all_results.items():
        naam = KLANTEN.get(klantnr, str(klantnr))
        alerts = sum(1 for r in results if r["alert"])
        status = "OK" if alerts == 0 else f"{alerts} ALERT(S)"
        print(f"  {naam:20s} {status}")


if __name__ == "__main__":
    main()
