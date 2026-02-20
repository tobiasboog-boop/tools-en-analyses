-- ============================================================
-- SYNTESS DWH ANONIMISATIE SCRIPT
-- Database: gekloonde demo-database (bijv. demo_1225)
-- Bron: database 1225
-- Schema: prepare (endviews zijn views hierop)
--
-- Dit script vervangt alle klantgevoelige tekstuele data
-- met realistische Nederlandse demodata.
-- Numerieke/financiele waarden blijven INTACT.
-- ============================================================

-- ============================================================
-- STAP 0: LOOKUP TABELLEN MET DEMODATA
-- ============================================================
-- Tijdelijke tabellen met Nederlandse namen, adressen, etc.
-- We gebruiken een hash-mapping zodat dezelfde bronwaarde
-- altijd dezelfde demowaarde krijgt (consistentie).

-- Helper functie: deterministische mapping van tekst naar index
CREATE OR REPLACE FUNCTION prepare.anon_index(input_text text, pool_size int)
RETURNS int AS $$
BEGIN
    IF input_text IS NULL OR input_text = '' THEN
        RETURN 0;
    END IF;
    RETURN (abs(hashtext(input_text)) % pool_size) + 1;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Nederlandse voornamen (50 stuks)
CREATE TEMPORARY TABLE _voornamen (id serial, naam varchar(30));
INSERT INTO _voornamen (naam) VALUES
('Jan'),('Pieter'),('Henk'),('Willem'),('Kees'),('Dirk'),('Gerrit'),('Bas'),('Tom'),('Sander'),
('Mark'),('Erik'),('Paul'),('Frank'),('Rob'),('Joost'),('Dennis'),('Stefan'),('Martijn'),('Rick'),
('Anne'),('Lisa'),('Maria'),('Sophie'),('Eva'),('Linda'),('Kim'),('Sandra'),('Monique'),('Petra'),
('Ingrid'),('Anja'),('Marieke'),('Esther'),('Nicole'),('Marion'),('Judith'),('Ellen'),('Bianca'),('Wendy'),
('Ruud'),('Wim'),('Arjan'),('Marcel'),('Hugo'),('Thijs'),('Daan'),('Lucas'),('Bram'),('Lars');

-- Nederlandse achternamen (50 stuks)
CREATE TEMPORARY TABLE _achternamen (id serial, naam varchar(40));
INSERT INTO _achternamen (naam) VALUES
('de Vries'),('Jansen'),('van den Berg'),('Bakker'),('Visser'),('Smit'),('Meijer'),('de Boer'),('Mulder'),('de Groot'),
('Bos'),('Vos'),('Peters'),('Hendriks'),('van Dijk'),('Dekker'),('Brouwer'),('de Wit'),('Dijkstra'),('Smeets'),
('de Graaf'),('van der Linden'),('van Leeuwen'),('de Jong'),('Vermeer'),('Schouten'),('Kuijpers'),('Willems'),('van der Heijden'),('Hermans'),
('Wolters'),('Hoekstra'),('van Dam'),('Scholten'),('Timmermans'),('Groen'),('van Beek'),('Jacobs'),('Vlaar'),('Mol'),
('van der Wal'),('Kramer'),('Janssen'),('Post'),('Kok'),('Verhoeven'),('Zwart'),('van Loon'),('Evers'),('Koster');

-- Nederlandse bedrijfsnamen (40 stuks)
CREATE TEMPORARY TABLE _bedrijfsnamen (id serial, naam varchar(80));
INSERT INTO _bedrijfsnamen (naam) VALUES
('Bakker & Zonen BV'),('De Groot Techniek BV'),('Visser Installaties BV'),('Jansen Bouw BV'),('Van Dijk Services BV'),
('Brouwer Engineering BV'),('Smit & Partners BV'),('Meijer Facilitair BV'),('Mulder Vastgoed BV'),('De Boer Onderhoud BV'),
('Peters Klimaat BV'),('Dekker Elektra BV'),('Hendriks Loodgieterij BV'),('Bos Warmte BV'),('Vos Projecten BV'),
('Scholten Bouwbedrijf BV'),('Timmermans Dakdekkers BV'),('Groen & Co BV'),('Wolters Montage BV'),('Hoekstra Installatie BV'),
('Van Beek Renovatie BV'),('Jacobs Bouwservice BV'),('Vermeer Technisch Beheer BV'),('Schouten Bouwmanagement BV'),('Kuijpers Totaal BV'),
('Willems Klimaattechniek BV'),('Post Installatietechniek BV'),('Kramer Bouw BV'),('Koster Service BV'),('Evers Onderhoud BV'),
('Zwart Projectontwikkeling BV'),('Van Loon Beheer BV'),('Verhoeven Techniek BV'),('Mol Vastgoedbeheer BV'),('Hermans Facility BV'),
('Dijkstra Installatiegroep BV'),('De Wit Engineering BV'),('De Graaf Bouwgroep BV'),('Van der Linden Beheer BV'),('Smeets Technisch BV');

-- Nederlandse straatnamen (30 stuks)
CREATE TEMPORARY TABLE _straatnamen (id serial, naam varchar(45));
INSERT INTO _straatnamen (naam) VALUES
('Kerkstraat'),('Dorpsstraat'),('Hoofdstraat'),('Molenweg'),('Stationsweg'),
('Industrieweg'),('Havenstraat'),('Marktplein'),('Schoolstraat'),('Nieuwstraat'),
('Julianastraat'),('Beatrixlaan'),('Wilhelminastraat'),('Oranjelaan'),('Burgemeesterstraat'),
('Parkweg'),('Bosweg'),('Rijnstraat'),('Maasstraat'),('Amstelweg'),
('Populierenlaan'),('Eikenlaan'),('Berkenlaan'),('Lindenlaan'),('Kastanjelaan'),
('Daalseweg'),('Herengracht'),('Prinsengracht'),('Keizersgracht'),('Singel');

-- Nederlandse plaatsnamen (30 stuks)
CREATE TEMPORARY TABLE _plaatsnamen (id serial, naam varchar(35));
INSERT INTO _plaatsnamen (naam) VALUES
('Amsterdam'),('Rotterdam'),('Utrecht'),('Den Haag'),('Eindhoven'),
('Tilburg'),('Groningen'),('Almere'),('Breda'),('Nijmegen'),
('Apeldoorn'),('Haarlem'),('Arnhem'),('Amersfoort'),('Zaanstad'),
('Den Bosch'),('Haarlemmermeer'),('Zwolle'),('Leiden'),('Maastricht'),
('Dordrecht'),('Ede'),('Emmen'),('Deventer'),('Delft'),
('Venlo'),('Helmond'),('Oss'),('Leeuwarden'),('Hilversum');

-- Postcodes (30 stuks, realistische Nederlandse formaten)
CREATE TEMPORARY TABLE _postcodes (id serial, code varchar(10));
INSERT INTO _postcodes (code) VALUES
('1011 AB'),('1017 CD'),('1071 EF'),('2511 GH'),('2514 IJ'),
('3011 KL'),('3511 MN'),('3512 OP'),('3521 QR'),('4811 ST'),
('5038 UV'),('5211 WX'),('5612 YZ'),('5616 AA'),('6211 BB'),
('6511 CC'),('6821 DD'),('7411 EE'),('7511 FF'),('7811 GG'),
('8011 HH'),('8911 II'),('9711 JJ'),('9726 KK'),('2312 LL'),
('4331 MM'),('5401 NN'),('6041 OO'),('7001 PP'),('8441 QQ');

