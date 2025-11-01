# Maintenance Scripts

Utilities for manual maintenance and administration tasks.

## Duplicate Scanning

### scan_duplicates.py

Manual duplicate scanning utility for detecting and reporting duplicate company records.

**Usage:**

```bash
# Basic scan with default settings
python scripts/maintenance/scan_duplicates.py

# Dry run (report findings without creating candidates)
python scripts/maintenance/scan_duplicates.py --dry-run

# Custom batch size
python scripts/maintenance/scan_duplicates.py --batch-size 200

# Custom similarity threshold
python scripts/maintenance/scan_duplicates.py --threshold 0.75

# Verbose logging
python scripts/maintenance/scan_duplicates.py --verbose

# Combined options
python scripts/maintenance/scan_duplicates.py --dry-run --threshold 0.85 --verbose
```

**Options:**

- `--batch-size INT`: Number of companies to process per batch (default: from settings)
- `--threshold FLOAT`: Minimum similarity threshold 0.0-1.0 (default: from settings)
- `--dry-run`: Report findings without creating duplicate candidates
- `--verbose`: Enable debug-level logging

**Output:**

The script outputs a JSON summary:

```json
{
  "mode": "live",
  "scanned_companies": 15000,
  "candidates_created": 42,
  "batch_size": 100,
  "threshold": 0.8
}
```

**Examples:**

```bash
# Test with relaxed threshold to find more candidates
python scripts/maintenance/scan_duplicates.py --dry-run --threshold 0.70

# Production scan with stricter threshold
python scripts/maintenance/scan_duplicates.py --threshold 0.90 --batch-size 200

# Quick scan of small dataset
python scripts/maintenance/scan_duplicates.py --batch-size 50
```

**When to Use:**

- After bulk data imports
- When adjusting duplicate detection thresholds
- For periodic data quality audits
- Before/after major data cleanup operations

**Performance:**

- Batch processing prevents memory issues with large datasets
- Progress is logged every batch
- Database commits occur per batch to prevent transaction timeouts
- Typical scan rate: 100-500 companies/second (depends on data and thresholds)

## See Also

- [Duplicate Detection Documentation](../../docs/DUPLICATE-DETECTION.md)
- [API Endpoints](../../docs/DUPLICATE-DETECTION.md#api-endpoints)
- [Scheduled Jobs](../../docs/DUPLICATE-DETECTION.md#scheduled-jobs)
