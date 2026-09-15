"""payments: transfer_to_party_id / transfer_amount, for the
"transfer part of this to a vendor" option on a customer payment.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("transfer_to_party_id", sa.BigInteger(), sa.ForeignKey("parties.id")))
    op.add_column("payments", sa.Column("transfer_amount", sa.Numeric(14, 2)))
    op.create_check_constraint(
        "ck_payments_transfer_pair",
        "payments",
        "(transfer_to_party_id IS NULL) = (transfer_amount IS NULL)",
    )
    op.create_check_constraint(
        "ck_payments_transfer_amount_bounds",
        "payments",
        "transfer_amount IS NULL OR (transfer_amount > 0 AND transfer_amount <= amount)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_payments_transfer_amount_bounds", "payments", type_="check")
    op.drop_constraint("ck_payments_transfer_pair", "payments", type_="check")
    op.drop_column("payments", "transfer_amount")
    op.drop_column("payments", "transfer_to_party_id")
