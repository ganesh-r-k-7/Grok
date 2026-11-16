"""Add provider_account_id to oauth_tokens

Revision ID: 005
Revises: 004
Create Date: 2026-08-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'oauth_tokens',
        sa.Column('provider_account_id', sa.String(length=255), nullable=True)
    )
    op.create_index(
        op.f('ix_oauth_tokens_provider_account_id'),
        'oauth_tokens',
        ['provider_account_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_oauth_tokens_provider_account_id'), table_name='oauth_tokens')
    op.drop_column('oauth_tokens', 'provider_account_id')