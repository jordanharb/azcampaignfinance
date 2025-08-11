# Comprehensive Fix Plan for Address and Data Shift Issues

## Problems Identified

### 1. Address Parsing Issue (Suite Numbers)
- **11,205 donations** have invalid state codes (Ph, Ch, Sc, etc.)
- Caused by suite/unit numbers creating 4-part addresses
- Parser treats suite as city, city as state

### 2. Data Shift Issue (Field Misalignment)
- Phone numbers appearing in email field
- Addresses appearing in phone field  
- Treasurer names in address field
- Everything shifted left by one or more columns
- Affects entities like:
  - Grantham for Arizona 2020 (entity 100016)
  - Committee to Elect Kim Owens (entity 100009)
  - Coral4AZ (entity 100008)

### 3. Duplication Risk
- **CRITICAL**: The upload process does NOT check for duplicates
- If we only delete bad donations and re-scrape, we'll get duplicates of good donations
- **MUST delete ALL donations from affected reports**

## Root Causes

### Address Issue
- Fixed: Parser now handles 4-part addresses correctly

### Data Shift Issue
- Likely caused by PDFs with different formats or missing fields
- R scraper misinterprets field boundaries
- Need to detect pattern: email fields starting with "Phone:", phone fields containing addresses

## Comprehensive Solution

### Step 1: Identify ALL Affected Records
1. Find donations with invalid state codes (address issue)
2. Find reports with shifted data (email contains "Phone:", phone contains address pattern)
3. Combine both lists of affected reports

### Step 2: Complete Cleanup
1. Delete ALL donations from affected reports (not just bad ones)
2. Delete the affected reports themselves
3. Mark PDFs as not processed for re-scraping

### Step 3: Add Safeguards
1. Add donor_full_address column (preserve original)
2. Add validation in Python processor to detect shifted data
3. Skip and log reports with detected shift issues

### Step 4: Reprocess
1. Run with fixed address parser
2. Monitor for shift issues
3. May need R scraper fixes for persistent shift problems

## Implementation Scripts

### 1. `identify_all_issues.py`
- Find donations with bad states
- Find reports with shifted data (email="Phone:*", phone contains street patterns)
- Combine into single list of affected PDFs

### 2. `complete_cleanup.py`
- Delete ALL donations from affected reports
- Delete affected reports
- Reset PDFs to unprocessed

### 3. `add_validation.py`
- Update step3_concurrent.py with:
  - Fixed address parser (done)
  - Detection for shifted data
  - Skip reports with shift issues and log for manual review

## Why Complete Deletion is Required

Current upload code:
```python
response = requests.post(url, headers=self.supabase_headers, json=batch)
```

This is a simple POST with no deduplication. If Report X has:
- 50 good donations
- 10 bad donations (invalid states)

And we only delete the 10 bad ones, then re-scrape:
- Result: 60 good + 10 good = 70 total (20 duplicates!)

**MUST delete all 60 and re-scrape to get clean 60.**

## Detection Patterns

### Address Issue (Suite Numbers)
- State field contains 2-letter non-state codes
- Common: Ph, Ch, Sc, Ne, Sa, Tu, etc.

### Data Shift Issue  
- org_email contains "Phone:"
- org_phone contains address pattern (numbers + street names)
- org_address contains "Treasurer:"
- org_treasurer contains "Jurisdiction:"

## Expected Outcome

After cleanup and reprocessing:
- ~12,000+ donations deleted and re-scraped correctly
- ~1,300+ reports rebuilt with proper data
- No duplicates
- Addresses properly parsed with suites
- No shifted data (or logged for R scraper fix)