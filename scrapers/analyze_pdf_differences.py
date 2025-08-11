#!/usr/bin/env python3
"""
Download and analyze PDFs from good vs shifted reports to find the root cause
"""

import os
import requests
import json
from pathlib import Path

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

# Create test directory
TEST_DIR = Path("pdf_shift_analysis")
TEST_DIR.mkdir(exist_ok=True)

print("="*70)
print("ANALYZING PDF DIFFERENCES")
print("="*70)

# Load analysis
with open('all_issues_analysis.json', 'r') as f:
    analysis = json.load(f)

# Get examples of good reports (no shifting)
print("\n📥 Finding good reports (no shifting)...")
url = f"{SUPABASE_URL}/rest/v1/cf_reports"
params = {
    "select": "report_id,pdf_id,entity_id,org_name,org_email,org_phone,org_address",
    "limit": "100"
}
response = requests.get(url, headers=headers, params=params)
good_reports = []
if response.status_code == 200:
    for report in response.json():
        # Check if it's NOT in our shifted list
        if report['report_id'] not in analysis['shift_issues']:
            email = report.get('org_email', '')
            phone = report.get('org_phone', '')
            # Also verify it looks normal
            if email and 'Phone:' not in email and '@' in email:
                good_reports.append(report)

print(f"Found {len(good_reports)} good reports")

# Get examples of shifted reports
shifted_reports = []
for report_id, info in list(analysis['shift_issues'].items())[:10]:
    shifted_reports.append({
        'report_id': report_id,
        'pdf_id': info['pdf_id'],
        'entity_id': info['entity_id'],
        'reasons': info['reasons']
    })

print(f"Using {len(shifted_reports)} shifted reports")

# Get PDF URLs for both sets
print("\n📥 Getting PDF URLs...")

def get_pdf_urls(pdf_ids):
    """Get URLs for a list of PDF IDs"""
    if not pdf_ids:
        return {}
    
    id_list = ",".join(str(id) for id in pdf_ids)
    url = f"{SUPABASE_URL}/rest/v1/cf_report_pdfs"
    params = {
        "select": "pdf_id,pdf_url,report_name",
        "pdf_id": f"in.({id_list})"
    }
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        return {p['pdf_id']: (p['pdf_url'], p['report_name']) for p in response.json()}
    return {}

# Get URLs for good PDFs
good_pdf_ids = [r['pdf_id'] for r in good_reports[:5] if r.get('pdf_id')]
good_pdf_urls = get_pdf_urls(good_pdf_ids)

# Get URLs for shifted PDFs
shifted_pdf_ids = [r['pdf_id'] for r in shifted_reports[:5] if r.get('pdf_id')]
shifted_pdf_urls = get_pdf_urls(shifted_pdf_ids)

print(f"Found {len(good_pdf_urls)} good PDF URLs")
print(f"Found {len(shifted_pdf_urls)} shifted PDF URLs")

# Download sample PDFs
print("\n📥 Downloading sample PDFs for analysis...")

session = requests.Session()

def download_pdf(pdf_id, pdf_url, label):
    """Download a PDF for analysis"""
    if not pdf_url or '/ReportFile/' in pdf_url:
        return None
    
    try:
        response = session.get(pdf_url, timeout=30)
        if response.status_code == 200:
            filename = TEST_DIR / f"{label}_pdf_{pdf_id}.pdf"
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"  ✅ Downloaded {label} PDF {pdf_id}")
            return filename
        else:
            print(f"  ❌ Failed to download {label} PDF {pdf_id}: {response.status_code}")
    except Exception as e:
        print(f"  ❌ Error downloading {label} PDF {pdf_id}: {e}")
    return None

# Download good PDFs
good_files = []
for pdf_id, (url, name) in list(good_pdf_urls.items())[:3]:
    file = download_pdf(pdf_id, url, "good")
    if file:
        good_files.append((pdf_id, file, name))

# Download shifted PDFs
shifted_files = []
for pdf_id, (url, name) in list(shifted_pdf_urls.items())[:3]:
    file = download_pdf(pdf_id, url, "shifted")
    if file:
        shifted_files.append((pdf_id, file, name))

# Now let's check what the R scraper sees
print("\n📊 Analyzing PDF structure differences...")

# Look at the actual report data
print("\n🔍 Comparing report field patterns:")
print("-" * 40)

