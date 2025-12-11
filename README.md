# EDGAR Financial Data Parser

> Parse S&P 500 companies from SEC EDGAR to calculate ROCE and Earnings Yield using the Greenblatt Magic Formula.

## Overview

This project parses ~374 S&P 500 companies (filtered to compatible sectors) to calculate:
- **ROCE (Return on Capital Employed)** - Measures business quality
- **Earnings Yield** - Measures valuation attractiveness
- **Industry Benchmarks** - Compare companies to sector averages (50-77 companies per sector)

**Data Sources:**
- SEC EDGAR API (free) for financial statements
- Wikipedia (free) for S&P 500 constituent list
- Yahoo Finance (free) for market capitalization

**Database:** PostgreSQL with historical time-series data

## Quick Start

### 1. Prerequisites
- Python 3.9+
- PostgreSQL 14+
- Git

### 2. Installation

```bash
# Clone repository (if using git)
cd /Users/caryschwartzstein/Projects/edgar-parser

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your database credentials and email
```

### 3. Database Setup

```bash
# Create PostgreSQL user (one-time setup, uses password from .env)
make db-user

# Create database
make db-create

# Load schema and grant permissions
make db-schema

# Or run all database setup at once
make db-setup-all

# Verify
psql edgar_financial_metrics -c "\dt"
```

### 4. Run Proof-of-Concept

```bash
# Step 1: Download S&P 500 company list (~374 companies)
python scripts/build_company_list.py
# Output: data/target_companies.csv

# Step 2: Test parser with Apple's embedded data
python src/edgar_parser/parser.py
# Should show: ROCE = 55.10%, Earnings Yield = 3.82%

# Step 3: Test database connection
python scripts/test_db_connection.py

# Step 4: Test EDGAR API access
python scripts/test_edgar_fetch.py
```

## Project Structure

```
edgar-parser/
├── src/edgar_parser/     # Main application code
├── scripts/              # Executable scripts
├── database/             # SQL schemas and migrations
├── docs/                 # Documentation
├── tests/                # Test suite
└── data/                 # Generated data (git-ignored)
```

See [docs/00_START_HERE_MASTER_FOUNDATION.md](docs/00_START_HERE_MASTER_FOUNDATION.md) for complete project documentation.

## Usage

### Download S&P 500 Company List
```bash
python scripts/build_company_list.py
```

### Test Parser with Embedded Data
```bash
python src/edgar_parser/parser.py
```

### Query Database
```sql
-- After populating the database
SELECT ticker, company_name, roce, earnings_yield
FROM latest_metrics
WHERE roce IS NOT NULL
ORDER BY roce DESC
LIMIT 10;
```

## Development

### Running Tests
```bash
pytest tests/
```

### Makefile Commands
```bash
make help         # Show available commands
make setup        # Install dependencies
make db-create    # Create database
make db-schema    # Load schema
make build-list   # Download S&P 500 list
make test-parse   # Test parser
```

## Documentation

- [Master Foundation Document](docs/00_START_HERE_MASTER_FOUNDATION.md) - Complete project vision and 4-week build plan
- Database Schema - See `database/schema.sql`

## Roadmap

- [x] Phase 1.1: Project setup and proof-of-concept
- [ ] Phase 1.2: Parse all 374 S&P 500 companies
- [ ] Phase 1.3: Calculate sector benchmarks
- [ ] Phase 2: Build REST API
- [ ] Phase 3: Automated daily updates
- [ ] Phase 4: Web dashboard

## Success Criteria (POC)

After setup, you should be able to:
- Download S&P 500 list (374 companies)
- Parse Apple embedded data (ROCE: 55.10%, EY: 3.82%)
- Connect to PostgreSQL database
- Fetch real data from SEC EDGAR API

## Common Issues

### PostgreSQL not installed
**macOS:** `brew install postgresql@14 && brew services start postgresql@14`

### SEC API returns 403
Update `EDGAR_USER_AGENT` in `.env` with your real name and email. SEC requires proper User-Agent.

### Parser can't find data directory
Create data directory: `mkdir -p data/parsed`

## Acknowledgments

- Joel Greenblatt's "The Little Book That Beats the Market" for the Magic Formula concept
- SEC EDGAR for free, comprehensive financial data

## License

MIT
