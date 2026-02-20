# Database Migratie: 1190 → 1210

## Overzicht

Dit document beschrijft de migratie van het `contract_checker` schema van database 1190 naar database 1210.

### Wat wordt gemigreerd?

**Schema:** `contract_checker`

**Tabellen:**
- `contracts` - Contract metadata en koppelingen met klanten
- `classifications` - AI classificatie resultaten voor werkbonnen
- `contract_changes` - Audit log voor contract wijzigingen

**Database objecten:**
- Alle indexes
- Foreign key constraints
- Check constraints
- Sequences
- Views (indien aanwezig)

## Voorwaarden

1. **Toegang:** PostgreSQL admin rechten op beide databases
2. **Extension:** `postgres_fdw` moet beschikbaar zijn
3. **Database 1210:** Schema moet al zijn aangemaakt (gebruik [setup.sql](sql/setup.sql))
4. **Netwerk:** Connectiviteit tussen databases
5. **Wachtwoord:** Postgres wachtwoord moet beschikbaar zijn

## Migratie Stappen

### Stap 1: Voorbereiding

1. **Backup maken van database 1190 (aanbevolen):**
   ```bash
   pg_dump -h 10.3.152.9 -U postgres -d 1190 -n contract_checker -F c -f contract_checker_backup_1190.dump
   ```

2. **Controleer huidige data in 1190:**
   ```bash
   psql -h 10.3.152.9 -U postgres -d 1190 -c "SELECT COUNT(*) FROM contract_checker.contracts;"
   psql -h 10.3.152.9 -U postgres -d 1190 -c "SELECT COUNT(*) FROM contract_checker.classifications;"
   psql -h 10.3.152.9 -U postgres -d 1190 -c "SELECT COUNT(*) FROM contract_checker.contract_changes;"
   ```

3. **Zorg dat database 1210 klaar is:**
   ```bash
   # Als het schema nog niet bestaat, voer eerst setup.sql uit
   psql -h 10.3.152.9 -U postgres -d 1210 -f sql/setup.sql
   ```

### Stap 2: Voer de migratie uit

```bash
psql -h 10.3.152.9 -U postgres -d 1210 -f sql/migrate_1190_to_1210.sql
```

**Wat doet dit script?**
1. Maakt een Foreign Data Wrapper connectie naar database 1190
2. Importeert het schema tijdelijk in 1210
3. Telt records in bron database
4. Kopieert alle data (contracts → contract_changes → classifications)
5. Update sequences naar de juiste waarden
6. Verifieert de migratie
7. Ruimt tijdelijke objecten op

**Verwachte output:**
- Aantal records in bron en doel databases
- Voortgang per tabel
- Verificatie resultaten
- Success bericht

### Stap 3: Verificatie

Voer het verificatie script uit om de migratie te controleren:

```bash
psql -h 10.3.152.9 -U postgres -d 1210 -f sql/verify_migration.sql
```

**Het script controleert:**
- Record counts komen overeen
- Geen missende records
- Geen orphaned records (foreign key integriteit)
- Sequences zijn correct ingesteld
- Indexes zijn aanwezig
- Data integriteit

**Verwachte resultaten:**
- Alle counts in 1190 en 1210 zijn identiek
- Alle "missing" en "orphaned" counts zijn 0
- Sequences zijn > max(id) van de tabellen

### Stap 4: Test de applicatie

1. **Controleer .env configuratie:**
   ```env
   DB_NAME=1210
   DB_SCHEMA=contract_checker
   ```

2. **Start de applicatie:**
   ```bash
   streamlit run app.py
   ```

3. **Test de functionaliteit:**
   - Contract Register pagina moet contracts tonen
   - Classification moet werken met bestaande data
   - Results pagina moet oude classificaties tonen

### Stap 5: Opruimen (OPTIONEEL)

**WAARSCHUWING:** Doe dit pas nadat je zeker weet dat de migratie succesvol is en de applicatie correct werkt!

```bash
# Drop het oude schema uit database 1190
psql -h 10.3.152.9 -U postgres -d 1190 -c "DROP SCHEMA contract_checker CASCADE;"
```

## Rollback Procedure

Als de migratie mislukt of er zijn problemen:

### Optie 1: Restore vanuit backup
```bash
pg_restore -h 10.3.152.9 -U postgres -d 1190 -n contract_checker contract_checker_backup_1190.dump
```

### Optie 2: Terug naar 1190
1. Update [.env](c:\Projects\contract-check\.env):
   ```env
   DB_NAME=1190
   ```
2. Herstart de applicatie

## Troubleshooting

### Foutmelding: "postgres_fdw extension not available"
**Oplossing:** Installeer de extensie als superuser:
```sql
CREATE EXTENSION postgres_fdw;
```

### Foutmelding: "password authentication failed"
**Oplossing:** Controleer het wachtwoord in het migratie script en pas aan indien nodig:
```sql
CREATE USER MAPPING FOR postgres
    SERVER db_1190
    OPTIONS (user 'postgres', password 'HET_CORRECTE_WACHTWOORD');
```

### Foutmelding: "duplicate key value violates unique constraint"
**Oplossing:** Er bestaat al data in 1210. Optie:
- Verwijder bestaande data in 1210 eerst: `TRUNCATE contract_checker.contracts CASCADE;`
- Of pas het script aan om `ON CONFLICT` te gebruiken (dit staat al in het script)

### Sequences zijn verkeerd
**Oplossing:** Handmatig resetten:
```sql
SELECT setval('contract_checker.contracts_id_seq',
    (SELECT MAX(id) FROM contract_checker.contracts));
SELECT setval('contract_checker.classifications_id_seq',
    (SELECT MAX(id) FROM contract_checker.classifications));
SELECT setval('contract_checker.contract_changes_id_seq',
    (SELECT MAX(id) FROM contract_checker.contract_changes));
```

## Checklist

- [ ] Backup gemaakt van database 1190
- [ ] Database 1210 schema is aangemaakt (setup.sql)
- [ ] Migratie script uitgevoerd (migrate_1190_to_1210.sql)
- [ ] Verificatie script uitgevoerd (verify_migration.sql)
- [ ] Alle verificaties succesvol (counts kloppen, geen orphaned records)
- [ ] .env aangepast naar DB_NAME=1210
- [ ] Applicatie getest en werkt correct
- [ ] Team is geïnformeerd over de migratie
- [ ] Oude schema in 1190 verwijderd (optioneel, na bevestiging)

## Contact

Bij vragen of problemen tijdens de migratie, neem contact op met het development team.

---

**Laatste update:** 2026-01-19
