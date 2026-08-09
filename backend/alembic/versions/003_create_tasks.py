"""Create tasks table

Revision ID: 003
Revises: 002
Create Date: 2026-08-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='todo'),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tasks_user_id'), 'tasks', ['user_id'], unique=False)
    op.create_index(op.f('ix_tasks_due_at'), 'tasks', ['due_at'], unique=False)
    op.create_index(op.f('ix_tasks_user_id_status'), 'tasks', ['user_id', 'status'], unique=False)
    op.create_index(op.f('ix_tasks_user_id_due_at'), 'tasks', ['user_id', 'due_at'], unique=False)

    # Add check constraints for status and priority
    op.create_check_constraint(
        'ck_tasks_status',
        'tasks',
        "status IN ('todo', 'in_progress', 'completed')"
    )
    op.create_check_constraint(
        'ck_tasks_priority',
        'tasks',
        "priority IN ('low', 'medium', 'high', 'urgent')"
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_tasks_user_id_due_at'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_user_id_status'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_due_at'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_user_id'), table_name='tasks')
    op.drop_table('tasks')