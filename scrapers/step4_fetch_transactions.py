#!/usr/bin/env python3
"""
Arizona Campaign Finance Transactions Scraper V3 - CONCURRENT WITH AUTO-UPLOAD
Fixed version that:
1. Pulls entity IDs from Supabase
2. Uploads entities BEFORE transactions to avoid foreign key errors
3. Uses multiple workers for concurrent processing
4. Auto-uploads to Supabase periodically
5. Shows real-time progress with ETA
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
import logging
from collections import defaultdict
from functools import wraps
import random
from threading import Lock, Thread
import signal
import sys
import atexit
from queue import Queue

# Configuration
OUTPUT_DIR = Path("campaign_finance_transactions")
OUTPUT_DIR.mkdir(exist_ok=True)
BASE_URL = "https://seethemoney.az.gov"

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

# Retry configuration
MAX_RETRIES = 5
RETRY_BACKOFF_FACTOR = 2
RETRY_JITTER = True

# Upload configuration
UPLOAD_BATCH_SIZE = 100  # Upload after every N entities
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

# Pending data for periodic upload
pending_transactions_lock = Lock()
pending_transactions = []
pending_entities_lock = Lock()
pending_entities = {}

# Flag for graceful shutdown
shutdown_requested = False

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_requested
    print("\n\n⚠️  Shutdown requested. Uploading remaining data and cleaning up...")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(OUTPUT_DIR / 'scraper_v3.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def retry_with_backoff(max_retries=MAX_RETRIES, backoff_factor=RETRY_BACKOFF_FACTOR, jitter=RETRY_JITTER):
    """Decorator to retry function calls with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    # Calculate backoff time with optional jitter
                    backoff_time = backoff_factor ** attempt
                    if jitter:
                        backoff_time *= (0.5 + random.random() * 0.5)  # Add 50% jitter
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    logger.info(f"Retrying in {backoff_time:.2f} seconds...")
                    time.sleep(backoff_time)
            
            return None  # Should never reach here
        return wrapper
    return decorator

