#!/usr/bin/env python3
"""
Inspect current Supabase database structure
"""

import os
from supabase import create_client

# Supabase credentials
SUPABASE_URL = "https://usxstdmeljiclmcbjgvu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVzeHN0ZG1lbGppY2xtY2JqZ3Z1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk0Mjg0NTYsImV4cCI6MjA4NTAwNDQ1Nn0.OhtOSrpsxqJaWNvhYTGFnZNVQ1JsmOMObbDdYEWR07A"

def run_query(client, query, description):
    """Run a SQL query and display results"""
    print(f"\n{'='*80}")
    print(f"  {description}")
    print('='*80)

    try:
        result = client.rpc('exec_sql', {'sql': query}).execute()

        if result.data:
            # Print as table
            if isinstance(result.data, list) and len(result.data) > 0:
                # Get headers
                headers = list(result.data[0].keys())

                # Print headers
                print("\n" + " | ".join(headers))
                print("-" * (sum(len(h) for h in headers) + len(headers) * 3))

                # Print rows
                for row in result.data:
                    print(" | ".join(str(row.get(h, '')) for h in headers))

                print(f"\n{len(result.data)} rows")
            else:
                print(result.data)
        else:
            print("No data returned")

    except Exception as e:
        print(f"Error: {e}")

def main():
    print("="*80)
    print("  SUPABASE DATABASE INSPECTION")
    print(f"  URL: {SUPABASE_URL}")
    print("="*80)

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Query 1: List all tables
    run_query(client, """
        SELECT
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """, "1. All Tables in Public Schema")

    # Query 2: Column details
    run_query(client, """
        SELECT
            table_name,
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """, "2. Column Details for All Tables")

    # Query 3: Foreign keys
    run_query(client, """
        SELECT
            tc.table_name AS source_table,
            kcu.column_name AS source_column,
            ccu.table_name AS target_table,
            ccu.column_name AS target_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
        ORDER BY tc.table_name;
    """, "3. Foreign Key Relationships")

    # Query 4: Check for existing LLM tables
    run_query(client, """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
            AND (
                table_name LIKE '%llm%'
                OR table_name LIKE '%ai%'
                OR table_name LIKE '%model%'
            )
        ORDER BY table_name;
    """, "4. Existing LLM-related Tables")

    # Query 5: Apps table (if exists)
    run_query(client, """
        SELECT *
        FROM apps
        ORDER BY code;
    """, "5. Apps Registry")

    # Query 6: Organizations table (if exists)
    run_query(client, """
        SELECT id, name, organization_type, is_active
        FROM organizations
        ORDER BY name;
    """, "6. Organizations")

    # Query 7: Row counts
    run_query(client, """
        SELECT
            schemaname,
            relname AS table_name,
            n_live_tup AS row_count
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY n_live_tup DESC;
    """, "7. Table Row Counts")

    print("\n" + "="*80)
    print("  INSPECTION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()
