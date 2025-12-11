#!/usr/bin/env python3
"""
Parse all companies - with optional SEC API download

This script can:
1. Process existing files in data/raw_edgar/
2. Download company data directly from SEC API and parse
3. Generate comprehensive reports

Usage:
    # Process existing files
    python scripts/parse_all_companies.py

    # Download from SEC API and process
    python scripts/parse_all_companies.py --download --tickers AAPL,MSFT,GOOGL

    # Download using CIKs
    python scripts/parse_all_companies.py --download --ciks 320193,789019
"""

import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
import csv
import urllib.request
import urllib.error

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from edgar_parser.parser_v2 import EDGARParser


# Ticker to CIK mapping for common companies
TICKER_TO_CIK = {
    'AAPL': '0000320193',
    'MSFT': '0000789019',
    'GOOGL': '0001652044',
    'GOOG': '0001652044',
    'AMZN': '0001018724',
    'NVDA': '0001045810',
    'META': '0001326801',
    'TSLA': '0001318605',
    'BRK.B': '0001067983',
    'V': '0001403161',
    'JPM': '0000019617',
    'WMT': '0000104169',
    'MA': '0001141391',
    'PG': '0000080424',
    'JNJ': '0000200406',
    'HD': '0000354950',
    'CVX': '0000093410',
    'MRK': '0000310158',
    'ABBV': '0001551152',
    'KO': '0000021344',
    'PEP': '0000077476',
    'COST': '0000909832',
    'MCD': '0000063908',
    'XOM': '0000034088',
    'CAT': '0000018230',
    'BA': '0000012927',
}


def download_from_sec(cik: str, ticker: str = None) -> dict:
    """
    Download EDGAR company facts data directly from SEC API.

    Args:
        cik: Company CIK (can include leading zeros or not)
        ticker: Optional ticker symbol for display

    Returns:
        Dictionary with EDGAR company facts data

    Raises:
        Exception if download fails
    """
    # Format CIK to 10 digits with leading zeros
    cik_formatted = str(cik).zfill(10)

    # SEC API endpoint
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_formatted}.json"

    display_name = ticker if ticker else cik_formatted
    print(f"  Downloading {display_name} from SEC API...")
    print(f"    URL: {url}")

    try:
        # SEC requires a User-Agent header with contact info
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Edgar Parser research@example.com',  # Update with your email
                'Accept-Encoding': 'gzip, deflate',
            }
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))

        print(f"    ✓ Downloaded successfully")
        return data

    except urllib.error.HTTPError as e:
        error_msg = f"HTTP Error {e.code}: {e.reason}"
        if e.code == 404:
            error_msg += f" - CIK {cik_formatted} not found"
        elif e.code == 403:
            error_msg += " - Access forbidden (check User-Agent header)"
        print(f"    ✗ {error_msg}")
        raise Exception(error_msg)

    except urllib.error.URLError as e:
        error_msg = f"URL Error: {e.reason}"
        print(f"    ✗ {error_msg}")
        raise Exception(error_msg)

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"    ✗ {error_msg}")
        raise Exception(error_msg)