-- Projectnamen (30 stuks)
CREATE TEMPORARY TABLE _projectnamen (id serial, naam varchar(80));
INSERT INTO _projectnamen (naam) VALUES
('Renovatie Kantoorpand'),('Nieuwbouw Bedrijfshal'),('Onderhoud Wooncomplex'),('Verduurzaming Schoolgebouw'),('Installatie Warmtepomp'),
('Vervanging CV-ketel'),('Dakisolatie Appartement'),('Airco Installatie Kantoor'),('Leidingwerk Ziekenhuis'),('Brandbeveiliging Parkeergarage'),
('Elektra Revisie Fabriek'),('Vloerverwarming Woonwijk'),('Zonnepanelen Bedrijfsterrein'),('Klimaatinstallatie Museum'),('Sprinkler Distributiecentrum'),
('Liftonderhoud Woontoren'),('Riolering Nieuwbouwwijk'),('Glasvezel Bedrijvenpark'),('Ventilatie Sporthal'),('Warmtenet Woonwijk'),
('Transformatorstation Upgrade'),('Koelinstallatie Supermarkt'),('Waterleiding Revitalisatie'),('Meterkast Renovatie'),('Verwarmingsinstallatie School'),
('Zwembad Techniek'),('Luchtbehandeling Ziekenhuis'),('Stadsverwarming Uitbreiding'),('Laadpalen Kantoorpand'),('Domotica Appartementencomplex');

-- Monteursnamen (20 stuks, combinatie voornaam + achternaam)
CREATE TEMPORARY TABLE _monteursnamen (id serial, naam varchar(80));
INSERT INTO _monteursnamen (naam) VALUES
('Jan de Vries'),('Pieter Bakker'),('Henk Visser'),('Willem Smit'),('Kees Meijer'),
('Dirk de Boer'),('Gerrit Mulder'),('Bas Jansen'),('Tom van Dijk'),('Sander Dekker'),
('Mark Brouwer'),('Erik de Wit'),('Paul Dijkstra'),('Frank Peters'),('Rob Hendriks'),
('Arjan Bos'),('Marcel Vos'),('Thijs Schouten'),('Daan Kuijpers'),('Lars Willems');


-- ============================================================
-- STAP 1: STAMTABELLEN (Master Data)
-- Kern van de anonimisatie - relaties, medewerkers, adressen
-- ============================================================

-- 1.1 stamrelaties - Alle klant/leverancier/debiteur/crediteur namen
UPDATE prepare.stamrelaties SET
    relatie = (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(stamrelaties.relatie, 40)),
    relatiekortenaam = LEFT((SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(stamrelaties.relatie, 40)), 10),
    fac_relatienaam = CASE WHEN fac_relatienaam IS NOT NULL AND fac_relatienaam != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(stamrelaties.fac_relatienaam, 40))
        ELSE fac_relatienaam END,
    pst_relatienaam = CASE WHEN pst_relatienaam IS NOT NULL AND pst_relatienaam != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(stamrelaties.pst_relatienaam, 40))
        ELSE pst_relatienaam END,
    bez_relatienaam = CASE WHEN bez_relatienaam IS NOT NULL AND bez_relatienaam != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(stamrelaties.bez_relatienaam, 40))
        ELSE bez_relatienaam END,
    email = CASE WHEN email IS NOT NULL AND email != ''
        THEN 'info@demo-' || abs(hashtext(email)) % 999 || '.nl'
        ELSE email END,
    url = CASE WHEN url IS NOT NULL AND url != ''
        THEN 'https://www.demo-' || abs(hashtext(url)) % 999 || '.nl'
        ELSE url END,
    kvknummer = CASE WHEN kvknummer IS NOT NULL AND kvknummer != ''
        THEN LPAD((abs(hashtext(kvknummer)) % 99999999)::text, 8, '0')
        ELSE kvknummer END,
    btwnummer = CASE WHEN btwnummer IS NOT NULL AND btwnummer != ''
        THEN 'NL' || LPAD((abs(hashtext(btwnummer)) % 999999999)::text, 9, '0') || 'B01'
        ELSE btwnummer END,
    vrij_veld_1 = CASE WHEN vrij_veld_1 IS NOT NULL AND vrij_veld_1 != ''
        THEN 'Demo veld ' || abs(hashtext(vrij_veld_1)) % 100
        ELSE vrij_veld_1 END;

-- 1.2 stamadministraties - Bedrijfsnamen/administratienamen
UPDATE prepare.stamadministraties SET
    administratie = 'Demo Administratie ' || LPAD(gc_id::text, 2, '0'),
    gc_korte_naam = CASE WHEN gc_korte_naam IS NOT NULL AND gc_korte_naam != ''
        THEN 'ADM' || LPAD(gc_id::text, 2, '0')
        ELSE gc_korte_naam END,
    opmerking_administratierelatie = CASE WHEN opmerking_administratierelatie IS NOT NULL AND opmerking_administratierelatie != ''
        THEN 'Demo opmerking'
        ELSE opmerking_administratierelatie END;

-- 1.3 stammedewerkers - Alle medewerker persoonsgegevens
UPDATE prepare.stammedewerkers SET
    medewerker = (SELECT naam FROM _voornamen WHERE id = prepare.anon_index(stammedewerkers.medewerker, 50))
        || ' '
        || (SELECT naam FROM _achternamen WHERE id = prepare.anon_index(stammedewerkers.achternaam || stammedewerkers.medewerkercode, 50)),
    roepnaam = (SELECT naam FROM _voornamen WHERE id = prepare.anon_index(stammedewerkers.roepnaam || stammedewerkers.medewerkercode, 50)),
    achternaam = (SELECT naam FROM _achternamen WHERE id = prepare.anon_index(stammedewerkers.achternaam || stammedewerkers.medewerkercode, 50)),
    voorvoegsel = CASE
        WHEN voorvoegsel IS NOT NULL AND voorvoegsel != '' THEN
            (ARRAY['van', 'de', 'van de', 'van der', 'van den'])[prepare.anon_index(voorvoegsel, 5)]
        ELSE voorvoegsel END,
    achtervoegsel = NULL,
    email = CASE WHEN email IS NOT NULL AND email != ''
        THEN 'medewerker' || medewerkerkey || '@demo-bedrijf.nl'
        ELSE email END,
    email_intern = CASE WHEN email_intern IS NOT NULL AND email_intern != ''
        THEN 'medewerker' || medewerkerkey || '@demo-intern.nl'
        ELSE email_intern END,
    straat = CASE WHEN straat IS NOT NULL AND straat != ''
        THEN (SELECT naam FROM _straatnamen WHERE id = prepare.anon_index(stammedewerkers.straat, 30))
        ELSE straat END,
    huis_nr = CASE WHEN huis_nr IS NOT NULL AND huis_nr != ''
        THEN (abs(hashtext(huis_nr)) % 200 + 1)::text
        ELSE huis_nr END,
    huis_nr_toevoeging = NULL,
    postcode = CASE WHEN postcode IS NOT NULL AND postcode != ''
        THEN (SELECT code FROM _postcodes WHERE id = prepare.anon_index(stammedewerkers.postcode, 30))
        ELSE postcode END,
    plaats = CASE WHEN plaats IS NOT NULL AND plaats != ''
        THEN (SELECT naam FROM _plaatsnamen WHERE id = prepare.anon_index(stammedewerkers.plaats, 30))
        ELSE plaats END,
    locatie = CASE WHEN locatie IS NOT NULL AND locatie != ''
        THEN 'Locatie ' || (abs(hashtext(locatie)) % 20 + 1)
        ELSE locatie END,
    modem = CASE WHEN modem IS NOT NULL AND modem != ''
        THEN '06-' || LPAD((abs(hashtext(modem)) % 99999999)::text, 8, '0')
        ELSE modem END,
    geboortedatum = CASE WHEN geboortedatum IS NOT NULL
        THEN '1980-01-01'::timestamp + (abs(hashtext(medewerkerkey::text)) % 7300 || ' days')::interval
        ELSE geboortedatum END;

