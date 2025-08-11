#!/usr/bin/env python3
"""
Arizona Campaign Finance Transactions Scraper - CONCURRENT VERSION
Fetches transaction data with multiple workers and progress tracking
Automatically uploads to Supabase periodically
"""

import json
import time
import requests
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Thread
import signal
import sys
import random
from queue import Queue
import atexit

# Configuration
OUTPUT_DIR = Path("campaign_finance_transactions")
OUTPUT_DIR.mkdir(exist_ok=True)
BASE_URL = "https://seethemoney.az.gov"

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

# Upload configuration
UPLOAD_BATCH_SIZE = 100  # Upload after every N entities processed
UPLOAD_INTERVAL_SECONDS = 60  # Also upload every N seconds

# Global stats for tracking
stats_lock = Lock()
global_stats = {
    'total': 0,
    'success': 0,
    'failed': 0,
    'skipped': 0,
    'transactions_found': 0,
    'start_time': None,
    'entities_uploaded': 0,
    'transactions_uploaded': 0,
    'last_upload_time': None
}

# Global collections for deduplication
unique_entities_lock = Lock()
unique_transaction_entities = {}
transaction_types = {}
transaction_groups = {}
entity_types = {}

# Queue for transactions to upload
upload_queue = Queue()
pending_transactions = []
pending_transactions_lock = Lock()

# Flag for graceful shutdown
shutdown_requested = False
upload_thread = None

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_requested
    print("\n\n⚠️  Shutdown requested. Uploading remaining data and cleaning up...")
    shutdown_requested = True
    # Final upload before exit
    upload_pending_data(force=True)

signal.signal(signal.SIGINT, signal_handler)

def cleanup_on_exit():
    """Ensure data is uploaded even on unexpected exit"""
    global shutdown_requested
    shutdown_requested = True
    upload_pending_data(force=True)

atexit.register(cleanup_on_exit)

