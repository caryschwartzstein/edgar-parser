# TODO: Add New Financial Metrics to Parser

**Status:** Ready to Implement  
**Date Created:** 2025-12-13  
**Goal:** Expand parser to extract additional financial metrics for comprehensive company analysis

---

## Overview

Add extraction for new financial metrics to support advanced screening calculations:
- Free Cash Flow (FCF) and FCF-related ratios
- EBITDA and Net Debt/EBITDA
- Revenue growth (CAGR)
- Market Cap calculations (with external stock price data)

**Approach:** Build new metric-focused calculators following existing pattern, test with JSON outputs, then update database schemas.

---

## Metrics to Add

### Income Statement Metrics
1. **Revenue** - Top-line sales
2. **Net Income** - Bottom-line profit
3. **Depreciation & Amortization (D&A)** - For EBITDA calculation

### Cash Flow Statement Metrics
4. **Operating Cash Flow (OCF)** - Cash from operations
5. **Capital Expenditures (CapEx)** - Cash spent on PP&E

### Balance Sheet Metrics
6. **Shares Outstanding** - For market cap calculation

### Derived Metrics (Calculated)
7. **EBITDA** = EBIT + D&A
8. **Free Cash Flow (FCF)** = OCF - CapEx
9. **FCF Yield** = FCF / Market Cap
10. **FCF Conversion** = FCF / Net Income
11. **Revenue Growth (CAGR)** = (Revenue_t / Revenue_t-n)^(1/n) - 1
12. **Net Debt / EBITDA** = Net Debt / EBITDA
13. **Market Cap** = Stock Price × Shares Outstanding (requires external data)
14. **Enterprise Value** = Market Cap + Net Debt (already have Net Debt)

---

## Implementation Plan

### Phase 1: Create New Calculators (Metric-Focused Pattern)

Following existing pattern (one calculator per metric or tightly-related group):

#### 1. `RevenueCalculator` 
**File:** `src/edgar_parser/revenue_calculator.py`

**Extraction Strategy:**
```
Tier 1: Revenues
Tier 2: RevenueFromContractWithCustomerExcludingAssessedTax
Tier 3: RevenueFromContractWithCustomerIncludingAssessedTax
Tier 4: SalesRevenueNet
```

**Validation:**
- ✓ Revenue > 0 (should always be positive)
- ✓ Revenue > EBIT (top line should be greater than operating income)
- ⚠ If Revenue < EBIT: Flag as data quality warning

**Returns:**
```python
{
    'value': <amount>,
    'tag': <xbrl_tag_used>,
    'fiscal_year_end': <date>,
    'filed_date': <date>,
}
```

---

#### 2. `NetIncomeCalculator`
**File:** `src/edgar_parser/net_income_calculator.py`

**Extraction Strategy:**
```
Tier 1: NetIncomeLoss
Tier 2: ProfitLoss
Tier 3: NetIncomeLossAvailableToCommonStockholdersBasic
```

**Validation:**
- Net Income can be negative (losses are valid)
- ✓ Net Income < EBIT (should be less after interest & taxes)
- ✓ Net Income < Revenue
- ⚠ If Net Income > EBIT: Flag as impossible

**Returns:**
```python
{
    'value': <amount>,
    'tag': <xbrl_tag_used>,
    'fiscal_year_end': <date>,
    'filed_date': <date>,
}
```

---

#### 3. `DACalculator` (Depreciation & Amortization)
**File:** `src/edgar_parser/da_calculator.py`

**Extraction Strategy:**
```
Tier 1: DepreciationDepletionAndAmortization (combined)
Tier 2: DepreciationAndAmortization
Tier 3: Calculate from components:
        Depreciation + AmortizationOfIntangibleAssets
```

**Tag Options:**
- Combined: `DepreciationDepletionAndAmortization`, `DepreciationAndAmortization`
- Depreciation: `Depreciation`, `DepreciationAndAmortizationExpense`
- Amortization: `AmortizationOfIntangibleAssets`, `Amortization`

**Validation:**
- ✓ D&A > 0 (should be positive expense)
- ✓ D&A < Revenue (sanity check)
- ⚠ If EBITDA < EBIT: Flag as impossible (since EBITDA = EBIT + D&A)

