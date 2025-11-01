"""Restore PostgreSQL database backups with safety checks and verification."""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

DEFAULT_BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/backups"))

logger = logging.getLogger("restore_database")


def list_available_backups(limit: int = 20) -> list[dict[str, Any]]:
    backups = sorted(
        [p for p in DEFAULT_BACKUP_DIR.glob("backup_*_*.sql*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]

    results: list[dict[str, Any]] = []
    for backup in backups:
        results.append(
            {
                "filename": backup.name,
                "path": str(backup),
                "size_mb": round(backup.stat().st_size / (1024 * 1024), 2),
                "modified_at": datetime.fromtimestamp(
                    backup.stat().st_mtime, tz=UTC
                ).isoformat(),
                "type": _derive_backup_type(backup.name),
            }
        )
    return results


def restore_database(
    backup_file: Path,
    target_db: str | None = None,
    force: bool = False,
    stop_app: bool = True,
) -> dict[str, Any]:
    backup_path = backup_file
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    db_url = make_url(os.getenv("DATABASE_URL", ""))
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")

    target_database = target_db or (db_url.database or "postgres")

    if not force and not _confirm_restore(target_database, backup_path):
        logger.info("Restore aborted by user")
        return {"aborted": True}

    if stop_app:
        _stop_application_containers()

    _terminate_connections(target_database)
    _run_restore(backup_path, target_database)

    verification = _verify_restore(target_database)

    if stop_app:
        _start_application_containers()

    logger.info(
        "Database restore completed",
        extra={"target_db": target_database, "backup": backup_path.name, **verification},
    )

    return {
        "target_db": target_database,
        "backup": backup_path.name,
        "verification": verification,
    }


def test_restore(backup_file: Path) -> dict[str, Any]:
    temp_db = f"test_restore_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    result: dict[str, Any] = {}

    try:
        _create_database(temp_db)
        _run_restore(backup_file, temp_db)
        verification = _verify_restore(temp_db)
        result = {"test_database": temp_db, "verification": verification}
        logger.info("Test restore succeeded", extra=result)
    finally:
        _drop_database(temp_db)

    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore PostgreSQL backups from Docker container")
    parser.add_argument("--backup-file", type=Path, help="Path to backup file")
    parser.add_argument(
        "--target-db", type=str, default=None, help="Target database to restore into"
    )
    parser.add_argument(
        "--test-only", action="store_true", help="Test restore to temporary database"
    )
    parser.add_argument(
        "--force", action="store_true", help="Skip confirmation prompts (dangerous)"
    )
    parser.add_argument(
        "--no-stop-app",
        action="store_true",
        help="Do not stop application containers before restore",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    backup_path = args.backup_file
    if backup_path is None:
        backups = list_available_backups()
        if not backups:
            logger.error("No backups available")
            return 1
        _print_backup_list(backups)
        selection = input("Select backup number to restore: ")
        try:
            index = int(selection) - 1
            backup_path = Path(backups[index]["path"])
        except (ValueError, IndexError):  # pragma: no cover - CLI
            logger.error("Invalid selection")
            return 1

    try:
        if args.test_only:
            result = test_restore(backup_path)
        else:
            result = restore_database(
                backup_file=backup_path,
                target_db=args.target_db,
                force=args.force,
                stop_app=not args.no_stop_app,
            )
    except Exception as exc:  # pragma: no cover - CLI
        logger.error("Restore failed: %s", exc)
        return 1

    logger.info("Restore summary", extra=result)
    return 0


def _derive_backup_type(filename: str) -> str:
    parts = filename.split("_")
    if len(parts) >= 3:
        return parts[1]
    return "unknown"


def _print_backup_list(backups: list[dict[str, Any]]) -> None:  # pragma: no cover - CLI only
    print("Available backups:")
    for idx, backup in enumerate(backups, start=1):
        print(
            f"{idx}. {backup['filename']} | {backup['size_mb']} MB | {backup['modified_at']} | type={backup['type']}"
        )


def _confirm_restore(target_db: str, backup_path: Path) -> bool:  # pragma: no cover - CLI only
    print("⚠️ WARNING: You are about to restore the database.")
    print(f"Target database: {target_db}")
    print(f"Backup file: {backup_path}")
    confirmation = input("Type 'RESTORE' to continue: ")
    return confirmation.strip().upper() == "RESTORE"


def _stop_application_containers() -> None:
    compose_file = os.getenv("COMPOSE_FILE", "docker-compose.prod.yml")
    services = os.getenv(
        "APP_SERVICES",
        "app-blue app-green worker-1 worker-2",
    ).split()
    cmd = ["docker-compose", "-f", compose_file, "stop", *services]
    subprocess.run(cmd, check=False)


def _start_application_containers() -> None:
    compose_file = os.getenv("COMPOSE_FILE", "docker-compose.prod.yml")
    services = os.getenv(
        "APP_SERVICES",
        "app-blue app-green worker-1 worker-2",
    ).split()
    cmd = ["docker-compose", "-f", compose_file, "start", *services]
    subprocess.run(cmd, check=False)


def _terminate_connections(database: str) -> None:
    _run_psql_command(
        "postgres",
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{database}';",
    )


def _run_restore(backup_path: Path, database: str) -> None:
    db_url = make_url(os.getenv("DATABASE_URL", ""))
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

    input_stream: subprocess.Popen[bytes] | None = None
    try:
        if backup_path.suffix.endswith(".gpg"):
            decrypt_cmd = [
                "gpg",
                "--decrypt",
                "--batch",
                "--yes",
                str(backup_path),
            ]
            input_stream = subprocess.Popen(
                decrypt_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
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
            stdout = open(backup_path, "rb")

        if stdout is None:
            raise RuntimeError("Failed to open backup stream")

        with subprocess.Popen(
            restore_cmd, stdin=stdout, stderr=subprocess.PIPE, env=env
        ) as restore_proc:
            stderr = restore_proc.stderr.read() if restore_proc.stderr else b""
            if restore_proc.wait() != 0:
                raise RuntimeError(f"psql restore failed: {stderr.decode(errors='ignore')}")
    finally:
        if input_stream is not None and input_stream.stdout is not None:
            input_stream.stdout.close()
        if input_stream is not None and input_stream.stderr is not None:
            input_stream.stderr.close()
        if input_stream is not None:
            input_stream.wait()


def _verify_restore(database: str) -> dict[str, Any]:
    tables = _run_psql_command(
        database,
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';",
    )
    rows = _run_psql_command(
        database,
        "SELECT SUM(reltuples) FROM pg_class WHERE relkind = 'r';",
    )

    return {
        "tables_count": int(float(tables or 0)),
        "rows_estimate": int(float(rows or 0)),
    }


def _create_database(database: str) -> None:
    _run_psql_command("postgres", f"CREATE DATABASE {database} WITH TEMPLATE template0;")


def _drop_database(database: str) -> None:
    _terminate_connections(database)
    _run_psql_command("postgres", f"DROP DATABASE IF EXISTS {database};")


def _run_psql_command(database: str, sql: str) -> str:
    db_url = make_url(os.getenv("DATABASE_URL", ""))
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


if __name__ == "__main__":
    raise SystemExit(main())
