"""Analyze open actions that indicate a werkbon trajectory is NOT ready yet."""
import sys
sys.path.insert(0, ".")
from src.models.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print("=" * 70)
print("ANALYSE: Openstaande acties voor Uitgevoerd + Openstaand werkbonnen")
print("=" * 70)

# 1. Check opvolgingen status
print("\n### 1. Opvolgingen Status ###")
result = db.execute(text('''
    SELECT
        o."Status",
        COUNT(DISTINCT o."WerkbonparagraafKey") as paragrafen,
        COUNT(*) as opvolgingen
    FROM werkbonnen."Werkbon opvolgingen" o
    JOIN werkbonnen."Werkbonparagrafen" p ON o."WerkbonparagraafKey" = p."WerkbonparagraafKey"
    JOIN werkbonnen."Werkbonnen" w ON p."WerkbonDocumentKey" = w."WerkbonDocumentKey"
    WHERE TRIM(w."Status") = 'Uitgevoerd'
      AND TRIM(w."Documentstatus") = 'Openstaand'
    GROUP BY o."Status"
    ORDER BY opvolgingen DESC
'''))
for row in result:
    print(f"  {row[0]}: {row[2]:,} opvolgingen in {row[1]:,} paragrafen")

# 2. Check kostenstatus (open bestellingen?)
print("\n### 2. Kostenstatus (indicatie open bestellingen) ###")
result = db.execute(text('''
    SELECT
        k."Kostenstatus",
        COUNT(*) as regels,
        ROUND(SUM(k."Regelbedrag")::numeric, 0) as bedrag
    FROM financieel."Kosten" k
    JOIN werkbonnen."Werkbonnen" w ON k."WerkbonKey" = w."WerkbonDocumentKey"
    WHERE TRIM(w."Status") = 'Uitgevoerd'
      AND TRIM(w."Documentstatus") = 'Openstaand'
    GROUP BY k."Kostenstatus"
    ORDER BY regels DESC
'''))
for row in result:
    print(f"  {row[0]}: {row[1]:,} regels | EUR {row[2] or 0:,.0f}")

# 3. Check pakbon status
print("\n### 3. Pakbon Status (leveringen) ###")
result = db.execute(text('''
    SELECT
        k."Pakbon Status",
        COUNT(*) as regels
    FROM financieel."Kosten" k
    JOIN werkbonnen."Werkbonnen" w ON k."WerkbonKey" = w."WerkbonDocumentKey"
    WHERE TRIM(w."Status") = 'Uitgevoerd'
      AND TRIM(w."Documentstatus") = 'Openstaand'
    GROUP BY k."Pakbon Status"
    ORDER BY regels DESC
'''))
for row in result:
    print(f"  {row[0]}: {row[1]:,} regels")

# 4. Analyse per werkbon - hoeveel hebben open acties?
print("\n### 4. Werkbonnen met/zonder open acties ###")
result = db.execute(text('''
    WITH werkbon_status AS (
        SELECT
            w."WerkbonDocumentKey",
            w."Werkbon",
            -- Open opvolgingen
            (SELECT COUNT(*) FROM werkbonnen."Werkbon opvolgingen" o
             JOIN werkbonnen."Werkbonparagrafen" p ON o."WerkbonparagraafKey" = p."WerkbonparagraafKey"
             WHERE p."WerkbonDocumentKey" = w."WerkbonDocumentKey"
             AND TRIM(o."Status") NOT IN ('Afgehandeld', 'Vervallen')) as open_opvolgingen,
            -- Niet-definitieve kosten
            (SELECT COUNT(*) FROM financieel."Kosten" k
             WHERE k."WerkbonKey" = w."WerkbonDocumentKey"
             AND TRIM(k."Kostenstatus") != 'Definitief') as niet_definitieve_kosten
        FROM werkbonnen."Werkbonnen" w
        WHERE TRIM(w."Status") = 'Uitgevoerd'
          AND TRIM(w."Documentstatus") = 'Openstaand'
    )
    SELECT
        CASE
            WHEN open_opvolgingen > 0 AND niet_definitieve_kosten > 0 THEN 'Beide open'
            WHEN open_opvolgingen > 0 THEN 'Alleen opvolgingen open'
            WHEN niet_definitieve_kosten > 0 THEN 'Alleen kosten niet definitief'
            ELSE 'Geen open acties (KLAAR?)'
        END as status,
        COUNT(*) as werkbonnen
    FROM werkbon_status
    GROUP BY
        CASE
            WHEN open_opvolgingen > 0 AND niet_definitieve_kosten > 0 THEN 'Beide open'
            WHEN open_opvolgingen > 0 THEN 'Alleen opvolgingen open'
            WHEN niet_definitieve_kosten > 0 THEN 'Alleen kosten niet definitief'
            ELSE 'Geen open acties (KLAAR?)'
        END
    ORDER BY werkbonnen DESC
'''))
print("  Uitgevoerd + Openstaand werkbonnen:")
for row in result:
    print(f"    {row[0]}: {row[1]:,}")

# 5. Vergelijk met Historisch - hadden die ooit open acties?
print("\n### 5. Ter vergelijking: Uitgevoerd + Historisch ###")
result = db.execute(text('''
    SELECT
        o."Status",
        COUNT(*) as opvolgingen
    FROM werkbonnen."Werkbon opvolgingen" o
    JOIN werkbonnen."Werkbonparagrafen" p ON o."WerkbonparagraafKey" = p."WerkbonparagraafKey"
    JOIN werkbonnen."Werkbonnen" w ON p."WerkbonDocumentKey" = w."WerkbonDocumentKey"
    WHERE TRIM(w."Status") = 'Uitgevoerd'
      AND TRIM(w."Documentstatus") = 'Historisch'
    GROUP BY o."Status"
    ORDER BY opvolgingen DESC
'''))
print("  Opvolgingen status in Historische werkbonnen:")
for row in result:
    print(f"    {row[0]}: {row[1]:,}")

db.close()

print("\n" + "=" * 70)
print("CONCLUSIE:")
print("=" * 70)
print("""
Werkbonnen met 'Geen open acties' zijn mogelijk KLAAR voor classificatie.
Werkbonnen met open opvolgingen of niet-definitieve kosten zijn mogelijk
nog NIET klaar - er kunnen nog wijzigingen komen.

Dit onderscheid is belangrijk voor:
1. Dagelijkse beoordeling: focus eerst op 'klaar' werkbonnen
2. Voorspelling: open acties kunnen leiden tot meer kosten
""")
