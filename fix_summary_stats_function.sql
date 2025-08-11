-- Drop and recreate the summary stats function to calculate from donations, not transactions
DROP FUNCTION IF EXISTS public.get_entity_summary_stats(int);

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
        -- Total raised from DONATIONS only (not transactions which include expenses)
        COALESCE((SELECT SUM(d.donation_amt) FROM cf_donations d WHERE d.entity_id = p_entity_id), 0) as total_raised,
        
        -- Total spent from negative transactions
        COALESCE((SELECT SUM(ABS(t.amount)) FROM cf_transactions t WHERE t.entity_id = p_entity_id AND t.amount < 0), 0) as total_spent,
        
        -- Cash on hand from latest report
        COALESCE((
            SELECT r.cash_balance_ending 
            FROM cf_reports r 
            WHERE r.entity_id = p_entity_id 
            ORDER BY r.rpt_file_date DESC 
            LIMIT 1
        ), 0) as cash_on_hand,
        
        -- Count of donations
        (SELECT COUNT(*) FROM cf_donations WHERE entity_id = p_entity_id) as donation_count,
        
        -- Count of all transactions
        (SELECT COUNT(*) FROM cf_transactions WHERE entity_id = p_entity_id) as transaction_count,
        
        -- Count of reports
        (SELECT COUNT(*) FROM cf_reports WHERE entity_id = p_entity_id) as report_count,
        
        -- First activity date
        LEAST(
            (SELECT MIN(donation_date) FROM cf_donations WHERE entity_id = p_entity_id),
            (SELECT MIN(transaction_date) FROM cf_transactions WHERE entity_id = p_entity_id)
        ) as first_activity,
        
        -- Last activity date
        GREATEST(
            (SELECT MAX(donation_date) FROM cf_donations WHERE entity_id = p_entity_id),
            (SELECT MAX(transaction_date) FROM cf_transactions WHERE entity_id = p_entity_id)
        ) as last_activity,
        
        -- Largest single donation
        COALESCE((SELECT MAX(donation_amt) FROM cf_donations WHERE entity_id = p_entity_id), 0) as largest_donation,
        
        -- Average donation amount
        COALESCE((SELECT AVG(donation_amt) FROM cf_donations WHERE entity_id = p_entity_id), 0) as average_donation;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.get_entity_summary_stats(int) TO anon, authenticated, service_role;

-- Test the function
SELECT * FROM get_entity_summary_stats(100035);