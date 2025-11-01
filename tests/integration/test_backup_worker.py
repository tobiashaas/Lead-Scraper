"""Integration-style tests for the database backup worker."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.core.config import settings
from app.workers import backup_worker


@pytest.fixture(autouse=True)
def reset_backup_settings(monkeypatch):
    """Ensure backup-related settings are restored after each test."""

    original = {
        "backup_enabled": settings.backup_enabled,
        "backup_compression_enabled": settings.backup_compression_enabled,
        "backup_encryption_enabled": settings.backup_encryption_enabled,
        "backup_cloud_sync_enabled": settings.backup_cloud_sync_enabled,
        "backup_encryption_key": settings.backup_encryption_key,
    }

    yield

    for key, value in original.items():
        setattr(settings, key, value)


def test_backup_database_job_creates_compressed_backup(monkeypatch, tmp_path):
    """Running a backup should produce a compressed artifact and report metadata."""

    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_worker, "DEFAULT_BACKUP_DIR", backup_dir)
    monkeypatch.setattr(backup_worker, "POSTGRES_CONTAINER", "test-postgres")

    # Enable backup and compression, disable other optional features
    settings.backup_enabled = True
    settings.backup_compression_enabled = True
    settings.backup_encryption_enabled = False
    settings.backup_cloud_sync_enabled = False

    # Stub pg_dump to write predictable output
    def fake_pg_dump(output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("-- dummy backup\nSELECT 1;\n", encoding="utf-8")

    monkeypatch.setattr(backup_worker, "_run_pg_dump", fake_pg_dump)
    monkeypatch.setattr(backup_worker, "_encrypt_backup", lambda path: path)
    monkeypatch.setattr(backup_worker, "_upload_backup_to_cloud", lambda path: False)

    # Avoid touching real retention logic here
    monkeypatch.setattr(
        backup_worker,
        "cleanup_old_backups_job",
        lambda retention_config=None: {"deleted_count": 0, "deleted_files": [], "retained": {}},
    )

    result = backup_worker.backup_database_job("daily")

    artifact_path = Path(result["path"])
    assert artifact_path.exists()
    assert artifact_path.suffix == ".gz"
    assert result["filename"].endswith(".sql.gz")
    assert result["encrypted"] is False
    assert result["cloud_synced"] is False


def test_cleanup_old_backups_job_respects_retention(monkeypatch, tmp_path):
    """Retention cleanup should keep newest files up to configured limits."""

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(backup_worker, "DEFAULT_BACKUP_DIR", backup_dir)

    def create_backup(name: str, age_seconds: int) -> Path:
        path = backup_dir / name
        path.write_text("dummy", encoding="utf-8")
        # Older files have smaller modification times
        ts = time.time() - age_seconds
        os.utime(path, (ts, ts))
        return path

    # Create more files than retention policy allows
    create_backup("backup_daily_20250101030000.sql.gz", 500)
    create_backup("backup_daily_20250102030000.sql.gz", 400)
    create_backup("backup_daily_20250103030000.sql.gz", 300)
    create_backup("backup_daily_20250104030000.sql.gz", 200)

    create_backup("backup_weekly_20250105040000.sql.gz", 1000)
    create_backup("backup_weekly_20250112040000.sql.gz", 900)
    create_backup("backup_weekly_20250119040000.sql.gz", 800)

    create_backup("backup_monthly_20240101050000.sql.gz", 4000)
    create_backup("backup_monthly_20240201050000.sql.gz", 3700)
    create_backup("backup_monthly_20240301050000.sql.gz", 3400)

    retention = {"daily": 2, "weekly": 2, "monthly": 2}
    result = backup_worker.cleanup_old_backups_job(retention)

    assert result["retained"] == {"daily": 2, "weekly": 2, "monthly": 2}
    # Ensure only newest files per category remain
    remaining_files = sorted(p.name for p in backup_dir.iterdir())
    assert remaining_files == [
        "backup_daily_20250103030000.sql.gz",
        "backup_daily_20250104030000.sql.gz",
        "backup_monthly_20240201050000.sql.gz",
        "backup_monthly_20240301050000.sql.gz",
        "backup_weekly_20250112040000.sql.gz",
        "backup_weekly_20250119040000.sql.gz",
    ]
