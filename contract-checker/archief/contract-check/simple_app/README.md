# Contract Checker - Simpele versie

Eenvoudige tool om werkbonnen te classificeren tegen contracten.

## Wat doet het?

1. Upload een contract (PDF, Word, Excel of TXT)
2. Voer werkbon(nen) in (tekst of CSV)
3. Krijg classificatie: **JA** (binnen contract) / **NEE** (factureren) / **TWIJFEL** (handmatig checken)

## Installatie

```bash
# Virtual environment aanmaken
python -m venv venv
venv\Scripts\activate  # Windows

# Dependencies installeren
pip install -r requirements.txt

# .env aanmaken met API keys
copy .env.example .env
# Vul je API keys in
```

## Starten

```bash
streamlit run app.py
```

De app opent op http://localhost:8501

## Instellingen

**LLM Provider:**
- **Claude** - Nauwkeuriger, maar duurder (~$3/1M tokens)
- **Mistral** - Goedkoper (~$0.80/1M tokens)

**Drempelwaardes:**
- Stel in bij welke confidence score een classificatie definitief wordt
- Standaard: 85% voor zowel JA als NEE
- Onder de drempel -> TWIJFEL (handmatig beoordelen)

## API Keys

- Claude: https://console.anthropic.com
- Mistral: https://console.mistral.ai

Of vraag Mark om de .env met keys.
