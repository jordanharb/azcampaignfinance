#!/usr/bin/env python3
"""
Remove duplicate donations from the database
"""

import os
import requests

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

print("="*70)
print("REMOVING DUPLICATE DONATIONS")
print("="*70)

# First, find ALL duplicates (not just sample)
print("\n📊 Finding all duplicate donations...")

all_donations = []
offset = 0
batch_size = 1000

while True:
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {
        "select": "donation_id,report_id,donor_name,donation_date,donation_amt",
        "order": "donation_id",
        "limit": str(batch_size),
        "offset": str(offset)
    }
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        batch = response.json()
        if not batch:
            break
        all_donations.extend(batch)
        if len(batch) < batch_size:
            break
        offset += batch_size
        if len(all_donations) % 10000 == 0:
            print(f"  Checked {len(all_donations)} donations so far...")
    else:
        print(f"❌ Error fetching donations: {response.status_code}")
        break

print(f"✅ Total donations checked: {len(all_donations)}")

# Find duplicates
from collections import defaultdict
donation_groups = defaultdict(list)

for d in all_donations:
    key = (d['report_id'], d['donor_name'], d['donation_date'], d['donation_amt'])
    donation_groups[key].append(d['donation_id'])

duplicates = {k: v for k, v in donation_groups.items() if len(v) > 1}

if not duplicates:
    print("\n✅ No duplicate donations found!")
else:
    print(f"\n⚠️  Found {len(duplicates)} sets of duplicate donations")
    
    # Show duplicates
    print("\nDuplicates found:")
    for key, ids in duplicates.items():
        report_id, donor, date, amt = key
        print(f"  Report {report_id}: {donor} on {date} for ${amt}")
        print(f"    Duplicate IDs: {ids} (keeping {ids[0]}, removing {ids[1:]})")
    
    # Remove duplicates (keep first, delete rest)
    ids_to_delete = []
    for ids in duplicates.values():
        ids_to_delete.extend(ids[1:])  # Keep first, delete rest
    
    print(f"\n🗑️  Removing {len(ids_to_delete)} duplicate donations...")
    
    # Delete in batches
    batch_size = 50
    for i in range(0, len(ids_to_delete), batch_size):
        batch = ids_to_delete[i:i+batch_size]
        id_list = ",".join(str(id) for id in batch)
        
        url = f"{SUPABASE_URL}/rest/v1/cf_donations"
        params = {"donation_id": f"in.({id_list})"}
        
        response = requests.delete(url, headers=headers, params=params)
        
        if response.status_code in [200, 204]:
            print(f"  ✅ Deleted batch: {len(batch)} donations")
        else:
            print(f"  ❌ Failed to delete batch: {response.status_code}")
    
    print(f"\n✅ Removed {len(ids_to_delete)} duplicate donations")

print("\n" + "="*70)
print("DUPLICATE REMOVAL COMPLETE")
print("="*70)