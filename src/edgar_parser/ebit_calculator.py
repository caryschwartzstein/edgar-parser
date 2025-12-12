#!/usr/bin/env python3
"""
EBIT/Operating Income Calculator with Waterfall Fallback Strategy

Implements the 4-tier waterfall strategy from the Financial Metrics Extraction Guide:
- Tier 1: Direct Operating Income or Revenues - CostsAndExpenses (with validation)
- Tier 2: Build from Components (Revenues - COGS - OpEx)
- Tier 3: Work Backwards from Net Income (NI + Tax + Interest)
- Tier 4: Pre-tax Income + Interest (Last Resort)

Key features:
- Validates Revenues - CostsAndExpenses against pre-tax income
- Returns detailed calculation metadata
- Handles multiple tag variations per component
"""

from typing import Dict, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)


class EBITCalculator:
    """
    Calculate EBIT/Operating Income using multiple fallback methods.

    Implements the 4-tier waterfall approach per the Financial Metrics Extraction Guide.
    """

    # Tier 1: Direct Operating Income or Revenues - CostsAndExpenses
    TIER_1_TAGS = {
        'operating_income_direct': ['OperatingIncomeLoss'],
        'revenues': [
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'RevenueFromContractWithCustomerIncludingAssessedTax',
        ],
        'costs_and_expenses': ['CostsAndExpenses'],
        # For validation
        'pretax_income_validation': [
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ],
    }

    # Tier 2: Build from Components
    TIER_2_TAGS = {
        'revenues': [
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'RevenueFromContractWithCustomerIncludingAssessedTax',
        ],
        'cogs': ['CostOfGoodsAndServicesSold'],
        'operating_expenses': ['OperatingCostsAndExpenses'],
    }

    # Tier 3: Work Backwards from Net Income
    TIER_3_TAGS = {
        'net_income': [
            'NetIncomeLoss',
            'ProfitLoss',
            'NetIncomeLossAvailableToCommonStockholdersBasic',
        ],
        'income_tax': ['IncomeTaxExpenseBenefit'],
        'interest_expense': [
            'InterestExpenseDebt',
            'InterestExpense',
        ],
    }

    # Tier 4: Pre-tax Income + Interest
    TIER_4_TAGS = {
        'pretax_income': [
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ],
        'interest_expense': [
            'InterestExpenseDebt',
            'InterestExpense',
        ],
    }

    def __init__(self):
        """Initialize the EBIT calculator."""
        pass

    def _get_tag_value(
        self,
        gaap_data: Dict,
        tag_list: List[str],
        form_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Extract value for first available tag from tag list.

        Args:
            gaap_data: Dictionary of GAAP facts
            tag_list: List of potential tag names to try (in priority order)
            form_type: Form type to filter on (default: 10-K)

        Returns:
            Dictionary with 'val', 'end', 'filed', 'tag' keys, or None if not found
        """
        for tag in tag_list:
            if tag in gaap_data:
                units = gaap_data[tag].get('units', {})

                if 'USD' in units:
                    values = units['USD']
                    annual_values = [v for v in values if v.get('form') == form_type]

                    if annual_values:
                        # Sort by period end date (fiscal year end), then by filed date
                        # This ensures we get the most recent fiscal period
                        annual_values.sort(
                            key=lambda x: (x.get('end', ''), x.get('filed', '')),
                            reverse=True
                        )
                        most_recent = annual_values[0]

                        return {
                            'val': most_recent.get('val'),
                            'end': most_recent.get('end'),
                            'filed': most_recent.get('filed'),
                            'tag': tag,
                        }

        return None

    def _tier_1_direct_operating_income(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Tuple[float, str, Dict, Optional[str]]]:
        """
        Tier 1: Try to get Operating Income directly or calculate Revenues - CostsAndExpenses.

        Per guide:
        1. Try OperatingIncomeLoss first (most direct)
        2. Calculate: Revenues - CostsAndExpenses (with validation)

        Validation: When using Revenues - CostsAndExpenses, validate against pre-tax income.
        For companies with simple structures, these should match exactly or be very close
        (within $1M tolerance).

        Args:
            gaap_data: Dictionary of GAAP facts
            form_type: Form type to filter on (10-K or 10-Q)

        Returns:
            Tuple of (ebit_value, method, sources, validation_note) or None
        """
        # Priority 1: Direct OperatingIncomeLoss
        operating_income = self._get_tag_value(
            gaap_data,
            self.TIER_1_TAGS['operating_income_direct'],
            form_type
        )
        if operating_income and operating_income['val'] is not None:
            return (
                operating_income['val'],
                'Direct OperatingIncomeLoss',
                {'operating_income': operating_income},
                None
            )

        # Priority 2: Revenues - CostsAndExpenses (with validation)
        revenues = self._get_tag_value(gaap_data, self.TIER_1_TAGS['revenues'], form_type)
        costs = self._get_tag_value(gaap_data, self.TIER_1_TAGS['costs_and_expenses'], form_type)

        if revenues and costs and revenues['val'] is not None and costs['val'] is not None:
            ebit = revenues['val'] - costs['val']

            # VALIDATION: Check against pre-tax income
            pretax = self._get_tag_value(
                gaap_data,
                self.TIER_1_TAGS['pretax_income_validation'],
                form_type
            )

            validation_note = None
            if pretax and pretax['val'] is not None:
                difference = abs(ebit - pretax['val'])
                tolerance = 1_000_000  # $1M tolerance

                if difference <= tolerance:
                    validation_note = f"✓ Validation passed: matches pre-tax income (diff: ${difference:,.0f})"
                else:
                    validation_note = f"⚠ Validation warning: differs from pre-tax income by ${difference:,.0f} (>{tolerance:,.0f})"

            sources = {
                'revenues': revenues,
                'costs_and_expenses': costs
            }
            if pretax:
                sources['pretax_income_validation'] = pretax

            return (
                ebit,
                'Revenues - CostsAndExpenses',
                sources,
                validation_note
            )

        return None

    def _tier_2_build_from_components(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Tuple[float, str, Dict, Optional[str]]]:
        """
        Tier 2: Build EBIT from components: Revenues - COGS - Operating Expenses.

        Per guide:
        EBIT = Revenues - CostOfGoodsAndServicesSold - OperatingCostsAndExpenses

        Args:
            gaap_data: Dictionary of GAAP facts
            form_type: Form type to filter on (10-K or 10-Q)

        Returns:
            Tuple of (ebit_value, method, sources, validation_note) or None
        """
        revenues = self._get_tag_value(gaap_data, self.TIER_2_TAGS['revenues'], form_type)
        cogs = self._get_tag_value(gaap_data, self.TIER_2_TAGS['cogs'], form_type)
        opex = self._get_tag_value(gaap_data, self.TIER_2_TAGS['operating_expenses'], form_type)

        if all([revenues, cogs, opex]) and all(x['val'] is not None for x in [revenues, cogs, opex]):
            ebit = revenues['val'] - cogs['val'] - opex['val']
            return (
                ebit,
                'Revenues - COGS - OpEx',
                {
                    'revenues': revenues,
                    'cost_of_goods_and_services_sold': cogs,
                    'operating_costs_and_expenses': opex
                },
                None
            )

        return None

    def _tier_3_work_backwards_from_net_income(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Tuple[float, str, Dict, Optional[str]]]:
        """
        Tier 3: Work backwards from Net Income.

        Per guide:
        EBIT = NetIncomeLoss + IncomeTaxExpenseBenefit + InterestExpenseDebt

        Args:
            gaap_data: Dictionary of GAAP facts
            form_type: Form type to filter on (10-K or 10-Q)

        Returns:
            Tuple of (ebit_value, method, sources, validation_note) or None
        """
        net_income = self._get_tag_value(gaap_data, self.TIER_3_TAGS['net_income'], form_type)
        tax = self._get_tag_value(gaap_data, self.TIER_3_TAGS['income_tax'], form_type)
        interest = self._get_tag_value(gaap_data, self.TIER_3_TAGS['interest_expense'], form_type)

        if all([net_income, tax, interest]) and all(x['val'] is not None for x in [net_income, tax, interest]):
            ebit = net_income['val'] + tax['val'] + interest['val']
            return (
                ebit,
                'NetIncome + Tax + Interest',
                {
                    'net_income': net_income,
                    'income_tax_expense_benefit': tax,
                    'interest_expense': interest
                },
                None
            )

        return None

    def _tier_4_pretax_plus_interest(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Tuple[float, str, Dict, Optional[str]]]:
        """
        Tier 4: Last resort - Pre-tax Income + Interest.

        Per guide:
        EBIT = IncomeLossFromContinuingOperationsBeforeIncomeTaxes... + InterestExpenseDebt

        Args:
            gaap_data: Dictionary of GAAP facts
            form_type: Form type to filter on (10-K or 10-Q)

        Returns:
            Tuple of (ebit_value, method, sources, validation_note) or None
        """
        pretax = self._get_tag_value(gaap_data, self.TIER_4_TAGS['pretax_income'], form_type)
        interest = self._get_tag_value(gaap_data, self.TIER_4_TAGS['interest_expense'], form_type)

        if all([pretax, interest]) and all(x['val'] is not None for x in [pretax, interest]):
            ebit = pretax['val'] + interest['val']
            return (
                ebit,
                'PreTaxIncome + Interest',
                {
                    'pretax_income': pretax,
                    'interest_expense': interest
                },
                None
            )

        return None

    def calculate_ebit(self, gaap_data: Dict, form_type: str = "10-K") -> Optional[Dict]:
        """
        Calculate EBIT using waterfall fallback strategy.

        Tries multiple methods in order of reliability per the guide:
        1. Direct Operating Income or Revenues - CostsAndExpenses (with validation)
        2. Build from Components (Revenues - COGS - OpEx)
        3. Work Backwards from Net Income (NI + Tax + Interest)
        4. Pre-tax Income + Interest

        Args:
            gaap_data: Dictionary of GAAP facts from EDGAR
            form_type: Form type to filter on (default: 10-K)

        Returns:
            Dictionary with EBIT value, calculation method, tier, sources, and validation info
            Returns None if EBIT cannot be calculated using any method
        """
        # Try each tier in order
        for tier_num, tier_method in enumerate([
            self._tier_1_direct_operating_income,
            self._tier_2_build_from_components,
            self._tier_3_work_backwards_from_net_income,
            self._tier_4_pretax_plus_interest,
        ], start=1):
            result = tier_method(gaap_data, form_type)
            if result:
                ebit_value, method, sources, validation_note = result
                logger.info(f"EBIT calculated using Tier {tier_num}: {method}")

                return {
                    'value': ebit_value,
                    'method': method,
                    'tier': tier_num,
                    'sources': sources,
                    'validation': validation_note,
                }

        logger.warning("Could not calculate EBIT using any available method")
        return None

    def validate_ebit(
        self,
        ebit: float,
        net_income: Optional[float] = None,
        revenues: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Validate EBIT calculation with sanity checks per the guide.

        Args:
            ebit: Calculated EBIT value
            net_income: Net income for comparison (optional)
            revenues: Total revenues for margin check (optional)

        Returns:
            Tuple of (is_valid, message)
        """
        checks = []

        # Check 1: EBIT should be positive for most profitable companies
        if ebit <= 0:
            checks.append(f"⚠ EBIT is non-positive: ${ebit:,.0f}")
        else:
            checks.append(f"✓ EBIT is positive: ${ebit:,.0f}")

        # Check 2: EBIT should be greater than Net Income (before interest and taxes)
        if net_income is not None:
            if ebit < net_income:
                checks.append(f"✗ EBIT (${ebit:,.0f}) < Net Income (${net_income:,.0f}) - impossible")
                return False, " | ".join(checks)
            else:
                checks.append(f"✓ EBIT > Net Income")

        # Check 3: EBIT margin should be reasonable (typically 5-30% per guide)
        if revenues is not None and revenues > 0:
            margin = (ebit / revenues) * 100
            if margin < 0 or margin > 100:
                checks.append(f"✗ EBIT margin {margin:.1f}% outside reasonable range (0-100%)")
                return False, " | ".join(checks)
            elif 5 <= margin <= 30:
                checks.append(f"✓ EBIT margin {margin:.1f}% within typical range (5-30%)")
            else:
                checks.append(f"⚠ EBIT margin {margin:.1f}% outside typical range (5-30%), but acceptable")

        return True, " | ".join(checks)
