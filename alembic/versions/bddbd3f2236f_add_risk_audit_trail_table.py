"""Add risk audit trail table

Revision ID: bddbd3f2236f
Revises: a1b2c3d4e5f6
Create Date: 2026-08-23 22:34:36.727470

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bddbd3f2236f'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'risk_audit_trail',
        sa.Column('transaction_id', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('model_version', sa.String(length=20), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('decision', sa.String(length=20), nullable=False),
        sa.Column('requires_review', sa.Boolean(), nullable=False),
        sa.Column('signals', sa.JSON(), nullable=False),
        sa.Column('policy_version', sa.String(length=20), nullable=False),
        sa.Column('explanation', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('transaction_id')
    )
    op.create_index(op.f('ix_risk_audit_trail_decision'), 'risk_audit_trail', ['decision'], unique=False)
    op.create_index(op.f('ix_risk_audit_trail_risk_level'), 'risk_audit_trail', ['risk_level'], unique=False)
    op.create_index(op.f('ix_risk_audit_trail_risk_score'), 'risk_audit_trail', ['risk_score'], unique=False)
    op.create_index(op.f('ix_risk_audit_trail_timestamp'), 'risk_audit_trail', ['timestamp'], unique=False)
    op.create_index(op.f('ix_risk_audit_trail_transaction_id'), 'risk_audit_trail', ['transaction_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_risk_audit_trail_transaction_id'), table_name='risk_audit_trail')
    op.drop_index(op.f('ix_risk_audit_trail_timestamp'), table_name='risk_audit_trail')
    op.drop_index(op.f('ix_risk_audit_trail_risk_score'), table_name='risk_audit_trail')
    op.drop_index(op.f('ix_risk_audit_trail_risk_level'), table_name='risk_audit_trail')
    op.drop_index(op.f('ix_risk_audit_trail_decision'), table_name='risk_audit_trail')
    op.drop_table('risk_audit_trail')
