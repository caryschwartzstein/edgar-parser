#!/usr/bin/env python3
"""
Load parsed EDGAR data into PostgreSQL database.

This script loads parsed JSON files from data/parsed/with_quarterly_fixed/
into the PostgreSQL database using the schema defined in database/schema.sql.

Usage:
    python scripts/load_to_database.py --load-all
    python scripts/load_to_database.py --ticker AAPL
    python scripts/load_to_database.py --recalculate-ratios
"""

import json
import sys
import argparse
import psycopg2
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.edgar_parser.config import config


class DatabaseLoader:
    """Load parsed EDGAR data into PostgreSQL."""

    def __init__(self, db_url: str):
        """Initialize database connection."""
        self.conn = psycopg2.connect(db_url)
        self.conn.autocommit = False  # Use transactions
        self.cursor = self.conn.cursor()

    def close(self):
        """Close database connection."""
        self.cursor.close()
        self.conn.close()

    def get_or_create_company(self, metadata: Dict) -> int:
        """
        Get existing company ID or create new company record.

        Args:
            metadata: Parsed metadata dict with company_name, cik, etc.

        Returns:
            company_id
        """
        cik = str(metadata['cik']).zfill(10)  # Convert to 10-digit string
        company_name = metadata['company_name']

        # Try to get existing
        self.cursor.execute(
            "SELECT id FROM companies WHERE cik = %s",
            (cik,)
        )
        result = self.cursor.fetchone()

        if result:
            return result[0]

        # Create new company
        # Note: ticker will need to be updated separately (from target_companies.csv)
        ticker = "UNKNOWN"  # Will be updated later

        self.cursor.execute("""
            INSERT INTO companies (cik, ticker, company_name, created_at, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
        """, (cik, ticker, company_name))

        company_id = self.cursor.fetchone()[0]
        print(f"  Created company: {company_name} (CIK: {cik}) -> ID: {company_id}")

        return company_id

    def load_annual_period(self, period: Dict, company_id: int) -> None:
        """
        Load an annual (10-K) period into the database.

        Args:
            period: Annual period dict from parsed JSON
            company_id: Company ID
        """
        # Extract period metadata
        fiscal_year = int(period['fiscal_year'])
        fiscal_year_end = period['fiscal_year_end']
        filing_date = period['filing_date']
        form_type = period['form']  # '10-K'

        # 1. Insert filing record
        filing_id = self._insert_filing(
            company_id=company_id,
            filing_date=filing_date,
            filing_type=form_type,
            fiscal_year=fiscal_year,
            fiscal_year_end=fiscal_year_end,
            fiscal_quarter=None
        )

        # 2. Insert financial metrics
        metric_id = self._insert_annual_metrics(
            filing_id=filing_id,
            company_id=company_id,
            fiscal_year=fiscal_year,
            fiscal_year_end=fiscal_year_end,
            period=period
        )

        # 3. Insert calculated ratios
        self._insert_calculated_ratios(
            metric_id=metric_id,
            company_id=company_id,
            fiscal_year=fiscal_year,
            fiscal_year_end=fiscal_year_end,
            period_type='10-K',
            period=period
        )

    def load_quarterly_period(self, period: Dict, company_id: int) -> None:
        """
        Load a quarterly (10-Q) period into the database.

        Args:
            period: Quarterly period dict from parsed JSON
            company_id: Company ID
        """
        # Extract period metadata
        fiscal_year = int(period['fiscal_year'])
        fiscal_year_end = period['fiscal_year_end']
        filing_date = period['filing_date']
        form_type = period['form']  # '10-Q'

        # Infer fiscal quarter from date (1-4)
        # This is a simple heuristic - could be improved
        fiscal_quarter = self._infer_fiscal_quarter(fiscal_year_end, fiscal_year)

        # 1. Insert filing record
        filing_id = self._insert_filing(
            company_id=company_id,
            filing_date=filing_date,
            filing_type=form_type,
            fiscal_year=fiscal_year,
            fiscal_year_end=fiscal_year_end,
            fiscal_quarter=fiscal_quarter
        )

        # 2. Insert financial metrics
        metric_id = self._insert_quarterly_metrics(
            filing_id=filing_id,
            company_id=company_id,
            fiscal_year=fiscal_year,
            fiscal_year_end=fiscal_year_end,
            period=period
        )

        # 3. Insert calculated ratios
        self._insert_calculated_ratios(
            metric_id=metric_id,
            company_id=company_id,
            fiscal_year=fiscal_year,
            fiscal_year_end=fiscal_year_end,
            period_type='10-Q',
            period=period
        )

    def _insert_filing(
        self,
        company_id: int,
        filing_date: str,
        filing_type: str,
        fiscal_year: int,
        fiscal_year_end: str,
        fiscal_quarter: Optional[int]
    ) -> int:
        """Insert filing record, return filing_id."""
        try:
            self.cursor.execute("""
                INSERT INTO filings (
                    company_id, filing_date, filing_type, fiscal_year,
                    fiscal_year_end, fiscal_quarter, parser_version, processed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (company_id, fiscal_year, fiscal_year_end, filing_type)
                DO UPDATE SET
                    filing_date = EXCLUDED.filing_date,
                    fiscal_quarter = EXCLUDED.fiscal_quarter,
                    parser_version = EXCLUDED.parser_version,
                    processed_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                company_id, filing_date, filing_type, fiscal_year,
                fiscal_year_end, fiscal_quarter, '2.0'
            ))

            return self.cursor.fetchone()[0]

        except psycopg2.IntegrityError as e:
            self.conn.rollback()
            raise Exception(f"Error inserting filing: {e}")

    def _insert_annual_metrics(
        self,
        filing_id: int,
        company_id: int,
        fiscal_year: int,
        fiscal_year_end: str,
        period: Dict
    ) -> int:
        """Insert annual (10-K) financial metrics."""
        metrics = period.get('metrics', {})

        # Extract EBIT
        ebit_data = metrics.get('ebit', {})
        ebit = ebit_data.get('value')
        ebit_method = ebit_data.get('method')
        ebit_tier = ebit_data.get('tier')

        # Extract balance sheet
        total_debt = metrics.get('total_debt', {}).get('value')
        unrestricted_cash = metrics.get('cash', {}).get('unrestricted_cash')
        total_cash = metrics.get('cash', {}).get('total_cash')
        total_assets = metrics.get('assets', {}).get('value')
        current_liabilities = metrics.get('current_liabilities', {}).get('value')

        # Build metadata JSON
        calculation_metadata = {
            'parser_version': '2.0',
            'period_type': '10-K',
            'ebit_validation': ebit_data.get('validation'),
            'ebit_sources': ebit_data.get('sources'),
            'debt_warnings': metrics.get('total_debt', {}).get('warnings', []),
            'cash_method': metrics.get('cash', {}).get('method')
        }

        self.cursor.execute("""
            INSERT INTO financial_metrics (
                filing_id, company_id, fiscal_year, fiscal_year_end,
                metric_date, period_type,
                total_assets, current_liabilities,
                total_debt, unrestricted_cash, total_cash,
                ebit, ebit_ytd, ebit_quarterly, ebit_method, ebit_tier,
                calculation_metadata, created_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (company_id, fiscal_year, fiscal_year_end, period_type)
            DO UPDATE SET
                total_assets = EXCLUDED.total_assets,
                current_liabilities = EXCLUDED.current_liabilities,
                total_debt = EXCLUDED.total_debt,
                unrestricted_cash = EXCLUDED.unrestricted_cash,
                total_cash = EXCLUDED.total_cash,
                ebit = EXCLUDED.ebit,
                ebit_method = EXCLUDED.ebit_method,
                ebit_tier = EXCLUDED.ebit_tier,
                calculation_metadata = EXCLUDED.calculation_metadata
            RETURNING id
        """, (
            filing_id, company_id, fiscal_year, fiscal_year_end,
            fiscal_year_end,  # metric_date = fiscal_year_end
            '10-K',
            total_assets, current_liabilities,
            total_debt, unrestricted_cash, total_cash,
            ebit, None, None, ebit_method, ebit_tier,  # ebit_ytd and ebit_quarterly are NULL for 10-K
            json.dumps(calculation_metadata)
        ))

        return self.cursor.fetchone()[0]

    def _insert_quarterly_metrics(
        self,
        filing_id: int,
        company_id: int,
        fiscal_year: int,
        fiscal_year_end: str,
        period: Dict
    ) -> int:
        """Insert quarterly (10-Q) financial metrics."""
        metrics = period.get('metrics', {})

        # Extract EBIT (with YTD and quarterly values)
        ebit_data = metrics.get('ebit', {})
        ebit_ytd = ebit_data.get('ytd_value')
        ebit_quarterly = ebit_data.get('quarterly_value')
        ebit_method = ebit_data.get('method')
        ebit_tier = ebit_data.get('tier')

        # Extract balance sheet (point-in-time)
        total_debt = metrics.get('total_debt', {}).get('value')
        unrestricted_cash = metrics.get('cash', {}).get('unrestricted_cash')
        total_cash = metrics.get('cash', {}).get('total_cash')
        total_assets = metrics.get('assets', {}).get('value')
        current_liabilities = metrics.get('current_liabilities', {}).get('value')

        # Build metadata JSON
        calculation_metadata = {
            'parser_version': '2.0',
            'period_type': '10-Q',
            'ebit_calculation_note': ebit_data.get('calculation_note'),
            'ebit_is_calculated': ebit_data.get('is_calculated', False),
            'ebit_previous_quarter_ytd': ebit_data.get('previous_quarter_ytd'),
            'debt_warnings': metrics.get('total_debt', {}).get('warnings', []),
            'cash_method': metrics.get('cash', {}).get('method')
        }

        self.cursor.execute("""
            INSERT INTO financial_metrics (
                filing_id, company_id, fiscal_year, fiscal_year_end,
                metric_date, period_type,
                total_assets, current_liabilities,
                total_debt, unrestricted_cash, total_cash,
                ebit, ebit_ytd, ebit_quarterly, ebit_method, ebit_tier,
                calculation_metadata, created_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (company_id, fiscal_year, fiscal_year_end, period_type)
            DO UPDATE SET
                total_assets = EXCLUDED.total_assets,
                current_liabilities = EXCLUDED.current_liabilities,
                total_debt = EXCLUDED.total_debt,
                unrestricted_cash = EXCLUDED.unrestricted_cash,
                total_cash = EXCLUDED.total_cash,
                ebit_ytd = EXCLUDED.ebit_ytd,
                ebit_quarterly = EXCLUDED.ebit_quarterly,
                ebit_method = EXCLUDED.ebit_method,
                ebit_tier = EXCLUDED.ebit_tier,
                calculation_metadata = EXCLUDED.calculation_metadata
            RETURNING id
        """, (
            filing_id, company_id, fiscal_year, fiscal_year_end,
            fiscal_year_end,  # metric_date = fiscal_year_end
            '10-Q',
            total_assets, current_liabilities,
            total_debt, unrestricted_cash, total_cash,
            None, ebit_ytd, ebit_quarterly, ebit_method, ebit_tier,  # ebit is NULL for 10-Q
            json.dumps(calculation_metadata)
        ))

        return self.cursor.fetchone()[0]

    def _insert_calculated_ratios(
        self,
        metric_id: int,
        company_id: int,
        fiscal_year: int,
        fiscal_year_end: str,
        period_type: str,
        period: Dict
    ) -> None:
        """Insert calculated ratios (ROCE, earnings yield components)."""
        ratios = period.get('calculated_ratios', {})

        # Extract ROCE
        roce_data = ratios.get('roce', {})
        roce = roce_data.get('value')
        capital_employed = roce_data.get('components', {}).get('capital_employed')

        # Build ROCE components JSON
        roce_components = {
            'ebit': roce_data.get('components', {}).get('ebit'),
            'total_assets': roce_data.get('components', {}).get('total_assets'),
            'current_liabilities': roce_data.get('components', {}).get('current_liabilities'),
            'capital_employed': capital_employed,
            'formula': roce_data.get('formula'),
            'interpretation': roce_data.get('interpretation')
        }

        # Calculate quarterly ROCE if this is 10-Q and we have quarterly EBIT
        roce_quarterly = None
        if period_type == '10-Q':
            metrics = period.get('metrics', {})
            ebit_data = metrics.get('ebit', {})
            ebit_quarterly_val = ebit_data.get('quarterly_value')

            if ebit_quarterly_val and capital_employed and capital_employed > 0:
                roce_quarterly = (ebit_quarterly_val / capital_employed) * 100

        # Extract earnings yield components
        ey_data = ratios.get('earnings_yield_components', {})
        net_debt = ey_data.get('net_debt')

        # Build metadata JSON
        calculation_metadata = {
            'roce_status': roce_data.get('status'),
            'ey_status': ey_data.get('status'),
            'ey_formula': ey_data.get('formula'),
            'ey_note': ey_data.get('note')
        }

        self.cursor.execute("""
            INSERT INTO calculated_ratios (
                metric_id, company_id, fiscal_year, fiscal_year_end,
                calculation_date, period_type,
                roce, capital_employed, roce_quarterly,
                net_debt, market_cap, enterprise_value, earnings_yield,
                roce_components, calculation_metadata, created_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (company_id, fiscal_year, fiscal_year_end, period_type)
            DO UPDATE SET
                roce = EXCLUDED.roce,
                capital_employed = EXCLUDED.capital_employed,
                roce_quarterly = EXCLUDED.roce_quarterly,
                net_debt = EXCLUDED.net_debt,
                roce_components = EXCLUDED.roce_components,
                calculation_metadata = EXCLUDED.calculation_metadata
            RETURNING id
        """, (
            metric_id, company_id, fiscal_year, fiscal_year_end,
            fiscal_year_end,  # calculation_date = fiscal_year_end
            period_type,
            roce, capital_employed, roce_quarterly,
            net_debt, None, None, None,  # market_cap, EV, earnings_yield come later
            json.dumps(roce_components) if roce_components else None,
            json.dumps(calculation_metadata)
        ))

    def _infer_fiscal_quarter(self, fiscal_year_end: str, fiscal_year: int) -> Optional[int]:
        """
        Infer fiscal quarter (1-4) from fiscal_year_end date.

        This is a simple heuristic based on month.
        Note: This may not be perfectly accurate for all companies.
        """
        try:
            month = int(fiscal_year_end.split('-')[1])

            # Assume quarters end in Mar, Jun, Sep, Dec
            # Map to Q1, Q2, Q3, Q4
            if month in [1, 2, 3]:
                return 1
            elif month in [4, 5, 6]:
                return 2
            elif month in [7, 8, 9]:
                return 3
            elif month in [10, 11, 12]:
                return 4
            else:
                return None
        except:
            return None

    def load_parsed_file(self, filepath: Path) -> None:
        """
        Load a complete parsed JSON file into the database.

        Args:
            filepath: Path to parsed JSON file
        """
        print(f"\nLoading: {filepath.name}")
        print("="*80)

        with open(filepath) as f:
            data = json.load(f)

        # Get or create company
        company_id = self.get_or_create_company(data['metadata'])

        # Load annual periods
        annual_count = 0
        for period in data.get('annual_periods', []):
            self.load_annual_period(period, company_id)
            annual_count += 1

        print(f"  Loaded {annual_count} annual periods")

        # Load quarterly periods
        quarterly_count = 0
        for period in data.get('quarterly_periods', []):
            self.load_quarterly_period(period, company_id)
            quarterly_count += 1

        print(f"  Loaded {quarterly_count} quarterly periods")

        # Commit transaction
        self.conn.commit()
        print(f"  ✓ Committed to database")

        # Log to processing_log
        self._log_processing(
            company_id=company_id,
            process_type='filing_parse',
            status='success',
            records_processed=annual_count + quarterly_count
        )

    def _log_processing(
        self,
        company_id: int,
        process_type: str,
        status: str,
        records_processed: int = 0,
        error_message: str = None
    ) -> None:
        """Log processing activity."""
        self.cursor.execute("""
            INSERT INTO processing_log (
                company_id, process_type, status, error_message,
                records_processed, created_at
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (company_id, process_type, status, error_message, records_processed))
        self.conn.commit()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Load parsed EDGAR data into PostgreSQL')
    parser.add_argument('--load-all', action='store_true',
                      help='Load all parsed files from data/parsed/with_quarterly_fixed/')
    parser.add_argument('--ticker', type=str,
                      help='Load specific ticker (e.g., AAPL)')
    parser.add_argument('--file', type=str,
                      help='Load specific file path')

    args = parser.parse_args()

    # Get database URL from config
    DATABASE_URL = config.DATABASE_URL

    # Check DATABASE_URL is set
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set in .env file")
        print("Please set database credentials in .env file")
        sys.exit(1)

    print("="*80)
    print("EDGAR DATA LOADER")
    print("="*80)
    print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print()

    # Initialize loader
    loader = DatabaseLoader(DATABASE_URL)

    try:
        if args.load_all:
            # Load all files in parsed directory
            parsed_dir = Path('data/parsed/with_quarterly_fixed')
            files = sorted(parsed_dir.glob('*_parsed_with_quarterly.json'))

            if not files:
                print(f"No files found in {parsed_dir}")
                sys.exit(1)

            print(f"Found {len(files)} files to load")
            print()

            for filepath in files:
                try:
                    loader.load_parsed_file(filepath)
                except Exception as e:
                    print(f"  ✗ Error loading {filepath.name}: {e}")
                    loader.conn.rollback()
                    continue

        elif args.ticker:
            # Load specific ticker
            parsed_dir = Path('data/parsed/with_quarterly_fixed')
            filepath = parsed_dir / f"{args.ticker}_parsed_with_quarterly.json"

            if not filepath.exists():
                print(f"File not found: {filepath}")
                sys.exit(1)

            loader.load_parsed_file(filepath)

        elif args.file:
            # Load specific file
            filepath = Path(args.file)

            if not filepath.exists():
                print(f"File not found: {filepath}")
                sys.exit(1)

            loader.load_parsed_file(filepath)

        else:
            parser.print_help()
            sys.exit(1)

        print()
        print("="*80)
        print("LOAD COMPLETE")
        print("="*80)

    finally:
        loader.close()


if __name__ == '__main__':
    main()
