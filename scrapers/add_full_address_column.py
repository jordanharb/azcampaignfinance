#!/usr/bin/env python3
"""
Add donor_full_address column to cf_donations table
"""

import os
import requests
import psycopg2
from urllib.parse import urlparse

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ffdrtpknppmtkkbqsvek.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s')

print("="*70)
print("ADDING FULL ADDRESS COLUMN")
print("="*70)

# Note: Supabase doesn't allow direct ALTER TABLE via REST API
# This would typically be done in the Supabase dashboard or via SQL editor
# Here we'll document the SQL command needed

sql_command = """
-- Run this in Supabase SQL Editor:
ALTER TABLE cf_donations 
ADD COLUMN IF NOT EXISTS donor_full_address TEXT;

-- Verify the column was added:
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'cf_donations' 
AND column_name = 'donor_full_address';
"""

print("\n⚠️  Column addition needs to be done via Supabase Dashboard")
print("\nPlease run this SQL in the Supabase SQL Editor:")
print("-" * 50)
print(sql_command)
print("-" * 50)

print("\n📝 Instructions:")
print("1. Go to your Supabase dashboard")
print("2. Navigate to SQL Editor")
print("3. Run the above SQL command")
print("4. The column will be added to store full addresses")

print("\n" + "="*70)