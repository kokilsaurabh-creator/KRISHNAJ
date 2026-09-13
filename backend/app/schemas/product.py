from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    code: str
    name: str
    category: str | None = None
    uom: str = "PCS"
    default_rate: Decimal | None = None
    notes: str | None = None


class ProductUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    category: str | None = None
    uom: str | None = None
    default_rate: Decimal | None = None
    notes: str | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    category: str | None
    uom: str
    default_rate: Decimal | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