class TransactionScraperV3:
    """Enhanced scraper that pulls from Supabase and handles foreign keys properly"""
    
    def __init__(self, upload_to_db: bool = False):
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
        
        self.upload_to_db = upload_to_db
        self.supabase_headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        # Track unique entities and types
        self.unique_transaction_entities = {}
        self.transaction_types = {}
        self.transaction_groups = {}
        self.entity_types = {}
        
        # Store all transactions to process after entities are uploaded
        self.all_transactions_to_upload = []
    
    def check_entity_already_scraped(self, entity_id: int) -> bool:
        """Check if an entity has already been scraped by looking for transactions in Supabase"""
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
            else:
                logger.warning(f"Could not check if entity {entity_id} was scraped: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"Error checking if entity {entity_id} was scraped: {e}")
            return False
    
    def check_entities_already_scraped_batch(self, entity_ids: List[int]) -> set:
        """Efficiently check which entities have already been scraped in batch"""
        logger.info(f"Checking which of {len(entity_ids)} entities have already been scraped...")
        
        scraped_entities = set()
        batch_size = 500  # Process in chunks to avoid URL length limits
        
        for i in range(0, len(entity_ids), batch_size):
            batch = entity_ids[i:i+batch_size]
            
            # Create an OR query for all entity IDs in this batch
            entity_filter = f"entity_id=in.({','.join(map(str, batch))})"
            
            url = f"{SUPABASE_URL}/rest/v1/cf_transactions"
            params = {
                "select": "entity_id",
                entity_filter.split('=')[0]: entity_filter.split('=', 1)[1]
            }
            
            try:
                response = requests.get(url, headers=self.supabase_headers, params=params)
                if response.status_code == 200:
                    transactions = response.json()
                    # Extract unique entity IDs that have transactions
                    batch_scraped = {t['entity_id'] for t in transactions if 'entity_id' in t}
                    scraped_entities.update(batch_scraped)
                    
                    if i % (batch_size * 10) == 0 and i > 0:
                        logger.info(f"  Checked {i}/{len(entity_ids)} entities...")
                else:
                    logger.warning(f"Failed to check batch {i//batch_size}: {response.status_code}")
            except Exception as e:
                logger.warning(f"Error checking batch {i//batch_size}: {e}")
        
        logger.info(f"Found {len(scraped_entities)} entities that have already been scraped")
        return scraped_entities
    
    def fetch_entity_ids_from_supabase(self, limit: Optional[int] = None, skip_scraped: bool = True) -> List[int]:
        """Fetch entity IDs from Supabase database with pagination"""
        logger.info("Fetching entity IDs from Supabase...")
        
        all_entities = []
        offset = 0
        batch_size = 1000  # Supabase max
        
        while True:
            url = f"{SUPABASE_URL}/rest/v1/cf_entities"
            params = {
                "select": "entity_id",
                "order": "entity_id",
                "limit": str(batch_size),
                "offset": str(offset)
            }
            
            # If user specified a limit and we've fetched enough, stop
            if limit and len(all_entities) >= limit:
                all_entities = all_entities[:limit]
                break
            
            try:
                response = requests.get(url, headers=self.supabase_headers, params=params)
                if response.status_code == 200:
                    batch = response.json()
                    all_entities.extend(batch)
                    
                    # Check if we got all records
                    if len(batch) < batch_size:
                        break
                    
                    offset += batch_size
                    if len(all_entities) > 1000:
                        logger.info(f"  Fetched {len(all_entities)} entities so far...")
                else:
                    logger.error(f"Failed to fetch entities from Supabase: {response.status_code}")
                    break
            except Exception as e:
                logger.error(f"Error fetching entities from Supabase: {e}")
                break
        
        # Apply user limit if specified
        if limit:
            all_entities = all_entities[:limit]
        
        entity_ids = [e['entity_id'] for e in all_entities]
        logger.info(f"Fetched {len(entity_ids)} total entity IDs from Supabase")
        
        if skip_scraped:
            # Filter out already scraped entities
            logger.info("Checking which entities have already been scraped...")
            unscraped_ids = []
            for entity_id in entity_ids:
                if not self.check_entity_already_scraped(entity_id):
                    unscraped_ids.append(entity_id)
            logger.info(f"Found {len(unscraped_ids)} entities that haven't been scraped yet (out of {len(entity_ids)} total)")
            return unscraped_ids
        
        return entity_ids
    
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
    
    def parse_date_to_date(self, date_str: str) -> Optional[str]:
        """Convert /Date(timestamp)/ format to date string"""
        if date_str and '/Date(' in str(date_str):
            try:
                timestamp = int(date_str.replace('/Date(', '').replace(')/', '')) / 1000
                return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            except:
                return None
        return None
    
    @retry_with_backoff(max_retries=MAX_RETRIES)
    def fetch_entity_transactions(self, entity_id: int, table_page: int = 1, table_length: int = 100) -> Optional[Dict]:
        """Fetch transactions for a specific entity and page with retry logic"""
        
        url_params = {
            'Page': '24',
            'startYear': '2002',
            'endYear': '2026',
            'JurisdictionId': '0',
            'TablePage': str(table_page),
            'TableLength': str(table_length),
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
            'start': str((table_page - 1) * table_length),
            'length': str(table_length),
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
            return response.json()
        elif response.status_code >= 500:
            # Server errors should trigger retry
            raise Exception(f"Server error fetching entity {entity_id} page {table_page}: Status {response.status_code}")
        else:
            # Client errors shouldn't retry (400-499)
            logger.error(f"Client error fetching entity {entity_id} page {table_page}: Status {response.status_code}")
            return None
    
    def fetch_all_entity_transactions(self, entity_id: int, page_size: int = 100) -> Tuple[List[Dict], Dict]:
        """Fetch all transactions for an entity with pagination"""
        
        all_transactions = []
        stats = {
            'entity_id': entity_id,
            'total_records': 0,
            'pages_fetched': 0,
            'fetch_errors': 0,
            'start_time': datetime.now()
        }
        
        logger.info(f"Fetching transactions for entity {entity_id}...")
        first_page = self.fetch_entity_transactions(entity_id, table_page=1, table_length=page_size)
        
        if not first_page:
            stats['fetch_errors'] += 1
            logger.warning(f"No data for entity {entity_id}")
            return all_transactions, stats
        
        total_records = first_page.get('recordsTotal', 0)
        stats['total_records'] = total_records
        
        if total_records == 0:
            logger.info(f"Entity {entity_id} has no transactions")
            return all_transactions, stats
        
        if 'data' in first_page:
            all_transactions.extend(first_page['data'])
            stats['pages_fetched'] += 1
        
        total_pages = (total_records + page_size - 1) // page_size
        logger.info(f"Entity {entity_id}: {total_records} transactions across {total_pages} pages")
        
        for page in range(2, total_pages + 1):
            time.sleep(0.1)  # Rate limiting
            
            page_data = self.fetch_entity_transactions(entity_id, table_page=page, table_length=page_size)
            if page_data and 'data' in page_data:
                all_transactions.extend(page_data['data'])
                stats['pages_fetched'] += 1
                
                if page % 10 == 0:
                    logger.info(f"  Entity {entity_id}: Fetched page {page}/{total_pages}")
            else:
                stats['fetch_errors'] += 1
                logger.warning(f"  Failed to fetch page {page} for entity {entity_id}")
        
        stats['end_time'] = datetime.now()
        stats['duration_seconds'] = (stats['end_time'] - stats['start_time']).total_seconds()
        
        logger.info(f"Completed entity {entity_id}: {len(all_transactions)} transactions fetched")
        return all_transactions, stats
    
    def process_transaction_for_db(self, transaction: Dict, entity_id: int) -> Dict:
        """Process transaction data for database insertion with ALL fields"""
        
        # Parse ReceivedFromOrPaidTo
        rfpt = transaction.get('ReceivedFromOrPaidTo', '')
        parsed_entity = self.parse_received_from_paid_to(rfpt)
        transaction_entity_id = parsed_entity['entity_id'] if parsed_entity else None
        
        # Track unique entities (including -1 for "Multiple Contributors")
        if parsed_entity and transaction_entity_id:
            if transaction_entity_id not in self.unique_transaction_entities:
                if transaction_entity_id == -1:
                    # Special handling for "Multiple Contributors"
                    self.unique_transaction_entities[transaction_entity_id] = {
                        'entity_id': -1,
                        'entity_name': 'Multiple Contributors',
                        'first_name': None,
                        'middle_name': None,
                        'last_name': 'Multiple Contributors',
                        'entity_type_id': parsed_entity['entity_type_id'],
                        'group_number': parsed_entity['group_number'],
                        'group_id': parsed_entity['group_id']
                    }
                else:
                    self.unique_transaction_entities[transaction_entity_id] = {
                        'entity_id': transaction_entity_id,
                        'entity_name': parsed_entity['full_name'] or f"{parsed_entity['last_name']}, {parsed_entity['first_name']}".strip(', '),
                        'first_name': parsed_entity['first_name'],
                        'middle_name': parsed_entity['middle_name'],
                        'last_name': parsed_entity['last_name'],
                        'entity_type_id': parsed_entity['entity_type_id'],
                        'group_number': parsed_entity['group_number'],
                        'group_id': parsed_entity['group_id']
                    }
        
        # Track transaction types
        type_id = transaction.get('TransactionTypeId')
        if type_id and type_id not in self.transaction_types:
            self.transaction_types[type_id] = {
                'transaction_type_id': type_id,
                'transaction_type_name': transaction.get('TransactionType'),
                'transaction_disposition_id': transaction.get('TransactionTypeDispositionId')
            }
        
        # Track groups
        group_num = transaction.get('TransactionGroupNumber')
        if group_num and group_num not in self.transaction_groups:
            self.transaction_groups[group_num] = {
                'group_number': group_num,
                'group_name': transaction.get('TransactionGroupName'),
                'group_color': transaction.get('TransactionGroupColor')
            }
        
        # Track entity types
        entity_type = transaction.get('TransactionEntityTypeId')
        if entity_type and entity_type not in self.entity_types:
            self.entity_types[entity_type] = {
                'entity_type_id': entity_type,
                'entity_type_name': transaction.get('EntityDescription')
            }
        
        # Build complete transaction record
        processed = {
            # Primary identifiers
            'public_transaction_id': transaction.get('PublicTransactionId'),
            'transaction_id': transaction.get('TransactionId'),
            
            # Entity relationships
            'entity_id': entity_id,  # The committee/candidate
            'transaction_entity_id': transaction_entity_id,  # The donor/vendor
            
            # Committee information
            'committee_id': transaction.get('CommitteeId'),
            'committee_unique_id': transaction.get('CommitteeUniqueId'),
            'committee_name': transaction.get('CommitteeName'),
            
            # Transaction details
            'transaction_date': self.parse_date_to_date(transaction.get('TransactionDate')),
            'transaction_date_timestamp': self.parse_date(transaction.get('TransactionDate')),
            'transaction_date_year': transaction.get('TransactionDateYear'),
            'transaction_date_year_month': self.parse_date_to_date(transaction.get('TransactionDateYearMonth')),
            'transaction_type_id': transaction.get('TransactionTypeId'),
            'transaction_type': transaction.get('TransactionType'),
            'transaction_type_disposition_id': transaction.get('TransactionTypeDispositionId'),
            'amount': float(transaction.get('Amount', 0)) if transaction.get('Amount') is not None else 0,
            
            # Transaction party details
            'transaction_name_id': transaction.get('TransactionNameId'),
            'transaction_name_group_id': transaction.get('TransactionNameGroupId'),
            'transaction_entity_type_id': transaction.get('TransactionEntityTypeId'),
            # Use parsed values if available, otherwise fall back to API response
            'transaction_first_name': parsed_entity['first_name'] if parsed_entity else transaction.get('TransactionFirstName'),
            'transaction_middle_name': parsed_entity['middle_name'] if parsed_entity else transaction.get('TransactionMiddleName'),
            'transaction_last_name': parsed_entity['last_name'] if parsed_entity else transaction.get('TransactionLastName'),
            'received_from_or_paid_to': rfpt,
            
            # Additional party information
            'transaction_occupation': transaction.get('TransactionOccupation'),
            'transaction_employer': transaction.get('TransactionEmployer'),
            'transaction_city': transaction.get('TransactionCity'),
            'transaction_state': transaction.get('TransactionState'),
            'transaction_zip_code': transaction.get('TransactionZipCode'),
            
            # Entity categorization
            'entity_type_id': transaction.get('EntityTypeId'),
            'entity_description': transaction.get('EntityDescription'),
            'transaction_group_number': transaction.get('TransactionGroupNumber'),
            'transaction_group_name': transaction.get('TransactionGroupName'),
            'transaction_group_color': transaction.get('TransactionGroupColor'),
            
            # Committee categorization
            'committee_group_number': transaction.get('CommitteeGroupNumber'),
            'committee_group_name': transaction.get('CommitteeGroupName'),
            'committee_group_color': transaction.get('CommitteeGroupColor'),
            
            # Subject committee information
            'subject_committee_id': transaction.get('SubjectCommitteeId'),
            'subject_committee_name': transaction.get('SubjectCommitteeName'),
            'subject_committee_name_id': transaction.get('SubjectCommitteeNameId'),
            'subject_group_number': transaction.get('SubjectGroupNumber'),
            'is_for_benefit': transaction.get('IsForBenefit'),
            'benefited_opposed': transaction.get('BenefitedOpposed'),
            
            # Candidate information
            'candidate_cycle_id': transaction.get('CandidateCycleId'),
            'candidate_office_type_id': transaction.get('CandidateOfficeTypeId'),
            'candidate_office_id': transaction.get('CandidateOfficeId'),
            'candidate_party_id': transaction.get('CandidatePartyId'),
            'candidate_first_name': transaction.get('CandidateFirstName'),
            'candidate_middle_name': transaction.get('CandidateMiddleName'),
            'candidate_last_name': transaction.get('CandidateLastName'),
            
            # Ballot measure information
            'ballot_measure_id': transaction.get('BallotMeasureId'),
            'ballot_measure_number': transaction.get('BallotMeasureNumber'),
            
            # Additional metadata
            'jurisdiction_id': transaction.get('JurisdictionId', 0),
            'jurisdiction_name': transaction.get('JurisdictionName'),
            'report_id': transaction.get('ReportId'),
            'memo': transaction.get('Memo')
        }
        
        return processed
    
    def collect_transactions(self, entity_id: int, transactions: List[Dict]):
        """Collect and process transactions but don't upload yet"""
        
        logger.info(f"Processing {len(transactions)} transactions for entity {entity_id}...")
        
        for trans in transactions:
            processed = self.process_transaction_for_db(trans, entity_id)
            self.all_transactions_to_upload.append(processed)
    
    def upload_all_data(self):
        """Upload all data in the correct order to avoid foreign key errors"""
        
        if not self.upload_to_db:
            return
        
        logger.info("=" * 50)
        logger.info("UPLOADING ALL DATA IN CORRECT ORDER")
        logger.info("=" * 50)
        
        # 1. Upload lookup tables first
        self.upload_lookup_tables()
        
        # 2. Upload transaction entities (donors/vendors) BEFORE transactions
        self.upload_transaction_entities()
        
        # 3. Finally upload all transactions
        self.upload_all_transactions()
        
        logger.info("=" * 50)
        logger.info("ALL DATA UPLOADED SUCCESSFULLY")
        logger.info("=" * 50)
    
    @retry_with_backoff(max_retries=MAX_RETRIES)
    def _upload_with_retry(self, url: str, data: Dict, conflict_field: str = None) -> bool:
        """Helper method to upload data with retry logic"""
        headers = self.supabase_headers.copy()
        headers['Prefer'] = 'resolution=merge-duplicates,return=minimal'
        
        if conflict_field:
            url = f"{url}?on_conflict={conflict_field}"
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            return True
        elif response.status_code >= 500:
            # Server errors should trigger retry
            raise Exception(f"Server error: {response.status_code} - {response.text[:200]}")
        else:
            # Client errors shouldn't retry
            logger.error(f"Client error: {response.status_code} - {response.text[:200]}")
            return False
    
    def upload_lookup_tables(self):
        """Upload lookup tables with retry logic"""
        if not self.upload_to_db:
            return
        
        logger.info("Step 1: Uploading lookup tables...")
        
        # Upload transaction types
        if self.transaction_types:
            url = f"{SUPABASE_URL}/rest/v1/cf_transaction_types"
            for type_data in self.transaction_types.values():
                try:
                    self._upload_with_retry(url, type_data, 'transaction_type_id')
                except Exception as e:
                    logger.error(f"Error uploading transaction type after retries: {e}")
        
        # Upload transaction groups
        if self.transaction_groups:
            url = f"{SUPABASE_URL}/rest/v1/cf_transaction_groups"
            for group_data in self.transaction_groups.values():
                try:
                    self._upload_with_retry(url, group_data, 'group_number')
                except Exception as e:
                    logger.error(f"Error uploading transaction group after retries: {e}")
        
        # Upload entity types
        if self.entity_types:
            url = f"{SUPABASE_URL}/rest/v1/cf_entity_types"
            for entity_type_data in self.entity_types.values():
                try:
                    self._upload_with_retry(url, entity_type_data, 'entity_type_id')
                except Exception as e:
                    logger.error(f"Error uploading entity type after retries: {e}")
        
        logger.info(f"  ✓ Uploaded {len(self.transaction_types)} transaction types")
        logger.info(f"  ✓ Uploaded {len(self.transaction_groups)} transaction groups")
        logger.info(f"  ✓ Uploaded {len(self.entity_types)} entity types")
    
    @retry_with_backoff(max_retries=MAX_RETRIES)
    def _upload_batch_with_retry(self, url: str, batch: List[Dict], batch_num: int, conflict_field: str = None) -> bool:
        """Helper method to upload batch data with retry logic"""
        headers = self.supabase_headers.copy()
        headers['Prefer'] = 'resolution=merge-duplicates,return=minimal'
        
        if conflict_field:
            url = f"{url}?on_conflict={conflict_field}"
        
        response = requests.post(url, headers=headers, json=batch)
        
        if response.status_code in [200, 201]:
            logger.info(f"  ✓ Successfully uploaded batch {batch_num}")
            return True
        elif response.status_code >= 500:
            # Server errors should trigger retry
            raise Exception(f"Server error uploading batch {batch_num}: {response.status_code} - {response.text[:200]}")
        else:
            # Client errors shouldn't retry
            logger.error(f"Client error uploading batch {batch_num}: {response.status_code} - {response.text[:200]}")
            return False
    
    def upload_transaction_entities(self):
        """Upload unique transaction entities BEFORE transactions with retry logic"""
        if not self.upload_to_db or not self.unique_transaction_entities:
            return
        
        logger.info(f"Step 2: Uploading {len(self.unique_transaction_entities)} transaction entities...")
        
        url = f"{SUPABASE_URL}/rest/v1/cf_transaction_entities"
        entities_list = list(self.unique_transaction_entities.values())
        
        # Upload in batches
        batch_size = 100
        success_count = 0
        failed_batches = []
        
        for i in range(0, len(entities_list), batch_size):
            batch = entities_list[i:i+batch_size]
            batch_num = i//batch_size + 1
            
            try:
                if self._upload_batch_with_retry(url, batch, batch_num, 'entity_id'):
                    success_count += len(batch)
                else:
                    failed_batches.append((batch_num, batch))
            except Exception as e:
                logger.error(f"  ✗ Failed to upload entity batch {batch_num} after {MAX_RETRIES} retries: {e}")
                failed_batches.append((batch_num, batch))
        
        logger.info(f"  ✓ Successfully uploaded {success_count} entities")
    
    def upload_all_transactions(self):
        """Upload all collected transactions with retry logic"""
        if not self.upload_to_db or not self.all_transactions_to_upload:
            return
        
        logger.info(f"Step 3: Uploading {len(self.all_transactions_to_upload)} transactions...")
        
        url = f"{SUPABASE_URL}/rest/v1/cf_transactions"
        batch_size = 500
        success_count = 0
        failed_batches = []
        
        for i in range(0, len(self.all_transactions_to_upload), batch_size):
            batch = self.all_transactions_to_upload[i:i+batch_size]
            batch_num = i//batch_size + 1
            
            try:
                if self._upload_batch_with_retry(url, batch, batch_num, 'public_transaction_id'):
                    success_count += len(batch)
                else:
                    failed_batches.append((batch_num, batch))
            except Exception as e:
                logger.error(f"  ✗ Failed to upload transaction batch {batch_num} after {MAX_RETRIES} retries: {e}")
                failed_batches.append((batch_num, batch))
        
        if failed_batches:
            logger.warning(f"Failed to upload {len(failed_batches)} transaction batches after retries")
        
        logger.info(f"  ✓ Successfully uploaded {success_count} transactions")

def print_progress():
    """Print real-time progress with ETA"""
    with stats_lock:
        if global_stats['start_time']:
            elapsed = datetime.now() - global_stats['start_time']
            processed = global_stats['success'] + global_stats['failed'] + global_stats['skipped']
            if processed > 0:
                rate = processed / max(elapsed.total_seconds(), 1)
                remaining = global_stats['total'] - processed
                eta = timedelta(seconds=remaining / max(rate, 0.001))
                
                print(f"\r📊 Progress: {processed}/{global_stats['total']} | "
                      f"✅ {global_stats['success']} | ❌ {global_stats['failed']} | ⏭️ {global_stats['skipped']} | "
                      f"💰 {global_stats['transactions_found']:,} transactions | "
                      f"⚡ {rate:.1f}/sec | ⏱️ ETA: {str(eta).split('.')[0]}", end='', flush=True)

def upload_pending_data(scraper, force=False):
    """Upload pending data to Supabase"""
    global pending_transactions, pending_entities
    
    should_upload = force
    
    with pending_transactions_lock:
        trans_count = len(pending_transactions)
    with pending_entities_lock:
        entities_count = len(pending_entities)
    
    # Check thresholds
    if trans_count >= UPLOAD_BATCH_SIZE * 10:
        should_upload = True
    
    with stats_lock:
        if global_stats['last_upload_time']:
            time_since = (datetime.now() - global_stats['last_upload_time']).total_seconds()
            if time_since >= UPLOAD_INTERVAL_SECONDS:
                should_upload = True
        else:
            global_stats['last_upload_time'] = datetime.now()
    
    if not should_upload or (trans_count == 0 and entities_count == 0):
        return
    
    # Upload entities first
    if entities_count > 0:
        with pending_entities_lock:
            entities_to_upload = dict(pending_entities)
            pending_entities.clear()
        
        # Update scraper's entities for upload
        scraper.unique_transaction_entities.update(entities_to_upload)
        with stats_lock:
            global_stats['entities_uploaded'] += len(entities_to_upload)
    
    # Upload transactions
    if trans_count > 0:
        with pending_transactions_lock:
            trans_to_upload = list(pending_transactions)
            pending_transactions.clear()
        
        # Add to scraper's transaction list
        scraper.all_transactions_to_upload.extend(trans_to_upload)
        with stats_lock:
            global_stats['transactions_uploaded'] += len(trans_to_upload)
    
    # Do the actual upload
    if scraper.upload_to_db and (entities_count > 0 or trans_count > 0):
        scraper.upload_all_data()
        scraper.all_transactions_to_upload = []  # Clear after upload
    
    with stats_lock:
        global_stats['last_upload_time'] = datetime.now()

def worker_process_entity(worker_id, entity_id, scraper, args):
    """Worker function to process a single entity"""
    try:
        # Note: Batch checking is now done upfront in main(), so we don't check individually here
        
        # Fetch transactions
        transactions, stats = scraper.fetch_all_entity_transactions(entity_id)
        
        if transactions:
            # Save to file if requested
            if args.save_files:
                output_file = OUTPUT_DIR / f"entity_{entity_id}_transactions.json"
                with open(output_file, 'w') as f:
                    json.dump(transactions, f, indent=2)
            
            # Process transactions and queue for upload
            processed_trans = []
            for trans in transactions:
                processed = scraper.process_transaction_for_db(trans, entity_id)
                processed_trans.append(processed)
            
            # Add to pending
            with pending_transactions_lock:
                pending_transactions.extend(processed_trans)
            
            # Track unique entities
            with pending_entities_lock:
                for ent_id, ent_data in scraper.unique_transaction_entities.items():
                    if ent_id not in pending_entities:
                        pending_entities[ent_id] = ent_data
            
            with stats_lock:
                global_stats['success'] += 1
                global_stats['transactions_found'] += len(transactions)
            
            return {'entity_id': entity_id, 'status': 'success', 'count': len(transactions)}
        else:
            with stats_lock:
                global_stats['failed'] += 1
            return {'entity_id': entity_id, 'status': 'failed'}
            
    except Exception as e:
        with stats_lock:
            global_stats['failed'] += 1
        return {'entity_id': entity_id, 'status': 'error', 'error': str(e)}

def main():
    """Main execution"""
    
    parser = argparse.ArgumentParser(description='Scrape Arizona Campaign Finance Transactions V3')
    parser.add_argument('--upload', action='store_true',
                       help='Upload results to Supabase database')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of entities to process')
    parser.add_argument('--entity-id', type=int, default=None,
                       help='Process specific entity ID')
    parser.add_argument('--start-from', type=int, default=0,
                       help='Start from entity index (for resuming)')
    parser.add_argument('--save-files', action='store_true',
                       help='Save transaction data to JSON files')
    parser.add_argument('--use-local', action='store_true',
                       help='Use local entity file instead of fetching from Supabase')
    parser.add_argument('--max-retries', type=int, default=5,
                       help='Maximum number of retries for failed requests (default: 5)')
    parser.add_argument('--skip-scraped', action='store_true', default=True,
                       help='Skip entities that have already been scraped (default: True)')
    parser.add_argument('--force-rescrape', action='store_true',
                       help='Force re-scraping of all entities, ignoring existing data')
    parser.add_argument('--workers', type=int, default=10,
                       help='Number of parallel workers (default: 10)')
    args = parser.parse_args()
    
    # Update global retry configuration if specified
    global MAX_RETRIES
    if args.max_retries != MAX_RETRIES:
        MAX_RETRIES = args.max_retries
        logger.info(f"Set maximum retries to {MAX_RETRIES}")
    
    print("\n" + "="*70)
    print("ARIZONA CAMPAIGN FINANCE - TRANSACTION SCRAPER V3")
    print("Enhanced with retry logic and automatic skip of scraped entities")
    print(f"Max retries per request: {MAX_RETRIES}")
    print(f"Skip already scraped: {not args.force_rescrape}")
    print("="*70)
    
    scraper = TransactionScraperV3(upload_to_db=args.upload)
    
    # Get entity IDs to process
    if args.entity_id:
        entity_ids = [args.entity_id]
    elif args.use_local:
        # Use local file if specified
        entity_file = Path("campaign_finance_data/step1_entity_ids.json")
        if entity_file.exists():
            with open(entity_file, 'r') as f:
                entity_ids = json.load(f)
            logger.info(f"Loaded {len(entity_ids)} entity IDs from local file")
        else:
            logger.warning("No local file found, using test entities")
            entity_ids = [201600383, 100147, 100148, 100149, 100150]
    else:
        # Fetch from Supabase by default
        entity_ids = scraper.fetch_entity_ids_from_supabase(limit=args.limit)
    
    # Apply start-from and limit
    if args.start_from:
        entity_ids = entity_ids[args.start_from:]
    if args.limit and not args.entity_id:
        entity_ids = entity_ids[:args.limit]
    
    # Batch check for already scraped entities if not force rescraping
    if not args.force_rescrape and args.skip_scraped:
        scraped_set = scraper.check_entities_already_scraped_batch([e if isinstance(e, int) else e['entity_id'] for e in entity_ids])
        original_count = len(entity_ids)
        entity_ids = [e for e in entity_ids if (e if isinstance(e, int) else e['entity_id']) not in scraped_set]
        skipped_count = original_count - len(entity_ids)
        if skipped_count > 0:
            logger.info(f"Skipping {skipped_count} already-scraped entities, processing {len(entity_ids)} remaining")
            with stats_lock:
                global_stats['skipped'] = skipped_count
    
    logger.info(f"Processing {len(entity_ids)} entities with {args.workers} workers")
    
    # Initialize global stats
    with stats_lock:
        global_stats['total'] = len(entity_ids) + global_stats.get('skipped', 0)
        global_stats['start_time'] = datetime.now()
    
    # Track overall statistics
    overall_stats = {
        'start_time': datetime.now(),
        'entities_processed': 0,
        'entities_with_transactions': 0,
        'total_transactions': 0,
        'unique_transaction_entities': 0,
        'errors': 0
    }
    
    print("\n" + "="*70)
    print("Processing entities...")
    if args.upload:
        print(f"📤 Auto-upload enabled (every {UPLOAD_INTERVAL_SECONDS} seconds or {UPLOAD_BATCH_SIZE} entities)")
    print("="*70 + "\n")
    
    # Process entities concurrently
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Create a scraper instance for each worker
        scrapers = {i: TransactionScraperV3(upload_to_db=args.upload) for i in range(args.workers)}
        
        # Submit all tasks
        future_to_entity = {
            executor.submit(worker_process_entity, i % args.workers, entity_id, scrapers[i % args.workers], args): entity_id
            for i, entity_id in enumerate(entity_ids)
        }
        
        # Process completed tasks
        completed = 0
        for future in as_completed(future_to_entity):
            if shutdown_requested:
                executor.shutdown(wait=False)
                break
            
            entity_id = future_to_entity[future]
            try:
                result = future.result()
                completed += 1
                
                # Print progress every 10 entities
                if completed % 10 == 0:
                    print_progress()
                
                # Check if we should upload
                if args.upload and completed % UPLOAD_BATCH_SIZE == 0:
                    # Use the first scraper for uploads
                    upload_pending_data(scrapers[0], force=False)
                
            except Exception as e:
                logger.error(f"Error processing entity {entity_id}: {e}")
                with stats_lock:
                    global_stats['failed'] += 1
            
            # Small delay to avoid overwhelming server
            time.sleep(0.1)
    
    # Final upload
    if args.upload and not shutdown_requested:
        print("\n📤 Performing final upload...")
        upload_pending_data(scrapers[0], force=True)
    
    # Update overall stats from global stats
    with stats_lock:
        overall_stats['entities_processed'] = global_stats['success'] + global_stats['failed'] + global_stats['skipped']
        overall_stats['entities_with_transactions'] = global_stats['success']
        overall_stats['total_transactions'] = global_stats['transactions_found']
        overall_stats['unique_transaction_entities'] = global_stats['entities_uploaded']
    
    # Calculate final statistics
    overall_stats['end_time'] = datetime.now()
    overall_stats['duration'] = (overall_stats['end_time'] - overall_stats['start_time']).total_seconds()
    
    # Print summary
    print("\n" + "="*70)
    print("SCRAPING COMPLETE!")
    print("="*70)
    print(f"\n📊 Final Statistics:")
    print(f"  Entities processed: {overall_stats['entities_processed']}")
    print(f"  Entities with transactions: {overall_stats['entities_with_transactions']}")
    print(f"  Total transactions: {overall_stats['total_transactions']:,}")
    print(f"  Unique transaction entities: {overall_stats['unique_transaction_entities']:,}")
    print(f"  Duration: {overall_stats['duration']:.2f} seconds")
    
    if args.upload:
        print(f"\n✅ Data uploaded to Supabase in correct order:")
        print(f"  1. Lookup tables")
        print(f"  2. Transaction entities (donors/vendors)")
        print(f"  3. Transactions")
    
    # Save statistics
    stats_file = OUTPUT_DIR / f"scraping_stats_v3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(stats_file, 'w') as f:
        json.dump(overall_stats, f, indent=2, default=str)
    print(f"\n📈 Statistics saved to {stats_file}")

if __name__ == "__main__":
    main()