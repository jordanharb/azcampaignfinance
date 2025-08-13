#!/usr/bin/env python3
"""
Fix script to fetch missing transactions for all entities
This will check each entity and fetch transactions if missing
"""

import json
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import sys

# Configuration
BASE_URL = "https://seethemoney.az.gov"

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

# Stats tracking
stats_lock = Lock()
stats = {
    'total': 0,
    'checked': 0,
    'already_has_transactions': 0,
    'fetched': 0,
    'uploaded': 0,
    'failed': 0,
    'no_transactions': 0,
    'start_time': None
}

class TransactionFixer:
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
        
        self.supabase_headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
    
    def get_all_entities(self) -> List[int]:
        """Get all entity IDs from the database"""
        url = f"{SUPABASE_URL}/rest/v1/cf_entities"
        params = {
            "select": "entity_id",
            "order": "entity_id"
        }
        
        all_entities = []
        offset = 0
        limit = 1000
        
        while True:
            params["offset"] = offset
            params["limit"] = limit
            
            response = requests.get(url, headers=self.supabase_headers, params=params)
            if response.status_code == 200:
                batch = response.json()
                if not batch:
                    break
                all_entities.extend([e['entity_id'] for e in batch])
                offset += limit
                
                # Show progress
                print(f"\rLoading entities... {len(all_entities)}", end="", flush=True)
            else:
                print(f"\nError fetching entities: {response.status_code}")
                break
        
        print(f"\nLoaded {len(all_entities)} entities")
        return all_entities
    
    def check_entity_has_transactions(self, entity_id: int) -> bool:
        """Check if an entity already has transactions in the database"""
        url = f"{SUPABASE_URL}/rest/v1/cf_transactions"
        params = {
            "select": "transaction_id",
            "entity_id": f"eq.{entity_id}",
            "limit": "1"
        }
        
        try:
            response = requests.get(url, headers=self.supabase_headers, params=params)
            if response.status_code == 200:
                transactions = response.json()
                return len(transactions) > 0
            return False
        except:
            return False
    
    def fetch_entity_transactions(self, entity_id: int) -> Optional[List[Dict]]:
        """Fetch transactions for a single entity"""
        try:
            # Build the request
            url_params = {
                'Page': '24',
                'startYear': '2002',
                'endYear': '2026',
                'JurisdictionId': '0',
                'TablePage': '1',
                'TableLength': '10000',
                'Name': f'1~{entity_id}',
                'entityId': str(entity_id),
                'ChartName': '24',
                'IsLessActive': 'false',
                'ShowOfficeHolder': 'false'
            }
            
            endpoint = f"{BASE_URL}/Reporting/GetNEWDetailedTableData"
            url = f"{endpoint}?{'&'.join([f'{k}={v}' for k, v in url_params.items()])}"
            
            post_data = {
                'draw': '1',
                'start': '0',
                'length': '10000',
                'search[value]': '',
                'search[regex]': 'false',
                'order[0][column]': '2',
                'order[0][dir]': 'desc'
            }
            
            columns = ['', 'TransactionId', 'TransactionDate', 'Amount', 'TransactionType', 'ReceivedFromOrPaidTo']
            for i, col in enumerate(columns):
                post_data[f'columns[{i}][data]'] = col
                post_data[f'columns[{i}][name]'] = ''
                post_data[f'columns[{i}][searchable]'] = 'true' if i > 0 else 'false'
                post_data[f'columns[{i}][orderable]'] = 'true' if i > 0 else 'false'
                post_data[f'columns[{i}][search][value]'] = ''
                post_data[f'columns[{i}][search][regex]'] = 'false'
            
            response = self.session.post(url, data=post_data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                transactions = result.get('data', [])
                return transactions
            else:
                return None
                
        except Exception as e:
            print(f"\nError fetching transactions for {entity_id}: {e}")
            return None
    
    def transform_transactions(self, entity_id: int, raw_transactions: List[Dict]) -> List[Dict]:
        """Transform raw transactions to database format"""
        transformed = []
        
        for tx in raw_transactions:
            # Parse the date
            date_str = tx.get('TransactionDate', '')
            if date_str and '/Date(' in date_str:
                timestamp = int(date_str.replace('/Date(', '').replace(')/', '')) / 1000
                transaction_date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            else:
                transaction_date = None
            
            # Parse the From/To field
            from_to = tx.get('ReceivedFromOrPaidTo', '')
            parts = from_to.split('|') if from_to else []
            
            # Year-month parsing
            year_month_str = tx.get('TransactionDateYearMonth', '')
            if year_month_str and '/Date(' in year_month_str:
                ym_timestamp = int(year_month_str.replace('/Date(', '').replace(')/', '')) / 1000
                transaction_date_year_month = datetime.fromtimestamp(ym_timestamp).strftime('%Y-%m-01')
            else:
                transaction_date_year_month = None
            
            transformed.append({
                'public_transaction_id': tx.get('PublicTransactionId'),
                'transaction_id': tx.get('TransactionId'),
                'entity_id': entity_id,
                'transaction_entity_id': tx.get('TransactionNameId', -1),
                'committee_id': tx.get('CommitteeId', entity_id),
                'committee_unique_id': tx.get('CommitteeUniqueId'),
                'committee_name': tx.get('CommitteeName'),
                'transaction_date': transaction_date,
                'transaction_date_timestamp': transaction_date + 'T00:00:00' if transaction_date else None,
                'transaction_date_year': datetime.strptime(transaction_date, '%Y-%m-%d').year if transaction_date else None,
                'transaction_date_year_month': transaction_date_year_month,
                'transaction_type_id': tx.get('TransactionTypeId'),
                'transaction_type': tx.get('TransactionType'),
                'transaction_type_disposition_id': tx.get('TransactionTypeDispositionId'),
                'amount': float(tx.get('Amount', 0)),
                'transaction_name_id': tx.get('TransactionNameId', -1),
                'transaction_name_group_id': tx.get('TransactionNameGroupId', -1),
                'transaction_entity_type_id': tx.get('TransactionEntityTypeId', 1),
                'transaction_first_name': tx.get('TransactionFirstName'),
                'transaction_middle_name': tx.get('TransactionMiddleName'),
                'transaction_last_name': tx.get('TransactionLastName'),
                'received_from_or_paid_to': from_to,
                'transaction_occupation': tx.get('TransactionOccupation'),
                'transaction_employer': tx.get('TransactionEmployer'),
                'transaction_city': tx.get('TransactionCity'),
                'transaction_state': tx.get('TransactionState'),
                'transaction_zip_code': tx.get('TransactionZipCode'),
                'entity_type_id': tx.get('EntityTypeId'),
                'entity_description': tx.get('EntityDescription'),
                'transaction_group_number': tx.get('TransactionGroupNumber'),
                'transaction_group_name': tx.get('TransactionGroupName'),
                'transaction_group_color': tx.get('TransactionGroupColor'),
                'committee_group_number': tx.get('CommitteeGroupNumber'),
                'committee_group_name': tx.get('CommitteeGroupName'),
                'committee_group_color': tx.get('CommitteeGroupColor'),
                'subject_committee_id': tx.get('SubjectCommitteeId'),
                'subject_committee_name': tx.get('SubjectCommitteeName'),
                'subject_committee_name_id': tx.get('SubjectCommitteeNameId'),
                'subject_group_number': tx.get('SubjectGroupNumber'),
                'is_for_benefit': tx.get('IsForBenefit'),
                'benefited_opposed': tx.get('BenefitedOpposed'),
                'candidate_cycle_id': tx.get('CandidateCycleId'),
                'candidate_office_type_id': tx.get('CandidateOfficeTypeId'),
                'candidate_office_id': tx.get('CandidateOfficeId'),
                'candidate_party_id': tx.get('CandidatePartyId'),
                'candidate_first_name': tx.get('CandidateFirstName'),
                'candidate_middle_name': tx.get('CandidateMiddleName'),
                'candidate_last_name': tx.get('CandidateLastName'),
                'ballot_measure_id': tx.get('BallotMeasureId'),
                'ballot_measure_number': tx.get('BallotMeasureNumber'),
                'jurisdiction_id': tx.get('JurisdictionId', 0),
                'jurisdiction_name': tx.get('JurisdictionName'),
                'report_id': tx.get('ReportId'),
                'memo': tx.get('Memo')
            })
        
        return transformed
    
    def ensure_transaction_entities_exist(self, transactions: List[Dict]) -> bool:
        """Ensure all transaction entities exist before uploading transactions"""
        # Extract unique transaction entity IDs
        entity_ids = set()
        entity_data = {}
        
        for tx in transactions:
            entity_id = tx.get('transaction_entity_id')
            if entity_id and entity_id != -1:
                entity_ids.add(entity_id)
                # Store the entity data for potential insertion
                if entity_id not in entity_data:
                    # Parse the received_from_or_paid_to field for better name
                    from_to = tx.get('received_from_or_paid_to', '')
                    parts = from_to.split('|') if from_to else []
                    
                    # Get the best name - use the formatted name from the end of the array if available
                    entity_name = parts[-1] if parts and len(parts) > 9 else tx.get('transaction_last_name', '')
                    
                    entity_data[entity_id] = {
                        'entity_id': entity_id,
                        'entity_name': entity_name,
                        'first_name': tx.get('transaction_first_name'),
                        'middle_name': tx.get('transaction_middle_name'),
                        'last_name': tx.get('transaction_last_name'),
                        'entity_type_id': tx.get('transaction_entity_type_id', 1),
                        'entity_type_description': tx.get('entity_description'),
                        'group_number': tx.get('transaction_group_number', 7),
                        'group_id': tx.get('transaction_name_group_id', entity_id),
                        # These will be populated later when we have full transaction history
                        'total_contributions': 0.0,
                        'total_expenditures': 0.0,
                        'transaction_count': 0,
                        'unique_committees_count': 0,
                        'first_transaction_date': None,
                        'last_transaction_date': None
                    }
        
        if not entity_ids:
            return True
        
        # Check which entities already exist - batch to avoid URI too long errors
        url = f"{SUPABASE_URL}/rest/v1/cf_transaction_entities"
        existing = set()
        
        # Process in batches of 50 to avoid URI length limits
        entity_list = list(entity_ids)
        batch_size = 50
        
        try:
            for i in range(0, len(entity_list), batch_size):
                batch_ids = entity_list[i:i+batch_size]
                params = {
                    "select": "entity_id",
                    "entity_id": f"in.({','.join(map(str, batch_ids))})"
                }
                
                response = requests.get(url, headers=self.supabase_headers, params=params)
                if response.status_code == 200:
                    existing.update(e['entity_id'] for e in response.json())
                elif response.status_code == 414:
                    # URI too long, use smaller batch
                    print(f"\nURI too long, reducing batch size")
                    # Process one by one if needed
                    for eid in batch_ids:
                        params = {"select": "entity_id", "entity_id": f"eq.{eid}"}
                        response = requests.get(url, headers=self.supabase_headers, params=params)
                        if response.status_code == 200 and response.json():
                            existing.add(eid)
                else:
                    print(f"\nError checking transaction entities: {response.status_code}")
                    return False
            
            # Find missing entities
            missing = entity_ids - existing
            
            if missing:
                # Insert missing entities in batches
                missing_entities = [entity_data[eid] for eid in missing if eid in entity_data]
                
                if missing_entities:
                    headers = self.supabase_headers.copy()
                    headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
                    
                    # Insert in batches of 100
                    for i in range(0, len(missing_entities), 100):
                        batch = missing_entities[i:i+100]
                        response = requests.post(
                            url,
                            headers=headers,
                            json=batch
                        )
                        
                        if response.status_code not in [200, 201, 204]:
                            print(f"\nError creating transaction entities: {response.status_code} - {response.text[:200]}")
                            return False
            
            return True
                
        except Exception as e:
            print(f"\nError with transaction entities: {e}")
            return False
    
    def upload_transactions(self, transactions: List[Dict]) -> bool:
        """Upload transactions to Supabase with retry logic for deadlocks"""
        if not transactions:
            return True
        
        # First ensure all transaction entities exist
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if not self.ensure_transaction_entities_exist(transactions):
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    print("\nFailed to ensure transaction entities exist")
                    return False
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return False
        
        url = f"{SUPABASE_URL}/rest/v1/cf_transactions"
        
        # Upload in batches of 500
        batch_size = 500
        for i in range(0, len(transactions), batch_size):
            batch = transactions[i:i+batch_size]
            
            # Retry logic for deadlocks
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        url,
                        headers=self.supabase_headers,
                        json=batch
                    )
                    
                    if response.status_code not in [200, 201, 204]:
                        # Check for deadlock error
                        if '40P01' in response.text:
                            if attempt < max_retries - 1:
                                time.sleep(2 ** attempt)  # Exponential backoff
                                continue
                        print(f"\nError uploading batch: {response.status_code} - {response.text[:200]}")
                        return False
                    
                    # Success, break retry loop
                    break
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    print(f"\nError uploading transactions: {e}")
                    return False
        
        return True
    
    def process_entity(self, entity_id: int) -> str:
        """Process a single entity"""
        # Check if already has transactions
        if self.check_entity_has_transactions(entity_id):
            with stats_lock:
                stats['already_has_transactions'] += 1
            return f"skip:{entity_id}"
        
        # Fetch transactions
        raw_transactions = self.fetch_entity_transactions(entity_id)
        
        if raw_transactions is None:
            with stats_lock:
                stats['failed'] += 1
            return f"fail:{entity_id}"
        
        if not raw_transactions:
            with stats_lock:
                stats['no_transactions'] += 1
            return f"none:{entity_id}"
        
        # Transform and upload
        transformed = self.transform_transactions(entity_id, raw_transactions)
        
        if self.upload_transactions(transformed):
            with stats_lock:
                stats['fetched'] += 1
                stats['uploaded'] += len(transformed)
            return f"success:{entity_id}:{len(transformed)}"
        else:
            with stats_lock:
                stats['failed'] += 1
            return f"fail:{entity_id}"

