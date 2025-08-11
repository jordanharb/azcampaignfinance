-- Add error_message column to cf_report_pdfs if it doesn't exist
-- This stores the reason why a PDF was skipped (e.g., "Report not filed - 404")

ALTER TABLE cf_report_pdfs 
ADD COLUMN IF NOT EXISTS error_message TEXT;

-- View how many PDFs are marked as skipped/errored
SELECT 
    COUNT(*) FILTER (WHERE error_message IS NOT NULL) as skipped_pdfs,
    COUNT(*) FILTER (WHERE error_message = 'Report not filed - 404') as not_filed_404,
    COUNT(*) FILTER (WHERE csv_converted = true AND error_message IS NULL) as successfully_converted,
    COUNT(*) FILTER (WHERE csv_converted = false) as pending_conversion,
    COUNT(*) as total_pdfs
FROM cf_report_pdfs;