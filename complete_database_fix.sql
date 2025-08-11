-- =====================================================
-- COMPLETE DATABASE FIX FOR ARIZONA CAMPAIGN FINANCE
-- =====================================================
-- This script fixes all API errors and optimizes performance for heavy data loads
-- Author: System
-- Date: 2025

-- =====================================================
-- PART 1: CREATE MISSING INDEXES FOR PERFORMANCE
-- =====================================================

-- Indexes for cf_transactions (Heavy table - optimize for common queries)
CREATE INDEX IF NOT EXISTS idx_cf_transactions_entity_date 
    ON cf_transactions(entity_id, transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_cf_transactions_date 
    ON cf_transactions(transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_cf_transactions_amount 
    ON cf_transactions(amount) WHERE amount > 0;
CREATE INDEX IF NOT EXISTS idx_cf_transactions_type 
    ON cf_transactions(transaction_type);

-- Indexes for cf_donations (Heavy table - optimize for pagination)
CREATE INDEX IF NOT EXISTS idx_cf_donations_entity_date 
    ON cf_donations(entity_id, donation_date DESC);
CREATE INDEX IF NOT EXISTS idx_cf_donations_report_date 
    ON cf_donations(report_id, donation_date DESC);
CREATE INDEX IF NOT EXISTS idx_cf_donations_amount 
    ON cf_donations(donation_amt) WHERE donation_amt > 0;

-- Indexes for cf_reports (Join optimization)
CREATE INDEX IF NOT EXISTS idx_cf_reports_entity_date 
    ON cf_reports(entity_id, rpt_file_date DESC);

-- =====================================================
-- PART 2: DROP EXISTING FUNCTIONS TO AVOID CONFLICTS
-- =====================================================

DROP FUNCTION IF EXISTS public.get_entity_transactions_paginated(int, int, int);
DROP FUNCTION IF EXISTS public.get_entity_transactions_csv(int);
DROP FUNCTION IF EXISTS public.get_entity_donations_by_report(int, int, int);
DROP FUNCTION IF EXISTS public.get_entity_donations_csv(int);
DROP FUNCTION IF EXISTS public.get_entity_reports_detailed(int);
DROP FUNCTION IF EXISTS public.get_entity_reports_csv(int);
DROP FUNCTION IF EXISTS public.get_entity_summary_stats(int);

-- =====================================================
-- PART 3: OPTIMIZED PAGINATED TRANSACTIONS FUNCTION
-- =====================================================

CREATE OR REPLACE FUNCTION public.get_entity_transactions_paginated(
    p_entity_id int,
    p_limit int DEFAULT 50,
    p_offset int DEFAULT 0
)
RETURNS TABLE (
    transaction_id bigint,
    transaction_date date,
    amount numeric,
    transaction_type text,
    contributor_name text,
    vendor_name text,
    occupation text,
    employer text,
    city text,
    state text,
    zip_code text,
    memo text,
    total_count bigint
)
LANGUAGE plpgsql STABLE 
SECURITY DEFINER
SET statement_timeout = '10s'
AS $$
BEGIN
    -- Use CTE for better query optimization
    RETURN QUERY
    WITH counted_transactions AS (
        SELECT COUNT(*) OVER() as row_count
        FROM cf_transactions t
        WHERE t.entity_id = p_entity_id
    ),
    paginated_transactions AS (
        SELECT 
            t.public_transaction_id,
            t.transaction_date as trans_date,
            t.amount as trans_amount,
            COALESCE(t.transaction_type, 'Unknown')::text as trans_type,
            -- Handle contributor/vendor names based on amount
            CASE 
                WHEN t.amount > 0 THEN 
                    COALESCE(
                        NULLIF(TRIM(CONCAT_WS(' ', 
                            t.transaction_first_name, 
                            t.transaction_middle_name,
                            t.transaction_last_name
                        )), ''),
                        t.received_from_or_paid_to,
                        'Unknown'
                    )::text
                ELSE NULL 
            END as contrib_name,
            CASE 
                WHEN t.amount <= 0 THEN 
                    COALESCE(
                        NULLIF(TRIM(CONCAT_WS(' ', 
                            t.transaction_first_name,
                            t.transaction_middle_name,
                            t.transaction_last_name
                        )), ''),
                        t.received_from_or_paid_to,
                        'Unknown'
                    )::text
                ELSE NULL 
            END as vend_name,
            COALESCE(t.transaction_occupation, '')::text as trans_occupation,
            COALESCE(t.transaction_employer, '')::text as trans_employer,
            COALESCE(t.transaction_city, '')::text as trans_city,
            COALESCE(t.transaction_state, '')::text as trans_state,
            COALESCE(t.transaction_zip_code, '')::text as trans_zip,
            COALESCE(t.memo, '')::text as trans_memo,
            ct.row_count
        FROM cf_transactions t
        CROSS JOIN (SELECT row_count FROM counted_transactions LIMIT 1) ct
        WHERE t.entity_id = p_entity_id
        ORDER BY t.transaction_date DESC, t.public_transaction_id DESC
        LIMIT p_limit
        OFFSET p_offset
    )
    SELECT 
        public_transaction_id as transaction_id,
        trans_date as transaction_date,
        trans_amount as amount,
        trans_type as transaction_type,
        contrib_name as contributor_name,
        vend_name as vendor_name,
        trans_occupation as occupation,
        trans_employer as employer,
        trans_city as city,
        trans_state as state,
        trans_zip as zip_code,
        trans_memo as memo,
        row_count as total_count
    FROM paginated_transactions;
END;
$$;

-- =====================================================
-- PART 4: OPTIMIZED DONATIONS BY REPORT FUNCTION
-- =====================================================

CREATE OR REPLACE FUNCTION public.get_entity_donations_by_report(
    p_entity_id int,
    p_limit int DEFAULT 50,
    p_offset int DEFAULT 0
)
RETURNS TABLE (
    donation_id bigint,
    report_id int,
    report_name text,
    filing_date date,
    donation_date date,
    amount numeric,
    donor_name text,
    donor_type text,
    occupation text,
    employer text,
    address text,
    total_count bigint
)
LANGUAGE plpgsql STABLE 
SECURITY DEFINER
SET statement_timeout = '10s'
AS $$
BEGIN
    RETURN QUERY
    WITH counted_donations AS (
        SELECT COUNT(*) as row_count
        FROM cf_donations d
        WHERE d.entity_id = p_entity_id
    ),
    paginated_donations AS (
        SELECT 
            d.donation_id::bigint as don_id,
            d.report_id as rep_id,
            COALESCE(r.rpt_name, 'Unknown Report')::text as rep_name,
            r.rpt_file_date as file_date,
            d.donation_date as don_date,
            d.donation_amt as don_amount,
            COALESCE(d.donor_name, 'Unknown')::text as don_name,
            COALESCE(d.donation_type, 'Individual')::text as don_type,
            COALESCE(d.donor_occupation, '')::text as don_occupation,
            COALESCE(d.donor_employer, '')::text as don_employer,
            COALESCE(
                NULLIF(TRIM(CONCAT_WS(', ', 
                    d.donor_addr,
                    d.donor_city,
                    d.donor_state,
                    d.donor_zip
                )), ''),
                ''
            )::text as don_address,
            cd.row_count
        FROM cf_donations d
        LEFT JOIN cf_reports r ON d.report_id = r.report_id
        CROSS JOIN (SELECT row_count FROM counted_donations LIMIT 1) cd
        WHERE d.entity_id = p_entity_id
        ORDER BY d.donation_date DESC, d.donation_id DESC
        LIMIT p_limit
        OFFSET p_offset
    )
    SELECT 
        don_id as donation_id,
        rep_id as report_id,
        rep_name as report_name,
        file_date as filing_date,
        don_date as donation_date,
        don_amount as amount,
        don_name as donor_name,
        don_type as donor_type,
        don_occupation as occupation,
        don_employer as employer,
        don_address as address,
        row_count as total_count
    FROM paginated_donations;
END;
$$;

-- =====================================================
-- PART 5: ENTITY REPORTS DETAILED VIEW
-- =====================================================

CREATE OR REPLACE FUNCTION public.get_entity_reports_detailed(p_entity_id int)
RETURNS TABLE (
    report_id int,
    report_name text,
    report_period text,
    filing_date date,
    total_income numeric,
    total_expense numeric,
    cash_balance numeric,
    donation_count bigint,
    pdf_url text
)
LANGUAGE plpgsql STABLE 
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.report_id,
        COALESCE(r.rpt_name, 'Unknown')::text as report_name,
        COALESCE(r.rpt_period, '')::text as report_period,
        r.rpt_file_date as filing_date,
        COALESCE(r.total_income, 0) as total_income,
        COALESCE(r.total_expenditures, 0) as total_expense,
        COALESCE(r.cash_balance_ending, 0) as cash_balance,
        (SELECT COUNT(*) FROM cf_donations d WHERE d.report_id = r.report_id) as donation_count,
        COALESCE(p.pdf_url, '')::text as pdf_url
    FROM cf_reports r
    LEFT JOIN cf_report_pdfs p ON r.pdf_id = p.pdf_id
    WHERE r.entity_id = p_entity_id
    ORDER BY r.rpt_file_date DESC, r.report_id DESC;
END;
$$;

-- =====================================================
-- PART 6: CSV EXPORT FUNCTIONS (OPTIMIZED)
-- =====================================================

-- Transactions CSV Export
CREATE OR REPLACE FUNCTION public.get_entity_transactions_csv(p_entity_id int)
RETURNS TABLE (
    transaction_date date,
    amount numeric,
    transaction_type text,
    name text,
    occupation text,
    employer text,
    address text,
    memo text
)
LANGUAGE sql STABLE 
SECURITY DEFINER
AS $$
    SELECT 
        transaction_date,
        amount,
        COALESCE(transaction_type, 'Unknown')::text,
        COALESCE(
            NULLIF(TRIM(CONCAT_WS(' ', 
                transaction_first_name,
                transaction_middle_name,
                transaction_last_name
            )), ''),
            received_from_or_paid_to,
            'Unknown'
        )::text as name,
        COALESCE(transaction_occupation, '')::text as occupation,
        COALESCE(transaction_employer, '')::text as employer,
        COALESCE(
            NULLIF(TRIM(CONCAT_WS(', ', 
                transaction_city,
                transaction_state,
                transaction_zip_code
            )), ''),
            ''
        )::text as address,
        COALESCE(memo, '')::text
    FROM cf_transactions
    WHERE entity_id = p_entity_id
    ORDER BY transaction_date DESC, public_transaction_id DESC;
$$;

-- Donations CSV Export
CREATE OR REPLACE FUNCTION public.get_entity_donations_csv(p_entity_id int)
RETURNS TABLE (
    donation_date date,
    amount numeric,
    donor_name text,
    donor_type text,
    occupation text,
    employer text,
    address text,
    report_name text
)
LANGUAGE sql STABLE 
SECURITY DEFINER
AS $$
    SELECT 
        d.donation_date,
        d.donation_amt as amount,
        COALESCE(d.donor_name, 'Unknown')::text as donor_name,
        COALESCE(d.donation_type, 'Individual')::text as donor_type,
        COALESCE(d.donor_occupation, '')::text as occupation,
        COALESCE(d.donor_employer, '')::text as employer,
        COALESCE(
            NULLIF(TRIM(CONCAT_WS(', ', 
                d.donor_addr,
                d.donor_city,
                d.donor_state,
                d.donor_zip
            )), ''),
            ''
        )::text as address,
        COALESCE(r.rpt_name, '')::text as report_name
    FROM cf_donations d
    LEFT JOIN cf_reports r ON d.report_id = r.report_id
    WHERE d.entity_id = p_entity_id
    ORDER BY d.donation_date DESC, d.donation_id DESC;
$$;

-- Reports CSV Export
CREATE OR REPLACE FUNCTION public.get_entity_reports_csv(p_entity_id int)
RETURNS TABLE (
    report_name text,
    filing_date date,
    report_period text,
    total_income numeric,
    total_expense numeric,
    cash_balance numeric,
    donation_count int
)
LANGUAGE sql STABLE 
SECURITY DEFINER
AS $$
    SELECT 
        COALESCE(r.rpt_name, 'Unknown')::text as report_name,
        r.rpt_file_date as filing_date,
        COALESCE(r.rpt_period, '')::text as report_period,
        COALESCE(r.total_income, 0) as total_income,
        COALESCE(r.total_expenditures, 0) as total_expense,
        COALESCE(r.cash_balance_ending, 0) as cash_balance,
        COALESCE(r.donation_count, 0) as donation_count
    FROM cf_reports r
    WHERE r.entity_id = p_entity_id
    ORDER BY r.rpt_file_date DESC;
$$;

-- =====================================================
-- PART 7: SUMMARY STATISTICS FUNCTION
-- =====================================================

CREATE OR REPLACE FUNCTION public.get_entity_summary_stats(p_entity_id int)
RETURNS TABLE (
    total_raised numeric,
    total_spent numeric,
    cash_on_hand numeric,
    donation_count bigint,
    transaction_count bigint,
    report_count bigint,
    first_activity date,
    last_activity date,
    largest_donation numeric,
    average_donation numeric
)
LANGUAGE plpgsql STABLE 
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0) as total_raised,
        COALESCE(SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END), 0) as total_spent,
        COALESCE((
            SELECT r.cash_balance_ending 
            FROM cf_reports r 
            WHERE r.entity_id = p_entity_id 
            ORDER BY r.rpt_file_date DESC 
            LIMIT 1
        ), 0) as cash_on_hand,
        (SELECT COUNT(*) FROM cf_donations WHERE entity_id = p_entity_id) as donation_count,
        COUNT(t.*) as transaction_count,
        (SELECT COUNT(*) FROM cf_reports WHERE entity_id = p_entity_id) as report_count,
        MIN(t.transaction_date) as first_activity,
        MAX(t.transaction_date) as last_activity,
        COALESCE(MAX(CASE WHEN t.amount > 0 THEN t.amount ELSE NULL END), 0) as largest_donation,
        COALESCE(AVG(CASE WHEN t.amount > 0 THEN t.amount ELSE NULL END), 0) as average_donation
    FROM cf_transactions t
    WHERE t.entity_id = p_entity_id;
