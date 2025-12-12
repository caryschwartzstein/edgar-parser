# TODO List - EDGAR Parser Project

## High Priority

### 1. Build Unified Parse-and-Load Pipeline
**Status:** Not Started
**Priority:** High
**Context:** Current pipeline is inefficient - requires 3 steps (fetch → save JSON → parse JSON → load DB). Should streamline to 1 step (fetch → parse → load DB).

**What to Build:**
- New script: `scripts/parse_and_load.py`
- Fetch from SEC API → Parse with `parser_v2.py` → Load with `DatabaseLoader` → Done
- Optional `--save-json` flag for debugging/backup only
- **Run-based folder structure** - Each run gets its own timestamped folder

**CLI Interface:**
```bash
# Production mode (no JSON files saved, database only)
python scripts/parse_and_load.py --ticker AAPL
python scripts/parse_and_load.py --load-all

# Debug mode (save JSONs in run-specific folder)
python scripts/parse_and_load.py --ticker AAPL --save-json
python scripts/parse_and_load.py --load-all --save-json

# Custom run name
python scripts/parse_and_load.py --load-all --run-name "sp500_initial_load"
```

**Folder Structure:**
```
data/
├── runs/
│   ├── 2025-12-11_14-30-45/          # Timestamp-based run folder
│   │   ├── metadata.json              # Run config and timing
│   │   ├── raw/                       # Raw EDGAR JSON (if --save-json)
│   │   │   ├── AAPL_raw.json
│   │   │   └── ...
│   │   ├── parsed/                    # Parsed JSON (if --save-json)
│   │   │   ├── AAPL_parsed.json
│   │   │   └── ...
│   │   ├── errors/                    # Failed tickers with errors
│   │   │   └── BA_error.json
│   │   └── run_summary.json           # Stats (success/fail counts)
│   │
│   └── latest -> 2025-12-11_14-30-45/ # Symlink to most recent
│
└── parsed/                             # Legacy - keep existing
    └── with_quarterly_fixed/
```

**Benefits:**
- ✅ Much faster (no disk I/O for JSONs in production mode)
- ✅ Less disk space (only save JSONs when debugging)
- ✅ Simpler workflow (one command)
- ✅ Organized runs (isolated by timestamp)
- ✅ Easy comparison (compare results across runs)
- ✅ Audit trail (know when data was fetched)
- ✅ Error tracking (failed companies grouped by run)
- ✅ Rollback capability (reload database from specific run)

**Implementation Notes:**
- Reuse existing components:
  - EDGAR API fetching (with rate limiting: 10 req/sec)
  - `EDGARParser` from `parser_v2.py`
  - `DatabaseLoader` from `load_to_database.py`
- Create run directory structure:
  - Generate timestamp-based folder name (YYYY-MM-DD_HH-MM-SS)
  - Create subdirectories: raw/, parsed/, errors/
  - Save metadata.json with run config
  - Update 'latest' symlink on success
- Add transaction support (rollback on error)
- Add progress tracking for batch mode
- Save run_summary.json with stats:
  - Companies attempted/succeeded/failed
  - Duration
  - Database load status
- Respect SEC rate limits

**Files to Create:**
- `scripts/parse_and_load.py` - Main unified script

**Files to Keep (for debugging):**
- `scripts/parse_all_companies.py` - Keep for manual JSON generation
- `scripts/load_to_database.py` - Keep for loading existing JSONs

---

## Medium Priority

### 2. Parse Full S&P 500 Dataset
**Status:** Not Started
**Priority:** Medium
**Dependencies:** Requires unified parse_and_load.py script

**What to Do:**
- Use unified script to parse all ~374 companies
- Monitor for failures and data quality issues
- Expected time: ~37 minutes (374 companies × 6 seconds each)

---

### 3. Integrate Market Cap Data
**Status:** Not Started
**Priority:** Medium

**What to Do:**
- Fetch daily market cap from yfinance or Alpha Vantage
- Update `market_data` table
- Calculate complete earnings yield values
- Add to sector benchmarks

---

### 4. Calculate Sector Benchmarks
**Status:** Not Started
**Priority:** Medium

**What to Do:**
- Populate `sector_benchmarks` table
- Calculate median ROCE, earnings yield by sector
- Calculate percentile thresholds (25th, 75th, 90th)

---

## Low Priority

### 5. Build REST API
**Status:** Not Started
**Priority:** Low

**What to Do:**
- FastAPI implementation
- Endpoints: companies, metrics, ratios, screening
- Magic Formula screening endpoint

---

### 6. Build Web Dashboard
**Status:** Not Started
**Priority:** Low

**What to Do:**
- Frontend for Magic Formula screening
- Company comparison charts
- Sector analysis

---

## Completed

### ✅ Parser V2 with Modular Architecture
- EBIT Calculator with 4-tier waterfall
- Debt Calculator with 3-component structure
- Cash Calculator (unrestricted vs restricted)
- Balance Sheet Calculator
- Quarterly delta calculation (YTD de-cumulation)

### ✅ Database Schema Design
- PostgreSQL schema with quarterly support
- Dual EBIT columns (ytd, quarterly)
- Dual ROCE columns (ytd-based, quarterly-based)
- Views for latest metrics

### ✅ Database Loader
- Loads both annual and quarterly data
- Transaction support with rollback
- ON CONFLICT handling for idempotent loads
- JSONB metadata storage

### ✅ Test Dataset
- 10 companies parsed and loaded
- 841 total filings (173 annual + 668 quarterly)
- Data quality verified

---

**Last Updated:** 2025-12-11
