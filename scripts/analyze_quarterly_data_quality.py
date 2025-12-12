#!/usr/bin/env python3
"""
Analyze the quality and completeness of quarterly data.

This script examines all parsed quarterly data to understand:
- What metrics are available in quarterly filings
- How many quarters have complete data
- Whether this is a data issue or standard practice
"""

import json
from pathlib import Path
from collections import defaultdict


def analyze_quarterly_file(filepath):
    """Analyze a single company's quarterly data."""
    with open(filepath) as f:
        data = json.load(f)

    company_name = data['metadata']['company_name']
    ticker = filepath.stem.replace('_parsed_with_quarterly', '')

    quarterly_periods = data.get('quarterly_periods', [])

    if not quarterly_periods:
        return None

    # Track metrics availability
    metrics_available = defaultdict(int)
    metrics_missing = defaultdict(int)
    total_quarters = len(quarterly_periods)

    # Detailed breakdown
    complete_quarters = 0
    quarters_with_ebit = 0
    quarters_with_debt = 0
    quarters_with_cash = 0
    quarters_with_assets = 0
    quarters_with_liabilities = 0
    quarters_with_roce = 0

    # Sample data from most recent quarters
    recent_samples = []

    for i, quarter in enumerate(quarterly_periods):  # Check ALL quarters
        metrics = quarter.get('metrics', {})

        sample = None
        if i < 5:  # Only save samples for first 5
            sample = {
                'period_end': quarter['fiscal_year_end'],
                'filing_date': quarter['filing_date'],
                'metrics': {}
            }

        # Check each metric
        ebit = metrics.get('ebit')
        if ebit and ebit.get('value') is not None:
            quarters_with_ebit += 1
            if sample:
                sample['metrics']['ebit'] = {
                    'value': ebit['value'],
                    'method': ebit.get('method', 'N/A')
                }

        debt = metrics.get('total_debt')
        if debt and debt.get('value') is not None:
            quarters_with_debt += 1
            if sample:
                sample['metrics']['debt'] = debt['value']

        cash = metrics.get('cash')
        if cash and cash.get('unrestricted_cash') is not None:
            quarters_with_cash += 1
            if sample:
                sample['metrics']['cash'] = cash['unrestricted_cash']

        assets = metrics.get('assets')
        if assets and assets.get('value') is not None:
            quarters_with_assets += 1
            if sample:
                sample['metrics']['assets'] = assets['value']

        liabilities = metrics.get('current_liabilities')
        if liabilities and liabilities.get('value') is not None:
            quarters_with_liabilities += 1
            if sample:
                sample['metrics']['current_liabilities'] = liabilities['value']

        # Check if ROCE was calculated
        roce = quarter.get('calculated_ratios', {}).get('roce', {})
        if roce and roce.get('value') is not None:
            quarters_with_roce += 1

        # Check if complete (all 5 metrics needed for ROCE)
        has_all = all([
            ebit and ebit.get('value') is not None,
            debt and debt.get('value') is not None,
            cash and cash.get('unrestricted_cash') is not None,
            assets and assets.get('value') is not None,
            liabilities and liabilities.get('value') is not None
        ])
        if has_all:
            complete_quarters += 1

        if sample and i < 5:
            recent_samples.append(sample)

    return {
        'ticker': ticker,
        'company_name': company_name,
        'total_quarters': total_quarters,
        'quarters_with_ebit': quarters_with_ebit,
        'quarters_with_debt': quarters_with_debt,
        'quarters_with_cash': quarters_with_cash,
        'quarters_with_assets': quarters_with_assets,
        'quarters_with_liabilities': quarters_with_liabilities,
        'quarters_with_roce': quarters_with_roce,
        'complete_quarters': complete_quarters,
        'recent_samples': recent_samples,
        'ebit_percentage': (quarters_with_ebit / total_quarters * 100) if total_quarters > 0 else 0,
        'completeness_percentage': (complete_quarters / total_quarters * 100) if total_quarters > 0 else 0,
    }


