# DATA CLEANUP AND FIX PLAN

## Current Situation Analysis

### Database State:
1. **cf_donations**: 128,911 records
   - Only 2 duplicates found in sample of 5,000 (minimal issue)
   - Properly linked to reports via `report_id`

2. **cf_reports**: 5,493 records  
   - NO duplicate PDF IDs (each PDF has exactly one report)
   - Properly linked to PDFs via `pdf_id`

3. **cf_report_pdfs**: 37,884 total PDFs
   - Only 167 marked as `csv_converted=true`
   - But actually 5,493 have reports (major mismatch!)
   - This means 5,326 PDFs were successfully processed but not marked

### Key Problems:
1. **Minor**: 2 duplicate donations (easily fixed)
2. **MAJOR**: 5,326 PDFs successfully processed but not marked as converted
3. **Result**: If we run the processor again, it will re-process 5,326 PDFs that are already done!

## PROPOSED FIX PLAN

### Step 1: Remove Duplicate Donations (Minor Fix)
- Remove the 2 duplicate donation records
- Keep the first occurrence of each duplicate

### Step 2: Properly Mark Processed PDFs (Major Fix)
- Find all PDFs that have a corresponding report in cf_reports
- Mark these as `csv_converted=true` with proper conversion_date
- This will prevent re-processing of already completed PDFs

### Step 3: Identify Actually Failed PDFs
- PDFs marked as converted but have NO reports = actually failed
- PDFs not marked as converted and have NO reports = need processing
- PDFs with /ReportFile/ pattern = unfiled reports (correctly skip)

### Step 4: Create Accurate Processing Queue
- Only process PDFs that:
  1. Are NOT marked as converted
  2. Do NOT have reports in the database
  3. Are NOT unfiled reports (/ReportFile/ pattern)

## Implementation Scripts

### 1. `fix_duplicates.py`
- Removes the minimal duplicate donations
- Safe operation - only affects 2 records

### 2. `fix_pdf_status.py`
- Marks all PDFs with reports as converted
- Updates 5,326 PDFs to correct status
- Prevents re-processing of completed work

### 3. `verify_status.py`
- Shows accurate counts of:
  - Truly processed PDFs (have reports)
  - Empty reports (processed but no donations found)
  - Failed PDFs (marked but no reports)
  - Pending PDFs (need processing)

## Expected Outcome

After fixes:
- ~5,493 PDFs correctly marked as processed
- ~32,391 PDFs remaining to be processed
- No duplicate processing
- Accurate tracking of what's done vs. pending

## Risk Assessment
- **Low Risk**: All operations are based on actual data relationships
- **No Data Loss**: We're only updating status fields, not deleting data
- **Reversible**: Can reset csv_converted flags if needed

## Execution Order
1. Run `fix_duplicates.py` first (removes 2 duplicates)
2. Run `fix_pdf_status.py` (marks 5,326 PDFs as processed)
3. Run `verify_status.py` (confirms correct state)
4. Resume PDF processing with confidence