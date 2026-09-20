"""Cash ledger endpoints: the report (thin, like routers/bank_ledger.py —
all arithmetic lives in services/cash_ledger.py) and the admin-only
opening balance for the one cash account.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db import get_session
from app.models import User, UserRole
from app.schemas.cash_ledger import (
    CashLedgerOut,
    CashLedgerRowOut,
    CashOpeningBalanceOut,
    CashOpeningBalanceRequest,
)
from app.services import cash_ledger

router = APIRouter(prefix="/cash-ledger", tags=["cash-ledger"], dependencies=[Depends(get_current_user)])


@router.get("/opening-balance", response_model=CashOpeningBalanceOut)
async def get_opening_balance(session: AsyncSession = Depends(get_session)) -> CashOpeningBalanceOut:
    account = await cash_ledger.get_cash_account(session)
    if account is None:
        return CashOpeningBalanceOut(amount=None, as_of_date=None)
    return CashOpeningBalanceOut(amount=account.opening_balance, as_of_date=account.opening_balance_date)


@router.put(
    "/opening-balance",
    response_model=CashOpeningBalanceOut,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def set_opening_balance(
    body: CashOpeningBalanceRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CashOpeningBalanceOut:
    account = await cash_ledger.set_opening_balance(
        session, as_of_date=body.as_of_date, amount=body.amount, user_id=current_user.id
    )
    await session.commit()
    return CashOpeningBalanceOut(amount=account.opening_balance, as_of_date=account.opening_balance_date)


@router.get("", response_model=CashLedgerOut)
async def get_cash_ledger_report(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    session: AsyncSession = Depends(get_session),
) -> CashLedgerOut:
    try:
        report = await cash_ledger.get_cash_ledger(session, from_date, to_date)
    except cash_ledger.InvalidDateRangeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    return CashLedgerOut(
        from_date=report.from_date,
        to_date=report.to_date,
        opening=report.opening,
        rows=[
            CashLedgerRowOut(
                date=row.txn_date,
                type=row.txn_type,
                doc_no=row.doc_no,
                narration=row.narration,
                debit=row.debit,
                credit=row.credit,
                balance=row.balance,
                party_name=row.party_name,
            )
            for row in report.rows
        ],
        total_debit=report.total_debit,
        total_credit=report.total_credit,
        closing=report.closing,
    )
