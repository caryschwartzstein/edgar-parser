#!/usr/bin/env python3
"""
Demonstrate YTD (Year-to-Date) cumulative accounting in quarterly 10-Q filings.

This script loads real Apple quarterly data and shows how EBIT values
are cumulative throughout the fiscal year, not isolated quarterly amounts.
"""

import json
from pathlib import Path


def main():
    """Show YTD cumulative accounting with real Apple data."""

    # Load Apple's parsed quarterly data
    apple_file = Path('data/parsed/with_quarterly_fixed/AAPL_parsed_with_quarterly.json')

    if not apple_file.exists():
        print(f"Error: {apple_file} not found")
        return

    with open(apple_file) as f:
        data = json.load(f)

    quarterly_periods = data.get('quarterly_periods', [])

    if not quarterly_periods:
        print("No quarterly periods found")
        return

    print("="*80)
    print("QUARTERLY EBIT VALUES - YTD CUMULATIVE DEMONSTRATION")
    print("="*80)
    print()
    print("Apple Inc. - Most Recent Fiscal Year Quarters")
    print()

    # Group quarters by fiscal year
    fiscal_years = {}
    for period in quarterly_periods:
        fiscal_year_end = period['fiscal_year_end']
        year = fiscal_year_end[:4]  # Extract year

        if year not in fiscal_years:
            fiscal_years[year] = []
        fiscal_years[year].append(period)

    # Get most recent fiscal year
    most_recent_year = sorted(fiscal_years.keys(), reverse=True)[0]
    recent_quarters = sorted(
        fiscal_years[most_recent_year],
        key=lambda x: x['fiscal_year_end']
    )

    print(f"Fiscal Year: {most_recent_year}")
    print("-"*80)
    print()

    # Show each quarter's EBIT value
    quarters_with_ebit = []
    for i, quarter in enumerate(recent_quarters, 1):
        period_end = quarter['fiscal_year_end']
        filing_date = quarter['filing_date']
        ebit = quarter.get('metrics', {}).get('ebit', {})
        ebit_value = ebit.get('value')

        if ebit_value is not None:
            quarters_with_ebit.append({
                'quarter': i,
                'period_end': period_end,
                'filing_date': filing_date,
                'ytd_ebit': ebit_value,
                'method': ebit.get('method', 'N/A')
            })

    if not quarters_with_ebit:
        print("No quarters with EBIT data found for this fiscal year")
        return

    # Display YTD values
    print("YEAR-TO-DATE (YTD) VALUES FROM 10-Q FILINGS:")
    print()
    format_str = "{:<8} {:<12} {:<20} {:<25}"
    print(format_str.format("Quarter", "Period End", "YTD EBIT", "Method"))
    print("-"*80)

    for q in quarters_with_ebit:
        ebit_billions = q['ytd_ebit'] / 1_000_000_000
        quarter_label = f"Q{q['quarter']}"
        ebit_display = f"${ebit_billions:,.1f}B"
        print(format_str.format(
            quarter_label,
            q['period_end'],
            ebit_display,
            q['method'][:22]
        ))

    # Calculate true quarterly values (de-cumulated)
    if len(quarters_with_ebit) > 1:
        print()
        print()
        print("TRUE QUARTERLY VALUES (De-cumulated):")
        print()
        print("To get actual quarter-specific EBIT, subtract previous YTD:")
        print()

        format_str2 = "{:<8} {:<25} {:<25} {:<20}"
        print(format_str2.format("Quarter", "Current YTD", "Previous YTD", "True Quarterly"))
        print("-"*80)

        # Q1 is already isolated (no previous quarter)
        q1 = quarters_with_ebit[0]
        q1_billions = q1['ytd_ebit'] / 1_000_000_000
        current_display = f"${q1_billions:,.1f}B"
        quarterly_display = f"${q1_billions:,.1f}B"

        print(format_str2.format(
            "Q1",
            current_display,
            "(none)",
            quarterly_display
        ))

        # Subsequent quarters need de-cumulation
        for i in range(1, len(quarters_with_ebit)):
            current = quarters_with_ebit[i]
            previous = quarters_with_ebit[i-1]

            current_billions = current['ytd_ebit'] / 1_000_000_000
            previous_billions = previous['ytd_ebit'] / 1_000_000_000
            quarterly_billions = current_billions - previous_billions

            current_display = f"${current_billions:,.1f}B"
            previous_display = f"${previous_billions:,.1f}B"
            quarterly_display = f"${quarterly_billions:,.1f}B"

            quarter_label = f"Q{current['quarter']}"

            print(format_str2.format(
                quarter_label,
                current_display,
                previous_display,
                quarterly_display
            ))

    print()
    print()
    print("="*80)
    print("KEY INSIGHTS:")
    print("="*80)
    print()
    print("1. 10-Q income statement items are CUMULATIVE (year-to-date)")
    print("   - Q1 EBIT = Oct 1 - Dec 31 (3 months)")
    print("   - Q2 EBIT = Oct 1 - Mar 31 (6 months cumulative)")
    print("   - Q3 EBIT = Oct 1 - Jun 30 (9 months cumulative)")
    print()
    print("2. To get true quarterly performance:")
    print("   - Q1 alone = Q1 YTD (already isolated)")
    print("   - Q2 alone = Q2 YTD - Q1 YTD")
    print("   - Q3 alone = Q3 YTD - Q2 YTD")
    print()
    print("3. Balance sheet items are POINT-IN-TIME (not cumulative)")
    print("   - Assets, Debt, Cash are actual values at quarter-end")
    print("   - No need to de-cumulate these metrics")
    print()
    print("4. For ROCE calculation:")
    print("   - Using YTD EBIT with point-in-time balance sheet is acceptable")
    print("   - But comparing Q2 vs Q3 ROCE requires understanding YTD vs quarterly")
    print()
    print("="*80)


if __name__ == '__main__':
    main()
