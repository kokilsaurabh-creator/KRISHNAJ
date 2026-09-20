"""cash ledger: cash_account (singleton) and cash_ledger_entries

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Already created earlier; referenced here, not recreated. Cash reuses
# opening / receipt / payment, so no new enum value is needed.
ledger_txn_type = postgresql.ENUM(
    "opening", "sale", "purchase", "receipt", "payment", "settlement_discount",
    name="ledger_txn_type", create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "cash_account",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("opening_balance_date", sa.Date()),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_cash_account_singleton"),
    )

    op.create_table(
        "cash_ledger_entries",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("txn_type", ledger_txn_type, nullable=False),
        sa.Column("source_table", sa.Text()),
        sa.Column("source_id", sa.BigInteger()),
        sa.Column("doc_no", sa.Text()),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("narration", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_cash_ledger_entries_nonnegative"),
        sa.CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_cash_ledger_entries_one_sided"),
    )
    op.create_index("idx_cash_ledger_date", "cash_ledger_entries", ["txn_date", "id"])
    op.create_index(
        "idx_cash_ledger_source",
        "cash_ledger_entries",
        ["source_table", "source_id"],
        unique=True,
        postgresql_where=sa.text("source_table IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_cash_ledger_source", table_name="cash_ledger_entries")
    op.drop_index("idx_cash_ledger_date", table_name="cash_ledger_entries")
    op.drop_table("cash_ledger_entries")
    op.drop_table("cash_account")
