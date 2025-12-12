# Database Schema Design for Quarterly Data

**Date:** 2025-12-11
**Status:** Design Proposal

---

## Current Schema Analysis

The existing `schema.sql` has:
- ✅ `filings` table with `fiscal_quarter` field (1-4 for quarterly, NULL for annual)
- ✅ `financial_metrics` table for time-series data
- ✅ `calculated_ratios` table for derived metrics
- ⚠️ **Issue:** No distinction between YTD vs true quarterly values for income statement items

## Key Challenge: YTD vs Quarterly Values

**Problem:** Income statement items in 10-Q filings are **cumulative YTD**:
- Q1 EBIT = Oct-Dec (3 months)
- Q2 EBIT = Oct-Mar (6 months cumulative)
- Q3 EBIT = Oct-Sep (9 months cumulative)

**Our Parser Now Provides:**
- `ytd_value`: Original cumulative value from 10-Q
- `quarterly_value`: De-cumulated true quarterly value
- Both are valuable for different analyses

---

## Design Options

### Option 1: Single Table with YTD/Quarterly Columns ✅ RECOMMENDED

**Approach:** Extend existing `financial_metrics` table with separate columns for YTD vs quarterly values.

```sql
ALTER TABLE financial_metrics
ADD COLUMN ebit_ytd BIGINT,                    -- Year-to-date EBIT (from 10-Q)
ADD COLUMN ebit_quarterly BIGINT,              -- De-cumulated quarterly EBIT
ADD COLUMN revenue_ytd BIGINT,                 -- Future: YTD revenue
ADD COLUMN revenue_quarterly BIGINT,           -- Future: True quarterly revenue
ADD COLUMN is_ytd_cumulative BOOLEAN DEFAULT FALSE;  -- Flag for 10-Q vs 10-K

-- Rename existing columns for clarity
ALTER TABLE financial_metrics
RENAME COLUMN operating_income TO ebit;        -- For 10-K (non-cumulative)
```

**Pros:**
- ✅ Single source of truth - one table to query
- ✅ Easy to compare YTD vs quarterly in same row
- ✅ Preserves both values for validation
- ✅ Minimal schema changes
- ✅ Works with existing views and functions

**Cons:**
- ⚠️ More NULL values (quarterly values only for 10-Q, YTD only for 10-Q)
- ⚠️ Slightly wider table

---

### Option 2: Separate Quarterly Metrics Table ❌ NOT RECOMMENDED

**Approach:** Create `quarterly_financial_metrics` table separate from annual.

```sql
CREATE TABLE quarterly_financial_metrics (
    id SERIAL PRIMARY KEY,
    filing_id INTEGER REFERENCES filings(id),
    company_id INTEGER REFERENCES companies(id),
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER NOT NULL,  -- 1, 2, 3, 4

    -- YTD values (from 10-Q)
    ebit_ytd BIGINT,
    revenue_ytd BIGINT,

    -- De-cumulated quarterly values
    ebit_quarterly BIGINT,
    revenue_quarterly BIGINT,

    -- Balance sheet (point-in-time, not cumulative)
    total_assets BIGINT,
    total_debt BIGINT,
    ...
);
```

**Pros:**
- ✅ Clean separation of annual vs quarterly
- ✅ No NULL values

**Cons:**
- ❌ Data duplication (balance sheet items same in both tables)
- ❌ More complex queries (need UNIONs)
- ❌ Two tables to maintain
- ❌ Harder to compare annual vs quarterly trends

---

### Option 3: Metadata JSONB Column ❌ NOT RECOMMENDED

**Approach:** Store YTD/quarterly distinction in JSONB metadata.

```sql
ALTER TABLE financial_metrics
ADD COLUMN income_statement_metadata JSONB;

-- Example data:
{
  "ebit": {
    "ytd_value": 100623000000,
    "quarterly_value": 28200000000,
    "calculation_note": "De-cumulated from YTD"
  }
}
```

**Pros:**
- ✅ Flexible schema
- ✅ Can store additional metadata

**Cons:**
- ❌ Can't index JSONB values efficiently for numeric queries
- ❌ Can't use in WHERE/ORDER BY without extracting
- ❌ Harder to query and aggregate
- ❌ Not suitable for time-series analytics

---

## Recommended Schema: Option 1 (Extended Single Table)

### Updated `filings` Table

