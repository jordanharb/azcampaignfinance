#!/usr/bin/env python3
"""
Identify ALL data quality issues:
1. Invalid state codes (address parsing issue)
2. Shifted data (field misalignment issue)
"""

import os
import requests
import json
import re
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
    'DC', 'PR', 'VI', 'GU', 'AS', 'MP',
    '', None
}

print("="*70)
print("IDENTIFYING ALL DATA QUALITY ISSUES")
print("="*70)

# Track all issues
affected_reports = set()
issue_details = {
    'address_parsing': {},  # report_id -> count
    'data_shift': {},       # report_id -> example
    'both_issues': set()
}

# ============================================================
# ISSUE 1: Invalid State Codes (Address Parsing)
# ============================================================
print("\n📍 ISSUE 1: Checking for invalid state codes...")

bad_states_by_report = defaultdict(int)
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
                report_id = donation['report_id']
                bad_states_by_report[report_id] += 1
                affected_reports.add(report_id)
        
        if len(batch) < batch_size:
            break
        offset += batch_size
    else:
        break

issue_details['address_parsing'] = dict(bad_states_by_report)
print(f"✅ Found {len(bad_states_by_report)} reports with address parsing issues")

# ============================================================
# ISSUE 2: Shifted Data (Field Misalignment)
# ============================================================
print("\n📊 ISSUE 2: Checking for shifted data in reports...")

offset = 0
shifted_reports = {}

while True:
    url = f"{SUPABASE_URL}/rest/v1/cf_reports"
    params = {
        "select": "report_id,pdf_id,entity_id,org_email,org_phone,org_address,org_treasurer",
        "order": "report_id",
        "limit": str(batch_size),
        "offset": str(offset)
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        batch = response.json()
        if not batch:
            break
        
        for report in batch:
            # Check for shifted patterns
            email = report.get('org_email', '')
            phone = report.get('org_phone', '')
            address = report.get('org_address', '')
            treasurer = report.get('org_treasurer', '')
            
            is_shifted = False
            shift_reason = []
            
            # Pattern 1: Email contains "Phone:"
            if email and 'Phone:' in email:
                is_shifted = True
                shift_reason.append(f"Email contains phone: '{email}'")
            
            # Pattern 2: Phone contains address (digits + street words)
            if phone and any(word in phone.lower() for word in ['street', 'st', 'ave', 'avenue', 'road', 'rd', 'drive', 'dr', 'court', 'ct', 'lane', 'ln', 'way', 'blvd']):
                is_shifted = True
                shift_reason.append(f"Phone contains address: '{phone}'")
            
            # Pattern 3: Address contains "Treasurer:"
            if address and 'Treasurer:' in address:
                is_shifted = True
                shift_reason.append(f"Address contains treasurer: '{address}'")
            
            # Pattern 4: Treasurer contains "Jurisdiction:"
            if treasurer and 'Jurisdiction:' in treasurer:
                is_shifted = True
                shift_reason.append(f"Treasurer contains jurisdiction: '{treasurer}'")
            
            if is_shifted:
                shifted_reports[report['report_id']] = {
                    'entity_id': report['entity_id'],
                    'pdf_id': report['pdf_id'],
                    'reasons': shift_reason
                }
                affected_reports.add(report['report_id'])
        
        if len(batch) < batch_size:
            break
        offset += batch_size
    else:
        break

issue_details['data_shift'] = shifted_reports
print(f"✅ Found {len(shifted_reports)} reports with shifted data")

# Find reports with BOTH issues
for report_id in bad_states_by_report:
    if report_id in shifted_reports:
        issue_details['both_issues'].add(report_id)

print(f"⚠️  Found {len(issue_details['both_issues'])} reports with BOTH issues")

# ============================================================
# Get PDF and Entity Information
# ============================================================
print("\n📋 Getting PDF information for all affected reports...")

pdf_ids_to_reset = set()
entities_affected = set()

if affected_reports:
    # Process in batches
    report_list = list(affected_reports)
    for i in range(0, len(report_list), 100):
        batch = report_list[i:i+100]
        id_list = ",".join(str(id) for id in batch)
        
        url = f"{SUPABASE_URL}/rest/v1/cf_reports"
        params = {
            "select": "report_id,pdf_id,entity_id,donation_count",
            "report_id": f"in.({id_list})"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            reports = response.json()
            for r in reports:
                if r['pdf_id']:
                    pdf_ids_to_reset.add(r['pdf_id'])
                if r['entity_id']:
                    entities_affected.add(r['entity_id'])

# ============================================================
# Summary
# ============================================================
print("\n" + "="*70)
print("📊 SUMMARY OF ALL ISSUES")
print("="*70)

print(f"\n1. ADDRESS PARSING ISSUES:")
print(f"   Reports affected: {len(issue_details['address_parsing'])}")
print(f"   Sample reports with bad states:")
for report_id, count in list(issue_details['address_parsing'].items())[:5]:
    print(f"     Report {report_id}: {count} bad donations")

print(f"\n2. DATA SHIFT ISSUES:")
print(f"   Reports affected: {len(issue_details['data_shift'])}")
print(f"   Sample reports with shifted data:")
for report_id, info in list(issue_details['data_shift'].items())[:5]:
    print(f"     Report {report_id} (Entity {info['entity_id']}):")
    for reason in info['reasons'][:2]:
        print(f"       - {reason}")

print(f"\n3. COMBINED IMPACT:")
print(f"   Total unique reports affected: {len(affected_reports)}")
print(f"   Reports with BOTH issues: {len(issue_details['both_issues'])}")
print(f"   PDFs to reprocess: {len(pdf_ids_to_reset)}")
print(f"   Entities affected: {len(entities_affected)}")

# Count total donations to be deleted
total_donations = 0
if affected_reports:
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    id_list = ",".join(str(id) for id in list(affected_reports)[:1000])
    params = {
        "select": "donation_id",
        "report_id": f"in.({id_list})",
        "limit": "1"
    }
    response = requests.head(url, headers={**headers, "Prefer": "count=exact"}, params=params)
    if 'content-range' in response.headers:
        total_donations = int(response.headers['content-range'].split('/')[1])

print(f"   Donations to be deleted: ~{total_donations}")

# Save analysis
output = {
    'total_affected_reports': len(affected_reports),
    'address_parsing_reports': len(issue_details['address_parsing']),
    'data_shift_reports': len(issue_details['data_shift']),
    'both_issues_reports': len(issue_details['both_issues']),
    'pdfs_to_reset': list(pdf_ids_to_reset),
    'entities_affected': list(entities_affected),
    'affected_report_ids': list(affected_reports),
    'address_issues': issue_details['address_parsing'],
    'shift_issues': issue_details['data_shift']
}

with open('all_issues_analysis.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\n💾 Saved detailed analysis to all_issues_analysis.json")

print("\n⚠️  CRITICAL NOTES:")
print("1. MUST delete ALL donations from affected reports (not just bad ones)")
print("2. This prevents duplicates when re-scraping")
print("3. Run complete_cleanup.py next to fix everything")

print("\n" + "="*70)