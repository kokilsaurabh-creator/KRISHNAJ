"""bank tracking: banks, bank_ledger_entries, payments.bank_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Already created by 0001; referenced here, not recreated.
ledger_txn_type = postgresql.ENUM(
    "opening", "sale", "purchase", "receipt", "payment", name="ledger_txn_type", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "banks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("account_number", sa.Text()),
        sa.Column("branch", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "bank_ledger_entries",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("bank_id", sa.BigInteger(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("txn_type", ledger_txn_type, nullable=False),
        sa.Column("source_table", sa.Text()),
        sa.Column("source_id", sa.BigInteger()),
        sa.Column("doc_no", sa.Text()),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("narration", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_bank_ledger_entries_nonnegative"),
        sa.CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_bank_ledger_entries_one_sided"),
    )
    op.create_index("idx_bank_ledger_bank_date", "bank_ledger_entries", ["bank_id", "txn_date", "id"])
    op.create_index(
        "idx_bank_ledger_source",
        "bank_ledger_entries",
        ["source_table", "source_id"],
        unique=True,
        postgresql_where=sa.text("source_table IS NOT NULL"),
    )

    op.add_column("payments", sa.Column("bank_id", sa.BigInteger(), sa.ForeignKey("banks.id")))
    # Deliberately not "exactly one of transfer/bank must be set": rows
    # from before this feature have neither, and that's correct — they
    # predate bank tracking, not a data-entry gap to paper over. Only the
    # combination that's never valid (both at once) is enforced here; "one
    # of them is required going forward" lives in the API layer instead.
    op.create_check_constraint(
        "ck_payments_bank_or_transfer_not_both",
        "payments",
        "NOT (transfer_to_party_id IS NOT NULL AND bank_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_payments_bank_or_transfer_not_both", "payments", type_="check")
    op.drop_column("payments", "bank_id")
    op.drop_index("idx_bank_ledger_source", table_name="bank_ledger_entries")
    op.drop_index("idx_bank_ledger_bank_date", table_name="bank_ledger_entries")
    op.drop_table("bank_ledger_entries")
    op.drop_table("banks")
