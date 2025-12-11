#!/usr/bin/env python3
"""
Parse Test Companies Script
Fetches and parses 10 diverse S&P 500 companies from EDGAR
Saves results to JSON files with detailed calculation logging
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import requests
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.edgar_parser.parser_v2 import EnhancedEDGARParserV2
from src.edgar_parser.config import config


class TestCompanyParser:
    """Parse test companies with detailed logging using V2 parser"""

    # 10 diverse companies for testing (2 from most sectors)
    TEST_COMPANIES = [
        'AAPL',   # Tech
        'MSFT',   # Tech
        'WMT',    # Consumer Staples
        'PG',     # Consumer Staples
        'HD',     # Consumer Discretionary
        'MCD',    # Consumer Discretionary
        'CAT',    # Industrials
        'BA',     # Industrials
        'XOM',    # Energy
        'CVX',    # Energy
    ]

    def __init__(self):
        self.parser = EnhancedEDGARParserV2()
        self.data_dir = Path('data')
        self.parsed_dir = self.data_dir / 'parsed'
        self.raw_dir = self.data_dir / 'raw_edgar'  # Store raw EDGAR responses
        self.parsed_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        # Validate configuration (only EDGAR_USER_AGENT required for parsing)
        if not config.EDGAR_USER_AGENT:
            print("\n❌ Configuration Error: EDGAR_USER_AGENT not set in .env file")
            print("\nThe SEC requires a proper User-Agent header.")
            print("Please set EDGAR_USER_AGENT in your .env file to:")
            print("  Your Name email@example.com")
            print("\nExample: EDGAR_USER_AGENT=John Doe john.doe@example.com")
            sys.exit(1)

    def load_company_list(self) -> pd.DataFrame:
        """Load company list from CSV"""
        csv_path = self.data_dir / 'target_companies.csv'

        if not csv_path.exists():
            print(f"\n❌ Error: {csv_path} not found")
            print("Run 'make build-list' first to download company list")
            sys.exit(1)

        return pd.read_csv(csv_path)

    def fetch_edgar_data(self, cik: str, ticker: str) -> Optional[Dict]:
        """Fetch company facts from EDGAR API"""
        # Ensure CIK is zero-padded to 10 digits
        cik_padded = str(cik).zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"

        headers = {
            'User-Agent': config.EDGAR_USER_AGENT,
            'Accept-Encoding': 'gzip, deflate',
        }

        try:
            print(f"      Fetching from EDGAR API...")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            print(f"      ✓ Fetched data from EDGAR")
            return data

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"      ✗ CIK {cik} not found in EDGAR")
            elif e.response.status_code == 403:
                print(f"      ✗ 403 Forbidden - Check EDGAR_USER_AGENT in .env")
            else:
                print(f"      ✗ HTTP Error {e.response.status_code}: {e}")
            return None
        except Exception as e:
            print(f"      ✗ Error fetching data: {e}")
            return None

    def parse_company(self, ticker: str, company_info: pd.Series) -> Tuple[bool, Optional[Dict]]:
        """Parse a single company and save to JSON"""
        print(f"\n{'─'*70}")
        print(f"  Ticker: {ticker}")
        print(f"  Name:   {company_info['company_name']}")
        print(f"  Sector: {company_info['sector']}")
        print(f"  CIK:    {company_info['cik']}")
        print(f"{'─'*70}")

        # Fetch from EDGAR
        edgar_data = self.fetch_edgar_data(company_info['cik'], ticker)
        if not edgar_data:
            return False, None

        # Save raw EDGAR response for inspection/verification
        raw_file = self.raw_dir / f"{ticker}_edgar_raw.json"
        with open(raw_file, 'w') as f:
            json.dump(edgar_data, f, indent=2)
        print(f"      ✓ Saved raw EDGAR data to {raw_file}")

        # Parse the data with V2 parser (suppressed output)
        print(f"      Parsing financial metrics...")
        parsed_data = self.parser.parse_company_data(edgar_data, verbose=False)

        # Get most recent period
        if not parsed_data.get('annual_periods'):
            print(f"      ✗ No annual periods found")
            return False, None

        most_recent = parsed_data['annual_periods'][0]
        metrics_count = most_recent['metrics_count']
        roce = most_recent['calculated_ratios'].get('roce')

        # Check date consistency
        dates = set(m['date'] for m in most_recent['metrics'].values())
        date_consistent = len(dates) == 1

        print(f"      ✓ Extracted {metrics_count} financial metrics")
        print(f"      ✓ Found {parsed_data['metadata']['total_periods']} historical periods")

        if date_consistent:
            print(f"      ✓ Date consistency: PASS (all from {list(dates)[0]})")
        else:
            print(f"      ⚠ Date consistency: WARNING ({len(dates)} different dates)")

        # Show ROCE result
        if roce:
            print(f"      ✓ ROCE calculated: {roce:.2f}%")
        else:
            print(f"      ✗ ROCE calculation failed (missing data)")

        # Add metadata to output
        parsed_data['metadata']['ticker'] = ticker
        parsed_data['metadata']['company_name'] = company_info['company_name']
        parsed_data['metadata']['sector'] = company_info['sector']

        # Save to JSON (with ALL historical periods)
        output_file = self.parsed_dir / f"{ticker}_parsed.json"
        with open(output_file, 'w') as f:
            json.dump(parsed_data, f, indent=2)

        print(f"      ✓ Saved to {output_file}")

        # Return success and summary data
        return True, {
            'ticker': ticker,
            'name': company_info['company_name'],
            'sector': company_info['sector'],
            'roce': roce,
            'metrics_extracted': metrics_count,
            'periods_extracted': parsed_data['metadata']['total_periods'],
            'date_consistent': date_consistent
        }

    def run(self):
        """Run the test parse on 10 companies"""
        print("\n" + "="*70)
        print("PARSE TEST COMPANIES - EDGAR FETCHING & JSON STORAGE")
        print("="*70)
        print("\nThis script will:")
        print("  1. Fetch real data from SEC EDGAR API")
        print("  2. Parse financial metrics using XBRL tags")
        print("  3. Calculate ROCE with detailed logging")
        print("  4. Save results to data/parsed/{TICKER}_parsed.json")
        print("\nTesting with 10 diverse companies across sectors...")

        # Load company list
        print(f"\n[Step 1] Loading company list...")
        companies_df = self.load_company_list()
        print(f"✓ Loaded {len(companies_df)} companies from data/target_companies.csv")

        # Filter to test companies
        test_companies = companies_df[companies_df['ticker'].isin(self.TEST_COMPANIES)]

        if len(test_companies) < len(self.TEST_COMPANIES):
            missing = set(self.TEST_COMPANIES) - set(test_companies['ticker'])
            print(f"\n⚠ Warning: {len(missing)} test companies not found in CSV: {missing}")

        print(f"\n[Step 2] Parsing {len(test_companies)} test companies...")
        print(f"Output directory: {self.parsed_dir}")

        # Parse each company
        results = []
        success_count = 0
        failed = []

        for idx, (_, company) in enumerate(test_companies.iterrows(), 1):
            ticker = company['ticker']
            print(f"\n[{idx}/{len(test_companies)}] {ticker} ({company['company_name']})")

            try:
                success, data = self.parse_company(ticker, company)

                if success:
                    success_count += 1
                    results.append(data)  # data already has the right structure from V2
                else:
                    failed.append(ticker)
                    results.append({
                        'ticker': ticker,
                        'name': company['company_name'],
                        'sector': company['sector'],
                        'roce': None,
                        'metrics_extracted': 0,
                        'periods_extracted': 0,
                        'status': 'failed'
                    })

                # Rate limiting: SEC allows 10 requests per second
                time.sleep(0.12)  # ~8 requests/second to be safe

            except Exception as e:
                print(f"      ✗ Unexpected error: {e}")
                failed.append(ticker)
                results.append({
                    'ticker': ticker,
                    'name': company['company_name'],
                    'sector': company['sector'],
                    'roce': None,
                    'metrics_extracted': 0,
                    'status': f'error: {str(e)}'
                })

        # Print summary
        self._print_summary(results, success_count, failed)

        return results

    def _print_summary(self, results: List[Dict], success_count: int, failed: List[str]):
        """Print summary of parsing results"""
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)

        print(f"\nSuccess Rate: {success_count}/{len(results)} companies ({success_count/len(results)*100:.1f}%)")

        if failed:
            print(f"\nFailed: {len(failed)} companies")
            for ticker in failed:
                print(f"  ✗ {ticker}")

        # Show ROCE results
        successful_results = [r for r in results if r['roce'] is not None]
        if successful_results:
            print(f"\n{'Ticker':<8} {'Company':<30} {'Sector':<25} {'ROCE':>10}")
            print("─"*70)
            for r in sorted(successful_results, key=lambda x: x['roce'], reverse=True):
                print(f"{r['ticker']:<8} {r['name'][:28]:<30} {r['sector'][:23]:<25} {r['roce']:>9.2f}%")

            avg_roce = sum(r['roce'] for r in successful_results) / len(successful_results)
            print("─"*70)
            print(f"{'Average ROCE:':<65} {avg_roce:>9.2f}%")

        print("\n" + "="*70)
        print("NEXT STEPS")
        print("="*70)
        print("""
1. Review the JSON files in data/parsed/
   - Check calculation_log for detailed ROCE calculations
   - Verify metrics look reasonable

2. If results look good, proceed to parse all 366 companies:
   - Run: python scripts/parse_all_companies.py

3. Then load data into PostgreSQL:
   - Run: python scripts/load_to_database.py

4. Query your data:
   - Run: psql edgar_financial_metrics
""")

        print(f"\nParsed data saved to: {self.parsed_dir}/")
        print(f"Review calculation details in each {self.parsed_dir}/{{TICKER}}_parsed.json\n")


def main():
    """Main execution"""
    parser = TestCompanyParser()
    results = parser.run()
    return results


if __name__ == '__main__':
    main()