def parse_all_companies(
    download_mode: bool = False,
    tickers: list = None,
    ciks: list = None,
    user_email: str = None
):
    """
    Parse all companies - from files or by downloading from SEC API.

    Args:
        download_mode: If True, download from SEC API instead of using local files
        tickers: List of ticker symbols to download
        ciks: List of CIKs to download
        user_email: Email address for SEC User-Agent header
    """

    print("\n" + "="*80)
    print("EDGAR PARSER V2 - BATCH PROCESSING")
    print("="*80)

    data_dir = Path(__file__).parent.parent / "data"
    raw_edgar_dir = data_dir / "raw_edgar"

    # Determine what to process
    companies_to_process = []

    if download_mode:
        print("\nMode: Download from SEC API")

        if user_email:
            # Update User-Agent with provided email
            pass  # Would update in download_from_sec function

        # Build list of companies to download
        if tickers:
            print(f"Tickers requested: {', '.join(tickers)}\n")
            for ticker in tickers:
                ticker_upper = ticker.upper()
                if ticker_upper in TICKER_TO_CIK:
                    companies_to_process.append({
                        'ticker': ticker_upper,
                        'cik': TICKER_TO_CIK[ticker_upper],
                        'source': 'download'
                    })
                else:
                    print(f"⚠ Warning: Ticker {ticker_upper} not in mapping - skipping")
                    print(f"  Available tickers: {', '.join(sorted(TICKER_TO_CIK.keys()))}")

        elif ciks:
            print(f"CIKs requested: {', '.join(ciks)}\n")
            for cik in ciks:
                companies_to_process.append({
                    'ticker': None,
                    'cik': cik,
                    'source': 'download'
                })

        if not companies_to_process:
            print("No valid companies to download. Use --tickers or --ciks.")
            return

    else:
        print("\nMode: Process existing files")

        # Look in raw_edgar directory for existing files
        if raw_edgar_dir.exists():
            json_files = list(raw_edgar_dir.glob("*_edgar_raw.json"))
            print(f"Found {len(json_files)} file(s) in {raw_edgar_dir}\n")

            for f in json_files:
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"  - {f.name} ({size_mb:.1f} MB)")
                companies_to_process.append({
                    'ticker': f.stem.replace('_edgar_raw', ''),
                    'file_path': f,
                    'source': 'file'
                })
        else:
            print(f"Raw EDGAR directory not found: {raw_edgar_dir}")
            print("\nTry using --download mode to fetch from SEC API")
            return

    if not companies_to_process:
        print("No companies to process.")
        return

    print(f"\n{'='*80}")
    print(f"Processing {len(companies_to_process)} companies")
    print(f"{'='*80}\n")

    # Create output directory
    output_dir = data_dir / "parsed"
    output_dir.mkdir(exist_ok=True)

    # Initialize parser
    parser = EDGARParser()

    # Process each company
    results = []

    for idx, company_info in enumerate(companies_to_process, 1):
        ticker = company_info.get('ticker', 'Unknown')

        print(f"\n{'='*80}")
        print(f"[{idx}/{len(companies_to_process)}] Processing: {ticker}")
        print(f"{'='*80}\n")

        try:
            # Get EDGAR data (either from file or download)
            if company_info['source'] == 'file':
                print(f"Loading from file: {company_info['file_path'].name}")
                with open(company_info['file_path']) as f:
                    edgar_data = json.load(f)
            else:
                # Download from SEC API
                edgar_data = download_from_sec(
                    cik=company_info['cik'],
                    ticker=company_info.get('ticker')
                )
                # Be nice to SEC servers
                time.sleep(0.5)

            # Parse the data
            result = parser.parse_company_data(edgar_data, verbose=True)

            # Save individual company output
            output_file = output_dir / f"{ticker}_parsed.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)

            print(f"\n✓ Saved to: {output_file}")

            # Collect summary data
            if result['annual_periods']:
                most_recent = result['annual_periods'][0]

                summary = {
                    'company': result['metadata']['company_name'],
                    'ticker': ticker,
                    'cik': result['metadata']['cik'],
                    'total_periods': result['metadata']['total_periods'],
                    'most_recent_year': most_recent['fiscal_year_end'],
                    'filing_date': most_recent['filing_date'],
                }

                # Add metric details from most recent period
                metrics = most_recent.get('metrics', {})

                if 'ebit' in metrics:
                    ebit = metrics['ebit']
                    summary['ebit'] = ebit['value']
                    summary['ebit_method'] = ebit['method']
                    summary['ebit_tier'] = ebit['tier']
                    summary['ebit_validation'] = ebit.get('validation', 'N/A')
                else:
                    summary['ebit'] = None
                    summary['ebit_method'] = 'Not found'
                    summary['ebit_tier'] = None
                    summary['ebit_validation'] = None

                if 'total_debt' in metrics:
                    debt = metrics['total_debt']
                    summary['total_debt'] = debt['value']
                    summary['debt_method'] = debt['method']
                    warnings = debt.get('warnings')
                    summary['debt_warnings'] = len(warnings) if warnings else 0
                else:
                    summary['total_debt'] = None
                    summary['debt_method'] = 'Not found'
                    summary['debt_warnings'] = None

                if 'cash' in metrics:
                    cash = metrics['cash']
                    summary['unrestricted_cash'] = cash['unrestricted_cash']
                    summary['total_cash'] = cash['total_cash']
                    summary['restricted_cash'] = cash['restricted_cash']
                    summary['cash_method'] = cash['method']
                else:
                    summary['unrestricted_cash'] = None
                    summary['total_cash'] = None
                    summary['restricted_cash'] = None
                    summary['cash_method'] = 'Not found'

                if 'assets' in metrics:
                    summary['assets'] = metrics['assets']['value']
                    summary['assets_method'] = metrics['assets']['method']
                else:
                    summary['assets'] = None
                    summary['assets_method'] = 'Not found'

                if 'current_liabilities' in metrics:
                    summary['current_liabilities'] = metrics['current_liabilities']['value']
                    summary['current_liabilities_method'] = metrics['current_liabilities']['method']
                else:
                    summary['current_liabilities'] = None
                    summary['current_liabilities_method'] = 'Not found'

                # Add calculated ratios
                ratios = most_recent.get('calculated_ratios', {})

                if 'roce' in ratios:
                    roce = ratios['roce']
                    summary['roce'] = roce.get('value')
                    summary['roce_status'] = roce.get('status', 'success')
                    summary['capital_employed'] = roce.get('components', {}).get('capital_employed')
                else:
                    summary['roce'] = None
                    summary['roce_status'] = 'missing'
                    summary['capital_employed'] = None

                if 'earnings_yield_components' in ratios:
                    ey = ratios['earnings_yield_components']
                    summary['net_debt'] = ey.get('net_debt')
                    summary['ey_status'] = ey.get('status', 'success')
                else:
                    summary['net_debt'] = None
                    summary['ey_status'] = 'missing'

                results.append(summary)

        except Exception as e:
            print(f"\n✗ ERROR processing {ticker}: {str(e)}")
            import traceback
            traceback.print_exc()

            results.append({
                'company': ticker,
                'ticker': ticker,
                'cik': company_info.get('cik', 'Unknown'),
                'error': str(e)
            })

    # Generate summary reports (same as before)
    print(f"\n{'='*80}")
    print("GENERATING SUMMARY REPORTS")
    print(f"{'='*80}\n")

    # CSV Summary
    csv_file = output_dir / f"parsing_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    if results:
        all_keys = set()
        for r in results:
            all_keys.update(r.keys())

        fieldnames = sorted(all_keys)

        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"✓ CSV summary saved to: {csv_file}")

    # Text Report
    report_file = output_dir / f"parsing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    with open(report_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("EDGAR PARSER V2 - BATCH PROCESSING REPORT\n")
        f.write("="*80 + "\n")
        f.write(f"\nGenerated: {datetime.now().isoformat()}\n")
        f.write(f"Total companies processed: {len(companies_to_process)}\n")
        f.write(f"Successful: {len([r for r in results if 'error' not in r])}\n")
        f.write(f"Errors: {len([r for r in results if 'error' in r])}\n")
        f.write("\n" + "="*80 + "\n\n")

        # Summary by company
        for result in results:
            if 'error' in result:
                f.write(f"Company: {result['company']}\n")
                f.write(f"Ticker: {result['ticker']}\n")
                f.write(f"Status: ERROR\n")
                f.write(f"Error: {result['error']}\n")
                f.write("-"*80 + "\n\n")
                continue

            f.write(f"Company: {result['company']}\n")
            f.write(f"Ticker: {result['ticker']}\n")
            f.write(f"CIK: {result['cik']}\n")
            f.write(f"Total Periods Extracted: {result['total_periods']}\n")
            f.write(f"Most Recent Period: {result['most_recent_year']}\n")
            f.write(f"Filing Date: {result['filing_date']}\n\n")

            f.write("Metrics Extracted:\n")
            f.write(f"  EBIT: ${result['ebit']:,} ({result['ebit_method']}, Tier {result['ebit_tier']})\n" if result['ebit'] else "  EBIT: Not found\n")
            if result.get('ebit_validation') and result['ebit_validation'] != 'N/A':
                f.write(f"    Validation: {result['ebit_validation']}\n")

            f.write(f"  Total Debt: ${result['total_debt']:,} ({result['debt_method']})\n" if result['total_debt'] else "  Total Debt: Not found\n")
            if result.get('debt_warnings') and result['debt_warnings'] > 0:
                f.write(f"    Warnings: {result['debt_warnings']}\n")

            f.write(f"  Unrestricted Cash: ${result['unrestricted_cash']:,} ({result['cash_method']})\n" if result['unrestricted_cash'] else "  Unrestricted Cash: Not found\n")
            if result.get('restricted_cash') and result['restricted_cash'] > 0:
                f.write(f"    Restricted Cash: ${result['restricted_cash']:,}\n")

            f.write(f"  Total Assets: ${result['assets']:,}\n" if result['assets'] else "  Total Assets: Not found\n")
            f.write(f"  Current Liabilities: ${result['current_liabilities']:,}\n" if result['current_liabilities'] else "  Current Liabilities: Not found\n")

            f.write("\nCalculated Ratios:\n")
            f.write(f"  ROCE: {result['roce']:.2f}% (Capital Employed: ${result['capital_employed']:,})\n" if result['roce'] else f"  ROCE: Could not calculate ({result['roce_status']})\n")
            f.write(f"  Net Debt: ${result['net_debt']:,} (ready for Earnings Yield)\n" if result['net_debt'] is not None else f"  Net Debt: Could not calculate ({result['ey_status']})\n")

            f.write("\n" + "-"*80 + "\n\n")

        # Method usage statistics
        f.write("="*80 + "\n")
        f.write("METHOD USAGE STATISTICS\n")
        f.write("="*80 + "\n\n")

        # Count methods
        ebit_methods = {}
        debt_methods = {}
        cash_methods = {}

        for r in results:
            if 'error' not in r:
                if r.get('ebit_method'):
                    ebit_methods[r['ebit_method']] = ebit_methods.get(r['ebit_method'], 0) + 1
                if r.get('debt_method'):
                    debt_methods[r['debt_method']] = debt_methods.get(r['debt_method'], 0) + 1
                if r.get('cash_method'):
                    cash_methods[r['cash_method']] = cash_methods.get(r['cash_method'], 0) + 1

        f.write("EBIT Calculation Methods:\n")
        for method, count in sorted(ebit_methods.items(), key=lambda x: x[1], reverse=True):
            f.write(f"  {method}: {count}\n")

        f.write("\nDebt Calculation Methods:\n")
        for method, count in sorted(debt_methods.items(), key=lambda x: x[1], reverse=True):
            f.write(f"  {method}: {count}\n")

        f.write("\nCash Calculation Methods:\n")
        for method, count in sorted(cash_methods.items(), key=lambda x: x[1], reverse=True):
            f.write(f"  {method}: {count}\n")

    print(f"✓ Text report saved to: {report_file}")

    # Console summary
    print(f"\n{'='*80}")
    print("BATCH PROCESSING COMPLETE")
    print(f"{'='*80}\n")

    print(f"Total companies processed: {len(companies_to_process)}")
    print(f"Successful: {len([r for r in results if 'error' not in r])}")
    print(f"Errors: {len([r for r in results if 'error' in r])}")

    print("\nCompany Summary:")
    print(f"{'Ticker':<8} {'Company':<30} {'Periods':<10} {'ROCE':<10} {'EBIT Method':<30}")
    print("-"*88)

    for result in results:
        if 'error' in result:
            print(f"{result['ticker']:<8} {'ERROR':<30} {'-':<10} {'-':<10} {result.get('error', 'Unknown')[:30]:<30}")
        else:
            company_name = result['company'][:28] if len(result['company']) > 28 else result['company']
            roce_str = f"{result['roce']:.2f}%" if result['roce'] else "N/A"
            ebit_method = result.get('ebit_method', 'N/A')[:28]
            print(f"{result['ticker']:<8} {company_name:<30} {result['total_periods']:<10} {roce_str:<10} {ebit_method:<30}")

    print(f"\n{'='*80}")
    print("Output files created:")
    print(f"  - Individual parsed JSONs: {output_dir}/*_parsed.json")
    print(f"  - Summary CSV: {csv_file}")
    print(f"  - Detailed report: {report_file}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse EDGAR company data - from files or SEC API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process files in data/raw_edgar/
  python scripts/parse_all_companies.py

  # Download from SEC API and process
  python scripts/parse_all_companies.py --download --tickers AAPL,MSFT,CVX

  # Download using CIKs
  python scripts/parse_all_companies.py --download --ciks 320193,789019

Available tickers: """ + ', '.join(sorted(TICKER_TO_CIK.keys()))
    )

    parser.add_argument(
        '--download',
        action='store_true',
        help='Download data from SEC API instead of using local files'
    )

    parser.add_argument(
        '--tickers',
        type=str,
        help='Comma-separated list of ticker symbols to download (requires --download)'
    )

    parser.add_argument(
        '--ciks',
        type=str,
        help='Comma-separated list of CIKs to download (requires --download)'
    )

    parser.add_argument(
        '--email',
        type=str,
        help='Email address for SEC User-Agent header (recommended)'
    )

    args = parser.parse_args()

    # Parse arguments
    tickers_list = args.tickers.split(',') if args.tickers else None
    ciks_list = args.ciks.split(',') if args.ciks else None

    if args.download and not (tickers_list or ciks_list):
        parser.error("--download requires either --tickers or --ciks")

    if (tickers_list or ciks_list) and not args.download:
        parser.error("--tickers and --ciks require --download flag")

    parse_all_companies(
        download_mode=args.download,
        tickers=tickers_list,
        ciks=ciks_list,
        user_email=args.email
    )