```sql
CREATE TABLE filings (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    filing_date DATE NOT NULL,
    filing_type VARCHAR(10) NOT NULL,  -- '10-K', '10-Q'
    fiscal_year INTEGER NOT NULL,      -- 2025, 2024, etc.
    fiscal_year_end DATE NOT NULL,     -- 2025-09-27 (Apple)
    fiscal_quarter INTEGER,            -- NULL for 10-K, 1-4 for 10-Q
    accession_number VARCHAR(20) UNIQUE,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_quality_score FLOAT,
    UNIQUE(company_id, fiscal_year, fiscal_quarter)
);

CREATE INDEX idx_filings_fiscal_year ON filings(fiscal_year);
CREATE INDEX idx_filings_quarter ON filings(fiscal_quarter);
```

### Updated `financial_metrics` Table

```sql
CREATE TABLE financial_metrics (
    id SERIAL PRIMARY KEY,
    filing_id INTEGER REFERENCES filings(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    fiscal_year_end DATE NOT NULL,
    metric_date DATE NOT NULL,  -- Fiscal period end date
    period_type VARCHAR(10) NOT NULL,  -- '10-K' or '10-Q'

    -- Balance Sheet Items (point-in-time, same for annual/quarterly)
    total_assets BIGINT,
    current_liabilities BIGINT,
    total_debt BIGINT,
    unrestricted_cash BIGINT,  -- For EV calculation
    total_cash BIGINT,         -- Total cash including restricted

    -- Income Statement Items - EBIT
    -- For 10-K: use ebit field
    -- For 10-Q: use both ebit_ytd and ebit_quarterly
    ebit BIGINT,                -- Annual (10-K) or NULL for 10-Q
    ebit_ytd BIGINT,            -- Year-to-date (10-Q only)
    ebit_quarterly BIGINT,      -- De-cumulated quarterly (10-Q only)
    ebit_method VARCHAR(100),   -- 'Direct OperatingIncomeLoss', 'Tier 2', etc.
    ebit_tier INTEGER,          -- 1, 2, 3, 4

    -- Future: Add revenue, COGS, etc. with same pattern
    -- revenue BIGINT,
    -- revenue_ytd BIGINT,
    -- revenue_quarterly BIGINT,

    -- Metadata
    calculation_metadata JSONB,  -- Store calculation notes, sources, warnings
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(company_id, fiscal_year, fiscal_year_end, period_type)
);

CREATE INDEX idx_metrics_company ON financial_metrics(company_id);
CREATE INDEX idx_metrics_fiscal_year ON financial_metrics(fiscal_year);
CREATE INDEX idx_metrics_period_type ON financial_metrics(period_type);
CREATE INDEX idx_metrics_company_year ON financial_metrics(company_id, fiscal_year);
```

### Updated `calculated_ratios` Table

```sql
CREATE TABLE calculated_ratios (
    id SERIAL PRIMARY KEY,
    metric_id INTEGER REFERENCES financial_metrics(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    fiscal_year_end DATE NOT NULL,
    calculation_date DATE NOT NULL,
    period_type VARCHAR(10) NOT NULL,  -- '10-K' or '10-Q'

    -- ROCE - Use YTD EBIT for quarterly
    roce DECIMAL(10, 4),
    roce_components JSONB,  -- Store EBIT, Assets, Current Liab breakdown

    -- ROCE using quarterly EBIT (10-Q only)
    roce_quarterly DECIMAL(10, 4),  -- Uses ebit_quarterly instead of ebit_ytd

    -- Earnings Yield components
    net_debt BIGINT,
    enterprise_value BIGINT,  -- Requires market cap
    earnings_yield DECIMAL(10, 4),

    -- Metadata
    calculation_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(company_id, fiscal_year, fiscal_year_end, period_type)
);

CREATE INDEX idx_ratios_company ON calculated_ratios(company_id);
CREATE INDEX idx_ratios_fiscal_year ON calculated_ratios(fiscal_year);
CREATE INDEX idx_ratios_period_type ON calculated_ratios(period_type);
```

---

## Data Loading Strategy

### Step 1: Parse JSON Files

For each period in parsed JSON:
```python
# From: AAPL_parsed_with_quarterly.json
{
  "fiscal_year": "2025",
  "fiscal_year_end": "2025-06-28",
  "form": "10-Q",
  "metrics": {
    "ebit": {
      "value": 100623000000,
      "ytd_value": 100623000000,
      "quarterly_value": 28200000000,
      "method": "Direct OperatingIncomeLoss",
      "tier": 1
    },
    "total_debt": { "value": 101698000000 },
    "cash": { "unrestricted_cash": 36269000000 }
  }
}
```

### Step 2: Insert into Database

