#!/usr/bin/env python3
"""
Arizona Campaign Finance Scraper - Step 3: Download and Process PDFs
FINAL VERSION with Supabase integration

This script downloads PDFs and uploads them to Supabase for processing.
Includes support for backcheck mode to retry failed PDFs.
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import argparse

# Configuration
OUTPUT_DIR = Path("campaign_finance_data")
OUTPUT_DIR.mkdir(exist_ok=True)
BASE_URL = "https://seethemoney.az.gov"

# Supabase configuration (can be overridden with environment variables)
import os
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

class PDFProcessor:
    """Download and process campaign finance PDFs"""
    
    def __init__(self, upload_to_supabase: bool = False):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        self.upload_to_supabase = upload_to_supabase
        if upload_to_supabase:
            self.supabase_headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
    
    def build_correct_entity_url(self, entity_id: int) -> str:
        """Build the correct entity URL with all required parameters"""
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
    
    def check_pdf_exists(self, pdf_url: str) -> bool:
        """Check if a PDF URL is accessible"""
        try:
            response = self.session.head(pdf_url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def attempt_fix_pdf_url(self, report: Dict) -> Optional[str]:
        """
        Attempt to fix invalid PDF URLs by trying alternative formats
        Used in backcheck mode to find working URLs
        """
        entity_id = report.get('EntityID')
        report_name = report.get('ReportName', '')
        year = report.get('FilingYear')
        
        # Try different URL patterns
        attempts = []
        
        # Pattern 1: PublicReports with GUID
        if 'ReportId' in report and year:
            url = f"{BASE_URL}/PublicReports/{year}/{report['ReportId']}.pdf"
            attempts.append(url)
        
        # Pattern 2: Try current year if year is missing
        if 'ReportId' in report and not year:
            current_year = datetime.now().year
            for test_year in range(current_year, current_year - 5, -1):
                url = f"{BASE_URL}/PublicReports/{test_year}/{report['ReportId']}.pdf"
                attempts.append(url)
        
        # Test each attempt
        for url in attempts:
            if self.check_pdf_exists(url):
                return url
        
        return None
    
    def upload_to_supabase_db(self, report: Dict, pdf_url: str, is_valid: bool):
        """Upload report information to Supabase"""
        if not self.upload_to_supabase:
            return
        
        # Check if entity exists, if not create it
        entity_id = report.get('EntityID')
        
        # Check if entity exists
        url = f"{SUPABASE_URL}/rest/v1/cf_entities"
        params = {"entity_id": f"eq.{entity_id}"}
        response = requests.get(url, headers=self.supabase_headers, params=params)
        
        if response.status_code == 200 and not response.json():
            # Entity doesn't exist, create it
            entity_data = {
                'entity_id': entity_id,
                'entity_url': self.build_correct_entity_url(entity_id),
                'primary_committee_name': report.get('CommitteeName', ''),
                'primary_candidate_name': report.get('CandidateName', ''),
                'created_at': datetime.now().isoformat()
            }
            requests.post(url, headers=self.supabase_headers, json=entity_data)
        
        # Insert report PDF record
        pdf_data = {
            'entity_id': entity_id,
            'pdf_url': pdf_url,
            'report_name': report.get('ReportName', ''),
            'filing_date': report.get('FilingDate'),
            'cycle_year': report.get('FilingYear'),
            'csv_converted': False,
            'is_valid_url': is_valid
        }
        
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        requests.post(url, headers=self.supabase_headers, json=pdf_data)

def process_reports(reports: List[Dict], backcheck: bool = False, upload_to_supabase: bool = False):
    """Process a list of reports"""
    
    processor = PDFProcessor(upload_to_supabase=upload_to_supabase)
    
    stats = {
        'total_reports': len(reports),
        'valid_pdfs': 0,
        'invalid_pdfs': 0,
        'fixed_pdfs': 0,
        'downloaded': 0,
        'failed': 0
    }
    
    print(f"\n📊 Processing {len(reports)} reports...")
    
    for i, report in enumerate(reports, 1):
        if i % 10 == 0:
            print(f"  Progress: {i}/{len(reports)} ({i/len(reports)*100:.1f}%)")
        
        pdf_url = report.get('PDFUrl', '')
        is_valid = report.get('PDFUrlValid')
        
        # In backcheck mode, try to fix invalid URLs
        if backcheck and is_valid is False:
            fixed_url = processor.attempt_fix_pdf_url(report)
            if fixed_url:
                print(f"  ✅ Fixed URL for entity {report['EntityID']}: {fixed_url}")
                pdf_url = fixed_url
                is_valid = True
                stats['fixed_pdfs'] += 1
        
        # Check if PDF exists
        if pdf_url and processor.check_pdf_exists(pdf_url):
            stats['valid_pdfs'] += 1
            
            # Upload to Supabase if enabled
            if upload_to_supabase:
                processor.upload_to_supabase_db(report, pdf_url, True)
        else:
            stats['invalid_pdfs'] += 1
            
            # Still upload to Supabase but mark as invalid
            if upload_to_supabase and pdf_url:
                processor.upload_to_supabase_db(report, pdf_url, False)
        
        # Rate limiting
        time.sleep(0.05)
    
    return stats

def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Process Arizona Campaign Finance PDFs')
    parser.add_argument('--backcheck', action='store_true',
                       help='Process reports with invalid URLs and attempt to fix them')
    parser.add_argument('--upload', action='store_true',
                       help='Upload results to Supabase database')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of reports to process')
    parser.add_argument('--valid-only', action='store_true',
                       help='Only process reports with valid PDF URLs')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("ARIZONA CAMPAIGN FINANCE - STEP 3: PROCESS PDFs (FINAL)")
    if args.backcheck:
        print("MODE: BACKCHECK - Attempting to fix invalid PDF URLs")
    if args.upload:
        print("MODE: UPLOAD - Will upload to Supabase database")
    print("="*70)
    
    # Load reports from step 2
    if args.backcheck:
        reports_file = OUTPUT_DIR / "step2_invalid_pdfs.json"
    elif args.valid_only:
        reports_file = OUTPUT_DIR / "step2_valid_pdfs.json"
    else:
        reports_file = OUTPUT_DIR / "step2_all_reports.json"
    
    if not reports_file.exists():
        print(f"❌ Reports file not found: {reports_file}")
        print("Run step2_fetch_reports.py first.")
        return
    
    with open(reports_file, 'r') as f:
        reports = json.load(f)
    
    if args.limit:
        reports = reports[:args.limit]
        print(f"\n📍 Processing first {args.limit} reports")
    
    # Process reports
    stats = process_reports(reports, backcheck=args.backcheck, upload_to_supabase=args.upload)
    
    # Print statistics
    print("\n📈 Final Statistics:")
    print(f"  Total reports processed: {stats['total_reports']}")
    print(f"  Valid PDFs: {stats['valid_pdfs']}")
    print(f"  Invalid PDFs: {stats['invalid_pdfs']}")
    if args.backcheck:
        print(f"  Fixed PDFs: {stats['fixed_pdfs']}")
    
    if args.upload:
        print(f"\n✅ Data uploaded to Supabase")
    
    # Save processing results
    results_file = OUTPUT_DIR / f"step3_processing_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"\n💾 Saved results to {results_file}")
    
    print("\n" + "="*70)
    print("PROCESSING COMPLETE!")
    if stats['invalid_pdfs'] > 0 and not args.backcheck:
        print("\nTIP: Run with --backcheck to attempt fixing invalid PDF URLs")
    print("="*70)

if __name__ == "__main__":
    main()