"""add full-text search index for companies

Revision ID: f6b0e7d42c3a
Revises: d5a50d72e841
Create Date: 2025-11-01 12:48:00.000000
"""

from collections.abc import Sequence

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision: str = "f6b0e7d42c3a"
down_revision: str | None = "d5a50d72e841"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create GIN index to accelerate full-text search on company names."""

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_companies_name_fts
        ON companies
        USING GIN (to_tsvector('german', company_name));
        """
    )


def downgrade() -> None:
    """Drop the full-text search index."""

    op.execute("DROP INDEX IF EXISTS idx_companies_name_fts;")
