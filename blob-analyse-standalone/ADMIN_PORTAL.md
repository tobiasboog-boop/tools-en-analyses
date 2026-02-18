# Admin Portal Integratie

## Streamlit App URL
```
https://blob-analyse-jh9uipkssuu99y6d5agmdb.streamlit.app/
```

## Admin Portal Link
De app is toegevoegd aan de Notifica Admin Portal:
```
https://notifica.nl/admin/tools/blob-analyse/
```

## Locatie in Admin Portal
- **Sectie:** Klant Specifieke Dashboards
- **Naam:** Zenith Security - Blob Analyse
- **Status:** Pilot

## Bestanden in notifica_site
- `src/admin/tools/blob-analyse.njk` - Wrapper pagina met iframe
- `src/admin/index.njk` - Link toegevoegd aan dashboard sectie

## Deployment
De Streamlit app wordt automatisch gedeployed bij push naar `main` branch van:
```
https://github.com/tobiasboog-boop/blob-analyse
```

## Klantgegevens
- **Klant:** Zenith Security
- **Klantnummer:** 1229
- **Type:** Pilot werkbon blobvelden
