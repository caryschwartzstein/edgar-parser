#!/usr/bin/env python3
"""
Parse the top 10 test companies with both annual and quarterly data.

This script processes the companies we have raw EDGAR data for and generates
updated parsed files with quarterly information included.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.edgar_parser.parser_v2 import EDGARParser


def main():
    """Parse all companies in data/raw_edgar/ with quarterly data."""

    # Setup paths
    raw_dir = Path('data/raw_edgar')
    parsed_dir = Path('data/parsed/with_quarterly_fixed')
    parsed_dir.mkdir(exist_ok=True, parents=True)

    # Get all raw EDGAR files
    raw_files = sorted(raw_dir.glob('*_edgar_raw.json'))

    if not raw_files:
        print(f"No raw EDGAR files found in {raw_dir}")
        return

    print(f"Found {len(raw_files)} companies to parse")
    print("="*80)

    # Initialize parser
    parser = EDGARParser()

    # Track results
    success_count = 0
    failed_companies = []

    # Parse each company
    for raw_file in raw_files:
        ticker = raw_file.stem.replace('_edgar_raw', '')

        try:
            print(f"\n{'='*80}")
            print(f"Processing: {ticker}")
            print(f"{'='*80}")

            # Load raw EDGAR data
            with open(raw_file) as f:
                edgar_data = json.load(f)

            # Parse with quarterly data
            result = parser.parse_company_data(
                edgar_data,
                verbose=True,
                include_quarterly=True
            )

            # Save parsed result
            output_file = parsed_dir / f"{ticker}_parsed_with_quarterly.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)

            print(f"\n✓ Saved to: {output_file}")
            print(f"  Annual periods: {result['metadata']['total_annual_periods']}")
            print(f"  Quarterly periods: {result['metadata']['total_quarterly_periods']}")

            success_count += 1

        except Exception as e:
            print(f"\n✗ Error processing {ticker}: {e}")
            import traceback
            traceback.print_exc()
            failed_companies.append((ticker, str(e)))

    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total companies: {len(raw_files)}")
    print(f"Successfully parsed: {success_count}")
    print(f"Failed: {len(failed_companies)}")

    if failed_companies:
        print(f"\nFailed companies:")
        for ticker, error in failed_companies:
            print(f"  - {ticker}: {error}")

    print(f"\n✓ Parsed files saved to: {parsed_dir}")


if __name__ == '__main__':
    main()