-- 1.4 stampersonen - Persoonsgegevens
UPDATE prepare.stampersonen SET
    roepnaam = (SELECT naam FROM _voornamen WHERE id = prepare.anon_index(stampersonen.roepnaam || gc_id::text, 50)),
    voorvoegsel = CASE WHEN voorvoegsel IS NOT NULL AND voorvoegsel != ''
        THEN (ARRAY['van', 'de', 'van de', 'van der', 'van den'])[prepare.anon_index(voorvoegsel, 5)]
        ELSE voorvoegsel END,
    gc_korte_naam = CASE WHEN gc_korte_naam IS NOT NULL AND gc_korte_naam != ''
        THEN LEFT((SELECT naam FROM _achternamen WHERE id = prepare.anon_index(gc_korte_naam, 50)), 10)
        ELSE gc_korte_naam END,
    achtervoegsel = NULL,
    voorletters = CASE WHEN voorletters IS NOT NULL AND voorletters != ''
        THEN LEFT((SELECT naam FROM _voornamen WHERE id = prepare.anon_index(voorletters || gc_id::text, 50)), 1) || '.'
        ELSE voorletters END,
    voornamen = (SELECT naam FROM _voornamen WHERE id = prepare.anon_index(stampersonen.voornamen || gc_id::text, 50)),
    telefoon1 = CASE WHEN telefoon1 IS NOT NULL AND telefoon1 != ''
        THEN '010-' || LPAD((abs(hashtext(telefoon1)) % 9999999)::text, 7, '0')
        ELSE telefoon1 END,
    mobiel = CASE WHEN mobiel IS NOT NULL AND mobiel != ''
        THEN '06-' || LPAD((abs(hashtext(mobiel)) % 99999999)::text, 8, '0')
        ELSE mobiel END,
    email = CASE WHEN email IS NOT NULL AND email != ''
        THEN 'persoon' || gc_id || '@demo.nl'
        ELSE email END,
    geboortedatum = CASE WHEN geboortedatum IS NOT NULL
        THEN '1975-01-01'::timestamp + (abs(hashtext(gc_id::text)) % 10950 || ' days')::interval
        ELSE geboortedatum END;

-- 1.5 stamadressen - Alle adressen
UPDATE prepare.stamadressen SET
    straat = (SELECT naam FROM _straatnamen WHERE id = prepare.anon_index(stamadressen.straat || adreskey::text, 30)),
    huisnummer = (abs(hashtext(huisnummer || adreskey::text)) % 200 + 1)::text,
    huisnummertoevoeging = NULL,
    postcode = (SELECT code FROM _postcodes WHERE id = prepare.anon_index(stamadressen.postcode || adreskey::text, 30)),
    plaats = (SELECT naam FROM _plaatsnamen WHERE id = prepare.anon_index(stamadressen.plaats || adreskey::text, 30)),
    locatie = CASE WHEN locatie IS NOT NULL AND locatie != ''
        THEN 'Locatie ' || (abs(hashtext(locatie)) % 20 + 1)
        ELSE locatie END;

-- 1.6 stambedrijfseenheden
UPDATE prepare.stambedrijfseenheden SET
    bedrijfseenheid = 'Demo Eenheid ' || LPAD(bedrijfseenheidkey::text, 2, '0');

-- 1.7 stamafdelingen
UPDATE prepare.stamafdelingen SET
    afdeling = 'Afdeling ' || LPAD(afdelingkey::text, 2, '0'),
    afdeling_omschrijving = 'Demo afdeling ' || LPAD(afdelingkey::text, 2, '0'),
    administratie = 'Demo Administratie ' || LPAD(administratiekey::text, 2, '0');

-- 1.8 stambestellingen - Bestel/leverancier adressen
UPDATE prepare.stambestellingen SET
    relatienaam = CASE WHEN relatienaam IS NOT NULL AND relatienaam != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(relatienaam, 40))
        ELSE relatienaam END,
    tav = CASE WHEN tav IS NOT NULL AND tav != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(tav, 20))
        ELSE tav END,
    contactpersoon = CASE WHEN contactpersoon IS NOT NULL AND contactpersoon != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(contactpersoon, 20))
        ELSE contactpersoon END,
    straat = CASE WHEN straat IS NOT NULL AND straat != ''
        THEN (SELECT naam FROM _straatnamen WHERE id = prepare.anon_index(straat, 30))
        ELSE straat END,
    huis_nr = CASE WHEN huis_nr IS NOT NULL AND huis_nr != ''
        THEN (abs(hashtext(huis_nr)) % 200 + 1)::text
        ELSE huis_nr END,
    huis_nr_toevoeging = NULL,
    postcode = CASE WHEN postcode IS NOT NULL AND postcode != ''
        THEN (SELECT code FROM _postcodes WHERE id = prepare.anon_index(postcode, 30))
        ELSE postcode END,
    plaats = CASE WHEN plaats IS NOT NULL AND plaats != ''
        THEN (SELECT naam FROM _plaatsnamen WHERE id = prepare.anon_index(plaats, 30))
        ELSE plaats END,
    locatie = CASE WHEN locatie IS NOT NULL AND locatie != ''
        THEN 'Locatie ' || (abs(hashtext(locatie)) % 20 + 1)
        ELSE locatie END,
    notitie = CASE WHEN notitie IS NOT NULL AND notitie != ''
        THEN 'Demo notitie'
        ELSE notitie END,
    afleverinstructie = CASE WHEN afleverinstructie IS NOT NULL AND afleverinstructie != ''
        THEN 'Standaard levering'
        ELSE afleverinstructie END,
    extra_referentie = CASE WHEN extra_referentie IS NOT NULL AND extra_referentie != ''
        THEN 'REF-' || abs(hashtext(extra_referentie)) % 9999
        ELSE extra_referentie END,
    debiteur_nr = CASE WHEN debiteur_nr IS NOT NULL AND debiteur_nr != ''
        THEN 'D' || LPAD((abs(hashtext(debiteur_nr)) % 9999)::text, 4, '0')
        ELSE debiteur_nr END;

