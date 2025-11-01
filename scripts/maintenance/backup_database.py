"""Manual database backup script supporting compression, encryption, and retention cleanup."""
from __future__ import annotations

import argparse
import gzip
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

DEFAULT_BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/backups"))

logger = logging.getLogger("backup_database")


def create_backup(
    backup_type: str = "manual",
    compress: bool = True,
    encrypt: bool = False,
    verify: bool = True,
    cleanup: bool = False,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    start = time.monotonic()
    backup_dir = (output_dir or DEFAULT_BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)

    stem = _build_backup_stem(backup_type)
    raw_path = backup_dir / f"{stem}.sql"
    final_path = raw_path

    _run_pg_dump(raw_path)

    if compress:
        final_path = _compress_backup(raw_path)
        raw_path.unlink(missing_ok=True)

    encrypted = False
    if encrypt:
        final_path = _encrypt_backup(final_path)
        encrypted = True

    if verify:
        _quick_verify(final_path)

    retention_result: dict[str, Any] | None = None
    if cleanup:
        retention_result = cleanup_old_backups()

    duration = round(time.monotonic() - start, 2)
    size_mb = round(final_path.stat().st_size / (1024 * 1024), 2)

    logger.info(
        "Backup created",
        extra={
            "path": str(final_path),
            "type": backup_type,
            "size_mb": size_mb,
            "duration_seconds": duration,
            "compressed": compress,
            "encrypted": encrypted,
            "verified": verify,
        },
    )

    return {
        "filename": final_path.name,
        "path": str(final_path),
        "compressed": compress,
        "encrypted": encrypted,
        "verified": verify,
        "duration_seconds": duration,
        "size_mb": size_mb,
        "cleanup": retention_result,
    }


def _build_backup_stem(backup_type: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"backup_{backup_type}_{timestamp}"


def _run_pg_dump(output_path: Path) -> None:
    db_url = make_url(os.getenv("DATABASE_URL", ""))
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")

    env = os.environ.copy()
    if db_url.password:
        env["PGPASSWORD"] = db_url.password

    cmd = [
        "pg_dump",
        "-h",
        db_url.host or "localhost",
        "-p",
        str(db_url.port or 5432),
        "-U",
        db_url.username or "postgres",
        "-d",
        db_url.database or "postgres",
        "-F",
        "p",
        "--clean",
        "--if-exists",
    ]

    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:
        if process.stdout is None:
            raise RuntimeError("pg_dump did not provide stdout")

        with open(output_path, "wb") as dst:
            for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
                dst.write(chunk)

        stderr = process.stderr.read() if process.stderr else b""
        if process.wait() != 0:
            raise RuntimeError(f"pg_dump failed: {stderr.decode(errors='ignore')}")


def _compress_backup(input_path: Path) -> Path:
    compressed_path = input_path.with_suffix(input_path.suffix + ".gz")
    with open(input_path, "rb") as src, gzip.open(compressed_path, "wb") as dst:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            dst.write(chunk)
    return compressed_path


def _encrypt_backup(input_path: Path) -> Path:
    gpg_key = os.getenv("BACKUP_ENCRYPTION_KEY")
    if not gpg_key:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY must be set for encryption")

    encrypted_path = input_path.with_suffix(input_path.suffix + ".gpg")
    cmd = [
        "gpg",
        "--yes",
        "--batch",
        "--trust-model",
        "always",
        "--output",
        str(encrypted_path),
        "--recipient",
        gpg_key,
        "--encrypt",
        str(input_path),
    ]

    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gpg encryption failed: {result.stderr.decode(errors='ignore')}")

    input_path.unlink(missing_ok=True)
    return encrypted_path


def _quick_verify(backup_path: Path) -> None:
    if backup_path.suffix.endswith(".gpg"):
        decrypt_cmd = [
            "gpg",
            "--decrypt",
            "--batch",
            "--yes",
            str(backup_path),
        ]
        result = subprocess.run(decrypt_cmd, capture_output=True, check=False)
        if result.returncode != 0:
            raise RuntimeError("Encrypted backup verification failed")
    elif backup_path.suffix.endswith(".gz") or backup_path.name.endswith(".sql.gz"):
        with gzip.open(backup_path, "rb") as src:
            while src.read(1024 * 1024):
                pass
    else:
        if backup_path.stat().st_size == 0:
            raise RuntimeError("Backup file is empty")


def cleanup_old_backups(retention_config: dict[str, int] | None = None) -> dict[str, Any]:
    retention = retention_config or {
        "daily": int(os.getenv("BACKUP_RETENTION_DAILY", 7)),
        "weekly": int(os.getenv("BACKUP_RETENTION_WEEKLY", 4)),
        "monthly": int(os.getenv("BACKUP_RETENTION_MONTHLY", 12)),
    }

    backup_dir = DEFAULT_BACKUP_DIR
    backup_files = sorted(
        [p for p in backup_dir.glob("backup_*_*.sql*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    deleted_files: list[str] = []
    retained_counts: dict[str, int] = {"daily": 0, "weekly": 0, "monthly": 0}

    categorized: dict[str, list[Path]] = {"daily": [], "weekly": [], "monthly": []}
    for backup in backup_files:
        backup_type = _derive_backup_type(backup.name)
        if backup_type in categorized:
            categorized[backup_type].append(backup)

    for backup_type, files in categorized.items():
        limit = retention.get(backup_type, 0)
        retained_counts[backup_type] = min(len(files), limit)
        for index, file_path in enumerate(files):
            if index >= limit:
                file_path.unlink(missing_ok=True)
                deleted_files.append(file_path.name)

    if deleted_files:
        logger.info("Retention cleanup removed backups", extra={"files": deleted_files})

    return {
        "deleted_count": len(deleted_files),
        "deleted_files": deleted_files,
        "retained": retained_counts,
    }


def _derive_backup_type(filename: str) -> str:
    parts = filename.split("_")
    if len(parts) >= 3:
        return parts[1]
    return "unknown"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create PostgreSQL backups from Docker container")
    parser.add_argument("--type", default="manual", choices=["manual", "daily", "weekly", "monthly"], help="Backup type label")
    parser.add_argument("--compress", action=argparse.BooleanOptionalAction, default=True, help="Enable gzip compression")
    parser.add_argument("--encrypt", action=argparse.BooleanOptionalAction, default=False, help="Enable GPG encryption")
    parser.add_argument("--verify", action=argparse.BooleanOptionalAction, default=True, help="Verify backup after creation")
    parser.add_argument("--cleanup", action=argparse.BooleanOptionalAction, default=False, help="Run retention cleanup after backup")
    parser.add_argument("--output-dir", type=Path, default=None, help="Custom backup directory")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--verify-only", action="store_true", help="Only verify the latest backup without creating a new one")
    parser.add_argument("--backup-file", type=Path, default=None, help="Specific backup file to verify")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.verify_only:
        file_path = args.backup_file
        if file_path is None:
            file_path = _find_latest_backup()
            if file_path is None:
                logger.error("No backups found to verify")
                return 1
        try:
            _quick_verify(file_path)
            logger.info("Backup verification succeeded", extra={"file": str(file_path)})
            return 0
        except Exception as exc:  # pragma: no cover - CLI
            logger.error("Backup verification failed: %s", exc)
            return 1

    try:
        result = create_backup(
            backup_type=args.type,
            compress=args.compress,
            encrypt=args.encrypt,
            verify=args.verify,
            cleanup=args.cleanup,
            output_dir=args.output_dir,
        )
    except Exception as exc:  # pragma: no cover - CLI
        logger.error("Backup failed: %s", exc)
        return 1

    logger.info("Backup summary", extra=result)
    return 0


def _find_latest_backup() -> Path | None:
    candidates = sorted(
        [p for p in DEFAULT_BACKUP_DIR.glob("backup_*_*.sql*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


if __name__ == "__main__":
    raise SystemExit(main())
