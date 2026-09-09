import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    owner = "owner"
    staff = "staff"


class PartyType(str, enum.Enum):
    customer = "customer"
    supplier = "supplier"
    both = "both"


class DocStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"


class PaymentDirection(str, enum.Enum):
    IN = "in"
    OUT = "out"


class LedgerTxnType(str, enum.Enum):
    opening = "opening"
    sale = "sale"
    purchase = "purchase"
    receipt = "receipt"
    payment = "payment"
