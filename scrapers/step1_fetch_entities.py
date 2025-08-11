#!/usr/bin/env python3
"""
Arizona Campaign Finance Scraper - Step 1: Fetch All Entities
FINAL VERSION with correct entity URL format

This script fetches all EntityIDs from the campaign finance API.
Using the discovered endpoint: /Reporting/GetNEWTableData/
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import argparse

# Configuration
OUTPUT_DIR = Path("campaign_finance_data")
OUTPUT_DIR.mkdir(exist_ok=True)
BASE_URL = "https://seethemoney.az.gov"

class AZCampaignFinanceAPI:
    """Interface to Arizona Campaign Finance API"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': f'{BASE_URL}/Reporting/Explore',
            'Origin': BASE_URL
        })
    
    def build_correct_entity_url(self, entity_id: int) -> str:
        """
        Build the correct entity URL with all required parameters
        Based on HAR analysis: includes JurisdictionId, Page, startYear, endYear, etc.
        """
        params = {
            "JurisdictionId": "0",
            "Page": "1",
            "startYear": "2002",
            "endYear": "2026",
            "IsLessActive": "false",
            "ShowOfficeHolder": "false",
            "View": "Detail",
            "Name": f"1~{entity_id}",
            "TablePage": "1",
            "TableLength": "100"
        }
        
        param_string = "|".join([f"{k}={v}" for k, v in params.items()])
        return f"{BASE_URL}/Reporting/Explore#{param_string}"
    
    def fetch_entities_page(self, start: int = 0, length: int = 100) -> Dict:
        """Fetch a page of entities from the API"""
        
        # Build URL with query parameters
        url_params = {
            'Page': '1',
            'startYear': '2002',  # Use wider date range
            'endYear': '2026',
            'JurisdictionId': '0',
            'TablePage': '1',
            'TableLength': str(length),
            'IsLessActive': 'false',
            'ShowOfficeHolder': 'false',
            'ChartName': '1'
        }
        
        endpoint = f"{BASE_URL}/Reporting/GetNEWTableData/"
        url = f"{endpoint}?{'&'.join([f'{k}={v}' for k, v in url_params.items()])}"
        
        # Build DataTables POST data
        post_data = {
            'draw': '1',
            'start': str(start),
            'length': str(length),
            'search[value]': '',
            'search[regex]': 'false',
            'order[0][column]': '0',
            'order[0][dir]': 'asc'
        }
        
        # Add column definitions (required by DataTables)
        columns = [
            'EntityLastName', 'CommitteeName', 'OfficeName', 'PartyName',
            'Income', 'Expense', 'CashBalance', 'IESupport', 'IEOpposition'
        ]
        
        for i, col in enumerate(columns):
            post_data[f'columns[{i}][data]'] = col
            post_data[f'columns[{i}][name]'] = ''
            post_data[f'columns[{i}][searchable]'] = 'true'
            post_data[f'columns[{i}][orderable]'] = 'true'
            post_data[f'columns[{i}][search][value]'] = ''
            post_data[f'columns[{i}][search][regex]'] = 'false'
        
        try:
            response = self.session.post(url, data=post_data, timeout=30)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
        
        return None
    
    def fetch_all_entities(self) -> List[Dict]:
        """Fetch all entities from the API using pagination"""
        all_entities = []
        start = 0
        length = 100  # Records per page
        
        while True:
            print(f"Fetching entities {start} to {start + length}...")
            
            data = self.fetch_entities_page(start, length)
            
            if not data or 'data' not in data:
                print("⚠️  No more data to fetch")
                break
            
            entities = data['data']
            if not entities:
                break
            
            all_entities.extend(entities)
            
            # Check if we have all records
            records_total = data.get('recordsTotal', 0)
            records_filtered = data.get('recordsFiltered', 0)
            
            print(f"  Found {len(entities)} entities in this batch")
            print(f"  Total records: {records_total}, Filtered: {records_filtered}")
            print(f"  Total collected so far: {len(all_entities)}")
            
            # Check if we've reached the end
            if start + length >= records_total:
                break
            
            # Prepare for next batch
            start += length
            time.sleep(0.5)  # Rate limiting
        
        return all_entities

def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Fetch all entities from Arizona Campaign Finance')
    parser.add_argument('--update-db', action='store_true', 
                       help='Update entities directly in Supabase database')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("ARIZONA CAMPAIGN FINANCE - STEP 1: FETCH ALL ENTITIES (FINAL)")
    print("="*70)
    
    api = AZCampaignFinanceAPI()
    
    # Fetch all entities
    print("\n📡 Fetching all entities from API...")
    entities = api.fetch_all_entities()
    
    if not entities:
        print("❌ No entities found")
        return
    
    print(f"\n✅ Successfully fetched {len(entities)} entities")
    
    # Extract key information with CORRECT entity URLs
    entity_summary = []
    for entity in entities:
        entity_id = entity.get('EntityID')
        entity_summary.append({
            'EntityID': entity_id,
            'EntityURL': api.build_correct_entity_url(entity_id) if entity_id else None,
            'EntityName': entity.get('EntityLastName', '').replace('<br>', ' ').replace('(', '').replace(')', ''),
            'CommitteeName': entity.get('CommitteeName', '').replace('<br>', ' '),
            'OfficeName': entity.get('OfficeName'),
            'PartyName': entity.get('PartyName'),
            'EntityTypeName': entity.get('EntityTypeName'),
            'CashBalance': entity.get('CashBalance'),
            'Income': entity.get('Income'),
            'Expense': entity.get('Expense')
        })
    
    # Save raw data
    raw_file = OUTPUT_DIR / "step1_all_entities_raw.json"
    with open(raw_file, 'w') as f:
        json.dump(entities, f, indent=2)
    print(f"\n💾 Saved raw data to {raw_file}")
    
    # Save summary with correct URLs
    summary_file = OUTPUT_DIR / "step1_entities_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(entity_summary, f, indent=2)
    print(f"💾 Saved summary to {summary_file}")
    
    # If update-db flag is set, update Supabase
    if args.update_db:
        print("\n🔄 Updating Supabase database...")
        from update_supabase import update_entities_in_supabase
        update_entities_in_supabase(entity_summary)
    
    # Statistics
    print("\n📈 Statistics:")
    print(f"  Total entities: {len(entities)}")
    
    # Count by entity type
    entity_types = {}
    for entity in entities:
        entity_type = entity.get('EntityTypeName', 'Unknown')
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
    
    print("\n  By Entity Type:")
    for entity_type, count in sorted(entity_types.items(), key=lambda x: x[1], reverse=True):
        print(f"    - {entity_type}: {count}")
    
    # Show sample entities with CORRECT URLs
    print("\n📋 Sample Entities (first 5):")
    for i, entity in enumerate(entity_summary[:5], 1):
        print(f"\n  {i}. EntityID: {entity['EntityID']}")
        print(f"     Committee: {entity['CommitteeName']}")
        print(f"     URL: {entity['EntityURL']}")
    
    # Save entity IDs for next step
    entity_ids = [entity.get('EntityID') for entity in entities if entity.get('EntityID')]
    entity_ids_file = OUTPUT_DIR / "step1_entity_ids.json"
    with open(entity_ids_file, 'w') as f:
        json.dump(entity_ids, f, indent=2)
    print(f"\n💾 Saved {len(entity_ids)} EntityIDs to {entity_ids_file}")
    
    print("\n" + "="*70)
    print("NEXT STEP:")
    print("Run step2_fetch_reports.py to get reports for all entities")
    print("="*70)

if __name__ == "__main__":
    main()