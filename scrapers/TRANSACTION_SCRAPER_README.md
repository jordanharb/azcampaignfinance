# Transaction Scraper Usage Guide

## Overview
The transaction scraper (`step4_fetch_transactions.py`) fetches campaign finance transaction data from the Arizona Secretary of State's website. It now includes:
- **Concurrent processing** with configurable workers
- **Efficient batch checking** for already-scraped entities
- **Auto-upload** to Supabase with periodic batching
- **Real-time progress** with ETA

## Installation

```bash
# Install required packages
pip install requests

# Set environment variables (optional, defaults are provided)
export SUPABASE_URL='your_supabase_url'
export SUPABASE_KEY='your_supabase_key'
```

## Basic Usage

### 1. Scrape All Entities (Default)
```bash
# Scrape all entities from Supabase, skip already-scraped ones
python step4_fetch_transactions.py

# With 20 concurrent workers for faster processing
python step4_fetch_transactions.py --workers 20
```

### 2. Scrape and Upload to Database
```bash
# Scrape and auto-upload to Supabase
python step4_fetch_transactions.py --upload

# With more workers for speed
python step4_fetch_transactions.py --upload --workers 30
```

### 3. Scrape Specific Number of Entities
```bash
# Process first 100 entities
python step4_fetch_transactions.py --limit 100

# Process entities 100-200
python step4_fetch_transactions.py --start-from 100 --limit 100
```

### 4. Force Re-scrape (Ignore Existing Data)
```bash
# Re-scrape all entities even if already in database
python step4_fetch_transactions.py --force-rescrape --upload
```

### 5. Save to JSON Files
```bash
# Save transaction data to JSON files (in campaign_finance_transactions/)
python step4_fetch_transactions.py --save-files
```

### 6. Process Single Entity
```bash
# Scrape specific entity by ID
python step4_fetch_transactions.py --entity-id 100566
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--upload` | Upload results to Supabase database | False |
| `--workers N` | Number of concurrent workers | 10 |
| `--limit N` | Limit number of entities to process | None (all) |
| `--entity-id ID` | Process specific entity ID | None |
| `--start-from N` | Start from entity index (for resuming) | 0 |
| `--save-files` | Save transaction data to JSON files | False |
| `--force-rescrape` | Force re-scraping, ignore existing data | False |
| `--skip-scraped` | Skip entities already in database | True |
| `--max-retries N` | Maximum retries for failed requests | 5 |

## Performance Tips

### Optimal Worker Count
- **10 workers** (default): Safe, stable rate
- **20-30 workers**: Faster, good for large batches
- **50+ workers**: Maximum speed, monitor for rate limits

### Memory Usage
The scraper batches uploads every 100 entities or 60 seconds to manage memory efficiently.

### Resume After Interruption
```bash
# If interrupted at entity 500 of 1000
python step4_fetch_transactions.py --start-from 500 --upload
```

## Features

### Efficient Batch Checking
- Checks which entities are already scraped in batches of 500
- Dramatically reduces startup time
- Automatically skips scraped entities unless `--force-rescrape`

### Concurrent Processing
- Multiple workers process entities in parallel
- Configurable worker count with `--workers`
- Automatic rate limiting between requests

### Auto-Upload with Batching
- Uploads every 100 entities or 60 seconds
- Handles foreign key relationships properly
- Uploads entities before transactions

### Progress Tracking
- Real-time progress display with:
  - Entities processed/total
  - Success/failure/skipped counts
  - Transaction count
  - Processing rate (entities/sec)
  - Estimated time remaining (ETA)

### Graceful Shutdown
- Ctrl+C triggers graceful shutdown
- Uploads remaining data before exit
- No data loss on interruption

## Output

### Console Output
```
📊 Progress: 234/1000 | ✅ 200 | ❌ 4 | ⏭️ 30 | 💰 45,234 transactions | ⚡ 2.3/sec | ⏱️ ETA: 0:05:33
```

### Log File
Detailed logs saved to: `campaign_finance_transactions/scraper_v3.log`

### JSON Files (if --save-files)
Transaction data saved to: `campaign_finance_transactions/entity_{id}_transactions.json`

## Troubleshooting

### Rate Limiting
If you see many failures:
- Reduce workers: `--workers 5`
- Increase retries: `--max-retries 10`

### Memory Issues
The scraper automatically manages memory by:
- Batching uploads periodically
- Clearing processed data after upload

### Network Errors
The scraper includes:
- Automatic retry with exponential backoff
- Configurable retry attempts
- Graceful error handling

## Example Workflows

### Full Database Update
```bash
# Update database with all new transactions
python step4_fetch_transactions.py --upload --workers 20
```

### Test Run
```bash
# Test with 10 entities, save to files
python step4_fetch_transactions.py --limit 10 --save-files
```

### Production Run
```bash
# Full scrape with optimal settings
python step4_fetch_transactions.py --upload --workers 30 --max-retries 10
```

### Debug Single Entity
```bash
# Debug specific entity with file output
python step4_fetch_transactions.py --entity-id 100566 --save-files
```