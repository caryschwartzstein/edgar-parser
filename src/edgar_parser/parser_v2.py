#!/usr/bin/env python3
"""
EDGAR Parser V2 - Complete Financial Metrics Extraction

Implements the comprehensive financial metrics extraction strategy from the guide.

Calculates:
- ROCE = EBIT / (Total Assets - Current Liabilities) × 100
- Earnings Yield = EBIT / Enterprise Value × 100
  Where: EV = Market Cap + Total Debt - Unrestricted Cash

Features:
- Multi-period historical data extraction
- Comprehensive calculation logging
- Validation and quality checks
- Follows all heuristics and fallbacks from the guide
"""

import json
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

from .ebit_calculator import EBITCalculator
from .debt_calculator import DebtCalculator
from .cash_calculator import CashCalculator
from .balance_sheet_calculator import BalanceSheetCalculator


class EDGARParser:
    """
    Comprehensive EDGAR parser implementing the Financial Metrics Extraction Guide.

    Extracts all necessary metrics for Magic Formula screening:
    - EBIT (4-tier waterfall)
    - Total Debt (3-component structure)
    - Cash (unrestricted for EV)
    - Assets and Current Liabilities
    - Calculates ROCE and Earnings Yield components
    """

    def __init__(self):
        """Initialize parser with all metric calculators."""
        self.ebit_calculator = EBITCalculator()
        self.debt_calculator = DebtCalculator()
        self.cash_calculator = CashCalculator()
        self.balance_sheet_calculator = BalanceSheetCalculator()

    def extract_all_periods(
        self,
        facts: Dict,
        form_type: str = "10-K"
    ) -> List[Dict]:
        """
        Extract ALL fiscal periods from EDGAR data.

        Returns:
            List of dicts, one per fiscal period, with all metrics from that period
        """
        # Step 1: Identify all fiscal periods by looking at Assets
        periods = self._identify_fiscal_periods(facts, form_type)

        if not periods:
            return []

        # Step 2: For each fiscal period, extract all metrics from that period
        period_data = []
        for period_end, filing_info in periods.items():
            period_metrics = self._extract_period_metrics(
                facts,
                period_end,
                filing_info,
                form_type
            )

            if period_metrics:
                period_data.append(period_metrics)

        # Sort by fiscal year end (most recent first)
        period_data.sort(key=lambda x: x['fiscal_year_end'], reverse=True)

        # Mark the most recent period
        if period_data:
            period_data[0]['is_most_recent'] = True
            for p in period_data[1:]:
                p['is_most_recent'] = False

        return period_data

    def _identify_fiscal_periods(
        self,
        facts: Dict,
        form_type: str
    ) -> Dict[str, Dict]:
        """
        Identify all unique fiscal periods by examining Assets tag.

        Returns:
            Dict mapping fiscal_year_end -> {filed, form}
        """
        if 'us-gaap' not in facts.get('facts', {}):
            return {}

        gaap_facts = facts['facts']['us-gaap']

        # Use Assets to identify periods (every company has this)
        if 'Assets' not in gaap_facts:
            return {}

        assets = gaap_facts['Assets']
        if 'USD' not in assets.get('units', {}):
            return {}

        # Get all annual filings
        annual_filings = [
            v for v in assets['units']['USD']
            if v.get('form') == form_type
        ]

        # Group by fiscal year end, keep most recent filing for each
        periods = {}
        for filing in annual_filings:
            end_date = filing.get('end')
            filed_date = filing.get('filed')

            if not end_date or not filed_date:
                continue

            # If we already have this period, keep the most recent filing
            if end_date not in periods or filed_date > periods[end_date]['filed']:
                periods[end_date] = {
                    'filed': filed_date,
                    'form': filing.get('form')
                }

        return periods

    def _extract_period_metrics(
        self,
        facts: Dict,
        period_end: str,
        filing_info: Dict,
        form_type: str
    ) -> Optional[Dict]:
        """
        Extract all metrics for a specific fiscal period.

        Returns:
            Dictionary with all metrics, calculations, and metadata for the period
        """
        if 'us-gaap' not in facts.get('facts', {}):
            return None

        gaap_facts = facts['facts']['us-gaap']

        # Filter GAAP data to only this period's values
        period_gaap_data = self._filter_gaap_to_period(
            gaap_facts,
            period_end,
            form_type
        )

        # Extract all components
        ebit_result = self.ebit_calculator.calculate_ebit(period_gaap_data, form_type)
        debt_result = self.debt_calculator.calculate_total_debt(period_gaap_data, form_type)
        cash_result = self.cash_calculator.calculate_cash(period_gaap_data, form_type)
        assets_result = self.balance_sheet_calculator.calculate_assets(period_gaap_data, form_type)
        current_liabilities_result = self.balance_sheet_calculator.calculate_current_liabilities(
            period_gaap_data,
            form_type
        )

        # Build metrics dictionary
        metrics = {}

        if ebit_result:
            metrics['ebit'] = ebit_result

        if debt_result:
            metrics['total_debt'] = debt_result

        if cash_result:
            metrics['cash'] = cash_result

        if assets_result:
            metrics['assets'] = assets_result

        if current_liabilities_result:
            metrics['current_liabilities'] = current_liabilities_result

        # Calculate derived metrics
        roce_result = self._calculate_roce(
            ebit_result,
            assets_result,
            current_liabilities_result
        )

        earnings_yield_components = self._calculate_earnings_yield_components(
            ebit_result,
            debt_result,
            cash_result
        )

        # Extract fiscal year from fiscal_year_end (e.g., "2025" from "2025-09-27")
        fiscal_year = period_end[:4]

        return {
            'fiscal_year': fiscal_year,
            'fiscal_year_end': period_end,
            'filing_date': filing_info['filed'],
            'form': form_type,
            'metrics': metrics,
            'calculated_ratios': {
                'roce': roce_result,
                'earnings_yield_components': earnings_yield_components,
            },
        }

    def _filter_gaap_to_period(
        self,
        gaap_facts: Dict,
        period_end: str,
        form_type: str
    ) -> Dict:
        """
        Filter GAAP facts to only include values for a specific period.

        This ensures all metrics come from the same fiscal period.
        """
        period_gaap_data = {}

        for tag_name, tag_data in gaap_facts.items():
            if 'units' in tag_data and 'USD' in tag_data['units']:
                # Find values for this specific period
                period_values = [
                    v for v in tag_data['units']['USD']
                    if v.get('end') == period_end and v.get('form') == form_type
                ]

                if period_values:
                    # Take most recent filing if multiple
                    period_values.sort(key=lambda x: x.get('filed', ''), reverse=True)
                    period_gaap_data[tag_name] = {
                        'units': {'USD': [period_values[0]]}
                    }

        return period_gaap_data

    def _calculate_quarterly_deltas(self, quarterly_periods: List[Dict]) -> None:
        """
        Calculate true quarterly values by de-cumulating YTD income statement items.

        Income statement items in 10-Q filings are cumulative year-to-date:
        - Q1: Jan-Mar (3 months)
        - Q2: Jan-Jun (6 months cumulative)
        - Q3: Jan-Sep (9 months cumulative)

        To get true quarterly values:
        - Q1 = Q1_YTD (already isolated)
        - Q2 = Q2_YTD - Q1_YTD
        - Q3 = Q3_YTD - Q2_YTD

        This method modifies quarterly_periods in place, adding 'quarterly_value'
        fields to income statement metrics (EBIT only for now).

        Balance sheet items (Assets, Debt, Cash, Liabilities) are point-in-time
        snapshots and are NOT de-cumulated.

        Args:
            quarterly_periods: List of quarterly period dictionaries to modify
        """
        if not quarterly_periods:
            return

        # Group quarters by fiscal year
        # We use the year from fiscal_year_end to group, but need to be smart about
        # fiscal years that don't align with calendar years (e.g., Apple ends in September)
        fiscal_years = defaultdict(list)

        for period in quarterly_periods:
            # Extract just the year from fiscal_year_end (e.g., "2025" from "2025-09-27")
            fy_key = period['fiscal_year_end'][:4]
            fiscal_years[fy_key].append(period)

        # Process each fiscal year separately
        for fy, quarters in fiscal_years.items():
            # Sort chronologically by fiscal_year_end (earliest first for processing)
            sorted_quarters = sorted(quarters, key=lambda x: x['fiscal_year_end'])

            # De-cumulate EBIT for each quarter
            for i, quarter in enumerate(sorted_quarters):
                ebit_data = quarter.get('metrics', {}).get('ebit')

                if not ebit_data or ebit_data.get('value') is None:
                    # No EBIT data - skip this quarter
                    continue

                if i == 0:
                    # First quarter of fiscal year: YTD = quarterly (no subtraction needed)
                    ebit_data['ytd_value'] = ebit_data['value']
                    ebit_data['quarterly_value'] = ebit_data['value']
                    ebit_data['is_q1'] = True
                    ebit_data['calculation_note'] = 'Q1 - YTD equals quarterly (no de-cumulation needed)'
                else:
                    # Subsequent quarters: try to calculate delta
                    prev_ebit = sorted_quarters[i-1].get('metrics', {}).get('ebit')

                    # Store YTD value
                    ebit_data['ytd_value'] = ebit_data['value']

                    if prev_ebit and prev_ebit.get('value') is not None:
                        # We have previous quarter's data - can de-cumulate
                        quarterly_value = ebit_data['value'] - prev_ebit['value']
                        ebit_data['quarterly_value'] = quarterly_value
                        ebit_data['is_calculated'] = True
                        ebit_data['calculation_note'] = f'De-cumulated from YTD (current YTD - previous YTD)'
                        ebit_data['previous_quarter_ytd'] = prev_ebit['value']
                    else:
                        # Previous quarter missing EBIT - cannot de-cumulate
                        ebit_data['quarterly_value'] = None
                        ebit_data['calculation_failed'] = True
                        ebit_data['calculation_note'] = 'Cannot de-cumulate - previous quarter missing EBIT'

    def _calculate_roce(
        self,
        ebit_result: Optional[Dict],
        assets_result: Optional[Dict],
        current_liabilities_result: Optional[Dict]
    ) -> Optional[Dict]:
        """
        Calculate ROCE = EBIT / (Total Assets - Current Liabilities) × 100

        Returns:
            Dictionary with ROCE value, formula, components, and interpretation
        """
        if not all([ebit_result, assets_result, current_liabilities_result]):
            return {
                'value': None,
                'status': 'missing_components',
                'missing': [
                    k for k, v in {
                        'ebit': ebit_result,
                        'assets': assets_result,
                        'current_liabilities': current_liabilities_result
                    }.items() if not v
                ]
            }

        ebit = ebit_result['value']
        assets = assets_result['value']
        current_liabilities = current_liabilities_result['value']

        capital_employed = assets - current_liabilities

        if capital_employed <= 0:
            return {
                'value': None,
                'status': 'invalid_capital_employed',
                'capital_employed': capital_employed,
                'note': 'Capital employed is non-positive'
            }

        roce = (ebit / capital_employed) * 100

        # Interpretation per guide
        if roce > 25:
            interpretation = "Excellent - High quality business with strong capital efficiency"
        elif roce > 15:
            interpretation = "Good - Above average capital efficiency"
        elif roce > 10:
            interpretation = "Average - Acceptable returns on capital"
        else:
            interpretation = "Below Average - May indicate capital inefficiency or competitive pressures"

        return {
            'value': roce,
            'formula': 'ROCE = (EBIT / Capital Employed) × 100',
            'where': 'Capital Employed = Total Assets - Current Liabilities',
            'components': {
                'ebit': ebit,
                'total_assets': assets,
                'current_liabilities': current_liabilities,
                'capital_employed': capital_employed,
            },
            'interpretation': interpretation,
            'status': 'success',
        }

    def _calculate_earnings_yield_components(
        self,
        ebit_result: Optional[Dict],
        debt_result: Optional[Dict],
        cash_result: Optional[Dict]
    ) -> Optional[Dict]:
        """
        Calculate components for Earnings Yield (except Market Cap).

        Earnings Yield = EBIT / Enterprise Value
        Where: EV = Market Cap + Total Debt - Unrestricted Cash

        Note: Market Cap must be provided separately (from market data API).

        Returns:
            Dictionary with all EV components except market cap, plus helper formulas
        """
        if not all([ebit_result, debt_result, cash_result]):
            return {
                'status': 'missing_components',
                'missing': [
                    k for k, v in {
                        'ebit': ebit_result,
                        'total_debt': debt_result,
                        'cash': cash_result
                    }.items() if not v
                ]
            }

        ebit = ebit_result['value']
        total_debt = debt_result['value']
        unrestricted_cash = cash_result['unrestricted_cash']

        net_debt = total_debt - unrestricted_cash

        return {
            'status': 'success',
            'ebit': ebit,
            'total_debt': total_debt,
            'unrestricted_cash': unrestricted_cash,
            'net_debt': net_debt,
            'formula': 'Earnings Yield = EBIT / (Market Cap + Net Debt)',
            'formula_expanded': 'Earnings Yield = EBIT / (Market Cap + Total Debt - Unrestricted Cash)',
            'note': 'Market Cap must be provided from external market data source',
            'ready_for_calculation': True,
        }

    def calculate_earnings_yield_with_market_cap(
        self,
        earnings_yield_components: Dict,
        market_cap: float
    ) -> Optional[Dict]:
        """
        Calculate Earnings Yield given market cap.

        This is a helper function for when market cap data is available.

        Args:
            earnings_yield_components: Output from _calculate_earnings_yield_components
            market_cap: Market capitalization from external source

        Returns:
            Dictionary with earnings yield and full EV calculation
        """
        if earnings_yield_components.get('status') != 'success':
            return earnings_yield_components

        ebit = earnings_yield_components['ebit']
        net_debt = earnings_yield_components['net_debt']

        enterprise_value = market_cap + net_debt

        if enterprise_value <= 0:
            return {
                'status': 'invalid_enterprise_value',
                'enterprise_value': enterprise_value,
                'note': 'Enterprise value is non-positive'
            }

        earnings_yield = (ebit / enterprise_value) * 100

        return {
            'status': 'success',
            'value': earnings_yield,
            'formula': 'Earnings Yield = (EBIT / Enterprise Value) × 100',
            'components': {
                'ebit': ebit,
                'market_cap': market_cap,
                'net_debt': net_debt,
                'enterprise_value': enterprise_value,
            },
            'interpretation': self._interpret_earnings_yield(earnings_yield),
        }

    def _interpret_earnings_yield(self, earnings_yield: float) -> str:
        """Interpret Earnings Yield value per guide."""
        if earnings_yield > 10:
            return "High earnings yield - potential bargain (compare to 10Y Treasury ~4-5%)"
        elif earnings_yield > 8:
            return "Good earnings yield - attractive valuation"
        elif earnings_yield > 6:
            return "Fair earnings yield - reasonable valuation"
        else:
            return "Low earnings yield - potentially expensive (compare to Treasury rates)"

    def parse_company_data(self, edgar_data: Dict, verbose: bool = False, include_quarterly: bool = True) -> Dict:
        """
        Parse EDGAR data and extract ALL fiscal periods with complete metrics.

        Returns structured data with all historical periods including:
        - All raw metrics (EBIT, Debt, Cash, Assets, Liabilities)
        - Calculated ratios (ROCE, Earnings Yield components)
        - Detailed calculation logs

        Args:
            edgar_data: Raw EDGAR data dictionary
            verbose: Print detailed progress information
            include_quarterly: Include quarterly (10-Q) data in addition to annual (10-K)

        Returns:
            Comprehensive parsed data structure
        """
        company_name = edgar_data.get('entityName', 'Unknown')
        cik = edgar_data.get('cik', 'Unknown')

        if verbose:
            print(f"\n{'='*80}")
            print(f"EDGAR Parser V2: {company_name} (CIK: {cik})")
            print(f"{'='*80}\n")

        # Extract annual periods (10-K)
        annual_periods = self.extract_all_periods(edgar_data, form_type="10-K")

        if verbose:
            print(f"Found {len(annual_periods)} annual periods (10-K)")

        # Extract quarterly periods (10-Q) if requested
        quarterly_periods = []
        if include_quarterly:
            quarterly_periods = self.extract_all_periods(edgar_data, form_type="10-Q")
            if verbose:
                print(f"Found {len(quarterly_periods)} quarterly periods (10-Q)")

            # Calculate de-cumulated quarterly values for income statement items
            self._calculate_quarterly_deltas(quarterly_periods)
            if verbose:
                print(f"Calculated quarterly deltas for income statement items")

        if verbose:
            print()

        # Create calculation logs for each period
        for period in annual_periods:
            period['calculation_log'] = self._create_calculation_log(
                period,
                company_name,
                cik
            )

        for period in quarterly_periods:
            period['calculation_log'] = self._create_calculation_log(
                period,
                company_name,
                cik
            )

        # Create structured output
        result = {
            'metadata': {
                'company_name': company_name,
                'cik': cik,
                'parsed_at': datetime.now().isoformat(),
                'parser_version': '2.0',
                'total_annual_periods': len(annual_periods),
                'total_quarterly_periods': len(quarterly_periods),
                'guide_version': 'Financial Metrics Extraction Guide - December 2024',
            },
            'annual_periods': annual_periods,
            'quarterly_periods': quarterly_periods
        }

        if verbose and (annual_periods or quarterly_periods):
            self._print_summary(result)

        return result

    def _create_calculation_log(
        self,
        period_data: Dict,
        company_name: str,
        cik: str
    ) -> Dict:
        """Create detailed calculation log for a period."""
        log = {
            'timestamp': datetime.now().isoformat(),
            'company': company_name,
            'cik': cik,
            'fiscal_year_end': period_data['fiscal_year_end'],
            'filing_date': period_data['filing_date'],
            'metrics_extracted': {},
            'calculations': {},
        }

        metrics = period_data.get('metrics', {})

        # Log each metric extraction
        for metric_name, metric_data in metrics.items():
            log['metrics_extracted'][metric_name] = {
                'value': metric_data.get('value'),
                'method': metric_data.get('method'),
                'tier': metric_data.get('tier') if metric_name == 'ebit' else None,
                'validation': metric_data.get('validation') if metric_name == 'ebit' else None,
                'warnings': metric_data.get('warnings') if metric_name == 'total_debt' else None,
            }

        # Log ROCE calculation
        roce_data = period_data.get('calculated_ratios', {}).get('roce')
        if roce_data:
            log['calculations']['roce'] = roce_data

        # Log Earnings Yield components
        ey_components = period_data.get('calculated_ratios', {}).get('earnings_yield_components')
        if ey_components:
            log['calculations']['earnings_yield_components'] = ey_components

        return log

    def _print_summary(self, result: Dict):
        """Print a summary of the parsing results."""
        print(f"\n{'='*80}")
        print("PARSING SUMMARY")
        print(f"{'='*80}\n")

        metadata = result['metadata']
        print(f"Company: {metadata['company_name']}")
        print(f"CIK: {metadata['cik']}")
        print(f"Annual periods: {metadata['total_annual_periods']}")
        print(f"Quarterly periods: {metadata['total_quarterly_periods']}\n")

        # Print annual periods
        if result['annual_periods']:
            print("Annual Periods (10-K):")
            print(f"{'Year End':<15} {'ROCE':<10} {'EBIT Method':<30} {'Status':<20}")
            print("-" * 80)

            for period in result['annual_periods']:
                year_end = period['fiscal_year_end']
                roce = period.get('calculated_ratios', {}).get('roce', {})
                roce_val = f"{roce.get('value', 0):.2f}%" if roce.get('value') else "N/A"

                ebit = period.get('metrics', {}).get('ebit', {})
                ebit_method = ebit.get('method', 'N/A')[:28]

                marker = "← MOST RECENT" if period.get('is_most_recent') else ""

                print(f"{year_end:<15} {roce_val:<10} {ebit_method:<30} {marker:<20}")

        # Print quarterly periods
        if result['quarterly_periods']:
            print(f"\nQuarterly Periods (10-Q):")
            print(f"{'Period End':<15} {'ROCE':<10} {'EBIT Method':<30} {'Status':<20}")
            print("-" * 80)

            for period in result['quarterly_periods'][:12]:  # Show last 12 quarters
                period_end = period['fiscal_year_end']
                roce = period.get('calculated_ratios', {}).get('roce', {})
                roce_val = f"{roce.get('value', 0):.2f}%" if roce.get('value') else "N/A"

                ebit = period.get('metrics', {}).get('ebit', {})
                ebit_method = ebit.get('method', 'N/A')[:28]

                marker = "← MOST RECENT" if period.get('is_most_recent') else ""

                print(f"{period_end:<15} {roce_val:<10} {ebit_method:<30} {marker:<20}")

            if len(result['quarterly_periods']) > 12:
                print(f"... and {len(result['quarterly_periods']) - 12} more quarters")

    def get_most_recent_period(self, parsed_data: Dict) -> Optional[Dict]:
        """Get just the most recent fiscal period from parsed data."""
        periods = parsed_data.get('annual_periods', [])
        return periods[0] if periods else None
