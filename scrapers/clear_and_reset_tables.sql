-- Script to clear and reset the cf_reports and cf_donations tables
-- Run this in Supabase SQL editor to start fresh

-- First, clear the donations table (has foreign key to reports)
TRUNCATE TABLE cf_donations CASCADE;

-- Then clear the reports table
TRUNCATE TABLE cf_reports CASCADE;

-- Reset the sequences (auto-increment counters)
ALTER SEQUENCE cf_donations_donation_id_seq RESTART WITH 1;
ALTER SEQUENCE cf_reports_report_id_seq RESTART WITH 1;

-- Also reset the PDF tracking to mark them as not converted
UPDATE cf_report_pdfs 
SET csv_converted = false,
    conversion_date = NULL
WHERE csv_converted = true;

-- Verify the tables are empty
SELECT 
    'cf_donations' as table_name, 
    COUNT(*) as row_count 
FROM cf_donations
UNION ALL
SELECT 
    'cf_reports' as table_name, 
    COUNT(*) as row_count 
FROM cf_reports
UNION ALL
SELECT 
    'PDFs marked as converted' as table_name,
    COUNT(*) as row_count
FROM cf_report_pdfs
WHERE csv_converted = true;