#!/usr/bin/env python3
"""
Find all donations with invalid state codes
"""

import os
import requests
from collections import defaultdict

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Valid US state codes
VALID_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC', 'PR', 'VI', 'GU', 'AS', 'MP',  # Territories
    '', None  # Allow empty/null for missing data
}

print("="*70)
print("FINDING DONATIONS WITH INVALID STATE CODES")
print("="*70)

# Fetch all donations
print("\n📥 Fetching all donations to check state codes...")

bad_donations = []
state_counts = defaultdict(int)
offset = 0
batch_size = 1000
total_checked = 0

while True:
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {
        "select": "donation_id,report_id,entity_id,donor_name,donor_state,donor_city,donor_addr",
        "order": "donation_id",
        "limit": str(batch_size),
        "offset": str(offset)
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        batch = response.json()
        if not batch:
            break
        
        for donation in batch:
            total_checked += 1
            state = donation.get('donor_state', '')
            
            # Check if state is invalid
            if state not in VALID_STATES:
                bad_donations.append(donation)
                state_counts[state] += 1
        
        if len(batch) < batch_size:
            break
        
        offset += batch_size
        
        if total_checked % 10000 == 0:
            print(f"  Checked {total_checked} donations, found {len(bad_donations)} with bad states...")
    else:
        print(f"❌ Error fetching donations: {response.status_code}")
        break

print(f"\n✅ Checked {total_checked} total donations")
print(f"❌ Found {len(bad_donations)} donations with invalid state codes")

# Show breakdown of invalid states
print("\n📊 Invalid State Code Breakdown:")
print("-" * 40)
for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f"  '{state}': {count} occurrences")
    
if len(state_counts) > 20:
    print(f"  ... and {len(state_counts) - 20} more invalid codes")

# Group by report to see affected reports
reports_affected = defaultdict(list)
for donation in bad_donations:
    reports_affected[donation['report_id']].append(donation['donation_id'])

print(f"\n📋 Affected Reports: {len(reports_affected)}")

# Get entity and PDF information for affected reports
print("\n🔍 Getting PDF information for affected reports...")

report_ids = list(reports_affected.keys())[:100]  # Sample first 100
if report_ids:
    id_list = ",".join(str(id) for id in report_ids)
    url = f"{SUPABASE_URL}/rest/v1/cf_reports"
    params = {
        "select": "report_id,pdf_id,entity_id",
        "report_id": f"in.({id_list})"
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        reports = response.json()
        pdf_ids = set(r['pdf_id'] for r in reports if r['pdf_id'])
        entity_ids = set(r['entity_id'] for r in reports if r['entity_id'])
        
        print(f"  PDFs to reprocess: {len(pdf_ids)}")
        print(f"  Entities affected: {len(entity_ids)}")

# Show sample of bad data
print("\n📋 Sample of Bad Address Data:")
print("-" * 40)
for donation in bad_donations[:10]:
    print(f"  ID {donation['donation_id']}: {donation['donor_name']}")
    print(f"    Address: {donation['donor_addr']}")
    print(f"    City: {donation['donor_city']}")
    print(f"    State: '{donation['donor_state']}' ❌")
    print()

# Save to file for review
output_file = "bad_addresses.json"
import json
with open(output_file, 'w') as f:
    json.dump({
        'total_bad': len(bad_donations),
        'reports_affected': len(reports_affected),
        'state_counts': dict(state_counts),
        'sample_donations': bad_donations[:100],
        'affected_report_ids': list(reports_affected.keys())
    }, f, indent=2)

print(f"\n💾 Saved detailed analysis to {output_file}")

print("\n" + "="*70)
print("ANALYSIS COMPLETE")
print("="*70)
print(f"\nNext step: Run clean_bad_addresses.py to:")
print(f"1. Delete {len(bad_donations)} bad donations")
print(f"2. Delete empty reports")
print(f"3. Mark {len(reports_affected)} PDFs for reprocessing")