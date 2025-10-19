"""add_performance_indexes

Revision ID: d5a50d72e841
Revises: bdb54e5d9d8e
Create Date: 2025-10-18 18:36:40.001743

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5a50d72e841"
down_revision: str | None = "bdb54e5d9d8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add performance indexes for common queries"""

    # Companies table - Query optimization indexes
    op.create_index(
        "idx_companies_lead_status_quality",
        "companies",
        ["lead_status", "lead_quality"],
        unique=False,
    )

    op.create_index("idx_companies_city_industry", "companies", ["city", "industry"], unique=False)

    op.create_index("idx_companies_created_at", "companies", ["first_scraped_at"], unique=False)

    op.create_index("idx_companies_updated_at", "companies", ["last_updated_at"], unique=False)

    op.create_index("idx_companies_lead_score", "companies", ["lead_score"], unique=False)

    op.create_index(
        "idx_companies_active_status", "companies", ["is_active", "lead_status"], unique=False
    )

    # Scraping Jobs table - Status queries
    op.create_index(
        "idx_scraping_jobs_status_created", "scraping_jobs", ["status", "created_at"], unique=False
    )

    op.create_index(
        "idx_scraping_jobs_source_status", "scraping_jobs", ["source_id", "status"], unique=False
    )

    # Users table - Authentication queries
    op.create_index("idx_users_email_active", "users", ["email", "is_active"], unique=False)

    # Company Notes - Timestamp queries
    op.create_index("idx_company_notes_created", "company_notes", ["created_at"], unique=False)


def downgrade() -> None:
    """Remove performance indexes"""

    # Drop all indexes in reverse order
    op.drop_index("idx_company_notes_created", table_name="company_notes")
    op.drop_index("idx_users_email_active", table_name="users")
    op.drop_index("idx_scraping_jobs_source_status", table_name="scraping_jobs")
    op.drop_index("idx_scraping_jobs_status_created", table_name="scraping_jobs")
    op.drop_index("idx_companies_active_status", table_name="companies")
    op.drop_index("idx_companies_lead_score", table_name="companies")
    op.drop_index("idx_companies_updated_at", table_name="companies")
    op.drop_index("idx_companies_created_at", table_name="companies")
    op.drop_index("idx_companies_city_industry", table_name="companies")
    op.drop_index("idx_companies_lead_status_quality", table_name="companies")
