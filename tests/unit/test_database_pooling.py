"""Unit tests for database pooling helpers."""
from __future__ import annotations

import time

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import TimeoutError

from app.database import database as database_module


class _DummyConnection:
    def __enter__(self):  # pragma: no cover - simple context helper
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - simple context helper
        return False

    def execute(self, statement):  # pragma: no cover - store executed statement
        self.statement = statement


class _DummyPool:
    def __init__(self, size=20, checked_in=15, checked_out=5, overflow=2):
        self._size = size
        self._checked_in = checked_in
        self._checked_out = checked_out
        self._overflow = overflow

    def size(self):
        return self._size

    def checkedin(self):
        return self._checked_in

    def checkedout(self):
        return self._checked_out

    def overflow(self):
        return self._overflow


class _DummyEngine:
    def __init__(self, pool: _DummyPool | None = None):
        self.pool = pool
        self.disposed = False

    def connect(self):
        return _DummyConnection()

    def dispose(self):
        self.disposed = True


def test_create_engine_uses_settings(monkeypatch):
    """Ensure engine creation passes tuned pooling parameters."""

    captured: dict[str, object] = {}
    dummy_engine = _DummyEngine(pool=_DummyPool())

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return dummy_engine

    monkeypatch.setattr(database_module, "create_engine", fake_create_engine)
    monkeypatch.setattr(database_module, "text", lambda sql: sql)

    monkeypatch.setattr(database_module.settings, "database_url_psycopg3", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setattr(database_module.settings, "db_pool_size", 42)
    monkeypatch.setattr(database_module.settings, "db_max_overflow", 17)
    monkeypatch.setattr(database_module.settings, "db_pool_timeout", 55)
    monkeypatch.setattr(database_module.settings, "db_pool_recycle", 1200)
    monkeypatch.setattr(database_module.settings, "db_connect_timeout", 9)
    monkeypatch.setattr(database_module.settings, "db_pool_pre_ping", False)
    monkeypatch.setattr(database_module.settings, "db_echo", False)

    engine = database_module._create_database_engine()

    assert engine is dummy_engine
    assert captured["url"] == "postgresql://user:pass@localhost:5432/db"
    assert captured["kwargs"] == {
        "echo": False,
        "pool_pre_ping": False,
        "pool_size": 42,
        "max_overflow": 17,
        "pool_timeout": 55,
        "pool_recycle": 1200,
        "connect_args": {"connect_timeout": 9},
    }


def test_get_pool_status_reports_metrics(monkeypatch):
    """Pool statistics should include configured timeout and pool counts."""

    dummy_pool = _DummyPool(size=10, checked_in=6, checked_out=4, overflow=1)
    monkeypatch.setattr(database_module, "engine", _DummyEngine(pool=dummy_pool))
    monkeypatch.setattr(database_module.settings, "db_pool_timeout", 33)

    result = database_module.get_pool_status()

    assert result == {
        "size": 10,
        "checked_in": 6,
        "checked_out": 4,
        "overflow": 1,
        "timeout": 33,
    }


def test_get_pool_status_handles_missing_pool(monkeypatch):
    """Engines without pools should return zeroed metrics."""

    monkeypatch.setattr(database_module, "engine", _DummyEngine(pool=None))

    status = database_module.get_pool_status()

    assert status == {
        "size": 0,
        "checked_in": 0,
        "checked_out": 0,
        "overflow": 0,
    }


def test_reset_connection_pool_recreates_engine(monkeypatch):
    """Reset should dispose old engine and bind SessionLocal to the new one."""

    disposed = {"value": False}

    class _OldEngine:
        def dispose(self):
            disposed["value"] = True

    new_engine = _DummyEngine()

    class _DummySessionmaker:
        def __init__(self):
            self.bound = None

        def configure(self, *, bind):
            self.bound = bind

    dummy_sessionmaker = _DummySessionmaker()

    monkeypatch.setattr(database_module, "engine", _OldEngine())
    monkeypatch.setattr(database_module, "SessionLocal", dummy_sessionmaker)
    monkeypatch.setattr(database_module, "_create_database_engine", lambda: new_engine)

    database_module.reset_connection_pool()

    assert disposed["value"] is True
    assert database_module.engine is new_engine
    assert dummy_sessionmaker.bound is new_engine


@pytest.mark.unit
def test_pool_timeout_exceeded():
    """Second checkout should time out when pool capacity is exhausted."""

    pool_timeout_seconds = 0.1
    engine = create_engine(
        "sqlite://",
        pool_size=1,
        max_overflow=0,
        pool_timeout=pool_timeout_seconds,
        connect_args={"check_same_thread": False},
    )

    try:
        with engine.connect():
            start = time.perf_counter()
            with pytest.raises(TimeoutError):
                engine.connect()
            elapsed = time.perf_counter() - start
        assert elapsed >= pool_timeout_seconds
    finally:
        engine.dispose()


@pytest.mark.unit
def test_pool_recycle_connections():
    """Connections older than recycle threshold should be refreshed on checkout."""

    engine = create_engine(
        "sqlite://",
        pool_size=1,
        max_overflow=0,
        pool_recycle=1,
        connect_args={"check_same_thread": False},
    )

    connection_ids: list[int] = []

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, connection_record):
        connection_ids.append(id(dbapi_connection))

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        time.sleep(1.2)

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        assert len(connection_ids) >= 2
        assert connection_ids[0] != connection_ids[-1]
    finally:
        try:
            event.remove(engine, "connect", _on_connect)
        finally:
            engine.dispose()


@pytest.mark.unit
def test_pool_pre_ping_replaces_stale_connections():
    """Stale connections should be replaced transparently when pre_ping is enabled."""

    engine = create_engine(
        "sqlite://",
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
    )

    connection_ids: list[int] = []

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, connection_record):
        connection_ids.append(id(dbapi_connection))

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        fairy = engine.raw_connection()
        stale_dbapi = fairy.dbapi_connection
        stale_connection_id = id(stale_dbapi)
        stale_dbapi.close()
        fairy.close()

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        assert len(connection_ids) >= 2
        assert connection_ids[-1] != stale_connection_id
    finally:
        try:
            event.remove(engine, "connect", _on_connect)
        finally:
            engine.dispose()