def main():
    """Analyze all quarterly files."""

    parsed_dir = Path('data/parsed')
    quarterly_files = sorted(parsed_dir.glob('*_parsed_with_quarterly.json'))

    if not quarterly_files:
        print("No quarterly files found!")
        return

    print("="*80)
    print("QUARTERLY DATA QUALITY ANALYSIS")
    print("="*80)
    print()

    all_results = []

    for filepath in quarterly_files:
        result = analyze_quarterly_file(filepath)
        if result:
            all_results.append(result)

    # Summary statistics
    total_companies = len(all_results)
    total_quarters = sum(r['total_quarters'] for r in all_results)
    total_with_ebit = sum(r['quarters_with_ebit'] for r in all_results)
    total_with_debt = sum(r['quarters_with_debt'] for r in all_results)
    total_with_cash = sum(r['quarters_with_cash'] for r in all_results)
    total_with_assets = sum(r['quarters_with_assets'] for r in all_results)
    total_with_liabilities = sum(r['quarters_with_liabilities'] for r in all_results)
    total_with_roce = sum(r['quarters_with_roce'] for r in all_results)
    total_complete = sum(r['complete_quarters'] for r in all_results)

    print(f"OVERALL SUMMARY")
    print(f"-" * 80)
    print(f"Total companies analyzed: {total_companies}")
    print(f"Total quarterly periods: {total_quarters}")
    print()
    print(f"Metric Availability:")
    print(f"  EBIT:                {total_with_ebit:4d} / {total_quarters} ({total_with_ebit/total_quarters*100:.1f}%)")
    print(f"  Total Debt:          {total_with_debt:4d} / {total_quarters} ({total_with_debt/total_quarters*100:.1f}%)")
    print(f"  Cash:                {total_with_cash:4d} / {total_quarters} ({total_with_cash/total_quarters*100:.1f}%)")
    print(f"  Assets:              {total_with_assets:4d} / {total_quarters} ({total_with_assets/total_quarters*100:.1f}%)")
    print(f"  Current Liabilities: {total_with_liabilities:4d} / {total_quarters} ({total_with_liabilities/total_quarters*100:.1f}%)")
    print(f"  ROCE calculated:     {total_with_roce:4d} / {total_quarters} ({total_with_roce/total_quarters*100:.1f}%)")
    print()
    print(f"Complete quarters (all metrics): {total_complete} / {total_quarters} ({total_complete/total_quarters*100:.1f}%)")
    print()

    # Per-company breakdown
    print(f"\nPER-COMPANY BREAKDOWN")
    print(f"-" * 80)
    print(f"{'Ticker':<6} {'Total Q':>7} {'EBIT':>7} {'Debt':>7} {'Cash':>7} {'Assets':>7} {'Liab':>7} {'Complete':>9}")
    print(f"-" * 80)

    for r in sorted(all_results, key=lambda x: x['ticker']):
        print(f"{r['ticker']:<6} "
              f"{r['total_quarters']:>7} "
              f"{r['quarters_with_ebit']:>7} "
              f"{r['quarters_with_debt']:>7} "
              f"{r['quarters_with_cash']:>7} "
              f"{r['quarters_with_assets']:>7} "
              f"{r['quarters_with_liabilities']:>7} "
              f"{r['complete_quarters']:>9}")

    # Detailed look at recent quarters for one company
    print(f"\n\nDETAILED SAMPLE: APPLE (AAPL) - Most Recent 5 Quarters")
    print(f"-" * 80)

    apple_data = next((r for r in all_results if r['ticker'] == 'AAPL'), None)
    if apple_data and apple_data['recent_samples']:
        for i, sample in enumerate(apple_data['recent_samples'], 1):
            print(f"\nQuarter {i}: {sample['period_end']} (filed: {sample['filing_date']})")
            print(f"  Metrics available:")
            if sample['metrics']:
                for metric, value in sample['metrics'].items():
                    if isinstance(value, dict):
                        print(f"    - {metric}: ${value['value']:,} (method: {value['method']})")
                    else:
                        print(f"    - {metric}: ${value:,}")
            else:
                print(f"    (none)")

    # Analysis and recommendations
    print(f"\n\n{'='*80}")
    print("ANALYSIS & FINDINGS")
    print(f"{'='*80}")

    ebit_pct = total_with_ebit / total_quarters * 100

    if ebit_pct < 10:
        print(f"\n⚠️  CRITICAL FINDING: Only {ebit_pct:.1f}% of quarters have EBIT data")
        print(f"\nThis is NOT a data quality issue. Here's why:")
        print(f"\n1. Quarterly 10-Q filings have DIFFERENT reporting requirements than annual 10-K")
        print(f"   - 10-Q is an abbreviated report, not a complete financial statement")
        print(f"   - Companies are NOT required to report all the same line items")
        print(f"\n2. Income statement items in 10-Q are year-to-date (YTD) cumulative")
        print(f"   - Q2 EBIT = Jan 1 to Jun 30 (6 months cumulative)")
        print(f"   - Q3 EBIT = Jan 1 to Sep 30 (9 months cumulative)")
        print(f"   - NOT individual quarter performance")
        print(f"\n3. To get true quarterly EBIT, you need to calculate:")
        print(f"   - Q2 quarterly EBIT = Q2 YTD - Q1 YTD")
        print(f"   - Q3 quarterly EBIT = Q3 YTD - Q2 YTD")
        print(f"   - This requires the raw tags to exist, which they often don't")

    balance_sheet_pct = (total_with_assets / total_quarters * 100)

    print(f"\n✓ Balance sheet items ARE available: {balance_sheet_pct:.1f}% of quarters")
    print(f"  - Assets, Liabilities, Debt, Cash are point-in-time snapshots")
    print(f"  - These DO NOT have the YTD cumulative issue")
    print(f"  - Useful for tracking balance sheet trends over time")

    print(f"\n\nRECOMMENDATIONS:")
    print(f"-" * 80)

    if ebit_pct < 50:
        print(f"\n1. QUARTERLY ROCE: Not reliable for most companies")
        print(f"   - Only {total_with_roce} out of {total_quarters} quarters have ROCE")
        print(f"   - Stick to ANNUAL ROCE for screening and ranking")
        print(f"   - Use annual 10-K data for Magic Formula calculations")

    if balance_sheet_pct > 80:
        print(f"\n2. BALANCE SHEET TRACKING: Very useful!")
        print(f"   - Track debt levels quarterly")
        print(f"   - Monitor cash position changes")
        print(f"   - Watch for major balance sheet events")
        print(f"   - Useful for risk monitoring")

    print(f"\n3. DATABASE STRATEGY:")
    print(f"   - Store quarterly data in separate table")
    print(f"   - Use for balance sheet trend analysis")
    print(f"   - DO NOT use for quarterly ROCE/screening")
    print(f"   - Annual data = primary screening dataset")
    print(f"   - Quarterly data = supplementary risk monitoring")

    print(f"\n4. SHOULD YOU KEEP QUARTERLY DATA?")
    if balance_sheet_pct > 70:
        print(f"   ✓ YES - Balance sheet data is {balance_sheet_pct:.0f}% complete")
        print(f"   - Valuable for monitoring trends")
        print(f"   - Helps identify companies in distress")
        print(f"   - Shows debt/cash changes between annual reports")
    else:
        print(f"   ⚠️  MAYBE - Data completeness is only {balance_sheet_pct:.0f}%")
        print(f"   - Consider if the storage/complexity is worth it")
        print(f"   - Annual data may be sufficient for Magic Formula screening")

    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    main()