-- 1.9 stammicrosoftauthenticatie
UPDATE prepare.stammicrosoftauthenticatie SET
    email = 'user' || gc_id || '@demo-tenant.onmicrosoft.com',
    object_id = LPAD((abs(hashtext(object_id)) % 99999999)::text, 8, '0') || '-0000-0000-0000-000000000000',
    tenant_id = '00000000-0000-0000-0000-demo00000000',
    client_id = '00000000-0000-0000-0000-client000000';


-- ============================================================
-- STAP 2: DIMENSIE TABELLEN
-- ============================================================

-- 2.1 dimobjecten - Gebouwen/objecten met adres en contactgegevens
UPDATE prepare.dimobjecten SET
    object = 'Object ' || LPAD((abs(hashtext(object || gebouw_gc_id::text)) % 500 + 1)::text, 3, '0'),
    object_code = 'OBJ' || LPAD((abs(hashtext(object_code)) % 999)::text, 3, '0'),
    object_referentie = CASE WHEN object_referentie IS NOT NULL AND object_referentie != ''
        THEN 'REF' || LPAD((abs(hashtext(object_referentie)) % 999)::text, 3, '0')
        ELSE object_referentie END,
    straat = CASE WHEN straat IS NOT NULL AND straat != ''
        THEN (SELECT naam FROM _straatnamen WHERE id = prepare.anon_index(dimobjecten.straat, 30))
        ELSE straat END,
    huisnummer = CASE WHEN huisnummer IS NOT NULL AND huisnummer != ''
        THEN (abs(hashtext(huisnummer || gebouw_gc_id::text)) % 200 + 1)::text
        ELSE huisnummer END,
    huisnummertoevoeging = NULL,
    postcode = CASE WHEN postcode IS NOT NULL AND postcode != ''
        THEN (SELECT code FROM _postcodes WHERE id = prepare.anon_index(dimobjecten.postcode, 30))
        ELSE postcode END,
    plaats = CASE WHEN plaats IS NOT NULL AND plaats != ''
        THEN (SELECT naam FROM _plaatsnamen WHERE id = prepare.anon_index(dimobjecten.plaats, 30))
        ELSE plaats END,
    eigenaar = CASE WHEN eigenaar IS NOT NULL AND eigenaar != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(eigenaar, 40))
        ELSE eigenaar END,
    eigenaar_code = CASE WHEN eigenaar_code IS NOT NULL AND eigenaar_code != ''
        THEN 'EIG' || LPAD((abs(hashtext(eigenaar_code)) % 999)::text, 3, '0')
        ELSE eigenaar_code END,
    gebruiker = CASE WHEN gebruiker IS NOT NULL AND gebruiker != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(gebruiker, 40))
        ELSE gebruiker END,
    gebruiker_code = CASE WHEN gebruiker_code IS NOT NULL AND gebruiker_code != ''
        THEN 'GBR' || LPAD((abs(hashtext(gebruiker_code)) % 999)::text, 3, '0')
        ELSE gebruiker_code END,
    beheerder = CASE WHEN beheerder IS NOT NULL AND beheerder != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(beheerder, 40))
        ELSE beheerder END,
    beheerder_code = CASE WHEN beheerder_code IS NOT NULL AND beheerder_code != ''
        THEN 'BHR' || LPAD((abs(hashtext(beheerder_code)) % 999)::text, 3, '0')
        ELSE beheerder_code END,
    telefoon = CASE WHEN telefoon IS NOT NULL AND telefoon != ''
        THEN '010-' || LPAD((abs(hashtext(telefoon)) % 9999999)::text, 7, '0')
        ELSE telefoon END,
    mobiel = CASE WHEN mobiel IS NOT NULL AND mobiel != ''
        THEN '06-' || LPAD((abs(hashtext(mobiel)) % 99999999)::text, 8, '0')
        ELSE mobiel END,
    email = CASE WHEN email IS NOT NULL AND email != ''
        THEN 'object' || gebouw_gc_id || '@demo.nl'
        ELSE email END,
    contactpersoon = CASE WHEN contactpersoon IS NOT NULL AND contactpersoon != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(contactpersoon, 20))
        ELSE contactpersoon END,
    complexcode = CASE WHEN complexcode IS NOT NULL AND complexcode != ''
        THEN 'CX' || LPAD((abs(hashtext(complexcode)) % 99)::text, 2, '0')
        ELSE complexcode END;

-- 2.2 dimwerkbonnen - Werkbonnen met klant/monteur/adresgegevens
UPDATE prepare.dimwerkbonnen SET
    werkbon = 'Werkbon ' || LPAD(werkbondocumentkey::text, 6, '0'),
    hoofdwerkbon = CASE WHEN hoofdwerkbon IS NOT NULL AND hoofdwerkbon != ''
        THEN 'Hoofdwerkbon ' || LPAD(hoofdwerkbondocumentkey::text, 6, '0')
        ELSE hoofdwerkbon END,
    klant = CASE WHEN klant IS NOT NULL AND klant != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(klant, 40))
        ELSE klant END,
    debiteur = CASE WHEN debiteur IS NOT NULL AND debiteur != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(debiteur, 40))
        ELSE debiteur END,
    onderaannemer = CASE WHEN onderaannemer IS NOT NULL AND onderaannemer != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(onderaannemer, 40))
        ELSE onderaannemer END,
    monteur = CASE WHEN monteur IS NOT NULL AND monteur != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(monteur, 20))
        ELSE monteur END,
    contactpersoon = CASE WHEN contactpersoon IS NOT NULL AND contactpersoon != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(contactpersoon, 20))
        ELSE contactpersoon END,
    meldpersoon = CASE WHEN meldpersoon IS NOT NULL AND meldpersoon != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(meldpersoon, 20))
        ELSE meldpersoon END,
    relatienaam = CASE WHEN relatienaam IS NOT NULL AND relatienaam != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(relatienaam, 40))
        ELSE relatienaam END,
    ondertekenaar = CASE WHEN ondertekenaar IS NOT NULL AND ondertekenaar != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(ondertekenaar, 20))
        ELSE ondertekenaar END,
    email = CASE WHEN email IS NOT NULL AND email != ''
        THEN 'werkbon' || werkbondocumentkey || '@demo.nl'
        ELSE email END,
    plaats = CASE WHEN plaats IS NOT NULL AND plaats != ''
        THEN (SELECT naam FROM _plaatsnamen WHERE id = prepare.anon_index(plaats, 30))
        ELSE plaats END,
    postcode = CASE WHEN postcode IS NOT NULL AND postcode != ''
        THEN (SELECT code FROM _postcodes WHERE id = prepare.anon_index(postcode, 30))
        ELSE postcode END,
    werkorder = CASE WHEN werkorder IS NOT NULL AND werkorder != ''
        THEN 'WO-' || LPAD((abs(hashtext(werkorder)) % 99999)::text, 5, '0')
        ELSE werkorder END,
    inkoopnummer = CASE WHEN inkoopnummer IS NOT NULL AND inkoopnummer != ''
        THEN 'INK-' || LPAD((abs(hashtext(inkoopnummer)) % 99999)::text, 5, '0')
        ELSE inkoopnummer END,
    planreferentie = CASE WHEN planreferentie IS NOT NULL AND planreferentie != ''
        THEN 'PLAN-' || abs(hashtext(planreferentie)) % 9999
        ELSE planreferentie END,
    referentie = CASE WHEN referentie IS NOT NULL AND referentie != ''
        THEN 'REF' || LPAD((abs(hashtext(referentie)) % 999)::text, 3, '0')
        ELSE referentie END,
    referentie_2 = CASE WHEN referentie_2 IS NOT NULL AND referentie_2 != ''
        THEN 'RF2' || LPAD((abs(hashtext(referentie_2)) % 999)::text, 3, '0')
        ELSE referentie_2 END;

