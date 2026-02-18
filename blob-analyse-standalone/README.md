# Blob Analyse - Zenith Security

Pilot project voor analyse van werkbon-blobvelden voor klant Zenith Security (1229).

## Doel

Ongestructureerde blobvelden uit Syntess analyseren en toevoegen aan het semantisch model voor werkbonrapportage.

## Structuur

```
blob-analyse/
├── ANALYSE_BLOBVELDEN_ZENITH_SECURITY.md   # Analyse document
├── scripts/
│   ├── rtf_parser.py                       # RTF naar tekst conversie
│   ├── xml_parser.py                       # XML urenregels parser
│   └── extract_blobvelden.py               # Hoofdscript data-extractie
├── output/                                  # Geëxporteerde data (niet in git)
└── requirements.txt
```

## Relevante Blobvelden

| Blobveld | Bron | Inhoud |
|----------|------|--------|
| NOTITIE.txt | AT_MWBSESS | Monteurnotities |
| TEKST.txt | AT_UITVBEST | Storingsmeldingen |
| GC_INFORMATIE.txt | AT_WERK | Casebeschrijvingen |
| INGELEVERDE_URENREGELS.txt | AT_MWBSESS | Urenregistratie (XML) |

## Gebruik

```bash
# Installeer dependencies
pip install -r requirements.txt

# Run extractie
cd scripts
python extract_blobvelden.py --output-dir ../output
```

## Volgende stappen

1. [ ] Streamlit prototype app voor AI-analyse
2. [ ] Integratie met semantisch model SynthesAnalyse
3. [ ] Extra tabel `WerkbonBlobvelden` voor Power BI
