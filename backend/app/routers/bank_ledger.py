"""Bank ledger read endpoint. Thin by design, mirroring routers/ledger.py:
all arithmetic lives in bank_ledger.get_bank_ledger — this just resolves
the bank, passes the date range through, and reshapes the service's
dataclasses into the response.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db import get_session
from app.models import Bank
from app.schemas.bank_ledger import BankLedgerBankOut, BankLedgerOut, BankLedgerRowOut
from app.services import bank_ledger

router = APIRouter(prefix="/bank-ledger", tags=["bank-ledger"], dependencies=[Depends(get_current_user)])


@router.get("/{bank_id}", response_model=BankLedgerOut)
async def get_bank_ledger_report(
    bank_id: int,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    session: AsyncSession = Depends(get_session),
) -> BankLedgerOut:
    bank = await session.get(Bank, bank_id)
    if bank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bank not found")

    try:
        report = await bank_ledger.get_bank_ledger(session, bank_id, from_date, to_date)
    except bank_ledger.InvalidDateRangeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    return BankLedgerOut(
        bank=BankLedgerBankOut.model_validate(bank),
        from_date=report.from_date,
        to_date=report.to_date,
        opening=report.opening,
        rows=[
            BankLedgerRowOut(
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