class TransactionScraper:
    """Scraper for a single worker"""
    
    def __init__(self, worker_id: int = 0):
        self.worker_id = worker_id
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
    
    def check_entity_already_scraped(self, entity_id: int) -> bool:
        """Check if an entity has already been scraped"""
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
    
    def fetch_entity_transactions(self, entity_id: int, max_retries: int = 1) -> Optional[Dict]:
        """Fetch transactions for a single entity with retry logic"""
        
        for attempt in range(max_retries):
            try:
                # Build the request using the CORRECT endpoint
                url_params = {
                    'Page': '24',
                    'startYear': '2002',
                    'endYear': '2026',
                    'JurisdictionId': '0',
                    'TablePage': '1',
                    'TableLength': '10000',  # Get many at once
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
                    
                    # Extract data from DataTables format
                    transactions = result.get('data', [])
                    total_records = result.get('recordsTotal', 0)
                    
                    return {
                        'entity_id': entity_id,
                        'transactions': transactions,
                        'total_records': total_records,
                        'count': len(transactions)
                    }
                elif response.status_code == 404:
                    return {
                        'entity_id': entity_id,
                        'transactions': [],
                        'aggregations': {},
                        'count': 0
                    }
                else:
                    # Log the error for debugging - ALWAYS on last attempt
                    if attempt == max_retries - 1:
                        print(f"\n⚠️ Error {response.status_code} for entity {entity_id}: {response.text[:200]}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    print(f"\n⚠️ Timeout for entity {entity_id}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"\n⚠️ Exception for entity {entity_id}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
        
        return None
    
    def extract_unique_entities(self, transactions: List[Dict]) -> Dict:
        """Extract unique entities from transactions"""
        local_entities = {}
        
        for trans in transactions:
            # From entity
            from_id = trans.get('FromEntityId')
            if from_id and from_id not in local_entities:
                local_entities[from_id] = {
                    'entity_id': from_id,
                    'entity_name': trans.get('FromName'),
                    'entity_type': trans.get('FromType'),
                    'entity_type_id': trans.get('FromTypeId')
                }
            
            # To entity
            to_id = trans.get('ToEntityId')
            if to_id and to_id not in local_entities:
                local_entities[to_id] = {
                    'entity_id': to_id,
                    'entity_name': trans.get('ToName'),
                    'entity_type': trans.get('ToType'),
                    'entity_type_id': trans.get('ToTypeId')
                }
        
        return local_entities
    
    def parse_received_from_paid_to(self, value: str) -> Optional[Dict]:
        """Parse the ReceivedFromOrPaidTo field"""
        if not value or '|' not in value:
            return None
        
        parts = value.split('|')
        if len(parts) < 10:
            return None
        
        try:
            entity_id = int(parts[0]) if parts[0] and parts[0] != '-1' else -1
        except:
            entity_id = -1
        
        return {
            'entity_id': entity_id,
            'last_name': parts[1] or None,
            'first_name': parts[2] or None,
            'middle_name': parts[3] or None,
            'entity_type_id': int(parts[4]) if parts[4] else None,
            'group_number': int(parts[5]) if parts[5] else None,
            'group_id': int(parts[6]) if parts[6] else None,
            'full_name': parts[9] if len(parts) > 9 else None
        }
    
    def parse_date(self, date_str: str) -> Optional[str]:
        """Convert /Date(timestamp)/ format to ISO format"""
        if date_str and '/Date(' in str(date_str):
            try:
                timestamp = int(date_str.replace('/Date(', '').replace(')/', '')) / 1000
                return datetime.fromtimestamp(timestamp).isoformat()
            except:
                return None
        return None
    
    def process_transactions(self, data: Dict) -> Dict:
        """Process transactions and extract entities"""
        entity_id = data['entity_id']
        transactions = data['transactions']
        
        result = {
            'entity_id': entity_id,
            'transaction_count': len(transactions),
            'entities_found': 0,
            'success': True
        }
        
        if not transactions:
            result['success'] = False
            return result
        
        # Extract unique entities from transactions
        local_entities = self.extract_unique_entities(transactions)
        
        # Merge with global collections
        with unique_entities_lock:
            for ent_id, entity_data in local_entities.items():
                if ent_id not in unique_transaction_entities:
                    unique_transaction_entities[ent_id] = entity_data
            
            # Also track transaction types and groups
            for trans in transactions:
                type_id = trans.get('TransactionTypeId')
                if type_id and type_id not in transaction_types:
                    transaction_types[type_id] = trans.get('TransactionType')
                
                group_id = trans.get('TransactionGroupId')
                if group_id and group_id not in transaction_groups:
                    transaction_groups[group_id] = trans.get('TransactionGroup')
        
        result['entities_found'] = len(local_entities)
        
        # Queue transactions for upload
        if transactions:
            # Transform for database
            db_transactions = []
            for trans in transactions:
                db_trans = {
                    'transaction_id': trans.get('TransactionId'),
                    'entity_id': entity_id,
                    'from_entity_id': trans.get('FromEntityId'),
                    'to_entity_id': trans.get('ToEntityId'),
                    'transaction_date': trans.get('Date'),
                    'amount': trans.get('Amount'),
                    'transaction_type': trans.get('TransactionType'),
                    'transaction_type_id': trans.get('TransactionTypeId'),
                    'transaction_group': trans.get('TransactionGroup'),
                    'transaction_group_id': trans.get('TransactionGroupId'),
                    'from_name': trans.get('FromName'),
                    'to_name': trans.get('ToName'),
                    'from_type': trans.get('FromType'),
                    'to_type': trans.get('ToType'),
                    'memo': trans.get('Memo'),
                    'report_link': trans.get('ReportLink'),
                    'import_date': datetime.now().isoformat()
                }
                db_transactions.append(db_trans)
            
            # Add to pending queue
            with pending_transactions_lock:
                pending_transactions.extend(db_transactions)
            
            # Also save to file for backup
            output_file = OUTPUT_DIR / f"entity_{entity_id}_transactions.json"
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
        
        return result

def fetch_entity_ids_from_supabase(limit: Optional[int] = None, skip_scraped: bool = True) -> List[int]:
    """Fetch entity IDs from Supabase database with pagination"""
    print("📥 Fetching entity IDs from Supabase...")
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    all_entities = []
    offset = 0
    batch_size = 1000
    
    while True:
        url = f"{SUPABASE_URL}/rest/v1/cf_entities"
        params = {
            "select": "entity_id",
            "order": "entity_id",
            "limit": str(batch_size),
            "offset": str(offset)
        }
        
        if limit and len(all_entities) >= limit:
            all_entities = all_entities[:limit]
            break
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                batch = response.json()
                entity_ids = [e['entity_id'] for e in batch]
                all_entities.extend(entity_ids)
                
                if len(batch) < batch_size:
                    break
                    
                offset += batch_size
                if len(all_entities) > 1000:
                    print(f"  Fetched {len(all_entities)} entity IDs so far...")
            else:
                print(f"❌ Failed to fetch entities: {response.status_code}")
                break
        except Exception as e:
            print(f"❌ Error fetching entities: {e}")
            break
    
    if limit:
        all_entities = all_entities[:limit]
    
    print(f"✅ Found {len(all_entities)} total entities")
    
    # Filter out already scraped entities if requested
    if skip_scraped:
        print("🔍 Fetching already scraped entities (this is fast!)...")
        
        # Get all unique entity_ids that have transactions in ONE query
        scraped_entities = set()
        offset = 0
        
        while True:
            url = f"{SUPABASE_URL}/rest/v1/cf_transactions"
            params = {
                "select": "entity_id",
                "order": "entity_id",
                "limit": "1000",
                "offset": str(offset)
            }
            
            try:
                response = requests.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    batch = response.json()
                    if not batch:
                        break
                    
                    # Add to set (automatically deduplicates)
                    for record in batch:
                        scraped_entities.add(record['entity_id'])
                    
                    if len(batch) < 1000:
                        break
                    offset += 1000
                else:
                    print(f"  Warning: Could not fetch scraped entities: {response.status_code}")
                    break
            except Exception as e:
                print(f"  Warning: Error fetching scraped entities: {e}")
                break
        
        # Filter out scraped entities
        filtered_entities = [e for e in all_entities if e not in scraped_entities]
        
        print(f"✅ {len(filtered_entities)} entities need scraping ({len(scraped_entities)} already done)")
        return filtered_entities
    
    return all_entities

def worker_process_entity(worker_id: int, entity_id: int) -> Dict:
    """Worker function to process a single entity"""
    scraper = TransactionScraper(worker_id)
    
    # Fetch transactions
    data = scraper.fetch_entity_transactions(entity_id)
    
    if data is None:
        return {
            'entity_id': entity_id,
            'success': False,
            'transaction_count': 0,
            'entities_found': 0
        }
    
    # Process and extract entities
    result = scraper.process_transactions(data)
    
    with stats_lock:
        global_stats['transactions_found'] += result['transaction_count']
    
    return result

def upload_pending_data(force: bool = False):
    """Upload pending entities and transactions to Supabase"""
    global pending_transactions, unique_transaction_entities
    
    # Check if we should upload (based on batch size or time)
    should_upload = force
    
    with pending_transactions_lock:
        transactions_count = len(pending_transactions)
    
    with unique_entities_lock:
        entities_count = len(unique_transaction_entities)
    
    # Check batch size threshold
    if transactions_count >= UPLOAD_BATCH_SIZE * 10:  # 1000 transactions
        should_upload = True
    
    # Check time threshold
    with stats_lock:
        if global_stats['last_upload_time']:
            time_since_upload = (datetime.now() - global_stats['last_upload_time']).total_seconds()
            if time_since_upload >= UPLOAD_INTERVAL_SECONDS:
                should_upload = True
        else:
            global_stats['last_upload_time'] = datetime.now()
    
    if not should_upload:
        return
    
    # Upload entities first
    if entities_count > 0:
        with unique_entities_lock:
            entities_to_upload = list(unique_transaction_entities.values())
            # Clear after copying
            unique_transaction_entities.clear()
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates"
        }
        
        # Upload entities in batches
        batch_size = 500
        for i in range(0, len(entities_to_upload), batch_size):
            batch = entities_to_upload[i:i+batch_size]
            
            url = f"{SUPABASE_URL}/rest/v1/cf_entities"
            response = requests.post(url, headers=headers, json=batch)
            
            if response.status_code in [200, 201]:
                with stats_lock:
                    global_stats['entities_uploaded'] += len(batch)
    
    # Upload transactions
    if transactions_count > 0:
        with pending_transactions_lock:
            transactions_to_upload = pending_transactions.copy()
            pending_transactions.clear()
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Upload transactions in batches
        batch_size = 500
        for i in range(0, len(transactions_to_upload), batch_size):
            batch = transactions_to_upload[i:i+batch_size]
            
            url = f"{SUPABASE_URL}/rest/v1/cf_transactions"
            response = requests.post(url, headers=headers, json=batch)
            
            if response.status_code in [200, 201]:
                with stats_lock:
                    global_stats['transactions_uploaded'] += len(batch)
    
    # Update last upload time
    with stats_lock:
        global_stats['last_upload_time'] = datetime.now()
    
    if force and (entities_count > 0 or transactions_count > 0):
        print(f"\n📤 Uploaded {entities_count} entities and {transactions_count} transactions")

def periodic_upload_worker():
    """Background thread that periodically uploads data"""
    while not shutdown_requested:
        time.sleep(10)  # Check every 10 seconds
        if not shutdown_requested:
            upload_pending_data(force=False)


def print_progress():
    """Print progress statistics"""
    with stats_lock:
        if global_stats['start_time']:
            elapsed = datetime.now() - global_stats['start_time']
            processed = global_stats['success'] + global_stats['failed'] + global_stats['skipped']
            rate = processed / max(elapsed.total_seconds(), 1)
            remaining = global_stats['total'] - processed
            eta = timedelta(seconds=remaining / max(rate, 0.001))
            
            print(f"\r📊 Progress: {processed}/{global_stats['total']} | "
                  f"✅ {global_stats['success']} | ❌ {global_stats['failed']} | ⏭️ {global_stats['skipped']} | "
                  f"💰 {global_stats['transactions_found']} transactions | "
                  f"⚡ {rate:.1f}/sec | ⏱️ ETA: {str(eta).split('.')[0]}", end='', flush=True)

def main():
    """Main execution with concurrent processing"""
    parser = argparse.ArgumentParser(description='Fetch Campaign Finance Transactions CONCURRENTLY')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of entities to process')
    parser.add_argument('--workers', type=int, default=10,
                       help='Number of parallel workers (default: 10)')
    parser.add_argument('--skip-scraped', action='store_true', default=True,
                       help='Skip entities that have already been scraped')
    parser.add_argument('--no-skip-scraped', dest='skip_scraped', action='store_false',
                       help='Process all entities even if already scraped')
    parser.add_argument('--no-upload', action='store_true', default=False,
                       help='Disable automatic upload to Supabase')
    parser.add_argument('--upload-interval', type=int, default=60,
                       help='Upload interval in seconds (default: 60)')
    args = parser.parse_args()
    
    global UPLOAD_INTERVAL_SECONDS, upload_thread
    UPLOAD_INTERVAL_SECONDS = args.upload_interval
    
    print("\n" + "="*70)
    print("ARIZONA CAMPAIGN FINANCE - CONCURRENT TRANSACTION SCRAPER")
    print("="*70)
    
    # Fetch entity IDs
    entity_ids = fetch_entity_ids_from_supabase(
        limit=args.limit,
        skip_scraped=args.skip_scraped
    )
    
    if not entity_ids:
        print("No entities found to process")
        return
    
    print(f"\n🔧 Using {args.workers} parallel workers")
    
    # Calculate estimates
    total_time_estimate = len(entity_ids) * 2 / args.workers  # Assume 2 seconds per entity
    print(f"⏱️  Estimated time: {timedelta(seconds=total_time_estimate)}")
    
    # Initialize stats
    with stats_lock:
        global_stats['total'] = len(entity_ids)
        global_stats['start_time'] = datetime.now()
    
    print("\n" + "="*70)
    print("Fetching transactions...")
    if not args.no_upload:
        print(f"📤 Auto-upload enabled (every {UPLOAD_INTERVAL_SECONDS} seconds or {UPLOAD_BATCH_SIZE} entities)")
    print("="*70 + "\n")
    
    # Start background upload thread if uploads are enabled
    if not args.no_upload:
        upload_thread = Thread(target=periodic_upload_worker, daemon=True)
        upload_thread.start()
    
    # Process entities concurrently
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_entity = {
            executor.submit(worker_process_entity, i % args.workers, entity_id): entity_id 
            for i, entity_id in enumerate(entity_ids)
        }
        
        # Process completed tasks
        for future in as_completed(future_to_entity):
            if shutdown_requested:
                executor.shutdown(wait=False)
                break
                
            entity_id = future_to_entity[future]
            try:
                result = future.result()
                with stats_lock:
                    if result['success']:
                        if result['transaction_count'] > 0:
                            global_stats['success'] += 1
                        else:
                            global_stats['skipped'] += 1
                    else:
                        global_stats['failed'] += 1
            except Exception as e:
                with stats_lock:
                    global_stats['failed'] += 1
            
            # Print progress every 10 entities
            processed = global_stats['success'] + global_stats['failed'] + global_stats['skipped']
            if processed % 10 == 0:
                print_progress()
            
            # Check if we should upload (every N entities)
            if not args.no_upload and processed % UPLOAD_BATCH_SIZE == 0:
                upload_pending_data(force=False)
            
            # Add small delay to avoid overwhelming the server
            time.sleep(0.1)
    
    # Final upload of any remaining data
    if not args.no_upload and not shutdown_requested:
        print("\n📤 Performing final upload...")
        upload_pending_data(force=True)
    
    # Final statistics
    print("\n\n" + "="*70)
    print("📈 FINAL STATISTICS")
    print("="*70)
    
    with stats_lock:
        elapsed = datetime.now() - global_stats['start_time']
        processed = global_stats['success'] + global_stats['failed'] + global_stats['skipped']
        print(f"  Total entities: {global_stats['total']}")
        print(f"  Successfully scraped: {global_stats['success']}")
        print(f"  Failed: {global_stats['failed']}")
        print(f"  Skipped (no transactions): {global_stats['skipped']}")
        print(f"  Total transactions found: {global_stats['transactions_found']:,}")
        print(f"  Unique entities discovered: {global_stats['entities_uploaded']:,}")
        if not args.no_upload:
            print(f"  Entities uploaded to DB: {global_stats['entities_uploaded']:,}")
            print(f"  Transactions uploaded to DB: {global_stats['transactions_uploaded']:,}")
        print(f"  Total time: {str(elapsed).split('.')[0]}")
        print(f"  Average rate: {processed / elapsed.total_seconds():.2f} entities/second")
        print(f"  Transaction files saved in: {OUTPUT_DIR}")
    
    print("\n" + "="*70)
    print("SCRAPING COMPLETE!")
    print("="*70)

if __name__ == "__main__":
    main()