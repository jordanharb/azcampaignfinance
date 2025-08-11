#!/usr/bin/env python3
"""
Analyze duplicates and processing status
"""

import os
import requests
import json
from collections import defaultdict

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

print("="*70)
print("DUPLICATE AND PROCESSING ANALYSIS")
print("="*70)

# 1. Check for duplicate reports (same pdf_id)
print("\n1. CHECKING FOR DUPLICATE REPORTS:")
print("-" * 40)

all_reports = []
offset = 0
batch_size = 1000

while True:
    url = f"{SUPABASE_URL}/rest/v1/cf_reports"
    params = {
        "select": "report_id,pdf_id,entity_id,donation_count",
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
        break

# Find duplicate pdf_ids in reports
pdf_id_counts = defaultdict(list)
for report in all_reports:
    pdf_id_counts[report['pdf_id']].append(report['report_id'])

duplicate_pdfs = {k: v for k, v in pdf_id_counts.items() if len(v) > 1}
print(f"Total reports: {len(all_reports)}")
print(f"Duplicate PDF IDs: {len(duplicate_pdfs)}")
if duplicate_pdfs:
    for pdf_id, report_ids in list(duplicate_pdfs.items())[:5]:
        print(f"  PDF {pdf_id}: has {len(report_ids)} reports: {report_ids}")

# 2. Check for duplicate donations within same report
print("\n2. CHECKING FOR DUPLICATE DONATIONS:")
print("-" * 40)

# Get a sample of donations to check for exact duplicates
url = f"{SUPABASE_URL}/rest/v1/cf_donations"
params = {
    "select": "donation_id,report_id,donor_name,donation_date,donation_amt",
    "order": "report_id,donor_name,donation_date",
    "limit": "5000"
}
response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    donations = response.json()
    
    # Group by report and check for duplicates
    report_donations = defaultdict(list)
    for d in donations:
        key = (d['report_id'], d['donor_name'], d['donation_date'], d['donation_amt'])
        report_donations[key].append(d['donation_id'])
    
    duplicate_donations = {k: v for k, v in report_donations.items() if len(v) > 1}
    print(f"Sample of 5000 donations checked")
    print(f"Duplicate donations found: {len(duplicate_donations)}")
    if duplicate_donations:
        for key, donation_ids in list(duplicate_donations.items())[:3]:
            report_id, donor, date, amt = key
            print(f"  Report {report_id}: {donor} on {date} for ${amt}")
            print(f"    Donation IDs: {donation_ids}")

# 3. Check which PDFs actually have data
print("\n3. CHECKING WHICH PDFs HAVE ACTUAL DATA:")
print("-" * 40)

# Get all PDFs marked as converted
url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
params = {
    "select": "pdf_id,entity_id,pdf_url",
    "csv_converted": "eq.true",
    "limit": "1000"
}
response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    converted_pdfs = response.json()
    print(f"PDFs marked as converted: {len(converted_pdfs)}")
    
    # Check which have reports
    pdf_ids = [p['pdf_id'] for p in converted_pdfs]
    pdf_id_list = ",".join(str(id) for id in pdf_ids)
    
    url = f"{SUPABASE_URL}/rest/v1/cf_reports"
    params = {
        "select": "pdf_id,donation_count",
        "pdf_id": f"in.({pdf_id_list})"
    }
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        reports = response.json()
        pdfs_with_reports = set(r['pdf_id'] for r in reports)
        pdfs_with_donations = set(r['pdf_id'] for r in reports if r['donation_count'] > 0)
        
        print(f"  Have reports: {len(pdfs_with_reports)}")
        print(f"  Have donations: {len(pdfs_with_donations)}")
        print(f"  Marked but no reports: {len(pdf_ids) - len(pdfs_with_reports)}")
        print(f"  Have reports but no donations: {len(pdfs_with_reports) - len(pdfs_with_donations)}")

# 4. Find PDFs that should be marked as processed
print("\n4. FINDING PDFs THAT SHOULD BE MARKED AS PROCESSED:")
print("-" * 40)

# Get all reports with their pdf_ids
url = f"{SUPABASE_URL}/rest/v1/cf_reports"
params = {
    "select": "pdf_id",
    "limit": "10000"
}
response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    reports = response.json()
    processed_pdf_ids = set(r['pdf_id'] for r in reports if r['pdf_id'])
    print(f"PDFs with reports (should be marked as processed): {len(processed_pdf_ids)}")
    
    # Check how many of these are NOT marked as converted
    pdf_id_list = ",".join(str(id) for id in list(processed_pdf_ids)[:1000])
    url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
    params = {
        "select": "pdf_id,csv_converted",
        "pdf_id": f"in.({pdf_id_list})"
    }
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        pdf_statuses = response.json()
        not_marked = [p['pdf_id'] for p in pdf_statuses if not p['csv_converted']]
        print(f"  Not marked as converted but have reports: {len(not_marked)}")
        if not_marked:
            print(f"    Sample: {not_marked[:5]}")

print("\n" + "="*70)