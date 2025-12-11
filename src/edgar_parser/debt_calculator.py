#!/usr/bin/env python3
"""
Total Debt Calculator with 3-Component Structure

Implements the comprehensive debt calculation strategy from the Financial Metrics
Extraction Guide. Properly handles the THREE components of total debt:

1. Long-Term Debt (non-current portion) - portion due after 1 year
2. Current Portion of Long-Term Debt - portion of LT debt due within 1 year
3. Short-Term Borrowings - pure short-term debt (commercial paper, credit lines)

Key features:
- Prevents double-counting when tags include current maturities
- Detects duplicate tags with different names for same values
- Handles both 2-component and 3-component structures
- Returns detailed calculation metadata
"""

from typing import Dict, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class DebtCalculator:
    """
    Calculate Total Debt using the 3-component structure per the guide.

    Formula:
        Total Debt = LT Debt (non-current) + Current Portion of LT Debt + ST Borrowings
    """

    # Component 1: Long-Term Debt (Non-Current)
    LT_DEBT_NONCURRENT_TAGS = [
        'LongTermDebtNoncurrent',  # Explicitly non-current only
        'LongTermDebtAndCapitalLeaseObligations',  # Usually non-current only, but verify
        'LongTermDebt',  # May or may not include current portion
    ]

    # Tags that INCLUDE current maturities (use these alone, skip Component 2)
    LT_DEBT_INCLUDING_CURRENT_TAGS = [
        'LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities',
        'LongTermDebtIncludingCurrentMaturities',
    ]

    # Component 2: Current Portion of Long-Term Debt
    LT_DEBT_CURRENT_TAGS = [
        'LongTermDebtCurrent',  # Most common
        'LongTermDebtAndCapitalLeaseObligationsCurrent',  # Alternative name
        'LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths',  # More explicit
    ]

    # Component 3: Short-Term Borrowings
    ST_BORROWINGS_TAGS = [
        'ShortTermBorrowings',  # Use this if available (most direct)
    ]

    ST_BORROWINGS_COMPONENT_TAGS = [
        'ShortTermBankLoansAndNotesPayable',
        'CommercialPaper',
    ]

    # WARNING: DebtCurrent includes BOTH current portion AND short-term borrowings
    # Only use as absolute last resort

    def __init__(self):
        """Initialize the debt calculator."""
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

    def _check_for_duplicate_tags(
        self,
        gaap_data: Dict,
        tag_list: List[str],
        form_type: str = "10-K"
    ) -> List[Dict]:
        """
        Check if multiple tags from the list exist and have the same value.

        This handles cases like XOM where both LongTermDebtCurrent AND
        LongTermDebtAndCapitalLeaseObligationsCurrent exist with identical values.

        Returns:
            List of all matching tag data dictionaries
        """
        results = []
        for tag in tag_list:
            tag_data = self._get_tag_value(gaap_data, [tag], form_type)
            if tag_data:
                results.append(tag_data)
        return results

    def calculate_total_debt(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Calculate Total Debt using the 3-component structure.

        Returns detailed breakdown including which tags were used and any warnings
        about potential double-counting or missing components.

        Returns:
            Dictionary with total_debt value, components breakdown, and metadata
            Returns None if total debt cannot be calculated
        """
        components = {}
        warnings = []
        total_debt = 0

        # STEP 1: Check if we have a tag that INCLUDES current maturities
        lt_debt_including_current = self._get_tag_value(
            gaap_data,
            self.LT_DEBT_INCLUDING_CURRENT_TAGS,
            form_type
        )

        if lt_debt_including_current:
            # This tag includes both non-current AND current portions
            # So we skip Component 2 and just add Component 3
            components['lt_debt_including_current'] = lt_debt_including_current
            total_debt += lt_debt_including_current['val'] if lt_debt_including_current['val'] else 0

            warnings.append(
                f"Using {lt_debt_including_current['tag']} which includes current maturities - "
                "skipping separate current portion"
            )

            # Now add Component 3: Short-Term Borrowings
            st_borrowings = self._calculate_st_borrowings(gaap_data, form_type)
            if st_borrowings:
                components['st_borrowings'] = st_borrowings
                total_debt += st_borrowings['value']

            return {
                'value': total_debt,
                'method': '2-component (LT including current + ST borrowings)',
                'components': components,
                'warnings': warnings,
            }

        # STEP 2: Standard 3-component approach
        # Component 1: Long-Term Debt (non-current)
        lt_debt_noncurrent = self._get_tag_value(
            gaap_data,
            self.LT_DEBT_NONCURRENT_TAGS,
            form_type
        )

        if lt_debt_noncurrent:
            components['lt_debt_noncurrent'] = lt_debt_noncurrent
            total_debt += lt_debt_noncurrent['val'] if lt_debt_noncurrent['val'] else 0
        else:
            warnings.append("Could not find non-current long-term debt")

        # Component 2: Current Portion of Long-Term Debt
        # Check for duplicate tags first
        lt_debt_current_matches = self._check_for_duplicate_tags(
            gaap_data,
            self.LT_DEBT_CURRENT_TAGS,
            form_type
        )

        if len(lt_debt_current_matches) > 1:
            # Check if they all have the same value
            values = [m['val'] for m in lt_debt_current_matches]
            if len(set(values)) == 1:
                # All duplicates have same value - only count once
                warnings.append(
                    f"Found {len(lt_debt_current_matches)} tags for current portion of LT debt "
                    f"with same value (${values[0]:,}) - counted once only"
                )
                components['lt_debt_current'] = lt_debt_current_matches[0]
                total_debt += lt_debt_current_matches[0]['val'] if lt_debt_current_matches[0]['val'] else 0
            else:
                # Different values - this is a problem
                warnings.append(
                    f"WARNING: Found {len(lt_debt_current_matches)} tags for current portion "
                    f"with DIFFERENT values: {values} - using first one but needs review"
                )
                components['lt_debt_current'] = lt_debt_current_matches[0]
                total_debt += lt_debt_current_matches[0]['val'] if lt_debt_current_matches[0]['val'] else 0
        elif len(lt_debt_current_matches) == 1:
            components['lt_debt_current'] = lt_debt_current_matches[0]
            total_debt += lt_debt_current_matches[0]['val'] if lt_debt_current_matches[0]['val'] else 0
        else:
            warnings.append("Could not find current portion of long-term debt")

        # Component 3: Short-Term Borrowings
        st_borrowings = self._calculate_st_borrowings(gaap_data, form_type)
        if st_borrowings:
            components['st_borrowings'] = st_borrowings
            total_debt += st_borrowings['value']

        if not components:
            logger.warning("Could not calculate total debt - no components found")
            return None

        method = self._determine_method(components)

        return {
            'value': total_debt,
            'method': method,
            'components': components,
            'warnings': warnings if warnings else None,
        }

    def _calculate_st_borrowings(
        self,
        gaap_data: Dict,
        form_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Calculate short-term borrowings (Component 3).

        Priority:
        1. ShortTermBorrowings (direct)
        2. Sum of ShortTermBankLoansAndNotesPayable + CommercialPaper
        3. If all unavailable, return None (some companies have zero ST borrowings)

        Returns:
            Dictionary with value and component breakdown, or None
        """
        # Try direct tag first
        st_borrowings = self._get_tag_value(gaap_data, self.ST_BORROWINGS_TAGS, form_type)
        if st_borrowings:
            return {
                'value': st_borrowings['val'] if st_borrowings['val'] else 0,
                'method': 'Direct ShortTermBorrowings',
                'source': st_borrowings,
            }

        # Try component tags
        bank_loans = self._get_tag_value(
            gaap_data,
            ['ShortTermBankLoansAndNotesPayable'],
            form_type
        )
        commercial_paper = self._get_tag_value(
            gaap_data,
            ['CommercialPaper'],
            form_type
        )

        if bank_loans or commercial_paper:
            value = 0
            sources = {}

            if bank_loans:
                value += bank_loans['val'] if bank_loans['val'] else 0
                sources['bank_loans'] = bank_loans

            if commercial_paper:
                value += commercial_paper['val'] if commercial_paper['val'] else 0
                sources['commercial_paper'] = commercial_paper

            return {
                'value': value,
                'method': 'Sum of components (bank loans + commercial paper)',
                'sources': sources,
            }

        # No short-term borrowings found
        return None

    def _determine_method(self, components: Dict) -> str:
        """Determine which calculation method was used based on components."""
        has_noncurrent = 'lt_debt_noncurrent' in components
        has_current = 'lt_debt_current' in components
        has_st = 'st_borrowings' in components
        has_including = 'lt_debt_including_current' in components

        if has_including:
            return '2-component (LT including current + ST borrowings)'
        elif has_noncurrent and has_current and has_st:
            return '3-component (LT non-current + LT current + ST borrowings)'
        elif has_noncurrent and has_current:
            return '2-component (LT non-current + LT current, no ST borrowings)'
        elif has_noncurrent and has_st:
            return '2-component (LT non-current + ST borrowings, no LT current)'
        else:
            component_list = ', '.join(components.keys())
            return f'Partial ({component_list})'
