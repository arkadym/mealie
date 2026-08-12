"""add ai provider request body

Revision ID: c3d5e7a91f24
Revises: 8f2c41d0b7ae
Create Date: 2026-08-12 16:10:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d5e7a91f24"
down_revision: str | None = "8f2c41d0b7ae"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade():
    # Extra request-body parameters as JSON text. Null means "send nothing extra", which is the
    # pre-existing behaviour.
    op.add_column("ai_providers", sa.Column("request_body", sa.String(), nullable=True))


def downgrade():
    op.drop_column("ai_providers", "request_body")
