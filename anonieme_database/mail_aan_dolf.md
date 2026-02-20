# Concept-mail aan Dolf

**Onderwerp:** Verzoek: database 1225 klonen via GRIP voor demo-omgeving

---

Hoi Dolf,

Ik wil een geanonimiseerde demo-database opzetten zodat we rapporten en dashboards veilig kunnen laten zien aan prospects en bij demo's, zonder dat er echte klantdata zichtbaar is.

**Wat heb ik van jou nodig?**

Kun je via GRIP een kopie (kloon) maken van database **1225** naar een nieuwe database, bijvoorbeeld `demo_1225`? Dezelfde server is prima (10.3.152.9).

**Wat doe ik daarna?**

Ik heb een anonimisatiescript gebouwd dat alle klantgevoelige tekst in de prepare-tabellen vervangt door realistische Nederlandse demodata:

- Alle klant-, leverancier- en persoonsnamen → fictieve Nederlandse namen
- Alle adressen → fictieve Nederlandse adressen
- E-mailadressen, telefoonnummers, KvK/BTW-nummers → fictieve waarden
- Projectnamen, werkbonomschrijvingen → generieke demo-omschrijvingen

Financiele bedragen en datums blijven intact, zodat de rapporten er realistisch uitzien.

Omdat de endviews (SSM-laag) views zijn op de prepare-tabellen, toont alles automatisch de geanonimiseerde data. Ik koppel daar vervolgens een Power BI semantisch model aan voor de demo-rapporten.

**Bestanden**

Ik heb de scripts en documentatie in de SharePoint gezet:
📁 `Sharepoint Notifica intern > 113. Dolf > anonieme_database`

Daar vind je:
- `README.md` — volledige uitleg van de aanpak en alle tabellen die worden aangepast
- `anonymization.sql` — het SQL-script met alle UPDATE-statements
- `anonymize_demo.py` — Python wrapper om het geheel in één keer te draaien
- `verify_anonymization.sql` — steekproef-queries om te controleren of alles is geanonimiseerd

**Samengevat**

Het enige wat ik van jou nodig heb is de gekloonde database. De rest (anonimiseren, semantisch model, rapporten koppelen) doe ik zelf.

Kun je me laten weten wanneer de kloon beschikbaar is?

Groet,
Tobias
