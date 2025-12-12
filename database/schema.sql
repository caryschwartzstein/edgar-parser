-- ============================================================================
-- EDGAR Financial Metrics Database Schema
-- ============================================================================
-- Version: 2.0
-- Created: 2025-12-11
-- Purpose: Store parsed EDGAR data with quarterly support
--
-- Key Features:
-- - Supports both annual (10-K) and quarterly (10-Q) data
-- - Handles YTD vs de-cumulated quarterly values for income statement items
-- - Preserves fiscal year information
-- - Optimized for Magic Formula screening (ROCE + Earnings Yield)
-- ============================================================================


-- ============================================================================
-- COMPANIES TABLE - Master company list
-- ============================================================================
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    cik VARCHAR(10) UNIQUE NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    sector VARCHAR(100),
    industry VARCHAR(100),
    exchange VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_companies_ticker ON companies(ticker);
CREATE INDEX idx_companies_cik ON companies(cik);
CREATE INDEX idx_companies_sector ON companies(sector);

COMMENT ON TABLE companies IS 'Master list of S&P 500 companies (filtered for Magic Formula compatibility)';
COMMENT ON COLUMN companies.cik IS 'SEC Central Index Key (CIK)';


-- ============================================================================
-- FILINGS TABLE - Track which SEC filings we've processed
-- ============================================================================
CREATE TABLE filings (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    filing_date DATE NOT NULL,
    filing_type VARCHAR(10) NOT NULL,  -- '10-K', '10-Q'
    fiscal_year INTEGER NOT NULL,      -- 2025, 2024, etc.
    fiscal_year_end DATE NOT NULL,     -- 2025-09-27 (end of fiscal period)
    fiscal_quarter INTEGER,            -- NULL for 10-K, 1-4 for 10-Q
    accession_number VARCHAR(20) UNIQUE,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parser_version VARCHAR(20),
    data_quality_score FLOAT,
    UNIQUE(company_id, fiscal_year, fiscal_year_end, filing_type)
);

CREATE INDEX idx_filings_company ON filings(company_id);
CREATE INDEX idx_filings_fiscal_year ON filings(fiscal_year);
CREATE INDEX idx_filings_type ON filings(filing_type);
CREATE INDEX idx_filings_company_year ON filings(company_id, fiscal_year);

COMMENT ON TABLE filings IS 'Tracks processed SEC filings (10-K annual, 10-Q quarterly)';
COMMENT ON COLUMN filings.fiscal_quarter IS 'NULL for annual 10-K, 1-4 for quarterly 10-Q';


