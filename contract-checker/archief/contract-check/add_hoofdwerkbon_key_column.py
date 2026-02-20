#!/usr/bin/env python3
"""Migrate classifications table to latest schema."""
from sqlalchemy import text
from src.models.database import engine
from src.config import config


def get_existing_columns(conn):
    """Get list of existing columns in classifications table."""
    result = conn.execute(text(f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = '{config.DB_SCHEMA}'
          AND table_name = 'classifications'
    """))
    return {row[0] for row in result}


def add_column_if_not_exists(conn, column_name, column_def, index=False):
    """Add column if it doesn't exist."""
    existing_cols = get_existing_columns(conn)

    if column_name not in existing_cols:
        print(f"Adding {column_name} column...")
        alter_query = text(f"""
            ALTER TABLE {config.DB_SCHEMA}.classifications
            ADD COLUMN {column_name} {column_def}
        """)
        conn.execute(alter_query)

        if index:
            index_query = text(f"""
                CREATE INDEX IF NOT EXISTS ix_{config.DB_SCHEMA}_classifications_{column_name}
                ON {config.DB_SCHEMA}.classifications ({column_name})
            """)
            conn.execute(index_query)

        print(f"  + Added {column_name}")
    else:
        print(f"  - {column_name} already exists")


def migrate_classifications_table():
    """Migrate classifications table to latest schema."""
    print(f"Migrating {config.DB_SCHEMA}.classifications table...\n")

    with engine.connect() as conn:
        # Add all missing columns
        add_column_if_not_exists(
            conn,
            "hoofdwerkbon_key",
            "INTEGER",
            index=True
        )

        add_column_if_not_exists(
            conn,
            "modus",
            "VARCHAR(20) NOT NULL DEFAULT 'classificatie' CHECK (modus IN ('validatie', 'classificatie'))",
            index=True
        )

        conn.commit()
        print("\nMigration completed successfully!")


if __name__ == "__main__":
    migrate_classifications_table()