END;
$$;

-- =====================================================
-- PART 8: GRANT PERMISSIONS
-- =====================================================

-- Grant execute permissions to authenticated and anonymous users
GRANT EXECUTE ON FUNCTION public.get_entity_transactions_paginated(int, int, int) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_entity_donations_by_report(int, int, int) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_entity_reports_detailed(int) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_entity_transactions_csv(int) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_entity_donations_csv(int) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_entity_reports_csv(int) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_entity_summary_stats(int) TO anon, authenticated, service_role;

-- =====================================================
-- PART 9: ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================

-- Enable RLS on main tables (optional - only if you want to restrict access)
-- ALTER TABLE cf_transactions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE cf_donations ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE cf_reports ENABLE ROW LEVEL SECURITY;

-- Create policies for public read access (uncomment if RLS is enabled)
-- CREATE POLICY "Allow public read access" ON cf_transactions FOR SELECT USING (true);
-- CREATE POLICY "Allow public read access" ON cf_donations FOR SELECT USING (true);
-- CREATE POLICY "Allow public read access" ON cf_reports FOR SELECT USING (true);

-- =====================================================
-- PART 10: MATERIALIZED VIEWS FOR HEAVY QUERIES (OPTIONAL)
-- =====================================================

-- Create a materialized view for entity summaries to speed up dashboard loads
-- This is optional but recommended for frequently accessed entity summary pages