**Methods:**
1. `calculate_depreciation_amortization()` - Extract D&A
2. `calculate_ebitda(ebit)` - Calculate EBITDA = EBIT + D&A

**Returns (D&A):**
```python
{
    'value': <amount>,
    'method': 'Combined D&A' or 'Depreciation + Amortization (separate)',
    'tag': <xbrl_tag_used>,
    'fiscal_year_end': <date>,
    'filed_date': <date>,
    'components': {  # Only if calculated from separate components
        'depreciation': <amount>,
        'amortization': <amount>,
    }
}
```

**Returns (EBITDA):**
```python
{
    'value': <amount>,
    'ebit': <amount>,
    'depreciation_amortization': <amount>,
    'da_method': <method_used>,
    'fiscal_year_end': <date>,
    'filed_date': <date>,
}
```

**Note:** D&A can appear in both Income Statement and Cash Flow Statement. Don't overthink it - use whichever tag is found first.

---

#### 4. `CashFlowCalculator`
**File:** `src/edgar_parser/cash_flow_calculator.py`

**Metrics:**
1. Operating Cash Flow (OCF)
2. Capital Expenditures (CapEx)
3. Free Cash Flow (FCF) = OCF - CapEx

**Extraction Strategy - OCF:**
```
Tier 1: NetCashProvidedByUsedInOperatingActivities
Tier 2: CashProvidedByUsedInOperatingActivities
```

**Extraction Strategy - CapEx:**
```
Tier 1: PaymentsToAcquirePropertyPlantAndEquipment
Tier 2: PaymentsForCapitalImprovements
```

**CRITICAL: CapEx Sign Convention**
- In XBRL, CapEx is reported as a **positive number** (cash outflow)
- Store CapEx as **positive**
- Calculate FCF = OCF - CapEx (subtraction)

**Validation:**
- OCF: Minimal validation (can be negative for cash burn)
  - Optional: Flag if |OCF - Net Income| > 2x Net Income
- CapEx:
  - ✓ CapEx > 0 (companies should be investing)
  - ✓ CapEx < Revenue
  - ⚠ If CapEx = 0: Flag as unusual
  - ⚠ If CapEx > OCF: Results in negative FCF (note but valid)

**Methods:**
1. `calculate_operating_cash_flow()`
2. `calculate_capital_expenditures()`
3. `calculate_free_cash_flow(ocf, capex)` - Derives FCF

**Returns (OCF):**
```python
{
    'value': <amount>,
    'tag': <xbrl_tag_used>,
    'fiscal_year_end': <date>,
    'filed_date': <date>,
}
```

**Returns (CapEx):**
```python
{
    'value': <amount>,  # Stored as positive
    'tag': <xbrl_tag_used>,
    'fiscal_year_end': <date>,
    'filed_date': <date>,
}
```

**Returns (FCF):**
```python
{
    'value': <amount>,  # Can be negative
    'operating_cash_flow': <amount>,
    'capital_expenditures': <amount>,
    'fiscal_year_end': <date>,
    'filed_date': <date>,
}
```

---

#### 5. `SharesCalculator`
**File:** `src/edgar_parser/shares_calculator.py`

**Extraction Strategy:**
```
Tier 1: CommonStockSharesOutstanding
Tier 2: CommonStockSharesIssued (may include treasury shares)
```

**CRITICAL DIFFERENCES:**
- Uses **"shares"** units, NOT **"USD"** units
- Need to create new method: `_get_tag_value_shares()` that looks for "shares" units
- Grab **end-of-period** shares (matches balance sheet date)

**Validation:**
- ✓ Shares Outstanding > 0
- ✓ Shares should be in millions/billions range
  - ⚠ If < 1,000,000: Flag as unusual (very small float)
  - ⚠ If > 100,000,000,000: Flag as unusual

**Returns:**
```python
{
    'value': <share_count>,
    'tag': <xbrl_tag_used>,
    'fiscal_year_end': <date>,
    'filed_date': <date>,
}
```

**Note:** No need to handle stock splits - historical data already reflects splits.

---

### Phase 2: Update Parser V2

