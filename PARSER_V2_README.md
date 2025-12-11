# EDGAR Parser V2 - Complete Refactor

## Overview

The EDGAR Parser has been completely refactored to implement the **Financial Metrics Extraction Guide** (December 2024). This version provides comprehensive, accurate financial metrics extraction for Magic Formula screening.

## What's New

### Core Metrics Calculated

1. **ROCE (Return on Capital Employed)**
   - Formula: `ROCE = EBIT / (Total Assets - Current Liabilities) × 100`
   - Interpretation included (Excellent > 25%, Good > 15%, etc.)

2. **Earnings Yield Components**
   - Formula: `Earnings Yield = EBIT / (Market Cap + Net Debt)`
   - Where: `Net Debt = Total Debt - Unrestricted Cash`
   - Note: Market Cap must be provided externally (ready for integration)

### Modular Calculator Architecture

The parser now uses specialized calculator modules:

#### 1. **EBIT Calculator** (`ebit_calculator.py`)
- **4-Tier Waterfall Strategy** with validation:
  - **Tier 1**: Direct OperatingIncomeLoss OR Revenues - CostsAndExpenses (with validation)
  - **Tier 2**: Revenues - COGS - Operating Expenses
  - **Tier 3**: Net Income + Tax + Interest
  - **Tier 4**: Pre-tax Income + Interest
- **Validation**: Revenues - CostsAndExpenses validated against pre-tax income (±$1M tolerance)
- Returns method used, tier, and validation status

#### 2. **Debt Calculator** (`debt_calculator.py`)
- **3-Component Total Debt Structure**:
  - Component 1: Long-Term Debt (non-current portion)
  - Component 2: Current Portion of Long-Term Debt
  - Component 3: Short-Term Borrowings
- **Prevents double-counting**:
  - Detects tags that include current maturities
  - Identifies duplicate tags with same values
- **Handles both structures**:
  - 3-component: LT non-current + LT current + ST borrowings
  - 2-component: LT including current + ST borrowings

#### 3. **Cash Calculator** (`cash_calculator.py`)
- **Distinguishes Restricted vs Unrestricted Cash**:
  - Unrestricted cash for Enterprise Value (restricted not available to pay debt)
  - Total cash for balance sheet
- **Priority order**:
  1. Direct unrestricted cash tag (most reliable)
  2. Calculate: Total Cash - Restricted Cash
  3. Calculate: Total Cash - Restricted Current - Restricted Non-current

#### 4. **Balance Sheet Calculator** (`balance_sheet_calculator.py`)
- Extracts Assets and Current Liabilities
- Calculates Capital Employed
- Includes fallback strategies (rarely needed)

### Historical Data Support

- Extracts **ALL fiscal periods** from EDGAR data
- Each period gets complete metric calculations
- No need to re-fetch data for historical analysis
- Most recent period flagged automatically

### Comprehensive Logging

Each period includes:
- **Metrics Extracted**: Value, method, tier (for EBIT), validation results
- **Calculations**: ROCE and Earnings Yield components with formulas
- **Warnings**: Any data quality issues or fallback methods used
- **Timestamps**: When parsed

## Usage

### Basic Usage

```python
from edgar_parser.parser_v2 import EDGARParser

# Initialize parser
parser = EDGARParser()

# Parse EDGAR data (from SEC API)
result = parser.parse_company_data(edgar_data, verbose=True)

# Access most recent period
most_recent = result['annual_periods'][0]

# Get ROCE
roce = most_recent['calculated_ratios']['roce']['value']
print(f"ROCE: {roce:.2f}%")

# Get Earnings Yield components (ready for Market Cap)
ey_components = most_recent['calculated_ratios']['earnings_yield_components']
print(f"EBIT: ${ey_components['ebit']:,}")
print(f"Net Debt: ${ey_components['net_debt']:,}")

# When you have Market Cap from market data API:
earnings_yield = parser.calculate_earnings_yield_with_market_cap(
    ey_components,
    market_cap=3_000_000_000_000  # Example: $3T
)
print(f"Earnings Yield: {earnings_yield['value']:.2f}%")
```

### Output Structure

