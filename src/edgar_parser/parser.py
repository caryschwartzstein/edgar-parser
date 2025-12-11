#!/usr/bin/env python3
"""
Enhanced EDGAR Parser with Earnings Yield Support
Includes EBIT, Total Debt, Cash and equivalents for EV calculation
"""

import json
from typing import Dict, Optional
from datetime import datetime
from .ebit_calculator import EBITCalculator, print_ebit_result

# Sample data now includes debt and cash metrics
SAMPLE_APPLE_DATA_ENHANCED = {
    "entityName": "Apple Inc.",
    "cik": "0000320193",
    "facts": {
        "us-gaap": {
            # ... (previous balance sheet items remain the same)
            "Assets": {
                "label": "Assets",
                "units": {"USD": [{"end": "2023-09-30", "val": 352755000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            "AssetsCurrent": {
                "label": "Assets, Current",
                "units": {"USD": [{"end": "2023-09-30", "val": 143566000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            "Liabilities": {
                "label": "Liabilities",
                "units": {"USD": [{"end": "2023-09-30", "val": 290437000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            "LiabilitiesCurrent": {
                "label": "Liabilities, Current",
                "units": {"USD": [{"end": "2023-09-30", "val": 145308000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            "StockholdersEquity": {
                "label": "Stockholders' Equity",
                "units": {"USD": [{"end": "2023-09-30", "val": 62146000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            
            # DEBT METRICS - NEW
            "LongTermDebtNoncurrent": {
                "label": "Long-term Debt",
                "units": {"USD": [{"end": "2023-09-30", "val": 95281000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            "DebtCurrent": {
                "label": "Short-term Debt",
                "units": {"USD": [{"end": "2023-09-30", "val": 9822000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            
            # CASH METRICS - NEW
            "CashAndCashEquivalentsAtCarryingValue": {
                "label": "Cash and Cash Equivalents",
                "units": {"USD": [{"end": "2023-09-30", "val": 29965000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            "CashCashEquivalentsAndShortTermInvestments": {
                "label": "Cash, Cash Equivalents and Short-term Investments",
                "units": {"USD": [{"end": "2023-09-30", "val": 61555000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            
            # Income Statement
            "Revenues": {
                "label": "Revenues",
                "units": {"USD": [{"end": "2023-09-30", "val": 383285000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            "NetIncomeLoss": {
                "label": "Net Income",
                "units": {"USD": [{"end": "2023-09-30", "val": 96995000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            "OperatingIncomeLoss": {
                "label": "Operating Income (EBIT)",
                "units": {"USD": [{"end": "2023-09-30", "val": 114301000000, "form": "10-K", "filed": "2023-11-03"}]}
            },
            
            # Shares Outstanding
            "CommonStockSharesOutstanding": {
                "label": "Common Stock, Shares Outstanding",
                "units": {"shares": [{"end": "2023-09-30", "val": 15550061000, "form": "10-K", "filed": "2023-11-03"}]}
            },
        }
    }
}


class EnhancedEDGARParser:
    """Enhanced parser with debt, cash, and earnings yield support"""

    def __init__(self):
        """Initialize the parser with EBIT calculator."""
        self.ebit_calculator = EBITCalculator()

    TAG_MAPPINGS = {
        # Balance Sheet
        'total_assets': ['Assets'],
        'current_assets': ['AssetsCurrent'],
        'total_liabilities': ['Liabilities'],
        'current_liabilities': ['LiabilitiesCurrent'],
        'stockholders_equity': ['StockholdersEquity'],
        
        # Debt Metrics (NEW)
        'short_term_debt': [
            'DebtCurrent',
            'ShortTermBorrowings',
            'ShortTermDebtAndCurrentLongTermDebt',
        ],
        'long_term_debt': [
            'LongTermDebtNoncurrent',
            'LongTermDebt',
            'LongTermDebtAndCapitalLeaseObligations',
        ],
        'total_debt': [
            'DebtLongtermAndShorttermCombinedAmount',
        ],
        
        # Cash Metrics (NEW)
        'cash_and_equivalents': [
            'CashAndCashEquivalentsAtCarryingValue',
            'Cash',
        ],
        'cash_and_short_term_investments': [
            'CashCashEquivalentsAndShortTermInvestments',
        ],
        
        # Income Statement
        'revenue': ['Revenues'],
        'net_income': ['NetIncomeLoss'],
        'operating_income': ['OperatingIncomeLoss'],  # This is EBIT
        
        # Shares
        'shares_outstanding': [
            'CommonStockSharesOutstanding',
            'CommonStockSharesIssued',
        ],
    }
    
    def extract_metric(self, facts: Dict, metric_name: str, form_type: str = "10-K", unit_type: str = "USD") -> Optional[Dict]:
        """Extract a specific metric from company facts"""
        
        for tag in self.TAG_MAPPINGS.get(metric_name, []):
            if 'us-gaap' in facts.get('facts', {}):
                gaap_facts = facts['facts']['us-gaap']
                
                if tag in gaap_facts:
                    units = gaap_facts[tag].get('units', {})
                    
                    # Handle shares vs USD
                    if metric_name == 'shares_outstanding':
                        unit_type = 'shares'
                    
                    if unit_type in units:
                        values = units[unit_type]
                        annual_values = [v for v in values if v.get('form') == form_type]
                        
                        if annual_values:
                            annual_values.sort(key=lambda x: x.get('filed', ''), reverse=True)
                            most_recent = annual_values[0]
                            
                            return {
                                'value': most_recent.get('val'),
                                'date': most_recent.get('end'),
                                'filed': most_recent.get('filed'),
                                'form': most_recent.get('form'),
                                'tag': tag,
                                'unit': unit_type
                            }
        
        return None
    
    def parse_company_data(self, edgar_data: Dict, use_enhanced_ebit: bool = True) -> Dict:
        """
        Parse EDGAR data into standardized format.

        Args:
            edgar_data: Raw EDGAR data dictionary
            use_enhanced_ebit: If True, use waterfall EBIT calculator instead of simple tag lookup

        Returns:
            Standardized data dictionary with metrics
        """
        company_name = edgar_data.get('entityName', 'Unknown')
        cik = edgar_data.get('cik', 'Unknown')

        print(f"\n{'='*70}")
        print(f"Enhanced Parsing: {company_name} (CIK: {cik})")
        print(f"{'='*70}\n")

        standardized_data = {
            'company_name': company_name,
            'cik': cik,
            'parsed_at': datetime.now().isoformat(),
            'metrics': {}
        }

        print("Extracting Financial Metrics:")
        print("-" * 70)

        # Extract all standard metrics
        for metric_name in self.TAG_MAPPINGS.keys():
            metric_data = self.extract_metric(edgar_data, metric_name)
            if metric_data:
                standardized_data['metrics'][metric_name] = metric_data

                # Format differently for shares vs currency
                if metric_data['unit'] == 'shares':
                    value_str = f"{metric_data['value']:,} shares"
                else:
                    value_str = f"${metric_data['value']:,}"

                print(f"✓ {metric_name:30} {value_str:>30} ({metric_data['date']})")
            else:
                print(f"✗ {metric_name:30} {'Not found':>30}")

        # Use enhanced EBIT calculation if requested
        if use_enhanced_ebit:
            print(f"\n{'─'*70}")
            print("Calculating EBIT using Waterfall Method:")
            print("─" * 70)

            gaap_data = edgar_data.get('facts', {}).get('us-gaap', {})
            ebit_result = self.ebit_calculator.calculate_ebit(gaap_data)

            if ebit_result:
                # Store the enhanced EBIT data
                standardized_data['metrics']['operating_income_enhanced'] = {
                    'value': ebit_result['value'],
                    'method': ebit_result['method'],
                    'tier': ebit_result['tier'],
                    'sources': ebit_result['sources'],
                    'unit': 'USD'
                }

                print(f"✓ Operating Income (EBIT):     ${ebit_result['value']:>20,}")
                print(f"  Method: {ebit_result['method']} (Tier {ebit_result['tier']})")

                # Validate the EBIT
                net_income = standardized_data['metrics'].get('net_income', {}).get('value')
                revenue = standardized_data['metrics'].get('revenue', {}).get('value')

                is_valid, msg = self.ebit_calculator.validate_ebit(
                    ebit_result['value'],
                    net_income=net_income,
                    revenues=revenue
                )

                if is_valid:
                    print(f"  ✓ Validation: {msg}")
                else:
                    print(f"  ⚠️  Validation Warning: {msg}")
            else:
                print(f"✗ Operating Income (EBIT):     Could not calculate using any method")

        return standardized_data
    
    def calculate_total_debt(self, data: Dict) -> Optional[int]:
        """Calculate total debt from short-term + long-term"""
        metrics = data.get('metrics', {})
        
        # Try to get total_debt directly
        total_debt = metrics.get('total_debt')
        if total_debt:
            return total_debt['value']
        
        # Otherwise calculate from components
        st_debt = metrics.get('short_term_debt')
        lt_debt = metrics.get('long_term_debt')
        
        if st_debt and lt_debt:
            return st_debt['value'] + lt_debt['value']
        elif lt_debt:  # Some companies have no short-term debt
            return lt_debt['value']
        
        return None
    
    def calculate_earnings_yield(self, data: Dict, market_cap: float) -> Optional[Dict]:
        """
        Calculate Earnings Yield using Greenblatt's Magic Formula

        Earnings Yield = EBIT / Enterprise Value
        Where: EV = Market Cap + Total Debt - Cash
        """
        metrics = data.get('metrics', {})

        # Get EBIT - prefer enhanced calculation, fall back to standard
        ebit_data = metrics.get('operating_income_enhanced') or metrics.get('operating_income')
        if not ebit_data:
            print("\n❌ Cannot calculate Earnings Yield - missing EBIT")
            return None
        ebit = ebit_data['value']

        # Track which EBIT method was used
        ebit_method = ebit_data.get('method', 'Standard tag lookup')
        
        # Get Total Debt
        total_debt = self.calculate_total_debt(data)
        if total_debt is None:
            print("\n❌ Cannot calculate Earnings Yield - missing debt data")
            return None
        
        # Get Cash (prefer cash + ST investments)
        cash_data = metrics.get('cash_and_short_term_investments') or \
                    metrics.get('cash_and_equivalents')
        if not cash_data:
            print("\n❌ Cannot calculate Earnings Yield - missing cash data")
            return None
        cash = cash_data['value']
        
        # Calculate Enterprise Value
        enterprise_value = market_cap + total_debt - cash
        
        if enterprise_value <= 0:
            print("\n❌ Cannot calculate Earnings Yield - invalid EV")
            return None
        
        # Calculate metrics
        earnings_yield = (ebit / enterprise_value) * 100
        ev_to_ebit = enterprise_value / ebit if ebit > 0 else None
        net_debt = total_debt - cash
        
        print(f"\n{'='*70}")
        print(f"EARNINGS YIELD CALCULATION (Greenblatt's Magic Formula)")
        print(f"{'='*70}")
        print(f"\nFormula: Earnings Yield = EBIT / Enterprise Value")
        print(f"Where: EV = Market Cap + Total Debt - Cash")
        print(f"\nInputs:")
        print(f"  EBIT (Operating Income):    ${ebit:>20,}")
        print(f"    Method: {ebit_method}")
        print(f"  Market Cap (external):      ${int(market_cap):>20,}")
        print(f"  Total Debt:                 ${total_debt:>20,}")
        print(f"  Cash & ST Investments:      ${cash:>20,}")
        print(f"  {'─'*50}")
        print(f"  Net Debt (Debt - Cash):     ${net_debt:>20,}")
        print(f"  Enterprise Value:           ${int(enterprise_value):>20,}")
        print(f"\nResults:")
        print(f"  Earnings Yield:             {earnings_yield:>20.2f}%")
        print(f"  EV/EBIT Multiple:           {ev_to_ebit:>20.2f}x")
        print(f"\nInterpretation:")
        print(f"  • Earnings Yield > 8-10% typically indicates potential bargain")
        print(f"  • Compare to 10-year Treasury rate (~4-5% currently)")
        print(f"  • Higher earnings yield = cheaper valuation")
        
        return {
            'ebit': ebit,
            'market_cap': market_cap,
            'total_debt': total_debt,
            'cash': cash,
            'net_debt': net_debt,
            'enterprise_value': enterprise_value,
            'earnings_yield': earnings_yield,
            'ev_to_ebit': ev_to_ebit,
        }
    
    def calculate_roce(self, data: Dict) -> Optional[float]:
        """Calculate Return on Capital Employed (ROCE)"""
        metrics = data.get('metrics', {})
        
        operating_income = metrics.get('operating_income')
        total_assets = metrics.get('total_assets')
        current_liabilities = metrics.get('current_liabilities')
        
        if not all([operating_income, total_assets, current_liabilities]):
            print("\n❌ Cannot calculate ROCE - missing required metrics")
            return None
        
        ebit = operating_income['value']
        assets = total_assets['value']
        curr_liab = current_liabilities['value']
        
        capital_employed = assets - curr_liab
        
        if capital_employed <= 0:
            print("\n❌ Cannot calculate ROCE - invalid capital employed")
            return None
        
        roce = (ebit / capital_employed) * 100
        
        print(f"\n{'='*70}")
        print(f"ROCE CALCULATION")
        print(f"{'='*70}")
        print(f"\nFormula: ROCE = EBIT / (Total Assets - Current Liabilities)")
        print(f"\nInputs:")
        print(f"  Operating Income (EBIT):    ${ebit:>20,}")
        print(f"  Total Assets:               ${assets:>20,}")
        print(f"  Current Liabilities:        ${curr_liab:>20,}")
        print(f"  {'─'*50}")
        print(f"  Capital Employed:           ${capital_employed:>20,}")
        print(f"\nResult:")
        print(f"  ROCE:                       {roce:>20.2f}%")
        print(f"\nInterpretation:")
        print(f"  • ROCE > 15% = good company")
        print(f"  • ROCE > 25% = excellent company")
        print(f"  • Compare to sector median")
        
        return roce


def demonstrate_enhanced_parsing():
    """Run demonstration with earnings yield calculation"""
    
    print("\n" + "="*70)
    print("ENHANCED EDGAR PARSER - WITH EARNINGS YIELD SUPPORT")
    print("="*70)
    print("\nThis demo shows:")
    print("  1. Extracting debt metrics (short-term + long-term)")
    print("  2. Extracting cash metrics")
    print("  3. Calculating Enterprise Value")
    print("  4. Calculating Earnings Yield (Greenblatt's Magic Formula)")
    print("  5. Calculating ROCE")
    print("\nUsing real Apple Inc. FY2023 data from 10-K filing")
    
    parser = EnhancedEDGARParser()
    
    # Parse the data
    standardized_data = parser.parse_company_data(SAMPLE_APPLE_DATA_ENHANCED)
    
    # Save standardized data
    output_file = "data/apple_parsed_data_enhanced.json"
    with open(output_file, 'w') as f:
        json.dump(standardized_data, f, indent=2)
    print(f"\n✓ Standardized data saved to: {output_file}")
    
    # Calculate ROCE
    roce = parser.calculate_roce(standardized_data)
    
    # Calculate Earnings Yield
    # Note: Market cap must come from external source (Yahoo Finance, etc.)
    # Using Apple's market cap as of Nov 2023 (~$2.95T)
    market_cap_nov_2023 = 2_945_000_000_000  # $2.945 trillion
    
    ey_result = parser.calculate_earnings_yield(standardized_data, market_cap_nov_2023)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY - Apple Inc. (FY 2023)")
    print(f"{'='*70}")
    print(f"\nQuality Metric:")
    if roce:
        print(f"  ROCE:              {roce:>10.2f}%  ← High quality business")
    
    print(f"\nValuation Metrics:")
    if ey_result:
        print(f"  Earnings Yield:    {ey_result['earnings_yield']:>10.2f}%")
        print(f"  EV/EBIT:           {ey_result['ev_to_ebit']:>10.2f}x")
        print(f"  Net Debt:          ${ey_result['net_debt']:>10,}")
    
    print(f"\nGreenblatt Magic Formula Interpretation:")
    if roce and ey_result:
        if roce > 25:
            quality = "Excellent"
        elif roce > 15:
            quality = "Good"
        else:
            quality = "Average"
        
        if ey_result['earnings_yield'] > 10:
            valuation = "Bargain"
        elif ey_result['earnings_yield'] > 6:
            valuation = "Fair"
        else:
            valuation = "Expensive"
        
        print(f"  Quality:           {quality} (ROCE {roce:.1f}%)")
        print(f"  Valuation:         {valuation} (EY {ey_result['earnings_yield']:.1f}%)")
        print(f"\n  Overall: High quality company trading at premium valuation")
        print(f"  This is typical for Apple - market pays up for quality")
    
    print(f"\n{'='*70}")
    print(f"DATA SOURCES NEEDED:")
    print(f"{'='*70}")
    print("""
From EDGAR (✅ We have):
  • EBIT (Operating Income)
  • Total Debt (Short-term + Long-term)
  • Cash and Cash Equivalents
  • All balance sheet items
  • Shares outstanding (sometimes)

From Market Data (❌ Need external API):
  • Current Stock Price
  • Market Capitalization
  • Or: Stock Price + Shares Outstanding

Recommended Market Data Sources:
  • Yahoo Finance API (yfinance library) - Free
  • Alpha Vantage - Free tier available
  • Financial Modeling Prep - $15/month
""")
    
    return standardized_data, roce, ey_result


if __name__ == "__main__":
    demonstrate_enhanced_parsing()
