"""Initial migration – create jobs, transactions, and job_summaries tables.

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2024-10-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- jobs table ---
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("row_count_raw", sa.Integer(), nullable=True),
        sa.Column("row_count_clean", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- transactions table ---
    op.create_table(
        "transactions",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id"),
            nullable=False,
        ),
        sa.Column("txn_id", sa.String(100), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("merchant", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("account_id", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_anomaly",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("anomaly_reason", sa.String(255), nullable=True),
        sa.Column("llm_category", sa.String(100), nullable=True),
        sa.Column("llm_raw_response", sa.Text(), nullable=True),
        sa.Column(
            "llm_failed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_job_id", "transactions", ["job_id"])

    # --- job_summaries table ---
    op.create_table(
        "job_summaries",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("total_spend_inr", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_spend_usd", sa.Numeric(15, 2), nullable=True),
        sa.Column("top_merchants", postgresql.JSON(), nullable=True),
        sa.Column(
            "anomaly_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(10), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("job_summaries")
    op.drop_index("ix_transactions_job_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("jobs")
