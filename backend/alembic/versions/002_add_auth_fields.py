"""Add authentication fields to users table

Revision ID: 002
Revises: 001
Create Date: 2026-08-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add password_hash column
    op.add_column(
        'users',
        sa.Column('password_hash', sa.String(length=255), nullable=False, server_default='')
    )
    # Remove server_default after adding column
    op.alter_column('users', 'password_hash', server_default=None)

    # Add is_active column
    op.add_column(
        'users',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true')
    )
    op.alter_column('users', 'is_active', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'password_hash')