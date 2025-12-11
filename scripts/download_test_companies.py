#!/usr/bin/env python3
"""
Download EDGAR company facts data for test companies

Downloads full EDGAR company facts JSON from SEC API for the companies
mentioned in the Financial Metrics Extraction Guide (CVX, CAT, XOM).
"""

import json
import time
from pathlib import Path
import urllib.request
import urllib.error


# Test companies from the guide
TEST_COMPANIES = {
    'CVX': {
        'name': 'Chevron Corporation',
        'cik': '0000093410',  # CVX
    },
    'CAT': {
        'name': 'Caterpillar Inc.',
        'cik': '0000018230',  # CAT
    },
    'XOM': {
        'name': 'Exxon Mobil Corporation',
        'cik': '0000034088',  # XOM
    },
}


def download_edgar_data(cik: str, ticker: str, company_name: str, output_dir: Path) -> bool:
    """
    Download EDGAR company facts data from SEC API.

    Args:
        cik: Company CIK (with leading zeros, 10 digits)
        ticker: Stock ticker symbol
        company_name: Company name for display
        output_dir: Directory to save the JSON file

    Returns:
        True if successful, False otherwise
    """
    # Format CIK to 10 digits with leading zeros
    cik_formatted = cik.zfill(10)

    # SEC API endpoint
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_formatted}.json"

    print(f"\nDownloading {ticker} ({company_name})...")
    print(f"  URL: {url}")

    try:
        # SEC requires a User-Agent header
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Edgar Parser Test cary@example.com',  # Replace with your email
                'Accept-Encoding': 'gzip, deflate',
            }
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))

        # Save to file
        output_file = output_dir / f"{ticker}_edgar_company_facts.json"
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"  ✓ Downloaded successfully: {output_file.name} ({size_mb:.1f} MB)")

        return True

    except urllib.error.HTTPError as e:
        print(f"  ✗ HTTP Error {e.code}: {e.reason}")
        if e.code == 404:
            print(f"    CIK {cik_formatted} not found - please verify the CIK")
        elif e.code == 403:
            print(f"    Access forbidden - check User-Agent header")
        return False

    except urllib.error.URLError as e:
        print(f"  ✗ URL Error: {e.reason}")
        return False

    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
        return False


def main():
    """Download all test companies."""

    print("="*80)
    print("EDGAR DATA DOWNLOADER - Test Companies")
    print("="*80)
    print("\nThis script will download full EDGAR company facts data for:")
    for ticker, info in TEST_COMPANIES.items():
        print(f"  - {ticker}: {info['name']}")

    print("\nNote: SEC requires a User-Agent with contact email.")
    print("Please update the script with your email before running.\n")

    # Create data directory
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    print(f"Output directory: {data_dir}\n")
    print("="*80)

    successful = 0
    failed = 0

    for ticker, info in TEST_COMPANIES.items():
        success = download_edgar_data(
            cik=info['cik'],
            ticker=ticker,
            company_name=info['name'],
            output_dir=data_dir
        )

        if success:
            successful += 1
        else:
            failed += 1

        # Be nice to SEC servers - wait between requests
        if ticker != list(TEST_COMPANIES.keys())[-1]:  # Don't wait after last one
            print("  Waiting 1 second before next request...")
            time.sleep(1)

    print(f"\n{'='*80}")
    print("DOWNLOAD SUMMARY")
    print(f"{'='*80}")
    print(f"\nTotal companies: {len(TEST_COMPANIES)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if successful > 0:
        print(f"\n✓ Downloaded files are in: {data_dir}")
        print("\nNext steps:")
        print("  1. Run: python scripts/parse_all_companies.py")
        print("  2. Check results in: data/parsed/")

    print()


if __name__ == "__main__":
    main()
