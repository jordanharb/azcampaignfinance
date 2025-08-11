#!/usr/bin/env python3
"""
Arizona Campaign Finance Scraper - Step 2: Fetch Reports for All Entities
FINAL VERSION with backcheck support

This script fetches all available reports/PDFs for each entity.
Includes --backcheck option to recheck entities with invalid PDF URLs.
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

class ReportFetcher:
    """Fetch campaign finance reports for entities"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{BASE_URL}/Reporting/Explore',
            'Origin': BASE_URL
        })
    
    def fetch_entity_reports(self, entity_id: int) -> List[Dict]:
        """Fetch all reports for a specific entity"""
        
        # Try the GetReportsList endpoint
        url = f"{BASE_URL}/Reporting/GetReportsList"
        params = {
            'EntityId': entity_id,
            'startYear': '2000',
            'endYear': '2026'
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data:
                    return data['data']
        except Exception as e:
            print(f"    Error fetching reports: {e}")
        
        return []
    
    def get_pdf_url(self, report: Dict) -> str:
        """
        Extract or construct the PDF URL from report data
        Returns either PublicReports URL (working) or ReportFile URL (often broken)
        """
        # Check for direct PDF URL in report
        if 'PDFUrl' in report:
            return report['PDFUrl']
        
        # Check for ReportFileId (older format)
        if 'ReportFileId' in report:
            return f"{BASE_URL}/ReportFile/{report['ReportFileId']}"
        
        # Check for ReportId with year
        if 'ReportId' in report and 'FilingYear' in report:
            # This format works: /PublicReports/YEAR/GUID.pdf
            return f"{BASE_URL}/PublicReports/{report['FilingYear']}/{report['ReportId']}.pdf"
        
        return ""
    
    def validate_pdf_url(self, url: str) -> bool:
        """
        Check if a PDF URL is likely to be valid based on format
        PublicReports URLs are usually valid, ReportFile URLs often fail
        """
        if '/PublicReports/' in url and url.endswith('.pdf'):
            return True
        elif '/ReportFile/' in url:
            return False  # These usually return 404
        return None  # Unknown format

def process_entities(entity_ids: List[int], backcheck_only: bool = False):
    """Process a list of entities to fetch their reports"""
    
    fetcher = ReportFetcher()
    all_reports = []
    stats = {
        'total_entities': len(entity_ids),
        'entities_with_reports': 0,
        'total_reports': 0,
        'valid_pdf_urls': 0,
        'invalid_pdf_urls': 0,
        'unknown_pdf_urls': 0
    }
    
    print(f"\n📊 Processing {len(entity_ids)} entities...")
    
    for i, entity_id in enumerate(entity_ids, 1):
        if i % 10 == 0:
            print(f"  Progress: {i}/{len(entity_ids)} ({i/len(entity_ids)*100:.1f}%)")
        
        # Fetch reports for this entity
        reports = fetcher.fetch_entity_reports(entity_id)
        
        if reports:
            stats['entities_with_reports'] += 1
            
            for report in reports:
                # Add entity ID to report
                report['EntityID'] = entity_id
                
                # Get and validate PDF URL
                pdf_url = fetcher.get_pdf_url(report)
                report['PDFUrl'] = pdf_url
                
                # Validate URL format
                is_valid = fetcher.validate_pdf_url(pdf_url)
                report['PDFUrlValid'] = is_valid
                
                if is_valid is True:
                    stats['valid_pdf_urls'] += 1
                elif is_valid is False:
                    stats['invalid_pdf_urls'] += 1
                else:
                    stats['unknown_pdf_urls'] += 1
                
                # For backcheck mode, only include reports with invalid URLs
                if backcheck_only:
                    if is_valid is False:
                        all_reports.append(report)
                else:
                    all_reports.append(report)
            
            stats['total_reports'] += len(reports)
        
        # Rate limiting
        time.sleep(0.1)
    
    return all_reports, stats

def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Fetch reports for Arizona Campaign Finance entities')
    parser.add_argument('--backcheck', action='store_true',
                       help='Only process entities with invalid PDF URLs (ReportFile format)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of entities to process')
    parser.add_argument('--entity-id', type=int, default=None,
                       help='Process a specific entity ID')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("ARIZONA CAMPAIGN FINANCE - STEP 2: FETCH REPORTS (FINAL)")
    if args.backcheck:
        print("MODE: BACKCHECK - Rechecking entities with invalid PDF URLs")
    print("="*70)
    
    # Load entity IDs from step 1
    entity_ids_file = OUTPUT_DIR / "step1_entity_ids.json"
    if not entity_ids_file.exists():
        print("❌ Entity IDs file not found. Run step1_fetch_entities.py first.")
        return
    
    with open(entity_ids_file, 'r') as f:
        entity_ids = json.load(f)
    
    # Handle specific entity ID
    if args.entity_id:
        entity_ids = [args.entity_id]
        print(f"\n📍 Processing specific entity: {args.entity_id}")
    elif args.limit:
        entity_ids = entity_ids[:args.limit]
        print(f"\n📍 Processing first {args.limit} entities")
    
    # If backcheck mode, load previous results and filter to invalid URLs
    if args.backcheck:
        reports_file = OUTPUT_DIR / "step2_all_reports.json"
        if reports_file.exists():
            with open(reports_file, 'r') as f:
                previous_reports = json.load(f)
            
            # Find entities with invalid PDF URLs
            entities_to_check = set()
            for report in previous_reports:
                if report.get('PDFUrlValid') is False:
                    entities_to_check.add(report['EntityID'])
            
            entity_ids = list(entities_to_check)
            print(f"\n🔍 Found {len(entity_ids)} entities with invalid PDF URLs to recheck")
    
    # Process entities
    all_reports, stats = process_entities(entity_ids, backcheck_only=args.backcheck)
    
    # Save results
    if args.backcheck:
        output_file = OUTPUT_DIR / "step2_backcheck_reports.json"
    else:
        output_file = OUTPUT_DIR / "step2_all_reports.json"
    
    with open(output_file, 'w') as f:
        json.dump(all_reports, f, indent=2)
    
    print(f"\n💾 Saved {len(all_reports)} reports to {output_file}")
    
    # Print statistics
    print("\n📈 Statistics:")
    print(f"  Total entities processed: {stats['total_entities']}")
    print(f"  Entities with reports: {stats['entities_with_reports']}")
    print(f"  Total reports found: {stats['total_reports']}")
    print(f"\n  PDF URL Analysis:")
    print(f"    ✅ Valid URLs (PublicReports): {stats['valid_pdf_urls']}")
    print(f"    ❌ Invalid URLs (ReportFile): {stats['invalid_pdf_urls']}")
    print(f"    ❓ Unknown format: {stats['unknown_pdf_urls']}")
    
    # Create separate files for valid and invalid PDFs
    valid_pdfs = [r for r in all_reports if r.get('PDFUrlValid') is True]
    invalid_pdfs = [r for r in all_reports if r.get('PDFUrlValid') is False]
    
    valid_file = OUTPUT_DIR / "step2_valid_pdfs.json"
    with open(valid_file, 'w') as f:
        json.dump(valid_pdfs, f, indent=2)
    print(f"\n💾 Saved {len(valid_pdfs)} valid PDFs to {valid_file}")
    
    invalid_file = OUTPUT_DIR / "step2_invalid_pdfs.json"
    with open(invalid_file, 'w') as f:
        json.dump(invalid_pdfs, f, indent=2)
    print(f"💾 Saved {len(invalid_pdfs)} invalid PDFs to {invalid_file}")
    
    print("\n" + "="*70)
    print("NEXT STEP:")
    print("Run step3_process_pdfs.py to download and process the PDFs")
    if stats['invalid_pdf_urls'] > 0:
        print("\nNOTE: You can run with --backcheck later to recheck invalid URLs")
    print("="*70)

if __name__ == "__main__":
    main()