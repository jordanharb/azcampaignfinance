#!/usr/bin/env python3
"""Test script to debug transaction API issues"""

import requests
import time
import json

BASE_URL = "https://seethemoney.az.gov"

# Create session
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9',
    'X-Requested-With': 'XMLHttpRequest',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Referer': f'{BASE_URL}/Reporting/Explore',
    'Origin': BASE_URL
})

# Test entity IDs
test_entities = [90001, 90002, 90003, 100001, 100029]

print("Testing transaction API...")
print("="*50)

for entity_id in test_entities:
    print(f"\nTesting entity {entity_id}:")
    
    # Build request
    url = f"{BASE_URL}/Reporting/Transactions"
    data = {
        'pageNumber': 1,
        'pageSize': 10,  # Just get 10 for testing
        'orderBy[0].Name': 'DateField',
        'orderBy[0].Desc': 'true',
        'entities[0]': entity_id,
        '_ts': str(int(time.time() * 1000))
    }
    
    try:
        response = session.post(url, data=data, timeout=10)
        
        print(f"  Status: {response.status_code}")
        print(f"  Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            trans_count = len(result.get('data', []))
            print(f"  ✅ Success! Found {trans_count} transactions")
            if trans_count > 0:
                print(f"  First transaction: {json.dumps(result['data'][0], indent=2)[:200]}...")
        else:
            print(f"  ❌ Error response:")
            print(f"  Response text: {response.text[:500]}")
            
    except Exception as e:
        print(f"  ❌ Exception: {e}")
    
    time.sleep(1)  # Be nice to the server

print("\n" + "="*50)
print("Testing complete!")