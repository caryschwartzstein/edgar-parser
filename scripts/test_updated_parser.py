#!/usr/bin/env python3
"""
Test script for the updated EDGAR Parser V2

Tests the parser with all the new calculators to ensure everything works correctly.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from edgar_parser.parser_v2 import EDGARParser


def test_parser_with_sample_data():
    """Test the parser with a sample EDGAR data file if available."""

    print("\n" + "="*80)
    print("EDGAR PARSER V2 - TEST SCRIPT")
    print("="*80)
    print("\nThis script tests the updated parser with all new calculators:")
    print("  - EBIT Calculator (4-tier waterfall with validation)")
    print("  - Debt Calculator (3-component structure)")
    print("  - Cash Calculator (restricted vs unrestricted)")
    print("  - Balance Sheet Calculator (assets & liabilities)")
    print("  - ROCE calculation")
    print("  - Earnings Yield components calculation")
    print("\n" + "="*80 + "\n")

    # Look for sample data files
    data_dir = Path(__file__).parent.parent / "data"

    # Try to find any .json files in the data directory
    if data_dir.exists():
        json_files = list(data_dir.glob("*.json"))

        if json_files:
            print(f"Found {len(json_files)} data file(s) in {data_dir}\n")

            # Test with the first file
            test_file = json_files[0]
            print(f"Testing with: {test_file.name}\n")

            try:
                with open(test_file) as f:
                    edgar_data = json.load(f)

                # Initialize parser
                parser = EDGARParser()

                # Parse the data
                result = parser.parse_company_data(edgar_data, verbose=True)

                # Save the output
                output_dir = data_dir / "parsed"
                output_dir.mkdir(exist_ok=True)

                output_file = output_dir / f"{test_file.stem}_parsed_v2.json"
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)

                print(f"\n{'='*80}")
                print("TEST SUCCESSFUL!")
                print(f"{'='*80}")
                print(f"\nParsed data saved to: {output_file}")
                print(f"\nYou can inspect the output to see:")
                print("  - All historical periods extracted")
                print("  - Detailed metric calculations for each period")
                print("  - ROCE values with interpretations")
                print("  - Earnings Yield components (ready for Market Cap)")
                print("  - Comprehensive calculation logs")

                # Print some sample output details
                if result['annual_periods']:
                    most_recent = result['annual_periods'][0]
                    print(f"\n{'='*80}")
                    print("MOST RECENT PERIOD DETAILS")
                    print(f"{'='*80}\n")

                    print(f"Fiscal Year End: {most_recent['fiscal_year_end']}")
                    print(f"Filing Date: {most_recent['filing_date']}\n")

                    # Print metric values
                    print("Extracted Metrics:")
                    print("-" * 80)

                    metrics = most_recent.get('metrics', {})

                    if 'ebit' in metrics:
                        ebit = metrics['ebit']
                        print(f"  EBIT: ${ebit['value']:,.0f}")
                        print(f"    Method: {ebit['method']} (Tier {ebit['tier']})")
                        if ebit.get('validation'):
                            print(f"    Validation: {ebit['validation']}")

                    if 'total_debt' in metrics:
                        debt = metrics['total_debt']
                        print(f"\n  Total Debt: ${debt['value']:,.0f}")
                        print(f"    Method: {debt['method']}")
                        if debt.get('warnings'):
                            for warning in debt['warnings']:
                                print(f"    Warning: {warning}")

                    if 'cash' in metrics:
                        cash = metrics['cash']
                        print(f"\n  Cash (Unrestricted): ${cash['unrestricted_cash']:,.0f}")
                        print(f"  Cash (Total): ${cash['total_cash']:,.0f}")
                        if cash.get('restricted_cash'):
                            print(f"  Cash (Restricted): ${cash['restricted_cash']:,.0f}")
                        print(f"    Method: {cash['method']}")

                    if 'assets' in metrics:
                        assets = metrics['assets']
                        print(f"\n  Total Assets: ${assets['value']:,.0f}")
                        print(f"    Method: {assets['method']}")

                    if 'current_liabilities' in metrics:
                        curr_liab = metrics['current_liabilities']
                        print(f"\n  Current Liabilities: ${curr_liab['value']:,.0f}")
                        print(f"    Method: {curr_liab['method']}")

                    # Print calculated ratios
                    print(f"\n{'='*80}")
                    print("Calculated Ratios:")
                    print("-" * 80)

                    ratios = most_recent.get('calculated_ratios', {})

                    if 'roce' in ratios:
                        roce = ratios['roce']
                        if roce.get('value'):
                            print(f"\n  ROCE: {roce['value']:.2f}%")
                            print(f"    Formula: {roce['formula']}")
                            print(f"    {roce['where']}")
                            print(f"    Capital Employed: ${roce['components']['capital_employed']:,.0f}")
                            print(f"    Interpretation: {roce['interpretation']}")
                        else:
                            print(f"\n  ROCE: Could not calculate ({roce.get('status')})")

                    if 'earnings_yield_components' in ratios:
                        ey = ratios['earnings_yield_components']
                        if ey.get('status') == 'success':
                            print(f"\n  Earnings Yield Components:")
                            print(f"    EBIT: ${ey['ebit']:,.0f}")
                            print(f"    Total Debt: ${ey['total_debt']:,.0f}")
                            print(f"    Unrestricted Cash: ${ey['unrestricted_cash']:,.0f}")
                            print(f"    Net Debt: ${ey['net_debt']:,.0f}")
                            print(f"    Formula: {ey['formula']}")
                            print(f"    Note: {ey['note']}")
                        else:
                            print(f"\n  Earnings Yield: Could not calculate ({ey.get('status')})")

                return True

            except Exception as e:
                print(f"\n{'='*80}")
                print("TEST FAILED!")
                print(f"{'='*80}")
                print(f"\nError: {str(e)}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print(f"No JSON data files found in {data_dir}")
            print("\nTo test the parser, please:")
            print("  1. Download EDGAR company facts data (JSON format)")
            print("  2. Place the file in the 'data' directory")
            print("  3. Run this script again")
            return False
    else:
        print(f"Data directory not found: {data_dir}")
        print("\nPlease create the 'data' directory and add EDGAR JSON files.")
        return False


if __name__ == "__main__":
    success = test_parser_with_sample_data()
    sys.exit(0 if success else 1)
