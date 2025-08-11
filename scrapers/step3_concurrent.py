#!/usr/bin/env python3
"""
Arizona Campaign Finance Scraper - Step 3 CONCURRENT VERSION
Processes PDFs in parallel with multiple workers for faster processing
Target: 37,000 PDFs in 18 hours
"""

import os
import subprocess
import time
import csv
import requests
import hashlib
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import signal
import sys

# Configuration
OUTPUT_DIR = Path("campaign_finance_data")
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_PDF_DIR = OUTPUT_DIR / "temp_pdfs"
TEMP_PDF_DIR.mkdir(exist_ok=True)
PROCESSED_CSV_DIR = OUTPUT_DIR / "processed_csvs"
PROCESSED_CSV_DIR.mkdir(exist_ok=True)

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

# Global stats for tracking
stats_lock = Lock()
global_stats = {
    'total': 0,
    'success': 0,
    'failed': 0,
    'skipped': 0,
    'start_time': None,
    'donations_uploaded': 0
}

# Flag for graceful shutdown
shutdown_requested = False

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_requested
    print("\n\n⚠️  Shutdown requested. Waiting for current PDFs to complete...")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)

class PDFDonationProcessor:
    """Process PDFs through R scraper and upload to Supabase"""
    
    def __init__(self, worker_id: int = 0):
        self.worker_id = worker_id
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        self.supabase_headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Create R wrapper script if it doesn't exist
        self.r_wrapper_path = OUTPUT_DIR / f"pdf_scraper_wrapper_{worker_id}.R"
        self._create_r_wrapper()
    
    def _create_r_wrapper(self):
        """Create a simple R script to call the PDF scraper function"""
        r_wrapper_content = '''
# R Wrapper for PDF Donation Scraper
args <- commandArgs(trailingOnly = TRUE)
pdf_path <- args[1]
output_path <- args[2]

# Load required libraries (individual tidyverse components)
suppressMessages({
    library(dplyr)
    library(tidyr)
    library(stringr)
    library(purrr)
    library(tibble)
    library(readr)
    library(lubridate)
    library(pdftools)
})

# First try to use the fixed scraper if it exists
fixed_scraper_path <- "/Users/jordanharb/Documents/az-campaign-finance/scrapers/r_scraper_fixed.R"
original_scraper_path <- "/Users/jordanharb/Documents/az-campaign-finance/pdf-scraper/DonationReportScrapingCode/20250425-001_DonationReportDataScrape/_04-LocalFunctions/PDFData_DonorReports.R"

if (file.exists(fixed_scraper_path)) {
    source(fixed_scraper_path)
} else if (file.exists(original_scraper_path)) {
    source(original_scraper_path)
} else {
    stop("No R scraper function found")
}

# Process the PDF
tryCatch({
    result <- TEMP_FUNC(pdf_path)
    
    if (nrow(result) > 0) {
        # Add metadata columns
        result$META_SegmentName <- basename(dirname(pdf_path))
        result$META_FileName <- basename(pdf_path)
        
        # Write to CSV
        write.csv(result, output_path, row.names = FALSE)
        cat("SUCCESS: Processed", nrow(result), "donations\\n")
    } else {
        cat("WARNING: No donations found in PDF\\n")
        # Write empty CSV with headers
        write.csv(result, output_path, row.names = FALSE)
    }
}, error = function(e) {
    cat("ERROR:", e$message, "\\n")
    quit(status = 1)
})
'''
        
        with open(self.r_wrapper_path, 'w') as f:
            f.write(r_wrapper_content)
    
    def download_pdf(self, pdf_url: str, entity_id: int, pdf_id: int) -> Optional[Path]:
        """Download a PDF to temporary directory with proper retry logic"""
        # Check if this is an unfiled report URL pattern (ReportFile/ID format)
        is_unfiled_report = '/ReportFile/' in pdf_url
        
        max_retries = 1 if is_unfiled_report else 3
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(pdf_url, timeout=45)  # Increased timeout
                if response.status_code == 200:
                    # Create a safe filename with worker ID to avoid conflicts
                    safe_name = f"entity_{entity_id}_pdf_{pdf_id}_w{self.worker_id}.pdf"
                    pdf_path = TEMP_PDF_DIR / safe_name
                    
                    with open(pdf_path, 'wb') as f:
                        f.write(response.content)
                    
                    return pdf_path
                elif response.status_code == 404:
                    if is_unfiled_report:
                        # This is expected for unfiled reports - mark as skipped
                        self.mark_pdf_as_skipped(pdf_id, "Report not filed - unfiled report URL")
                        return None
                    else:
                        # Regular PDF URL - might be network issue, retry
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)  # Exponential backoff
                            continue
                        else:
                            # Don't mark as processed - leave for future retry
                            print(f"\n⚠️ Failed to download PDF after {max_retries} attempts: {pdf_url}")
                            return None
                else:
                    # Other status codes - retry if not last attempt
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # Network errors - retry
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    print(f"\n⚠️ Network error downloading PDF: {pdf_url}")
                    return None
            except Exception as e:
                # Unexpected error
                return None
        
        return None
    
    def mark_pdf_as_skipped(self, pdf_id: int, reason: str):
        """Mark a PDF as skipped/processed so we don't retry it"""
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {"pdf_id": f"eq.{pdf_id}"}
        update_data = {
            'csv_converted': True,
            'conversion_date': datetime.now().isoformat(),
            'error_message': reason
        }
        
        requests.patch(
            url, 
            headers=self.supabase_headers, 
            params=params,
            json=update_data
        )
    
    def process_pdf_with_r(self, pdf_path: Path, retry_count: int = 0) -> Optional[Path]:
        """Process PDF through R scraper with retry logic"""
        output_csv = PROCESSED_CSV_DIR / f"{pdf_path.stem}_donations.csv"
        max_retries = 2  # Reduced for concurrent processing
        timeout_seconds = 90 if retry_count > 0 else 60
        
        try:
            result = subprocess.run(
                ['Rscript', str(self.r_wrapper_path), str(pdf_path), str(output_csv)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            
            if result.returncode == 0 and output_csv.exists():
                return output_csv
            else:
                return None
                
        except subprocess.TimeoutExpired:
            if retry_count < max_retries:
                time.sleep(1)
                return self.process_pdf_with_r(pdf_path, retry_count + 1)
            else:
                return None
        except Exception:
            return None
    
    def parse_occupation_employer(self, occupation_str: str) -> Tuple[str, str]:
        """Parse occupation field into occupation and employer"""
        if not occupation_str or occupation_str == 'NA':
            return ('', '')
        
        if occupation_str.lower() in ['retired', 'retired, n/a', 'retired, none']:
            return ('Retired', '')
        if occupation_str.lower() in ['self', 'self-employed', 'self employed']:
            return ('Self-employed', 'Self')
        if occupation_str.lower() in ['none, none', 'n/a, n/a']:
            return ('', '')
        
        parts = occupation_str.split(',', 1)
        if len(parts) == 2:
            occupation = parts[0].strip()
            employer = parts[1].strip()
            if employer.lower() in ['n/a', 'none', 'na']:
                employer = ''
            if occupation.lower() in ['n/a', 'none', 'na']:
                occupation = ''
            return (occupation, employer)
        else:
            return (occupation_str.strip(), '')
    
    def parse_address_components(self, address_str: str) -> Dict[str, str]:
        """Parse address into components"""
        result = {
            'addr': '',
            'city': '',
            'state': '',
            'zip': '',
            'full_address': address_str if address_str and address_str != 'NA' else ''
        }
        
        if not address_str or address_str == 'NA':
            return result
        
        parts = [p.strip() for p in address_str.split(',')]
        
        # Handle 4-part addresses (street, suite/unit, city, state+zip)
        if len(parts) == 4:
            # Combine street and suite/unit into single address
            result['addr'] = f"{parts[0]} {parts[1]}"
            result['city'] = parts[2]
            
            state_zip = parts[3].strip()
            match = re.match(r'^([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$', state_zip)
            if match:
                result['state'] = match.group(1)
                result['zip'] = match.group(2)
            else:
                sz_parts = state_zip.split()
                if len(sz_parts) >= 2:
                    result['state'] = sz_parts[0][:2]
                    result['zip'] = ' '.join(sz_parts[1:])
                else:
                    result['state'] = state_zip[:2] if len(state_zip) > 2 else state_zip
        
        # Handle 3-part addresses (street, city, state+zip)
        elif len(parts) == 3:
            result['addr'] = parts[0]
            result['city'] = parts[1]
            
            state_zip = parts[2].strip()
            match = re.match(r'^([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$', state_zip)
            if match:
                result['state'] = match.group(1)
                result['zip'] = match.group(2)
            else:
                sz_parts = state_zip.split()
                if len(sz_parts) >= 2:
                    result['state'] = sz_parts[0][:2]
                    result['zip'] = ' '.join(sz_parts[1:])
                else:
                    result['state'] = state_zip[:2] if len(state_zip) > 2 else state_zip
        
        # Handle 2-part addresses (street, city)
        elif len(parts) == 2:
            result['addr'] = parts[0]
            result['city'] = parts[1]
        
        # Handle 1-part addresses (just street)
        elif len(parts) == 1:
            result['addr'] = parts[0]
        
        return result
    
    def detect_donor_type(self, donor_name: str) -> Tuple[bool, bool]:
        """Detect if donor is a PAC or corporate entity"""
        donor_upper = donor_name.upper()
        
        pac_indicators = [
            'PAC', 'POLITICAL ACTION COMMITTEE', 'COMMITTEE',
            'FOR ARIZONA', 'FOR AMERICA', 'CITIZENS FOR',
            'FRIENDS OF', 'ALLIANCE', 'COALITION'
        ]
        is_pac = any(indicator in donor_upper for indicator in pac_indicators)
        
        corp_indicators = [
            'LLC', 'INC', 'CORP', 'CORPORATION', 'COMPANY', 'CO.',
            'LTD', 'LIMITED', 'LP', 'L.P.', 'PARTNERSHIP',
            'ASSOCIATES', 'GROUP', 'HOLDINGS', 'ENTERPRISES'
        ]
        is_corporate = any(indicator in donor_upper for indicator in corp_indicators)
        
        return is_pac, is_corporate
    
    def parse_csv_date(self, date_str: str) -> Optional[str]:
        """Parse various date formats from CSV to ISO format"""
        if not date_str or date_str == 'NA' or date_str == '':
            return None
        
        formats = [
            '%m/%d/%Y',
            '%Y-%m-%d',
            '%B %d, %Y',
            '%b %d, %Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date().isoformat()
            except:
                continue
        
        return None
    
    def parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount string to float"""
        if not amount_str or amount_str == 'NA' or amount_str == '':
            return None
        
        clean_amount = amount_str.replace('$', '').replace(',', '').strip()
        
        try:
            return float(clean_amount)
        except:
            return None
    
    def create_report_record(self, csv_path: Path, entity_id: int, pdf_id: int) -> Optional[int]:
        """Create a cf_reports record from the CSV data"""
        
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            if len(lines) <= 1:
                return self.create_empty_report_record(entity_id, pdf_id)
        
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            first_row = next(reader, None)
            
            if not first_row or not any(first_row.values()):
                return self.create_empty_report_record(entity_id, pdf_id)
            
            if 'Donor_Name' not in first_row or not first_row.get('Donor_Name'):
                report_id = self.create_report_record_from_metadata_only(csv_path, entity_id, pdf_id, first_row)
                return report_id
            
            return self.create_report_record_from_data(csv_path, entity_id, pdf_id, first_row)
    
    def create_empty_report_record(self, entity_id: int, pdf_id: int, report_name: str = None) -> Optional[int]:
        """Create a placeholder report record for PDFs with no donations"""
        if not report_name:
            url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
            params = {"pdf_id": f"eq.{pdf_id}", "select": "report_name"}
            response = requests.get(url, headers=self.supabase_headers, params=params)
            if response.status_code == 200 and response.json():
                report_name = response.json()[0].get('report_name', 'Campaign Finance Report')
            else:
                report_name = 'Campaign Finance Report'
        
        report_data = {
            'pdf_id': pdf_id,
            'entity_id': entity_id,
            'rpt_title': 'Campaign Finance Report',
            'rpt_name': report_name,
            'total_donations': 0.0,
            'donation_count': 0,
            'processed_date': datetime.now().isoformat()
        }
        
        url = f"{SUPABASE_URL}/rest/v1/cf_reports"
        response = requests.post(
            url,
            headers={**self.supabase_headers, "Prefer": "return=representation"},
            json=report_data
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result and len(result) > 0:
                return result[0].get('report_id')
        
        return None
    
    def create_report_record_from_metadata_only(self, csv_path: Path, entity_id: int, pdf_id: int, first_row: dict) -> Optional[int]:
        """Create a report record when we have metadata but no donations"""
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {"pdf_id": f"eq.{pdf_id}", "select": "report_name"}
        response = requests.get(url, headers=self.supabase_headers, params=params)
        pdf_report_name = ""
        if response.status_code == 200 and response.json():
            pdf_report_name = response.json()[0].get('report_name', '')
        
        # Get raw values
        org_email = first_row.get('OrgEml', '')
        org_phone = first_row.get('OrgTel', '')
        org_address = first_row.get('OrgAdr', '')
        org_treasurer = first_row.get('OrgTreasurer', '')
        org_jurisdiction = first_row.get('Jurisdiction', 'Arizona Secretary of State')
        
        # Detect and fix shifted data pattern
        if org_email and 'Phone:' in org_email:
            # Data is shifted - fix it
            actual_phone = org_email.replace('Phone:', '').strip()
            actual_address = org_phone  # Phone field contains address
            actual_treasurer = org_address.replace('Treasurer:', '').strip() if 'Treasurer:' in org_address else org_address
            actual_jurisdiction = org_treasurer.replace('Jurisdiction:', '').strip() if 'Jurisdiction:' in org_treasurer else org_treasurer
            
            # Email is missing in shifted data, set to empty
            org_email = ''
            org_phone = actual_phone
            org_address = actual_address
            org_treasurer = actual_treasurer
            org_jurisdiction = actual_jurisdiction if actual_jurisdiction else 'Arizona Secretary of State'
        
        report_data = {
            'pdf_id': pdf_id,
            'entity_id': entity_id,
            'rpt_title': first_row.get('Rpt_Title', 'Campaign Finance Report'),
            'rpt_name': first_row.get('Rpt_Name') or pdf_report_name or 'Campaign Finance Report',
            'rpt_cycle': int(first_row.get('Rpt_Cycle')) if first_row.get('Rpt_Cycle') and str(first_row.get('Rpt_Cycle')).isdigit() else None,
            'rpt_file_date': self.parse_csv_date(first_row.get('Rpt_FileDate')),
            'rpt_period': first_row.get('Rpt_Period', ''),
            'org_name': first_row.get('OrgNm', ''),
            'org_email': org_email,
            'org_phone': org_phone,
            'org_address': org_address,
            'org_treasurer': org_treasurer,
            'org_jurisdiction': org_jurisdiction,
            'total_donations': 0.0,
            'donation_count': 0,
            'processed_date': datetime.now().isoformat()
        }
        
        report_data = {k: v for k, v in report_data.items() if v is not None}
        
        url = f"{SUPABASE_URL}/rest/v1/cf_reports"
        response = requests.post(
            url,
            headers={**self.supabase_headers, "Prefer": "return=representation"},
            json=report_data
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result and len(result) > 0:
                return result[0].get('report_id')
        
        return None
    
    def create_report_record_from_data(self, csv_path: Path, entity_id: int, pdf_id: int, first_row: dict) -> Optional[int]:
        """Create a report record from CSV data"""
        # Get raw values
        org_email = first_row.get('OrgEml', '')
        org_phone = first_row.get('OrgTel', '')
        org_address = first_row.get('OrgAdr', '')
        org_treasurer = first_row.get('OrgTreasurer', '')
        org_jurisdiction = first_row.get('Jurisdiction', 'Arizona Secretary of State')
        
        # Detect and fix shifted data pattern
        # Pattern: When email contains "Phone:", everything is shifted left by one field
        if org_email and 'Phone:' in org_email:
            # Data is shifted - fix it
            actual_phone = org_email.replace('Phone:', '').strip()
            actual_address = org_phone  # Phone field contains address
            actual_treasurer = org_address.replace('Treasurer:', '').strip() if 'Treasurer:' in org_address else org_address
            actual_jurisdiction = org_treasurer.replace('Jurisdiction:', '').strip() if 'Jurisdiction:' in org_treasurer else org_treasurer
            
            # Email is missing in shifted data, set to empty
            org_email = ''
            org_phone = actual_phone
            org_address = actual_address
            org_treasurer = actual_treasurer
            org_jurisdiction = actual_jurisdiction if actual_jurisdiction else 'Arizona Secretary of State'
        
        report_data = {
            'pdf_id': pdf_id,
            'entity_id': entity_id,
            'rpt_title': first_row.get('Rpt_Title', ''),
            'rpt_name': first_row.get('Rpt_Name', ''),
            'rpt_cycle': int(first_row.get('Rpt_Cycle')) if first_row.get('Rpt_Cycle') and first_row.get('Rpt_Cycle').isdigit() else None,
            'rpt_file_date': self.parse_csv_date(first_row.get('Rpt_FileDate')),
            'rpt_period': first_row.get('Rpt_Period', ''),
            'org_name': first_row.get('OrgNm', ''),
            'org_email': org_email,
            'org_phone': org_phone,
            'org_address': org_address,
            'org_treasurer': org_treasurer,
            'org_jurisdiction': org_jurisdiction,
            'processed_date': datetime.now().isoformat()
        }
        
        report_data = {k: v for k, v in report_data.items() if v is not None}
        
        url = f"{SUPABASE_URL}/rest/v1/cf_reports"
        response = requests.post(
            url,
            headers={**self.supabase_headers, "Prefer": "return=representation"},
            json=report_data
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result and len(result) > 0:
                report_id = result[0].get('report_id')
                self.update_report_totals(csv_path, report_id)
                return report_id
        
        return None
    
    def update_report_totals(self, csv_path: Path, report_id: int):
        """Calculate and update report totals from donations"""
        total_donations = 0.0
        donation_count = 0
        
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Donor_Name', '').strip():  # Only count actual donations
                    amount = self.parse_amount(row.get('Donation_Amt'))
                    if amount:
                        total_donations += amount
                        donation_count += 1
        
        url = f"{SUPABASE_URL}/rest/v1/cf_reports"
        params = {"report_id": f"eq.{report_id}"}
        update_data = {
            'total_donations': total_donations,
            'donation_count': donation_count
        }
        
        requests.patch(
            url,
            headers=self.supabase_headers,
            params=params,
            json=update_data
        )
    
    def upload_donations_to_supabase(self, csv_path: Path, entity_id: int, report_id: int, pdf_url: str):
        """Upload donation data from CSV to Supabase"""
        donations = []
        
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                donor_name = row.get('Donor_Name', '').strip()
                if not donor_name:
                    continue
                
                occupation, employer = self.parse_occupation_employer(row.get('Donor_Occupation', ''))
                addr_components = self.parse_address_components(row.get('Donor_Addr', ''))
                donation_date = self.parse_csv_date(row.get('Donation_Date'))
                donation_amt = self.parse_amount(row.get('Donation_Amt'))
                
                record_id = None  # Foreign key to cf_entity_records
                is_pac, is_corporate = self.detect_donor_type(donor_name)
                
                donation = {
                    'report_id': report_id,
                    'entity_id': entity_id,
                    'record_id': record_id,
                    'donor_name': donor_name,
                    'donor_addr': addr_components['addr'],
                    'donor_city': addr_components['city'],
                    'donor_state': addr_components['state'],
                    'donor_zip': addr_components['zip'],
                    'donor_full_address': addr_components.get('full_address', ''),
                    'donor_occupation': occupation,
                    'donor_employer': employer,
                    'donation_date': donation_date,
                    'donation_amt': donation_amt,
                    'donation_type': row.get('Donation_Type', ''),
                    'cycle_to_date_amt': self.parse_amount(row.get('CycleToDate_Amt')),
                    'page_num': int(row.get('PageNum')) if row.get('PageNum') and row.get('PageNum').isdigit() else None,
                    'page_type': row.get('PageType', ''),
                    'meta_segment_name': row.get('META_SegmentName', ''),
                    'meta_file_name': row.get('META_FileName', ''),
                    'donor_person_id': None,
                    'is_pac': is_pac,
                    'is_corporate': is_corporate,
                    'import_date': datetime.now().isoformat()
                }
                
                if donation['donation_amt'] is None:
                    continue
                if donation['donation_date'] is None:
                    continue
                
                donations.append(donation)
        
        if donations:
            batch_size = 100
            for i in range(0, len(donations), batch_size):
                batch = donations[i:i+batch_size]
                
                url = f"{SUPABASE_URL}/rest/v1/cf_donations"
                response = requests.post(
                    url, 
                    headers=self.supabase_headers, 
                    json=batch
                )
                
                if response.status_code not in [200, 201]:
                    return 0
        
        return len(donations)
    
    def process_pdf(self, pdf_record: Dict) -> Dict:
        """Process a single PDF through the full pipeline"""
        entity_id = pdf_record.get('entity_id')
        pdf_id = pdf_record.get('pdf_id')
        pdf_url = pdf_record.get('pdf_url')
        report_name = pdf_record.get('report_name', 'unknown')
        
        result = {
            'entity_id': entity_id,
            'pdf_id': pdf_id,
            'success': False,
            'donations': 0,
            'error': None
        }
        
        # Download PDF
        pdf_path = self.download_pdf(pdf_url, entity_id, pdf_id)
        if not pdf_path:
            # Check if it was marked as skipped (unfiled report)
            if '/ReportFile/' in pdf_url:
                result['error'] = 'Unfiled report - skipped'
                with stats_lock:
                    global_stats['skipped'] += 1
            else:
                # Regular download failure - don't mark as processed
                result['error'] = 'Download failed - will retry later'
                with stats_lock:
                    global_stats['failed'] += 1
            return result
        
        try:
            # Process with R scraper
            csv_path = self.process_pdf_with_r(pdf_path)
            if not csv_path:
                result['error'] = 'R scraper failed'
                return result
            
            # Create report record
            report_id = self.create_report_record(csv_path, entity_id, pdf_id)
            if not report_id:
                result['error'] = 'Failed to create report'
                return result
            
            # Check if CSV has actual donations
            has_donations = False
            with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('Donor_Name', '').strip():
                        has_donations = True
                        break
            
            # Upload donations if there are any
            if has_donations:
                donation_count = self.upload_donations_to_supabase(csv_path, entity_id, report_id, pdf_url)
                result['donations'] = donation_count
                with stats_lock:
                    global_stats['donations_uploaded'] += donation_count
            
            # Mark PDF as converted
            url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
            params = {"pdf_id": f"eq.{pdf_id}"}
            update_data = {
                'csv_converted': True,
                'conversion_date': datetime.now().isoformat()
            }
            
            requests.patch(
                url, 
                headers=self.supabase_headers, 
                params=params,
                json=update_data
            )
            
            result['success'] = True
            
        finally:
            # Clean up temporary PDF
            if pdf_path and pdf_path.exists():
                pdf_path.unlink(missing_ok=True)
        
        return result

def fetch_reports_from_supabase(entity_id: Optional[int] = None, limit: Optional[int] = None):
    """Fetch all unprocessed report PDFs from Supabase"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    all_pdfs = []
    offset = 0
    batch_size = 1000
    
    while True:
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {
            "select": "*",
            "pdf_url": "not.is.null",
            "csv_converted": "eq.false",
            "limit": str(batch_size),
            "offset": str(offset),
            "order": "pdf_id"
        }
        
        if entity_id:
            params["entity_id"] = f"eq.{entity_id}"
        
        if limit and len(all_pdfs) >= limit:
            all_pdfs = all_pdfs[:limit]
            break
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            batch = response.json()
            all_pdfs.extend(batch)
            
            if len(batch) < batch_size:
                break
                
            offset += batch_size
        else:
            break
    
    if limit:
        all_pdfs = all_pdfs[:limit]
    
    return all_pdfs

def worker_process_pdf(worker_id: int, pdf_record: Dict) -> Dict:
    """Worker function to process a single PDF"""
    processor = PDFDonationProcessor(worker_id)
    return processor.process_pdf(pdf_record)

def print_progress():
    """Print progress statistics"""
    with stats_lock:
        if global_stats['start_time']:
            elapsed = datetime.now() - global_stats['start_time']
            rate = global_stats['success'] / max(elapsed.total_seconds(), 1)
            remaining = global_stats['total'] - (global_stats['success'] + global_stats['failed'] + global_stats['skipped'])
            eta = timedelta(seconds=remaining / max(rate, 0.001))
            
            print(f"\r📊 Progress: {global_stats['success'] + global_stats['failed'] + global_stats['skipped']}/{global_stats['total']} | "
                  f"✅ {global_stats['success']} | ❌ {global_stats['failed']} | ⏭️ {global_stats['skipped']} | "
                  f"💰 {global_stats['donations_uploaded']} donations | "
                  f"⚡ {rate:.1f}/sec | ⏱️ ETA: {str(eta).split('.')[0]}", end='', flush=True)

def main():
    """Main execution with concurrent processing"""
    parser = argparse.ArgumentParser(description='Process Campaign Finance PDFs CONCURRENTLY')
    parser.add_argument('--entity', type=int, default=None,
                       help='Process specific entity ID only')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of PDFs to process')
    parser.add_argument('--workers', type=int, default=8,
                       help='Number of parallel workers (default: 8)')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("ARIZONA CAMPAIGN FINANCE - CONCURRENT PDF PROCESSOR")
    print("="*70)
    
    # Check R is available
    try:
        subprocess.run(['Rscript', '--version'], capture_output=True, check=True)
    except:
        print("❌ R is not installed or not in PATH")
        return
    
    # Fetch PDFs
    print(f"\n📥 Fetching unprocessed PDFs...")
    pdfs = fetch_reports_from_supabase(entity_id=args.entity, limit=args.limit)
    
    if not pdfs:
        print("No PDFs found to process")
        return
    
    print(f"✅ Found {len(pdfs)} PDFs to process")
    print(f"🔧 Using {args.workers} parallel workers")
    
    # Calculate estimates
    total_time_estimate = len(pdfs) * 5 / args.workers  # Assume 5 seconds per PDF
    print(f"⏱️  Estimated time: {timedelta(seconds=total_time_estimate)}")
    
    # Initialize stats
    with stats_lock:
        global_stats['total'] = len(pdfs)
        global_stats['start_time'] = datetime.now()
    
    print("\n" + "="*70)
    print("Processing PDFs...")
    print("="*70 + "\n")
    
    # Process PDFs concurrently
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_pdf = {
            executor.submit(worker_process_pdf, i % args.workers, pdf): pdf 
            for i, pdf in enumerate(pdfs)
        }
        
        # Process completed tasks
        for future in as_completed(future_to_pdf):
            if shutdown_requested:
                executor.shutdown(wait=False)
                break
                
            pdf = future_to_pdf[future]
            try:
                result = future.result()
                with stats_lock:
                    if result['success']:
                        global_stats['success'] += 1
                    elif result['error'] and '404' in result['error']:
                        pass  # Already counted in skipped
                    else:
                        global_stats['failed'] += 1
            except Exception as e:
                with stats_lock:
                    global_stats['failed'] += 1
            
            # Print progress every 10 PDFs
            total_processed = global_stats['success'] + global_stats['failed'] + global_stats['skipped']
            if total_processed % 10 == 0:
                print_progress()
    
    # Final statistics
    print("\n\n" + "="*70)
    print("📈 FINAL STATISTICS")
    print("="*70)
    
    with stats_lock:
        elapsed = datetime.now() - global_stats['start_time']
        print(f"  Total PDFs: {global_stats['total']}")
        print(f"  Successfully processed: {global_stats['success']}")
        print(f"  Failed: {global_stats['failed']}")
        print(f"  Skipped (404s): {global_stats['skipped']}")
        print(f"  Total donations uploaded: {global_stats['donations_uploaded']}")
        print(f"  Total time: {str(elapsed).split('.')[0]}")
        print(f"  Average rate: {(global_stats['success'] + global_stats['failed'] + global_stats['skipped']) / elapsed.total_seconds():.2f} PDFs/second")
    
    print("\n" + "="*70)
    print("PROCESSING COMPLETE!")
    print("="*70)

if __name__ == "__main__":
    main()