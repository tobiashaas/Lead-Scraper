# Scripts

Utility scripts for KR Lead Scraper.

## Setup Scripts

### `init_db.py`
Initializes the database with tables and initial data.

```bash
python scripts/init_db.py
```

### `setup_ollama.sh`
Downloads and installs Ollama models for AI-powered scraping.

```bash
chmod +x scripts/setup_ollama.sh
./scripts/setup_ollama.sh
```

## Main Scripts

### `scrape_complete_pipeline.py`
Runs the complete scraping pipeline with all enrichment steps.

```bash
python scripts/scrape_complete_pipeline.py
```

## Example Scripts

The `examples/` directory contains various test and example scripts:

- `scrape_11880_test.py` - Test 11880 scraper
- `scrape_gelbe_seiten_test.py` - Test Gelbe Seiten scraper
- `scrape_multi_source.py` - Multi-source scraping example
- `debug_*.py` - Various debugging scripts

These are kept for reference and testing purposes.
