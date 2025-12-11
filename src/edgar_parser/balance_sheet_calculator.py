#!/usr/bin/env python3
"""
Balance Sheet Items Calculator

Extracts Assets and Current Liabilities per the Financial Metrics Extraction Guide.

Per guide:
- Assets: Almost always available as 'Assets' tag (99% of cases)
- Current Liabilities: Almost always available as 'LiabilitiesCurrent' tag (99% of cases)

Fallbacks are provided for rare cases where direct tags are missing.
"""

from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class BalanceSheetCalculator:
    """
    Extract balance sheet items needed for ROCE calculation.

    Focuses on:
    - Total Assets
    - Current Liabilities
    """

    # Assets
    ASSETS_TAGS = [
        'Assets',  # Always use this if available (99% of cases)
    ]

    ASSETS_COMPONENT_TAGS = {
        'current': ['AssetsCurrent'],
        'noncurrent': ['AssetsNoncurrent'],
    }

    # Current Liabilities
    CURRENT_LIABILITIES_TAGS = [
        'LiabilitiesCurrent',  # Always use this if available (99% of cases)
    ]

    # Fallback for current liabilities
    LIABILITIES_TAGS = [
        'Liabilities',
    ]

    NONCURRENT_LIABILITIES_TAGS = [
        'LiabilitiesNoncurrent',
    ]

    def __init__(self):
        """Initialize the balance sheet calculator."""
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

    def calculate_assets(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Calculate total assets.

        Per guide:
        Priority 1: Assets tag (99% of cases)
        Priority 2: Sum of AssetsCurrent + AssetsNoncurrent (rare fallback)

        Returns:
            Dictionary with value, method, and source tags
        """
        # Try direct Assets tag first
        assets = self._get_tag_value(gaap_data, self.ASSETS_TAGS, form_type)

        if assets:
            return {
                'value': assets['val'] if assets['val'] else 0,
                'method': 'Direct Assets tag',
                'source': assets,
            }

        # Fallback: Sum of current + noncurrent
        assets_current = self._get_tag_value(
            gaap_data,
            self.ASSETS_COMPONENT_TAGS['current'],
            form_type
        )
        assets_noncurrent = self._get_tag_value(
            gaap_data,
            self.ASSETS_COMPONENT_TAGS['noncurrent'],
            form_type
        )

        if assets_current and assets_noncurrent:
            value = (assets_current['val'] if assets_current['val'] else 0) + \
                    (assets_noncurrent['val'] if assets_noncurrent['val'] else 0)

            return {
                'value': value,
                'method': 'Sum of AssetsCurrent + AssetsNoncurrent',
                'sources': {
                    'current': assets_current,
                    'noncurrent': assets_noncurrent,
                },
            }

        logger.warning("Could not calculate total assets - missing tags")
        return None

    def calculate_current_liabilities(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Calculate current liabilities.

        Per guide:
        Priority 1: LiabilitiesCurrent tag (99% of cases)
        Priority 2: Liabilities - LiabilitiesNoncurrent (rare fallback)

        Returns:
            Dictionary with value, method, and source tags
        """
        # Try direct LiabilitiesCurrent tag first
        current_liabilities = self._get_tag_value(
            gaap_data,
            self.CURRENT_LIABILITIES_TAGS,
            form_type
        )

        if current_liabilities:
            return {
                'value': current_liabilities['val'] if current_liabilities['val'] else 0,
                'method': 'Direct LiabilitiesCurrent tag',
                'source': current_liabilities,
            }

        # Fallback: Total liabilities - Noncurrent liabilities
        total_liabilities = self._get_tag_value(
            gaap_data,
            self.LIABILITIES_TAGS,
            form_type
        )
        noncurrent_liabilities = self._get_tag_value(
            gaap_data,
            self.NONCURRENT_LIABILITIES_TAGS,
            form_type
        )

        if total_liabilities and noncurrent_liabilities:
            value = (total_liabilities['val'] if total_liabilities['val'] else 0) - \
                    (noncurrent_liabilities['val'] if noncurrent_liabilities['val'] else 0)

            return {
                'value': value,
                'method': 'Calculated: Liabilities - LiabilitiesNoncurrent',
                'sources': {
                    'total': total_liabilities,
                    'noncurrent': noncurrent_liabilities,
                },
            }

        logger.warning("Could not calculate current liabilities - missing tags")
        return None

    def calculate_capital_employed(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Calculate Capital Employed for ROCE.

        Formula: Capital Employed = Total Assets - Current Liabilities

        Returns:
            Dictionary with value, formula, and component breakdowns
        """
        assets_result = self.calculate_assets(gaap_data, form_type)
        current_liabilities_result = self.calculate_current_liabilities(gaap_data, form_type)

        if not assets_result or not current_liabilities_result:
            logger.warning("Could not calculate capital employed - missing components")
            return None

        assets = assets_result['value']
        current_liabilities = current_liabilities_result['value']
        capital_employed = assets - current_liabilities

        if capital_employed <= 0:
            logger.warning(f"Capital employed is non-positive: {capital_employed}")

        return {
            'value': capital_employed,
            'formula': 'Total Assets - Current Liabilities',
            'components': {
                'assets': assets_result,
                'current_liabilities': current_liabilities_result,
            },
        }
