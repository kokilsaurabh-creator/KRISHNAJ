from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

ActivityType = Literal["sale", "purchase", "payment"]


class ActivityItem(BaseModel):
    type: ActivityType
    id: int
    doc_no: str
    party_id: int
    party_name: str
    amount: Decimal
    txn_date: date
    status: Literal["active", "cancelled"]
    created_at: datetime


class DashboardSummary(BaseModel):
    as_on_date: date
    receivable_total: Decimal
    payable_total: Decimal
    month_sales_total: Decimal
    recent_activity: list[ActivityItem]
