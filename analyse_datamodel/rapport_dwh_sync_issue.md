# DWH Sync Issue - Analyse rapport

**Datum:** 20-02-2026
**Aanleiding:** Arthur Gartz meldt 7u arbeid in Power BI vs 26,5u in Syntess op werkbon WB25011324 (WETEC 1264)

---

## Conclusie

**Het DWH doet precies wat het moet doen.** De nachtelijke full load exporteert de SSM-data correct. Het probleem zit in Syntess zelf: de SSM (Syntess Standard Model) is een **berekende laag** die afhankelijk is van het "doorberekenen werkbonnen" proces. Wanneer uren worden omgeboekt in Syntess, updatet de SSM pas als het doorberekenen opnieuw draait.

---

## Architectuur en het probleem

### Pipeline

```
[1] Gebruiker boekt uren in Syntess     (direct zichtbaar in Syntess app)
                    |
[2] "Doorberekenen werkbonnen"          (Syntess batch -> vult SSM tabellen)
                    |
[3] Nachtelijke full load               (SSM -> DWH notifica schema)
                    |
[4] Transformatie                       (notifica -> uren/werkbonnen/prepare)
                    |
[5] Power BI                            (leest prepare tabellen)
```

**Stap 3, 4 en 5 werken correct.** Het probleem zit tussen stap 1 en 2: het doorberekenen houdt de SSM niet actueel na omboekingen.

### Twee SSM-tabellen, twee perspectieven

| Tabel | Bevat | Werkbon-link? |
|---|---|---|
| `SSM Geboekte uren` | Uren per medewerker/dag (vanuit urenstaat) | Nee |
| `SSM Werkbonparagraaf kosten` | Kosten per werkbon (vanuit doorberekenen) | Ja |

De transformatie JOINt deze twee om `uren.Geboekte Uren` te maken (uren MET werkbon-link). Als de `SSM WB kosten` verouderd is door ontbrekend doorberekenen, is de werkbon-koppeling in het DWH fout.

---

## Bewijs

### Case: Eeuwit Kievit op WB25011324

| Bron | Uren | Taak | Werkbon |
|---|---|---|---|
| Syntess applicatie | 19,5u | P02 | WB25011324 |
| SSM Geboekte uren | 11u | KAST (100034) | *(geen link)* |
| SSM WB kosten | 11u | KAST (100034) | WB 677499/674076 |
| DWH alle lagen | 11u | KAST | WB 677499/674076 |

De uren zijn in Syntess omgeboekt van KAST op andere werkbonnen naar P02 op WB25011324. De SSM heeft de omboeking niet meegekregen.

### Structureel: maandelijks gat van ~1%

| Maand | Geboekte uren | WB kosten | Verschil | % |
|---|---|---|---|---|
| jun 2025 | 3.258u | 3.207u | 51u | 1,6% |
| jul 2025 | 3.701u | 3.665u | 36u | 1,0% |
| aug 2025 | 2.999u | 2.971u | 28u | 0,9% |
| sep 2025 | 3.372u | 3.339u | 34u | 1,0% |
| okt 2025 | 3.927u | 3.898u | 30u | 0,8% |
| nov 2025 | 3.290u | 3.256u | 34u | 1,0% |
| **dec 2025** | **2.495u** | **2.427u** | **69u** | **2,7%** |

Er is **altijd** een gat, maar december is 2-3x groter dan normaal. Dit past bij: vakantieperiode, minder doorberekenen, meer achterstallige omboekingen.

### Week-patroon WB kosten (dec 2025)

| Week (boekdatum) | Medewerkers | Regels | Uren |
|---|---|---|---|
| 01-12 (week 49) | 26 | 219 | 781u |
| 08-12 (week 50) | 26 | 244 | 836u |
| 15-12 (week 51) | 27 | 224 | 799u |
| 22-12 (week 52) | **1** | **2** | **7u** |

Week 52 is vrijwel leeg. Het doorberekenen is na week 51 grotendeels gestopt. Uren die NA het doorberekenen van week 51 zijn omgeboekt (zoals Eeuwit's uren) komen niet meer bij.

---

## Checks & balances

Uitgewerkt in apart document: **[checks_and_balances.md](checks_and_balances.md)** (top-10 checks met SQL queries)
Geautomatiseerd script: **[daily_checks.py](daily_checks.py)** (draait alle checks per klant)

### Eerste resultaten (20-02-2026)

| Klant | ETL | Freshness | Debit/Credit | Orphan Keys | NULL Keys |
|-------|-----|-----------|-------------|-------------|-----------|
| WETEC (1264) | OK | OK | **ALERT** (55.8% dec) | OK | **ALERT** (25.6%) |
| Liquiditeit Demo (1241) | OK | OK | **ALERT** (97% - demo) | OK | **ALERT** (91.1%) |
| Van den Buijs (1256) | **ALERT** | **ALERT** (8 mnd!) | n.v.t. | n.v.t. | **ALERT** (38.6%) |

**Belangrijkste bevinding:** Van den Buijs ETL draait al 8 maanden niet (laatste run: juni 2025).

---

## Aanbevelingen

### Korte termijn
1. **WETEC: doorberekenen werkbonnen opnieuw draaien** in Syntess voor week 51-52 en januari/februari 2026
2. **Antwoord aan Arthur:** De oorzaak is bekend, werkbonkosten worden opnieuw doorberekend
3. **Van den Buijs: ETL opnieuw starten** - data is 8 maanden oud

### Middellange termijn
4. **Monitoring implementeren:** daily_checks.py dagelijks draaien over alle klant-databases
5. **Alert bij afwijking > 2%** in de debit/credit aansluiting
6. **Escalatie-protocol:** als de ETL > 24 uur niet gedraaid heeft

### Structureel
7. **Met Syntess (BTEK) afstemmen:**
   - Kan het doorberekenen automatisch draaien na elke omboeking?
   - Of minstens dagelijks automatisch als batch?
   - Is er een API/export die het SSM bypassed en direct de actuele transactiedata levert?
8. **DWH: pre-load validatie** toevoegen die de debit/credit check draait VOORDAT de transformatie start, en alert bij afwijking