-- 2.3 dimprojecten - Projectnamen, opdrachtgevers, locaties
UPDATE prepare.dimprojecten SET
    project_titel = (SELECT naam FROM _projectnamen WHERE id = prepare.anon_index(project_titel, 30)),
    opdrachtgever = CASE WHEN opdrachtgever IS NOT NULL AND opdrachtgever != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(opdrachtgever, 40))
        ELSE opdrachtgever END,
    principaal = CASE WHEN principaal IS NOT NULL AND principaal != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(principaal, 40))
        ELSE principaal END,
    projectleider = CASE WHEN projectleider IS NOT NULL AND projectleider != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(projectleider, 20))
        ELSE projectleider END,
    werkgroep = CASE WHEN werkgroep IS NOT NULL AND werkgroep != ''
        THEN 'Werkgroep ' || (abs(hashtext(werkgroep)) % 10 + 1)
        ELSE werkgroep END,
    hoofdproject_werkgroep = CASE WHEN hoofdproject_werkgroep IS NOT NULL AND hoofdproject_werkgroep != ''
        THEN 'Werkgroep ' || (abs(hashtext(hoofdproject_werkgroep)) % 10 + 1)
        ELSE hoofdproject_werkgroep END,
    afdeling = CASE WHEN afdeling IS NOT NULL AND afdeling != ''
        THEN 'Afdeling ' || (abs(hashtext(afdeling)) % 10 + 1)
        ELSE afdeling END,
    postcode = CASE WHEN postcode IS NOT NULL AND postcode != ''
        THEN (SELECT code FROM _postcodes WHERE id = prepare.anon_index(postcode, 30))
        ELSE postcode END,
    plaats = CASE WHEN plaats IS NOT NULL AND plaats != ''
        THEN (SELECT naam FROM _plaatsnamen WHERE id = prepare.anon_index(plaats, 30))
        ELSE plaats END,
    referentie = CASE WHEN referentie IS NOT NULL AND referentie != ''
        THEN 'PRJ-' || LPAD((abs(hashtext(referentie)) % 9999)::text, 4, '0')
        ELSE referentie END,
    archief_nr = CASE WHEN archief_nr IS NOT NULL AND archief_nr != ''
        THEN 'ARC-' || LPAD((abs(hashtext(archief_nr)) % 9999)::text, 4, '0')
        ELSE archief_nr END;

-- dimprojecten: afgeleide velden (project, hoofdproject, etc.) worden
-- berekend in de prepare view (dimprojecten_v) via concat(project_code, ' - ', project_titel)
-- Dus project_titel aanpassen is voldoende als de view opnieuw wordt gelezen.
-- MAAR: als de materialized tabel ook project/hoofdproject bevat, die ook updaten:
UPDATE prepare.dimprojecten SET
    project = CASE WHEN project IS NOT NULL AND project != ''
        THEN project_code || ' - ' || project_titel
        ELSE project END,
    hoofdproject = CASE WHEN hoofdproject IS NOT NULL AND hoofdproject != ''
        THEN LEFT(hoofdproject, POSITION(' - ' IN hoofdproject) + 2) ||
            (SELECT naam FROM _projectnamen WHERE id = prepare.anon_index(hoofdproject, 30))
        ELSE hoofdproject END,
    niveau2project = CASE WHEN niveau2project IS NOT NULL AND niveau2project != ''
        THEN LEFT(niveau2project, POSITION(' - ' IN niveau2project) + 2) ||
            (SELECT naam FROM _projectnamen WHERE id = prepare.anon_index(niveau2project, 30))
        ELSE niveau2project END,
    niveau3project = CASE WHEN niveau3project IS NOT NULL AND niveau3project != ''
        THEN LEFT(niveau3project, POSITION(' - ' IN niveau3project) + 2) ||
            (SELECT naam FROM _projectnamen WHERE id = prepare.anon_index(niveau3project, 30))
        ELSE niveau3project END,
    niveau4project = CASE WHEN niveau4project IS NOT NULL AND niveau4project != ''
        THEN LEFT(niveau4project, POSITION(' - ' IN niveau4project) + 2) ||
            (SELECT naam FROM _projectnamen WHERE id = prepare.anon_index(niveau4project, 30))
        ELSE niveau4project END;

-- 2.4 dimabonnementen - Contracten/abonnementen
UPDATE prepare.dimabonnementen SET
    contactpersoon = CASE WHEN contactpersoon IS NOT NULL AND contactpersoon != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(contactpersoon, 20))
        ELSE contactpersoon END,
    serienummer = CASE WHEN serienummer IS NOT NULL AND serienummer != ''
        THEN 'SN-' || LPAD((abs(hashtext(serienummer)) % 999999)::text, 6, '0')
        ELSE serienummer END,
    externe_referentie = CASE WHEN externe_referentie IS NOT NULL AND externe_referentie != ''
        THEN 'EXT-' || LPAD((abs(hashtext(externe_referentie)) % 9999)::text, 4, '0')
        ELSE externe_referentie END;

-- 2.5 diminstallaties - Installatie referenties
UPDATE prepare.diminstallaties SET
    installatie = 'Installatie ' || LPAD(install_gc_id::text, 4, '0'),
    installatiecode = 'INS' || LPAD((abs(hashtext(installatiecode)) % 9999)::text, 4, '0'),
    installatiereferentie = CASE WHEN installatiereferentie IS NOT NULL AND installatiereferentie != ''
        THEN 'IREF-' || LPAD((abs(hashtext(installatiereferentie)) % 9999)::text, 4, '0')
        ELSE installatiereferentie END,
    serienummer = CASE WHEN serienummer IS NOT NULL AND serienummer != ''
        THEN 'SN-' || LPAD((abs(hashtext(serienummer)) % 999999)::text, 6, '0')
        ELSE serienummer END,
    locatie = CASE WHEN locatie IS NOT NULL AND locatie != ''
        THEN 'Locatie ' || (abs(hashtext(locatie)) % 20 + 1)
        ELSE locatie END,
    geplaatst_door = CASE WHEN geplaatst_door IS NOT NULL AND geplaatst_door != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(geplaatst_door, 40))
        ELSE geplaatst_door END;