**File:** `src/edgar_parser/parser_v2.py`

#### 2.1 Add Calculator Imports
```python
from .revenue_calculator import RevenueCalculator
from .net_income_calculator import NetIncomeCalculator
from .da_calculator import DACalculator
from .cash_flow_calculator import CashFlowCalculator
from .shares_calculator import SharesCalculator
```

#### 2.2 Initialize Calculators in `__init__()`
```python
def __init__(self):
    # Existing
    self.ebit_calculator = EBITCalculator()
    self.debt_calculator = DebtCalculator()
    self.cash_calculator = CashCalculator()
    self.balance_sheet_calculator = BalanceSheetCalculator()
    
    # New
    self.revenue_calculator = RevenueCalculator()
    self.net_income_calculator = NetIncomeCalculator()
    self.da_calculator = DACalculator()
    self.cash_flow_calculator = CashFlowCalculator()
    self.shares_calculator = SharesCalculator()
```

#### 2.3 Update `_extract_period_metrics()` to call new calculators

Add to the extraction section:
```python
# Income Statement - New Metrics
revenue = self.revenue_calculator.calculate_revenue(gaap_data, form_type)
net_income = self.net_income_calculator.calculate_net_income(gaap_data, form_type)
da = self.da_calculator.calculate_depreciation_amortization(gaap_data, form_type)

# Calculate EBITDA (requires EBIT)
ebitda = None
if ebit_result and da:
    ebitda = self.da_calculator.calculate_ebitda(
        gaap_data, 
        ebit=ebit_result['value'], 
        form_type=form_type
    )

# Cash Flow Statement - New Metrics
ocf = self.cash_flow_calculator.calculate_operating_cash_flow(gaap_data, form_type)
capex = self.cash_flow_calculator.calculate_capital_expenditures(gaap_data, form_type)

# Calculate Free Cash Flow
fcf = None
if ocf and capex:
    fcf = self.cash_flow_calculator.calculate_free_cash_flow(
        ocf['value'],
        capex['value']
    )

# Balance Sheet - Shares Outstanding
shares = self.shares_calculator.calculate_shares_outstanding(gaap_data, form_type)
```

#### 2.4 Update Output Schema

Add new sections to period_metrics dict:
```python
period_metrics = {
    'fiscal_year_end': period_end,
    'filing_date': filing_info['filed'],
    'form_type': filing_info['form'],
    
    # Existing sections...
    'balance_sheet': { ... },
    'debt': { ... },
    'cash': { ... },
    'ebit': { ... },
    
    # NEW: Income Statement
    'income_statement': {
        'revenue': revenue,
        'net_income': net_income,
        'depreciation_amortization': da,
        'ebitda': ebitda,
    },
    
    # NEW: Cash Flow Statement
    'cash_flow': {
        'operating_cash_flow': ocf,
        'capital_expenditures': capex,
        'free_cash_flow': fcf,
    },
    
    # NEW: Shares
    'shares': {
        'common_shares_outstanding': shares,
    },
    
    # Existing calculated_ratios section
    'calculated_ratios': {
        'roce': { ... },
        'earnings_yield_components': { ... },
        
        # NEW: Additional Ratios
        'fcf_yield': fcf_yield,  # If market cap available
        'fcf_conversion': fcf_conversion,  # FCF / Net Income
        'net_debt_to_ebitda': net_debt_to_ebitda,  # Net Debt / EBITDA
    }
}
```

---

### Phase 3: Calculate Derived Metrics

Add these calculations to the ratios section (after extracting raw metrics):

#### 3.1 FCF Conversion Ratio
```python
# FCF Conversion = Free Cash Flow / Net Income
fcf_conversion = None
if fcf and net_income and net_income['value'] and net_income['value'] != 0:
    fcf_conversion = {
        'value': (fcf['value'] / net_income['value']) * 100,
        'fcf': fcf['value'],
        'net_income': net_income['value'],
        'interpretation': 'Percentage of net income converted to free cash flow'
    }
```