```python
# 1. Insert/update filing record
filing_id = insert_filing(
    company_id=company_id,
    filing_date="2025-08-01",
    filing_type="10-Q",
    fiscal_year=2025,
    fiscal_year_end="2025-06-28",
    fiscal_quarter=3  # Infer from date
)

# 2. Insert financial metrics
metrics_id = insert_financial_metrics(
    filing_id=filing_id,
    company_id=company_id,
    fiscal_year=2025,
    fiscal_year_end="2025-06-28",
    metric_date="2025-06-28",
    period_type="10-Q",

    # Balance sheet (point-in-time)
    total_assets=331495000000,
    current_liabilities=141120000000,
    total_debt=101698000000,
    unrestricted_cash=36269000000,

    # Income statement (quarterly)
    ebit=None,  # NULL for 10-Q
    ebit_ytd=100623000000,
    ebit_quarterly=28200000000,
    ebit_method="Direct OperatingIncomeLoss",
    ebit_tier=1,

    # Metadata
    calculation_metadata={
        "ebit_calculation_note": "De-cumulated from YTD",
        "parser_version": "2.0",
        "quarterly_delta_enabled": True
    }
)

# 3. Calculate and insert ratios
insert_calculated_ratios(
    metric_id=metrics_id,
    company_id=company_id,
    fiscal_year=2025,
    fiscal_year_end="2025-06-28",
    period_type="10-Q",

    # ROCE using YTD EBIT
    roce=52.86,  # (100623000000 / (331495000000 - 141120000000)) * 100

    # ROCE using quarterly EBIT
    roce_quarterly=14.83,  # (28200000000 / (331495000000 - 141120000000)) * 100

    # Components
    roce_components={
        "ebit_ytd": 100623000000,
        "ebit_quarterly": 28200000000,
        "capital_employed": 190375000000
    }
)
```

---

## Query Patterns

### 1. Get All Annual Metrics for a Company

```sql
SELECT
    fm.fiscal_year,
    fm.fiscal_year_end,
    fm.ebit,
    fm.total_debt,
    fm.unrestricted_cash,
    cr.roce,
    cr.earnings_yield
FROM financial_metrics fm
LEFT JOIN calculated_ratios cr ON fm.id = cr.metric_id
WHERE fm.company_id = 123
  AND fm.period_type = '10-K'
ORDER BY fm.fiscal_year DESC;
```

### 2. Get Quarterly Trend for Last 12 Quarters

```sql
SELECT
    fm.fiscal_year,
    fm.fiscal_year_end,
    fm.ebit_quarterly,  -- True quarterly EBIT
    fm.total_debt,
    cr.roce_quarterly   -- ROCE using quarterly EBIT
FROM financial_metrics fm
LEFT JOIN calculated_ratios cr ON fm.id = cr.metric_id
WHERE fm.company_id = 123
  AND fm.period_type = '10-Q'
  AND fm.ebit_quarterly IS NOT NULL  -- Only quarters with de-cumulated data
ORDER BY fm.fiscal_year_end DESC
LIMIT 12;
```

### 3. Compare YTD vs Quarterly ROCE

```sql
SELECT
    fm.fiscal_year,
    fm.fiscal_year_end,
    fm.ebit_ytd,
    fm.ebit_quarterly,
    cr.roce as roce_ytd,           -- Using YTD EBIT
    cr.roce_quarterly,              -- Using quarterly EBIT
    (cr.roce - cr.roce_quarterly) as ytd_vs_quarterly_diff
FROM financial_metrics fm
JOIN calculated_ratios cr ON fm.id = cr.metric_id
WHERE fm.company_id = 123
  AND fm.period_type = '10-Q'
  AND fm.fiscal_year = 2025
ORDER BY fm.fiscal_year_end;
```

### 4. Get All Periods (Annual + Quarterly) Ordered

```sql
SELECT
    fm.fiscal_year,
    fm.fiscal_year_end,
    fm.period_type,
    COALESCE(fm.ebit, fm.ebit_quarterly) as ebit_value,
    CASE
        WHEN fm.period_type = '10-K' THEN 'Annual'
        WHEN fm.period_type = '10-Q' THEN 'Quarterly'
    END as period_label,
    cr.roce
FROM financial_metrics fm
LEFT JOIN calculated_ratios cr ON fm.id = cr.metric_id
WHERE fm.company_id = 123
ORDER BY fm.fiscal_year_end DESC;
```

### 5. Quarter-over-Quarter Growth

```sql
WITH quarterly_data AS (
    SELECT
        fm.fiscal_year,
        fm.fiscal_year_end,
        fm.ebit_quarterly,
        LAG(fm.ebit_quarterly) OVER (
            PARTITION BY fm.company_id
            ORDER BY fm.fiscal_year_end
        ) as prev_quarter_ebit
    FROM financial_metrics fm
    WHERE fm.company_id = 123
      AND fm.period_type = '10-Q'
      AND fm.ebit_quarterly IS NOT NULL
)
SELECT
    fiscal_year,
    fiscal_year_end,
    ebit_quarterly,
    prev_quarter_ebit,
    ((ebit_quarterly - prev_quarter_ebit)::DECIMAL / prev_quarter_ebit) * 100 as qoq_growth_pct
FROM quarterly_data
WHERE prev_quarter_ebit IS NOT NULL
ORDER BY fiscal_year_end DESC;
```

