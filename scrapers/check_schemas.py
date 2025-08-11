#!/usr/bin/env python3
"""
Check database schemas to understand relationships
"""

import os
import requests
import json

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

print("="*70)
print("DATABASE SCHEMA CHECK")
print("="*70)

# Check cf_donations table
print("\n1. CHECKING cf_donations TABLE:")
print("-" * 40)
url = f"{SUPABASE_URL}/rest/v1/cf_donations?limit=1"
response = requests.get(url, headers=headers)
if response.status_code == 200:
    data = response.json()
    if data:
        print("Fields:", json.dumps(list(data[0].keys()), indent=2))
        print("\nSample record:")
        for key, value in data[0].items():
            if key in ['donation_id', 'report_id', 'entity_id', 'pdf_id', 'donor_name', 'donation_date', 'donation_amt']:
                print(f"  {key}: {value}")
    else:
        print("No records found")
else:
    print(f"Error: {response.status_code}")

# Check for duplicates in donations
print("\n  Checking for duplicates...")
url = f"{SUPABASE_URL}/rest/v1/rpc/check_donation_duplicates"
check_query = """
SELECT 
    report_id,
    donor_name,
    donation_date,
    donation_amt,
    COUNT(*) as count
FROM cf_donations
GROUP BY report_id, donor_name, donation_date, donation_amt
HAVING COUNT(*) > 1
LIMIT 10
"""
# Note: This won't work via RPC, need to check differently

# Count donations
url = f"{SUPABASE_URL}/rest/v1/cf_donations?select=donation_id"
params = {"limit": "1", "order": "donation_id.desc"}
response = requests.get(url, headers=headers, params=params)
if response.status_code == 200:
    data = response.json()
    if data:
        # Get total count using a different approach
        response_count = requests.head(f"{SUPABASE_URL}/rest/v1/cf_donations", 
                                       headers={**headers, "Prefer": "count=exact"})
        if 'content-range' in response_count.headers:
            total = response_count.headers['content-range'].split('/')[1]
            print(f"  Total donation records: {total}")

# Check cf_reports table
print("\n2. CHECKING cf_reports TABLE:")
print("-" * 40)
url = f"{SUPABASE_URL}/rest/v1/cf_reports?limit=1"
response = requests.get(url, headers=headers)
if response.status_code == 200:
    data = response.json()
    if data:
        print("Fields:", json.dumps(list(data[0].keys()), indent=2))
        print("\nSample record:")
        for key, value in data[0].items():
            if key in ['report_id', 'pdf_id', 'entity_id', 'rpt_name', 'total_donations', 'donation_count']:
                print(f"  {key}: {value}")
    else:
        print("No records found")

# Count reports
response_count = requests.head(f"{SUPABASE_URL}/rest/v1/cf_reports", 
                               headers={**headers, "Prefer": "count=exact"})
if 'content-range' in response_count.headers:
    total = response_count.headers['content-range'].split('/')[1]
    print(f"  Total report records: {total}")

# Check cf_report_pdfs table
print("\n3. CHECKING cf_report_pdfs TABLE:")
print("-" * 40)
url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs?limit=1"
response = requests.get(url, headers=headers)
if response.status_code == 200:
    data = response.json()
    if data:
        print("Fields:", json.dumps(list(data[0].keys()), indent=2))
        print("\nSample record:")
        for key, value in data[0].items():
            if key in ['pdf_id', 'entity_id', 'pdf_url', 'csv_converted', 'report_name']:
                print(f"  {key}: {value}")

# Count PDFs by status
print("\n  PDF Processing Status:")
url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs?select=csv_converted"
params = {"csv_converted": "eq.true", "limit": "1"}
response = requests.head(url, headers={**headers, "Prefer": "count=exact"}, params=params)
if 'content-range' in response.headers:
    converted = response.headers['content-range'].split('/')[1]
    print(f"    Marked as converted: {converted}")

params = {"csv_converted": "eq.false", "limit": "1"}
response = requests.head(url, headers={**headers, "Prefer": "count=exact"}, params=params)
if 'content-range' in response.headers:
    not_converted = response.headers['content-range'].split('/')[1]
    print(f"    Not converted: {not_converted}")

# Check relationships
print("\n4. CHECKING RELATIONSHIPS:")
print("-" * 40)

# Get a sample of reports with their PDF info
url = f"{SUPABASE_URL}/rest/v1/cf_reports?limit=5&select=report_id,pdf_id,entity_id,donation_count"
response = requests.get(url, headers=headers)
if response.status_code == 200:
    reports = response.json()
    print(f"Sample reports with pdf_id references:")
    for r in reports[:3]:
        print(f"  Report {r['report_id']}: pdf_id={r['pdf_id']}, entity={r['entity_id']}, donations={r['donation_count']}")

# Check if there are PDFs marked as converted but with no reports
print("\n5. CHECKING FOR MISMATCHES:")
print("-" * 40)

# Get PDFs marked as converted
url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs?csv_converted=eq.true&limit=100&select=pdf_id,entity_id"
response = requests.get(url, headers=headers)
if response.status_code == 200:
    converted_pdfs = response.json()
    pdf_ids = [p['pdf_id'] for p in converted_pdfs]
    
    # Check if these have reports
    if pdf_ids:
        pdf_id_list = ",".join(str(id) for id in pdf_ids[:10])
        url = f"{SUPABASE_URL}/rest/v1/cf_reports?pdf_id=in.({pdf_id_list})&select=pdf_id"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            reports_with_pdfs = response.json()
            pdfs_with_reports = set(r['pdf_id'] for r in reports_with_pdfs)
            pdfs_without_reports = set(pdf_ids[:10]) - pdfs_with_reports
            print(f"  Sample of 10 converted PDFs:")
            print(f"    With reports: {len(pdfs_with_reports)}")
            print(f"    Without reports: {len(pdfs_without_reports)}")
            if pdfs_without_reports:
                print(f"    PDFs without reports: {list(pdfs_without_reports)[:5]}")

print("\n" + "="*70)