#### 3.2 Net Debt / EBITDA
```python
# Net Debt / EBITDA (leverage ratio)
net_debt_to_ebitda = None
if net_debt and ebitda and ebitda['value'] and ebitda['value'] != 0:
    ratio = net_debt / ebitda['value']
    net_debt_to_ebitda = {
        'value': ratio,
        'net_debt': net_debt,
        'ebitda': ebitda['value'],
        'interpretation': interpret_net_debt_to_ebitda(ratio)
    }

def interpret_net_debt_to_ebitda(ratio):
    """Interpret Net Debt/EBITDA leverage ratio"""
    if ratio < 0:
        return 'Net Cash Position (no debt burden)'
    elif ratio < 1:
        return 'Very Low Leverage'
    elif ratio < 2:
        return 'Low Leverage'
    elif ratio < 3:
        return 'Moderate Leverage'
    elif ratio < 4:
        return 'High Leverage'
    else:
        return 'Very High Leverage'
```

#### 3.3 FCF Yield (requires market cap)
```python
# FCF Yield = Free Cash Flow / Market Cap
# NOTE: Requires market cap from external source (yfinance, etc.)
fcf_yield = None
if fcf and market_cap and market_cap != 0:
    fcf_yield = {
        'value': (fcf['value'] / market_cap) * 100,
        'fcf': fcf['value'],
        'market_cap': market_cap,
        'interpretation': 'FCF as percentage of market cap'
    }
```

#### 3.4 Revenue Growth CAGR (requires historical data)
```python
# Revenue Growth CAGR
# This will require accessing multiple periods from historical data
# Calculate 3-year and 5-year CAGR
# CAGR = (Revenue_t / Revenue_t-n)^(1/n) - 1

# TODO: Implement after testing basic extraction
# Will need to:
# 1. Access historical revenue data from previous periods
# 2. Calculate CAGR for 3-year and 5-year windows
# 3. Handle edge cases (IPOs, missing data, etc.)
```

---

### Phase 4: Testing Strategy

**DO NOT update database schemas yet.** First validate with JSON outputs.

#### 4.1 Test Companies
Test on diverse company structures:
1. **Apple (AAPL)** - Already have test data
2. **Caterpillar (CAT)** - Industrial with complex structure
3. **Microsoft (MSFT)** - Tech with high FCF
4. **Walmart (WMT)** - Retail with different reporting

#### 4.2 Test Script
Create: `scripts/test_new_metrics.py`

```python
#!/usr/bin/env python3
"""
Test new financial metrics extraction
"""

from edgar_parser.parser_v2 import EDGARParser
import json

def test_new_metrics(ticker='AAPL'):
    # Load EDGAR data
    with open(f'data/raw_edgar/{ticker}_edgar_raw.json') as f:
        edgar_data = json.load(f)
    
    # Parse
    parser = EDGARParser()
    result = parser.parse_company_data(edgar_data, verbose=True)
    
    # Print new metrics
    latest = result['annual_periods'][0]
    
    print(f"\n{'='*60}")
    print(f"NEW METRICS TEST - {ticker}")
    print(f"{'='*60}")
    
    # Income Statement
    print("\nINCOME STATEMENT:")
    print(f"Revenue: ${latest['income_statement']['revenue']['value']:,.0f}")
    print(f"Net Income: ${latest['income_statement']['net_income']['value']:,.0f}")
    print(f"D&A: ${latest['income_statement']['depreciation_amortization']['value']:,.0f}")
    print(f"EBITDA: ${latest['income_statement']['ebitda']['value']:,.0f}")
    
    # Cash Flow
    print("\nCASH FLOW:")
    print(f"Operating Cash Flow: ${latest['cash_flow']['operating_cash_flow']['value']:,.0f}")
    print(f"CapEx: ${latest['cash_flow']['capital_expenditures']['value']:,.0f}")
    print(f"Free Cash Flow: ${latest['cash_flow']['free_cash_flow']['value']:,.0f}")
    
    # Shares
    print("\nSHARES:")
    print(f"Shares Outstanding: {latest['shares']['common_shares_outstanding']['value']:,.0f}")
    
    # Ratios
    print("\nRATIOS:")
    print(f"FCF Conversion: {latest['calculated_ratios']['fcf_conversion']['value']:.2f}%")
    print(f"Net Debt/EBITDA: {latest['calculated_ratios']['net_debt_to_ebitda']['value']:.2f}x")
    
    # Save full output
    output_path = f'data/parsed/{ticker}_new_metrics_test.json'
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nFull output saved to: {output_path}")

if __name__ == '__main__':
    test_new_metrics('AAPL')
```

