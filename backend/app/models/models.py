"""ORM models mirroring the DDL in krishna-jewellers-erp-spec.md section 2, 1:1.

Column order, names, types, defaults and constraints follow the spec exactly.
Do not add or rename columns here without updating the spec and the Alembic
migration to match.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import DocStatus, LedgerTxnType, PartyType, PaymentDirection, UserRole


def _pg_enum(enum_cls: type, name: str) -> SAEnum:
    """A native Postgres ENUM whose stored values are the Python enum's
    `.value`s (lowercase strings from the spec), not member names."""
    return SAEnum(enum_cls, name=name, values_callable=lambda cls: [e.value for e in cls])


# ============ USERS ============


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(_pg_enum(UserRole, "user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ============ MASTERS ============


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    party_type: Mapped[PartyType] = mapped_column(_pg_enum(PartyType, "party_type"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    address_line: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    pincode: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_parties_name", text("lower(name)")),
        Index("idx_parties_type", "party_type", postgresql_where=text("is_active")),
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    uom: Mapped[str] = mapped_column(Text, nullable=False, server_default="PCS")
    default_rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("idx_products_name", text("lower(name)")),)


class Bank(Base):
    __tablename__ = "banks"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    account_number: Mapped[str | None] = mapped_column(Text)
    branch: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ============ ATTACHMENTS ============
# Polymorphic: entity_type IN ('product', 'payment')


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_attach_entity", "entity_type", "entity_id"),)


# ============ SALES ============


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    invoice_no: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("parties.id"), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    narration: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DocStatus] = mapped_column(_pg_enum(DocStatus, "doc_status"), nullable=False, server_default=DocStatus.active.value)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["SaleLine"]] = relationship(
        back_populates="sale", order_by="SaleLine.line_no", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_sales_party_date", "party_id", "invoice_date"),)


class SaleLine(Base):
    __tablename__ = "sale_lines"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    sale_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    sale: Mapped["Sale"] = relationship(back_populates="lines")

    __table_args__ = (
        UniqueConstraint("sale_id", "line_no"),
        CheckConstraint("quantity > 0", name="ck_sale_lines_quantity_positive"),
        CheckConstraint("rate >= 0", name="ck_sale_lines_rate_nonnegative"),
    )


# ============ PURCHASES ============
# No product master: free-text item description


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    bill_no: Mapped[str] = mapped_column(Text, nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("parties.id"), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    narration: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DocStatus] = mapped_column(_pg_enum(DocStatus, "doc_status"), nullable=False, server_default=DocStatus.active.value)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["PurchaseLine"]] = relationship(
        back_populates="purchase", order_by="PurchaseLine.line_no", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("party_id", "bill_no"),
        Index("idx_purch_party_date", "party_id", "bill_date"),
    )


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    purchase_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    item_description: Mapped[str] = mapped_column(Text, nullable=False)
    uom: Mapped[str] = mapped_column(Text, nullable=False, server_default="PCS")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    purchase: Mapped["Purchase"] = relationship(back_populates="lines")

    __table_args__ = (
        UniqueConstraint("purchase_id", "line_no"),
        CheckConstraint("quantity > 0", name="ck_purchase_lines_quantity_positive"),
        CheckConstraint("rate >= 0", name="ck_purchase_lines_rate_nonnegative"),
    )


# ============ PAYMENTS ============


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    voucher_no: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("parties.id"), nullable=False)
    direction: Mapped[PaymentDirection] = mapped_column(_pg_enum(PaymentDirection, "payment_direction"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    reference_no: Mapped[str | None] = mapped_column(Text)
    narration: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DocStatus] = mapped_column(_pg_enum(DocStatus, "doc_status"), nullable=False, server_default=DocStatus.active.value)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # "Transfer part of this to a vendor": an IN payment from a customer
    # where part of the cash received is passed straight on to a supplier
    # without going through the bank. Both null together — a plain
    # payment never touches these. See ledger.py / routers/payments.py
    # for how this becomes a second ledger leg (source_table
    # 'payment_transfer') on the same payment row.
    transfer_to_party_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("parties.id"))
    transfer_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    # Which bank account the money actually moved through. Required by the
    # API whenever the transfer above isn't in play (that's a cash hand-off,
    # never touches a bank); left null for a transfer payment, since that
    # flow is explicitly untagged — see the payments router.
    #
    # Not a strict "exactly one of transfer/bank" CHECK constraint: rows
    # from before this feature existed have neither, and forcing a bank
    # onto historical cash entries would be inventing data, not recording
    # it. The one thing enforced at the DB level is the case that's never
    # legitimate — both set on the same payment.
    bank_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("banks.id"))

    # Residual knockoff: part of what the party owes is written off as a
    # settlement discount instead of being paid. Posts a second party-ledger
    # line (source_table 'payment_knockoff') in the same direction as the
    # payment itself; no real money moves, so it never touches the bank
    # ledger. Null when unused (never 0).
    knockoff_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    knockoff_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "knockoff_amount IS NULL OR knockoff_amount > 0",
            name="ck_payments_knockoff_positive",
        ),
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint(
            "(transfer_to_party_id IS NULL) = (transfer_amount IS NULL)",
            name="ck_payments_transfer_pair",
        ),
        CheckConstraint(
            "transfer_amount IS NULL OR (transfer_amount > 0 AND transfer_amount <= amount)",
            name="ck_payments_transfer_amount_bounds",
        ),
        CheckConstraint(
            "NOT (transfer_to_party_id IS NOT NULL AND bank_id IS NOT NULL)",
            name="ck_payments_bank_or_transfer_not_both",
        ),
        Index("idx_pay_party_date", "party_id", "payment_date"),
    )


# ============ LEDGER (the core) ============


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("parties.id"), nullable=False)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    txn_type: Mapped[LedgerTxnType] = mapped_column(_pg_enum(LedgerTxnType, "ledger_txn_type"), nullable=False)
    source_table: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[int | None] = mapped_column(BigInteger)
    doc_no: Mapped[str | None] = mapped_column(Text)
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    narration: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_ledger_entries_nonnegative"),
        CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_ledger_entries_one_sided"),
        Index("idx_ledger_party_date", "party_id", "txn_date", "id"),
        Index(
            "idx_ledger_source",
            "source_table",
            "source_id",
            unique=True,
            postgresql_where=text("source_table IS NOT NULL"),
        ),
    )


class BankLedgerEntry(Base):
    """Same shape and discipline as LedgerEntry, one table over: a bank's
    balance is SUM(debit) - SUM(credit), computed on read, never stored.
    Sign convention (deposit = debit, withdrawal = credit) is the reverse
    of how it reads in a passbook on purpose — it matches LedgerEntry's
    own debit-increases-balance convention, so both ledgers behave the
    same way to any code that touches them."""

    __tablename__ = "bank_ledger_entries"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    bank_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("banks.id"), nullable=False)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    txn_type: Mapped[LedgerTxnType] = mapped_column(_pg_enum(LedgerTxnType, "ledger_txn_type"), nullable=False)
    source_table: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[int | None] = mapped_column(BigInteger)
    doc_no: Mapped[str | None] = mapped_column(Text)
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    narration: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_bank_ledger_entries_nonnegative"),
        CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_bank_ledger_entries_one_sided"),
        Index("idx_bank_ledger_bank_date", "bank_id", "txn_date", "id"),
        Index(
            "idx_bank_ledger_source",
            "source_table",
            "source_id",
            unique=True,
            postgresql_where=text("source_table IS NOT NULL"),
        ),
    )


# ============ DOCUMENT NUMBERING ============


class DocSequence(Base):
    __tablename__ = "doc_sequences"

    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    fy: Mapped[str] = mapped_column(Text, nullable=False)
    prefix: Mapped[str] = mapped_column(Text, nullable=False)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (PrimaryKeyConstraint("doc_type", "fy"),)
