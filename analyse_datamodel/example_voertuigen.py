"""Voorbeeld: Voertuigen ophalen uit DWH."""
import pandas as pd
from db_connection import get_connection

def get_vehicles():
    """Haal alle voertuigen op."""
    conn = get_connection()

    query = """
        SELECT
            "K_nodeid",
            regno,
            description,
            make,
            model
        FROM stg.stg_ctrack_vehicles
        ORDER BY regno
    """

    df = pd.read_sql(query, conn)
    conn.close()

    return df

if __name__ == "__main__":
    print("Ophalen voertuigen uit DWH...\n")

    vehicles = get_vehicles()

    print(f"Totaal: {len(vehicles)} voertuigen\n")
    print(vehicles.head(20))

    # Export naar CSV
    vehicles.to_csv('voertuigen_export.csv', index=False, encoding='utf-8-sig')
    print(f"\nGeexporteerd naar: voertuigen_export.csv")
