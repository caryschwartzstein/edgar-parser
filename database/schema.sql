
-- ============================================================================
-- COMPANIES TABLE
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


-- ============================================================================
-- FILINGS TABLE - Track which filings we've processed
-- ============================================================================
CREATE TABLE filings (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    filing_date DATE NOT NULL,
    filing_type VARCHAR(10) NOT NULL,  -- 10-K, 10-Q, etc.
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,  -- NULL for annual, 1-4 for quarterly
    accession_number VARCHAR(20) UNIQUE,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_quality_score FLOAT,  -- Track confidence in parsed data
    UNIQUE(company_id, filing_date, filing_type)
);

CREATE INDEX idx_filings_company ON filings(company_id);
CREATE INDEX idx_filings_date ON filings(filing_date);
CREATE INDEX idx_filings_type ON filings(filing_type);


-- ============================================================================
-- FINANCIAL METRICS TABLE - Time series data
-- ============================================================================
CREATE TABLE financial_metrics (
    id SERIAL PRIMARY KEY,
    filing_id INTEGER REFERENCES filings(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,  -- The "as of" date for the metric
    
    -- Balance Sheet Items
    total_assets BIGINT,
    current_assets BIGINT,
    total_liabilities BIGINT,
    current_liabilities BIGINT,
    stockholders_equity BIGINT,
    
    -- Debt Items (for Enterprise Value calculation)
    short_term_debt BIGINT,
    long_term_debt BIGINT,
    total_debt BIGINT,
    
    -- Cash Items (for Enterprise Value calculation)
    cash_and_equivalents BIGINT,
    cash_and_short_term_investments BIGINT,
    
    -- Income Statement Items
    revenue BIGINT,
    cost_of_revenue BIGINT,
    gross_profit BIGINT,
    operating_income BIGINT,
    net_income BIGINT,
    ebitda BIGINT,
    
    -- Cash Flow Items
    operating_cash_flow BIGINT,
    investing_cash_flow BIGINT,
    financing_cash_flow BIGINT,
    free_cash_flow BIGINT,
    
    -- Per Share Metrics
    earnings_per_share DECIMAL(10, 2),
    book_value_per_share DECIMAL(10, 2),
    shares_outstanding BIGINT,
    
    -- Metadata
    xbrl_tag_source JSONB,  -- Store which XBRL tags were used
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(company_id, metric_date, filing_id)
);

CREATE INDEX idx_metrics_company ON financial_metrics(company_id);
CREATE INDEX idx_metrics_date ON financial_metrics(metric_date);
CREATE INDEX idx_metrics_company_date ON financial_metrics(company_id, metric_date);


-- ============================================================================
-- CALCULATED RATIOS TABLE - Derived metrics
-- ============================================================================
CREATE TABLE calculated_ratios (
    id SERIAL PRIMARY KEY,
    metric_id INTEGER REFERENCES financial_metrics(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    calculation_date DATE NOT NULL,
    
    -- Profitability Ratios
    roce DECIMAL(10, 4),  -- Return on Capital Employed
    roe DECIMAL(10, 4),   -- Return on Equity
    roa DECIMAL(10, 4),   -- Return on Assets
    gross_margin DECIMAL(10, 4),
    operating_margin DECIMAL(10, 4),
    net_margin DECIMAL(10, 4),
    
    -- Valuation Ratios (requires market data)
    enterprise_value BIGINT,
    earnings_yield DECIMAL(10, 4),
    pe_ratio DECIMAL(10, 4),
    price_to_book DECIMAL(10, 4),
    ev_to_ebit DECIMAL(10, 4),
    net_debt BIGINT,  -- Total Debt - Cash
    
    -- Liquidity Ratios
    current_ratio DECIMAL(10, 4),
    quick_ratio DECIMAL(10, 4),
    
    -- Leverage Ratios
    debt_to_equity DECIMAL(10, 4),
    debt_to_assets DECIMAL(10, 4),
    debt_to_capital DECIMAL(10, 4),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(company_id, calculation_date)
);

CREATE INDEX idx_ratios_company ON calculated_ratios(company_id);
CREATE INDEX idx_ratios_date ON calculated_ratios(calculation_date);


-- ============================================================================
-- MARKET DATA TABLE - Stock prices and market cap
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
    UNIQUE(company_id, price_date)
);

CREATE INDEX idx_market_data_company ON market_data(company_id);
CREATE INDEX idx_market_data_date ON market_data(price_date);


-- ============================================================================
-- SECTOR BENCHMARKS TABLE - Industry averages
-- ============================================================================
CREATE TABLE sector_benchmarks (
    id SERIAL PRIMARY KEY,
    sector VARCHAR(100) NOT NULL,
    benchmark_date DATE NOT NULL,
    
    -- Average ratios for the sector
    avg_roce DECIMAL(10, 4),
    median_roce DECIMAL(10, 4),
    avg_roe DECIMAL(10, 4),
    median_roe DECIMAL(10, 4),
    avg_operating_margin DECIMAL(10, 4),
    median_operating_margin DECIMAL(10, 4),
    
    -- Percentile thresholds
    roce_p25 DECIMAL(10, 4),
    roce_p75 DECIMAL(10, 4),
    roce_p90 DECIMAL(10, 4),
    
    -- Earnings Yield benchmarks
    avg_earnings_yield DECIMAL(10, 4),
    median_earnings_yield DECIMAL(10, 4),
    ey_p25 DECIMAL(10, 4),
    ey_p75 DECIMAL(10, 4),
    
    -- Debt/Leverage benchmarks
    avg_debt_to_capital DECIMAL(10, 4),
    median_debt_to_capital DECIMAL(10, 4),
    
    company_count INTEGER,  -- How many companies in this calculation
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(sector, benchmark_date)
);

CREATE INDEX idx_benchmarks_sector ON sector_benchmarks(sector);
CREATE INDEX idx_benchmarks_date ON sector_benchmarks(benchmark_date);


-- ============================================================================
-- PROCESSING LOG TABLE - Track updates and errors
-- ============================================================================
CREATE TABLE processing_log (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    process_type VARCHAR(50) NOT NULL,  -- 'filing_fetch', 'metric_calc', etc.
    status VARCHAR(20) NOT NULL,  -- 'success', 'error', 'partial'
    error_message TEXT,
    records_processed INTEGER,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_log_company ON processing_log(company_id);
CREATE INDEX idx_log_status ON processing_log(status);
CREATE INDEX idx_log_created ON processing_log(created_at);


-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Latest metrics for each company
CREATE VIEW latest_metrics AS
SELECT 
    c.ticker,
    c.company_name,
    c.sector,
    fm.*,
    cr.roce,
    cr.earnings_yield,
    cr.current_ratio
FROM companies c
JOIN financial_metrics fm ON c.id = fm.company_id
LEFT JOIN calculated_ratios cr ON fm.id = cr.metric_id
WHERE fm.metric_date = (
    SELECT MAX(metric_date) 
    FROM financial_metrics 
    WHERE company_id = c.id
);


-- Company performance vs sector
CREATE VIEW company_vs_sector AS
SELECT 
    c.ticker,
    c.company_name,
    c.sector,
    cr.roce as company_roce,
    sb.median_roce as sector_median_roce,
    (cr.roce - sb.median_roce) as roce_vs_sector,
    CASE 
        WHEN cr.roce > sb.roce_p90 THEN 'Excellent'
        WHEN cr.roce > sb.roce_p75 THEN 'Above Average'
        WHEN cr.roce > sb.median_roce THEN 'Average'
        ELSE 'Below Average'
    END as performance_tier
FROM companies c
JOIN calculated_ratios cr ON c.id = cr.company_id
JOIN sector_benchmarks sb ON c.sector = sb.sector
    AND cr.calculation_date = sb.benchmark_date
WHERE cr.calculation_date = (
    SELECT MAX(calculation_date) 
    FROM calculated_ratios 
    WHERE company_id = c.id
);


-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to calculate ROCE
CREATE OR REPLACE FUNCTION calculate_roce(
    p_operating_income BIGINT,
    p_total_assets BIGINT,
    p_current_liabilities BIGINT
) RETURNS DECIMAL(10, 4) AS $$
BEGIN
    IF p_total_assets IS NULL OR p_current_liabilities IS NULL OR p_operating_income IS NULL THEN
        RETURN NULL;
    END IF;
    
    IF (p_total_assets - p_current_liabilities) <= 0 THEN
        RETURN NULL;
    END IF;
    
    RETURN (p_operating_income::DECIMAL / (p_total_assets - p_current_liabilities)) * 100;
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- Function to update sector benchmarks
CREATE OR REPLACE FUNCTION update_sector_benchmarks(p_sector VARCHAR, p_date DATE)
RETURNS VOID AS $$
BEGIN
    INSERT INTO sector_benchmarks (
        sector, 
        benchmark_date,
        avg_roce,
        median_roce,
        roce_p25,
        roce_p75,
        roce_p90,
        company_count
    )
    SELECT 
        p_sector,
        p_date,
        AVG(roce),
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY roce),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY roce),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY roce),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY roce),
        COUNT(*)
    FROM calculated_ratios cr
    JOIN companies c ON cr.company_id = c.id
    WHERE c.sector = p_sector
        AND cr.calculation_date = p_date
        AND cr.roce IS NOT NULL
    ON CONFLICT (sector, benchmark_date) 
    DO UPDATE SET
        avg_roce = EXCLUDED.avg_roce,
        median_roce = EXCLUDED.median_roce,
        roce_p25 = EXCLUDED.roce_p25,
        roce_p75 = EXCLUDED.roce_p75,
        roce_p90 = EXCLUDED.roce_p90,
        company_count = EXCLUDED.company_count,
        calculated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;