```json
{
  "metadata": {
    "company_name": "Apple Inc.",
    "cik": "320193",
    "parsed_at": "2025-12-05T...",
    "parser_version": "2.0",
    "total_periods": 18,
    "guide_version": "Financial Metrics Extraction Guide - December 2024"
  },
  "annual_periods": [
    {
      "fiscal_year_end": "2025-09-27",
      "filing_date": "2024-11-01",
      "form": "10-K",
      "is_most_recent": true,
      "metrics": {
        "ebit": {
          "value": 133050000000,
          "method": "Direct OperatingIncomeLoss",
          "tier": 1,
          "sources": {...}
        },
        "total_debt": {
          "value": 98657000000,
          "method": "3-component (LT non-current + LT current + ST borrowings)",
          "components": {...}
        },
        "cash": {
          "unrestricted_cash": 35934000000,
          "total_cash": 35934000000,
          "restricted_cash": 0,
          "method": "Direct unrestricted (no restricted cash)"
        },
        "assets": {
          "value": 359241000000,
          "method": "Direct Assets tag"
        },
        "current_liabilities": {
          "value": 165631000000,
          "method": "Direct LiabilitiesCurrent tag"
        }
      },
      "calculated_ratios": {
        "roce": {
          "value": 68.72,
          "formula": "ROCE = (EBIT / Capital Employed) × 100",
          "components": {
            "ebit": 133050000000,
            "total_assets": 359241000000,
            "current_liabilities": 165631000000,
            "capital_employed": 193610000000
          },
          "interpretation": "Excellent - High quality business with strong capital efficiency"
        },
        "earnings_yield_components": {
          "ebit": 133050000000,
          "total_debt": 98657000000,
          "unrestricted_cash": 35934000000,
          "net_debt": 62723000000,
          "formula": "Earnings Yield = EBIT / (Market Cap + Net Debt)",
          "note": "Market Cap must be provided from external market data source",
          "ready_for_calculation": true
        }
      },
      "calculation_log": {
        "timestamp": "2025-12-05T...",
        "metrics_extracted": {...},
        "calculations": {...}
      }
    }
  ]
}
```

## Testing

Test the parser with the included script:

```bash
python scripts/test_updated_parser.py
```

Or test with specific companies:

```python
python -c "
import json
from edgar_parser.parser_v2 import EDGARParser

with open('data/apple_edgar_live.json') as f:
    edgar_data = json.load(f)

parser = EDGARParser()
result = parser.parse_company_data(edgar_data, verbose=True)
"
```

## Example Output (Apple Inc.)

```
================================================================================
EDGAR Parser V2: Apple Inc. (CIK: 320193)
================================================================================

Found 18 fiscal periods

================================================================================
PARSING SUMMARY
================================================================================

Company: Apple Inc.
CIK: 320193
Total periods extracted: 18

Fiscal Periods:
Year End        ROCE       EBIT Method                    Status
--------------------------------------------------------------------------------
2025-09-27      68.72%     Direct OperatingIncomeLoss     ← MOST RECENT
2024-09-28      65.34%     Direct OperatingIncomeLoss
2023-09-30      55.14%     Direct OperatingIncomeLoss
2022-09-24      60.09%     Direct OperatingIncomeLoss
...
```

## Files Changed/Created

### New Files
- `src/edgar_parser/ebit_calculator.py` - EBIT calculation with 4-tier waterfall
- `src/edgar_parser/debt_calculator.py` - 3-component debt calculation
- `src/edgar_parser/cash_calculator.py` - Unrestricted vs restricted cash
- `src/edgar_parser/balance_sheet_calculator.py` - Assets & liabilities
- `scripts/test_updated_parser.py` - Test script

### Updated Files
- `src/edgar_parser/parser_v2.py` - Complete rewrite with modular calculators
- `src/edgar_parser/__init__.py` - Updated to export new parser and calculators

### Old Files (Preserved)
- `src/edgar_parser/parser.py` - Original parser (not used)

## Key Features

### Data Quality
- ✅ All metrics from same fiscal period (date consistency)
- ✅ Validation of calculated EBIT against pre-tax income
- ✅ Detection of duplicate tags with same values
- ✅ Warning system for data quality issues
- ✅ Graceful handling of missing components

### Flexibility
- ✅ Handles different company reporting structures
- ✅ Works with energy companies (CVX, XOM), manufacturing (CAT), tech (AAPL)
- ✅ Multiple fallback strategies per metric
- ✅ Comprehensive logging for debugging

### Performance
- ✅ Extracts all historical periods in one pass
- ✅ No need to re-fetch data
- ✅ Efficient tag lookup with priority ordering

## Integration with Market Data

The parser is ready for market cap integration. When you have access to a market data API (yfinance, Alpha Vantage, etc.):

```python
# Example with yfinance
import yfinance as yf

# Get market cap for a ticker
ticker = yf.Ticker("AAPL")
market_cap = ticker.info['marketCap']

# Calculate earnings yield
ey_components = most_recent['calculated_ratios']['earnings_yield_components']
earnings_yield = parser.calculate_earnings_yield_with_market_cap(
    ey_components,
    market_cap
)

print(f"Earnings Yield: {earnings_yield['value']:.2f}%")
```

## Next Steps

1. **Market Cap Integration**: Add module to fetch market cap from external API
2. **Database Schema Update**: Modify database loader to store all periods
3. **Screening Tool**: Build Magic Formula screener using ROCE + Earnings Yield
4. **Validation**: Test with full S&P 500 dataset

## Guide Compliance

This parser fully implements the **Financial Metrics Extraction Guide** including:
- ✅ All EBIT tier strategies with validation
- ✅ 3-component debt structure
- ✅ Unrestricted cash for EV
- ✅ All tag priorities and fallbacks
- ✅ Data quality checks from guide
- ✅ Validated against CVX, CAT, XOM examples

## Support

For questions or issues, refer to:
- `financial-metrics-extraction-guide.md` - Detailed metric extraction strategy
- Parser source code comments - Implementation details
- Test output JSON - Example results structure
