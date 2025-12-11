#!/usr/bin/env python3
"""
Diagnostic script to investigate parsing issues
Shows what data is available in EDGAR and what we're actually extracting
"""

import json
import sys
from pathlib import Path
from typing import Dict
import requests
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.edgar_parser.config import config


def fetch_and_analyze(ticker: str, cik: str):
    """Fetch and analyze EDGAR data for a company"""

    print(f"\n{'='*80}")
    print(f"DIAGNOSTIC REPORT: {ticker}")
    print(f"{'='*80}\n")

    # Fetch data
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    headers = {'User-Agent': config.EDGAR_USER_AGENT}

    print(f"Fetching: {url}")
    response = requests.get(url, headers=headers)
    data = response.json()

    print(f"✓ Entity: {data.get('entityName')}")
    print(f"✓ CIK: {data.get('cik')}")
    print(f"✓ Total GAAP tags available: {len(data['facts']['us-gaap'])}\n")

    # Check for operating income alternatives
    print("="*80)
    print("ISSUE 1: Operating Income / EBIT Tag Search")
    print("="*80)

    operating_income_tags = [
        'OperatingIncomeLoss',
        'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
        'EarningsBeforeInterestAndTaxes',
    ]

    found_ebit = False
    for tag in operating_income_tags:
        if tag in data['facts']['us-gaap']:
            found_ebit = True
            tag_data = data['facts']['us-gaap'][tag]
            print(f"\n✓ Found: {tag}")
            print(f"  Label: {tag_data.get('label', 'N/A')}")

            # Show recent 10-K values
            if 'USD' in tag_data['units']:
                annual_vals = [v for v in tag_data['units']['USD'] if v.get('form') == '10-K']
                if annual_vals:
                    print(f"  Recent 10-K filings:")
                    for v in sorted(annual_vals, key=lambda x: x['end'], reverse=True)[:5]:
                        print(f"    {v['end']:12} (filed {v['filed']}): ${v['val']:>15,}")
        else:
            print(f"✗ Not found: {tag}")

    if not found_ebit:
        print("\n⚠ WARNING: No operating income/EBIT tag found!")
        print("  This company may use non-standard tags.")

    # Check date consistency
    print(f"\n{'='*80}")
    print("ISSUE 2: Date Consistency Across Metrics")
    print("="*80)

    key_metrics = {
        'Total Assets': 'Assets',
        'Current Liabilities': 'LiabilitiesCurrent',
        'Operating Income': 'OperatingIncomeLoss',
        'Net Income': 'NetIncomeLoss',
        'Revenue': 'Revenues'
    }

    print("\nMost recent 10-K for each metric:")
    print(f"{'Metric':<25} {'Date (end)':<15} {'Filed':<15} {'Value':>20}")
    print("-"*80)

    for metric_name, tag in key_metrics.items():
        if tag in data['facts']['us-gaap']:
            tag_data = data['facts']['us-gaap'][tag]
            if 'USD' in tag_data['units']:
                annual_vals = [v for v in tag_data['units']['USD'] if v.get('form') == '10-K']
                if annual_vals:
                    # Sort by FILED date (what current parser does)
                    by_filed = sorted(annual_vals, key=lambda x: x.get('filed', ''), reverse=True)[0]
                    print(f"{metric_name:<25} {by_filed['end']:<15} {by_filed['filed']:<15} ${by_filed['val']:>19,}")

    print(f"\n⚠ NOTICE: Different metrics may have different 'end' dates even though")
    print(f"  they're from the same 10-K filing!")
    print(f"  This happens when companies amend/restate previous filings.")

    # Check ALL available 10-K filings
    print(f"\n{'='*80}")
    print("ISSUE 3: All Available 10-K Filings")
    print("="*80)

    if 'Assets' in data['facts']['us-gaap']:
        assets = data['facts']['us-gaap']['Assets']
        if 'USD' in assets['units']:
            annual_vals = [v for v in assets['units']['USD'] if v.get('form') == '10-K']

            # Group by unique end dates
            by_end_date = {}
            for v in annual_vals:
                end_date = v['end']
                if end_date not in by_end_date:
                    by_end_date[end_date] = []
                by_end_date[end_date].append(v)

            print(f"\nTotal unique fiscal year ends: {len(by_end_date)}")
            print(f"Total 10-K data points: {len(annual_vals)}")
            print(f"\nRecent fiscal years (with all filings):")
            print(f"{'Fiscal Year End':<20} {'Filed Date':<15} {'Total Assets':>20}")
            print("-"*60)

            for end_date in sorted(by_end_date.keys(), reverse=True)[:5]:
                filings = sorted(by_end_date[end_date], key=lambda x: x['filed'], reverse=True)
                for i, filing in enumerate(filings):
                    marker = " ← MOST RECENT FILING" if i == 0 else " (amended/restated)"
                    print(f"{end_date:<20} {filing['filed']:<15} ${filing['val']:>19,}{marker}")
                if len(filings) > 1:
                    print()

    print(f"\n⚠ NOTICE: Multiple filings for same fiscal year indicate amendments.")
    print(f"  Current parser selects by most recent FILED date.")

    # Show what's in our parsed JSON
    print(f"\n{'='*80}")
    print("ISSUE 4: What We Actually Extracted")
    print("="*80)

    parsed_file = Path(f"data/parsed/{ticker}_parsed.json")
    if parsed_file.exists():
        with open(parsed_file) as f:
            parsed_data = json.load(f)

        print(f"\nFrom {parsed_file}:")
        print(f"{'Metric':<30} {'Date':<15} {'Value':>20} {'XBRL Tag':<30}")
        print("-"*100)

        for metric_name, metric_data in parsed_data['metrics'].items():
            if metric_data.get('unit') == 'USD':
                print(f"{metric_name:<30} {metric_data['date']:<15} ${metric_data['value']:>19,} {metric_data['tag']:<30}")
            else:
                print(f"{metric_name:<30} {metric_data['date']:<15} {metric_data['value']:>20,} {metric_data['tag']:<30}")

        print(f"\nCalculated ROCE: {parsed_data['calculated_ratios'].get('roce', 'N/A')}")

        # Check for date mismatches
        dates = [m['date'] for m in parsed_data['metrics'].values()]
        unique_dates = set(dates)
        if len(unique_dates) > 1:
            print(f"\n⚠ WARNING: Metrics from different fiscal periods detected!")
            print(f"  Unique dates: {sorted(unique_dates, reverse=True)}")
            print(f"  This could lead to incorrect ROCE calculations!")
    else:
        print(f"\n✗ No parsed file found at {parsed_file}")

    # Recommendations
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print("="*80)
    print("""
1. ADD ALTERNATIVE TAGS FOR OPERATING INCOME:
   - Current: OperatingIncomeLoss
   - Add: IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterest...
   - Add: EarningsBeforeInterestAndTaxes

2. FIX DATE CONSISTENCY:
   - Current approach: Sort by 'filed' date, take most recent
   - Problem: Gets metrics from different fiscal periods
   - Solution: Group by 'end' date (fiscal year), then take most recent filing

3. STORE HISTORICAL DATA:
   - Currently: Only stores most recent period
   - Enhancement: Store all historical periods for time-series analysis

4. HANDLE AMENDMENTS:
   - Currently: Implicitly handles by taking most recent filed
   - Enhancement: Flag when using amended data
""")


def main():
    """Run diagnostics on CVX and XOM"""

    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                      EDGAR PARSING DIAGNOSTIC TOOL                         ║
║                                                                            ║
║  This script investigates:                                                 ║
║    1. Why CVX/XOM are missing operating income                            ║
║    2. Whether we're pulling the most recent data                          ║
║    3. Annual vs quarterly data                                            ║
║    4. Date consistency across metrics                                     ║
╚════════════════════════════════════════════════════════════════════════════╝
""")

    # Load company list
    df = pd.read_csv('data/target_companies.csv')

    # Analyze CVX
    cvx = df[df['ticker'] == 'CVX'].iloc[0]
    fetch_and_analyze('CVX', cvx['cik'])

    print("\n" + "="*80)
    input("\nPress Enter to analyze XOM...")

    # Analyze XOM
    xom = df[df['ticker'] == 'XOM'].iloc[0]
    fetch_and_analyze('XOM', xom['cik'])

    print("\n" + "="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
