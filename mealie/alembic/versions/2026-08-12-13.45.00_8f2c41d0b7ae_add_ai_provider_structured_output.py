"""add ai provider structured output mode and max tokens

Revision ID: 8f2c41d0b7ae
Revises: 2187537c52b8
Create Date: 2026-08-12 13:45:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8f2c41d0b7ae"
down_revision: str | None = "2187537c52b8"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade():
    # Existing providers keep today's behaviour: strict json_schema, and no token cap sent.
    op.add_column(
        "ai_providers",
        sa.Column("structured_output_mode", sa.String(), nullable=False, server_default="json_schema"),
    )
    op.add_column("ai_providers", sa.Column("max_tokens", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("ai_providers", "max_tokens")
    op.drop_column("ai_providers", "structured_output_mode")
