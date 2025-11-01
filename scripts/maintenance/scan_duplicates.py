#!/usr/bin/env python
"""
Manual duplicate scanning utility

Usage:
    python scripts/maintenance/scan_duplicates.py [options]

Options:
    --batch-size INT    Batch size for scanning (default: from settings)
    --threshold FLOAT   Minimum similarity threshold (default: from settings)
    --dry-run          Report findings without creating candidates
    --verbose          Enable verbose logging
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.database.database import SessionLocal
from app.database.models import Company
from app.processors.deduplicator import Deduplicator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Manual duplicate scanning utility")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help=f"Batch size for scanning (default: {settings.deduplicator_scan_batch_size})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=f"Minimum similarity threshold 0.0-1.0 (default: {settings.deduplicator_candidate_threshold})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report findings without creating candidates",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def main():
    """Main execution"""
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    # Configuration
    batch_size = args.batch_size or settings.deduplicator_scan_batch_size
    threshold = args.threshold or settings.deduplicator_candidate_threshold

    logger.info("Starting manual duplicate scan")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Threshold: {threshold}")
    logger.info(f"Dry run: {args.dry_run}")

    # Create database session
    db = SessionLocal()

    try:
        # Count active companies
        total_companies = db.query(Company).filter(Company.is_active).count()
        logger.info(f"Total active companies: {total_companies}")

        if total_companies == 0:
            logger.warning("No active companies found")
            return 0

        # Initialize deduplicator
        deduplicator = Deduplicator(
            name_threshold=settings.deduplicator_name_threshold,
            address_threshold=settings.deduplicator_address_threshold,
            phone_threshold=settings.deduplicator_phone_threshold,
            website_threshold=settings.deduplicator_website_threshold,
            overall_threshold=int(threshold * 100),
        )

        if args.dry_run:
            logger.info("DRY RUN MODE - No candidates will be created")
            # Iterate through companies and report findings
            candidates_found = 0
            offset = 0

            while offset < total_companies:
                batch = (
                    db.query(Company)
                    .filter(Company.is_active)
                    .order_by(Company.id)
                    .limit(batch_size)
                    .offset(offset)
                    .all()
                )

                if not batch:
                    break

                for company in batch:
                    duplicates = deduplicator.find_duplicates(db, company, limit=5)
                    if duplicates:
                        candidates_found += len(duplicates)
                        for dup, similarity in duplicates:
                            logger.info(
                                f"Found duplicate: {company.company_name} <-> {dup.company_name} "
                                f"(similarity: {similarity:.1f}%)"
                            )

                offset += batch_size
                logger.info(f"Progress: {offset}/{total_companies}")

            result = {
                "mode": "dry_run",
                "scanned_companies": total_companies,
                "candidates_found": candidates_found,
                "batch_size": batch_size,
                "threshold": threshold,
            }

        else:
            # Actual scan with candidate creation
            candidates_created = deduplicator.scan_for_duplicates(db, batch_size=batch_size)
            db.commit()

            result = {
                "mode": "live",
                "scanned_companies": total_companies,
                "candidates_created": candidates_created,
                "batch_size": batch_size,
                "threshold": threshold,
            }

        # Print summary as JSON
        print("\n" + "=" * 60)
        print("SCAN SUMMARY")
        print("=" * 60)
        print(json.dumps(result, indent=2))
        print("=" * 60)

        logger.info("Scan completed successfully")
        return 0

    except Exception as exc:
        logger.exception("Scan failed", exc_info=True)
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
