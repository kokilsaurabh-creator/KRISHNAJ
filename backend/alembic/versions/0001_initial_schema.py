"""initial schema — matches krishna-jewellers-erp-spec.md section 2 exactly

Revision ID: 0001
Revises:
Create Date: 2026-09-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role = postgresql.ENUM("admin", "owner", "staff", name="user_role", create_type=False)
party_type = postgresql.ENUM("customer", "supplier", "both", name="party_type", create_type=False)
doc_status = postgresql.ENUM("active", "cancelled", name="doc_status", create_type=False)
payment_direction = postgresql.ENUM("in", "out", name="payment_direction", create_type=False)
ledger_txn_type = postgresql.ENUM(
    "opening", "sale", "purchase", "receipt", "payment", name="ledger_txn_type", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    party_type.create(bind, checkfirst=True)
    doc_status.create(bind, checkfirst=True)
    payment_direction.create(bind, checkfirst=True)
    ledger_txn_type.create(bind, checkfirst=True)

    # ============ USERS ============

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("username"),
    )

    # ============ MASTERS ============

    op.create_table(
        "parties",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("party_type", party_type, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text()),
        sa.Column("email", sa.Text()),
        sa.Column("address_line", sa.Text()),
        sa.Column("city", sa.Text()),
        sa.Column("state", sa.Text()),
        sa.Column("pincode", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute("CREATE INDEX idx_parties_name ON parties (lower(name))")
    op.execute("CREATE INDEX idx_parties_type ON parties (party_type) WHERE is_active")

    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text()),
        sa.Column("uom", sa.Text(), nullable=False, server_default="PCS"),
        sa.Column("default_rate", sa.Numeric(14, 2)),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code"),
    )
    op.execute("CREATE INDEX idx_products_name ON products (lower(name))")

    # ============ ATTACHMENTS ============

    op.create_table(
        "attachments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_attach_entity", "attachments", ["entity_type", "entity_id"])

    # ============ SALES ============

    op.create_table(
        "sales",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("invoice_no", sa.Text(), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("party_id", sa.BigInteger(), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("narration", sa.Text()),
        sa.Column("status", doc_status, nullable=False, server_default="active"),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cancelled_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("invoice_no"),
    )
    op.create_index("idx_sales_party_date", "sales", ["party_id", "invoice_date"])

    op.create_table(
        "sale_lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("sale_id", sa.BigInteger(), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("quantity", sa.Numeric(14, 3), sa.CheckConstraint("quantity > 0"), nullable=False),
        sa.Column("rate", sa.Numeric(14, 2), sa.CheckConstraint("rate >= 0"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("sale_id", "line_no"),
    )

    # ============ PURCHASES ============

    op.create_table(
        "purchases",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("bill_no", sa.Text(), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("party_id", sa.BigInteger(), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("narration", sa.Text()),
        sa.Column("status", doc_status, nullable=False, server_default="active"),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cancelled_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("party_id", "bill_no"),
    )
    op.create_index("idx_purch_party_date", "purchases", ["party_id", "bill_date"])

    op.create_table(
        "purchase_lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "purchase_id", sa.BigInteger(), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("item_description", sa.Text(), nullable=False),
        sa.Column("uom", sa.Text(), nullable=False, server_default="PCS"),
        sa.Column("quantity", sa.Numeric(14, 3), sa.CheckConstraint("quantity > 0"), nullable=False),
        sa.Column("rate", sa.Numeric(14, 2), sa.CheckConstraint("rate >= 0"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("purchase_id", "line_no"),
    )

    # ============ PAYMENTS ============

    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("voucher_no", sa.Text(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("party_id", sa.BigInteger(), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("direction", payment_direction, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), sa.CheckConstraint("amount > 0"), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("reference_no", sa.Text()),
        sa.Column("narration", sa.Text()),
        sa.Column("status", doc_status, nullable=False, server_default="active"),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cancelled_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("voucher_no"),
    )
    op.create_index("idx_pay_party_date", "payments", ["party_id", "payment_date"])

    # ============ LEDGER (the core) ============

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("party_id", sa.BigInteger(), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("txn_type", ledger_txn_type, nullable=False),
        sa.Column("source_table", sa.Text()),
        sa.Column("source_id", sa.BigInteger()),
        sa.Column("doc_no", sa.Text()),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("narration", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_ledger_entries_nonnegative"),
        sa.CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_ledger_entries_one_sided"),
    )
    op.execute("CREATE INDEX idx_ledger_party_date ON ledger_entries (party_id, txn_date, id)")
    op.execute(
        "CREATE UNIQUE INDEX idx_ledger_source "
        "ON ledger_entries (source_table, source_id) "
        "WHERE source_table IS NOT NULL"
    )

    # ============ DOCUMENT NUMBERING ============

    op.create_table(
        "doc_sequences",
        sa.Column("doc_type", sa.Text(), nullable=False),
        sa.Column("fy", sa.Text(), nullable=False),
        sa.Column("prefix", sa.Text(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("doc_type", "fy"),
    )


def downgrade() -> None:
    op.drop_table("doc_sequences")
    op.drop_index("idx_ledger_source", table_name="ledger_entries")
    op.drop_index("idx_ledger_party_date", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("idx_pay_party_date", table_name="payments")
    op.drop_table("payments")
    op.drop_table("purchase_lines")
    op.drop_index("idx_purch_party_date", table_name="purchases")
    op.drop_table("purchases")
    op.drop_table("sale_lines")
    op.drop_index("idx_sales_party_date", table_name="sales")
    op.drop_table("sales")
    op.drop_index("idx_attach_entity", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("idx_products_name", table_name="products")
    op.drop_table("products")
    op.drop_index("idx_parties_type", table_name="parties")
    op.drop_index("idx_parties_name", table_name="parties")
    op.drop_table("parties")
    op.drop_table("users")

    bind = op.get_bind()
    ledger_txn_type.drop(bind, checkfirst=True)
    payment_direction.drop(bind, checkfirst=True)
    doc_status.drop(bind, checkfirst=True)
    party_type.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
