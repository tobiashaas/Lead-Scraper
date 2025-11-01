from sqlalchemy import select

from app.database.models import Company
from tests.utils.test_helpers import count_database_queries


def test_expired_token_header(expired_token):
    assert "Authorization" in expired_token
    assert expired_token["Authorization"].startswith("Bearer ")


def test_rate_limited_client_enforces_threshold(rate_limited_client):
    for _ in range(5):
        response = rate_limited_client.get("/health")
        assert response.status_code == 200

    limited_response = rate_limited_client.get("/health")
    assert limited_response.status_code == 429
    assert rate_limited_client.request_counts["GET:/health"] == 6


def test_performance_timer_records_elapsed(performance_timer):
    with performance_timer() as timer:
        pass

    assert timer.elapsed_ms >= 0.0


def test_count_database_queries_context(db_session):
    with count_database_queries(db_session) as counter:
        db_session.execute(select(Company.id)).scalars().all()

    assert counter.count > 0
    assert counter.count < 5


def test_db_transaction_rollback_fixture(db_transaction_rollback, db_session):
    def operation(session):
        session.add(Company(company_name="Rollback Co"))

    db_transaction_rollback(operation)

    remaining = db_session.execute(select(Company)).scalars().all()
    assert remaining == []
