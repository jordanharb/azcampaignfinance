#!/usr/bin/env python3
"""
Arizona Campaign Finance Scraper - Step 3: Process PDFs from Supabase
Pulls PDF URLs directly from Supabase and processes them through R scraper.
"""

import os
import subprocess
import tempfile
import time
import csv
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import argparse

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

# Source the scraper function
# Use absolute path since we know the location
source_path <- "/Users/jordanharb/Documents/az-campaign-finance/pdf-scraper/DonationReportScrapingCode/20250425-001_DonationReportDataScrape/_04-LocalFunctions/PDFData_DonorReports.R"

if (!file.exists(source_path)) {
    stop(paste("R scraper function not found at:", source_path))
}

source(source_path)

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
        """Fetch report PDFs from Supabase"""
        
        # Query cf_report_pdfs directly since not all PDFs have cf_reports records
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {
            "select": "*",
            "pdf_url": "not.is.null"
        }
        
        if entity_id:
            params["entity_id"] = f"eq.{entity_id}"
        
        if limit:
            params["limit"] = str(limit)
        
        response = requests.get(url, headers=self.supabase_headers, params=params)
        
        if response.status_code == 200:
            pdfs = response.json()
            print(f"✅ Found {len(pdfs)} PDFs to process")
            return pdfs
        else:
            print(f"❌ Failed to fetch PDFs: {response.text}")
            return []
    
    def download_pdf(self, pdf_url: str, entity_id: int, report_name: str) -> Optional[Path]:
        """Download a PDF to temporary directory"""
        try:
            response = self.session.get(pdf_url, timeout=30)
            if response.status_code == 200:
                # Create a safe filename
                safe_name = f"entity_{entity_id}_{report_name.replace(' ', '_').replace('/', '-')}.pdf"
                pdf_path = TEMP_PDF_DIR / safe_name
                
                with open(pdf_path, 'wb') as f:
                    f.write(response.content)
                
                return pdf_path
            else:
                print(f"  ❌ Failed to download PDF: {response.status_code}")
                return None
        except Exception as e:
            print(f"  ❌ Error downloading PDF: {e}")
            return None
    
    def process_pdf_with_r(self, pdf_path: Path) -> Optional[Path]:
        """Process PDF through R scraper"""
        output_csv = PROCESSED_CSV_DIR / f"{pdf_path.stem}_donations.csv"
        
        try:
            # Call R script
            result = subprocess.run(
                ['Rscript', str(self.r_wrapper_path), str(pdf_path), str(output_csv)],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and output_csv.exists():
                print(f"  ✅ R scraper succeeded: {result.stdout.strip()}")
                return output_csv
            else:
                print(f"  ⚠️ R scraper failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print("  ❌ R scraper timed out")
            return None
        except Exception as e:
            print(f"  ❌ Error running R scraper: {e}")
            return None
    
    def parse_csv_date(self, date_str: str) -> Optional[str]:
        """Parse various date formats from CSV to ISO format"""
        if not date_str or date_str == 'NA':
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
                return datetime.strptime(date_str, fmt).date().isoformat()
            except:
                continue
        
        return None
    
    def parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount string to float"""
        if not amount_str or amount_str == 'NA':
            return None
        
        # Remove $ and commas
        clean_amount = amount_str.replace('$', '').replace(',', '').strip()
        
        try:
            return float(clean_amount)
        except:
            return None
    
    def upload_donations_to_supabase(self, csv_path: Path, entity_id: int, report_id: int, pdf_url: str):
        """Upload donation data from CSV to Supabase"""
        donations = []
        
        # Read and parse CSV
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                donation = {
                    'report_id': report_id,
                    'entity_id': entity_id,
                    'rpt_title': row.get('Rpt_Title', ''),
                    'rpt_name': row.get('Rpt_Name', ''),
                    'rpt_cycle': int(row.get('Rpt_Cycle')) if row.get('Rpt_Cycle') else None,
                    'rpt_file_date': self.parse_csv_date(row.get('Rpt_FileDate')),
                    'rpt_period': row.get('Rpt_Period', ''),
                    'org_name': row.get('OrgNm', ''),
                    'org_email': row.get('OrgEml', ''),
                    'org_phone': row.get('OrgTel', ''),
                    'org_address': row.get('OrgAdr', ''),
                    'org_treasurer': row.get('OrgTreasurer', ''),
                    'org_jurisdiction': row.get('Jurisdiction', ''),
                    'donor_name': row.get('Donor_Name', ''),
                    'donor_addr': row.get('Donor_Addr', ''),
                    'donor_occupation': row.get('Donor_Occupation', ''),
                    'donation_date': self.parse_csv_date(row.get('Donation_Date')),
                    'donation_amt': self.parse_amount(row.get('Donation_Amt')),
                    'donation_type': row.get('Donation_Type', ''),
                    'cycle_to_date_amt': self.parse_amount(row.get('CycleToDate_Amt')),
                    'page_num': int(row.get('PageNum')) if row.get('PageNum') else None,
                    'page_type': row.get('PageType', ''),
                    'meta_segment_name': row.get('META_SegmentName', ''),
                    'meta_file_name': row.get('META_FileName', ''),
                    'pdf_url': pdf_url
                }
                
                # Filter out None values
                donation = {k: v for k, v in donation.items() if v is not None}
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
                    print(f"    ❌ Failed to upload: {response.text}")
        
        # Update PDF tracking to mark as converted
        if donations:
            url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
            params = {"pdf_url": f"eq.{pdf_url}"}
            update_data = {
                'csv_converted': True,
                'conversion_date': datetime.now().isoformat(),
                'row_count': len(donations)
            }
            
            response = requests.patch(
                url, 
                headers=self.supabase_headers, 
                params=params,
                json=update_data
            )
    
    def process_report(self, report: Dict) -> bool:
        """Process a single report through the full pipeline"""
        entity_id = report.get('entity_id')
        report_id = report.get('report_id')
        report_name = report.get('rpt_name', 'unknown')
        
        # Get PDF URL from nested structure
        pdf_info = report.get('cf_report_pdfs')
        if not pdf_info or not pdf_info.get('pdf_url'):
            print(f"  ⚠️ No PDF URL for report {report_id}")
            return False
        
        pdf_url = pdf_info['pdf_url']
        already_converted = pdf_info.get('csv_converted', False)
        
        if already_converted:
            print(f"  ⏭️  Already converted: Entity {entity_id} - {report_name}")
            return True
        
        print(f"\n📄 Processing: Entity {entity_id} - {report_name}")
        
        # Download PDF
        pdf_path = self.download_pdf(pdf_url, entity_id, report_name)
        if not pdf_path:
            return False
        
        # Process with R scraper
        csv_path = self.process_pdf_with_r(pdf_path)
        if not csv_path:
            # Clean up PDF
            pdf_path.unlink(missing_ok=True)
            return False
        
        # Upload to Supabase
        self.upload_donations_to_supabase(csv_path, entity_id, report_id, pdf_url)
        
        # Clean up temporary PDF (keep CSV for review)
        pdf_path.unlink(missing_ok=True)
        
        return True

def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Process Campaign Finance PDFs from Supabase')
    parser.add_argument('--entity', type=int, default=None,
                       help='Process specific entity ID only')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of reports to process')
    parser.add_argument('--skip-converted', action='store_true',
                       help='Skip reports already converted to CSV')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("ARIZONA CAMPAIGN FINANCE - PROCESS PDFs FROM SUPABASE")
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
    
    # Fetch reports from Supabase
    reports = processor.fetch_reports_from_supabase(
        entity_id=args.entity, 
        limit=args.limit
    )
    
    if not reports:
        print("No reports found to process")
        return
    
    stats = {
        'total': len(reports),
        'success': 0,
        'failed': 0,
        'skipped': 0
    }
    
    for i, report in enumerate(reports, 1):
        print(f"\n[{i}/{len(reports)}]", end='')
        
        # Check if already converted
        pdf_info = report.get('cf_report_pdfs', {})
        if args.skip_converted and pdf_info.get('csv_converted'):
            stats['skipped'] += 1
            continue
        
        if processor.process_report(report):
            stats['success'] += 1
        else:
            stats['failed'] += 1
        
        # Rate limiting
        time.sleep(0.5)
    
    # Print statistics
    print("\n\n📈 Final Statistics:")
    print(f"  Total reports: {stats['total']}")
    print(f"  Successfully processed: {stats['success']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Skipped (already converted): {stats['skipped']}")
    print(f"  CSV files saved in: {PROCESSED_CSV_DIR}")
    
    print("\n" + "="*70)
    print("PROCESSING COMPLETE!")
    print("="*70)

if __name__ == "__main__":
    main()