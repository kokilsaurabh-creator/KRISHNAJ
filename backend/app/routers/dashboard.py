"""Dashboard summary. Read-only: reuses ledger.get_outstanding for the
receivable/payable totals rather than re-deriving the sign-split logic —
see that function's docstring for why a 'both'-party row's balance only
ever counts toward one total.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db import get_session
from app.models import DocStatus, Party, Payment, Purchase, Sale
from app.schemas.dashboard import ActivityItem, DashboardSummary
from app.services import ledger

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])

RECENT_ACTIVITY_LIMIT = 10


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(session: AsyncSession = Depends(get_session)) -> DashboardSummary:
    today = date.today()

    outstanding = await ledger.get_outstanding(session, party_type=None, as_on_date=today)

    month_start = today.replace(day=1)
    month_sales_result = await session.execute(
        select(func.coalesce(func.sum(Sale.net_amount), 0)).where(
            Sale.status == DocStatus.active, Sale.invoice_date >= month_start
        )
    )
    month_sales_total = Decimal(month_sales_result.scalar_one()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    sale_rows = select(
        literal("sale").label("type"),
        Sale.id.label("id"),
        Sale.invoice_no.label("doc_no"),
        Sale.party_id.label("party_id"),
        Sale.net_amount.label("amount"),
        Sale.invoice_date.label("txn_date"),
        Sale.status.label("status"),
        Sale.created_at.label("created_at"),
    )
    purchase_rows = select(
        literal("purchase"),
        Purchase.id,
        Purchase.bill_no,
        Purchase.party_id,
        Purchase.net_amount,
        Purchase.bill_date,
        Purchase.status,
        Purchase.created_at,
    )
    payment_rows = select(
        literal("payment"),
        Payment.id,
        Payment.voucher_no,
        Payment.party_id,
        Payment.amount,
        Payment.payment_date,
        Payment.status,
        Payment.created_at,
    )

    combined = sale_rows.union_all(purchase_rows, payment_rows).subquery()
    activity_stmt = (
        select(combined, Party.name.label("party_name"))
        .join(Party, Party.id == combined.c.party_id)
        .order_by(combined.c.created_at.desc())
        .limit(RECENT_ACTIVITY_LIMIT)
    )
    activity_result = await session.execute(activity_stmt)

    recent_activity = [
        ActivityItem(
            type=row.type,
            id=row.id,
            doc_no=row.doc_no,
            party_id=row.party_id,
            party_name=row.party_name,
            amount=row.amount,
            txn_date=row.txn_date,
            status=row.status.value,
            created_at=row.created_at,
        )
        for row in activity_result.all()
    ]

    return DashboardSummary(
        as_on_date=today,
        receivable_total=outstanding.receivable_total,
        payable_total=outstanding.payable_total,
        month_sales_total=month_sales_total,
        recent_activity=recent_activity,
    )