-- ============================================================================
-- FINANCIAL METRICS TABLE - Time series financial data
-- ============================================================================
CREATE TABLE financial_metrics (
    id SERIAL PRIMARY KEY,
    filing_id INTEGER REFERENCES filings(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    fiscal_year_end DATE NOT NULL,
    metric_date DATE NOT NULL,  -- Same as fiscal_year_end (period end date)
    period_type VARCHAR(10) NOT NULL,  -- '10-K' or '10-Q'

    -- Balance Sheet Items (point-in-time, same for annual/quarterly)
    total_assets BIGINT,
    current_liabilities BIGINT,

    -- Debt Components (for Enterprise Value calculation)
    total_debt BIGINT,
    total_debt_components JSONB,  -- Breakdown of debt calculation

    -- Cash Components (for Enterprise Value calculation)
    unrestricted_cash BIGINT,  -- Used in EV calculation
    total_cash BIGINT,         -- Total cash including restricted
    cash_components JSONB,     -- Breakdown of cash calculation

    -- Income Statement - EBIT
    -- Annual (10-K): Use ebit field
    -- Quarterly (10-Q): Use ebit_ytd and ebit_quarterly
    ebit BIGINT,                -- Annual EBIT (10-K only)
    ebit_ytd BIGINT,            -- Year-to-date cumulative EBIT (10-Q only)
    ebit_quarterly BIGINT,      -- De-cumulated quarterly EBIT (10-Q only)
    ebit_method VARCHAR(100),   -- 'Direct OperatingIncomeLoss', 'Tier 2', etc.
    ebit_tier INTEGER,          -- 1, 2, 3, 4 (waterfall tier used)

    -- Future: Revenue, COGS, etc. follow same pattern
    -- revenue BIGINT,
    -- revenue_ytd BIGINT,
    -- revenue_quarterly BIGINT,

    -- Metadata
    calculation_metadata JSONB,  -- Stores warnings, notes, sources
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(company_id, fiscal_year, fiscal_year_end, period_type)
);

CREATE INDEX idx_metrics_company ON financial_metrics(company_id);
CREATE INDEX idx_metrics_fiscal_year ON financial_metrics(fiscal_year);
CREATE INDEX idx_metrics_period_type ON financial_metrics(period_type);
CREATE INDEX idx_metrics_company_year ON financial_metrics(company_id, fiscal_year);
CREATE INDEX idx_metrics_company_period ON financial_metrics(company_id, fiscal_year_end);

COMMENT ON TABLE financial_metrics IS 'Time-series financial metrics from SEC filings';
COMMENT ON COLUMN financial_metrics.ebit IS 'Annual EBIT from 10-K (non-cumulative)';
COMMENT ON COLUMN financial_metrics.ebit_ytd IS 'Year-to-date cumulative EBIT from 10-Q';
COMMENT ON COLUMN financial_metrics.ebit_quarterly IS 'De-cumulated true quarterly EBIT (calculated)';
COMMENT ON COLUMN financial_metrics.unrestricted_cash IS 'Cash available for EV calculation (excludes restricted)';


-- ============================================================================
-- CALCULATED RATIOS TABLE - Derived metrics and ratios
-- ============================================================================
CREATE TABLE calculated_ratios (
    id SERIAL PRIMARY KEY,
    metric_id INTEGER REFERENCES financial_metrics(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    fiscal_year_end DATE NOT NULL,
    calculation_date DATE NOT NULL,
    period_type VARCHAR(10) NOT NULL,  -- '10-K' or '10-Q'

    -- ROCE (Return on Capital Employed)
    -- For 10-K: Uses ebit
    -- For 10-Q: Uses ebit_ytd
    roce DECIMAL(10, 4),
    capital_employed BIGINT,  -- Total Assets - Current Liabilities

    -- ROCE using quarterly EBIT (10-Q only)
    roce_quarterly DECIMAL(10, 4),  -- Uses ebit_quarterly instead of ebit_ytd

    -- Earnings Yield Components
    net_debt BIGINT,  -- Total Debt - Unrestricted Cash

    -- Requires market cap (from external source)
    market_cap BIGINT,              -- From market_data table
    enterprise_value BIGINT,        -- Market Cap + Net Debt
    earnings_yield DECIMAL(10, 4),  -- EBIT / Enterprise Value

    -- Metadata
    roce_components JSONB,  -- Detailed breakdown of ROCE calculation
    calculation_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(company_id, fiscal_year, fiscal_year_end, period_type)
);

CREATE INDEX idx_ratios_company ON calculated_ratios(company_id);
CREATE INDEX idx_ratios_fiscal_year ON calculated_ratios(fiscal_year);
CREATE INDEX idx_ratios_period_type ON calculated_ratios(period_type);
CREATE INDEX idx_ratios_company_year ON calculated_ratios(company_id, fiscal_year);
CREATE INDEX idx_ratios_roce ON calculated_ratios(roce) WHERE roce IS NOT NULL;
CREATE INDEX idx_ratios_earnings_yield ON calculated_ratios(earnings_yield) WHERE earnings_yield IS NOT NULL;

COMMENT ON TABLE calculated_ratios IS 'Calculated financial ratios (ROCE, Earnings Yield, etc.)';
COMMENT ON COLUMN calculated_ratios.roce IS 'Return on Capital Employed (uses YTD EBIT for quarterly)';
COMMENT ON COLUMN calculated_ratios.roce_quarterly IS 'ROCE using de-cumulated quarterly EBIT (10-Q only)';


-- ============================================================================
-- MARKET DATA TABLE - Stock prices and market capitalization
-- ============================================================================
CREATE TABLE market_data (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    price_date DATE NOT NULL,
    stock_price DECIMAL(10, 2),
    shares_outstanding BIGINT,
    market_cap BIGINT,
    source VARCHAR(50),  -- 'yahoo_finance', 'alpha_vantage', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, price_date, source)
);

CREATE INDEX idx_market_data_company ON market_data(company_id);
CREATE INDEX idx_market_data_date ON market_data(price_date);

COMMENT ON TABLE market_data IS 'Daily market capitalization data from external sources';


-- ============================================================================
-- SECTOR BENCHMARKS TABLE - Industry performance benchmarks
-- ============================================================================
CREATE TABLE sector_benchmarks (
    id SERIAL PRIMARY KEY,
    sector VARCHAR(100) NOT NULL,
    benchmark_date DATE NOT NULL,
    period_type VARCHAR(10) NOT NULL,  -- 'annual' or 'quarterly'

    -- ROCE benchmarks
    avg_roce DECIMAL(10, 4),
    median_roce DECIMAL(10, 4),
    roce_p25 DECIMAL(10, 4),  -- 25th percentile
    roce_p75 DECIMAL(10, 4),  -- 75th percentile
    roce_p90 DECIMAL(10, 4),  -- 90th percentile (top 10%)

    -- Earnings Yield benchmarks
    avg_earnings_yield DECIMAL(10, 4),
    median_earnings_yield DECIMAL(10, 4),
    ey_p25 DECIMAL(10, 4),
    ey_p75 DECIMAL(10, 4),

    -- Debt benchmarks
    avg_debt_to_capital DECIMAL(10, 4),
    median_debt_to_capital DECIMAL(10, 4),

    company_count INTEGER,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(sector, benchmark_date, period_type)
);

CREATE INDEX idx_benchmarks_sector ON sector_benchmarks(sector);
CREATE INDEX idx_benchmarks_date ON sector_benchmarks(benchmark_date);

COMMENT ON TABLE sector_benchmarks IS 'Sector-level performance benchmarks for comparison';


-- ============================================================================
-- PROCESSING LOG TABLE - Audit trail and error tracking
-- ============================================================================
CREATE TABLE processing_log (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    process_type VARCHAR(50) NOT NULL,  -- 'filing_parse', 'metric_calc', 'market_fetch'
    status VARCHAR(20) NOT NULL,        -- 'success', 'error', 'partial'
    error_message TEXT,
    records_processed INTEGER,
    processing_time_ms INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_log_company ON processing_log(company_id);
CREATE INDEX idx_log_status ON processing_log(status);
CREATE INDEX idx_log_created ON processing_log(created_at DESC);


-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Latest annual metrics for each company
CREATE VIEW latest_annual_metrics AS
SELECT
    c.ticker,
    c.company_name,
    c.sector,
    fm.fiscal_year,
    fm.fiscal_year_end,
    fm.ebit,
    fm.total_debt,
    fm.unrestricted_cash,
    fm.total_assets,
    fm.current_liabilities,
    cr.roce,
    cr.earnings_yield,
    cr.enterprise_value,
    cr.net_debt
FROM companies c
JOIN financial_metrics fm ON c.id = fm.company_id
LEFT JOIN calculated_ratios cr ON fm.id = cr.metric_id
WHERE fm.period_type = '10-K'
  AND fm.fiscal_year_end = (
    SELECT MAX(fiscal_year_end)
    FROM financial_metrics
    WHERE company_id = c.id AND period_type = '10-K'
  );

COMMENT ON VIEW latest_annual_metrics IS 'Most recent annual (10-K) metrics for each company';


-- Latest quarterly metrics for each company
CREATE VIEW latest_quarterly_metrics AS
SELECT
    c.ticker,
    c.company_name,
    c.sector,
    fm.fiscal_year,
    fm.fiscal_year_end,
    fm.ebit_ytd,
    fm.ebit_quarterly,
    fm.total_debt,
    fm.unrestricted_cash,
    fm.total_assets,
    fm.current_liabilities,
    cr.roce as roce_ytd,
    cr.roce_quarterly,
    cr.earnings_yield,
    cr.net_debt
FROM companies c
JOIN financial_metrics fm ON c.id = fm.company_id
LEFT JOIN calculated_ratios cr ON fm.id = cr.metric_id
WHERE fm.period_type = '10-Q'
  AND fm.fiscal_year_end = (
    SELECT MAX(fiscal_year_end)
    FROM financial_metrics
    WHERE company_id = c.id AND period_type = '10-Q'
  );

COMMENT ON VIEW latest_quarterly_metrics IS 'Most recent quarterly (10-Q) metrics for each company';


-- Company performance vs sector benchmarks
CREATE VIEW company_vs_sector AS
SELECT
    c.ticker,
    c.company_name,
    c.sector,
    cr.roce as company_roce,
    sb.median_roce as sector_median_roce,
    (cr.roce - sb.median_roce) as roce_vs_sector,
    cr.earnings_yield as company_ey,
    sb.median_earnings_yield as sector_median_ey,
    CASE
        WHEN cr.roce > sb.roce_p90 THEN 'Excellent (Top 10%)'
        WHEN cr.roce > sb.roce_p75 THEN 'Above Average (Top 25%)'
        WHEN cr.roce > sb.median_roce THEN 'Average'
        ELSE 'Below Average'
    END as performance_tier
FROM companies c
JOIN calculated_ratios cr ON c.id = cr.company_id
JOIN sector_benchmarks sb ON c.sector = sb.sector
    AND cr.period_type = sb.period_type
WHERE cr.period_type = '10-K'
  AND cr.fiscal_year_end = (
    SELECT MAX(fiscal_year_end)
    FROM calculated_ratios
    WHERE company_id = c.id AND period_type = '10-K'
  )
  AND sb.benchmark_date = (
    SELECT MAX(benchmark_date)
    FROM sector_benchmarks
    WHERE sector = c.sector AND period_type = 'annual'
  );

COMMENT ON VIEW company_vs_sector IS 'Compare company ROCE to sector benchmarks';


-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Calculate ROCE
CREATE OR REPLACE FUNCTION calculate_roce(
    p_ebit BIGINT,
    p_total_assets BIGINT,
    p_current_liabilities BIGINT
) RETURNS DECIMAL(10, 4) AS $$
DECLARE
    v_capital_employed BIGINT;
BEGIN
    IF p_ebit IS NULL OR p_total_assets IS NULL OR p_current_liabilities IS NULL THEN
        RETURN NULL;
    END IF;

    v_capital_employed := p_total_assets - p_current_liabilities;

    IF v_capital_employed <= 0 THEN
        RETURN NULL;
    END IF;

    RETURN (p_ebit::DECIMAL / v_capital_employed) * 100;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION calculate_roce IS 'Calculate ROCE = (EBIT / Capital Employed) × 100';


-- Calculate Earnings Yield
CREATE OR REPLACE FUNCTION calculate_earnings_yield(
    p_ebit BIGINT,
    p_enterprise_value BIGINT
) RETURNS DECIMAL(10, 4) AS $$
BEGIN
    IF p_ebit IS NULL OR p_enterprise_value IS NULL THEN
        RETURN NULL;
    END IF;

    IF p_enterprise_value <= 0 THEN
        RETURN NULL;
    END IF;

    RETURN (p_ebit::DECIMAL / p_enterprise_value) * 100;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION calculate_earnings_yield IS 'Calculate Earnings Yield = (EBIT / Enterprise Value) × 100';


-- Update sector benchmarks for a given date
CREATE OR REPLACE FUNCTION update_sector_benchmarks(
    p_sector VARCHAR,
    p_date DATE,
    p_period_type VARCHAR DEFAULT 'annual'
) RETURNS VOID AS $$
DECLARE
    v_period_filter VARCHAR;
BEGIN
    -- Determine period_type filter
    v_period_filter := CASE WHEN p_period_type = 'annual' THEN '10-K' ELSE '10-Q' END;

    INSERT INTO sector_benchmarks (
        sector,
        benchmark_date,
        period_type,
        avg_roce,
        median_roce,
        roce_p25,
        roce_p75,
        roce_p90,
        avg_earnings_yield,
        median_earnings_yield,
        ey_p25,
        ey_p75,
        company_count
    )
    SELECT
        p_sector,
        p_date,
        p_period_type,
        AVG(roce),
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY roce),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY roce),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY roce),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY roce),
        AVG(earnings_yield),
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY earnings_yield),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY earnings_yield),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY earnings_yield),
        COUNT(*)
    FROM calculated_ratios cr
    JOIN companies c ON cr.company_id = c.id
    WHERE c.sector = p_sector
        AND cr.period_type = v_period_filter
        AND cr.calculation_date = p_date
        AND cr.roce IS NOT NULL
    ON CONFLICT (sector, benchmark_date, period_type)
    DO UPDATE SET
        avg_roce = EXCLUDED.avg_roce,
        median_roce = EXCLUDED.median_roce,
        roce_p25 = EXCLUDED.roce_p25,
        roce_p75 = EXCLUDED.roce_p75,
        roce_p90 = EXCLUDED.roce_p90,
        avg_earnings_yield = EXCLUDED.avg_earnings_yield,
        median_earnings_yield = EXCLUDED.median_earnings_yield,
        ey_p25 = EXCLUDED.ey_p25,
        ey_p75 = EXCLUDED.ey_p75,
        company_count = EXCLUDED.company_count,
        calculated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_sector_benchmarks IS 'Calculate and update sector performance benchmarks';


-- ============================================================================
-- GRANTS (for application user)
-- ============================================================================
-- Run these after creating an application user:
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO edgar_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO edgar_app_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO edgar_app_user;
