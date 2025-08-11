# Arizona Campaign Finance Scraper - Final Version

Complete pipeline for scraping Arizona campaign finance data from seethemoney.az.gov

## Overview

This is a 4-step process to scrape all campaign finance data:
1. **Entities** - Fetch all committees/candidates
2. **Reports** - Fetch all PDF reports for each entity
3. **PDFs** - Process PDFs to extract donations
4. **Transactions** - Fetch all transaction details with entity relationships

## Setup

### Requirements
```bash
pip install requests pandas pdfplumber supabase python-dotenv
```

### Database Setup
1. Create tables in Supabase using `cf_transactions_schema_complete.sql`
2. Set environment variables (or use defaults):
```bash
export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-service-key"
```

## Usage

### Step 1: Fetch All Entities
```bash
python step1_fetch_entities.py
```
- Fetches all entities from the campaign finance API
- Generates correct entity URLs with all required parameters
- Saves to `campaign_finance_data/step1_entity_ids.json`

Options:
- `--update-db`: Update entities directly in Supabase

### Step 2: Fetch Reports
```bash
python step2_fetch_reports.py
```
- Fetches all available reports for each entity
- Validates PDF URLs (PublicReports vs ReportFile formats)
- Separates valid and invalid PDFs

Options:
- `--backcheck`: Only process entities with invalid PDF URLs
- `--limit N`: Process only first N entities
- `--entity-id ID`: Process a specific entity

### Step 3: Process PDFs
```bash
python step3_process_pdfs.py --upload --valid-only
```
- Downloads and validates PDFs
- Extracts donation data
- Uploads to Supabase

Options:
- `--backcheck`: Attempt to fix invalid PDF URLs
- `--upload`: Upload results to Supabase
- `--valid-only`: Only process reports with valid URLs

### Step 4: Fetch All Transactions (NEW)
```bash
python step4_fetch_transactions.py --upload
```
- Fetches detailed transaction data for all entities
- Parses entity relationships from ReceivedFromOrPaidTo field
- Extracts unique donor/vendor entity IDs
- Uploads in correct order to avoid foreign key errors

Options:
- `--upload`: Upload to Supabase
- `--limit N`: Process only N entities
- `--entity-id ID`: Process specific entity
- `--use-local`: Use local entity file instead of fetching from Supabase

## Complete Workflow

### Initial Full Scrape
```bash
# 1. Fetch all entities
python step1_fetch_entities.py

# 2. Fetch all reports
python step2_fetch_reports.py

# 3. Process PDFs
python step3_process_pdfs.py --upload --valid-only

# 4. Fetch all transactions with entity relationships
python step4_fetch_transactions.py --upload
```

### Incremental Updates
```bash
# Check for new reports on entities with previously invalid URLs
python step2_fetch_reports.py --backcheck

# Update transactions for specific entity
python step4_fetch_transactions.py --entity-id 201600383 --upload
```

## Database Schema

The system uses these main tables:
- `cf_entities`: Committees and candidates
- `cf_transaction_entities`: Unique donors/vendors with IDs
- `cf_transactions`: All transactions with full details (51 fields)
- `cf_report_pdfs`: PDF report tracking
- `cf_donations`: Donation records from PDFs

## Transaction Data

The transaction scraper (step4) captures:
- **51 fields per transaction** including amounts, dates, types
- **Entity IDs** parsed from ReceivedFromOrPaidTo field
- **Relationships** between committees and donors/vendors
- **Full categorization** (PACs, individuals, businesses, etc.)

This enables:
- Network analysis of money flows
- Tracking donors across multiple campaigns
- Identifying major political players
- Complete financial transparency

## Notes

- Rate limiting is implemented (0.1-0.5 seconds between requests)
- Invalid PDF URLs (ReportFile format) are tracked for future fixes
- Backcheck mode attempts to find alternative URLs for failed PDFs
- Transaction entities are uploaded BEFORE transactions to maintain referential integrity