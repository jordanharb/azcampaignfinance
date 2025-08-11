-- Clear all campaign finance data (CAREFUL! This deletes everything)
-- Run in Supabase SQL editor

-- First, disable foreign key checks temporarily
SET session_replication_role = 'replica';

-- Clear all schedule tables (in order to avoid FK constraints)
TRUNCATE TABLE cf_donations CASCADE;
TRUNCATE TABLE cf_personal_contributions CASCADE;
TRUNCATE TABLE cf_committee_contributions CASCADE;
TRUNCATE TABLE cf_business_contributions CASCADE;
TRUNCATE TABLE cf_small_contributions CASCADE;
TRUNCATE TABLE cf_ccec_funding CASCADE;
TRUNCATE TABLE cf_qualifying_contributions CASCADE;
TRUNCATE TABLE cf_operating_expenses CASCADE;
TRUNCATE TABLE cf_independent_expenditures CASCADE;
TRUNCATE TABLE cf_contributions_made CASCADE;
TRUNCATE TABLE cf_small_expenses CASCADE;
TRUNCATE TABLE cf_loans_received CASCADE;
TRUNCATE TABLE cf_loans_made CASCADE;
TRUNCATE TABLE cf_other_receipts CASCADE;
TRUNCATE TABLE cf_transfers CASCADE;
TRUNCATE TABLE cf_cash_surplus CASCADE;
TRUNCATE TABLE cf_bill_payments CASCADE;

-- Clear reports table
TRUNCATE TABLE cf_reports CASCADE;

-- Reset the PDF processing flags (but keep the PDFs)
UPDATE cf_report_pdfs 
SET csv_converted = false, 
    conversion_date = NULL,
    error_message = NULL,
    row_count = NULL;

-- Reset the entity transaction flags
UPDATE cf_entities 
SET transactions_fetched = false,
    last_transaction_fetch = NULL,
    transaction_count = NULL;

-- Re-enable foreign key checks
SET session_replication_role = 'origin';

-- Show counts to confirm
SELECT 'cf_donations' as table_name, COUNT(*) as count FROM cf_donations
UNION ALL
SELECT 'cf_reports', COUNT(*) FROM cf_reports
UNION ALL
SELECT 'cf_personal_contributions', COUNT(*) FROM cf_personal_contributions
UNION ALL
SELECT 'PDFs to process', COUNT(*) FROM cf_report_pdfs WHERE csv_converted = false;