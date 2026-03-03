"""
Backfill webinar aanmelders — eenmalig script
=============================================
- Zet LEADSTATUS='Webinar' in EmailOctopus voor alle bekende aanmelders
- Maakt Pipedrive deal aan in stage 'Webinar aangemeld' (ID 70) als er nog geen deal is
- Schrijft resultaten naar docs/backfill_webinar_resultaat.md
"""
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

EMAILOCTOPUS_API_KEY = os.getenv("EMAILOCTOPUS_API_KEY")
EMAILOCTOPUS_LIST_ID = "729f9b7e-12ec-11f1-acfe-6b0432c704d7"
EMAILOCTOPUS_BASE = "https://emailoctopus.com/api/1.6"
PIPEDRIVE_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
PIPEDRIVE_BASE = "https://notifica.pipedrive.com/api/v1"
WEBINAR_STAGE_ID = 70  # 'Webinar aangemeld' - nieuw aangemaakt

# ── Lijst van bekende webinar-aanmelders (uit Formspree export) ──────────────
# Formaat: (naam, email, bedrijf)
WEBINAR_REGISTRATIONS = [
    # Webinar-4 (27 maart 2026)
    ("Jeroen Stoorvogel",   "jeroen.stoorvogel@desservice.nl",      "DES Service en Onderhoud"),
    ("Lucien Jilissen",     "l.jilissen@rensen.nu",                  "Rensen"),
    # Webinar-3 (27 februari 2026)
    ("Wouter de Does",      "wouter@k-b-e.nl",                       "Knipmeijers & Blok elektrotechniek"),
    ("Bert van Rooij",      "b.vanrooij@vandenbroek-oss.nl",         "Van den Broek Systemen"),
    ("Marianne Blesing",    "marianne.blesing@k-b-e.nl",             "Knipmeijers & Blok elektrotechniek"),
    ("Jac van Stratum",     "j.v.stratum@vanstratum.nl",             "Van Stratum Techniek B.V."),
    ("Kevin Meeuwis",       "kmeeuwis@outlook.com",                  "Alwako"),
    ("Kevin Meeuwis",       "k.meeuwis@alwako.nl",                   "Alwako"),
    ("Jaron Wijten",        "jaron.wijten@van-hout.com",             "Van Hout adviseurs & installateurs"),
    ("Fabian Geerlings",    "fabian@installatiebedrijfloeffen.nl",   "Installatiebedrijf Loeffen"),
    ("Danielle van de Beeten", "danielle@installatiebedrijfloeffen.nl", "Installatiebedrijf Loeffen"),
    ("Benjamin van Beek",   "b.van.beek@delaat.nl",                  "De Laat Koudetechniek"),
    ("Raymond Netten",      "r.netten@vanhees.com",                  "Van Hees"),
    ("Hein Hogenhout",      "hein.hogenhout@veld.nl",                "Veld Koeltechniek"),
    ("Roald Bissels",       "rbissels@gacom.nl",                     ""),
    ("Cisca Poelgeest",     "c.poelgeest@sos-snelservice.nl",        "SOS Snelservice BV"),
    ("Patrick Dutour",      "p.dutour@zenithsecurity.nl",            "Zenith Security"),
    ("Nick Keijzer",        "nick.keijzer@hotmail.com",              "Feiken Verwarming"),
    ("Steven Holsappel",    "sholsappel@hartmaninstallatie.nl",      "Hartman Installatie"),
    ("Jan Post",            "service@hartmaninstallatie.nl",         "Hartman Installatie"),
    ("Tim Adema",           "t.adema@royalvanderleun.com",           "Royal Van der Leun"),
    ("Vehbi Yildirim",      "vyildirim@feenstra.com",                "Feenstra"),
    ("Jeroen Feiken",       "jeroen@feikencv.nl",                    "Feiken Verwarming"),
    ("Michiel Gersjes",     "m.gersjes@vanhees.com",                 "Electro-techniek van Hees BV"),
    # Stuurinformatie webinar (jan/feb 2026)
    ("Mark Lenferink",      "m.lenferink@loohuisgroep.nl",           "Loohuis"),
    ("Stefan van Maasakkers", "s.maasakkers@boladviseurs.nl",        "Bol Adviseurs"),
    ("Stefan Heeg",         "s.heeg@sandee.nl",                      "Sandee Groen"),
]


# ── EmailOctopus helpers ─────────────────────────────────────────────────────

def eo_get_all_contacts():
    """Laad alle subscribers als {email: contact_id} dict."""
    mapping = {}
    page = 1
    while True:
        r = requests.get(f"{EMAILOCTOPUS_BASE}/lists/{EMAILOCTOPUS_LIST_ID}/contacts",
                         params={"api_key": EMAILOCTOPUS_API_KEY, "limit": 100, "page": page},
                         timeout=30)
        batch = r.json().get("data", [])
        if not batch:
            break
        for sub in batch:
            mapping[sub["email_address"].lower()] = sub["id"]
        if not r.json().get("paging", {}).get("next"):
            break
        page += 1
    return mapping


def eo_update_contact(contact_id, name, company):
    """Zet LEADSTATUS=Webinar op bestaand contact."""
    parts = name.strip().split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    r = requests.put(
        f"{EMAILOCTOPUS_BASE}/lists/{EMAILOCTOPUS_LIST_ID}/contacts/{contact_id}",
        json={"api_key": EMAILOCTOPUS_API_KEY,
              "fields": {"LEADSTATUS": "Webinar", "FirstName": first, "LastName": last,
                         "COMPANY": company}},
        timeout=15)
    return r.status_code, r.json()