-- 2.6 diminstallatiecomponenten
UPDATE prepare.diminstallatiecomponenten SET
    gc_omschrijving = CASE WHEN gc_omschrijving IS NOT NULL AND gc_omschrijving != ''
        THEN 'Component ' || gc_id
        ELSE gc_omschrijving END,
    serie_nr = CASE WHEN serie_nr IS NOT NULL AND serie_nr != ''
        THEN 'SN-' || LPAD((abs(hashtext(serie_nr)) % 999999)::text, 6, '0')
        ELSE serie_nr END,
    locatie = CASE WHEN locatie IS NOT NULL AND locatie != ''
        THEN 'Locatie ' || (abs(hashtext(locatie)) % 20 + 1)
        ELSE locatie END,
    vrij_merktype = CASE WHEN vrij_merktype IS NOT NULL AND vrij_merktype != ''
        THEN 'Type ' || (abs(hashtext(vrij_merktype)) % 50 + 1)
        ELSE vrij_merktype END,
    verdieping = CASE WHEN verdieping IS NOT NULL AND verdieping != ''
        THEN 'Verd. ' || (abs(hashtext(verdieping)) % 10)
        ELSE verdieping END;

-- 2.7 dimmagazijnen
UPDATE prepare.dimmagazijnen SET
    magazijn = 'Magazijn ' || LPAD(magazijnkey::text, 3, '0');


-- ============================================================
-- STAP 3: FACT TABELLEN - Financieel
-- ============================================================

-- 3.1 factverkoopfactuurtermijnen - Debiteur + adres
UPDATE prepare.factverkoopfactuurtermijnen SET
    debiteur = CASE WHEN debiteur IS NOT NULL AND debiteur != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(debiteur, 40))
        ELSE debiteur END,
    straat = CASE WHEN straat IS NOT NULL AND straat != ''
        THEN (SELECT naam FROM _straatnamen WHERE id = prepare.anon_index(straat, 30))
        ELSE straat END,
    huisnummer = CASE WHEN huisnummer IS NOT NULL AND huisnummer != ''
        THEN (abs(hashtext(huisnummer || uniekeid::text)) % 200 + 1)::text
        ELSE huisnummer END,
    huisnummertoevoeging = NULL,
    postcode = CASE WHEN postcode IS NOT NULL AND postcode != ''
        THEN (SELECT code FROM _postcodes WHERE id = prepare.anon_index(postcode, 30))
        ELSE postcode END,
    plaats = CASE WHEN plaats IS NOT NULL AND plaats != ''
        THEN (SELECT naam FROM _plaatsnamen WHERE id = prepare.anon_index(plaats, 30))
        ELSE plaats END;

-- 3.2 factinkoopfactuurtermijnen - Crediteur
UPDATE prepare.factinkoopfactuurtermijnen SET
    crediteur = CASE WHEN crediteur IS NOT NULL AND crediteur != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(crediteur, 40))
        ELSE crediteur END;

-- 3.3 factbetalingperopbrengstregel - Debiteur
UPDATE prepare.factbetalingperopbrengstregel SET
    debiteur = CASE WHEN debiteur IS NOT NULL AND debiteur != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(debiteur, 40))
        ELSE debiteur END;

-- 3.4 factbetalingperinkoopregel - Crediteur
UPDATE prepare.factbetalingperinkoopregel SET
    crediteur = CASE WHEN crediteur IS NOT NULL AND crediteur != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(crediteur, 40))
        ELSE crediteur END,
    crediteur_code = CASE WHEN crediteur_code IS NOT NULL AND crediteur_code != ''
        THEN 'C' || LPAD((abs(hashtext(crediteur_code)) % 9999)::text, 4, '0')
        ELSE crediteur_code END;

-- 3.5 factopbrengsten - Debiteur met adres
UPDATE prepare.factopbrengsten SET
    debiteur = CASE WHEN debiteur IS NOT NULL AND debiteur != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(debiteur, 40))
        ELSE debiteur END,
    debiteurcode = CASE WHEN debiteurcode IS NOT NULL AND debiteurcode != ''
        THEN 'D' || LPAD((abs(hashtext(debiteurcode)) % 9999)::text, 4, '0')
        ELSE debiteurcode END,
    debiteurbezoekadres = CASE WHEN debiteurbezoekadres IS NOT NULL AND debiteurbezoekadres != ''
        THEN (SELECT naam FROM _straatnamen WHERE id = prepare.anon_index(debiteurbezoekadres, 30)) || ' ' || (abs(hashtext(debiteurbezoekadres)) % 200 + 1)
        ELSE debiteurbezoekadres END,
    debiteurbezoekpostcode = CASE WHEN debiteurbezoekpostcode IS NOT NULL AND debiteurbezoekpostcode != ''
        THEN (SELECT code FROM _postcodes WHERE id = prepare.anon_index(debiteurbezoekpostcode, 30))
        ELSE debiteurbezoekpostcode END,
    debiteurbezoekplaats = CASE WHEN debiteurbezoekplaats IS NOT NULL AND debiteurbezoekplaats != ''
        THEN (SELECT naam FROM _plaatsnamen WHERE id = prepare.anon_index(debiteurbezoekplaats, 30))
        ELSE debiteurbezoekplaats END,
    omschrijving = CASE WHEN omschrijving IS NOT NULL AND omschrijving != ''
        THEN 'Opbrengstregel ' || gc_id
        ELSE omschrijving END;

-- 3.6 factjournaalregels - Omschrijving (kan namen bevatten)
UPDATE prepare.factjournaalregels SET
    omschrijving = CASE WHEN omschrijving IS NOT NULL AND omschrijving != ''
        THEN 'Boeking ' || gc_id
        ELSE omschrijving END;

-- 3.7 factkosten - Omschrijving en document_titel
UPDATE prepare.factkosten SET
    omschrijving = CASE WHEN omschrijving IS NOT NULL AND omschrijving != ''
        THEN 'Kostenregel ' || gc_id
        ELSE omschrijving END,
    document_titel = CASE WHEN document_titel IS NOT NULL AND document_titel != ''
        THEN 'Document ' || document_gc_id
        ELSE document_titel END;

-- 3.8 factbankafschriftboekingregels
UPDATE prepare.factbankafschriftboekingregels SET
    omschrijving = CASE WHEN omschrijving IS NOT NULL AND omschrijving != ''
        THEN 'Bankregel ' || gc_id
        ELSE omschrijving END,
    iban_eigen_bedrijf = CASE WHEN iban_eigen_bedrijf IS NOT NULL AND iban_eigen_bedrijf != ''
        THEN 'NL00DEMO' || LPAD((abs(hashtext(iban_eigen_bedrijf)) % 9999999999)::text, 10, '0')
        ELSE iban_eigen_bedrijf END,
    factuur_document_titel = CASE WHEN factuur_document_titel IS NOT NULL AND factuur_document_titel != ''
        THEN 'Factuur ' || fac_document_gc_id
        ELSE factuur_document_titel END,
    bankafschrift_titel = CASE WHEN bankafschrift_titel IS NOT NULL AND bankafschrift_titel != ''
        THEN 'Bankafschrift ' || document_gc_id
        ELSE bankafschrift_titel END;

-- 3.9 factbankregels
UPDATE prepare.factbankregels SET
    gc_omschrijving = CASE WHEN gc_omschrijving IS NOT NULL AND gc_omschrijving != ''
        THEN 'Bankregel ' || gc_id
        ELSE gc_omschrijving END,
    document_titel = CASE WHEN document_titel IS NOT NULL AND document_titel != ''
        THEN 'Bankdocument ' || document_gc_id
        ELSE document_titel END;

