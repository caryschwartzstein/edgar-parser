#!/usr/bin/env python3
"""
Test the quarterly delta calculation feature.

This script tests the new _calculate_quarterly_deltas() method
by parsing Apple and showing both YTD and de-cumulated quarterly values.
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.edgar_parser.parser_v2 import EDGARParser


def main():
    """Test quarterly delta calculation with Apple."""

    # Load Apple's raw EDGAR data
    apple_file = Path('data/raw_edgar/AAPL_edgar_raw.json')

    if not apple_file.exists():
        print(f"Error: {apple_file} not found")
        return

    print("="*80)
    print("TESTING QUARTERLY DELTA CALCULATION")
    print("="*80)
    print()

    with open(apple_file) as f:
        edgar_data = json.load(f)

    # Parse with quarterly data
    parser = EDGARParser()
    result = parser.parse_company_data(
        edgar_data,
        verbose=True,
        include_quarterly=True
    )

    # Focus on the most recent fiscal year's quarters
    quarterly_periods = result.get('quarterly_periods', [])

    if not quarterly_periods:
        print("No quarterly periods found")
        return

    # Group by fiscal year
    fiscal_years = {}
    for period in quarterly_periods:
        fy_key = period['fiscal_year_end'][:4]
        if fy_key not in fiscal_years:
            fiscal_years[fy_key] = []
        fiscal_years[fy_key].append(period)

    # Get most recent fiscal year
    most_recent_year = sorted(fiscal_years.keys(), reverse=True)[0]
    recent_quarters = sorted(
        fiscal_years[most_recent_year],
        key=lambda x: x['fiscal_year_end']
    )

    print()
    print("="*80)
    print(f"FISCAL YEAR {most_recent_year} - QUARTERLY EBIT VALUES")
    print("="*80)
    print()

    # Display table
    print(f"{'Quarter':<10} {'Period End':<15} {'YTD EBIT':<20} {'Quarterly EBIT':<20} {'Note':<30}")
    print("-"*100)

    quarter_num = 1
    for quarter in recent_quarters:
        period_end = quarter['fiscal_year_end']
        ebit = quarter.get('metrics', {}).get('ebit', {})

        ytd_value = ebit.get('ytd_value')
        quarterly_value = ebit.get('quarterly_value')
        note = ebit.get('calculation_note', '')

        # Format values
        if ytd_value is not None:
            ytd_display = f"${ytd_value / 1e9:,.1f}B"
        else:
            ytd_display = "N/A"

        if quarterly_value is not None:
            quarterly_display = f"${quarterly_value / 1e9:,.1f}B"
        else:
            quarterly_display = "N/A"

        # Shorten note for display
        note_short = note[:28] if len(note) > 28 else note

        print(f"Q{quarter_num:<9} {period_end:<15} {ytd_display:<20} {quarterly_display:<20} {note_short:<30}")
        quarter_num += 1

    print()
    print()
    print("="*80)
    print("VERIFICATION")
    print("="*80)
    print()

    # Verify the math is correct
    if len(recent_quarters) >= 2:
        q1 = recent_quarters[0]
        q2 = recent_quarters[1]

        q1_ebit = q1.get('metrics', {}).get('ebit', {})
        q2_ebit = q2.get('metrics', {}).get('ebit', {})

        q1_ytd = q1_ebit.get('ytd_value')
        q2_ytd = q2_ebit.get('ytd_value')
        q2_quarterly = q2_ebit.get('quarterly_value')

        if all([q1_ytd, q2_ytd, q2_quarterly]):
            expected_q2_quarterly = q2_ytd - q1_ytd
            match = abs(q2_quarterly - expected_q2_quarterly) < 1  # Allow for floating point

            print("Q2 Quarterly EBIT Calculation:")
            print(f"  Q2 YTD:           ${q2_ytd / 1e9:,.1f}B")
            print(f"  Q1 YTD:           ${q1_ytd / 1e9:,.1f}B")
            print(f"  Expected Q2 Only: ${expected_q2_quarterly / 1e9:,.1f}B")
            print(f"  Calculated Q2:    ${q2_quarterly / 1e9:,.1f}B")
            print()
            if match:
                print("✓ Calculation VERIFIED - Math is correct!")
            else:
                print("✗ Calculation ERROR - Math doesn't match!")
        else:
            print("Cannot verify - missing data")
    else:
        print("Not enough quarters to verify calculation")

    print()
    print("="*80)
    print("KEY INSIGHTS")
    print("="*80)
    print()
    print("1. YTD values are cumulative from raw 10-Q filings")
    print("2. Quarterly values are de-cumulated (current YTD - previous YTD)")
    print("3. Q1 quarterly = Q1 YTD (already isolated)")
    print("4. Balance sheet items (Debt, Cash, Assets) are NOT de-cumulated")
    print()


if __name__ == '__main__':
    main()
