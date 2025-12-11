#!/usr/bin/env python3
"""
S&P 500 Company List Builder
Downloads S&P 500 constituents and filters to compatible sectors
Output: target_companies.csv with ~374 companies ready to parse
"""

import pandas as pd
import requests
import sys

def build_target_company_list():
    """
    Build list of ~350-400 companies to parse from S&P 500
    
    Returns:
        DataFrame with columns: ticker, company_name, sector, cik
    """
    
    print("="*70)
    print("S&P 500 COMPANY LIST BUILDER")
    print("="*70)
    
    # 1. Download S&P 500 from Wikipedia
    print("\n[1/5] Downloading S&P 500 constituents from Wikipedia...")
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'

        # Define headers with a proper User-Agent to avoid 403 errors
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Fetch the page with headers
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise error for bad status codes

        # Parse with pandas
        sp500 = pd.read_html(response.text)[0]
        print(f"      ✓ Downloaded {len(sp500)} companies")
    except Exception as e:
        print(f"      ✗ Error: {e}")
        print("\n      Unable to download from Wikipedia.")
        print("      Check your internet connection or try again later.")
        sys.exit(1)
    
    # 2. Define compatible sectors
    print("\n[2/5] Filtering to compatible sectors...")
    print("      Compatible sectors (where ROCE and Earnings Yield work):")
    
    compatible_sectors = {
        'Information Technology': 'Tech companies (AAPL, MSFT, GOOGL...)',
        'Consumer Discretionary': 'Retail, restaurants (WMT, HD, MCD...)',
        'Consumer Staples': 'Consumer goods (PG, KO, PEP...)',
        'Industrials': 'Manufacturing (BA, CAT, GE...)',
        'Energy': 'Oil & gas (XOM, CVX, COP...)',
        'Materials': 'Chemicals, metals (DOW, LIN...)',
        'Communication Services': 'Telecom, media (GOOGL, META, DIS...)',
        'Health Care': 'Pharma, biotech (JNJ, UNH, PFE...)'
    }
    
    for sector, description in compatible_sectors.items():
        count = len(sp500[sp500['GICS Sector'] == sector])
        print(f"      ✓ {sector:30} {count:3} companies")
    
    print("\n      Excluded sectors (incompatible accounting):")
    excluded_sectors = {
        'Financials': 'Banks, insurance (use ROE not ROCE)',
        'Real Estate': 'REITs (use FFO not EBIT)',
        'Utilities': 'Regulated returns (less meaningful)'
    }
    
    for sector, reason in excluded_sectors.items():
        count = len(sp500[sp500['GICS Sector'] == sector])
        print(f"      ✗ {sector:30} {count:3} companies - {reason}")
    
    # 3. Filter to compatible sectors
    target_companies = sp500[sp500['GICS Sector'].isin(compatible_sectors.keys())].copy()
    
    print(f"\n      ✓ Total compatible companies: {len(target_companies)}")
    
    # 4. Clean up data
    print("\n[3/5] Cleaning and formatting data...")
    
    # Clean up CIK (ensure 10 digits with leading zeros for EDGAR)
    target_companies['CIK'] = target_companies['CIK'].astype(str).str.zfill(10)
    
    # Select and rename columns
    target_companies = target_companies[[
        'Symbol',      # Ticker
        'Security',    # Company name
        'GICS Sector', # Sector
        'CIK'          # For EDGAR lookup
    ]].rename(columns={
        'Symbol': 'ticker',
        'Security': 'company_name',
        'GICS Sector': 'sector',
        'CIK': 'cik'
    })
    
    # Remove any rows with missing data
    initial_count = len(target_companies)
    target_companies = target_companies.dropna()
    if len(target_companies) < initial_count:
        print(f"      ⚠ Removed {initial_count - len(target_companies)} rows with missing data")
    
    print(f"      ✓ {len(target_companies)} companies ready")
    
    # 5. Summary statistics
    print("\n[4/5] Summary statistics:")
    print("\n      Companies per sector:")
    sector_counts = target_companies['sector'].value_counts().sort_values(ascending=False)
    for sector, count in sector_counts.items():
        print(f"        {sector:30} {count:3} companies")
    
    # 6. Save to CSV
    print("\n[5/5] Saving to file...")
    output_file = 'data/target_companies.csv'
    target_companies.to_csv(output_file, index=False)
    print(f"      ✓ Saved to: {output_file}")
    
    # Final summary
    print("\n" + "="*70)
    print("SUCCESS!")
    print("="*70)
    print(f"\n✓ Total companies ready to parse: {len(target_companies)}")
    print(f"✓ Average per sector: {len(target_companies) / len(compatible_sectors):.1f} companies")
    print(f"✓ File: {output_file}")
    print("\nSample companies:")
    print(target_companies.head(10).to_string(index=False))
    print("\n" + "="*70)
    print("NEXT STEPS:")
    print("="*70)
    print("1. Review target_companies.csv")
    print("2. Run parser on these companies")
    print("3. Build your industry benchmarks!")
    print("\nReady to parse! 🚀\n")
    
    return target_companies


def show_sector_breakdown(df):
    """Show detailed breakdown by sector"""
    print("\n" + "="*70)
    print("DETAILED SECTOR BREAKDOWN")
    print("="*70)
    
    for sector in df['sector'].unique():
        sector_companies = df[df['sector'] == sector]
        print(f"\n{sector} ({len(sector_companies)} companies):")
        print(sector_companies[['ticker', 'company_name']].head(10).to_string(index=False))
        if len(sector_companies) > 10:
            print(f"  ... and {len(sector_companies) - 10} more")


def main():
    """Main execution"""
    
    # Build the list
    companies = build_target_company_list()
    
    # Optionally show detailed breakdown
    if '--detailed' in sys.argv:
        show_sector_breakdown(companies)
    
    return companies


if __name__ == '__main__':
    main()