-- 3.10 facteliminatiejournaalregels
UPDATE prepare.facteliminatiejournaalregels SET
    versturende_administratie = CASE WHEN versturende_administratie IS NOT NULL AND versturende_administratie != ''
        THEN 'Demo Administratie A'
        ELSE versturende_administratie END,
    ontvangende_administratie = CASE WHEN ontvangende_administratie IS NOT NULL AND ontvangende_administratie != ''
        THEN 'Demo Administratie B'
        ELSE ontvangende_administratie END,
    administratie_relatie = CASE WHEN administratie_relatie IS NOT NULL AND administratie_relatie != ''
        THEN 'Demo A -> Demo B'
        ELSE administratie_relatie END,
    inkoopfactuur_referentie = CASE WHEN inkoopfactuur_referentie IS NOT NULL AND inkoopfactuur_referentie != ''
        THEN 'IKF-' || abs(hashtext(inkoopfactuur_referentie)) % 9999
        ELSE inkoopfactuur_referentie END,
    document = CASE WHEN document IS NOT NULL AND document != ''
        THEN 'Eliminatie doc ' || documentkey
        ELSE document END;


-- ============================================================
-- STAP 4: FACT TABELLEN - Operationeel
-- ============================================================

-- 4.1 factacties - Contactgegevens
UPDATE prepare.factacties SET
    contactpersoon = CASE WHEN contactpersoon IS NOT NULL AND contactpersoon != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(contactpersoon, 20))
        ELSE contactpersoon END,
    telefoon = CASE WHEN telefoon IS NOT NULL AND telefoon != ''
        THEN '010-' || LPAD((abs(hashtext(telefoon)) % 9999999)::text, 7, '0')
        ELSE telefoon END,
    mobiel = CASE WHEN mobiel IS NOT NULL AND mobiel != ''
        THEN '06-' || LPAD((abs(hashtext(mobiel)) % 99999999)::text, 8, '0')
        ELSE mobiel END;

-- 4.2 factmobieleuitvoersessies - Ondertekenaar + email
UPDATE prepare.factmobieleuitvoersessies SET
    ondertekenaar = CASE WHEN ondertekenaar IS NOT NULL AND ondertekenaar != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(ondertekenaar, 20))
        ELSE ondertekenaar END,
    email = CASE WHEN email IS NOT NULL AND email != ''
        THEN 'sessie' || gc_id || '@demo.nl'
        ELSE email END;

-- 4.3 factcalculatiekostenregels - Calculator en omschrijvingen
UPDATE prepare.factcalculatiekostenregels SET
    calculator = CASE WHEN calculator IS NOT NULL AND calculator != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(calculator, 20))
        ELSE calculator END,
    regel_omschrijving = CASE WHEN regel_omschrijving IS NOT NULL AND regel_omschrijving != ''
        THEN 'Calculatieregel ' || calculatieregelkey
        ELSE regel_omschrijving END,
    handelsartikel_leverancier = CASE WHEN handelsartikel_leverancier IS NOT NULL AND handelsartikel_leverancier != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(handelsartikel_leverancier, 40))
        ELSE handelsartikel_leverancier END;

-- 4.4 factdocumentparafeermedewerkers
UPDATE prepare.factdocumentparafeermedewerkers SET
    opmerking = CASE WHEN opmerking IS NOT NULL AND opmerking != ''
        THEN 'Demo opmerking'
        ELSE opmerking END,
    bijzonderheden = CASE WHEN bijzonderheden IS NOT NULL AND bijzonderheden != ''
        THEN 'Demo bijzonderheden'
        ELSE bijzonderheden END;

-- 4.5 factmedewerkerverzuim
UPDATE prepare.factmedewerkerverzuim SET
    omschrijving = CASE WHEN omschrijving IS NOT NULL AND omschrijving != ''
        THEN 'Verzuim ' || verzuimregelkey
        ELSE omschrijving END;

-- 4.6 factsalarishistorie
UPDATE prepare.factsalarishistorie SET
    omschrijving = CASE WHEN omschrijving IS NOT NULL AND omschrijving != ''
        THEN 'Salariswijziging ' || gc_id
        ELSE omschrijving END;

-- 4.7 factopvolgingen
UPDATE prepare.factopvolgingen SET
    beschrijving = CASE WHEN beschrijving IS NOT NULL AND beschrijving != ''
        THEN 'Opvolging ' || gc_id
        ELSE beschrijving END;

-- 4.8 factofferteregels
UPDATE prepare.factofferteregels SET
    omschrijving = CASE WHEN omschrijving IS NOT NULL AND omschrijving != ''
        THEN 'Offerteregel ' || gc_id
        ELSE omschrijving END;

-- 4.9 factwerkbonchecklistregels - Antwoorden kunnen namen bevatten
UPDATE prepare.factwerkbonchecklistregels SET
    antwoord = CASE WHEN antwoord IS NOT NULL AND antwoord != ''
        THEN 'Demo antwoord'
        ELSE antwoord END;


-- ============================================================
-- STAP 5: FACT TABELLEN - Orders & Handel
-- ============================================================

-- 5.1 facthandelorders
UPDATE prepare.facthandelorders SET
    document_titel = CASE WHEN document_titel IS NOT NULL AND document_titel != ''
        THEN 'Order ' || document_gc_id
        ELSE document_titel END,
    orderregelomschrijving = CASE WHEN orderregelomschrijving IS NOT NULL AND orderregelomschrijving != ''
        THEN 'Orderregel ' || gc_id
        ELSE orderregelomschrijving END;

-- 5.2 factorderseenmalig
UPDATE prepare.factorderseenmalig SET
    document_titel = CASE WHEN document_titel IS NOT NULL AND document_titel != ''
        THEN 'Eenmalige order ' || document_gc_id
        ELSE document_titel END,
    orderregelomschrijving = CASE WHEN orderregelomschrijving IS NOT NULL AND orderregelomschrijving != ''
        THEN 'Orderregel ' || gc_id
        ELSE orderregelomschrijving END;

-- 5.3 factserviceordersprognose
UPDATE prepare.factserviceordersprognose SET
    document_titel = CASE WHEN document_titel IS NOT NULL AND document_titel != ''
        THEN 'Serviceorder ' || document_gc_id
        ELSE document_titel END,
    orderregelomschrijving = CASE WHEN orderregelomschrijving IS NOT NULL AND orderregelomschrijving != ''
        THEN 'Orderregel ' || gc_id
        ELSE orderregelomschrijving END;

-- 5.4 factbestelregels
UPDATE prepare.factbestelregels SET
    omschrijving = CASE WHEN omschrijving IS NOT NULL AND omschrijving != ''
        THEN 'Bestelregel ' || bestelregelkey
        ELSE omschrijving END;

-- 5.5 factbestelverzoekregels
UPDATE prepare.factbestelverzoekregels SET
    gc_omschrijving = CASE WHEN gc_omschrijving IS NOT NULL AND gc_omschrijving != ''
        THEN 'Bestelverzoek ' || gc_id
        ELSE gc_omschrijving END;

-- 5.6 factmaterieeluitgiftes
UPDATE prepare.factmaterieeluitgiftes SET
    omschrijving = CASE WHEN omschrijving IS NOT NULL AND omschrijving != ''
        THEN 'Materieel uitgifte ' || materieeluitgifteregelkey
        ELSE omschrijving END;


-- ============================================================
-- STAP 6: FACT TABELLEN - Planning & Medewerkers
-- ============================================================

