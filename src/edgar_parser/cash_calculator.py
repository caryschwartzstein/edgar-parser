#!/usr/bin/env python3
"""
Cash and Cash Equivalents Calculator

Implements cash extraction strategy from the Financial Metrics Extraction Guide.

Key distinction:
- For ENTERPRISE VALUE: Use UNRESTRICTED cash only (restricted cash not available to pay debt)
- For BALANCE SHEET: Use TOTAL cash (including restricted)

Priority order for unrestricted cash:
1. CashAndCashEquivalentsAtCarryingValue (direct unrestricted - preferred)
2. Calculate: Total Cash - Restricted Cash (if direct tag missing)
3. Calculate: Total Cash - RestrictedCashCurrent - RestrictedCashNoncurrent

Priority order for total cash:
1. CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents (total - preferred)
2. CashAndCashEquivalentsAtCarryingValue (if restricted cash is zero/not reported)
"""

from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class CashCalculator:
    """
    Calculate cash and cash equivalents with proper handling of restricted cash.

    For Enterprise Value calculations, returns UNRESTRICTED cash only.
    """

    # Unrestricted Cash (Direct)
    UNRESTRICTED_CASH_TAGS = [
        'CashAndCashEquivalentsAtCarryingValue',  # Direct unrestricted (most reliable)
    ]

    # Total Cash (including restricted)
    TOTAL_CASH_TAGS = [
        'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',  # Total cash
        'CashAndCashEquivalentsAtCarryingValue',  # Fallback if no restricted cash
    ]

    # Restricted Cash
    RESTRICTED_CASH_TAGS = [
        'RestrictedCashAndCashEquivalentsAtCarryingValue',  # Direct total restricted
    ]

    RESTRICTED_CASH_COMPONENT_TAGS = {
        'current': ['RestrictedCashCurrent'],
        'noncurrent': ['RestrictedCashNoncurrent'],
    }

    def __init__(self):
        """Initialize the cash calculator."""
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

    def calculate_cash(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Calculate cash and cash equivalents with proper restricted cash handling.

        Returns both unrestricted cash (for EV) and total cash (for balance sheet).

        Returns:
            Dictionary with:
            - unrestricted_cash: For Enterprise Value calculations
            - total_cash: For balance sheet
            - restricted_cash: Amount of restricted cash (if any)
            - method: How the values were calculated
            - components: Source tags used
        """
        # Try to get unrestricted cash directly (most reliable)
        unrestricted_cash_direct = self._get_tag_value(
            gaap_data,
            self.UNRESTRICTED_CASH_TAGS,
            form_type
        )

        # Try to get total cash
        total_cash = self._get_tag_value(
            gaap_data,
            self.TOTAL_CASH_TAGS,
            form_type
        )

        # Try to get restricted cash
        restricted_cash_result = self._calculate_restricted_cash(gaap_data, form_type)

        # SCENARIO 1: We have direct unrestricted cash tag
        if unrestricted_cash_direct:
            unrestricted_value = unrestricted_cash_direct['val'] if unrestricted_cash_direct['val'] else 0

            # Calculate total if we also have restricted
            if restricted_cash_result:
                total_value = unrestricted_value + restricted_cash_result['value']
                method = 'Direct unrestricted + calculated total'
            else:
                # No restricted cash, so unrestricted = total
                total_value = unrestricted_value
                method = 'Direct unrestricted (no restricted cash)'

            return {
                'unrestricted_cash': unrestricted_value,
                'total_cash': total_value,
                'restricted_cash': restricted_cash_result['value'] if restricted_cash_result else 0,
                'method': method,
                'components': {
                    'unrestricted': unrestricted_cash_direct,
                    'restricted': restricted_cash_result,
                },
            }

        # SCENARIO 2: We have total cash but not unrestricted - need to calculate
        if total_cash and restricted_cash_result:
            total_value = total_cash['val'] if total_cash['val'] else 0
            restricted_value = restricted_cash_result['value']
            unrestricted_value = total_value - restricted_value

            return {
                'unrestricted_cash': unrestricted_value,
                'total_cash': total_value,
                'restricted_cash': restricted_value,
                'method': 'Calculated: Total cash - Restricted cash',
                'components': {
                    'total': total_cash,
                    'restricted': restricted_cash_result,
                },
            }

        # SCENARIO 3: We have total cash but no restricted cash info
        if total_cash:
            total_value = total_cash['val'] if total_cash['val'] else 0

            return {
                'unrestricted_cash': total_value,  # Assume all unrestricted
                'total_cash': total_value,
                'restricted_cash': 0,
                'method': 'Total cash (assuming no restricted cash)',
                'components': {
                    'total': total_cash,
                },
            }

        # Could not calculate cash
        logger.warning("Could not calculate cash - no cash tags found")
        return None

    def _calculate_restricted_cash(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Calculate restricted cash using available tags.

        Priority:
        1. Direct RestrictedCashAndCashEquivalentsAtCarryingValue
        2. Sum of RestrictedCashCurrent + RestrictedCashNoncurrent

        Returns:
            Dictionary with value and method, or None if not found
        """
        # Try direct restricted cash tag
        restricted_cash = self._get_tag_value(
            gaap_data,
            self.RESTRICTED_CASH_TAGS,
            form_type
        )

        if restricted_cash:
            return {
                'value': restricted_cash['val'] if restricted_cash['val'] else 0,
                'method': 'Direct RestrictedCashAndCashEquivalentsAtCarryingValue',
                'source': restricted_cash,
            }

        # Try component approach
        restricted_current = self._get_tag_value(
            gaap_data,
            self.RESTRICTED_CASH_COMPONENT_TAGS['current'],
            form_type
        )
        restricted_noncurrent = self._get_tag_value(
            gaap_data,
            self.RESTRICTED_CASH_COMPONENT_TAGS['noncurrent'],
            form_type
        )

        if restricted_current or restricted_noncurrent:
            value = 0
            sources = {}

            if restricted_current:
                value += restricted_current['val'] if restricted_current['val'] else 0
                sources['current'] = restricted_current

            if restricted_noncurrent:
                value += restricted_noncurrent['val'] if restricted_noncurrent['val'] else 0
                sources['noncurrent'] = restricted_noncurrent

            return {
                'value': value,
                'method': 'Sum of RestrictedCashCurrent + RestrictedCashNoncurrent',
                'sources': sources,
            }

        # No restricted cash found
        return None

    def get_unrestricted_cash_for_ev(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[float]:
        """
        Convenience method to get just the unrestricted cash value for EV calculation.

        Returns:
            Float value of unrestricted cash, or None if not found
        """
        result = self.calculate_cash(gaap_data, form_type)
        if result:
            return result['unrestricted_cash']
        return None

    def get_cash_for_balance_sheet(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[float]:
        """
        Convenience method to get total cash for balance sheet purposes.

        Returns:
            Float value of total cash, or None if not found
        """
        result = self.calculate_cash(gaap_data, form_type)
        if result:
            return result['total_cash']
        return None
