# Claude Code Project Instructions

## Project: Blob Analyse - Zenith Security

### Workflow
- Je kunt zelf de Streamlit app herstarten met: `python -m streamlit run app.py`
- Je kunt zelf Python scripts uitvoeren zonder dat te vragen

### Tech Stack
- Streamlit app
- PostgreSQL DWH (10.3.152.9, database per klant)
- Blobvelden uit Syntess ERP

### Key Concepts
- Blobveld ID = MobieleuitvoersessieRegelKey
- Koppeling naar werkbon via DocumentKey
- Alleen werken met blobvelden die een werkbon koppeling hebben
