"""Configuration for VLO Orderportefeuille dashboard."""

# App settings
APP_TITLE = "VLO Groep — Orderportefeuille"
APP_ICON = "📊"
APP_LAYOUT = "wide"

# Colors - Notifica navy palette
NAVY_PRIMARY = "#16136F"
NAVY_SECONDARY = "#3636A2"
NAVY_LIGHT = "#E8E8F4"
ACCENT = "#FF9500"
BG_LIGHT = "#F8F9FA"
TEXT_DARK = "#1A1A2E"

# Chart color sequence (navy-based with distinguishable hues)
CHART_COLORS = [
    "#16136F",  # navy
    "#3636A2",  # medium blue
    "#5B5BD6",  # lighter blue
    "#FF9500",  # orange accent
    "#2D9CDB",  # sky blue
    "#7B61FF",  # purple
    "#00B894",  # green
    "#E17055",  # coral
    "#0984E3",  # bright blue
    "#6C5CE7",  # violet
    "#00CEC9",  # teal
    "#FDCB6E",  # yellow
    "#E84393",  # pink
    "#636E72",  # gray
    "#2D3436",  # dark gray
    "#74B9FF",  # light blue
    "#A29BFE",  # lavender
    "#55EFC4",  # mint
    "#FAB1A0",  # peach
]

# Number formatting
def format_eur(value: float, decimals: int = 0) -> str:
    """Format a number as EUR currency (Dutch style)."""
    if abs(value) >= 1_000_000:
        return f"€ {value / 1_000_000:,.1f}M".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs(value) >= 1_000:
        return f"€ {value / 1_000:,.0f}K".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_eur_full(value: float) -> str:
    """Format as full EUR amount with thousands separator."""
    return f"€ {value:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
