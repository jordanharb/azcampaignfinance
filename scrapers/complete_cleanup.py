#!/usr/bin/env python3
"""
Complete cleanup of all data quality issues
Deletes ALL donations from affected reports to prevent duplicates
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

print("="*70)
print("COMPLETE DATA CLEANUP")
print("="*70)

# Load analysis
try:
    with open('all_issues_analysis.json', 'r') as f:
        analysis = json.load(f)
    print(f"\n📊 Loaded analysis:")
    print(f"  Total affected reports: {analysis['total_affected_reports']}")
    print(f"  - Address parsing issues: {analysis['address_parsing_reports']}")
    print(f"  - Data shift issues: {analysis['data_shift_reports']}")
    print(f"  - Both issues: {analysis['both_issues_reports']}")
    print(f"  PDFs to reset: {len(analysis['pdfs_to_reset'])}")
except FileNotFoundError:
    print("\n❌ all_issues_analysis.json not found. Run identify_all_issues.py first!")
    sys.exit(1)

affected_report_ids = analysis['affected_report_ids']
pdf_ids_to_reset = analysis['pdfs_to_reset']

if not affected_report_ids:
    print("\n✅ No issues found to clean up!")
    sys.exit(0)

# Count donations that will be deleted
print("\n📊 Counting donations to be deleted...")
total_donations = 0
batch_size = 100

for i in range(0, len(affected_report_ids), batch_size):
    batch = affected_report_ids[i:i+batch_size]
    id_list = ",".join(str(id) for id in batch)
    
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {
        "select": "donation_id",
        "report_id": f"in.({id_list})",
        "limit": "1"
    }
    
    response = requests.head(url, headers={**headers, "Prefer": "count=exact"}, params=params)
    if 'content-range' in response.headers:
        count = int(response.headers['content-range'].split('/')[1])
        total_donations += count

print(f"  Total donations to delete: {total_donations}")

print("\n⚠️  THIS WILL:")
print(f"1. Delete ALL {total_donations} donations from {len(affected_report_ids)} reports")
print(f"2. Delete all {len(affected_report_ids)} affected reports")
print(f"3. Reset {len(pdf_ids_to_reset)} PDFs for reprocessing")
print("\n⚠️  This is necessary to prevent duplicates when re-scraping!")

response = input("\nType 'DELETE ALL' to proceed: ")
if response != 'DELETE ALL':
    print("Cancelled.")
    sys.exit(0)

# Step 1: Delete ALL donations from affected reports
print(f"\n🗑️  Step 1: Deleting ALL donations from {len(affected_report_ids)} affected reports...")

deleted_donations = 0
batch_size = 50

for i in range(0, len(affected_report_ids), batch_size):
    batch = affected_report_ids[i:i+batch_size]
    id_list = ",".join(str(id) for id in batch)
    
    # Delete all donations for these reports
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {"report_id": f"in.({id_list})"}
    
    # First count how many we're deleting
    count_response = requests.head(url, headers={**headers, "Prefer": "count=exact"}, params=params)
    batch_count = 0
    if 'content-range' in count_response.headers:
        batch_count = int(count_response.headers['content-range'].split('/')[1])
    
    # Now delete them
    response = requests.delete(url, headers=headers, params=params)
    
    if response.status_code in [200, 204]:
        deleted_donations += batch_count
        print(f"  Batch {i//batch_size + 1}: Deleted {batch_count} donations from {len(batch)} reports")
        print(f"    Progress: {deleted_donations}/{total_donations} donations deleted")
    else:
        print(f"  ❌ Failed to delete batch: {response.status_code}")

print(f"\n✅ Deleted {deleted_donations} donations total")

# Step 2: Delete all affected reports
print(f"\n🗑️  Step 2: Deleting {len(affected_report_ids)} affected reports...")

deleted_reports = 0
batch_size = 100

for i in range(0, len(affected_report_ids), batch_size):
    batch = affected_report_ids[i:i+batch_size]
    id_list = ",".join(str(id) for id in batch)
    
    url = f"{SUPABASE_URL}/rest/v1/cf_reports"
    params = {"report_id": f"in.({id_list})"}
    
    response = requests.delete(url, headers=headers, params=params)
    
    if response.status_code in [200, 204]:
        deleted_reports += len(batch)
        print(f"  Batch {i//batch_size + 1}: Deleted {len(batch)} reports (total: {deleted_reports})")
    else:
        print(f"  ❌ Failed to delete batch: {response.status_code}")

print(f"\n✅ Deleted {deleted_reports} reports")

# Step 3: Reset PDFs for reprocessing
print(f"\n♻️  Step 3: Resetting {len(pdf_ids_to_reset)} PDFs for reprocessing...")

reset_count = 0
batch_size = 100

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
        reset_count += len(batch)
        print(f"  Batch {i//batch_size + 1}: Reset {len(batch)} PDFs (total: {reset_count})")
    else:
        print(f"  ❌ Failed to reset batch: {response.status_code}")

print(f"\n✅ Reset {reset_count} PDFs")

# Summary
print("\n" + "="*70)
print("✅ CLEANUP COMPLETE")
print("="*70)
print(f"\n📊 Final Summary:")
print(f"  Deleted {deleted_donations} donations")
print(f"  Deleted {deleted_reports} reports")
print(f"  Reset {reset_count} PDFs for reprocessing")

print(f"\n📝 Issues that were addressed:")
print(f"  - Address parsing (suite numbers): {analysis['address_parsing_reports']} reports")
print(f"  - Data shift (field misalignment): {analysis['data_shift_reports']} reports")
print(f"  - Both issues: {analysis['both_issues_reports']} reports")

print(f"\n🚀 Next Steps:")
print(f"1. Add donor_full_address column to database:")
print(f"   ALTER TABLE cf_donations ADD COLUMN IF NOT EXISTS donor_full_address TEXT;")
print(f"2. Run step3_concurrent.py to reprocess the {reset_count} PDFs")
print(f"3. The fixed parser will handle suite numbers correctly")
print(f"4. Monitor for shift issues - may need R scraper fixes")

print("\n" + "="*70)