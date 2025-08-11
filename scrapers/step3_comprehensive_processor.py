#!/usr/bin/env python3
"""
Arizona Campaign Finance Comprehensive Schedule Processor
Processes ALL schedule types from campaign finance PDFs
"""

import os
import subprocess
import time
import csv
import requests
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

class ComprehensiveScheduleProcessor:
    """Process all schedule types from campaign finance PDFs"""
    
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
        
        # Create R wrapper for comprehensive extractor
        self._create_comprehensive_r_wrapper()
        
        # Track processing statistics
        self.stats = {
            'schedules_found': {},
            'records_processed': {},
            'upload_errors': []
        }
    
    def _create_comprehensive_r_wrapper(self):
        """Create R wrapper that calls the comprehensive extractor"""
        r_wrapper_content = '''
# Comprehensive R Wrapper for All Schedules
args <- commandArgs(trailingOnly = TRUE)
pdf_path <- args[1]
output_base <- args[2]

# Load required libraries
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

# Source the comprehensive extractor
source("/Users/jordanharb/Documents/az-campaign-finance/scrapers/comprehensive_schedule_extractor.R")

# Process the PDF
tryCatch({
    result <- COMPREHENSIVE_EXTRACTOR(pdf_path)
    
    # The extractor handles saving CSVs and reporting
    # Just need to call it
    
}, error = function(e) {
    cat("ERROR:", e$message, "\\n")
    quit(status = 1)
})
'''
        
        self.r_wrapper_path = OUTPUT_DIR / "comprehensive_wrapper.R"
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
                safe_name = f"entity_{entity_id}_pdf_{pdf_id}.pdf"
                pdf_path = TEMP_PDF_DIR / safe_name
                
                with open(pdf_path, 'wb') as f:
                    f.write(response.content)
                
                return pdf_path
            elif response.status_code == 404:
                print(f"  ⏭️  Skipping - Report not filed (404)")
                self.mark_pdf_as_skipped(pdf_id, "Report not filed - 404")
                return None
            else:
                print(f"  ❌ Failed to download PDF: {response.status_code}")
                return None
        except Exception as e:
            print(f"  ❌ Error downloading PDF: {e}")
            return None
    
    def mark_pdf_as_skipped(self, pdf_id: int, reason: str):
        """Mark a PDF as skipped/processed"""
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {"pdf_id": f"eq.{pdf_id}"}
        update_data = {
            'csv_converted': True,
            'conversion_date': datetime.now().isoformat(),
            'error_message': reason
        }
        
        requests.patch(url, headers=self.supabase_headers, params=params, json=update_data)
    
    def process_pdf_with_comprehensive_extractor(self, pdf_path: Path) -> Dict[str, Path]:
        """Process PDF through comprehensive R extractor"""
        output_base = PROCESSED_CSV_DIR / pdf_path.stem
        csv_files = {}
        
        try:
            # Call comprehensive R script
            result = subprocess.run(
                ['Rscript', str(self.r_wrapper_path), str(pdf_path), str(output_base)],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                print(f"  ✅ Comprehensive extraction succeeded")
                
                # Parse output to see what was extracted
                for line in result.stdout.split('\n'):
                    if 'SCHEDULES FOUND:' in line:
                        schedules = line.replace('SCHEDULES FOUND:', '').strip()
                        print(f"     📊 Schedules detected: {schedules}")
                    elif 'SAVED:' in line:
                        print(f"     💾 {line}")
                
                # Check for created CSV files
                schedule_types = {
                    'c1_personal': 'cf_personal_contributions',
                    'c2_donations': 'cf_donations',
                    'c3_committees': 'cf_committee_contributions',
                    'c4_business': 'cf_business_contributions',
                    'c5_small': 'cf_small_contributions',
                    'e1_expenses': 'cf_operating_expenses',
                    'e2_independent': 'cf_independent_expenditures',
                    'e3_contributions': 'cf_contributions_made',
                    'e4_small_expenses': 'cf_small_expenses',
                    'l1_loans_received': 'cf_loans_received',
                    'l2_loans_made': 'cf_loans_made',
                    'metadata': None
                }
                
                for suffix, table in schedule_types.items():
                    csv_path = Path(f"{output_base}_{suffix}.csv")
                    if csv_path.exists():
                        csv_files[suffix] = csv_path
                        if table:
                            self.stats['schedules_found'][table] = \
                                self.stats['schedules_found'].get(table, 0) + 1
                
                return csv_files
            else:
                print(f"  ⚠️ R extractor failed")
                if result.stdout:
                    print(f"     Output: {result.stdout.strip()}")
                if result.stderr:
                    print(f"     Error: {result.stderr.strip()}")
                return {}
                
        except subprocess.TimeoutExpired:
            print("  ❌ R extractor timed out")
            return {}
        except Exception as e:
            print(f"  ❌ Error running R extractor: {e}")
            return {}
    
    def create_report_record(self, metadata_csv: Path, entity_id: int, pdf_id: int) -> Optional[int]:
        """Create a cf_reports record from metadata"""
        with open(metadata_csv, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            metadata = next(reader, {})
        
        report_data = {
            'pdf_id': pdf_id,
            'entity_id': entity_id,
            'rpt_title': metadata.get('ReportTitle', 'Campaign Finance Report'),
            'rpt_name': metadata.get('ReportName', ''),
            'rpt_cycle': metadata.get('Cycle', ''),
            'rpt_file_date': self.parse_date(metadata.get('FileDate')),
            'rpt_period': metadata.get('ReportPeriod', ''),
            'org_name': metadata.get('OrgName', ''),
            'org_email': metadata.get('OrgEmail', ''),
            'org_phone': metadata.get('OrgPhone', ''),
            'org_address': metadata.get('OrgAddr', ''),
            'org_treasurer': metadata.get('TreasurerName', ''),
            'org_jurisdiction': metadata.get('Jurisdiction', 'Arizona Secretary of State'),
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
                print(f"    ✅ Created report record ID: {report_id}")
                return report_id
        
        print(f"    ❌ Failed to create report: {response.text}")
        return None
    
    def parse_date(self, date_str: str) -> Optional[str]:
        """Parse various date formats to ISO format"""
        if not date_str or date_str == 'NA' or date_str == '':
            return None
        
        formats = ['%B %d, %Y', '%b %d, %Y', '%m/%d/%Y', '%Y-%m-%d']
        
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
    
    def upload_schedule_c1(self, csv_path: Path, report_id: int, entity_id: int):
        """Upload Schedule C1 - Personal/Family Contributions"""
        records = []
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                record = {
                    'report_id': report_id,
                    'entity_id': entity_id,
                    'contributor_name': row.get('Contributor_Name', ''),
                    'contributor_relationship': row.get('Relationship', ''),
                    'contribution_date': self.parse_date(row.get('Contribution_Date')),
                    'contribution_amt': self.parse_amount(row.get('Contribution_Amt')),
                    'page_num': int(row.get('PageNum')) if row.get('PageNum') else None
                }
                records.append({k: v for k, v in record.items() if v is not None})
        
        if records:
            url = f"{SUPABASE_URL}/rest/v1/cf_personal_contributions"
            response = requests.post(url, headers=self.supabase_headers, json=records)
            if response.status_code in [200, 201]:
                print(f"        ✅ Uploaded {len(records)} personal contributions")
                self.stats['records_processed']['c1'] = self.stats['records_processed'].get('c1', 0) + len(records)
            else:
                print(f"        ❌ Failed to upload personal contributions: {response.text[:200]}")
    
    def upload_schedule_c2(self, csv_path: Path, report_id: int, entity_id: int):
        """Upload Schedule C2 - Individual Donations (existing logic)"""
        donations = []
        
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows without donor names (metadata rows)
                if not row.get('Donor_Name'):
                    continue
                    
                donation = {
                    'report_id': report_id,
                    'entity_id': entity_id,
                    'donor_name': row.get('Donor_Name', ''),
                    'donor_addr': row.get('Donor_Addr', ''),
                    'donor_occupation': row.get('Donor_Occupation', ''),
                    'donation_date': self.parse_date(row.get('Donation_Date')),
                    'donation_amt': self.parse_amount(row.get('Donation_Amt')),
                    'donation_type': row.get('Donation_Type', ''),
                    'cycle_to_date_amt': self.parse_amount(row.get('CycleToDate_Amt')),
                    'page_num': int(row.get('PageNum')) if row.get('PageNum') else None,
                    'import_date': datetime.now().isoformat()
                }
                
                donations.append({k: v for k, v in donation.items() if v is not None})
        
        if donations:
            # Upload in batches
            batch_size = 100
            for i in range(0, len(donations), batch_size):
                batch = donations[i:i+batch_size]
                url = f"{SUPABASE_URL}/rest/v1/cf_donations"
                response = requests.post(url, headers=self.supabase_headers, json=batch)
                
                if response.status_code in [200, 201]:
                    print(f"        ✅ Uploaded {len(batch)} individual donations")
                    self.stats['records_processed']['c2'] = self.stats['records_processed'].get('c2', 0) + len(batch)
                else:
                    print(f"        ❌ Failed to upload donations: {response.text[:200]}")
    
    def upload_schedule_c3(self, csv_path: Path, report_id: int, entity_id: int):
        """Upload Schedule C3 - Committee Contributions"""
        records = []
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                record = {
                    'report_id': report_id,
                    'entity_id': entity_id,
                    'committee_name': row.get('Committee_Name', ''),
                    'committee_id_number': row.get('Committee_ID', ''),
                    'committee_address': row.get('Committee_Address', ''),
                    'contribution_date': self.parse_date(row.get('Contribution_Date')),
                    'contribution_amt': self.parse_amount(row.get('Contribution_Amt')),
                    'page_num': int(row.get('PageNum')) if row.get('PageNum') else None
                }
                records.append({k: v for k, v in record.items() if v is not None})
        
        if records:
            url = f"{SUPABASE_URL}/rest/v1/cf_committee_contributions"
            response = requests.post(url, headers=self.supabase_headers, json=records)
            if response.status_code in [200, 201]:
                print(f"        ✅ Uploaded {len(records)} committee contributions")
                self.stats['records_processed']['c3'] = self.stats['records_processed'].get('c3', 0) + len(records)
            else:
                print(f"        ❌ Failed to upload committee contributions: {response.text[:200]}")
    
    def upload_schedule_e1(self, csv_path: Path, report_id: int, entity_id: int):
        """Upload Schedule E1 - Operating Expenses"""
        records = []
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                record = {
                    'report_id': report_id,
                    'entity_id': entity_id,
                    'payee_name': row.get('Payee_Name', ''),
                    'payee_address': row.get('Payee_Address', ''),
                    'expense_date': self.parse_date(row.get('Expense_Date')),
                    'expense_amt': self.parse_amount(row.get('Expense_Amt')),
                    'expense_purpose': row.get('Purpose', ''),
                    'expense_category': row.get('Category', ''),
                    'page_num': int(row.get('PageNum')) if row.get('PageNum') else None
                }
                records.append({k: v for k, v in record.items() if v is not None})
        
        if records:
            url = f"{SUPABASE_URL}/rest/v1/cf_operating_expenses"
            response = requests.post(url, headers=self.supabase_headers, json=records)
            if response.status_code in [200, 201]:
                print(f"        ✅ Uploaded {len(records)} operating expenses")
                self.stats['records_processed']['e1'] = self.stats['records_processed'].get('e1', 0) + len(records)
            else:
                print(f"        ❌ Failed to upload operating expenses: {response.text[:200]}")
    
    def upload_schedule_e2(self, csv_path: Path, report_id: int, entity_id: int):
        """Upload Schedule E2 - Independent Expenditures"""
        records = []
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                record = {
                    'report_id': report_id,
                    'entity_id': entity_id,
                    'payee_name': row.get('Payee_Name', ''),
                    'expense_date': self.parse_date(row.get('Expense_Date')),
                    'expense_amt': self.parse_amount(row.get('Expense_Amt')),
                    'candidate_name': row.get('Candidate_Name', ''),
                    'support_or_oppose': row.get('Support_Oppose', ''),
                    'page_num': int(row.get('PageNum')) if row.get('PageNum') else None
                }
                records.append({k: v for k, v in record.items() if v is not None})
        
        if records:
            url = f"{SUPABASE_URL}/rest/v1/cf_independent_expenditures"
            response = requests.post(url, headers=self.supabase_headers, json=records)
            if response.status_code in [200, 201]:
                print(f"        ✅ Uploaded {len(records)} independent expenditures")
                self.stats['records_processed']['e2'] = self.stats['records_processed'].get('e2', 0) + len(records)
            else:
                print(f"        ❌ Failed to upload independent expenditures: {response.text[:200]}")
    
    def upload_all_schedules(self, csv_files: Dict[str, Path], report_id: int, entity_id: int):
        """Upload all extracted schedules to their respective tables"""
        
        # Map CSV suffixes to upload functions
        upload_functions = {
            'c1_personal': self.upload_schedule_c1,
            'c2_donations': self.upload_schedule_c2,
            'c3_committees': self.upload_schedule_c3,
            'c4_business': lambda p, r, e: print("        ℹ️  C4 upload not yet implemented"),
            'c5_small': lambda p, r, e: print("        ℹ️  C5 upload not yet implemented"),
            'e1_expenses': self.upload_schedule_e1,
            'e2_independent': self.upload_schedule_e2,
            'e3_contributions': lambda p, r, e: print("        ℹ️  E3 upload not yet implemented"),
            'e4_small_expenses': lambda p, r, e: print("        ℹ️  E4 upload not yet implemented"),
            'l1_loans_received': lambda p, r, e: print("        ℹ️  L1 upload not yet implemented"),
            'l2_loans_made': lambda p, r, e: print("        ℹ️  L2 upload not yet implemented"),
        }
        
        for suffix, csv_path in csv_files.items():
            if suffix == 'metadata':
                continue  # Already processed
            
            if suffix in upload_functions:
                print(f"      📤 Uploading {suffix}...")
                upload_functions[suffix](csv_path, report_id, entity_id)
    
    def update_report_totals(self, report_id: int):
        """Update report with calculated totals from all schedules"""
        # This would calculate totals from all the uploaded data
        # For now, just mark as processed
        pass
    
    def process_pdf(self, pdf_record: Dict) -> bool:
        """Process a single PDF through the comprehensive pipeline"""
        entity_id = pdf_record.get('entity_id')
        pdf_id = pdf_record.get('pdf_id')
        pdf_url = pdf_record.get('pdf_url')
        report_name = pdf_record.get('report_name', 'unknown')
        
        print(f"\n📄 Processing: Entity {entity_id} - PDF {pdf_id} - {report_name}")
        
        # Download PDF
        pdf_path = self.download_pdf(pdf_url, entity_id, pdf_id)
        if not pdf_path:
            return False
        
        # Process with comprehensive extractor
        csv_files = self.process_pdf_with_comprehensive_extractor(pdf_path)
        if not csv_files:
            pdf_path.unlink(missing_ok=True)
            return False
        
        # Create report record from metadata
        report_id = None
        if 'metadata' in csv_files:
            report_id = self.create_report_record(csv_files['metadata'], entity_id, pdf_id)
        
        if not report_id:
            print("    ❌ Failed to create report record")
            pdf_path.unlink(missing_ok=True)
            return False
        
        # Upload all schedules
        self.upload_all_schedules(csv_files, report_id, entity_id)
        
        # Update report totals
        self.update_report_totals(report_id)
        
        # Mark PDF as converted
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {"pdf_id": f"eq.{pdf_id}"}
        update_data = {
            'csv_converted': True,
            'conversion_date': datetime.now().isoformat()
        }
        
        requests.patch(url, headers=self.supabase_headers, params=params, json=update_data)
        
        # Clean up
        pdf_path.unlink(missing_ok=True)
        
        print(f"    ✅ Complete: Processed {len(csv_files)-1} schedule types")
        return True

def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Process ALL Campaign Finance Schedule Types')
    parser.add_argument('--entity', type=int, default=None,
                       help='Process specific entity ID only')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of PDFs to process')
    parser.add_argument('--pdf-id', type=int, default=None,
                       help='Process specific PDF ID only')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("ARIZONA CAMPAIGN FINANCE - COMPREHENSIVE SCHEDULE PROCESSOR")
    print("="*70)
    
    # Check R is available
    try:
        subprocess.run(['Rscript', '--version'], capture_output=True, check=True)
    except:
        print("❌ R is not installed or not in PATH")
        return
    
    # Process reports
    processor = ComprehensiveScheduleProcessor()
    
    # Fetch PDFs from Supabase
    pdfs = processor.fetch_reports_from_supabase(
        entity_id=args.entity, 
        limit=args.limit
    )
    
    if args.pdf_id:
        pdfs = [p for p in pdfs if p.get('pdf_id') == args.pdf_id]
    
    if not pdfs:
        print("No PDFs found to process")
        return
    
    # Process each PDF
    for i, pdf_record in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}]", end='')
        processor.process_pdf(pdf_record)
        time.sleep(0.5)
    
    # Print statistics
    print("\n\n📈 Final Statistics:")
    print(f"  Schedules found: {dict(processor.stats['schedules_found'])}")
    print(f"  Records processed: {dict(processor.stats['records_processed'])}")
    if processor.stats['upload_errors']:
        print(f"  Upload errors: {len(processor.stats['upload_errors'])}")
    
    print("\n" + "="*70)
    print("COMPREHENSIVE PROCESSING COMPLETE!")
    print("="*70)

if __name__ == "__main__":
    main()