/*
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_entity_summaries AS
SELECT 
    e.entity_id,
    e.primary_candidate_name,
    e.primary_committee_name,
    COUNT(DISTINCT t.public_transaction_id) as total_transactions,
    COUNT(DISTINCT d.donation_id) as total_donations,
    COUNT(DISTINCT r.report_id) as total_reports,
    COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0) as total_raised,
    COALESCE(SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END), 0) as total_spent,
    COALESCE(MAX(r.cash_balance_ending), 0) as latest_cash_balance,
    MIN(t.transaction_date) as first_activity,
    MAX(t.transaction_date) as last_activity
FROM cf_entities e
LEFT JOIN cf_transactions t ON e.entity_id = t.entity_id
LEFT JOIN cf_donations d ON e.entity_id = d.entity_id
LEFT JOIN cf_reports r ON e.entity_id = r.entity_id
GROUP BY e.entity_id, e.primary_candidate_name, e.primary_committee_name;

-- Create index on materialized view
CREATE INDEX idx_mv_entity_summaries_entity_id ON mv_entity_summaries(entity_id);

-- Refresh the materialized view (run this periodically, e.g., daily)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_entity_summaries;
*/

-- =====================================================
-- PART 11: PERFORMANCE MONITORING
-- =====================================================

-- Create a function to analyze slow queries (for debugging)
CREATE OR REPLACE FUNCTION public.analyze_query_performance(p_entity_id int)
RETURNS TABLE (
    table_name text,
    row_count bigint,
    has_index boolean
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'cf_transactions'::text,
        COUNT(*) as row_count,
        EXISTS(
            SELECT 1 FROM pg_indexes 
            WHERE tablename = 'cf_transactions' 
            AND indexdef LIKE '%entity_id%'
        ) as has_index
    FROM cf_transactions
    WHERE entity_id = p_entity_id
    UNION ALL
    SELECT 
        'cf_donations'::text,
        COUNT(*) as row_count,
        EXISTS(
            SELECT 1 FROM pg_indexes 
            WHERE tablename = 'cf_donations' 
            AND indexdef LIKE '%entity_id%'
        ) as has_index
    FROM cf_donations
    WHERE entity_id = p_entity_id
    UNION ALL
    SELECT 
        'cf_reports'::text,
        COUNT(*) as row_count,
        EXISTS(
            SELECT 1 FROM pg_indexes 
            WHERE tablename = 'cf_reports' 
            AND indexdef LIKE '%entity_id%'
        ) as has_index
    FROM cf_reports
    WHERE entity_id = p_entity_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.analyze_query_performance(int) TO anon, authenticated, service_role;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Test the functions with entity 100035
/*
-- Test paginated transactions
SELECT * FROM get_entity_transactions_paginated(100035, 5, 0);

-- Test donations by report
SELECT * FROM get_entity_donations_by_report(100035, 5, 0);

-- Test reports detailed
SELECT * FROM get_entity_reports_detailed(100035);

-- Test summary stats
SELECT * FROM get_entity_summary_stats(100035);

-- Check performance
SELECT * FROM analyze_query_performance(100035);
*/

-- =====================================================
-- CLEANUP OLD/BROKEN FUNCTIONS
-- =====================================================

-- Drop any other conflicting functions that might exist
DROP FUNCTION IF EXISTS public.get_entity_transactions(int);
DROP FUNCTION IF EXISTS public.get_entity_donations(int);
DROP FUNCTION IF EXISTS public.get_entity_reports(int);

-- =====================================================
-- SUCCESS MESSAGE
-- =====================================================
-- All functions have been created/updated successfully.
-- The API should now work without type mismatch errors.
-- Performance has been optimized for large datasets.