-- 6.1 factplanbaremedewerkers - Bevat volledige persoonsgegevens
UPDATE prepare.factplanbaremedewerkers SET
    medewerker = (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(medewerker, 20)),
    roepnaam = (SELECT naam FROM _voornamen WHERE id = prepare.anon_index(roepnaam || medewerkerkey::text, 50)),
    achternaam = (SELECT naam FROM _achternamen WHERE id = prepare.anon_index(achternaam || medewerkerkey::text, 50)),
    voorvoegsel = CASE WHEN voorvoegsel IS NOT NULL AND voorvoegsel != ''
        THEN (ARRAY['van', 'de', 'van de', 'van der', 'van den'])[prepare.anon_index(voorvoegsel, 5)]
        ELSE voorvoegsel END,
    achtervoegsel = NULL,
    samengestelde_naam = CASE WHEN samengestelde_naam IS NOT NULL AND samengestelde_naam != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(samengestelde_naam, 20))
        ELSE samengestelde_naam END,
    relatie = CASE WHEN relatie IS NOT NULL AND relatie != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(relatie, 40))
        ELSE relatie END;

-- 6.2 factplanningurenmedewerkers
UPDATE prepare.factplanningurenmedewerkers SET
    volledige_naam = CASE WHEN volledige_naam IS NOT NULL AND volledige_naam != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(volledige_naam, 20))
        ELSE volledige_naam END;


-- ============================================================
-- STAP 7: EXTRA TABELLEN
-- ============================================================

-- 7.1 extrabijzondererelaties
UPDATE prepare.extrabijzondererelaties SET
    relatie = CASE WHEN relatie IS NOT NULL AND relatie != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(relatie, 40))
        ELSE relatie END,
    relatie_code = CASE WHEN relatie_code IS NOT NULL AND relatie_code != ''
        THEN 'REL' || LPAD((abs(hashtext(relatie_code)) % 9999)::text, 4, '0')
        ELSE relatie_code END,
    filepath = CASE WHEN filepath IS NOT NULL AND filepath != ''
        THEN '/demo/relaties/' || relatiekey || '.pdf'
        ELSE filepath END;

-- 7.2 extrabudgetverzoeken
UPDATE prepare.extrabudgetverzoeken SET
    aanmaker = CASE WHEN aanmaker IS NOT NULL AND aanmaker != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(aanmaker, 20))
        ELSE aanmaker END,
    wijziger = CASE WHEN wijziger IS NOT NULL AND wijziger != ''
        THEN (SELECT naam FROM _monteursnamen WHERE id = prepare.anon_index(wijziger, 20))
        ELSE wijziger END,
    klantnaam = CASE WHEN klantnaam IS NOT NULL AND klantnaam != ''
        THEN (SELECT naam FROM _bedrijfsnamen WHERE id = prepare.anon_index(klantnaam, 40))
        ELSE klantnaam END,
    project = CASE WHEN project IS NOT NULL AND project != ''
        THEN (SELECT naam FROM _projectnamen WHERE id = prepare.anon_index(project, 30))
        ELSE project END,
    opmerking = CASE WHEN opmerking IS NOT NULL AND opmerking != ''
        THEN 'Demo opmerking budgetverzoek'
        ELSE opmerking END;


-- ============================================================
-- STAP 8: STAM DOCUMENT TABELLEN
-- ============================================================

-- 8.1 stamdocumenten - Document titels kunnen klantnamen bevatten
UPDATE prepare.stamdocumenten SET
    document_titel = CASE WHEN document_titel IS NOT NULL AND document_titel != ''
        THEN 'Document ' || documentkey
        ELSE document_titel END;

-- 8.2 stamoffertes
UPDATE prepare.stamoffertes SET
    offerte_omschrijving = CASE WHEN offerte_omschrijving IS NOT NULL AND offerte_omschrijving != ''
        THEN 'Offerte ' || document_gc_id
        ELSE NULL END;

-- 8.3 stamorders - Ordertitels
UPDATE prepare.stamorders SET
    document_titel = CASE WHEN document_titel IS NOT NULL AND document_titel != ''
        THEN 'Order ' || document_gc_id
        ELSE document_titel END;

-- 8.4 stamorderregels
UPDATE prepare.stamorderregels SET
    orderregelomschrijving = CASE WHEN orderregelomschrijving IS NOT NULL AND orderregelomschrijving != ''
        THEN 'Orderregel ' || gc_id
        ELSE orderregelomschrijving END;

-- 8.5 stamprojecttaken
UPDATE prepare.stamprojecttaken SET
    administratie = CASE WHEN administratie IS NOT NULL AND administratie != ''
        THEN 'Demo Administratie ' || administratiekey
        ELSE administratie END;


-- ============================================================
-- STAP 9: WERKBON DETAIL TABELLEN
-- ============================================================

-- 9.1 dimwerkbonparagrafen - Factuurtekst kan namen bevatten
UPDATE prepare.dimwerkbonparagrafen SET
    factuurtekst = CASE WHEN factuurtekst IS NOT NULL AND factuurtekst != ''
        THEN 'Factuurtekst werkbonparagraaf ' || werkbonparagraafkey
        ELSE factuurtekst END;

-- 9.2 dimwerkbonoplossingen
UPDATE prepare.dimwerkbonoplossingen SET
    oplossing_uitgebreid = CASE WHEN oplossing_uitgebreid IS NOT NULL AND oplossing_uitgebreid != ''
        THEN 'Oplossing ' || oplossingkey
        ELSE oplossing_uitgebreid END;

-- 9.3 dimbestekparagrafen - Bestekparagraaf omschrijvingen
UPDATE prepare.dimbestekparagrafen SET
    bestekparagraaf = CASE WHEN bestekparagraaf IS NOT NULL AND bestekparagraaf != ''
        THEN 'Bestekparagraaf ' || gc_id
        ELSE bestekparagraaf END,
    bestekparagraaf_samengevoegd = CASE WHEN bestekparagraaf_samengevoegd IS NOT NULL AND bestekparagraaf_samengevoegd != ''
        THEN bestekparagraafcode || ' - Bestekparagraaf ' || gc_id
        ELSE bestekparagraaf_samengevoegd END;


-- ============================================================
-- STAP 10: OPRUIMEN
-- ============================================================

-- Verwijder helper functie
DROP FUNCTION IF EXISTS prepare.anon_index(text, int);

-- Tijdelijke tabellen worden automatisch opgeruimd bij disconnect
-- Maar voor de zekerheid:
DROP TABLE IF EXISTS _voornamen;
DROP TABLE IF EXISTS _achternamen;
DROP TABLE IF EXISTS _bedrijfsnamen;
DROP TABLE IF EXISTS _straatnamen;
DROP TABLE IF EXISTS _plaatsnamen;
DROP TABLE IF EXISTS _postcodes;
DROP TABLE IF EXISTS _projectnamen;
DROP TABLE IF EXISTS _monteursnamen;

-- ============================================================
-- KLAAR!
-- Alle klantgevoelige tekstuele data is geanonimiseerd.
-- Financiele bedragen zijn INTACT gebleven.
-- De endviews (SSM-laag) tonen nu automatisch de demodata.
-- ============================================================
