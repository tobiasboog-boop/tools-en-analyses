# Notifica Tools

Verzameling van herbruikbare tools voor Notifica.

## Offerte Generator

**Locatie:** `offerte_generator.py`

Genereer offertes op basis van Word templates met behoud van alle opmaak, logo's en huisstijl.

### Snel gebruik

```python
from offerte_generator import genereer_offerte

genereer_offerte(
    template_path="pad/naar/template.docx",
    output_path="pad/naar/output.docx",
    bedrijfsnaam="BRAS ELEKTROTECHNIEK B.V.",
    contactpersoon="t.a.v. Ing. P. Bras, directeur",
    adres="Zeeheld 3",
    postcode_plaats="5342 VX  OSS",
    aanhef="Geachte heer Bras,",
    boekhoudpakket="AccountView",
    maandtarief="650"
)
```

### Beschikbare functies

| Functie | Omschrijving |
|---------|--------------|
| `genereer_offerte()` | Generieke functie voor elke klant |
| `genereer_offerte_bras()` | Specifiek voor Bras Elektrotechniek |
| `OfferteGenerator` | Klasse voor geavanceerd gebruik |

### Templates

Standaard template locatie:
```
C:\Users\tobia\OneDrive - Notifica B.V\Documenten - Sharepoint Notifica intern\104. Verkoop\Offerte documenten ENK\
```

### Voorbeelden klanten

In het script zijn voorbeeldklanten gedefinieerd in `VOORBEELD_KLANTEN`:
- `bras` - Bras Elektrotechniek
- `teo` - TEO Elektrotechniek

### Vereisten

- Python 3.x
- python-docx (`pip install python-docx`)
