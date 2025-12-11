#!/usr/bin/env python3
"""Test EDGAR API access"""

import requests
import json
import os
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

def test_edgar_fetch():
    """Test fetching data from SEC EDGAR API"""

    print("Testing SEC EDGAR API access...")
    print("=" * 70)

    # Get User-Agent from environment
    user_agent = os.getenv("EDGAR_USER_AGENT", "")

    if not user_agent or user_agent == "Your Name your.email@example.com":
        print("✗ ERROR: EDGAR_USER_AGENT not configured!")
        print("\nPlease update .env file with your real name and email:")
        print("  EDGAR_USER_AGENT=Your Name your.email@example.com")
        print("\nSEC requires proper identification in User-Agent header.")
        return False

    print(f"User-Agent: {user_agent}")
    print("=" * 70)

    # Test with Apple Inc.
    cik = "0000320193"  # Apple
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    print(f"\nFetching Apple Inc. (CIK: {cik})...")
    print(f"URL: {url}")

    try:
        headers = {"User-Agent": user_agent}
        response = requests.get(url, headers=headers)

        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            print(f"✓ Success!")
            print(f"  Company: {data.get('entityName', 'Unknown')}")
            print(f"  CIK: {data.get('cik', 'Unknown')}")
            print(f"  Data size: {len(response.text):,} bytes")

            # Count facts
            us_gaap_facts = data.get('facts', {}).get('us-gaap', {})
            fact_count = len(us_gaap_facts)
            print(f"  US-GAAP facts: {fact_count}")

            # Save to file
            output_file = "data/apple_edgar_live.json"
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2)

            print(f"\n✓ Saved to: {output_file}")

            # Show sample metrics
            print("\nSample metrics found:")
            sample_metrics = ['Assets', 'Liabilities', 'Revenues', 'NetIncomeLoss']
            for metric in sample_metrics:
                if metric in us_gaap_facts:
                    print(f"  ✓ {metric}")
                else:
                    print(f"  ✗ {metric} (not found)")

            print("\n" + "=" * 70)
            print("SUCCESS: EDGAR API test passed!")
            print("=" * 70)
            return True

        elif response.status_code == 403:
            print(f"✗ Access forbidden (403)")
            print("\nPossible issues:")
            print("  1. User-Agent header not properly configured")
            print("  2. Update EDGAR_USER_AGENT in .env with your real name/email")
            print("  3. SEC blocks generic or missing User-Agent headers")
            return False

        elif response.status_code == 429:
            print(f"✗ Rate limited (429)")
            print("\nSEC allows 10 requests per second. Wait and try again.")
            return False

        else:
            print(f"✗ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ Connection error!")
        print("\nCheck your internet connection.")
        return False

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_edgar_fetch()
    sys.exit(0 if success else 1)