print("\nGOOD REPORTS (correct fields):")
for report in good_reports[:3]:
    print(f"\nReport {report['report_id']}:")
    print(f"  org_name: {report.get('org_name', '')}")
    print(f"  org_email: {report.get('org_email', '')}")
    print(f"  org_phone: {report.get('org_phone', '')}")
    print(f"  org_address: {report.get('org_address', '')}")

print("\nSHIFTED REPORTS (misaligned fields):")
for report_id in list(analysis['shift_issues'].keys())[:3]:
    # Get full report data
    url = f"{SUPABASE_URL}/rest/v1/cf_reports"
    params = {"report_id": f"eq.{report_id}"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200 and response.json():
        report = response.json()[0]
        print(f"\nReport {report['report_id']}:")
        print(f"  org_name: {report.get('org_name', '')}")
        print(f"  org_email: {report.get('org_email', '')} ⚠️")
        print(f"  org_phone: {report.get('org_phone', '')} ⚠️")
        print(f"  org_address: {report.get('org_address', '')} ⚠️")
        print(f"  org_treasurer: {report.get('org_treasurer', '')} ⚠️")

# Check the CSV extraction pattern
print("\n📝 Checking R scraper extraction...")

# Look at raw CSV header mapping
print("\nLikely issue: R scraper expects specific field order")
print("If PDF format changes, fields may extract in wrong order")

# Create test R script to examine PDFs
test_r_script = TEST_DIR / "test_extraction.R"
r_content = '''
# Test PDF field extraction
library(pdftools)
library(dplyr)

# Read PDF and extract text
pdf_file <- commandArgs(trailingOnly = TRUE)[1]
text <- pdf_text(pdf_file)

# Print first page structure
cat("\\n=== FIRST PAGE TEXT ===\\n")
cat(text[1])

# Look for field markers
cat("\\n=== FIELD DETECTION ===\\n")
lines <- strsplit(text[1], "\\n")[[1]]

# Find organization info
for (i in 1:min(30, length(lines))) {
    line <- lines[i]
    if (grepl("Committee Name|Organization", line, ignore.case = TRUE)) {
        cat("Found org name line:", i, "-", line, "\\n")
        if (i < length(lines)) cat("  Next line:", lines[i+1], "\\n")
    }
    if (grepl("Email", line, ignore.case = TRUE)) {
        cat("Found email line:", i, "-", line, "\\n")
        if (i < length(lines)) cat("  Next line:", lines[i+1], "\\n")
    }
    if (grepl("Phone", line, ignore.case = TRUE)) {
        cat("Found phone line:", i, "-", line, "\\n")
        if (i < length(lines)) cat("  Next line:", lines[i+1], "\\n")
    }
    if (grepl("Address", line, ignore.case = TRUE)) {
        cat("Found address line:", i, "-", line, "\\n")
        if (i < length(lines)) cat("  Next line:", lines[i+1], "\\n")
    }
    if (grepl("Treasurer", line, ignore.case = TRUE)) {
        cat("Found treasurer line:", i, "-", line, "\\n")
        if (i < length(lines)) cat("  Next line:", lines[i+1], "\\n")
    }
}
'''

with open(test_r_script, 'w') as f:
    f.write(r_content)

print("\n🔬 Testing PDF extraction with R...")

import subprocess

# Test good PDF
if good_files:
    pdf_id, file, name = good_files[0]
    print(f"\nTesting GOOD PDF {pdf_id} ({name}):")
    try:
        result = subprocess.run(
            ['Rscript', str(test_r_script), str(file)],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(result.stdout[:1000])
    except Exception as e:
        print(f"Error: {e}")

# Test shifted PDF
if shifted_files:
    pdf_id, file, name = shifted_files[0]
    print(f"\nTesting SHIFTED PDF {pdf_id} ({name}):")
    try:
        result = subprocess.run(
            ['Rscript', str(test_r_script), str(file)],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(result.stdout[:1000])
    except Exception as e:
        print(f"Error: {e}")

print("\n" + "="*70)
print("ANALYSIS COMPLETE")
print("="*70)
print(f"\nPDFs saved in: {TEST_DIR}/")
print("\nLikely cause: R scraper expects fields in specific positions")
print("When PDF format varies, it may extract wrong lines")
print("Need to examine R scraper's field detection logic")