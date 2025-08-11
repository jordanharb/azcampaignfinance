#!/usr/bin/env python3
"""
Clean up donations with bad addresses and reset PDFs for reprocessing
"""

import os
import requests
import json
import sys
from datetime import datetime

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
    '', None  # Allow empty/null
}

print("="*70)
print("CLEANING BAD ADDRESS DATA")
print("="*70)

# Load analysis from previous script
try:
    with open('bad_addresses.json', 'r') as f:
        analysis = json.load(f)
    print(f"\n📊 Loaded analysis:")
    print(f"  Bad donations: {analysis['total_bad']}")
    print(f"  Reports affected: {analysis['reports_affected']}")
except FileNotFoundError:
    print("\n❌ bad_addresses.json not found. Run find_bad_addresses.py first!")
    sys.exit(1)

print("\n⚠️  This will:")
print(f"1. Delete donations with invalid state codes")
print(f"2. Delete reports that have no remaining donations")
print(f"3. Mark affected PDFs as not processed for re-scraping")

response = input("\nType 'DELETE' to proceed: ")
if response != 'DELETE':
    print("Cancelled.")
    sys.exit(0)

# Step 1: Find all bad donations
print("\n📥 Finding all donations with invalid state codes...")

bad_donation_ids = []
affected_report_ids = set()
offset = 0
batch_size = 1000

while True:
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {
        "select": "donation_id,report_id,donor_state",
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
            state = donation.get('donor_state', '')
            if state not in VALID_STATES:
                bad_donation_ids.append(donation['donation_id'])
                if donation['report_id']:
                    affected_report_ids.add(donation['report_id'])
        
        if len(batch) < batch_size:
            break
        offset += batch_size
    else:
        print(f"❌ Error fetching donations: {response.status_code}")
        break

print(f"✅ Found {len(bad_donation_ids)} bad donations across {len(affected_report_ids)} reports")

# Step 2: Delete bad donations
print(f"\n🗑️  Deleting {len(bad_donation_ids)} donations with bad addresses...")

deleted_count = 0
batch_size = 100

for i in range(0, len(bad_donation_ids), batch_size):
    batch = bad_donation_ids[i:i+batch_size]
    id_list = ",".join(str(id) for id in batch)
    
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {"donation_id": f"in.({id_list})"}
    
    response = requests.delete(url, headers=headers, params=params)
    
    if response.status_code in [200, 204]:
        deleted_count += len(batch)
        print(f"  Deleted batch {i//batch_size + 1}: {len(batch)} donations (total: {deleted_count})")
    else:
        print(f"  ❌ Failed to delete batch: {response.status_code}")

print(f"✅ Deleted {deleted_count} donations")

# Step 3: Find reports that now have no donations
print("\n🔍 Finding reports with no remaining donations...")

reports_to_delete = []
pdf_ids_to_reset = []

for report_id in affected_report_ids:
    # Check if report still has donations
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {
        "select": "donation_id",
        "report_id": f"eq.{report_id}",
        "limit": "1"
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        donations = response.json()
        if not donations:
            # No donations left, mark for deletion
            reports_to_delete.append(report_id)

# Get PDF IDs for all affected reports (both deleted and remaining)
if affected_report_ids:
    id_list = ",".join(str(id) for id in affected_report_ids)
    url = f"{SUPABASE_URL}/rest/v1/cf_reports"
    params = {
        "select": "report_id,pdf_id",
        "report_id": f"in.({id_list})"
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        reports = response.json()
        pdf_ids_to_reset = [r['pdf_id'] for r in reports if r['pdf_id']]

print(f"  Reports with no donations: {len(reports_to_delete)}")
print(f"  PDFs to reset: {len(pdf_ids_to_reset)}")

# Step 4: Delete empty reports
if reports_to_delete:
    print(f"\n🗑️  Deleting {len(reports_to_delete)} empty reports...")
    
    for i in range(0, len(reports_to_delete), batch_size):
        batch = reports_to_delete[i:i+batch_size]
        id_list = ",".join(str(id) for id in batch)
        
        url = f"{SUPABASE_URL}/rest/v1/cf_reports"
        params = {"report_id": f"in.({id_list})"}
        
        response = requests.delete(url, headers=headers, params=params)
        
        if response.status_code in [200, 204]:
            print(f"  Deleted batch: {len(batch)} reports")

# Step 5: Reset PDFs for reprocessing
if pdf_ids_to_reset:
    print(f"\n♻️  Resetting {len(pdf_ids_to_reset)} PDFs for reprocessing...")
    
    for i in range(0, len(pdf_ids_to_reset), batch_size):
        batch = pdf_ids_to_reset[i:i+batch_size]
        id_list = ",".join(str(id) for id in batch)
        
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {"pdf_id": f"in.({id_list})"}
        update_data = {
            'csv_converted': False,
            'conversion_date': None
        }
        
        response = requests.patch(url, headers=headers, params=params, json=update_data)
        
        if response.status_code in [200, 204]:
            print(f"  Reset batch: {len(batch)} PDFs")

print("\n" + "="*70)
print("✅ CLEANUP COMPLETE")
print("="*70)
print(f"\nSummary:")
print(f"  Deleted {deleted_count} bad donations")
print(f"  Deleted {len(reports_to_delete)} empty reports")
print(f"  Reset {len(pdf_ids_to_reset)} PDFs for reprocessing")
print(f"\nYou can now run step3_concurrent.py to reprocess these PDFs")
print(f"The fixed address parser will properly handle suite numbers!")