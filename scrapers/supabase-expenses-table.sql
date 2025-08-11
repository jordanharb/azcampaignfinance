-- Create table for campaign finance expenses
-- This table stores all expenditures from Schedule E1, E3, E3a, E4

CREATE TABLE IF NOT EXISTS cf_expenses (
    expense_id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES cf_reports(report_id),
    entity_id INTEGER REFERENCES cf_entities(entity_id),
    pdf_id INTEGER REFERENCES cf_report_pdfs(pdf_id),
    
    -- Expense details
    expense_type VARCHAR(50), -- 'Operating', 'Contribution to Org', 'Contribution to Candidate', 'Small Aggregate'
    schedule_type VARCHAR(10), -- 'E1', 'E3', 'E3a', 'E4'
    
    -- Payee information
    payee_name VARCHAR(255),
    payee_addr VARCHAR(500),
    payee_type VARCHAR(100), -- Organization, Candidate, Vendor, etc.
    
    -- Transaction details
    expense_date DATE,
    expense_amt NUMERIC(12,2),
    expense_purpose VARCHAR(500),
    expense_category VARCHAR(100), -- Advertising, Consulting, Travel, etc.
    
    -- Additional fields for contributions
    beneficiary_candidate VARCHAR(255), -- For E3a
    beneficiary_committee VARCHAR(255), -- For E3
    
    -- Aggregation info
    is_aggregate BOOLEAN DEFAULT FALSE,
    aggregate_count INTEGER,
    
    -- Page tracking
    page_num INTEGER,
    page_type VARCHAR(20),
    
    -- Metadata
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta_segment_name VARCHAR(255),
    meta_file_name VARCHAR(255),
    
    -- Indexes for performance
    INDEX idx_expense_report (report_id),
    INDEX idx_expense_entity (entity_id),
    INDEX idx_expense_date (expense_date),
    INDEX idx_expense_type (expense_type)
);

-- Add summary fields to cf_reports for expenses
ALTER TABLE cf_reports 
ADD COLUMN IF NOT EXISTS total_expenses NUMERIC(12,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS expense_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS has_expenses BOOLEAN DEFAULT FALSE;

-- View to get report summary including both donations and expenses
CREATE OR REPLACE VIEW cf_report_summary AS
SELECT 
    r.*,
    COALESCE(r.total_donations, 0) + COALESCE(r.total_expenses, 0) as total_activity,
    COALESCE(r.donation_count, 0) + COALESCE(r.expense_count, 0) as total_transaction_count
FROM cf_reports r;