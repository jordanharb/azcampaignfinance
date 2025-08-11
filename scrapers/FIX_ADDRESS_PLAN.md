# Address Parsing Fix Plan

## Problem Analysis

Current parser fails when addresses have suite/unit numbers:
- `2323 N Central Ave,#304,Phoenix,AZ 85001` 
- Currently parsed as: addr="2323 N Central Ave", city="#304", state="Ph" ❌
- Should be: addr="2323 N Central Ave #304", city="Phoenix", state="AZ" ✅

## Issues Found
- Invalid state codes like "Ph", "Ch", "Gi", "Do", "STE", etc.
- These are actually truncated city names in the wrong field
- Affects addresses with suite/unit/apt numbers

## Fix Strategy

### 1. Update Address Parser
- Handle 4-part addresses: street, suite, city, state+zip
- Combine street+suite into single address field
- Add new `donor_full_address` column to preserve original

### 2. Database Schema Update
- Add `donor_full_address` column to cf_donations table

### 3. Clean Existing Bad Data
- Find all donations with invalid state codes (not 2-letter US states)
- Delete those donations
- Delete associated reports if they have no other donations
- Mark PDFs as not processed for re-scraping

### 4. Update PDF Processor
- Fix parse_address_components() function
- Add full address preservation

## Implementation Steps

1. `add_full_address_column.py` - Add new column to database
2. `fix_address_parser.py` - Update step3_concurrent.py with fixed parser
3. `find_bad_addresses.py` - Identify all bad entries
4. `clean_bad_addresses.py` - Delete bad data and reset PDFs
5. Re-run PDF processor for affected PDFs

## Expected Outcome
- All addresses properly parsed
- Suite numbers preserved in address field
- Cities and states in correct fields
- Original full address preserved for reference