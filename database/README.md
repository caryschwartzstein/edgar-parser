# Database Schema for EDGAR Parser

**Version:** 2.0
**Created:** 2025-12-11
**Database:** PostgreSQL 14+

---

## Overview

This database stores parsed EDGAR financial data for ~374 S&P 500 companies, optimized for **Magic Formula screening** (ROCE + Earnings Yield).

### Key Features

- ✅ **Dual Period Support** - Handles both annual (10-K) and quarterly (10-Q) data
- ✅ **YTD De-cumulation** - Stores both cumulative and true quarterly values
- ✅ **Fiscal Year Aware** - Properly groups periods by fiscal year
- ✅ **Time-Series Ready** - Optimized for historical analysis and trending
- ✅ **Magic Formula Optimized** - Pre-calculated ROCE and Earnings Yield components

---

## Quick Start

### 1. Create Database

```bash
createdb edgar_financial_metrics
```

### 2. Run Schema

```bash
psql edgar_financial_metrics < database/schema.sql
```

### 3. Verify

```bash
psql edgar_financial_metrics -c "\dt"
```

You should see:
- `companies`
- `filings`
- `financial_metrics`
- `calculated_ratios`
- `market_data`
- `sector_benchmarks`
- `processing_log`

---

## Schema Diagram

```
companies (374 rows)
    ↓
filings (thousands of rows - each 10-K and 10-Q filing)
    ↓
financial_metrics (time-series data)
    ├── annual (10-K): ebit, total_debt, unrestricted_cash, assets
    └── quarterly (10-Q): ebit_ytd, ebit_quarterly, total_debt, assets
    ↓
calculated_ratios (derived metrics)
    ├── roce (using YTD EBIT for quarterly)
    ├── roce_quarterly (using de-cumulated EBIT)
    └── earnings_yield (requires market cap)
    ↓
market_data (daily market cap from external sources)
```

---

## Table Descriptions

### `companies`
Master list of S&P 500 companies (filtered for ROCE compatibility).

**Key Fields:**
- `ticker` - Stock ticker (AAPL, MSFT, etc.)
- `cik` - SEC Central Index Key
- `sector` - GICS sector classification

### `filings`
Tracks which SEC filings we've processed.

**Key Fields:**
- `filing_type` - '10-K' (annual) or '10-Q' (quarterly)
- `fiscal_year` - 2025, 2024, etc.
- `fiscal_year_end` - 2025-09-27 (end of fiscal period)
- `fiscal_quarter` - NULL for 10-K, 1-4 for 10-Q

### `financial_metrics`
Time-series financial data from SEC filings.

**Key Fields (Annual - 10-K):**
- `ebit` - Annual EBIT (non-cumulative)
- `total_debt` - Total debt
- `unrestricted_cash` - Cash for EV calculation
- `total_assets` - Total assets
- `current_liabilities` - Current liabilities

**Key Fields (Quarterly - 10-Q):**
- `ebit_ytd` - Year-to-date cumulative EBIT
- `ebit_quarterly` - De-cumulated true quarterly EBIT
- `total_debt` - Point-in-time debt (not cumulative)
- `total_assets` - Point-in-time assets

### `calculated_ratios`
Derived financial ratios and metrics.

**Key Fields:**
- `roce` - Return on Capital Employed (uses YTD EBIT for quarterly)
- `roce_quarterly` - ROCE using de-cumulated quarterly EBIT (10-Q only)
- `earnings_yield` - EBIT / Enterprise Value
- `net_debt` - Total Debt - Unrestricted Cash
- `enterprise_value` - Market Cap + Net Debt

### `market_data`
Daily market capitalization data from external sources (yfinance, etc.).

### `sector_benchmarks`
Industry performance benchmarks for comparison.

**Metrics:**
- Median ROCE by sector
- Percentile thresholds (25th, 75th, 90th)
- Average Earnings Yield

### `processing_log`
Audit trail of data loads, errors, and processing times.

---

## Important Design Decisions

### 1. Quarterly YTD vs De-cumulated Values

**Problem:** 10-Q filings report income statement items as cumulative YTD:
- Q1 EBIT = Oct-Dec (3 months)
- Q2 EBIT = Oct-Mar (6 months cumulative) ← includes Q1!

**Solution:** Store BOTH values:
```sql
-- Quarterly (10-Q) row
ebit_ytd: 100623000000        -- Cumulative Oct-Mar (from 10-Q filing)
ebit_quarterly: 28200000000   -- True Q2 only (Apr-Jun calculated)
```

### 2. Balance Sheet Items Are Point-in-Time

Balance sheet items (Assets, Debt, Cash) are **NOT** cumulative, even in 10-Q:
- They represent the actual value at the end of the fiscal period
- No de-cumulation needed
- Same column used for both 10-K and 10-Q

### 3. Fiscal Year Handling

Companies have different fiscal year ends:
- Apple: September (FY2025 ends 2025-09-27)
- Walmart: January (FY2025 ends 2025-01-31)
- Microsoft: June (FY2025 ends 2025-06-30)

Schema stores:
- `fiscal_year` - Integer year (2025)
- `fiscal_year_end` - Exact end date (2025-09-27)

### 4. JSONB Metadata Fields

