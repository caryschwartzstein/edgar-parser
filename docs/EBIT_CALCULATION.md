# EBIT/Operating Income Calculation Strategy

## Overview

This document describes the comprehensive waterfall approach implemented for calculating Operating Income (EBIT) from EDGAR XBRL data. The strategy handles the variability in GAAP tags across different companies and industries.

## Problem Statement

Different companies report operating income using different XBRL tags, and certain tags may or may not be available. This makes it challenging to reliably extract EBIT for all companies. For example:
- Some companies use `OperatingIncomeLoss` directly
- Energy companies often use long tags like `IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments`
- Some companies provide `CostsAndExpenses` which can be subtracted from `Revenues`
- Others break costs into components (COGS + Operating Expenses)

## Solution: Waterfall Approach with 4 Tiers

The implementation tries multiple calculation methods in order of reliability and cleanliness.

### Tier 1: Direct Operating Income (Preferred)

**Methods:**
1. Try `OperatingIncomeLoss` tag directly
2. Calculate `Revenues - CostsAndExpenses`

**Why preferred:** This is the cleanest method. `CostsAndExpenses` typically includes COGS + OpEx but excludes interest and taxes.

**Example (CVX - Chevron):**
```
Revenues:          $202,792,000,000
CostsAndExpenses:  $175,286,000,000
─────────────────────────────────
EBIT:              $ 27,506,000,000
```

### Tier 2: Build from Components

**Method:**
```
EBIT = Revenues - CostOfGoodsAndServicesSold - OperatingCostsAndExpenses
```

**Tags used:**
- `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, or `SalesRevenueNet`
- `CostOfGoodsAndServicesSold`, `CostOfRevenue`, or `CostOfGoodsSold`
- `OperatingCostsAndExpenses`, `OperatingExpenses`, or `CostsAndExpenses`

**Warning:** This method can fail if `OperatingExpenses` actually maps to `CostsAndExpenses`, which would double-count COGS. The variance detection will flag this.

### Tier 3: Work Backwards from Net Income

**Method:**
```
EBIT = NetIncomeLoss + IncomeTaxExpenseBenefit + InterestExpense
```

**Tags used:**
- `NetIncomeLoss`, `ProfitLoss`, or `NetIncomeLossAvailableToCommonStockholdersBasic`
- `IncomeTaxExpenseBenefit` or `IncomeTaxesPaid`
- `InterestExpense`, `InterestExpenseDebt`, or `InterestAndDebtExpense`

**Reliability:** This is highly reliable when all three components are available, as it's working from audited bottom-line figures.

### Tier 4: Pre-tax Income + Interest (Last Resort)

**Method:**
```
EBIT = IncomeLossFromContinuingOperationsBeforeIncomeTaxes + InterestExpense
```

**Why last resort:** Pre-tax income tags can be very long and may include or exclude various items. Less consistent across companies.

## Validation

The calculator includes validation checks:

1. **Positive EBIT:** EBIT should typically be positive for profitable companies
2. **EBIT > Net Income:** EBIT must be greater than net income (before subtracting interest and taxes)
3. **Reasonable Margin:** EBIT margin should be 0-100% of revenues

Example validation:
```python
is_valid, message = calculator.validate_ebit(
    ebit=49_674_000_000,
    net_income=35_465_000_000,
    revenues=246_252_000_000
)
# Returns: (True, "EBIT validation passed")
# Operating Margin: 20.17% (within typical 5-30% range)
```

## Variance Detection

When multiple methods are available, the calculator can compare results and flag discrepancies:

```python
comparison = calculator.compare_methods(gaap_data)
```

**Example output for CVX:**
```
Tier 1: $27,506,000,000  (Revenues - CostsAndExpenses)
Tier 2: $56,122,000,000  (Revenues - COGS - OpEx)  ⚠️ 104% variance
Tier 3: $28,012,000,000  (NetIncome + Tax + Interest)
Tier 4: $28,100,000,000  (PreTaxIncome + Interest)

