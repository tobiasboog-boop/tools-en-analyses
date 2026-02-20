-- ============================================================
-- VERIFICATIE: Steekproef na anonimisatie
-- Elke query controleert of gevoelige data is vervangen
-- ============================================================

--QUERY: Relaties (klanten/leveranciers)
SELECT relatie, relatiekortenaam, email, kvknummer, btwnummer
FROM prepare.stamrelaties
WHERE relatie IS NOT NULL AND relatie != ''
LIMIT 10;

--QUERY: Medewerkers (namen + adres)
SELECT medewerker, roepnaam, achternaam, email, straat, postcode, plaats
FROM prepare.stammedewerkers
WHERE medewerker IS NOT NULL AND medewerker != ''
LIMIT 10;

--QUERY: Personen (persoonsgegevens)
SELECT roepnaam, voornamen, gc_korte_naam, telefoon1, mobiel, email
FROM prepare.stampersonen
WHERE roepnaam IS NOT NULL AND roepnaam != ''
LIMIT 10;

--QUERY: Adressen
SELECT straat, huisnummer, postcode, plaats, locatie
FROM prepare.stamadressen
WHERE straat IS NOT NULL AND straat != ''
LIMIT 10;

--QUERY: Administraties (bedrijfsnamen)
SELECT administratie, gc_korte_naam
FROM prepare.stamadministraties
WHERE administratie IS NOT NULL AND administratie != ''
LIMIT 10;

--QUERY: Objecten (gebouwen + contactgegevens)
SELECT object, straat, postcode, plaats, eigenaar, contactpersoon, telefoon
FROM prepare.dimobjecten
WHERE object IS NOT NULL AND object != ''
LIMIT 10;

--QUERY: Werkbonnen (klant/monteur)
SELECT werkbon, klant, debiteur, monteur, contactpersoon, plaats, email
FROM prepare.dimwerkbonnen
WHERE werkbon IS NOT NULL AND werkbon != ''
LIMIT 10;

--QUERY: Projecten (titel + opdrachtgever)
SELECT project_code, project_titel, opdrachtgever, projectleider, plaats
FROM prepare.dimprojecten
WHERE project_titel IS NOT NULL AND project_titel != ''
LIMIT 10;

--QUERY: Verkoopfactuurtermijnen (debiteur + adres)
SELECT debiteur, straat, postcode, plaats
FROM prepare.factverkoopfactuurtermijnen
WHERE debiteur IS NOT NULL AND debiteur != ''
LIMIT 10;

--QUERY: Inkoopfactuurtermijnen (crediteur)
SELECT crediteur
FROM prepare.factinkoopfactuurtermijnen
WHERE crediteur IS NOT NULL AND crediteur != ''
LIMIT 10;

--QUERY: Opbrengsten (debiteur + adres)
SELECT debiteur, debiteurbezoekadres, debiteurbezoekplaats, omschrijving
FROM prepare.factopbrengsten
WHERE debiteur IS NOT NULL AND debiteur != ''
LIMIT 10;

--QUERY: Bankafschriftregels (IBAN + omschrijving)
SELECT iban_eigen_bedrijf, omschrijving, factuur_document_titel
FROM prepare.factbankafschriftboekingregels
WHERE iban_eigen_bedrijf IS NOT NULL AND iban_eigen_bedrijf != ''
LIMIT 10;

--QUERY: Planbare medewerkers (namen)
SELECT medewerker, roepnaam, achternaam, samengestelde_naam, relatie
FROM prepare.factplanbaremedewerkers
WHERE medewerker IS NOT NULL AND medewerker != ''
LIMIT 10;

--QUERY: Endview - Verkoopfactuurtermijnen (SSM laag)
SELECT "Debiteur", "Straat", "Postcode", "Plaats", "Bedrag"
FROM financieel."Verkoopfactuurtermijnen"
LIMIT 10;

--QUERY: Endview - Inkoopfactuurtermijnen (SSM laag)
SELECT "Crediteur", "Bedrag", "Vervaldatum"
FROM financieel."Inkoopfactuurtermijnen"
LIMIT 10;

--QUERY: Endview - Werkbonnen (SSM laag)
SELECT "Werkbon", "Klant", "Debiteur", "Monteur"
FROM installatie."Werkbonnen"
LIMIT 10;

--QUERY: Endview - Projecten (SSM laag)
SELECT "Project", "Hoofdproject", "Opdrachtgever", "Projectleider"
FROM installatie."Projecten"
LIMIT 10;

-- ============================================================
-- CONTROLE: Zoek naar resterende originele data
-- Pas onderstaande namen aan naar echte namen uit de brondata
-- om te verifiëren dat ze nergens meer voorkomen
-- ============================================================

--QUERY: Zoek naar resterende echte namen (pas aan!)
-- Vervang 'ECHTE_NAAM' door een bekende naam uit de originele data
-- SELECT 'stamrelaties' as tabel, COUNT(*) as matches FROM prepare.stamrelaties WHERE relatie ILIKE '%ECHTE_NAAM%'
-- UNION ALL
-- SELECT 'dimwerkbonnen', COUNT(*) FROM prepare.dimwerkbonnen WHERE klant ILIKE '%ECHTE_NAAM%' OR monteur ILIKE '%ECHTE_NAAM%'
-- UNION ALL
-- SELECT 'dimprojecten', COUNT(*) FROM prepare.dimprojecten WHERE project_titel ILIKE '%ECHTE_NAAM%' OR opdrachtgever ILIKE '%ECHTE_NAAM%';
SELECT 'Verificatie compleet' AS status;
