-- ============================================
-- FIXED SQL FUNCTIONS - Cast varchar columns to text
-- ============================================

-- Drop existing functions
DROP FUNCTION IF EXISTS get_entity_financial_summary(INTEGER);
DROP FUNCTION IF EXISTS get_report_financial_summary(INTEGER);
DROP FUNCTION IF EXISTS get_entity_reports_with_totals(INTEGER);

-- ============================================
-- 1. FUNCTION FOR ENTITY FINANCIAL SUMMARY
-- ============================================

CREATE OR REPLACE FUNCTION get_entity_financial_summary(p_entity_id INTEGER)
RETURNS TABLE (
    total_raised NUMERIC,
    total_spent NUMERIC,
    net_amount NUMERIC,
    transaction_count INTEGER,
    donation_count INTEGER,
    expense_count INTEGER,
    earliest_transaction DATE,
    latest_transaction DATE,
    largest_donation NUMERIC,
    largest_expense NUMERIC
) 
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(SUM(CASE WHEN t.transaction_type_disposition_id = 1 THEN t.amount ELSE 0 END), 0) as total_raised,
        COALESCE(SUM(CASE WHEN t.transaction_type_disposition_id = 2 THEN t.amount ELSE 0 END), 0) as total_spent,
        COALESCE(SUM(CASE 
            WHEN t.transaction_type_disposition_id = 1 THEN t.amount 
            WHEN t.transaction_type_disposition_id = 2 THEN -t.amount 
            ELSE 0 
        END), 0) as net_amount,
        COUNT(*)::INTEGER as transaction_count,
        COUNT(CASE WHEN t.transaction_type_disposition_id = 1 THEN 1 END)::INTEGER as donation_count,
        COUNT(CASE WHEN t.transaction_type_disposition_id = 2 THEN 1 END)::INTEGER as expense_count,
        MIN(t.transaction_date) as earliest_transaction,
        MAX(t.transaction_date) as latest_transaction,
        COALESCE(MAX(CASE WHEN t.transaction_type_disposition_id = 1 THEN t.amount END), 0) as largest_donation,
        COALESCE(MAX(CASE WHEN t.transaction_type_disposition_id = 2 THEN t.amount END), 0) as largest_expense
    FROM cf_transactions t
    WHERE t.entity_id = p_entity_id;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION get_entity_financial_summary(INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION get_entity_financial_summary(INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION get_entity_financial_summary(INTEGER) TO service_role;

-- ============================================
-- 2. FUNCTION FOR REPORT FINANCIAL SUMMARY
-- ============================================

CREATE OR REPLACE FUNCTION get_report_financial_summary(p_report_id INTEGER)
RETURNS TABLE (
    report_id INTEGER,
    total_donations NUMERIC,
    total_expenses NUMERIC,
    net_amount NUMERIC,
    donation_count INTEGER,
    expense_count INTEGER,
    transaction_count INTEGER,
    avg_donation NUMERIC,
    avg_expense NUMERIC,
    largest_donation NUMERIC,
    largest_expense NUMERIC
) 
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p_report_id as report_id,
        COALESCE(SUM(CASE WHEN t.transaction_type_disposition_id = 1 THEN t.amount ELSE 0 END), 0) as total_donations,
        COALESCE(SUM(CASE WHEN t.transaction_type_disposition_id = 2 THEN t.amount ELSE 0 END), 0) as total_expenses,
        COALESCE(SUM(CASE 
            WHEN t.transaction_type_disposition_id = 1 THEN t.amount 
            WHEN t.transaction_type_disposition_id = 2 THEN -t.amount 
            ELSE 0 
        END), 0) as net_amount,
        COUNT(CASE WHEN t.transaction_type_disposition_id = 1 THEN 1 END)::INTEGER as donation_count,
        COUNT(CASE WHEN t.transaction_type_disposition_id = 2 THEN 1 END)::INTEGER as expense_count,
        COUNT(*)::INTEGER as transaction_count,
        COALESCE(AVG(CASE WHEN t.transaction_type_disposition_id = 1 THEN t.amount END), 0) as avg_donation,
        COALESCE(AVG(CASE WHEN t.transaction_type_disposition_id = 2 THEN t.amount END), 0) as avg_expense,
        COALESCE(MAX(CASE WHEN t.transaction_type_disposition_id = 1 THEN t.amount END), 0) as largest_donation,
        COALESCE(MAX(CASE WHEN t.transaction_type_disposition_id = 2 THEN t.amount END), 0) as largest_expense
    FROM cf_transactions t
    WHERE t.report_id = p_report_id;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION get_report_financial_summary(INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION get_report_financial_summary(INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION get_report_financial_summary(INTEGER) TO service_role;

-- ============================================
-- 3. FUNCTION FOR MULTIPLE REPORTS SUMMARY
-- ============================================

CREATE OR REPLACE FUNCTION get_entity_reports_with_totals(p_entity_id INTEGER)
RETURNS TABLE (
    report_id INTEGER,
    entity_id INTEGER,
    rpt_name TEXT,
    rpt_title TEXT,
    rpt_file_date DATE,
    rpt_period TEXT,
    rpt_cycle INTEGER,
    org_name TEXT,
    org_treasurer TEXT,
    pdf_url TEXT,
    filing_date DATE,
    filing_period_end_date DATE,
    total_donations NUMERIC,
    total_expenses NUMERIC,
    net_amount NUMERIC,
    donation_count INTEGER,
    expense_count INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.report_id,
        r.entity_id,
        r.rpt_name::TEXT,
        r.rpt_title::TEXT,
        r.rpt_file_date,
        r.rpt_period::TEXT,
        r.rpt_cycle,
        r.org_name::TEXT,
        r.org_treasurer::TEXT,
        p.pdf_url::TEXT,
        p.filing_date,
        p.filing_period_end_date,
        COALESCE(SUM(CASE WHEN t.transaction_type_disposition_id = 1 THEN t.amount ELSE 0 END), 0) as total_donations,
        COALESCE(SUM(CASE WHEN t.transaction_type_disposition_id = 2 THEN t.amount ELSE 0 END), 0) as total_expenses,
        COALESCE(SUM(CASE 
            WHEN t.transaction_type_disposition_id = 1 THEN t.amount 
            WHEN t.transaction_type_disposition_id = 2 THEN -t.amount 
            ELSE 0 
        END), 0) as net_amount,
        COUNT(CASE WHEN t.transaction_type_disposition_id = 1 THEN 1 END)::INTEGER as donation_count,
        COUNT(CASE WHEN t.transaction_type_disposition_id = 2 THEN 1 END)::INTEGER as expense_count
    FROM cf_reports r
    LEFT JOIN cf_report_pdfs p ON r.pdf_id = p.pdf_id
    LEFT JOIN cf_transactions t ON t.report_id = r.report_id
    WHERE r.entity_id = p_entity_id
    GROUP BY 
        r.report_id,
        r.entity_id,
        r.rpt_name,
        r.rpt_title,
        r.rpt_file_date,
        r.rpt_period,
        r.rpt_cycle,
        r.org_name,
        r.org_treasurer,
        p.pdf_url,
        p.filing_date,
        p.filing_period_end_date
    ORDER BY COALESCE(p.filing_date, r.rpt_file_date) DESC;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION get_entity_reports_with_totals(INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION get_entity_reports_with_totals(INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION get_entity_reports_with_totals(INTEGER) TO service_role;

-- ============================================
-- TEST THE FUNCTIONS
-- ============================================

-- Test entity financial summary (Daniel Hernandez)
SELECT * FROM get_entity_financial_summary(201600418);

-- Test entity reports with totals
SELECT * FROM get_entity_reports_with_totals(201600418);