# Arizona Campaign Finance Data Pipeline - UPDATED WORKFLOW

## Overview
This pipeline extracts donation data from Arizona campaign finance PDFs and stores it in Supabase.

## Prerequisites

1. **R Installation**: The pipeline uses R to extract data from PDFs
   ```bash
   # Install R from https://www.r-project.org/
   
   # Install required R packages:
   R -e 'install.packages(c("tidyverse", "pdftools", "lubridate", "readxl", "openxlsx"))'
   ```

2. **Python Requirements**: Already in requirements.txt

3. **Supabase Setup**: 
   - Run `supabase-donations-table.sql` to create the donations table
   - Ensure environment variables are set

## Updated Pipeline Steps

### Step 1: Fetch Entities
```bash
python step1_fetch_entities.py
```
Gets list of all campaign entities from Arizona Secretary of State.

### Step 2: Fetch Reports & PDF URLs
```bash
python step2_fetch_reports.py --limit 100
```
For each entity, fetches their campaign finance reports and PDF URLs.

### Step 3: Process PDFs & Extract Donations (REPLACED)
```bash
# Test the R integration first
python test_r_scraper.py

# Process PDFs and extract donation data
python step3_process_pdfs_v2.py --limit 5  # Test with 5 reports

# Process specific entity
python step3_process_pdfs_v2.py --entity 201800057 --upload

# Full run with upload to Supabase
python step3_process_pdfs_v2.py --upload --valid-only
```

This new Step 3:
1. Downloads PDFs from URLs found in Step 2
2. Runs each PDF through the R scraper (extracts donation details)
3. Uploads extracted donation data to Supabase `cf_donations` table

### ~~Step 4: Process Transactions~~ (Still works independently)
The transaction scraper (step4) works independently and doesn't need changes.

## What Changed?

### Old Step 3 (DELETED):
- Only validated PDF URLs
- Didn't extract any data
- Created redundant `cf_report_pdfs` table

### New Step 3:
- Actually processes PDFs through the R scraper
- Extracts detailed donation information (donor names, amounts, dates, etc.)
- Stores data in `cf_donations` table matching the R scraper output format

## Database Schema

The new `cf_donations` table contains:
- Report metadata (title, name, cycle, filing date, period)
- Organization info (name, email, phone, address, treasurer)
- Donor details (name, address, occupation, employer)
- Donation specifics (date, amount, type, cycle-to-date)
- Processing metadata (page number, PDF URL, processed date)

## Troubleshooting

1. **R not found**: Make sure R is installed and `Rscript` is in your PATH
2. **R packages missing**: Install with the R command shown above
3. **PDF extraction fails**: Check the PDF exists and is readable
4. **Supabase upload fails**: Check your API keys and table permissions

## Example Usage

Process Consuelo Hernandez's reports:
```bash
# Find the entity ID for Consuelo Hernandez
python step1_fetch_entities.py
# Let's say it's entity 100940

# Fetch their reports
python step2_fetch_reports.py --entity 100940

# Process their PDFs and upload donations
python step3_process_pdfs_v2.py --entity 100940 --upload
```

## Output

- **CSV Files**: Saved in `campaign_finance_data/processed_csvs/`
- **Database**: Donations stored in Supabase `cf_donations` table
- **Logs**: Processing status printed to console