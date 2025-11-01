"""Backup and restore maintenance jobs executed via RQ scheduler."""
from __future__ import annotations

import asyncio
import gzip
import logging
import os
import subprocess
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rq import get_current_job
from sqlalchemy.engine import make_url

from app.api.webhooks import dispatch_webhook_event
from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/backups"))


def backup_database_job(backup_type: str = "daily") -> dict[str, Any]:
    """Synchronously executed entry point for database backup jobs."""

    rq_job = get_current_job()
    if rq_job is not None:
        rq_job.meta["task"] = f"backup_{backup_type}"
        rq_job.save_meta()

    return asyncio.run(_backup_database_async(backup_type))


async def _backup_database_async(backup_type: str) -> dict[str, Any]:
    if not settings.backup_enabled:
        logger.info("Backup skipped because BACKUP_ENABLED is False")
        return {"skipped": True, "reason": "disabled"}

    start_time = time.monotonic()
    backup_dir = _ensure_backup_dir()
    file_stem = _build_backup_stem(backup_type)

    compression_enabled = settings.backup_compression_enabled
    encrypted = False
    cloud_synced = False

    raw_backup_path = backup_dir / f"{file_stem}.sql"
    final_backup_path: Path = raw_backup_path

    try:
        _run_pg_dump(raw_backup_path)

        if compression_enabled:
            final_backup_path = _compress_backup(raw_backup_path)
            raw_backup_path.unlink(missing_ok=True)
        else:
            final_backup_path = raw_backup_path

        if settings.backup_encryption_enabled and settings.backup_encryption_key:
            final_backup_path = _encrypt_backup(final_backup_path)
            encrypted = True

        if settings.backup_cloud_sync_enabled and settings.backup_cloud_bucket:
            cloud_synced = await _upload_backup_to_cloud(final_backup_path)

        size_mb = round(final_backup_path.stat().st_size / (1024 * 1024), 2)
        duration_seconds = round(time.monotonic() - start_time, 2)

        cleanup_result = cleanup_old_backups_job()

        payload = {
            "filename": final_backup_path.name,
            "path": str(final_backup_path),
            "size_mb": size_mb,
            "duration_seconds": duration_seconds,
            "encrypted": encrypted,
            "cloud_synced": cloud_synced,
            "cleanup": cleanup_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with suppress(Exception):
            await dispatch_webhook_event("backup.completed", payload)

        logger.info(
            "Database backup created",
            extra={
                "filename": final_backup_path.name,
                "size_mb": size_mb,
                "duration_seconds": duration_seconds,
                "encrypted": encrypted,
                "cloud_synced": cloud_synced,
            },
        )

        return payload
    except Exception as exc:
        logger.exception("Database backup failed", exc_info=True)
        with suppress(Exception):
            await dispatch_webhook_event(
                "backup.failed",
                {
                    "backup_type": backup_type,
                    "error": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        raise
    finally:
        if raw_backup_path.exists():
            raw_backup_path.unlink(missing_ok=True)


def verify_backup_job(backup_filename: str | None = None) -> dict[str, Any]:
    """Synchronously executed verification job that restores a backup to validate integrity."""

    rq_job = get_current_job()
    if rq_job is not None:
        rq_job.meta["task"] = "backup_verification"
        rq_job.save_meta()

    return asyncio.run(_verify_backup_async(backup_filename))


async def _verify_backup_async(backup_filename: str | None = None) -> dict[str, Any]:
    if not settings.backup_verification_enabled:
        logger.info("Backup verification skipped because BACKUP_VERIFICATION_ENABLED is False")
        return {"skipped": True, "reason": "verification_disabled"}

    backup_path = _resolve_backup_path(backup_filename, preferred_type="weekly")
    if backup_path is None:
        logger.warning("No backup file found for verification")
        return {"skipped": True, "reason": "no_backup_found"}

    temp_db_name = f"test_restore_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    result: dict[str, Any] = {
        "valid": False,
        "backup_file": backup_path.name,
        "tables_count": 0,
        "rows_count": 0,
        "errors": [],
    }

    try:
        _create_temporary_database(temp_db_name)
        _restore_backup_to_database(backup_path, temp_db_name)

        tables_count = _run_psql_command(
            temp_db_name,
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';",
        )
        rows_count = _run_psql_command(
            temp_db_name,
            "SELECT SUM(reltuples) FROM pg_class WHERE relkind = 'r';",
        )

        result.update(
            {
                "valid": True,
                "tables_count": int(float(tables_count or 0)),
                "rows_count": int(float(rows_count or 0)),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        with suppress(Exception):
            await dispatch_webhook_event("backup.verified", result)

        logger.info(
            "Backup verification succeeded",
            extra={
                "backup_file": backup_path.name,
                "tables_count": result["tables_count"],
                "rows_count": result["rows_count"],
            },
        )

        return result
    except Exception as exc:
        logger.exception("Backup verification failed", exc_info=True)
        result["errors"].append(str(exc))
        with suppress(Exception):
            await dispatch_webhook_event(
                "backup.verification_failed",
                {
                    "backup_file": backup_path.name,
                    "error": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        raise
    finally:
        _drop_database(temp_db_name)


def cleanup_old_backups_job(retention_config: dict[str, int] | None = None) -> dict[str, Any]:
    """Remove backup files beyond retention limits."""

    retention = retention_config or {
        "daily": settings.backup_retention_daily,
        "weekly": settings.backup_retention_weekly,
        "monthly": settings.backup_retention_monthly,
    }

    backup_dir = _ensure_backup_dir()
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

    result = {
        "deleted_count": len(deleted_files),
        "deleted_files": deleted_files,
        "retained": retained_counts,
    }

    if deleted_files:
        logger.info(
            "Backup retention cleanup removed files",
            extra=result,
        )

    return result


# Helper utilities ---------------------------------------------------------


def _ensure_backup_dir() -> Path:
    DEFAULT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_BACKUP_DIR


def _build_backup_stem(backup_type: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"backup_{backup_type}_{timestamp}"


def _run_pg_dump(output_path: Path) -> None:
    db_url = make_url(settings.database_url_psycopg3)
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

    logger.debug("Running pg_dump command", extra={"cmd": " ".join(cmd), "output_path": str(output_path)})

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
        settings.backup_encryption_key,
        "--encrypt",
        str(input_path),
    ]

    logger.debug("Encrypting backup", extra={"cmd": " ".join(cmd)})
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gpg encryption failed: {result.stderr.decode(errors='ignore')}")

    input_path.unlink(missing_ok=True)
    return encrypted_path


async def _upload_backup_to_cloud(backup_path: Path) -> bool:
    try:
        if settings.backup_cloud_provider.lower() != "s3":
            logger.warning("Cloud provider %s not implemented", settings.backup_cloud_provider)
            return False

        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

        s3_client = boto3.client("s3")
        key = f"backups/{backup_path.name}"
        s3_client.upload_file(str(backup_path), settings.backup_cloud_bucket, key)
        logger.info(
            "Uploaded backup to S3",
            extra={"bucket": settings.backup_cloud_bucket, "key": key},
        )
        return True
    except (NoCredentialsError, BotoCoreError, ClientError) as exc:
        logger.error("Failed to upload backup to S3: %s", exc)
        return False


def _derive_backup_type(filename: str) -> str:
    parts = filename.split("_")
    if len(parts) >= 3:
        return parts[1]
    return "unknown"


def _resolve_backup_path(backup_filename: str | None, preferred_type: str) -> Path | None:
    backup_dir = _ensure_backup_dir()
    if backup_filename:
        path = backup_dir / backup_filename
        return path if path.exists() else None

    candidates = sorted(
        [p for p in backup_dir.glob(f"backup_{preferred_type}_*.sql*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]

    # Fallback: any backup
    all_backups = sorted(
        [p for p in backup_dir.glob("backup_*_*.sql*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return all_backups[0] if all_backups else None


def _run_psql_command(database: str, sql: str) -> str:
    db_url = make_url(settings.database_url_psycopg3)
    env = os.environ.copy()
    if db_url.password:
        env["PGPASSWORD"] = db_url.password

    cmd = [
        "psql",
        "-h",
        db_url.host or "localhost",
        "-p",
        str(db_url.port or 5432),
        "-U",
        db_url.username or "postgres",
        "-d",
        database,
        "-t",
        "-A",
        "-c",
        sql,
    ]

    result = subprocess.run(cmd, capture_output=True, env=env, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"psql command failed: {result.stderr.decode(errors='ignore')}")

    return result.stdout.decode().strip()


def _create_temporary_database(database: str) -> None:
    _run_psql_command(
        "postgres",
        f"CREATE DATABASE {database} WITH TEMPLATE template0;",
    )


def _restore_backup_to_database(backup_path: Path, database: str) -> None:
    db_url = make_url(settings.database_url_psycopg3)
    env = os.environ.copy()
    if db_url.password:
        env["PGPASSWORD"] = db_url.password

    restore_cmd = [
        "psql",
        "-h",
        db_url.host or "localhost",
        "-p",
        str(db_url.port or 5432),
        "-U",
        db_url.username or "postgres",
        "-d",
        database,
    ]

    logger.debug("Restoring backup", extra={"cmd": " ".join(restore_cmd), "backup": str(backup_path)})

    input_stream: subprocess.Popen[bytes] | None = None
    file_handle = None
    try:
        if backup_path.suffix.endswith(".gpg"):
            decrypt_cmd = [
                "gpg",
                "--decrypt",
                "--batch",
                "--yes",
                str(backup_path),
            ]
            input_stream = subprocess.Popen(decrypt_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout = input_stream.stdout
        elif backup_path.suffix.endswith(".gz") or backup_path.name.endswith(".sql.gz"):
            gzip_process = subprocess.Popen(
                ["gzip", "-dc", str(backup_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            input_stream = gzip_process
            stdout = gzip_process.stdout
        else:
            file_handle = open(backup_path, "rb")
            stdout = file_handle

        if stdout is None:
            raise RuntimeError("Failed to open backup stream")

        with subprocess.Popen(restore_cmd, stdin=stdout, stderr=subprocess.PIPE, env=env) as restore_proc:
            stderr = restore_proc.stderr.read() if restore_proc.stderr else b""
            if restore_proc.wait() != 0:
                raise RuntimeError(f"psql restore failed: {stderr.decode(errors='ignore')}")
    finally:
        if file_handle is not None:
            file_handle.close()
        if input_stream is not None and input_stream.stdout is not None:
            input_stream.stdout.close()
        if input_stream is not None and input_stream.stderr is not None:
            input_stream.stderr.close()
        if input_stream is not None:
            return_code = input_stream.wait()
            if return_code != 0:
                raise RuntimeError(
                    f"Backup stream command failed with exit code {return_code}"
                )


def _drop_database(database: str) -> None:
    try:
        _run_psql_command(
            "postgres",
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{database}';",
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Failed to terminate connections for %s: %s", database, exc)

    try:
        _run_psql_command("postgres", f"DROP DATABASE IF EXISTS {database};")
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Failed to drop temporary database %s: %s", database, exc)
*** End of File
