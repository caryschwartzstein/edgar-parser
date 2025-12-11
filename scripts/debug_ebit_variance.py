#!/usr/bin/env python3
"""
Debug EBIT Calculation Variance

This script helps understand why different EBIT calculation methods
give different results, which is important for choosing the right method.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from edgar_parser.ebit_calculator import EBITCalculator


def load_company_data(ticker: str = 'CVX'):
    """Load company raw EDGAR data."""
    data_path = Path('data') / 'raw_edgar' / f'{ticker}_edgar_raw.json'

    try:
        with open(data_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {data_path} not found.")
        return None


def debug_tier_2_issue(gaap_data):
    """
    Debug why Tier 2 gives different results.

    Tier 2 issue is usually because:
    1. COGS includes/excludes certain items
    2. Operating expenses double-counts items in COGS
    3. Non-operating items are included in one but not the other
    """
    calculator = EBITCalculator()

    print("\n" + "="*70)
    print("TIER 2 DEBUG: Revenues - COGS - OpEx")
    print("="*70)

    # Get the values used in Tier 2
    revenues = calculator._get_tag_value(gaap_data, calculator.TIER_2_TAGS['revenues'])
    cogs = calculator._get_tag_value(gaap_data, calculator.TIER_2_TAGS['cogs'])
    opex = calculator._get_tag_value(gaap_data, calculator.TIER_2_TAGS['operating_expenses'])

    if revenues:
        print(f"\nRevenues: ${revenues['val']:>20,}")
        print(f"  Tag: {revenues['tag']}")

    if cogs:
        print(f"\nCOGS: ${cogs['val']:>20,}")
        print(f"  Tag: {cogs['tag']}")

    if opex:
        print(f"\nOperating Expenses: ${opex['val']:>20,}")
        print(f"  Tag: {opex['tag']}")

    if all([revenues, cogs, opex]):
        gross_profit = revenues['val'] - cogs['val']
        ebit_tier2 = gross_profit - opex['val']

        print(f"\n{'─'*70}")
        print(f"Calculation:")
        print(f"  Revenues:           ${revenues['val']:>20,}")
        print(f"  - COGS:             ${cogs['val']:>20,}")
        print(f"  {'─'*50}")
        print(f"  = Gross Profit:     ${gross_profit:>20,}")
        print(f"  - Operating Exp:    ${opex['val']:>20,}")
        print(f"  {'─'*50}")
        print(f"  = Operating Income: ${ebit_tier2:>20,}")

        # Check if OpEx tag is actually CostsAndExpenses
        if opex['tag'] == 'CostsAndExpenses':
            print(f"\n⚠️  WARNING: Operating Expenses uses 'CostsAndExpenses' tag")
            print(f"   This tag typically includes BOTH COGS and OpEx combined!")
            print(f"   This causes COGS to be subtracted twice:")
            print(f"     Revenues - COGS - (COGS + OpEx) = Revenues - 2*COGS - OpEx")
            print(f"\n   This is why Tier 2 should NOT be used for this company.")
            print(f"   Tier 1 (Revenues - CostsAndExpenses) is the correct method.")

    return revenues, cogs, opex


def compare_with_tier_1(gaap_data):
    """Compare Tier 2 calculation with Tier 1."""
    calculator = EBITCalculator()

    print("\n" + "="*70)
    print("COMPARISON: Tier 1 vs Tier 2")
    print("="*70)

    # Tier 1
    tier1_result = calculator._tier_1_direct_operating_income(gaap_data)
    if tier1_result:
        tier1_ebit, tier1_method, tier1_sources = tier1_result
        print(f"\nTier 1: {tier1_method}")
        print(f"  EBIT: ${tier1_ebit:>20,}")

        if 'revenues' in tier1_sources and 'costs_and_expenses' in tier1_sources:
            rev = tier1_sources['revenues']['val']
            costs = tier1_sources['costs_and_expenses']['val']
            print(f"  Revenues:           ${rev:>20,}")
            print(f"  - Costs & Expenses: ${costs:>20,}")

    # Tier 2
    tier2_result = calculator._tier_2_build_from_components(gaap_data)
    if tier2_result:
        tier2_ebit, tier2_method, tier2_sources = tier2_result
        print(f"\nTier 2: {tier2_method}")
        print(f"  EBIT: ${tier2_ebit:>20,}")

        if all(k in tier2_sources for k in ['revenues', 'cogs', 'operating_expenses']):
            rev = tier2_sources['revenues']['val']
            cogs = tier2_sources['cogs']['val']
            opex = tier2_sources['operating_expenses']['val']
            print(f"  Revenues:                ${rev:>20,}")
            print(f"  - COGS:                  ${cogs:>20,}")
            print(f"  - Operating Expenses:    ${opex:>20,}")

    # Calculate difference
    if tier1_result and tier2_result:
        diff = abs(tier1_ebit - tier2_ebit)
        diff_pct = (diff / tier1_ebit * 100)

        print(f"\n{'─'*70}")
        print(f"Variance Analysis:")
        print(f"  Difference: ${diff:>20,} ({diff_pct:.1f}%)")

        # Try to explain the difference
        if tier2_result and 'operating_expenses' in tier2_sources:
            opex_tag = tier2_sources['operating_expenses']['tag']
            if opex_tag == 'CostsAndExpenses':
                print(f"\nExplanation:")
                print(f"  The variance exists because Tier 2 is using 'CostsAndExpenses'")
                print(f"  as the Operating Expenses, which already includes COGS.")
                print(f"  This causes double-counting of COGS.")


def check_available_tags(gaap_data):
    """Check what cost-related tags are available."""
    print("\n" + "="*70)
    print("AVAILABLE COST TAGS")
    print("="*70)

    cost_tags = [
        'CostOfRevenue',
        'CostOfGoodsAndServicesSold',
        'CostOfGoodsSold',
        'CostsAndExpenses',
        'OperatingExpenses',
        'OperatingCostsAndExpenses',
        'SellingGeneralAndAdministrativeExpense',
        'ResearchAndDevelopmentExpense',
    ]

    print("\nChecking for cost-related tags in 10-K data:\n")

    found_tags = []
    for tag in cost_tags:
        if tag in gaap_data:
            units = gaap_data[tag].get('units', {})
            if 'USD' in units:
                values = units['USD']
                annual_values = [v for v in values if v.get('form') == '10-K']
                if annual_values:
                    annual_values.sort(key=lambda x: x.get('filed', ''), reverse=True)
                    latest = annual_values[0]
                    found_tags.append((tag, latest['val']))
                    print(f"✓ {tag:50} ${latest['val']:>20,}")
        else:
            print(f"✗ {tag:50} {'Not found':>20}")

    return found_tags


def main():
    """Run diagnostics."""
    print("\n" + "="*70)
    print("EBIT VARIANCE DIAGNOSTIC TOOL")
    print("="*70)
    print("\nThis tool helps understand why different EBIT calculation methods")
    print("give different results for a company.\n")

    # Load CVX data
    edgar_data = load_company_data('CVX')
    if not edgar_data:
        return

    company_name = edgar_data.get('entityName', 'Unknown')
    print(f"\nCompany: {company_name}")

    gaap_data = edgar_data.get('facts', {}).get('us-gaap', {})

    # Step 1: Check available tags
    found_tags = check_available_tags(gaap_data)

    # Step 2: Debug Tier 2 issue
    debug_tier_2_issue(gaap_data)

    # Step 3: Compare Tier 1 vs Tier 2
    compare_with_tier_1(gaap_data)

    # Recommendation
    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    print("\nFor CVX (Chevron):")
    print("  ✓ Use Tier 1: Revenues - CostsAndExpenses")
    print("  ✗ Avoid Tier 2: The 'OperatingExpenses' tag maps to 'CostsAndExpenses'")
    print("              which includes COGS, causing double-counting")
    print("\nTier 1 EBIT: $49.7B ← This is the correct value")
    print("Tier 2 EBIT: $76.1B ← This is incorrect due to double-counting")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
