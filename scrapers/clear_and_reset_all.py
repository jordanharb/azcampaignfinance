#!/usr/bin/env python3
"""
Clear all donation/report data and reset PDFs to start fresh
"""

import os
import requests
import sys

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

print("\n" + "="*70)
print("⚠️  COMPLETE DATA RESET")
print("="*70)
print("\nThis will:")
print("1. DELETE all records from cf_donations")
print("2. DELETE all records from cf_reports")
print("3. Reset ALL cf_report_pdfs to unprocessed state")
print("\n" + "="*70)

response = input("\n⚠️  Are you SURE you want to delete all data? Type 'DELETE' to confirm: ")
if response != 'DELETE':
    print("Cancelled.")
    sys.exit(0)

print("\n🗑️  Clearing all donations...")
# Delete all donations
url = f"{SUPABASE_URL}/rest/v1/cf_donations"
response = requests.delete(url, headers=headers, params={"donation_id": "gte.0"})
if response.status_code in [200, 204]:
    print("✅ Deleted all donations")
else:
    print(f"❌ Failed to delete donations: {response.status_code}")
    print(response.text[:500])

print("\n🗑️  Clearing all reports...")
# Delete all reports
url = f"{SUPABASE_URL}/rest/v1/cf_reports"
response = requests.delete(url, headers=headers, params={"report_id": "gte.0"})
if response.status_code in [200, 204]:
    print("✅ Deleted all reports")
else:
    print(f"❌ Failed to delete reports: {response.status_code}")
    print(response.text[:500])

print("\n♻️  Resetting all PDFs to unprocessed...")
# Reset ALL PDFs
batch_size = 1000
offset = 0
total_reset = 0

while True:
    url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
    params = {
        "select": "pdf_id",
        "limit": str(batch_size),
        "offset": str(offset),
        "order": "pdf_id"
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        batch = response.json()
        if not batch:
            break
        
        pdf_ids = [p['pdf_id'] for p in batch]
        id_filter = ",".join(str(id) for id in pdf_ids)
        
        # Reset this batch
        params = {"pdf_id": f"in.({id_filter})"}
        update_data = {
            'csv_converted': False,
            'conversion_date': None
        }
        
        response = requests.patch(url, headers=headers, params=params, json=update_data)
        if response.status_code in [200, 204]:
            total_reset += len(pdf_ids)
            print(f"  Reset batch: {len(pdf_ids)} PDFs (total: {total_reset})")
        
        if len(batch) < batch_size:
            break
        offset += batch_size
    else:
        print(f"❌ Failed to fetch PDFs: {response.status_code}")
        break

print(f"\n✅ Reset {total_reset} PDFs to unprocessed state")

print("\n" + "="*70)
print("✅ RESET COMPLETE")
print("="*70)
print("\nYou can now run step3_concurrent.py to process PDFs fresh")
print("The improved script will:")
print("- Only skip /ReportFile/ URLs (unfiled reports)")
print("- Retry network failures 3 times")
print("- Not mark failures as processed")