#!/usr/bin/env python3
"""
Arizona Campaign Finance Scraper - Step 3 FIXED: Process PDFs through R Scraper
This version properly creates cf_reports records before cf_donations records.
"""

import os
import subprocess
import time
import csv
import requests
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse
import json

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

class PDFDonationProcessor:
    """Process PDFs through R scraper and upload to Supabase"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        self.supabase_headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Create R wrapper script
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

# Source the scraper function

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
        
        self.r_wrapper_path = OUTPUT_DIR / "pdf_scraper_wrapper.R"
        with open(self.r_wrapper_path, 'w') as f:
            f.write(r_wrapper_content)
    
    def fetch_reports_from_supabase(self, entity_id: Optional[int] = None, limit: Optional[int] = None):
        """Fetch report PDFs from Supabase with pagination"""
        all_pdfs = []
        offset = 0
        batch_size = 1000  # Supabase max
        
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
            
            # Override with user limit if specified and we've fetched enough
            if limit and len(all_pdfs) >= limit:
                all_pdfs = all_pdfs[:limit]
                break
            
            response = requests.get(url, headers=self.supabase_headers, params=params)
            
            if response.status_code == 200:
                batch = response.json()
                all_pdfs.extend(batch)
                
                # Check if we got all records or hit user limit
                if len(batch) < batch_size:
                    break
                    
                offset += batch_size
                if len(all_pdfs) > 1000:
                    print(f"  Fetched {len(all_pdfs)} PDFs so far...")
            else:
                print(f"❌ Failed to fetch PDFs: {response.text}")
                break
        
        # Apply user limit if specified
        if limit:
            all_pdfs = all_pdfs[:limit]
        
        print(f"✅ Found {len(all_pdfs)} PDFs to process")
        return all_pdfs
    
    def download_pdf(self, pdf_url: str, entity_id: int, pdf_id: int) -> Optional[Path]:
        """Download a PDF to temporary directory"""
        try:
            response = self.session.get(pdf_url, timeout=30)
            if response.status_code == 200:
                # Create a safe filename
                safe_name = f"entity_{entity_id}_pdf_{pdf_id}.pdf"
                pdf_path = TEMP_PDF_DIR / safe_name
                
                with open(pdf_path, 'wb') as f:
                    f.write(response.content)
                
                return pdf_path
            elif response.status_code == 404:
                print(f"  ⏭️  Skipping - Report not filed (404)")
                # Mark as "converted" so we don't retry it
                self.mark_pdf_as_skipped(pdf_id, "Report not filed - 404")
                return None
            else:
                print(f"  ❌ Failed to download PDF: {response.status_code}")
                return None
        except Exception as e:
            print(f"  ❌ Error downloading PDF: {e}")
            return None
    
    def mark_pdf_as_skipped(self, pdf_id: int, reason: str):
        """Mark a PDF as skipped/processed so we don't retry it"""
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {"pdf_id": f"eq.{pdf_id}"}
        update_data = {
            'csv_converted': True,  # Mark as "converted" to skip in future runs
            'conversion_date': datetime.now().isoformat(),
            'error_message': reason  # Store the skip reason
        }
        
        response = requests.patch(
            url, 
            headers=self.supabase_headers, 
            params=params,
            json=update_data
        )
    
    def process_pdf_with_r(self, pdf_path: Path, retry_count: int = 0) -> Optional[Path]:
        """Process PDF through R scraper with retry logic"""
        output_csv = PROCESSED_CSV_DIR / f"{pdf_path.stem}_donations.csv"
        max_retries = 3
        timeout_seconds = 90 if retry_count > 0 else 60  # Increase timeout on retry
        
        try:
            # Call R script
            result = subprocess.run(
                ['Rscript', str(self.r_wrapper_path), str(pdf_path), str(output_csv)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            
            if result.returncode == 0 and output_csv.exists():
                print(f"  ✅ R scraper succeeded: {result.stdout.strip()}")
                
                # Detect what schedules are in this PDF
                self.detect_schedules_in_pdf(pdf_path)
                
                return output_csv
            else:
                # Print both stdout and stderr for debugging
                print(f"  ⚠️ R scraper failed")
                if result.stdout:
                    print(f"     Output: {result.stdout.strip()}")
                if result.stderr:
                    print(f"     Error: {result.stderr.strip()}")
                return None
                
        except subprocess.TimeoutExpired:
            if retry_count < max_retries:
                print(f"  ⏱️ R scraper timed out (attempt {retry_count + 1}/{max_retries + 1}), retrying with {timeout_seconds + 30}s timeout...")
                time.sleep(2)  # Brief pause before retry
                return self.process_pdf_with_r(pdf_path, retry_count + 1)
            else:
                print(f"  ❌ R scraper timed out after {max_retries + 1} attempts")
                return None
        except Exception as e:
            print(f"  ❌ Error running R scraper: {e}")
            return None
    
    def detect_schedules_in_pdf(self, pdf_path: Path):
        """Detect what schedules are present in the PDF"""
        try:
            import pdfplumber
            
            schedules_found = set()
            schedule_patterns = {
                'C1': 'Personal and Family Contributions',
                'C2': 'Individual Contributions',
                'C3': 'Political Committee Contributions', 
                'C4': 'Business Contributions',
                'C5': 'Small Contributions',
                'C6': 'CCEC Funding',
                'C7': 'Qualifying Contributions',
                'E1': 'Operating Expenses',
                'E2': 'Independent Expenditures',
                'E3': 'Contributions to Committees',
                'E4': 'Small Expenses',
                'L1': 'Loans Received',
                'L2': 'Loans Made',
                'R1': 'Other Receipts',
                'T1': 'Transfers',
                'S1': 'Surplus',
                'D1': 'Bill Payments'
            }
            
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        for schedule, description in schedule_patterns.items():
                            if f"Schedule {schedule}" in text:
                                schedules_found.add(f"{schedule} ({description})")
            
            if schedules_found:
                print(f"     📊 Schedules found: {', '.join(sorted(schedules_found))}")
            else:
                print(f"     📊 No standard schedules found (may be NO ACTIVITY report)")
                
        except ImportError:
            # If pdfplumber not installed, use pdftools via subprocess
            try:
                result = subprocess.run(
                    ['pdftotext', str(pdf_path), '-'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    text = result.stdout
                    schedules_found = set()
                    
                    for schedule in ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 
                                    'E1', 'E2', 'E3', 'E4', 'L1', 'L2', 'R1', 
                                    'T1', 'S1', 'D1']:
                        if f"Schedule {schedule}" in text:
                            schedules_found.add(schedule)
                    
                    if schedules_found:
                        print(f"     📊 Schedules detected: {', '.join(sorted(schedules_found))}")
                        if 'C2' not in schedules_found:
                            print(f"     ⚠️  WARNING: No C2 schedule - no individual donations will be extracted")
                        if any(s in schedules_found for s in ['E1', 'E2', 'E3', 'E4']):
                            print(f"     ℹ️  NOTE: Expense schedules detected but not yet extracted")
            except:
                pass
    
    def parse_occupation_employer(self, occupation_str: str) -> Tuple[str, str]:
        """
        Parse occupation field into occupation and employer
        Format: "Occupation, Employer" -> ("Occupation", "Employer")
        """
        if not occupation_str or occupation_str == 'NA':
            return ('', '')
        
        # Handle special cases
        if occupation_str.lower() in ['retired', 'retired, n/a', 'retired, none']:
            return ('Retired', '')
        if occupation_str.lower() in ['self', 'self-employed', 'self employed']:
            return ('Self-employed', 'Self')
        if occupation_str.lower() in ['none, none', 'n/a, n/a']:
            return ('', '')
        
        # Split on comma
        parts = occupation_str.split(',', 1)
        if len(parts) == 2:
            occupation = parts[0].strip()
            employer = parts[1].strip()
            # Clean up common patterns
            if employer.lower() in ['n/a', 'none', 'na']:
                employer = ''
            if occupation.lower() in ['n/a', 'none', 'na']:
                occupation = ''
            return (occupation, employer)
        else:
            # No comma, treat entire string as occupation
            return (occupation_str.strip(), '')
    
    def parse_address_components(self, address_str: str) -> Dict[str, str]:
        """
        Parse address into components
        Format: "123 Main St, Phoenix, AZ 85001" -> 
        {addr: "123 Main St", city: "Phoenix", state: "AZ", zip: "85001"}
        """
        result = {
            'addr': '',
            'city': '',
            'state': '',
            'zip': ''
        }
        
        if not address_str or address_str == 'NA':
            return result
        
        # Split by comma
        parts = [p.strip() for p in address_str.split(',')]
        
        if len(parts) >= 3:
            # Standard format: street, city, state zip
            result['addr'] = parts[0]
            result['city'] = parts[1]
            
            # Parse state and zip from last part
            state_zip = parts[2].strip()
            # Match state (2 letters) and zip (5 or 9 digits)
            match = re.match(r'^([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$', state_zip)
            if match:
                result['state'] = match.group(1)
                result['zip'] = match.group(2)
            else:
                # Try to split on space
                sz_parts = state_zip.split()
                if len(sz_parts) >= 2:
                    result['state'] = sz_parts[0][:2]  # Limit to 2 chars for state
                    result['zip'] = ' '.join(sz_parts[1:])
                else:
                    result['state'] = state_zip[:2] if len(state_zip) > 2 else state_zip
        elif len(parts) == 2:
            # Might be missing state/zip or city
            result['addr'] = parts[0]
            result['city'] = parts[1]
        elif len(parts) == 1:
            # Just street address
            result['addr'] = parts[0]
        
        return result
    
    def generate_record_id(self, entity_id: int, donor_name: str, date: str, amount: float) -> str:
        """
        Generate a unique record ID for a donation
        Uses hash of key fields to ensure consistency
        """
        # Create a unique string from the donation details
        unique_str = f"{entity_id}|{donor_name}|{date}|{amount}"
        # Generate hash
        hash_obj = hashlib.md5(unique_str.encode())
        # Return first 12 characters of hex digest
        return hash_obj.hexdigest()[:12]
    
    def detect_donor_type(self, donor_name: str) -> Tuple[bool, bool]:
        """
        Detect if donor is a PAC or corporate entity
        Returns: (is_pac, is_corporate)
        """
        donor_upper = donor_name.upper()
        
        # PAC indicators
        pac_indicators = [
            'PAC', 'POLITICAL ACTION COMMITTEE', 'COMMITTEE',
            'FOR ARIZONA', 'FOR AMERICA', 'CITIZENS FOR',
            'FRIENDS OF', 'ALLIANCE', 'COALITION'
        ]
        is_pac = any(indicator in donor_upper for indicator in pac_indicators)
        
        # Corporate indicators
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
        
        # Try different date formats
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
        
        # Remove $ and commas
        clean_amount = amount_str.replace('$', '').replace(',', '').strip()
        
        try:
            return float(clean_amount)
        except:
            return None
    
    def create_report_record(self, csv_path: Path, entity_id: int, pdf_id: int) -> Optional[int]:
        """Create a cf_reports record from the CSV data"""
        
        # Check if CSV is empty or has no data rows
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            # CSV with only header or no content = empty report
            if len(lines) <= 1:
                print("    📋 Empty report (no donations) - creating placeholder record")
                return self.create_empty_report_record(entity_id, pdf_id)
        
        # Read first row to get report metadata
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            first_row = next(reader, None)
            
            if not first_row or not any(first_row.values()):
                print("    📋 Empty report (no donations) - creating placeholder record")
                return self.create_empty_report_record(entity_id, pdf_id)
            
            # Check if this is a report with only metadata (no donation fields)
            if 'Donor_Name' not in first_row or not first_row.get('Donor_Name'):
                # Has metadata but no donations
                print("    📋 Report has metadata but no donations")
                report_id = self.create_report_record_from_metadata_only(csv_path, entity_id, pdf_id, first_row)
                # Don't try to upload donations when there are none
                return report_id
            
            # If we have data, create report from it
            return self.create_report_record_from_data(csv_path, entity_id, pdf_id, first_row)
    
    def create_empty_report_record(self, entity_id: int, pdf_id: int, report_name: str = None) -> Optional[int]:
        """Create a placeholder report record for PDFs with no donations"""
        # Try to get report name from the PDF if possible
        if not report_name:
            # Try to fetch from cf_report_pdfs table
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
        
        # Insert report and get the ID
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
                print(f"    ✅ Created empty report record ID: {report_id}")
                return report_id
        
        print(f"    ❌ Failed to create empty report: {response.text}")
        return None
    
    def create_report_record_from_metadata_only(self, csv_path: Path, entity_id: int, pdf_id: int, first_row: dict) -> Optional[int]:
        """Create a report record when we have metadata but no donations"""
        # Fetch actual report name from cf_report_pdfs
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {"pdf_id": f"eq.{pdf_id}", "select": "report_name"}
        response = requests.get(url, headers=self.supabase_headers, params=params)
        pdf_report_name = ""
        if response.status_code == 200 and response.json():
            pdf_report_name = response.json()[0].get('report_name', '')
        
        # Use metadata from the CSV (even though no donations)
        report_data = {
            'pdf_id': pdf_id,
            'entity_id': entity_id,
            'rpt_title': first_row.get('Rpt_Title', 'Campaign Finance Report'),
            'rpt_name': first_row.get('Rpt_Name') or pdf_report_name or 'Campaign Finance Report',
            'rpt_cycle': int(first_row.get('Rpt_Cycle')) if first_row.get('Rpt_Cycle') and str(first_row.get('Rpt_Cycle')).isdigit() else None,
            'rpt_file_date': self.parse_csv_date(first_row.get('Rpt_FileDate')),
            'rpt_period': first_row.get('Rpt_Period', ''),
            'org_name': first_row.get('OrgNm', ''),
            'org_email': first_row.get('OrgEml', ''),
            'org_phone': first_row.get('OrgTel', ''),
            'org_address': first_row.get('OrgAdr', ''),
            'org_treasurer': first_row.get('OrgTreasurer', ''),
            'org_jurisdiction': first_row.get('Jurisdiction', 'Arizona Secretary of State'),
            'total_donations': 0.0,
            'donation_count': 0,
            'processed_date': datetime.now().isoformat()
        }
        
        # Filter out None values
        report_data = {k: v for k, v in report_data.items() if v is not None}
        
        # Insert report
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
                print(f"    ✅ Created report record ID: {report_id} (metadata only, no donations)")
                return report_id
        
        print(f"    ❌ Failed to create report: {response.text}")
        return None
    
    def create_report_record_from_data(self, csv_path: Path, entity_id: int, pdf_id: int, first_row: dict) -> Optional[int]:
        """Create a report record from CSV data"""
        # Create report record
        report_data = {
            'pdf_id': pdf_id,
            'entity_id': entity_id,
            'rpt_title': first_row.get('Rpt_Title', ''),
            'rpt_name': first_row.get('Rpt_Name', ''),
            'rpt_cycle': int(first_row.get('Rpt_Cycle')) if first_row.get('Rpt_Cycle') and first_row.get('Rpt_Cycle').isdigit() else None,
            'rpt_file_date': self.parse_csv_date(first_row.get('Rpt_FileDate')),
            'rpt_period': first_row.get('Rpt_Period', ''),
            'org_name': first_row.get('OrgNm', ''),
            'org_email': first_row.get('OrgEml', ''),
            'org_phone': first_row.get('OrgTel', ''),
            'org_address': first_row.get('OrgAdr', ''),
            'org_treasurer': first_row.get('OrgTreasurer', ''),
            'org_jurisdiction': first_row.get('Jurisdiction', 'Arizona Secretary of State'),
            'processed_date': datetime.now().isoformat()
        }
        
        # Filter out None values
        report_data = {k: v for k, v in report_data.items() if v is not None}
        
        # Insert report and get the ID
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
                print(f"    ✅ Created report record ID: {report_id}")
                
                # Calculate totals from CSV for the report
                self.update_report_totals(csv_path, report_id)
                
                return report_id
            else:
                print(f"    ❌ Failed to get report ID from response")
                return None
        else:
            print(f"    ❌ Failed to create report: {response.text}")
            return None
    
    def update_report_totals(self, csv_path: Path, report_id: int):
        """Calculate and update report totals from donations"""
        total_donations = 0.0
        donation_count = 0
        
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                amount = self.parse_amount(row.get('Donation_Amt'))
                if amount:
                    total_donations += amount
                    donation_count += 1
        
        # Update report with totals
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
        
        # Read and parse CSV
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # SKIP ROWS WITHOUT DONOR NAME (metadata rows)
                donor_name = row.get('Donor_Name', '').strip()
                if not donor_name:
                    continue
                
                # Parse occupation and employer
                occupation, employer = self.parse_occupation_employer(row.get('Donor_Occupation', ''))
                
                # Parse address components
                addr_components = self.parse_address_components(row.get('Donor_Addr', ''))
                
                # Parse dates and amounts
                donation_date = self.parse_csv_date(row.get('Donation_Date'))
                donation_amt = self.parse_amount(row.get('Donation_Amt'))
                
                # Generate record ID (set to None - it's a foreign key to cf_entity_records)
                # The hash-based record_id was for deduplication, but the DB expects an integer FK
                record_id = None  # Will be NULL unless we match to cf_entity_records later
                
                # Detect donor type (PAC or corporate)
                is_pac, is_corporate = self.detect_donor_type(donor_name)
                
                donation = {
                    'report_id': report_id,  # Link to the report we just created
                    'entity_id': entity_id,
                    'record_id': record_id,
                    'donor_name': donor_name,
                    'donor_addr': addr_components['addr'],
                    'donor_city': addr_components['city'],
                    'donor_state': addr_components['state'],
                    'donor_zip': addr_components['zip'],
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
                    'donor_person_id': None,  # Will be populated by entity matching later
                    'is_pac': is_pac,
                    'is_corporate': is_corporate,
                    'import_date': datetime.now().isoformat()
                }
                
                # Don't filter out fields - keep all keys for consistency
                # Just convert None to appropriate defaults for non-nullable fields
                if donation['donation_amt'] is None:
                    continue  # Skip donations without amounts
                if donation['donation_date'] is None:
                    continue  # Skip donations without dates
                donations.append(donation)
        
        if donations:
            # Upload in batches of 100
            batch_size = 100
            for i in range(0, len(donations), batch_size):
                batch = donations[i:i+batch_size]
                
                url = f"{SUPABASE_URL}/rest/v1/cf_donations"
                response = requests.post(
                    url, 
                    headers=self.supabase_headers, 
                    json=batch
                )
                
                if response.status_code in [200, 201]:
                    print(f"    ✅ Uploaded {len(batch)} donations to Supabase")
                else:
                    print(f"    ❌ Failed to upload donations: {response.text}")
        
        return len(donations)
    
    def process_pdf(self, pdf_record: Dict) -> bool:
        """Process a single PDF through the full pipeline"""
        entity_id = pdf_record.get('entity_id')
        pdf_id = pdf_record.get('pdf_id')
        pdf_url = pdf_record.get('pdf_url')
        report_name = pdf_record.get('report_name', 'unknown')
        
        print(f"\n📄 Processing: Entity {entity_id} - PDF {pdf_id} - {report_name}")
        
        # Download PDF
        pdf_path = self.download_pdf(pdf_url, entity_id, pdf_id)
        if not pdf_path:
            return False
        
        # Process with R scraper
        csv_path = self.process_pdf_with_r(pdf_path)
        if not csv_path:
            # Clean up PDF
            pdf_path.unlink(missing_ok=True)
            return False
        
        # Create report record FIRST
        report_id = self.create_report_record(csv_path, entity_id, pdf_id)
        if not report_id:
            print("    ❌ Failed to create report record")
            pdf_path.unlink(missing_ok=True)
            return False
        
        # Check if CSV has actual donations (not just metadata)
        has_donations = False
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Donor_Name', '').strip():
                    has_donations = True
                    break
        
        # Upload donations only if there are actual donations
        if has_donations:
            donation_count = self.upload_donations_to_supabase(csv_path, entity_id, report_id, pdf_url)
        else:
            donation_count = 0
        
        # Mark PDF as converted
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {"pdf_id": f"eq.{pdf_id}"}
        update_data = {
            'csv_converted': True,
            'conversion_date': datetime.now().isoformat()
        }
        
        response = requests.patch(
            url, 
            headers=self.supabase_headers, 
            params=params,
            json=update_data
        )
        
        # Clean up temporary PDF (keep CSV for review)
        pdf_path.unlink(missing_ok=True)
        
        print(f"    ✅ Complete: Report {report_id} with {donation_count} donations")
        return True

def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Process Campaign Finance PDFs with proper report creation')
    parser.add_argument('--entity', type=int, default=None,
                       help='Process specific entity ID only')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of PDFs to process')
    parser.add_argument('--pdf-id', type=int, default=None,
                       help='Process specific PDF ID only')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("ARIZONA CAMPAIGN FINANCE - PROCESS PDFs (FIXED VERSION)")
    print("="*70)
    
    # Check R is available
    try:
        subprocess.run(['Rscript', '--version'], capture_output=True, check=True)
    except:
        print("❌ R is not installed or not in PATH")
        print("Please install R and ensure Rscript is available")
        return
    
    # Process reports
    processor = PDFDonationProcessor()
    
    # Fetch PDFs from Supabase
    pdfs = processor.fetch_reports_from_supabase(
        entity_id=args.entity, 
        limit=args.limit
    )
    
    # Filter by specific PDF if requested
    if args.pdf_id:
        pdfs = [p for p in pdfs if p.get('pdf_id') == args.pdf_id]
        if not pdfs:
            print(f"❌ PDF ID {args.pdf_id} not found or already converted")
            return
    
    if not pdfs:
        print("No PDFs found to process")
        return
    
    stats = {
        'total': len(pdfs),
        'success': 0,
        'failed': 0
    }
    
    for i, pdf_record in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}]", end='')
        
        if processor.process_pdf(pdf_record):
            stats['success'] += 1
        else:
            stats['failed'] += 1
        
        # Rate limiting
        time.sleep(0.5)
    
    # Print statistics
    print("\n\n📈 Final Statistics:")
    print(f"  Total PDFs: {stats['total']}")
    print(f"  Successfully processed: {stats['success']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  CSV files saved in: {PROCESSED_CSV_DIR}")
    
    print("\n" + "="*70)
    print("PROCESSING COMPLETE!")
    print("="*70)

if __name__ == "__main__":
    main()