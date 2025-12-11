#!/usr/bin/env python3
"""
Company Data Inspector
Helps verify parsed data against raw EDGAR data
Shows all available tags and values for manual verification
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

def inspect_company(ticker: str):
    """Inspect both raw and parsed data for a company"""

    raw_file = Path(f"data/raw_edgar/{ticker}_edgar_raw.json")
    parsed_file = Path(f"data/parsed/{ticker}_parsed.json")

    if not raw_file.exists():
        print(f"❌ Raw EDGAR file not found: {raw_file}")
        print(f"   Run: python scripts/parse_test_companies.py first")
        return

    if not parsed_file.exists():
        print(f"❌ Parsed file not found: {parsed_file}")
        return

    # Load both files
    with open(raw_file) as f:
        raw = json.load(f)
    with open(parsed_file) as f:
        parsed = json.load(f)

    company_name = raw.get('entityName', 'Unknown')
    cik = raw.get('cik', 'Unknown')

    print("\n" + "="*80)
    print(f"COMPANY DATA INSPECTOR: {ticker}")
    print("="*80)
    print(f"Company: {company_name}")
    print(f"CIK: {cik}")

    # Show parsed summary
    most_recent = parsed['annual_periods'][0]
    print(f"\n{'='*80}")
    print("PARSED DATA SUMMARY (Most Recent Period)")
    print("="*80)
    print(f"Fiscal Year End: {most_recent['fiscal_year_end']}")
    print(f"Filing Date: {most_recent['filing_date']}")
    print(f"ROCE: {most_recent['calculated_ratios'].get('roce', 'N/A'):.2f}%" if most_recent['calculated_ratios'].get('roce') else "ROCE: N/A")

    print(f"\n{'Metric':<30} {'Value':>20} {'Date':<15} {'XBRL Tag':<50}")
    print("-"*120)
    for metric_name, metric_data in sorted(most_recent['metrics'].items()):
        if metric_data['unit'] == 'USD':
            value_str = f"${metric_data['value']/1e9:>8.2f}B"
        else:
            value_str = f"{metric_data['value']:>15,}"
        print(f"{metric_name:<30} {value_str:>20} {metric_data['date']:<15} {metric_data['tag']:<50}")

    # Show ALL available tags in raw data
    print(f"\n{'='*80}")
    print("ALL AVAILABLE US-GAAP TAGS IN RAW EDGAR DATA")
    print("="*80)

    gaap_tags = list(raw['facts']['us-gaap'].keys())
    print(f"Total tags available: {len(gaap_tags)}")

    # Categorize tags
    income_tags = [t for t in gaap_tags if any(x in t for x in ['Income', 'Revenue', 'Earnings', 'Profit', 'Loss'])]
    balance_tags = [t for t in gaap_tags if any(x in t for x in ['Asset', 'Liability', 'Equity', 'Debt', 'Cash'])]

    print(f"\nIncome statement related tags: {len(income_tags)}")
    print(f"Balance sheet related tags: {len(balance_tags)}")

    # Show income statement tags with recent values
    print(f"\n{'─'*80}")
    print("KEY INCOME STATEMENT TAGS (with most recent 10-K value):")
    print("─"*80)

    key_income_tags = [
        'Revenues',
        'OperatingIncomeLoss',
        'NetIncomeLoss',
        'EarningsPerShareBasic',
        'EarningsPerShareDiluted',
        'GrossProfit',
        'CostOfGoodsAndServicesSold',
        'OperatingExpenses',
        'ResearchAndDevelopmentExpense',
        'SellingGeneralAndAdministrativeExpense',
        'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
    ]

    for tag in key_income_tags:
        if tag in raw['facts']['us-gaap']:
            tag_data = raw['facts']['us-gaap'][tag]
            label = tag_data.get('label', tag)

            if 'USD' in tag_data.get('units', {}):
                annual_vals = [v for v in tag_data['units']['USD'] if v.get('form') == '10-K']
                if annual_vals:
                    recent = sorted(annual_vals, key=lambda x: x['end'], reverse=True)[0]
                    value = recent['val']
                    if value > 1e9:
                        value_str = f"${value/1e9:>10.2f}B"
                    elif value > 1e6:
                        value_str = f"${value/1e6:>10.2f}M"
                    else:
                        value_str = f"${value:>15,.0f}"

                    used = "✓ USED" if tag in [m['tag'] for m in most_recent['metrics'].values()] else ""
                    print(f"  {tag:<70} {value_str:>20} {recent['end']:<15} {used}")

    # Show balance sheet tags
    print(f"\n{'─'*80}")
    print("KEY BALANCE SHEET TAGS (with most recent 10-K value):")
    print("─"*80)

    key_balance_tags = [
        'Assets',
        'AssetsCurrent',
        'Liabilities',
        'LiabilitiesCurrent',
        'StockholdersEquity',
        'LongTermDebtNoncurrent',
        'DebtCurrent',
        'CashAndCashEquivalentsAtCarryingValue',
        'CashCashEquivalentsAndShortTermInvestments',
        'PropertyPlantAndEquipmentNet',
        'Goodwill',
        'IntangibleAssetsNetExcludingGoodwill',
    ]

    for tag in key_balance_tags:
        if tag in raw['facts']['us-gaap']:
            tag_data = raw['facts']['us-gaap'][tag]
            label = tag_data.get('label', tag)

            if 'USD' in tag_data.get('units', {}):
                annual_vals = [v for v in tag_data['units']['USD'] if v.get('form') == '10-K']
                if annual_vals:
                    recent = sorted(annual_vals, key=lambda x: x['end'], reverse=True)[0]
                    value = recent['val']
                    value_str = f"${value/1e9:>10.2f}B" if value > 1e9 else f"${value/1e6:>10.2f}M"

                    used = "✓ USED" if tag in [m['tag'] for m in most_recent['metrics'].values()] else ""
                    print(f"  {tag:<70} {value_str:>20} {recent['end']:<15} {used}")

    # Show calculation verification
    print(f"\n{'='*80}")
    print("ROCE CALCULATION VERIFICATION")
    print("="*80)

    if 'calculation_log' in most_recent:
        calc_log = most_recent['calculation_log']['calculations'].get('roce', {})

        if calc_log.get('status') != 'failed':
            print(f"\nFormula: {calc_log['formula']}")
            print(f"Where: {calc_log['where']}")
            print(f"\nInputs:")
            for input_name, input_data in calc_log['inputs'].items():
                print(f"  {input_name:<30}: {input_data['formatted']:<20} (XBRL: {input_data['xbrl_tag']})")

            print(f"\nIntermediate:")
            if 'intermediate_calculations' in calc_log:
                for calc_name, calc_data in calc_log['intermediate_calculations'].items():
                    print(f"  {calc_name:<30}: {calc_data.get('calculation', 'N/A')}")
                    print(f"  {'':30}  = {calc_data.get('formatted', 'N/A')}")

            print(f"\nFinal:")
            if 'final_calculation' in calc_log:
                print(f"  {calc_log['final_calculation'].get('calculation', 'N/A')}")
                print(f"  = {calc_log['final_calculation'].get('formatted', 'N/A')}")

            print(f"\nInterpretation: {calc_log.get('interpretation', 'N/A')}")
            print(f"Date Consistency: {calc_log.get('date_consistency', 'Unknown')}")
        else:
            print(f"\n❌ ROCE Calculation Failed")
            print(f"Reason: {calc_log.get('reason', 'Unknown')}")

    # Show historical trend
    print(f"\n{'='*80}")
    print("HISTORICAL ROCE TREND")
    print("="*80)
    print(f"\n{'Fiscal Year End':<20} {'ROCE':>10} {'Operating Income':>20} {'Capital Employed':>20}")
    print("-"*75)

    for period in parsed['annual_periods'][:10]:  # Show last 10 years
        fy = period['fiscal_year_end']
        roce = period['calculated_ratios'].get('roce')

        if roce and 'operating_income' in period['metrics']:
            op_inc = period['metrics']['operating_income']['value']
            assets = period['metrics'].get('total_assets', {}).get('value', 0)
            curr_liab = period['metrics'].get('current_liabilities', {}).get('value', 0)
            cap_emp = assets - curr_liab if assets and curr_liab else 0

            print(f"{fy:<20} {roce:>9.2f}% ${op_inc/1e9:>10.2f}B ${cap_emp/1e9:>18.2f}B")

    print(f"\n{'='*80}")
    print("FILES SAVED")
    print("="*80)
    print(f"Raw EDGAR data: {raw_file}")
    print(f"Parsed data:    {parsed_file}")
    print(f"\nYou can inspect these files directly to verify the numbers.")


def list_available_companies():
    """List all companies that have been parsed"""
    raw_dir = Path("data/raw_edgar")

    if not raw_dir.exists() or not list(raw_dir.glob("*_edgar_raw.json")):
        print("No companies parsed yet.")
        print("Run: python scripts/parse_test_companies.py first")
        return

    print("\nAvailable companies for inspection:")
    for file in sorted(raw_dir.glob("*_edgar_raw.json")):
        ticker = file.stem.replace("_edgar_raw", "")
        print(f"  - {ticker}")
    print("\nUsage: python scripts/inspect_company_data.py <TICKER>")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/inspect_company_data.py <TICKER>")
        print("Example: python scripts/inspect_company_data.py AAPL")
        list_available_companies()
        return

    ticker = sys.argv[1].upper()
    inspect_company(ticker)


if __name__ == '__main__':
    main()
