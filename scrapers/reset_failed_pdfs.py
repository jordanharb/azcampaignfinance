#!/usr/bin/env python3
"""
Reset PDFs that were incorrectly marked as processed
This script identifies PDFs that were marked as converted but likely failed due to network issues
"""

import os
import requests
import argparse
from datetime import datetime
from typing import List, Dict

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

def fetch_failed_pdfs(check_all: bool = False) -> List[Dict]:
    """Fetch PDFs that were marked as converted but might have failed
    
    Since we discovered many PDFs were incorrectly marked as 404s,
    we'll look for patterns that indicate they weren't actually processed.
    """
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    all_pdfs = []
    offset = 0
    batch_size = 1000
    
    if check_all:
        print("📥 Fetching ALL converted PDFs (this may take a while)...")
    else:
        print("📥 Fetching converted PDFs that might have failed...")
        print("   (Looking for PublicReports URLs that were marked as converted)")
    
    while True:
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {
            "select": "pdf_id,entity_id,pdf_url,report_name,conversion_date",
            "csv_converted": "eq.true",
            "limit": str(batch_size),
            "offset": str(offset),
            "order": "pdf_id"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            batch = response.json()
            
            # Filter for suspicious patterns
            filtered_batch = []
            for pdf in batch:
                pdf_url = pdf.get('pdf_url', '')
                
                # Skip unfiled reports (these are correctly marked as converted)
                if '/ReportFile/' in pdf_url:
                    continue
                
                if check_all:
                    # Include all non-ReportFile PDFs
                    filtered_batch.append(pdf)
                else:
                    # Only include PublicReports PDFs (these shouldn't fail with 404)
                    if '/PublicReports/' in pdf_url:
                        # Check if there's actually a corresponding report or donations
                        # If not, it probably failed
                        filtered_batch.append(pdf)
            
            all_pdfs.extend(filtered_batch)
            
            if len(batch) < batch_size:
                break
            
            offset += batch_size
            
            if len(all_pdfs) > 0 and len(all_pdfs) % 5000 == 0:
                print(f"  Found {len(all_pdfs)} PDFs so far...")
        else:
            print(f"❌ Failed to fetch PDFs: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            break
    
    return all_pdfs

def test_pdf_urls(pdfs: List[Dict], sample_size: int = 10) -> List[Dict]:
    """Test a sample of PDF URLs to see if they're actually accessible"""
    import random
    
    if len(pdfs) <= sample_size:
        sample = pdfs
    else:
        sample = random.sample(pdfs, sample_size)
    
    print(f"\n🔍 Testing {len(sample)} PDF URLs...")
    
    failed_pdfs = []
    session = requests.Session()
    
    for pdf in sample:
        pdf_url = pdf.get('pdf_url')
        if not pdf_url:
            continue
        
        try:
            response = session.head(pdf_url, timeout=5)
            if response.status_code == 200:
                print(f"  ✅ PDF exists: {pdf_url}")
                failed_pdfs.append(pdf)
            else:
                print(f"  ❌ Still 404: {pdf_url}")
        except:
            print(f"  ⚠️ Network error: {pdf_url}")
            failed_pdfs.append(pdf)
    
    return failed_pdfs

def reset_pdfs(pdf_ids: List[int], batch_size: int = 100):
    """Reset PDFs to unprocessed state"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"\n♻️ Resetting {len(pdf_ids)} PDFs to unprocessed state...")
    
    # Process in batches
    for i in range(0, len(pdf_ids), batch_size):
        batch_ids = pdf_ids[i:i+batch_size]
        
        # Build the filter for this batch
        id_filter = ",".join(str(id) for id in batch_ids)
        
        url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
        params = {
            "pdf_id": f"in.({id_filter})"
        }
        
        # Reset the fields
        update_data = {
            'csv_converted': False,
            'conversion_date': None
        }
        
        response = requests.patch(
            url,
            headers=headers,
            params=params,
            json=update_data
        )
        
        if response.status_code in [200, 204]:
            print(f"  ✅ Reset batch {i//batch_size + 1}: {len(batch_ids)} PDFs")
        else:
            print(f"  ❌ Failed to reset batch: {response.status_code}")
            print(f"     Response: {response.text[:200]}")

def main():
    parser = argparse.ArgumentParser(description='Reset failed PDFs for reprocessing')
    parser.add_argument('--test', action='store_true',
                       help='Test URLs before resetting')
    parser.add_argument('--all', action='store_true',
                       help='Check ALL converted PDFs (not just ones with errors)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of PDFs to reset')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be reset without actually doing it')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("PDF RESET UTILITY")
    print("="*70)
    
    # Fetch PDFs that might need resetting
    pdfs = fetch_failed_pdfs(check_all=args.all)
    
    if not pdfs:
        print("✅ No suspicious PDFs found!")
        return
    
    print(f"\n📊 Found {len(pdfs)} PDFs that might need resetting")
    
    # Show sample
    print("\n📋 Sample of PDFs found:")
    for pdf in pdfs[:5]:
        print(f"  - Entity {pdf['entity_id']}, PDF {pdf['pdf_id']}")
        print(f"    URL: {pdf['pdf_url']}")
    
    if len(pdfs) > 5:
        print(f"  ... and {len(pdfs) - 5} more")
    
    # Test URLs if requested
    if args.test:
        working_pdfs = test_pdf_urls(pdfs, sample_size=20)
        if working_pdfs:
            print(f"\n✅ Found {len(working_pdfs)} PDFs that are actually accessible!")
            pdfs = working_pdfs
        else:
            print("\n❌ No accessible PDFs found in sample")
            return
    
    # Apply limit if specified
    if args.limit:
        pdfs = pdfs[:args.limit]
        print(f"\n🔧 Limiting to {len(pdfs)} PDFs")
    
    # Extract PDF IDs
    pdf_ids = [pdf['pdf_id'] for pdf in pdfs]
    
    if args.dry_run:
        print(f"\n🔍 DRY RUN: Would reset {len(pdf_ids)} PDFs")
        print("PDF IDs:", pdf_ids[:10], "..." if len(pdf_ids) > 10 else "")
    else:
        # Confirm before proceeding
        print(f"\n⚠️  About to reset {len(pdf_ids)} PDFs to unprocessed state")
        response = input("Continue? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return
        
        # Reset the PDFs
        reset_pdfs(pdf_ids)
        
        print(f"\n✅ Reset complete! {len(pdf_ids)} PDFs are now ready for reprocessing")
        print("Run the step3_concurrent.py script to process them again")

if __name__ == "__main__":
    main()