-- Complete Arizona Campaign Finance Database Schema
-- Handles all schedule types from campaign finance reports
-- Fixed for PostgreSQL/Supabase compatibility

-- ============================================
-- INCOME TABLES
-- ============================================

-- Schedule C1: Personal and Family Contributions
CREATE TABLE IF NOT EXISTS cf_personal_contributions (
    contribution_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    contributor_name VARCHAR(255),
    contributor_relationship VARCHAR(100), -- Self, Spouse, Child, etc.
    contribution_date DATE,
    contribution_amt NUMERIC(12,2),
    cycle_to_date_amt NUMERIC(12,2),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_personal_report ON cf_personal_contributions(report_id);
CREATE INDEX IF NOT EXISTS idx_personal_entity ON cf_personal_contributions(entity_id);

-- Schedule C2: Individual Contributions (already exists as cf_donations)
-- Keep existing cf_donations table

-- Schedule C3: Contributions from Political Committees
CREATE TABLE IF NOT EXISTS cf_committee_contributions (
    contribution_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    committee_name VARCHAR(255),
    committee_id_number VARCHAR(50),
    committee_address VARCHAR(500),
    contribution_date DATE,
    contribution_amt NUMERIC(12,2),
    contribution_type VARCHAR(50), -- C3a, C3b, C3c
    cycle_to_date_amt NUMERIC(12,2),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_committee_report ON cf_committee_contributions(report_id);
CREATE INDEX IF NOT EXISTS idx_committee_entity ON cf_committee_contributions(entity_id);

-- Schedule C4: Business Contributions
CREATE TABLE IF NOT EXISTS cf_business_contributions (
    contribution_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    business_name VARCHAR(255),
    business_address VARCHAR(500),
    business_type VARCHAR(100),
    contribution_date DATE,
    contribution_amt NUMERIC(12,2),
    contribution_subtype VARCHAR(50), -- C4a, C4b, C4c
    cycle_to_date_amt NUMERIC(12,2),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_business_report ON cf_business_contributions(report_id);
CREATE INDEX IF NOT EXISTS idx_business_entity ON cf_business_contributions(entity_id);

-- Schedule C5: Small Contributions (Aggregated)
CREATE TABLE IF NOT EXISTS cf_small_contributions (
    aggregate_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    period_start DATE,
    period_end DATE,
    total_amount NUMERIC(12,2),
    contributor_count INTEGER,
    average_contribution NUMERIC(12,2),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_small_report ON cf_small_contributions(report_id);

-- Schedule C6: CCEC Funding and Matching
CREATE TABLE IF NOT EXISTS cf_ccec_funding (
    funding_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    funding_type VARCHAR(50), -- Initial, Matching, Supplemental
    funding_date DATE,
    funding_amt NUMERIC(12,2),
    qualifying_period VARCHAR(100),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ccec_report ON cf_ccec_funding(report_id);

-- Schedule C7: Qualifying Contributions
CREATE TABLE IF NOT EXISTS cf_qualifying_contributions (
    contribution_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    contributor_name VARCHAR(255),
    contributor_address VARCHAR(500),
    contribution_date DATE,
    contribution_amt NUMERIC(12,2), -- Usually $5
    verified BOOLEAN DEFAULT FALSE,
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_qualifying_report ON cf_qualifying_contributions(report_id);

-- Schedule L1: Loans Made to this Committee
CREATE TABLE IF NOT EXISTS cf_loans_received (
    loan_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    lender_name VARCHAR(255),
    lender_address VARCHAR(500),
    loan_date DATE,
    loan_amt NUMERIC(12,2),
    interest_rate NUMERIC(5,2),
    payment_due_date DATE,
    outstanding_balance NUMERIC(12,2),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_loans_received_report ON cf_loans_received(report_id);

-- Schedule R1: Other Receipts
CREATE TABLE IF NOT EXISTS cf_other_receipts (
    receipt_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    receipt_type VARCHAR(100), -- Interest, Dividends, Refunds, etc.
    source_name VARCHAR(255),
    receipt_date DATE,
    receipt_amt NUMERIC(12,2),
    receipt_description VARCHAR(500),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_other_receipts_report ON cf_other_receipts(report_id);

-- Schedule T1: Transfers (both from and to)
CREATE TABLE IF NOT EXISTS cf_transfers (
    transfer_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    transfer_direction VARCHAR(10), -- 'IN' or 'OUT'
    committee_name VARCHAR(255),
    committee_id_number VARCHAR(50),
    transfer_date DATE,
    transfer_amt NUMERIC(12,2),
    transfer_purpose VARCHAR(500),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_transfers_report ON cf_transfers(report_id);
CREATE INDEX IF NOT EXISTS idx_transfers_direction ON cf_transfers(transfer_direction);

-- Schedule S1: Cash Surplus
CREATE TABLE IF NOT EXISTS cf_cash_surplus (
    surplus_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    previous_committee_name VARCHAR(255),
    previous_committee_id VARCHAR(50),
    surplus_date DATE,
    surplus_amt NUMERIC(12,2),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_surplus_report ON cf_cash_surplus(report_id);

-- ============================================
-- EXPENDITURE TABLES
-- ============================================

-- Schedule E1: Operating Expenses
CREATE TABLE IF NOT EXISTS cf_operating_expenses (
    expense_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    payee_name VARCHAR(255),
    payee_address VARCHAR(500),
    expense_date DATE,
    expense_amt NUMERIC(12,2),
    expense_purpose VARCHAR(500),
    expense_category VARCHAR(100), -- Advertising, Consulting, Travel, etc.
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_operating_report ON cf_operating_expenses(report_id);
CREATE INDEX IF NOT EXISTS idx_operating_date ON cf_operating_expenses(expense_date);

-- Schedule E2: Independent & Ballot Measure Expenditures
CREATE TABLE IF NOT EXISTS cf_independent_expenditures (
    expense_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    expense_type VARCHAR(10), -- E2a, E2b, E2c
    payee_name VARCHAR(255),
    payee_address VARCHAR(500),
    expense_date DATE,
    expense_amt NUMERIC(12,2),
    
    -- For candidate-related expenditures
    candidate_name VARCHAR(255),
    candidate_office VARCHAR(100),
    support_or_oppose VARCHAR(10), -- SUPPORT or OPPOSE
    
    -- For ballot measures
    ballot_measure_number VARCHAR(50),
    ballot_measure_description VARCHAR(500),
    
    expense_purpose VARCHAR(500),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_independent_report ON cf_independent_expenditures(report_id);

-- Schedule E3: Contributions to Committees/Organizations
CREATE TABLE IF NOT EXISTS cf_contributions_made (
    contribution_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    contribution_type VARCHAR(10), -- E3a through E3f
    recipient_name VARCHAR(255),
    recipient_type VARCHAR(100), -- Candidate, Committee, Organization
    recipient_address VARCHAR(500),
    contribution_date DATE,
    contribution_amt NUMERIC(12,2),
    contribution_purpose VARCHAR(500),
    
    -- For candidate contributions
    candidate_office VARCHAR(100),
    election_date DATE,
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_contributions_made_report ON cf_contributions_made(report_id);

-- Schedule E4: Small Expenses (Aggregated)
CREATE TABLE IF NOT EXISTS cf_small_expenses (
    aggregate_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    period_start DATE,
    period_end DATE,
    total_amount NUMERIC(12,2),
    expense_count INTEGER,
    average_expense NUMERIC(12,2),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_small_expenses_report ON cf_small_expenses(report_id);

-- Schedule L2: Loans Made by This Committee
CREATE TABLE IF NOT EXISTS cf_loans_made (
    loan_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    borrower_name VARCHAR(255),
    borrower_address VARCHAR(500),
    loan_date DATE,
    loan_amt NUMERIC(12,2),
    interest_rate NUMERIC(5,2),
    payment_due_date DATE,
    outstanding_balance NUMERIC(12,2),
    loan_purpose VARCHAR(500),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_loans_made_report ON cf_loans_made(report_id);

-- Schedule D1: Bill Payments for Previous Expenditures
CREATE TABLE IF NOT EXISTS cf_bill_payments (
    payment_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    payee_name VARCHAR(255),
    payee_address VARCHAR(500),
    payment_date DATE,
    payment_amt NUMERIC(12,2),
    original_expense_date DATE,
    original_expense_amt NUMERIC(12,2),
    expense_description VARCHAR(500),
    
    page_num INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_bill_payments_report ON cf_bill_payments(report_id);

-- ============================================
-- UPDATE REPORTS TABLE
-- ============================================

-- Add comprehensive financial summary fields to cf_reports
ALTER TABLE cf_reports 
-- Income totals
ADD COLUMN IF NOT EXISTS total_personal_contributions NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_individual_contributions NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_committee_contributions NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_business_contributions NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_small_contributions NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_ccec_funding NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_qualifying_contributions NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_loans_received NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_other_receipts NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_transfers_in NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_cash_surplus NUMERIC(12,2) DEFAULT 0,

-- Expenditure totals
ADD COLUMN IF NOT EXISTS total_operating_expenses NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_independent_expenditures NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_contributions_made NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_small_expenses NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_transfers_out NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_loans_made NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_surplus_disposal NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_bill_payments NUMERIC(12,2) DEFAULT 0,

-- Summary fields
ADD COLUMN IF NOT EXISTS total_income NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS cash_balance_beginning NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS cash_balance_ending NUMERIC(12,2) DEFAULT 0,

-- Report metadata
ADD COLUMN IF NOT EXISTS report_type VARCHAR(50), -- Quarterly, Annual, Pre-Primary, etc.
ADD COLUMN IF NOT EXISTS is_amended BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_activity BOOLEAN DEFAULT TRUE;

-- Note: total_expenditures might already exist, so handle it separately
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'cf_reports' 
                   AND column_name = 'total_expenditures') THEN
        ALTER TABLE cf_reports ADD COLUMN total_expenditures NUMERIC(12,2) DEFAULT 0;
    END IF;
END $$;

-- ============================================
-- SUMMARY VIEWS
-- ============================================

-- Comprehensive report summary view
CREATE OR REPLACE VIEW cf_report_complete_summary AS
SELECT 
    r.*,
    -- Income counts
    (SELECT COUNT(*) FROM cf_personal_contributions WHERE report_id = r.report_id) as personal_contribution_count,
    (SELECT COUNT(*) FROM cf_donations WHERE report_id = r.report_id) as individual_contribution_count,
    (SELECT COUNT(*) FROM cf_committee_contributions WHERE report_id = r.report_id) as committee_contribution_count,
    (SELECT COUNT(*) FROM cf_business_contributions WHERE report_id = r.report_id) as business_contribution_count,
    
    -- Expenditure counts
    (SELECT COUNT(*) FROM cf_operating_expenses WHERE report_id = r.report_id) as operating_expense_count,
    (SELECT COUNT(*) FROM cf_independent_expenditures WHERE report_id = r.report_id) as independent_expenditure_count,
    (SELECT COUNT(*) FROM cf_contributions_made WHERE report_id = r.report_id) as contributions_made_count,
    
    -- Net calculations
    COALESCE(r.total_income, 0) - COALESCE(r.total_expenditures, 0) as net_funds,
    
    -- Activity flag
    CASE 
        WHEN COALESCE(r.total_income, 0) = 0 AND COALESCE(r.total_expenditures, 0) = 0 
        THEN FALSE 
        ELSE TRUE 
    END as has_financial_activity
FROM cf_reports r;

-- Entity financial summary across all reports
CREATE OR REPLACE VIEW cf_entity_financial_summary AS
SELECT 
    e.entity_id,
    e.primary_candidate_name,
    e.primary_committee_name,
    COUNT(DISTINCT r.report_id) as total_reports,
    SUM(r.total_income) as lifetime_income,
    SUM(r.total_expenditures) as lifetime_expenditures,
    SUM(r.total_individual_contributions) as lifetime_individual_contributions,
    SUM(r.total_operating_expenses) as lifetime_operating_expenses,
    MAX(r.rpt_file_date) as last_report_date,
    MIN(r.rpt_file_date) as first_report_date
FROM cf_entities e
LEFT JOIN cf_reports r ON e.entity_id = r.entity_id
GROUP BY e.entity_id, e.primary_candidate_name, e.primary_committee_name;

-- ============================================
-- ADDITIONAL INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX IF NOT EXISTS idx_reports_entity_date ON cf_reports(entity_id, rpt_file_date);
CREATE INDEX IF NOT EXISTS idx_reports_has_activity ON cf_reports(has_activity);
CREATE INDEX IF NOT EXISTS idx_reports_amended ON cf_reports(is_amended);