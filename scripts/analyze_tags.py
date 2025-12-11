import json
from pathlib import Path

ticker = 'XOM'

raw_data_path = Path('data') / 'raw_edgar' / f'{ticker}_edgar_raw.json'

try: 
    print(f"Loading data from {raw_data_path}")
    with open(raw_data_path, 'r') as file:
        data_dict = json.load(file)
        gaap_data = data_dict.get('facts', {}).get('us-gaap', {})
except FileNotFoundError:
    print(f"Error: '{ticker}_edgar_raw.json' not found.")
except json.JSONDecodeError:
    print(f"Error: '{ticker}_edgar_raw.json' not found. Decode error")


gaap_keys = list(gaap_data.keys())

def get_latest_value_for_10K_key(gaap_data, key):
    """Retrieve the latest value for a given 10-K key from the GAAP data."""
    if key not in gaap_data:
        return None
    
    entries = gaap_data[key].get('units', {}).get('USD', [])
    ten_k_entries = [entry for entry in entries if entry.get('form') == '10-K']
    
    if not ten_k_entries:
        return None
    
    latest_entry = max(ten_k_entries, key=lambda x: x.get('end', ''))
    return {
        "val": latest_entry.get('val'),
        "end": latest_entry.get('end'),
        "filed": latest_entry.get('filed')
    }

gaap_latest_key_value_map = {}

for key in gaap_keys:
    latest_value = get_latest_value_for_10K_key(gaap_data, key)
    gaap_latest_key_value_map[key] = latest_value
    

val_path = Path('data') / f"{ticker}_10K_Values.json"

with open(val_path, 'w') as f:
    json.dump(gaap_latest_key_value_map, f, indent=2)

