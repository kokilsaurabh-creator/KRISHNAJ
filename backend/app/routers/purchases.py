"""Purchases: create, edit, cancel. Same shape as sales.py, with two real
differences dictated by the spec, not by taste:

- No product master: item_description is free text (purchase_lines has no
  product_id), so there's nothing to validate a line's product against.
- bill_no is the SUPPLIER's own number, typed in by whoever enters the
  bill — not server-generated. doc_sequences only covers 'sale', 'receipt'
  and 'payment' (see its column comment in the spec's DDL); purchases were
  deliberately left out. So there's no allocate_doc_number call here, and
  instead a pre-check against the (party_id, bill_no) unique constraint,
  to fail with a clean 400 instead of a raw IntegrityError 500 on the
  entirely plausible case of double-entering the same supplier bill.
"""

from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, require_role
from app.db import get_session
from app.models import DocStatus, LedgerTxnType, Party, Purchase, PurchaseLine, User, UserRole
from app.schemas.purchase import PurchaseCancelRequest, PurchaseLineIn, PurchaseOut, PurchaseWrite
from app.services import ledger

router = APIRouter(prefix="/purchases", tags=["purchases"], dependencies=[Depends(get_current_user)])

_TWO_PLACES = Decimal("0.01")


def _price_lines(lines: list[PurchaseLineIn]) -> tuple[list[dict], Decimal]:
    priced: list[dict] = []
    gross_amount = Decimal("0.00")
    for line_no, line in enumerate(lines, start=1):
        amount = (line.quantity * line.rate).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        gross_amount += amount
        priced.append(
            {
                "line_no": line_no,
                "item_description": line.item_description,
                "uom": line.uom,
                "quantity": line.quantity,
                "rate": line.rate,
                "amount": amount,
            }
        )
    return priced, gross_amount


async def _check_bill_no_free(
    session: AsyncSession, *, party_id: int, bill_no: str, exclude_purchase_id: int | None = None
) -> None:
    stmt = select(Purchase.id).where(Purchase.party_id == party_id, Purchase.bill_no == bill_no)
    if exclude_purchase_id is not None:
        stmt = stmt.where(Purchase.id != exclude_purchase_id)
    existing = await session.execute(stmt)
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Bill {bill_no} already recorded for this party"
        )


async def _load_purchase(session: AsyncSession, purchase_id: int) -> Purchase | None:
    result = await session.execute(
        select(Purchase).where(Purchase.id == purchase_id).options(selectinload(Purchase.lines))
    )
    return result.scalar_one_or_none()


@router.post("", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    body: PurchaseWrite,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Purchase:
    party = await session.get(Party, body.party_id)
    if party is None or not party.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Party not found or inactive")

    await _check_bill_no_free(session, party_id=body.party_id, bill_no=body.bill_no)

    line_rows, gross_amount = _price_lines(body.lines)

    if body.discount < 0 or body.discount > gross_amount:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "discount must be between 0 and the gross amount")
    net_amount = gross_amount - body.discount

    purchase = Purchase(
        bill_no=body.bill_no,
        bill_date=body.bill_date,
        party_id=body.party_id,
        gross_amount=gross_amount,
        discount=body.discount,
        net_amount=net_amount,
        narration=body.narration,
        created_by=current_user.id,
    )
    session.add(purchase)
    await session.flush()

    for row in line_rows:
        session.add(PurchaseLine(purchase_id=purchase.id, **row))

    await ledger.post_to_ledger(
        session,
        party_id=body.party_id,
        txn_date=body.bill_date,
        txn_type=LedgerTxnType.purchase,
        source_table="purchases",
        source_id=purchase.id,
        doc_no=body.bill_no,
        debit=Decimal("0"),
        credit=net_amount,
        narration=body.narration,
    )

    await session.commit()
    return await _load_purchase(session, purchase.id)


@router.get("", response_model=list[PurchaseOut])
async def list_purchases(
    party_id: int | None = None,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> list[Purchase]:
    stmt = (
        select(Purchase)
        .options(selectinload(Purchase.lines))
        .order_by(Purchase.bill_date.desc(), Purchase.id.desc())
    )
    if party_id is not None:
        stmt = stmt.where(Purchase.party_id == party_id)
    if from_date is not None:
        stmt = stmt.where(Purchase.bill_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(Purchase.bill_date <= to_date)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{purchase_id}", response_model=PurchaseOut)
async def get_purchase(purchase_id: int, session: AsyncSession = Depends(get_session)) -> Purchase:
    purchase = await _load_purchase(session, purchase_id)
    if purchase is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase not found")
    return purchase


@router.patch("/{purchase_id}", response_model=PurchaseOut)
async def update_purchase(
    purchase_id: int,
    body: PurchaseWrite,
    session: AsyncSession = Depends(get_session),
) -> Purchase:
    purchase = await session.get(Purchase, purchase_id)
    if purchase is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase not found")
    if purchase.status == DocStatus.cancelled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot edit a cancelled purchase")

    party = await session.get(Party, body.party_id)
    if party is None or not party.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Party not found or inactive")

    await _check_bill_no_free(
        session, party_id=body.party_id, bill_no=body.bill_no, exclude_purchase_id=purchase.id
    )

    line_rows, gross_amount = _price_lines(body.lines)

    if body.discount < 0 or body.discount > gross_amount:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "discount must be between 0 and the gross amount")
    net_amount = gross_amount - body.discount

    purchase.party_id = body.party_id
    purchase.bill_no = body.bill_no
    purchase.bill_date = body.bill_date
    purchase.gross_amount = gross_amount
    purchase.discount = body.discount
    purchase.net_amount = net_amount
    purchase.narration = body.narration

    await session.execute(delete(PurchaseLine).where(PurchaseLine.purchase_id == purchase.id))
    await session.flush()
    for row in line_rows:
        session.add(PurchaseLine(purchase_id=purchase.id, **row))

    await ledger.repost_for_source(
        session,
        source_table="purchases",
        source_id=purchase.id,
        party_id=body.party_id,
        txn_date=body.bill_date,
        txn_type=LedgerTxnType.purchase,
        doc_no=body.bill_no,
        debit=Decimal("0"),
        credit=net_amount,
        narration=body.narration,
    )

    await session.commit()
    return await _load_purchase(session, purchase.id)


@router.post(
    "/{purchase_id}/cancel",
    response_model=PurchaseOut,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def cancel_purchase(
    purchase_id: int,
    body: PurchaseCancelRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Purchase:
    purchase = await session.get(Purchase, purchase_id)
    if purchase is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase not found")
    if purchase.status == DocStatus.cancelled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Purchase is already cancelled")

    purchase.status = DocStatus.cancelled
    purchase.cancelled_by = current_user.id
    purchase.cancelled_at = datetime.now(timezone.utc)
    purchase.cancel_reason = body.reason

    await ledger.remove_for_source(session, source_table="purchases", source_id=purchase.id)

    await session.commit()
    return await _load_purchase(session, purchase.id)