Used for storing calculation details without adding columns:
- `calculation_metadata` - Warnings, notes, calculation sources
- `total_debt_components` - Breakdown of debt calculation
- `roce_components` - EBIT, Assets, Capital Employed breakdown

---

## Common Queries

### Get Latest Annual Metrics for All Companies

```sql
SELECT * FROM latest_annual_metrics
ORDER BY roce DESC;
```

### Get Quarterly Trend for Apple (Last 12 Quarters)

```sql
SELECT
    fiscal_year_end,
    ebit_quarterly,
    roce_quarterly
FROM financial_metrics fm
JOIN calculated_ratios cr ON fm.id = cr.metric_id
WHERE fm.company_id = (SELECT id FROM companies WHERE ticker = 'AAPL')
  AND fm.period_type = '10-Q'
  AND fm.ebit_quarterly IS NOT NULL
ORDER BY fm.fiscal_year_end DESC
LIMIT 12;
```

### Compare YTD vs Quarterly ROCE

```sql
SELECT
    c.ticker,
    fm.fiscal_year_end,
    cr.roce as roce_ytd,
    cr.roce_quarterly,
    (cr.roce - cr.roce_quarterly) as difference
FROM financial_metrics fm
JOIN companies c ON fm.company_id = c.id
JOIN calculated_ratios cr ON fm.id = cr.metric_id
WHERE fm.period_type = '10-Q'
  AND fm.fiscal_year = 2025
  AND cr.roce_quarterly IS NOT NULL
ORDER BY c.ticker, fm.fiscal_year_end;
```

### Top 20 Companies by ROCE (Magic Formula Screening)

```sql
SELECT
    ticker,
    company_name,
    sector,
    roce,
    earnings_yield
FROM latest_annual_metrics
WHERE roce IS NOT NULL
  AND earnings_yield IS NOT NULL
ORDER BY roce DESC
LIMIT 20;
```

### Quarter-over-Quarter Growth

```sql
WITH quarterly_data AS (
    SELECT
        c.ticker,
        fm.fiscal_year_end,
        fm.ebit_quarterly,
        LAG(fm.ebit_quarterly) OVER (
            PARTITION BY fm.company_id
            ORDER BY fm.fiscal_year_end
        ) as prev_quarter_ebit
    FROM financial_metrics fm
    JOIN companies c ON fm.company_id = c.id
    WHERE fm.period_type = '10-Q'
      AND fm.ebit_quarterly IS NOT NULL
)
SELECT
    ticker,
    fiscal_year_end,
    ebit_quarterly,
    prev_quarter_ebit,
    ((ebit_quarterly - prev_quarter_ebit)::DECIMAL / prev_quarter_ebit) * 100 as qoq_growth_pct
FROM quarterly_data
WHERE prev_quarter_ebit IS NOT NULL
  AND ticker = 'AAPL'
ORDER BY fiscal_year_end DESC
LIMIT 8;
```

---

## Data Loading

The data loader script (`scripts/load_to_database.py`) will:

1. Load company metadata
2. Insert filing records
3. Load financial metrics (annual + quarterly)
4. Calculate ratios
5. Log processing status

**Example workflow:**
```bash
# Load all parsed companies
python scripts/load_to_database.py --load-all

# Load specific company
python scripts/load_to_database.py --ticker AAPL

# Recalculate ratios
python scripts/load_to_database.py --recalculate-ratios
```

---

## Indexes

Optimized indexes for common query patterns:

- **Company lookups:** `ticker`, `cik`
- **Time-series queries:** `(company_id, fiscal_year_end)`
- **Period filtering:** `period_type`, `fiscal_year`
- **Screening:** `roce` (partial index WHERE NOT NULL)
- **Benchmarking:** `sector`

---

## Views

Pre-built views for common analyses:

- `latest_annual_metrics` - Most recent 10-K for each company
- `latest_quarterly_metrics` - Most recent 10-Q for each company
- `company_vs_sector` - Company performance vs sector benchmarks

---

## Functions

Helper functions for calculations:

- `calculate_roce(ebit, assets, current_liab)` - Calculate ROCE
- `calculate_earnings_yield(ebit, ev)` - Calculate Earnings Yield
- `update_sector_benchmarks(sector, date)` - Recalculate sector stats

---

## Maintenance

### Backup

```bash
pg_dump edgar_financial_metrics > backup_$(date +%Y%m%d).sql
```

### Vacuum

```bash
psql edgar_financial_metrics -c "VACUUM ANALYZE;"
```

### Reindex

```bash
psql edgar_financial_metrics -c "REINDEX DATABASE edgar_financial_metrics;"
```

---

## Next Steps

1. ✅ Schema created (`schema.sql`)
2. ⏳ **Build data loader** (`scripts/load_to_database.py`) - NEXT
3. ⏳ Test with 10 companies
4. ⏳ Load full S&P 500 dataset
5. ⏳ Add market cap data
6. ⏳ Calculate sector benchmarks

---

## Notes

- Database supports PostgreSQL 14+
- All monetary values stored as `BIGINT` (dollars, not pennies)
- Percentages stored as `DECIMAL(10, 4)` (e.g., 52.86 for 52.86%)
- Dates stored as `DATE` type
- JSONB used for flexible metadata

---

**Schema File:** `database/schema.sql`
**Documentation:** This README
**Next:** Build data loader script
