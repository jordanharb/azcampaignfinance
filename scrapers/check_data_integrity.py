#!/usr/bin/env python3
"""
Check data integrity between cf_reports and cf_donations tables
"""

import os
import requests

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

def check_integrity():
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    print("🔍 Checking data integrity...\n")
    
    # Count total donations
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {"select": "count", "limit": "1"}
    response = requests.get(url, headers=headers, params=params)
    total_donations = int(response.headers.get('Content-Range', '0-0/0').split('/')[-1])
    print(f"📊 Total donations: {total_donations:,}")
    
    # Count total reports
    url = f"{SUPABASE_URL}/rest/v1/cf_reports"
    params = {"select": "count", "limit": "1"}
    response = requests.get(url, headers=headers, params=params)
    total_reports = int(response.headers.get('Content-Range', '0-0/0').split('/')[-1])
    print(f"📊 Total reports: {total_reports:,}")
    
    # Count donations with NULL report_id
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {"select": "count", "report_id": "is.null", "limit": "1"}
    response = requests.get(url, headers=headers, params=params)
    null_report_donations = int(response.headers.get('Content-Range', '0-0/0').split('/')[-1])
    print(f"❌ Donations with NULL report_id: {null_report_donations:,}")
    
    # Count donations with valid report_id
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {"select": "count", "report_id": "not.is.null", "limit": "1"}
    response = requests.get(url, headers=headers, params=params)
    valid_report_donations = int(response.headers.get('Content-Range', '0-0/0').split('/')[-1])
    print(f"✅ Donations with valid report_id: {valid_report_donations:,}")
    
    # Get sample of entities with donations
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {"select": "entity_id", "limit": "100"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        donations = response.json()
        unique_entities = set(d['entity_id'] for d in donations if d.get('entity_id'))
        print(f"\n📍 Sample of entities with donations: {list(unique_entities)[:5]}")
    
    # Average donations per report (if reports exist)
    if total_reports > 0:
        avg_donations = total_donations / total_reports
        print(f"\n📈 Average donations per report: {avg_donations:.1f}")
        print("   (Should be reasonable, like 10-200 per report)")
    
    # Check how many PDFs have been marked as converted
    url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
    params = {"select": "count", "csv_converted": "eq.true", "limit": "1"}
    response = requests.get(url, headers=headers, params=params)
    converted_pdfs = int(response.headers.get('Content-Range', '0-0/0').split('/')[-1])
    print(f"\n📄 PDFs marked as converted: {converted_pdfs:,}")
    
    print("\n" + "="*50)
    if null_report_donations > 0 or avg_donations > 500:
        print("⚠️  DATA INTEGRITY ISSUE DETECTED!")
        print("Recommendations:")
        print("1. Clear both tables and re-run the R scraper")
        print("2. Make sure report_id is properly set when inserting donations")
    else:
        print("✅ Data integrity looks good!")

if __name__ == "__main__":
    check_integrity()