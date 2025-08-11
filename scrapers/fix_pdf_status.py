#!/usr/bin/env python3
"""
Fix PDF status - mark PDFs as processed if they have reports
"""

import os
import requests
from datetime import datetime

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

print("="*70)
print("FIXING PDF STATUS")
print("="*70)

# Step 1: Get all PDFs that have reports
print("\n📊 Finding all PDFs with reports...")

all_reports = []
offset = 0
batch_size = 1000

while True:
    url = f"{SUPABASE_URL}/rest/v1/cf_reports"
    params = {
        "select": "pdf_id,report_id,entity_id,donation_count",
        "order": "pdf_id",
        "limit": str(batch_size),
        "offset": str(offset)
    }
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        batch = response.json()
        if not batch:
            break
        all_reports.extend(batch)
        if len(batch) < batch_size:
            break
        offset += batch_size
    else:
        print(f"❌ Error fetching reports: {response.status_code}")
        break

print(f"✅ Found {len(all_reports)} reports")

# Get unique PDF IDs from reports
pdf_ids_with_reports = set(r['pdf_id'] for r in all_reports if r['pdf_id'])
print(f"✅ Found {len(pdf_ids_with_reports)} unique PDFs with reports")

# Step 2: Check which of these are NOT marked as converted
print("\n🔍 Checking current status of these PDFs...")

pdfs_to_fix = []
offset = 0

while pdf_ids_with_reports:
    # Process in batches
    batch_ids = list(pdf_ids_with_reports)[:1000]
    pdf_ids_with_reports = set(list(pdf_ids_with_reports)[1000:])
    
    id_list = ",".join(str(id) for id in batch_ids)
    url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
    params = {
        "select": "pdf_id,csv_converted",
        "pdf_id": f"in.({id_list})"
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        pdfs = response.json()
        for pdf in pdfs:
            if not pdf['csv_converted']:
                pdfs_to_fix.append(pdf['pdf_id'])

print(f"⚠️  Found {len(pdfs_to_fix)} PDFs that have reports but are NOT marked as converted")

if not pdfs_to_fix:
    print("\n✅ All PDFs with reports are already correctly marked!")
else:
    # Step 3: Update these PDFs to mark them as converted
    print(f"\n♻️  Marking {len(pdfs_to_fix)} PDFs as converted...")
    
    batch_size = 100
    total_updated = 0
    
    for i in range(0, len(pdfs_to_fix), batch_size):
        batch = pdfs_to_fix[i:i+batch_size]
        id_list = ",".join(str(id) for id in batch)
        
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {"pdf_id": f"in.({id_list})"}
        update_data = {
            'csv_converted': True,
            'conversion_date': datetime.now().isoformat()
        }
        
        response = requests.patch(url, headers=headers, params=params, json=update_data)
        
        if response.status_code in [200, 204]:
            total_updated += len(batch)
            print(f"  ✅ Updated batch {i//batch_size + 1}: {len(batch)} PDFs (total: {total_updated})")
        else:
            print(f"  ❌ Failed to update batch: {response.status_code}")

    print(f"\n✅ Successfully marked {total_updated} PDFs as converted")

# Step 4: Final verification
print("\n📊 FINAL STATUS CHECK:")
print("-" * 40)

# Count total PDFs
response = requests.head(f"{SUPABASE_URL}/rest/v1/cf_report_pdfs", 
                        headers={**headers, "Prefer": "count=exact"})
if 'content-range' in response.headers:
    total_pdfs = response.headers['content-range'].split('/')[1]
    print(f"Total PDFs: {total_pdfs}")

# Count converted PDFs
params = {"csv_converted": "eq.true", "limit": "1"}
response = requests.head(f"{SUPABASE_URL}/rest/v1/cf_report_pdfs", 
                        headers={**headers, "Prefer": "count=exact"}, 
                        params=params)
if 'content-range' in response.headers:
    converted = response.headers['content-range'].split('/')[1]
    print(f"Marked as converted: {converted}")

# Count not converted
params = {"csv_converted": "eq.false", "limit": "1"}
response = requests.head(f"{SUPABASE_URL}/rest/v1/cf_report_pdfs", 
                        headers={**headers, "Prefer": "count=exact"}, 
                        params=params)
if 'content-range' in response.headers:
    not_converted = response.headers['content-range'].split('/')[1]
    print(f"Not converted (need processing): {not_converted}")

print("\n" + "="*70)
print("PDF STATUS FIX COMPLETE")
print("="*70)