def eo_create_contact(name, email, company):
    """Maak nieuw contact aan met LEADSTATUS=Webinar."""
    parts = name.strip().split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    r = requests.post(
        f"{EMAILOCTOPUS_BASE}/lists/{EMAILOCTOPUS_LIST_ID}/contacts",
        json={"api_key": EMAILOCTOPUS_API_KEY,
              "email_address": email.lower(),
              "status": "SUBSCRIBED",
              "fields": {"FirstName": first, "LastName": last,
                         "COMPANY": company, "LEADSTATUS": "Webinar"}},
        timeout=15)
    return r.status_code, r.json()


# ── Pipedrive helpers ────────────────────────────────────────────────────────

def pd_find_person(email):
    r = requests.get(f"{PIPEDRIVE_BASE}/persons/search",
                     params={"api_token": PIPEDRIVE_TOKEN, "term": email,
                             "fields": "email", "exact_match": "true"},
                     timeout=15)
    items = r.json().get("data", {}).get("items", []) or []
    return items[0]["item"] if items else None


def pd_create_person(name, email, company):
    # Zoek of maak org
    org_id = None
    if company:
        sr = requests.get(f"{PIPEDRIVE_BASE}/organizations/search",
                          params={"api_token": PIPEDRIVE_TOKEN, "term": company,
                                  "exact_match": "false", "limit": 3},
                          timeout=15)
        for item in (sr.json().get("data", {}).get("items") or []):
            if company.lower()[:6] in item["item"]["name"].lower():
                org_id = item["item"]["id"]
                break
        if not org_id:
            cr = requests.post(f"{PIPEDRIVE_BASE}/organizations",
                               params={"api_token": PIPEDRIVE_TOKEN},
                               json={"name": company}, timeout=15)
            org_id = cr.json().get("data", {}).get("id")

    body = {"name": name, "email": [{"value": email, "primary": True}]}
    if org_id:
        body["org_id"] = org_id
    r = requests.post(f"{PIPEDRIVE_BASE}/persons",
                      params={"api_token": PIPEDRIVE_TOKEN},
                      json=body, timeout=15)
    return r.json().get("data", {})


def pd_has_deal(person_id):
    r = requests.get(f"{PIPEDRIVE_BASE}/persons/{person_id}/deals",
                     params={"api_token": PIPEDRIVE_TOKEN, "status": "open"},
                     timeout=15)
    deals = r.json().get("data") or []
    return len(deals) > 0


def pd_create_deal(person_id, name, org_id=None):
    body = {"title": f"Webinar aanmelding — {name}",
            "person_id": person_id,
            "stage_id": WEBINAR_STAGE_ID}
    if org_id:
        body["org_id"] = org_id
    r = requests.post(f"{PIPEDRIVE_BASE}/deals",
                      params={"api_token": PIPEDRIVE_TOKEN},
                      json=body, timeout=15)
    return r.json().get("data", {})


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Ophalen EmailOctopus subscribers...")
    eo_map = eo_get_all_contacts()
    print(f"  {len(eo_map)} subscribers gevonden")

    results = []

    # Dedupliceer op email
    seen = set()
    unique = []
    for name, email, company in WEBINAR_REGISTRATIONS:
        key = email.lower()
        if key not in seen:
            seen.add(key)
            unique.append((name, email.lower(), company))

    for name, email, company in unique:
        row = {"naam": name, "email": email, "bedrijf": company,
               "eo": "", "pd": ""}

        # EmailOctopus
        if email in eo_map:
            status, _ = eo_update_contact(eo_map[email], name, company)
            row["eo"] = "bijgewerkt" if status == 200 else f"fout {status}"
        else:
            status, resp = eo_create_contact(name, email, company)
            if status in (200, 201):
                row["eo"] = "aangemaakt"
            elif "MEMBER_EXISTS" in str(resp):
                row["eo"] = "al aanwezig (geen update)"
            else:
                row["eo"] = f"fout {status}"

        # Pipedrive
        person = pd_find_person(email)
        if person:
            person_id = person["id"]
            org_id = (person.get("organization") or {}).get("id")
            if pd_has_deal(person_id):
                row["pd"] = "al deal aanwezig"
            else:
                deal = pd_create_deal(person_id, name, org_id)
                row["pd"] = f"deal aangemaakt (ID {deal.get('id', '?')})" if deal else "fout bij deal"
        else:
            person_data = pd_create_person(name, email, company)
            if person_data.get("id"):
                deal = pd_create_deal(person_data["id"], name, person_data.get("org_id"))
                row["pd"] = f"persoon + deal aangemaakt (deal {deal.get('id', '?')})"
            else:
                row["pd"] = "fout bij aanmaken persoon"

        print(f"  {email}: EO={row['eo']} | PD={row['pd']}")
        results.append(row)

    # Markdown rapport
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Webinar Backfill Resultaat",
        f"",
        f"Uitgevoerd: {ts}  ",
        f"Aanmelders verwerkt: {len(unique)}  ",
        f"",
        f"| Naam | Email | Bedrijf | EmailOctopus | Pipedrive |",
        f"|------|-------|---------|--------------|-----------|",
    ]
    for r in results:
        lines.append(f"| {r['naam']} | {r['email']} | {r['bedrijf']} | {r['eo']} | {r['pd']} |")
    lines += [
        f"",
        f"## Volgende stap",
        f"",
        f"- Controleer de [Show more]-vermeldingen in Formspree en voeg ontbrekende aanmelders handmatig toe via dit script",
        f"- Toekomstige aanmelders worden automatisch verwerkt via de gecorrigeerde `webinar-register.js`",
    ]

    out_path = os.path.join(os.path.dirname(__file__), "docs", "backfill_webinar_resultaat.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nRapport: {out_path}")


if __name__ == "__main__":
    main()
