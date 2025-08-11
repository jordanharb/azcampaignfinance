-- Fix report totals by calculating from actual donations
-- This updates the total_donations and total_income fields in cf_reports

-- First, let's check what we have for a specific entity
SELECT 
    r.report_id,
    r.rpt_name,
    r.total_donations,
    r.total_income,
    r.donation_count,
    (SELECT COUNT(*) FROM cf_donations d WHERE d.report_id = r.report_id) as actual_donation_count,
    (SELECT COALESCE(SUM(d.donation_amt), 0) FROM cf_donations d WHERE d.report_id = r.report_id) as actual_donation_total
FROM cf_reports r
WHERE r.entity_id = 100035
ORDER BY r.rpt_file_date DESC
LIMIT 10;

-- Update the reports with correct totals calculated from donations
UPDATE cf_reports r
SET 
    total_donations = COALESCE((
        SELECT SUM(d.donation_amt) 
        FROM cf_donations d 
        WHERE d.report_id = r.report_id
    ), 0),
    total_income = COALESCE((
        SELECT SUM(d.donation_amt) 
        FROM cf_donations d 
        WHERE d.report_id = r.report_id
    ), 0),
    donation_count = COALESCE((
        SELECT COUNT(*) 
        FROM cf_donations d 
        WHERE d.report_id = r.report_id
    ), 0)
WHERE EXISTS (
    SELECT 1 FROM cf_donations d WHERE d.report_id = r.report_id
);

-- Verify the update worked for entity 100035
SELECT 
    r.report_id,
    r.rpt_name,
    r.total_donations,
    r.total_income,
    r.donation_count
FROM cf_reports r
WHERE r.entity_id = 100035
ORDER BY r.rpt_file_date DESC
LIMIT 10;

-- Update the entity summary to calculate total raised from donations, not transactions
-- This gives the TRUE total raised amount
UPDATE cf_entities e
SET 
    total_income_all_records = COALESCE((
        SELECT SUM(d.donation_amt) 
        FROM cf_donations d 
        WHERE d.entity_id = e.entity_id
    ), 0)
WHERE e.entity_id = 100035;

-- Verify entity totals
SELECT 
    entity_id,
    primary_candidate_name,
    total_income_all_records as total_raised_from_donations,
    (SELECT COUNT(*) FROM cf_donations WHERE entity_id = 100035) as total_donation_count,
    (SELECT SUM(donation_amt) FROM cf_donations WHERE entity_id = 100035) as calculated_total_raised
FROM cf_entities
WHERE entity_id = 100035;