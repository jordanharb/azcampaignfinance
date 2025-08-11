-- Drop existing function if it exists
DROP FUNCTION IF EXISTS public.get_report_donations_csv(integer);

-- Function to get donations for a specific report with all available columns
CREATE OR REPLACE FUNCTION public.get_report_donations_csv(p_report_id integer)
RETURNS TABLE (
    donation_id bigint,
    report_id int,
    entity_id int,
    donation_date date,
    amount numeric,
    donor_name text,
    donor_first_name text,
    donor_last_name text,
    donor_organization text,
    donor_type text,
    occupation text,
    employer text,
    address text,
    city text,
    state text,
    zip text,
    country text,
    is_individual boolean
) 
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.donation_id::bigint,
        d.report_id::int,
        d.entity_id::int,
        d.donation_date,
        d.donation_amt as amount,
        COALESCE(d.donor_name, '')::text,
        COALESCE(d.donor_fname, '')::text as donor_first_name,
        COALESCE(d.donor_lname, '')::text as donor_last_name,
        COALESCE(d.donor_org, '')::text as donor_organization,
        COALESCE(d.donation_type, 'Unknown')::text as donor_type,
        COALESCE(d.donor_occupation, '')::text as occupation,
        COALESCE(d.donor_employer, '')::text as employer,
        COALESCE(d.donor_addr, '')::text as address,
        COALESCE(d.donor_city, '')::text as city,
        COALESCE(d.donor_state, '')::text as state,
        COALESCE(d.donor_zip, '')::text as zip,
        COALESCE(d.donor_country, '')::text as country,
        COALESCE(d.is_individual, false)::boolean
    FROM cf_donations d
    WHERE d.report_id = p_report_id
    ORDER BY d.donation_date DESC, d.donation_id;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.get_report_donations_csv(int) TO anon, authenticated, service_role;