# Arizona Campaign Finance Database Schema

This document describes all database tables related to the Arizona "See The Money" campaign finance data scraping project.

## Core Entity Tables

### `cf_entities`
Central table for all campaign finance entities (candidates, committees, PACs).
```sql
CREATE TABLE public.cf_entities (
  entity_id integer NOT NULL PRIMARY KEY,
  entity_url character varying,
  primary_committee_name character varying,
  primary_candidate_name character varying,
  total_records integer DEFAULT 0,
  earliest_activity date,
  latest_activity date,
  total_income_all_records numeric DEFAULT 0,
  total_expense_all_records numeric DEFAULT 0,
  max_cash_balance numeric DEFAULT 0,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  last_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

### `cf_entity_records`
Detailed records for each entity, tracking multiple committee registrations.
```sql
CREATE TABLE public.cf_entity_records (
  record_id integer NOT NULL PRIMARY KEY,
  entity_id integer REFERENCES cf_entities(entity_id),
  entity_name character varying,
  entity_first_name character varying,
  committee_name character varying,
  entity_type character varying,
  office_name character varying,
  office_id integer,
  office_type_id integer,
  party_name character varying,
  party_id integer,
  cash_balance numeric DEFAULT 0,
  income numeric DEFAULT 0,
  expense numeric DEFAULT 0,
  ie_support numeric DEFAULT 0,
  ie_opposition numeric DEFAULT 0,
  bme_for numeric DEFAULT 0,
  bme_against numeric DEFAULT 0,
  committee_status character varying,
  registration_date date,
  termination_date date,
  committee_address text,
  mailing_address text,
  phone character varying,
  email character varying,
  chairman character varying,
  treasurer character varying,
  candidate character varying,
  designee character varying,
  is_primary_record boolean DEFAULT false,
  record_source character varying,
  record_date date,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

## Transaction Tables

### `cf_transactions`
Main transaction table with all financial transactions (contributions, expenditures, etc.).
```sql
CREATE TABLE public.cf_transactions (
  public_transaction_id bigint NOT NULL PRIMARY KEY,
  transaction_id bigint NOT NULL,
  entity_id integer REFERENCES cf_entities(entity_id),
  transaction_entity_id integer REFERENCES cf_transaction_entities(entity_id),
  committee_id integer,
  committee_unique_id integer,
  committee_name character varying,
  transaction_date date,
  transaction_date_timestamp timestamp without time zone,
  transaction_date_year integer,
  transaction_date_year_month date,
  transaction_type_id integer,
  transaction_type character varying,
  transaction_type_disposition_id integer,
  amount numeric,
  transaction_name_id integer,
  transaction_name_group_id integer,
  transaction_entity_type_id integer,
  transaction_first_name character varying,
  transaction_middle_name character varying,
  transaction_last_name character varying,
  received_from_or_paid_to text,
  transaction_occupation character varying,
  transaction_employer character varying,
  transaction_city character varying,
  transaction_state character varying,
  transaction_zip_code character varying,
  entity_type_id integer,
  entity_description character varying,
  transaction_group_number integer,
  transaction_group_name character varying,
  transaction_group_color character varying,
  committee_group_number integer,
  committee_group_name character varying,
  committee_group_color character varying,
  subject_committee_id integer,
  subject_committee_name character varying,
  subject_committee_name_id integer,
  subject_group_number integer,
  is_for_benefit boolean,
  benefited_opposed character varying,
  candidate_cycle_id integer,
  candidate_office_type_id integer,
  candidate_office_id integer,
  candidate_party_id integer,
  candidate_first_name character varying,
  candidate_middle_name character varying,
  candidate_last_name character varying,
  ballot_measure_id integer,
  ballot_measure_number character varying,
  jurisdiction_id integer DEFAULT 0,
  jurisdiction_name character varying DEFAULT 'Arizona Secretary of State',
  report_id integer,
  memo text,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  last_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

### `cf_transaction_entities`
Entities involved in transactions (donors, vendors, etc.).
```sql
CREATE TABLE public.cf_transaction_entities (
  entity_id integer NOT NULL PRIMARY KEY,
  entity_name character varying,
  first_name character varying,
  middle_name character varying,
  last_name character varying,
  entity_type_id integer,
  entity_type_description character varying,
  group_number integer,
  group_id integer,
  total_contributions numeric DEFAULT 0,
  total_expenditures numeric DEFAULT 0,
  transaction_count integer DEFAULT 0,
  unique_committees_count integer DEFAULT 0,
  first_transaction_date date,
  last_transaction_date date,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  last_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

### `cf_transaction_summary`
Aggregated transaction statistics per entity.
```sql
CREATE TABLE public.cf_transaction_summary (
  entity_id integer NOT NULL PRIMARY KEY REFERENCES cf_entities(entity_id),
  total_contributions numeric DEFAULT 0,
  individual_contributions numeric DEFAULT 0,
  pac_contributions numeric DEFAULT 0,
  business_contributions numeric DEFAULT 0,
  party_contributions numeric DEFAULT 0,
  candidate_contributions numeric DEFAULT 0,
  other_contributions numeric DEFAULT 0,
  contribution_count integer DEFAULT 0,
  unique_contributors integer DEFAULT 0,
  total_expenditures numeric DEFAULT 0,
  operating_expenditures numeric DEFAULT 0,
  campaign_expenditures numeric DEFAULT 0,
  independent_expenditures numeric DEFAULT 0,
  other_expenditures numeric DEFAULT 0,
  expenditure_count integer DEFAULT 0,
  unique_vendors integer DEFAULT 0,
  total_loans_received numeric DEFAULT 0,
  total_loans_made numeric DEFAULT 0,
  outstanding_loans numeric DEFAULT 0,
  first_transaction_date date,
  last_transaction_date date,
  top_contributors jsonb,
  top_vendors jsonb,
  top_transaction_types jsonb,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  last_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

### `cf_transaction_processing`
Tracks scraping progress for each entity's transactions.
```sql
CREATE TABLE public.cf_transaction_processing (
  entity_id integer NOT NULL PRIMARY KEY REFERENCES cf_entities(entity_id),
  total_transactions integer DEFAULT 0,
  pages_processed integer DEFAULT 0,
  last_page_processed integer DEFAULT 0,
  processing_status character varying DEFAULT 'pending',
  last_processed_at timestamp without time zone,
  next_process_after timestamp without time zone,
  error_message text,
  retry_count integer DEFAULT 0,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  last_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

## Report Tables

### `cf_reports`
Campaign finance reports filed by committees.
```sql
CREATE TABLE public.cf_reports (
  report_id integer NOT NULL PRIMARY KEY,
  pdf_id integer REFERENCES cf_report_pdfs(pdf_id),
  entity_id integer REFERENCES cf_entities(entity_id),
  record_id integer REFERENCES cf_entity_records(record_id),
  rpt_title character varying,
  rpt_name character varying,
  rpt_cycle integer,
  rpt_file_date date,
  rpt_period character varying,
  org_name character varying,
  org_email character varying,
  org_phone character varying,
  org_address text,
  org_treasurer character varying,
  org_jurisdiction character varying,
  total_donations numeric,
  total_expenditures numeric,
  donation_count integer,
  processed_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

### `cf_report_pdfs`
PDF documents for campaign finance reports.
```sql
CREATE TABLE public.cf_report_pdfs (
  pdf_id integer NOT NULL PRIMARY KEY,
  entity_id integer REFERENCES cf_entities(entity_id),
  record_id integer REFERENCES cf_entity_records(record_id),
  committee_report_id integer UNIQUE,
  report_name character varying,
  pdf_url text NOT NULL,
  filing_date date,
  filing_period_end_date date,
  cycle_year integer,
  report_status character varying,
  fines_due numeric,
  local_csv_path character varying,
  csv_converted boolean DEFAULT false,
  conversion_date timestamp without time zone
);
```

### `cf_donations`
Individual donations extracted from reports.
```sql
CREATE TABLE public.cf_donations (
  donation_id integer NOT NULL PRIMARY KEY,
  report_id integer REFERENCES cf_reports(report_id),
  entity_id integer REFERENCES cf_entities(entity_id),
  record_id integer REFERENCES cf_entity_records(record_id),
  donor_name character varying,
  donor_addr text,
  donor_city character varying,
  donor_state character varying,
  donor_zip character varying,
  donor_occupation character varying,
  donor_employer character varying,
  donation_date date,
  donation_amt numeric,
  donation_type character varying,
  cycle_to_date_amt numeric,
  page_num integer,
  page_type character varying,
  meta_segment_name character varying,
  meta_file_name character varying,
  donor_person_id integer REFERENCES cf_persons(person_id),
  is_pac boolean DEFAULT false,
  is_corporate boolean DEFAULT false,
  import_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

## Lookup Tables

### `cf_transaction_types`
Types of transactions (contribution, expenditure, loan, etc.).
```sql
CREATE TABLE public.cf_transaction_types (
  transaction_type_id integer NOT NULL PRIMARY KEY,
  transaction_type_name character varying NOT NULL,
  transaction_disposition_id integer,
  disposition_name character varying,
  is_contribution boolean DEFAULT false,
  is_expenditure boolean DEFAULT false,
  is_loan boolean DEFAULT false,
  is_transfer boolean DEFAULT false,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

### `cf_transaction_groups`
Groupings for transactions.
```sql
CREATE TABLE public.cf_transaction_groups (
  group_number integer NOT NULL PRIMARY KEY,
  group_name character varying,
  group_color character varying,
  group_category character varying,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

### `cf_entity_types`
Types of entities (Individual, Business, PAC, etc.).
```sql
CREATE TABLE public.cf_entity_types (
  entity_type_id integer NOT NULL PRIMARY KEY,
  entity_type_name character varying,
  entity_category character varying,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

## People and Mapping Tables

### `cf_persons`
Normalized person records across all campaign finance data.
```sql
CREATE TABLE public.cf_persons (
  person_id integer NOT NULL PRIMARY KEY,
  full_name character varying NOT NULL,
  first_name character varying,
  last_name character varying,
  middle_name character varying,
  legislator_id integer,
  normalized_name character varying,
  aliases ARRAY,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
```

### `cf_entity_legislator_map`
Maps campaign finance entities to legislators.
```sql
CREATE TABLE public.cf_entity_legislator_map (
  map_id integer NOT NULL PRIMARY KEY,
  entity_id integer REFERENCES cf_entities(entity_id),
  legislator_id integer,
  person_id integer REFERENCES cf_persons(person_id),
  record_ids ARRAY,
  offices_sought ARRAY,
  election_years ARRAY,
  is_primary_entity boolean DEFAULT false,
  verified boolean DEFAULT false,
  verification_source character varying,
  verification_date date,
  notes text
);
```

## Table Relationships

### Primary Relationships:
- `cf_entities` → `cf_entity_records` (1:many) - Each entity can have multiple committee records
- `cf_entities` → `cf_transactions` (1:many) - Each entity has many transactions
- `cf_transaction_entities` → `cf_transactions` (1:many) - Each donor/vendor appears in many transactions
- `cf_entities` → `cf_reports` (1:many) - Each entity files multiple reports
- `cf_reports` → `cf_donations` (1:many) - Each report contains multiple donations
- `cf_entity_types` → `cf_transaction_entities` (1:many) - Categorizes transaction entities
- `cf_transaction_types` → `cf_transactions` (1:many) - Categorizes transactions

### Key Foreign Keys:
- `cf_transactions.entity_id` → `cf_entities.entity_id`
- `cf_transactions.transaction_entity_id` → `cf_transaction_entities.entity_id`
- `cf_donations.report_id` → `cf_reports.report_id`
- `cf_donations.entity_id` → `cf_entities.entity_id`
- `cf_entity_legislator_map.entity_id` → `cf_entities.entity_id`
- `cf_entity_legislator_map.person_id` → `cf_persons.person_id`

## Data Flow

1. **Entity Discovery**: `cf_entities` populated from main entity list
2. **Entity Details**: `cf_entity_records` populated with committee details
3. **Transaction Scraping**: 
   - `cf_transaction_entities` populated with unique donors/vendors
   - `cf_transactions` populated with all financial transactions
   - `cf_transaction_processing` tracks scraping progress
4. **Report Processing**: 
   - `cf_report_pdfs` tracks PDF reports
   - `cf_reports` contains report metadata
   - `cf_donations` contains extracted donation details
5. **Aggregation**: `cf_transaction_summary` computed from transaction data
6. **Mapping**: `cf_entity_legislator_map` links entities to legislators

## Important Notes

- All `entity_id` values come from the Arizona Secretary of State system
- The `transaction_entity_id` in `cf_transactions` links to donors/vendors in `cf_transaction_entities`
- The `ReceivedFromOrPaidTo` field in transactions is parsed to extract entity IDs
- Foreign key constraints ensure data integrity between related tables
- Transaction processing tracks progress to allow resuming interrupted scraping