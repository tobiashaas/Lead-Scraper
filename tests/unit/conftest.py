"""Unit test configuration overriding global fixtures to avoid DB access."""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import database as database_module


@pytest.fixture(autouse=True, scope="session")
def unit_test_session_override(tmp_path_factory):
    """Force SessionLocal to use an isolated in-memory SQLite database for unit tests."""

    # Create dedicated SQLite database file per test session
    db_dir = tmp_path_factory.mktemp("unit_db")
    db_url = f"sqlite:///{db_dir}/unit_tests.sqlite"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    original_engine = database_module.engine
    original_sessionlocal = database_module.SessionLocal
    database_module.engine = engine
    database_module.SessionLocal = testing_session_local

    # Ensure SQLAlchemy sees the override in env that other helpers may read
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url

    yield

    # Restore originals after tests run
    if original_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_url

    database_module.engine = original_engine
    database_module.SessionLocal = original_sessionlocal
