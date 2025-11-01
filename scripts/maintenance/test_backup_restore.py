"""CLI utility to exercise backup and restore scripts end-to-end."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from scripts.maintenance import backup_database, restore_database


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run backup/restore verification using maintenance scripts."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional directory to place backup artifacts.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging output.",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Do not delete generated backup files after verification.",
    )
    parser.add_argument(
        "--backup-type",
        default="test",
        choices=["test", "manual", "daily", "weekly", "monthly"],
        help="Label to use for generated backups.",
    )
    return parser.parse_args(argv)


def run_workflow(args: argparse.Namespace) -> int:
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger = logging.getLogger("test_backup_restore")

    logger.info("Starting backup/restore workflow", extra={"backup_type": args.backup_type})

    try:
        backup_result = backup_database.create_backup(
            backup_type=args.backup_type,
            compress=True,
            encrypt=False,
            verify=True,
            cleanup=False,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        logger.error("Backup creation failed", exc_info=exc)
        return 1

    backup_path = Path(backup_result["path"])
    logger.info(
        "Backup created",
        extra={
            "filename": backup_result["filename"],
            "path": str(backup_path),
            "size_mb": backup_result.get("size_mb"),
        },
    )

    try:
        test_result = restore_database.test_restore(backup_path)
    except Exception as exc:
        logger.error("Test restore failed", exc_info=exc)
        return 1

    logger.info(
        "Test restore succeeded",
        extra={
            "test_database": test_result.get("test_database"),
            "tables": test_result.get("verification", {}).get("tables_count"),
            "rows": test_result.get("verification", {}).get("rows_estimate"),
        },
    )

    if not args.keep_artifacts:
        backup_path.unlink(missing_ok=True)
        logger.info("Removed backup artifact", extra={"path": str(backup_path)})

    logger.info("Backup/restore workflow completed successfully")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    return run_workflow(args)


if __name__ == "__main__":
    raise SystemExit(main())
