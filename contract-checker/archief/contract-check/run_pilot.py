#!/usr/bin/env python3
"""
WVC Contract Checker - Pilot CLI

Usage:
    # From CSV file
    python run_pilot.py --input werkbonnen.csv

    # From database (date range)
    python run_pilot.py --start-date 2024-01-01 --end-date 2024-03-31

    # With output file
    python run_pilot.py --input werkbonnen.csv --output results.csv
"""
import argparse
import csv
import sys
from datetime import datetime as dt

from src.config import config
from src.services.contract_loader import ContractLoader
from src.services.classifier import ClassificationService
from src.services.werkbon_service import WerkbonService
from src.models.database import SessionLocal, init_db
from src.models.classification import Classification


def load_werkbonnen_from_csv(filepath: str) -> list:
    """Load werkbonnen from CSV file."""
    werkbonnen = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        # Try to detect delimiter
        sample = f.read(1024)
        f.seek(0)
        delimiter = ';' if ';' in sample else ','

        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            werkbonnen.append(row)
    return werkbonnen


def load_werkbonnen_from_db(start_date: str, end_date: str, limit: int):
    """Load werkbonnen from datawarehouse."""
    service = WerkbonService()
    try:
        start = dt.strptime(start_date, "%Y-%m-%d").date()
        end = dt.strptime(end_date, "%Y-%m-%d").date()

        total = service.get_werkbon_count(start, end)
        print(f"Found {total} werkbonnen in date range")

        werkbonnen = service.get_werkbonnen(start, end, limit=limit)
        return werkbonnen
    finally:
        service.close()


def save_results_to_csv(results: list, filepath: str):
    """Save classification results to CSV."""
    if not results:
        print("No results to save")
        return

    fieldnames = [
        'werkbon_id', 'classificatie', 'mapping_score',
        'contract_referentie', 'toelichting', 'werkbon_bedrag'
    ]

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, '') for k in fieldnames})

    print(f"\nResults saved to {filepath}")


def save_results_to_db(results: list):
    """Save classification results to database."""
    db = SessionLocal()
    try:
        for r in results:
            classification = Classification(
                werkbon_id=r.get('werkbon_id'),
                classificatie=r['classificatie'],
                mapping_score=r.get('mapping_score'),
                contract_referentie=r.get('contract_referentie'),
                toelichting=r.get('toelichting'),
                werkbon_bedrag=r.get('werkbon_bedrag'),
            )
            db.add(classification)
        db.commit()
        print(f"\nResults saved to database ({config.DB_SCHEMA})")
    finally:
        db.close()


def print_summary(results: list):
    """Print classification summary."""
    total = len(results)
    if total == 0:
        print("No results to summarize")
        return

    ja = sum(1 for r in results if r['classificatie'] == 'JA')
    nee = sum(1 for r in results if r['classificatie'] == 'NEE')
    onzeker = sum(1 for r in results if r['classificatie'] == 'ONZEKER')

    scores = [r['mapping_score'] for r in results if r.get('mapping_score')]
    avg_score = sum(scores) / len(scores) if scores else 0

    print("\n" + "=" * 50)
    print("CLASSIFICATION SUMMARY")
    print("=" * 50)
    print(f"Total werkbonnen:    {total}")
    print(f"JA (in contract):    {ja:3d} ({ja/total*100:5.1f}%)")
    print(f"NEE (factureren):    {nee:3d} ({nee/total*100:5.1f}%)")
    print(f"ONZEKER (review):    {onzeker:3d} ({onzeker/total*100:5.1f}%)")
    print(f"Avg mapping score:   {avg_score:.2f}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description='WVC Contract Checker - Pilot CLI'
    )

    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--input', '-i',
        help='Input CSV file with werkbonnen'
    )
    input_group.add_argument(
        '--start-date',
        help='Start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end-date',
        help='End date (YYYY-MM-DD), required with --start-date'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output CSV file for results'
    )
    parser.add_argument(
        '--no-db',
        action='store_true',
        help='Do not save results to database'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Max werkbonnen to process (default: 100)'
    )

    args = parser.parse_args()

    # Validate date args
    if args.start_date and not args.end_date:
        parser.error("--end-date required when using --start-date")

    # Initialize database
    if not args.no_db:
        print("Initializing database...")
        init_db()

    # Load contracts
    print(f"\nLoading contracts from {config.CONTRACTS_FOLDER}...")
    loader = ContractLoader()
    contracts = loader.load_contracts()

    if not contracts:
        print("ERROR: No contracts found")
        sys.exit(1)

    print(f"Loaded {len(contracts)} contract(s):")
    for c in loader.get_contracts_summary():
        print(f"  - {c['name']} ({c['content_length']} chars)")

    # Initialize classifier
    classifier = ClassificationService()
    classifier.set_contracts(loader.get_contracts_text())

    # Load werkbonnen
    if args.input:
        print(f"\nLoading werkbonnen from {args.input}...")
        werkbonnen = load_werkbonnen_from_csv(args.input)
    else:
        print("\nLoading werkbonnen from database...")
        print(f"  Date range: {args.start_date} to {args.end_date}")
        werkbonnen = load_werkbonnen_from_db(
            args.start_date, args.end_date, args.limit
        )

    if args.limit and len(werkbonnen) > args.limit:
        werkbonnen = werkbonnen[:args.limit]

    print(f"Processing {len(werkbonnen)} werkbonnen...\n")

    # Process each werkbon
    results = []
    for i, werkbon in enumerate(werkbonnen, 1):
        wb_id = werkbon.get('werkbon_id', 'N/A')
        print(f"[{i:3d}/{len(werkbonnen)}] {wb_id}...", end=' ', flush=True)

        try:
            result = classifier.classify_werkbon(werkbon)
            results.append(result)

            score = result.get('mapping_score', 0)
            print(f"{result['classificatie']:7s} ({score:.2f})")

        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                'werkbon_id': wb_id,
                'classificatie': 'ONZEKER',
                'mapping_score': 0,
                'toelichting': f'Error: {e}'
            })

    # Save results
    if not args.no_db:
        save_results_to_db(results)

    if args.output:
        save_results_to_csv(results, args.output)

    # Print summary
    print_summary(results)


if __name__ == '__main__':
    main()