---

## Migration Plan

### Phase 1: Schema Updates (Immediate)

1. **Backup existing database**
2. **Add new columns** to `financial_metrics`:
   ```sql
   ALTER TABLE financial_metrics
   ADD COLUMN fiscal_year INTEGER,
   ADD COLUMN ebit_ytd BIGINT,
   ADD COLUMN ebit_quarterly BIGINT,
   ADD COLUMN ebit_method VARCHAR(100),
   ADD COLUMN ebit_tier INTEGER,
   ADD COLUMN period_type VARCHAR(10),
   ADD COLUMN calculation_metadata JSONB;
   ```

3. **Add new columns** to `calculated_ratios`:
   ```sql
   ALTER TABLE calculated_ratios
   ADD COLUMN fiscal_year INTEGER,
   ADD COLUMN period_type VARCHAR(10),
   ADD COLUMN roce_quarterly DECIMAL(10, 4),
   ADD COLUMN roce_components JSONB;
   ```

4. **Update indexes**

### Phase 2: Data Loading Script

Create `scripts/load_to_database.py`:
```python
def load_parsed_file(filepath, db_connection):
    """Load a parsed JSON file into the database."""

    with open(filepath) as f:
        data = json.load(f)

    company_id = get_or_create_company(data['metadata'])

    # Load annual periods
    for period in data['annual_periods']:
        load_annual_period(period, company_id, db_connection)

    # Load quarterly periods
    for period in data['quarterly_periods']:
        load_quarterly_period(period, company_id, db_connection)

def load_quarterly_period(period, company_id, db):
    """Load a quarterly period with YTD and quarterly values."""

    ebit = period['metrics'].get('ebit', {})

    db.execute("""
        INSERT INTO financial_metrics (
            company_id, fiscal_year, fiscal_year_end,
            metric_date, period_type,
            ebit_ytd, ebit_quarterly, ebit_method, ebit_tier,
            total_debt, unrestricted_cash, total_assets, current_liabilities,
            calculation_metadata
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        company_id,
        period['fiscal_year'],
        period['fiscal_year_end'],
        period['fiscal_year_end'],  # metric_date = fiscal_year_end
        period['form'],  # '10-Q'
        ebit.get('ytd_value'),
        ebit.get('quarterly_value'),
        ebit.get('method'),
        ebit.get('tier'),
        period['metrics']['total_debt']['value'],
        period['metrics']['cash']['unrestricted_cash'],
        period['metrics']['assets']['value'],
        period['metrics']['current_liabilities']['value'],
        json.dumps({
            'calculation_note': ebit.get('calculation_note'),
            'is_calculated': ebit.get('is_calculated', False)
        })
    ))
```

### Phase 3: Verification

1. Load 10 test companies
2. Run verification queries
3. Compare database results to JSON files
4. Validate all indexes working

### Phase 4: Full S&P 500 Load

1. Parse remaining ~364 companies
2. Load all to database
3. Build sector benchmarks
4. Create materialized views for common queries

---

## Benefits of This Design

### ✅ Flexibility
- Single query to get annual or quarterly data
- Easy to add more income statement items later (revenue, COGS, etc.)
- Can compare YTD vs quarterly in same query

### ✅ Performance
- Indexed on fiscal_year, period_type for fast filtering
- Can query only annual or only quarterly efficiently
- Window functions work well for QoQ growth

### ✅ Accuracy
- Preserves both YTD and quarterly values
- Clear distinction between 10-K (annual) and 10-Q (quarterly)
- Metadata field for calculation notes and debugging

### ✅ Maintainability
- Single table to maintain
- Consistent column names
- Easy to understand schema

---

## Next Steps

1. **Review this design** - Get approval on schema
2. **Write migration SQL** - Create `schema_v2.sql` with ALTER statements
3. **Build data loader** - Create `scripts/load_to_database.py`
4. **Test with 10 companies** - Validate data loading works
5. **Create queries** - Build common query patterns
6. **Document** - Add examples to README

---

**Recommendation:** Proceed with **Option 1 (Extended Single Table)** approach.

This provides the best balance of:
- Simplicity (one table for all metrics)
- Flexibility (separate YTD and quarterly columns)
- Query performance (can filter/aggregate easily)
- Future extensibility (add revenue, COGS with same pattern)