#### 4.3 Validation Checklist

For each test company, verify:
- ✓ All metrics extracted successfully (or noted as unavailable)
- ✓ Values are reasonable (positive/negative as expected)
- ✓ Derived metrics calculated correctly
- ✓ Validation warnings appear when appropriate
- ✓ JSON structure is clean and parseable
- ✓ Method/tier information is logged for debugging

---

### Phase 5: Database Schema Updates (AFTER testing)

Once JSON outputs are validated, update database schemas:

#### 5.1 Update `financial_metrics` table

Add new columns for extracted metrics:
```sql
ALTER TABLE financial_metrics ADD COLUMN
    -- Income Statement
    revenue BIGINT,
    net_income BIGINT,
    depreciation_amortization BIGINT,
    da_method VARCHAR(100),
    
    -- Cash Flow
    operating_cash_flow BIGINT,
    capital_expenditures BIGINT,
    
    -- Shares
    common_shares_outstanding BIGINT;

-- Add comments
COMMENT ON COLUMN financial_metrics.revenue IS 'Total revenue/sales';
COMMENT ON COLUMN financial_metrics.net_income IS 'Net income after all expenses';
COMMENT ON COLUMN financial_metrics.depreciation_amortization IS 'D&A for EBITDA calculation';
COMMENT ON COLUMN financial_metrics.operating_cash_flow IS 'Cash from operations';
COMMENT ON COLUMN financial_metrics.capital_expenditures IS 'CapEx (stored as positive)';
COMMENT ON COLUMN financial_metrics.common_shares_outstanding IS 'Shares outstanding (end of period)';
```

#### 5.2 Update `calculated_ratios` table

Add new columns for derived metrics:
```sql
ALTER TABLE calculated_ratios ADD COLUMN
    -- Derived metrics
    ebitda BIGINT,
    free_cash_flow BIGINT,
    
    -- Ratios
    fcf_conversion DECIMAL(10, 4),  -- FCF / Net Income
    net_debt_to_ebitda DECIMAL(10, 4),  -- Net Debt / EBITDA
    fcf_yield DECIMAL(10, 4),  -- FCF / Market Cap (when available)
    
    -- Metadata
    ratio_metadata JSONB;  -- Store calculation details

-- Add comments
COMMENT ON COLUMN calculated_ratios.ebitda IS 'EBIT + Depreciation & Amortization';
COMMENT ON COLUMN calculated_ratios.free_cash_flow IS 'Operating Cash Flow - CapEx';
COMMENT ON COLUMN calculated_ratios.fcf_conversion IS 'FCF as % of Net Income';
COMMENT ON COLUMN calculated_ratios.net_debt_to_ebitda IS 'Leverage ratio';
COMMENT ON COLUMN calculated_ratios.fcf_yield IS 'FCF as % of Market Cap';
```

#### 5.3 Update views

Update `latest_annual_metrics` view to include new columns:
```sql
CREATE OR REPLACE VIEW latest_annual_metrics AS
SELECT
    c.ticker,
    c.company_name,
    c.sector,
    fm.fiscal_year,
    fm.fiscal_year_end,
    
    -- Existing metrics
    fm.ebit,
    fm.total_debt,
    fm.unrestricted_cash,
    fm.total_assets,
    fm.current_liabilities,
    
    -- NEW: Income Statement
    fm.revenue,
    fm.net_income,
    fm.depreciation_amortization,
    
    -- NEW: Cash Flow
    fm.operating_cash_flow,
    fm.capital_expenditures,
    fm.common_shares_outstanding,
    
    -- Existing ratios
    cr.roce,
    cr.earnings_yield,
    cr.enterprise_value,
    cr.net_debt,
    
    -- NEW: Derived metrics
    cr.ebitda,
    cr.free_cash_flow,
    cr.fcf_conversion,
    cr.net_debt_to_ebitda,
    cr.fcf_yield
FROM companies c
JOIN financial_metrics fm ON c.id = fm.company_id
LEFT JOIN calculated_ratios cr ON fm.id = cr.metric_id
WHERE fm.period_type = '10-K'
  AND fm.fiscal_year_end = (
    SELECT MAX(fiscal_year_end)
    FROM financial_metrics
    WHERE company_id = c.id AND period_type = '10-K'
  );
```

