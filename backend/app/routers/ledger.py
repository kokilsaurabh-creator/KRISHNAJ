"""Ledger read endpoint. Thin by design: all arithmetic lives in
ledger.get_ledger — this just resolves the party, passes the date range
through, and reshapes the service's dataclasses into the response.

Cancelled documents need no filtering here. Cancelling deletes the
document's ledger row in the same transaction as the status flip, so a
cancelled sale/purchase/payment simply has nothing left in ledger_entries
to return.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db import get_session
from app.models import Party
from app.schemas.ledger import LedgerOut, LedgerPartyOut, LedgerRowOut
from app.services import ledger

router = APIRouter(prefix="/ledger", tags=["ledger"], dependencies=[Depends(get_current_user)])


@router.get("/{party_id}", response_model=LedgerOut)
async def get_party_ledger(
    party_id: int,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    session: AsyncSession = Depends(get_session),
) -> LedgerOut:
    party = await session.get(Party, party_id)
    if party is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Party not found")

    try:
        report = await ledger.get_ledger(session, party_id, from_date, to_date)
    except ledger.InvalidDateRangeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    return LedgerOut(
        party=LedgerPartyOut.model_validate(party),
        from_date=report.from_date,
        to_date=report.to_date,
        opening=report.opening,
        rows=[
            LedgerRowOut(
                date=row.txn_date,
                type=row.txn_type,
                doc_no=row.doc_no,
                narration=row.narration,
                debit=row.debit,
                credit=row.credit,
                balance=row.balance,
            )
            for row in report.rows
        ],
        total_debit=report.total_debit,
        total_credit=report.total_credit,
        closing=report.closing,
    )