def print_progress():
    """Print progress statistics"""
    with stats_lock:
        elapsed = time.time() - stats['start_time']
        rate = stats['checked'] / elapsed if elapsed > 0 else 0
        
        print(f"\r[{stats['checked']}/{stats['total']}] "
              f"Skip: {stats['already_has_transactions']} | "
              f"Fetched: {stats['fetched']} | "
              f"No TX: {stats['no_transactions']} | "
              f"Failed: {stats['failed']} | "
              f"Uploaded: {stats['uploaded']} TX | "
              f"Rate: {rate:.1f}/s", end="", flush=True)

def main():
    fixer = TransactionFixer()
    
    # Get all entities
    print("Loading all entities from database...")
    all_entities = fixer.get_all_entities()
    
    if not all_entities:
        print("No entities found!")
        return
    
    stats['total'] = len(all_entities)
    stats['start_time'] = time.time()
    
    # Process in parallel with REDUCED workers to avoid deadlocks
    MAX_WORKERS = 3  # Reduced from 10 to avoid database deadlocks
    
    print(f"\nProcessing {len(all_entities)} entities with {MAX_WORKERS} workers...")
    print("This will fetch transactions for entities that don't have any yet.\n")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        
        for entity_id in all_entities:
            future = executor.submit(fixer.process_entity, entity_id)
            futures.append((entity_id, future))
        
        for entity_id, future in futures:
            try:
                result = future.result(timeout=60)
                with stats_lock:
                    stats['checked'] += 1
                
                # Print detailed info for successes
                if result.startswith("success:"):
                    parts = result.split(":")
                    count = parts[2] if len(parts) > 2 else "0"
                    print(f"\n✅ Entity {entity_id}: Uploaded {count} transactions")
                
                # Update progress
                if stats['checked'] % 10 == 0:
                    print_progress()
                    
            except Exception as e:
                with stats_lock:
                    stats['checked'] += 1
                    stats['failed'] += 1
                print(f"\n❌ Entity {entity_id}: {e}")
    
    # Final stats
    print("\n\n" + "="*50)
    print("FINAL STATISTICS")
    print("="*50)
    elapsed = time.time() - stats['start_time']
    print(f"Total entities: {stats['total']}")
    print(f"Already had transactions: {stats['already_has_transactions']}")
    print(f"Successfully fetched: {stats['fetched']}")
    print(f"No transactions found: {stats['no_transactions']}")
    print(f"Failed: {stats['failed']}")
    print(f"Total transactions uploaded: {stats['uploaded']}")
    print(f"Time elapsed: {elapsed:.1f} seconds")
    print(f"Average rate: {stats['total']/elapsed:.1f} entities/second")

if __name__ == "__main__":
    main()