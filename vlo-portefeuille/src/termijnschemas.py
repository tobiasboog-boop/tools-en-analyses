import pandas as pd
import numpy as np
from datetime import date


# Built-in schemas (altijd beschikbaar, niet bewerkbaar)
BUILTIN_SCHEMAS = {
    "Lineair": "Gelijke verdeling over alle maanden",
    "S-curve": "Langzame start, piek in het midden, geleidelijke afbouw",
}

# Default user-defined termijnschema's (bewerkbaar door gebruiker)
DEFAULT_USER_SCHEMAS = {
    "Schema 1": [10, 30, 40, 20],
}

MAX_USER_SCHEMAS = 5


def get_all_schema_namen(user_schemas: dict[str, list[float]] | None = None) -> list[str]:
    """Get all available schema names: user-defined first, then built-in."""
    namen = []
    if user_schemas:
        namen.extend(user_schemas.keys())
    namen.extend(BUILTIN_SCHEMAS.keys())
    return namen


def generate_month_range(start_date: date, end_date: date) -> pd.DatetimeIndex:
    """Generate monthly periods between start and end date."""
    return pd.date_range(
        start=start_date.replace(day=1),
        end=end_date.replace(day=1),
        freq="MS",
    )


def linear_distribution(total: float, n_months: int) -> np.ndarray:
    if n_months <= 0:
        return np.array([total])
    return np.full(n_months, total / n_months)


def s_curve_distribution(total: float, n_months: int) -> np.ndarray:
    if n_months <= 0:
        return np.array([total])
    if n_months == 1:
        return np.array([total])

    x = np.linspace(-4, 4, n_months + 1)
    cumulative = 1 / (1 + np.exp(-x))
    cumulative = (cumulative - cumulative[0]) / (cumulative[-1] - cumulative[0])
    monthly = np.diff(cumulative) * total
    return monthly


def weighted_distribution(total: float, n_months: int, weights: list[float]) -> np.ndarray:
    """Distribute total across phases with given weights."""
    if n_months <= 0:
        return np.array([total])

    n_phases = len(weights)
    w = np.array(weights, dtype=float)
    w = w / w.sum()

    monthly = np.zeros(n_months)
    phase_starts = np.linspace(0, n_months, n_phases + 1, dtype=int)

    for i in range(n_phases):
        start = phase_starts[i]
        end = phase_starts[i + 1]
        phase_months = end - start
        if phase_months > 0:
            phase_amount = total * w[i]
            monthly[start:end] = phase_amount / phase_months

    return monthly


def distribute_revenue(
    total_amount: float,
    start_date: date,
    end_date: date,
    schema: str,
    user_schemas: dict[str, list[float]] | None = None,
) -> pd.DataFrame:
    """
    Distribute total revenue across months using the selected schema.

    schema: name of a built-in or user-defined schema
    user_schemas: dict mapping schema name to list of percentages (0-100)
    """
    months = generate_month_range(start_date, end_date)
    n_months = len(months)

    if n_months == 0:
        months = pd.DatetimeIndex([start_date.replace(day=1)])
        n_months = 1

    # Check user-defined schemas first
    if user_schemas and schema in user_schemas:
        percentages = user_schemas[schema]
        weights = [p / 100.0 for p in percentages]
        amounts = weighted_distribution(total_amount, n_months, weights)
    elif schema == "Lineair":
        amounts = linear_distribution(total_amount, n_months)
    elif schema == "S-curve":
        amounts = s_curve_distribution(total_amount, n_months)
    else:
        # Fallback to linear
        amounts = linear_distribution(total_amount, n_months)

    return pd.DataFrame({
        "maand": months[:len(amounts)],
        "bedrag": amounts,
    })


def distribute_project(
    row: pd.Series,
    start_date: date,
    end_date: date,
    schema: str,
    user_schemas: dict[str, list[float]] | None = None,
) -> pd.DataFrame:
    dist = distribute_revenue(
        row["totaal"], start_date, end_date, schema, user_schemas
    )

    dist["project_id"] = row["project_id"]
    dist["naam"] = row["naam"]
    dist["vestiging"] = row["vestiging"]
    dist["categorie"] = row["categorie"]
    dist["is_wederkerend"] = row["is_wederkerend"]

    return dist


def distribute_all_projects(
    df: pd.DataFrame,
    project_settings: dict | None = None,
    default_schema: str = "Termijnfacturatie",
    user_schemas: dict[str, list[float]] | None = None,
) -> pd.DataFrame:
    """
    Distribute all projects' revenue across months.

    project_settings: dict mapping project_id to {schema, start_date, end_date}
    user_schemas: dict mapping schema name to list of percentages
    """
    if project_settings is None:
        project_settings = {}

    all_distributions = []

    for _, row in df.iterrows():
        pid = row["project_id"]
        settings = project_settings.get(pid, {})

        schema = settings.get("schema", default_schema)
        start_year = row.get("start_jaar", 2026) or 2026
        end_year = row.get("eind_jaar", 2026) or 2026

        start_date = settings.get("start_date", row.get("originele_start", date(int(start_year), 1, 1)))
        end_date = settings.get("end_date", row.get("originele_eind", date(int(end_year), 12, 1)))

        # Recurring projects always linear
        if row.get("is_wederkerend", False):
            schema = "Lineair"

        dist = distribute_project(row, start_date, end_date, schema, user_schemas)
        all_distributions.append(dist)

    if all_distributions:
        return pd.concat(all_distributions, ignore_index=True)
    return pd.DataFrame()