Variance: 104.04% - manual review recommended
```

The large Tier 2 variance indicates that method is using incorrect tags for CVX.

## Implementation Details

### Module: `ebit_calculator.py`

**Main class:** `EBITCalculator`

**Key methods:**
- `calculate_ebit(gaap_data, form_type="10-K")` - Returns EBIT using best available method
- `validate_ebit(ebit, net_income, revenues)` - Validates calculated EBIT
- `compare_methods(gaap_data)` - Compares all methods and detects variance

### Integration with Parser V2

The EBIT calculator is integrated into `parser_v2.py`:

1. Each period's GAAP data is filtered to that specific fiscal year
2. EBIT calculator is called with period-specific data
3. Result is stored as `operating_income_enhanced` metric
4. ROCE calculations preferentially use enhanced EBIT
5. Calculation logs track which method and tier was used

### Data Structure

Enhanced EBIT is stored with metadata:

```json
{
  "operating_income_enhanced": {
    "value": 27506000000,
    "method": "Revenues - CostsAndExpenses",
    "tier": 1,
    "sources": {
      "revenues": {
        "val": 202792000000,
        "end": "2024-12-31",
        "filed": "2025-02-21",
        "tag": "Revenues"
      },
      "costs_and_expenses": {
        "val": 175286000000,
        "end": "2024-12-31",
        "filed": "2025-02-21",
        "tag": "CostsAndExpenses"
      }
    },
    "unit": "USD",
    "date": "2024-12-31",
    "filed": "2025-02-21",
    "form": "10-K"
  }
}
```

## Testing

### Test Scripts

1. **`test_ebit_calculation.py`** - Tests EBIT calculation with CVX data
   - Tests single calculation
   - Compares all methods
   - Validates results

2. **`debug_ebit_variance.py`** - Diagnoses why methods give different results
   - Shows available cost tags
   - Explains Tier 2 variance
   - Provides recommendations

### Running Tests

```bash
# Test EBIT calculation
python scripts/test_ebit_calculation.py

# Debug variance issues
python scripts/debug_ebit_variance.py

# Test with full parser
python scripts/parse_test_companies.py
```

## Results - CVX Example

**Company:** Chevron Corp (CVX)
**Fiscal Year:** 2024 (ending 2024-12-31)

**Selected Method:** Tier 1 - Revenues - CostsAndExpenses

**EBIT:** $27,506,000,000

**Operating Margin:** 13.56% ✓

**Validation:** Passed
- EBIT > Net Income: ✓ ($27.5B > $17.7B)
- Reasonable margin: ✓ (13.56% is within 5-30% range)

**Why Tier 1 is correct for CVX:**
- `CostsAndExpenses` properly aggregates all operating costs
- Tier 2 double-counts COGS (104% variance)
- Tier 3 and 4 give similar results (~$28B), confirming Tier 1

## Recommendations

### For Your Application

1. **Use Tier 1 as primary method** - Cleanest and most reliable
2. **Monitor variance** - Flag companies with >10% variance between methods
3. **Log the method used** - Track which tier was used for each company
4. **Validate results** - Check that EBIT > Net Income and margin is reasonable

### For Specific Industries

- **Energy companies** (XOM, CVX): Tier 1 (Revenues - CostsAndExpenses) works well
- **Tech companies** (AAPL, MSFT): Tier 1 or direct OperatingIncomeLoss
- **Financial companies**: May need special handling (not covered in current implementation)

## Future Enhancements

1. **Industry-specific rules** - Different fallback orders for different sectors
2. **Non-operating items** - Better handling of equity method investments, gains/losses
3. **Quarterly data** - Extend to 10-Q forms
4. **Historical consistency** - Track if a company changes reporting methods over time

## References

- [SEC EDGAR Company Facts API](https://www.sec.gov/edgar/sec-api-documentation)
- [US-GAAP Taxonomy](https://www.fasb.org/xbrl)
- Your offline research on EBIT calculation methods

## Contact

For questions or issues with EBIT calculation, review the test scripts and debug tools provided.
