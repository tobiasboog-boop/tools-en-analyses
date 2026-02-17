import streamlit as st
import pandas as pd
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


@st.cache_data(ttl=600)
def load_vehicles() -> pd.DataFrame:
    """Load vehicle master data from Parquet."""
    return pd.read_parquet(os.path.join(DATA_DIR, 'vehicles.parquet'))


@st.cache_data(ttl=600)
def load_trips() -> pd.DataFrame:
    """Load all trips from Parquet with unit conversions."""
    df = pd.read_parquet(os.path.join(DATA_DIR, 'trips.parquet'))

    # Parse timestamps (UTC -> Europe/Amsterdam)
    start_ts = pd.to_datetime(df['tripstartutc'], utc=True)
    end_ts = pd.to_datetime(df['tripendutc'], utc=True)
    df['start'] = start_ts.dt.tz_convert('Europe/Amsterdam')
    df['eind'] = end_ts.dt.tz_convert('Europe/Amsterdam')
    df['datum'] = df['start'].dt.date

    # Convert units: meters -> km, seconds -> minutes
    df['afstand_km'] = df['tripdistance'].fillna(0) / 1000.0
    df['rijtijd_min'] = df['drivingtime'].fillna(0) / 60.0
    df['km_stand_start'] = df['startodometerreading'].fillna(0) / 1000.0
    df['km_stand_eind'] = df['endodometerreading'].fillna(0) / 1000.0

    # Parse coordinates to float
    for col in ['startlatitude', 'startlongitude', 'endlatitude', 'endlongitude']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Idle time in minutes
    df['stationair_min'] = df['excessidletime'].fillna(0) / 60.0
    df['overspeed_min'] = df['overspeedduration'].fillna(0) / 60.0

    return df
