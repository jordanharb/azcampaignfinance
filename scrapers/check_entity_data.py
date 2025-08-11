#!/usr/bin/env python3
"""
Check what data exists for a specific entity in Supabase
"""

import os
import requests
import json
import argparse

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

def check_entity(entity_id):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"\n🔍 Checking entity {entity_id}...")
    
    # Check if entity exists
    url = f"{SUPABASE_URL}/rest/v1/cf_entities"
    params = {"entity_id": f"eq.{entity_id}"}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        entities = response.json()
        if entities:
            entity = entities[0]
            print(f"\n✅ Entity found:")
            print(f"  Committee: {entity.get('primary_committee_name', 'N/A')}")
            print(f"  Candidate: {entity.get('primary_candidate_name', 'N/A')}")
            print(f"  Latest Activity: {entity.get('latest_activity', 'N/A')}")
        else:
            print(f"❌ Entity {entity_id} not found in cf_entities table")
            return
    
    # Check reports for this entity
    url = f"{SUPABASE_URL}/rest/v1/cf_reports"
    params = {"entity_id": f"eq.{entity_id}"}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        reports = response.json()
        print(f"\n📊 Found {len(reports)} reports for this entity")
        
        if reports:
            for i, report in enumerate(reports[:5], 1):
                print(f"  {i}. Report ID: {report.get('report_id')}")
                print(f"     Name: {report.get('rpt_name', 'N/A')}")
                print(f"     PDF ID: {report.get('pdf_id', 'None')}")
    
    # Check PDF records
    url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
    params = {"entity_id": f"eq.{entity_id}"}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        pdfs = response.json()
        print(f"\n📄 Found {len(pdfs)} PDF records for this entity")
        
        if pdfs:
            for i, pdf in enumerate(pdfs[:5], 1):
                print(f"  {i}. PDF ID: {pdf.get('pdf_id')}")
                print(f"     URL: {pdf.get('pdf_url', 'N/A')[:50]}...")
                print(f"     Converted: {pdf.get('csv_converted', False)}")
    
    # Check if we have any donations for this entity
    url = f"{SUPABASE_URL}/rest/v1/cf_donations"
    params = {"entity_id": f"eq.{entity_id}", "limit": "5"}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        donations = response.json()
        print(f"\n💰 Found {len(donations)} donations for this entity (showing up to 5)")
        
        if donations:
            for i, donation in enumerate(donations, 1):
                print(f"  {i}. Donor: {donation.get('donor_name', 'N/A')}")
                print(f"     Amount: ${donation.get('donation_amt', 0)}")
                print(f"     Date: {donation.get('donation_date', 'N/A')}")

def main():
    parser = argparse.ArgumentParser(description='Check entity data in Supabase')
    parser.add_argument('--entity', type=int, required=True,
                       help='Entity ID to check')
    args = parser.parse_args()
    
    check_entity(args.entity)

if __name__ == "__main__":
    main()