# Arizona Campaign Finance Tracker

A comprehensive system for tracking Arizona campaign finance data with web interface, scrapers, and data processing tools.

## Project Structure

```
az-campaign-finance/
├── app/                    # Next.js 14 app directory
│   ├── page.tsx           # Search page
│   ├── layout.tsx         # Root layout with navigation
│   ├── about/             # About page
│   ├── bulk/              # Bulk export page
│   ├── candidate/[id]/    # Candidate detail pages
│   └── api/               # API routes for CSV downloads
├── lib/                    # Shared libraries
│   ├── rest.ts            # Supabase REST client
│   ├── types.ts           # TypeScript type definitions
│   └── constants.ts       # Application constants
├── scrapers/              # Data collection scripts
│   ├── step1_fetch_entities.py      # Fetch candidate/committee entities
│   ├── step2_fetch_reports.py       # Fetch financial reports
│   ├── step3_process_pdfs.py        # Process PDF documents
│   └── step4_fetch_transactions.py  # Fetch transaction details
├── pdf-scraper/           # PDF processing tools
│   └── DonationReportScrapingCode/  # PDF scraping implementation
└── supabase/              # Supabase edge functions
    └── functions/bulk_export/        # Bulk CSV export function
```

## Features

### Web Application
- **Search**: Fuzzy search for candidates and committees
- **Detail Views**: Comprehensive financial data for each entity
- **CSV Downloads**: Export reports and transactions
- **Bulk Export**: Download data for multiple entities at once

### Data Collection
- Automated scraping of Arizona Secretary of State data
- PDF processing for financial reports
- Transaction-level detail extraction
- Incremental updates support

## Getting Started

### Prerequisites
- Node.js 18+ and npm
- Python 3.8+ (for scrapers)
- Supabase account and database

### Installation

1. **Install Node dependencies:**
   ```bash
   npm install
   ```

2. **Set up environment variables:**
   The `.env.local` file is already configured with:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`

3. **Run the development server:**
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

### Running Scrapers

Navigate to the `scrapers/` directory and run scripts in order:

```bash
cd scrapers/

# Step 1: Fetch all entities
python step1_fetch_entities.py

# Step 2: Fetch reports for entities
python step2_fetch_reports.py

# Step 3: Process PDF documents
python step3_process_pdfs.py

# Step 4: Fetch transaction details
python step4_fetch_transactions.py
```

## Database Schema

The application uses PostgreSQL with the following main tables:
- `entities` - Candidates and committees
- `financial_records` - Financial record metadata
- `reports` - Detailed report information
- `transactions` - Individual contributions and expenditures

## Technologies

- **Frontend**: Next.js 14, React, TypeScript
- **Database**: PostgreSQL (Supabase)
- **Scrapers**: Python, BeautifulSoup, aiohttp
- **PDF Processing**: pdfplumber, tabula-py

## API Endpoints

- `GET /api/download/entity-reports?id={entity_id}` - Download reports CSV
- `GET /api/download/entity-transactions?id={entity_id}` - Download transactions CSV
- `POST /api/bulk-export` - Bulk export multiple entities

## Development

### Build for Production
```bash
npm run build
npm start
```

### Type Checking
```bash
npm run type-check
```

### Linting
```bash
npm run lint
```

## License

This project is for educational and transparency purposes. All data is publicly available from the Arizona Secretary of State.

## Support

For questions or issues, please create an issue in the GitHub repository.