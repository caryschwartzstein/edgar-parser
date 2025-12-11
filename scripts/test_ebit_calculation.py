#!/usr/bin/env python3
"""
Test EBIT Calculation with CVX Data

This script tests the enhanced EBIT calculation waterfall approach
using real CVX (Chevron) data from EDGAR.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from edgar_parser.ebit_calculator import EBITCalculator, print_ebit_result, print_comparison_result


def load_cvx_data():
    """Load CVX raw EDGAR data."""
    data_path = Path('data') / 'raw_edgar' / 'CVX_edgar_raw.json'

    try:
        print(f"Loading data from {data_path}")
        with open(data_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {data_path} not found.")
        print("Please ensure the CVX data file exists.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON - {e}")
        sys.exit(1)


def test_single_ebit_calculation():
    """Test calculating EBIT using the waterfall method."""
    print("\n" + "="*70)
    print("TEST 1: Single EBIT Calculation (Waterfall Method)")
    print("="*70)

    # Load data
    edgar_data = load_cvx_data()
    company_name = edgar_data.get('entityName', 'Unknown')

    # Extract GAAP data
    gaap_data = edgar_data.get('facts', {}).get('us-gaap', {})

    # Calculate EBIT
    calculator = EBITCalculator()
    result = calculator.calculate_ebit(gaap_data)

    # Print result
    print_ebit_result(result, company_name)

    if result:
        print(f"\n✓ Successfully calculated EBIT: ${result['value']:,.0f}")
        print(f"  Using method: {result['method']} (Tier {result['tier']})")
        return result
    else:
        print(f"\n✗ Failed to calculate EBIT")
        return None


def test_all_methods_comparison():
    """Test all EBIT calculation methods and compare results."""
    print("\n" + "="*70)
    print("TEST 2: Compare All EBIT Calculation Methods")
    print("="*70)

    # Load data
    edgar_data = load_cvx_data()
    company_name = edgar_data.get('entityName', 'Unknown')

    # Extract GAAP data
    gaap_data = edgar_data.get('facts', {}).get('us-gaap', {})

    # Compare all methods
    calculator = EBITCalculator()
    comparison = calculator.compare_methods(gaap_data)

    # Print comparison
    print_comparison_result(comparison, company_name)

    return comparison


def test_validation():
    """Test EBIT validation."""
    print("\n" + "="*70)
    print("TEST 3: EBIT Validation")
    print("="*70)

    # Load data
    edgar_data = load_cvx_data()
    gaap_data = edgar_data.get('facts', {}).get('us-gaap', {})

    # Calculate EBIT
    calculator = EBITCalculator()
    result = calculator.calculate_ebit(gaap_data)

    if not result:
        print("\n✗ Cannot test validation - EBIT calculation failed")
        return

    ebit = result['value']

    # Try to get net income and revenue for validation
    def get_tag_value(tag_list):
        for tag in tag_list:
            if tag in gaap_data:
                units = gaap_data[tag].get('units', {})
                if 'USD' in units:
                    values = units['USD']
                    annual_values = [v for v in values if v.get('form') == '10-K']
                    if annual_values:
                        annual_values.sort(key=lambda x: x.get('filed', ''), reverse=True)
                        return annual_values[0].get('val')
        return None

    net_income = get_tag_value(['NetIncomeLoss', 'ProfitLoss'])
    revenues = get_tag_value(['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax'])

    print(f"\nValidation Inputs:")
    print(f"  EBIT:       ${ebit:>20,}")
    if net_income:
        print(f"  Net Income: ${net_income:>20,}")
    else:
        print(f"  Net Income: {'Not available':>20}")
    if revenues:
        print(f"  Revenues:   ${revenues:>20,}")
    else:
        print(f"  Revenues:   {'Not available':>20}")

    # Validate
    is_valid, message = calculator.validate_ebit(ebit, net_income=net_income, revenues=revenues)

    print(f"\nValidation Result:")
    if is_valid:
        print(f"  ✓ {message}")
    else:
        print(f"  ✗ {message}")

    # Additional checks
    if revenues and ebit:
        margin = (ebit / revenues) * 100
        print(f"\nOperating Margin: {margin:.2f}%")

        if 5 <= margin <= 30:
            print(f"  ✓ Margin is within typical range (5-30%)")
        else:
            print(f"  ⚠️  Margin is outside typical range")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("EBIT CALCULATION TEST SUITE - CVX (Chevron)")
    print("="*70)
    print("\nThis test suite validates the waterfall EBIT calculation approach")
    print("using real CVX data from EDGAR.\n")

    # Test 1: Single calculation
    result = test_single_ebit_calculation()

    # Test 2: Compare all methods
    comparison = test_all_methods_comparison()

    # Test 3: Validation
    test_validation()

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    if result:
        print(f"\n✓ EBIT Calculation: SUCCESS")
        print(f"  Value: ${result['value']:,.0f}")
        print(f"  Method: {result['method']}")
        print(f"  Tier: {result['tier']}")
    else:
        print(f"\n✗ EBIT Calculation: FAILED")

    if comparison:
        num_methods = sum(1 for key in ['tier_1', 'tier_2', 'tier_3', 'tier_4'] if key in comparison)
        print(f"\n✓ Method Comparison: {num_methods} method(s) available")

        if 'variance' in comparison:
            var_pct = comparison['variance']['variance_pct']
            if var_pct <= 10:
                print(f"  ✓ Variance: {var_pct:.2f}% (acceptable)")
            else:
                print(f"  ⚠️  Variance: {var_pct:.2f}% (needs review)")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