---

## Quarterly vs Annual Support

**Current Status:** All new metrics should work for both 10-K and 10-Q

**Notes:**
- Income Statement items (Revenue, Net Income, D&A): May need YTD handling for 10-Q
  - For now, extract as-is; deal with cumulative/de-cumulative later if needed
- Balance Sheet items (Shares Outstanding): Point-in-time, same for quarterly/annual
- Cash Flow items (OCF, CapEx): May need YTD handling for 10-Q
  - For now, extract as-is; deal with edge cases later

**Decision:** Start with annual (10-K) support, validate, then add quarterly (10-Q) nuances.

---

## Open Questions / Future Work

1. **Revenue Growth CAGR:**
   - Requires accessing multiple historical periods
   - Need to handle edge cases (IPOs, missing periods)
   - Implement after basic extraction is working

2. **Market Cap Integration:**
   - Need external data source (yfinance, Alpha Vantage, etc.)
   - Should be separate from EDGAR parsing
   - Required for: FCF Yield, Earnings Yield final calculation

3. **Stock Price:**
   - Need daily stock prices for Market Cap calculation
   - Consider creating separate `MarketDataFetcher` class
   - Store in `market_data` table (already in schema)

4. **Validation Thresholds:**
   - Current validation is basic
   - May want to add industry-specific thresholds
   - Consider adding data quality scoring

5. **Quarterly Data Handling:**
   - YTD vs quarterly values for income statement
   - De-cumulation logic (like current EBIT quarterly handling)
   - Test with 10-Q filings

---

## File Checklist

### New Files to Create:
- [ ] `src/edgar_parser/revenue_calculator.py`
- [ ] `src/edgar_parser/net_income_calculator.py`
- [ ] `src/edgar_parser/da_calculator.py`
- [ ] `src/edgar_parser/cash_flow_calculator.py`
- [ ] `src/edgar_parser/shares_calculator.py`
- [ ] `scripts/test_new_metrics.py`

### Files to Modify:
- [ ] `src/edgar_parser/parser_v2.py` - Add new calculators and update extraction logic
- [ ] `database/schema.sql` - Add new columns (AFTER testing)

### Test Data Needed:
- [ ] Apple (AAPL) - Already have
- [ ] Caterpillar (CAT) - Download if needed
- [ ] Microsoft (MSFT) - Download if needed
- [ ] Walmart (WMT) - Download if needed

---

## Success Criteria

Before moving to database schema updates:
- ✓ All 5 new calculators implemented and working
- ✓ Parser V2 updated to call new calculators
- ✓ Test script runs successfully on 3+ companies
- ✓ JSON output includes all new metrics
- ✓ Validation warnings appear appropriately
- ✓ Derived metrics calculate correctly
- ✓ No errors or crashes during parsing

After database updates:
- ✓ Schema migration runs successfully
- ✓ Data loads into new columns
- ✓ Views updated and working
- ✓ Can query new metrics via SQL
- ✓ Documentation updated

---

## Notes

- **Pattern Consistency:** All new calculators follow same pattern as existing ones
- **Testing First:** Validate with JSON before touching database
- **Metric-Focused:** One calculator per metric/group, not statement-focused
- **Sign Conventions:** CapEx stored as positive, FCF = OCF - CapEx
- **Units Matter:** Shares uses "shares" not "USD" - need special handling
- **Quarterly Support:** Build annual support first, add quarterly nuances later

---

## References

- Existing calculators: `ebit_calculator.py`, `debt_calculator.py`, `cash_calculator.py`
- Database schema: `database/schema.sql`
- Parser V2: `src/edgar_parser/parser_v2.py`
- Past conversation: Financial metrics extraction strategies and XBRL tag fallbacks
