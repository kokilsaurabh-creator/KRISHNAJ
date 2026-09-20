"""payments: knockoff_amount / knockoff_reason, and the 'settlement_discount'
ledger txn type for the second ledger line.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD VALUE can't be used in the transaction that adds it, so it gets
    # its own committed block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE ledger_txn_type ADD VALUE IF NOT EXISTS 'settlement_discount'")

    op.add_column("payments", sa.Column("knockoff_amount", sa.Numeric(14, 2)))
    op.add_column("payments", sa.Column("knockoff_reason", sa.Text()))
    op.create_check_constraint(
        "ck_payments_knockoff_positive", "payments", "knockoff_amount IS NULL OR knockoff_amount > 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_payments_knockoff_positive", "payments", type_="check")
    op.drop_column("payments", "knockoff_reason")
    op.drop_column("payments", "knockoff_amount")
    # Postgres can't drop an enum value; 'settlement_discount' stays in
    # ledger_txn_type, unused.
