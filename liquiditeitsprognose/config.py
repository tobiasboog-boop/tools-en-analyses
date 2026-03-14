"""
Liquiditeitsprognose - Configuration
=====================================
Configuratie voor database connecties, app settings en forecast profielen.
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict
from datetime import datetime
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Check if Streamlit is available (for secrets support)
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


@dataclass
class DatabaseConfig:
    """
    Database connection configuration (legacy, niet meer primair gebruikt).

    Data wordt nu opgehaald via de Notifica Data API (NotificaClient SDK).
    Deze config is alleen nog nodig als fallback.
    """
    host: str
    port: int
    database: str
    username: str
    password: str

    @classmethod
    def from_secrets(cls, customer_code: Optional[str] = None) -> "DatabaseConfig":
        """
        Load config from Streamlit secrets (for Streamlit Cloud deployment).

        Args:
            customer_code: Optional 4-digit customer code. If provided,
                          overrides the database name from secrets.
        """
        try:
            if STREAMLIT_AVAILABLE and hasattr(st, 'secrets') and 'database' in st.secrets:
                db = st.secrets["database"]

                # Database name can be overridden by customer_code
                database = db.get("database", "1229")
                if customer_code and len(customer_code) == 4 and customer_code.isdigit():
                    database = customer_code

                return cls(
                    host=db.get("host", "10.3.152.9"),
                    port=int(db.get("port", 5432)),
                    database=database,
                    username=db.get("user", "postgres"),
                    password=db.get("password", ""),
                )
        except Exception:
            # Streamlit secrets niet beschikbaar (bijv. bij CLI scripts)
            pass

        # Fallback to environment variables
        return cls.from_env(customer_code=customer_code)

    @classmethod
    def from_env(cls, customer_code: Optional[str] = None) -> "DatabaseConfig":
        """
        Load database config from environment variables.

        Args:
            customer_code: Optional 4-digit customer code. If provided,
                          database name will be set to the customer code directly.
        """
        database = os.getenv("SYNTESS_DB_NAME", "1229")
        if customer_code and len(customer_code) == 4 and customer_code.isdigit():
            # Database name = klantnummer direct (niet dwh_XXXX)
            database = customer_code

        return cls(
            host=os.getenv("SYNTESS_DB_HOST", "10.3.152.9"),
            port=int(os.getenv("SYNTESS_DB_PORT", "5432")),
            database=database,
            username=os.getenv("SYNTESS_DB_USER", "postgres"),
            password=os.getenv("SYNTESS_DB_PASSWORD", "TQwSTtLM9bSaLD"),
        )

    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class AppConfig:
    """Application configuration."""
    app_title: str = "Liquiditeitsprognose"
    app_icon: str = "💰"
    default_forecast_weeks: int = 13
    default_history_months: int = 12

    # Cashflow categorieën (standaard classificatie)
    cashflow_categories: dict = None

    def __post_init__(self):
        if self.cashflow_categories is None:
            self.cashflow_categories = {
                "inkomend": {
                    "debiteuren": "Openstaande debiteuren",
                    "orderintake": "Verwachte orderintake",
                    "overig_in": "Overige inkomsten",
                },
                "uitgaand": {
                    "crediteuren": "Openstaande crediteuren",
                    "salarissen": "Salarisbetalingen",
                    "btw": "BTW afdracht",
                    "overig_uit": "Overige uitgaven",
                },
                "saldo": {
                    "bank": "Banksaldo",
                    "kas": "Kassaldo",
                },
            }


# Default thresholds for alerts
LIQUIDITY_THRESHOLDS = {
    "current_ratio_warning": 1.5,
    "current_ratio_danger": 1.0,
    "quick_ratio_warning": 1.0,
    "quick_ratio_danger": 0.5,
    "min_cash_buffer_days": 30,
}

# Color scheme matching Notifica branding
COLORS = {
    "primary": "#1E3A5F",      # Dark blue
    "secondary": "#3498DB",    # Light blue
    "success": "#27AE60",      # Green
    "warning": "#F39C12",      # Orange
    "danger": "#E74C3C",       # Red
    "neutral": "#95A5A6",      # Gray
}


# =============================================================================
# FORECAST PROFIELEN — Configureerbaar per klant
# =============================================================================

@dataclass
class ForecastProfile:
    """Configureerbaar forecast profiel per klant.

    Het model detecteert automatisch een bedrijfstype en stelt een profiel voor.
    De klant of consultant kan dit overrulen en per knop finetunen.

    Knoppen:
        realiteit_horizon_weken: Hoe lang ERP-feiten dominant zijn in de blend.
            Langer = meer vertrouwen op openstaande posten, korter = sneller
            overschakelen naar statistische forecast.
        outlier_iqr_multiplier: Hoe streng grote facturen gefilterd worden bij
            het berekenen van de run rate. Hoger = meer uitschieters behouden.
        run_rate_methode: Welk statistisch "normaal niveau" wordt gebruikt.
            'mean' = gemiddelde (gevoelig voor uitschieters),
            'median' = mediaan (robuust),
            'p75' = 75e percentiel (conservatief hoog, vangt pieken).
        nieuwe_facturatie_pct: Minimaal gewicht voor geschatte nieuwe facturatie
            die nog niet in ERP staat. Hoger = meer verwachte nieuwe facturen.
        gebruik_pijplijn: Of de orderportefeuille/service orders worden
            meegenomen als aanvullende inkomstenbron.
        gebruik_recurring_revenue: Of servicecontracten/abonnementen als
            vaste recurring revenue worden meegeteld.
    """
    # Identificatie
    klantnummer: str = ""
    profiel_naam: str = "gemengd"  # 'onderhoud', 'gemengd', 'project'

    # Bron van keuze
    auto_detected: str = ""        # Wat het model voorstelde
    manually_set: bool = False      # Heeft klant/consultant dit overruled?

    # De knoppen (None = gebruik profiel-default via get_effective_*)
    realiteit_horizon_weken: Optional[int] = None
    outlier_iqr_multiplier: Optional[float] = None
    run_rate_methode: Optional[str] = None         # 'mean', 'median', 'p75'
    nieuwe_facturatie_pct: Optional[float] = None   # 0.0 - 1.0
    gebruik_pijplijn: Optional[bool] = None
    gebruik_recurring_revenue: Optional[bool] = None

    # Metadata
    laatst_gewijzigd: Optional[str] = None
    gewijzigd_door: Optional[str] = None   # 'systeem' of naam consultant

    def get_effective(self, knop: str):
        """Geef effectieve waarde: handmatige override of profiel-default."""
        override = getattr(self, knop, None)
        if override is not None:
            return override
        return PROFIEL_DEFAULTS[self.profiel_naam].get(knop)

    @property
    def effective_realiteit_horizon(self) -> int:
        return self.get_effective('realiteit_horizon_weken')

    @property
    def effective_iqr_multiplier(self) -> float:
        return self.get_effective('outlier_iqr_multiplier')

    @property
    def effective_run_rate_methode(self) -> str:
        return self.get_effective('run_rate_methode')

    @property
    def effective_nieuwe_facturatie(self) -> float:
        return self.get_effective('nieuwe_facturatie_pct')

    @property
    def effective_pijplijn(self) -> bool:
        return self.get_effective('gebruik_pijplijn')

    @property
    def effective_recurring(self) -> bool:
        return self.get_effective('gebruik_recurring_revenue')

    def to_dict(self) -> dict:
        """Serialiseer naar dict (voor opslag in API)."""
        d = asdict(self)
        # Verwijder None waarden voor compacte opslag
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "ForecastProfile":
        """Deserialiseer vanuit dict (uit API)."""
        # Filter alleen bekende velden
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def describe(self) -> str:
        """Menselijk leesbare beschrijving van het actieve profiel."""
        naam = PROFIEL_LABELS.get(self.profiel_naam, self.profiel_naam)
        bron = "handmatig ingesteld" if self.manually_set else "automatisch gedetecteerd"
        overrides = []
        for knop in KNOPPEN:
            val = getattr(self, knop, None)
            if val is not None:
                default = PROFIEL_DEFAULTS[self.profiel_naam].get(knop)
                if val != default:
                    overrides.append(f"  {KNOP_LABELS[knop]}: {val} (default: {default})")
        ovr = "\n".join(overrides) if overrides else "  Geen"
        return f"Profiel: {naam} ({bron})\nAangepaste instellingen:\n{ovr}"


# Profiel labels (voor UI)
PROFIEL_LABELS = {
    "onderhoud": "Onderhoud & Service",
    "gemengd": "Gemengd",
    "project": "Projectmatig",
}

# Profiel beschrijvingen (voor UI)
PROFIEL_BESCHRIJVINGEN = {
    "onderhoud": (
        "Regelmatige werkbonnen, storingen en servicecontracten. "
        "Voorspelbare cashflow met seizoenspatronen."
    ),
    "gemengd": (
        "Mix van onderhoud/service en af en toe grotere projecten. "
        "De meeste installatiebedrijven vallen in deze categorie."
    ),
    "project": (
        "Grote projecten met termijnfacturatie, wisselende omzet. "
        "Nieuwbouw, grote installaties, lange doorlooptijden."
    ),
}

# Default waarden per profiel (de "fabrieksinstellingen")
PROFIEL_DEFAULTS: Dict[str, dict] = {
    "onderhoud": {
        "realiteit_horizon_weken": 3,
        "outlier_iqr_multiplier": 1.5,
        "run_rate_methode": "mean",
        "nieuwe_facturatie_pct": 0.15,
        "gebruik_pijplijn": False,
        "gebruik_recurring_revenue": True,
    },
    "gemengd": {
        "realiteit_horizon_weken": 5,
        "outlier_iqr_multiplier": 2.0,
        "run_rate_methode": "median",
        "nieuwe_facturatie_pct": 0.25,
        "gebruik_pijplijn": True,
        "gebruik_recurring_revenue": True,
    },
    "project": {
        "realiteit_horizon_weken": 7,
        "outlier_iqr_multiplier": 2.5,
        "run_rate_methode": "p75",
        "nieuwe_facturatie_pct": 0.40,
        "gebruik_pijplijn": True,
        "gebruik_recurring_revenue": False,
    },
}

# Alle configureerbare knoppen
KNOPPEN = [
    "realiteit_horizon_weken",
    "outlier_iqr_multiplier",
    "run_rate_methode",
    "nieuwe_facturatie_pct",
    "gebruik_pijplijn",
    "gebruik_recurring_revenue",
]

# Labels voor UI
KNOP_LABELS = {
    "realiteit_horizon_weken": "Realiteit-horizon",
    "outlier_iqr_multiplier": "Outlier-gevoeligheid",
    "run_rate_methode": "Run rate methode",
    "nieuwe_facturatie_pct": "Nieuwe facturatie",
    "gebruik_pijplijn": "Orderportefeuille",
    "gebruik_recurring_revenue": "Servicecontracten",
}

# Tooltips voor UI
KNOP_TOOLTIPS = {
    "realiteit_horizon_weken": (
        "Hoe lang openstaande posten uit het ERP dominant zijn in de prognose. "
        "Langer = meer vertrouwen op bekende facturen. "
        "Korter = sneller overschakelen naar statistische forecast."
    ),
    "outlier_iqr_multiplier": (
        "Hoe streng grote facturen worden gefilterd bij het berekenen van het "
        "gemiddelde niveau. Soepeler = grote facturen tellen mee. "
        "Strenger = uitschieters worden weggefilterd."
    ),
    "run_rate_methode": (
        "Welk statistisch niveau als 'normaal' wordt gebruikt. "
        "Gemiddelde werkt goed bij stabiele inkomsten. "
        "Mediaan is robuuster bij wisselende bedragen. "
        "75e percentiel vangt grote pieken beter."
    ),
    "nieuwe_facturatie_pct": (
        "Hoeveel nieuwe facturatie (die nog niet in het ERP staat) verwacht wordt. "
        "Bij onderhoudsbedrijven is dit laag (werkbonnen worden snel gefactureerd). "
        "Bij projectbedrijven is dit hoog (termijnfacturen komen later)."
    ),
    "gebruik_pijplijn": (
        "Of de orderportefeuille en service orders worden meegenomen als "
        "aanvullende inkomstenbron. Relevant bij projectmatig werk."
    ),
    "gebruik_recurring_revenue": (
        "Of servicecontracten en abonnementen als vaste recurring revenue "
        "worden meegerekend. Relevant bij onderhoud met contracten."
    ),
}

# Opties voor UI dropdowns/sliders
KNOP_OPTIES = {
    "realiteit_horizon_weken": {"min": 1, "max": 10, "step": 1, "format": "{} weken"},
    "outlier_iqr_multiplier": {
        "choices": [
            (1.5, "Streng (1.5x)"),
            (2.0, "Normaal (2.0x)"),
            (2.5, "Soepel (2.5x)"),
            (3.0, "Zeer soepel (3.0x)"),
        ]
    },
    "run_rate_methode": {
        "choices": [
            ("mean", "Gemiddelde"),
            ("median", "Mediaan"),
            ("p75", "75e percentiel"),
        ]
    },
    "nieuwe_facturatie_pct": {"min": 0.0, "max": 0.60, "step": 0.05, "format": "{:.0%}"},
    "gebruik_pijplijn": {"type": "toggle"},
    "gebruik_recurring_revenue": {"type": "toggle"},
}
