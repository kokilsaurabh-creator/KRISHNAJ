"""Sales: create, edit, cancel. The first real caller of post_to_ledger,
repost_for_source, remove_for_source, and allocate_doc_number — everything
below happens in ONE transaction per request: line pricing, the header
totals, the document-number allocation, the sales/sale_lines writes, and
the ledger post. A single `await session.commit()` at the end is the only
commit; if anything above it raises, get_session's context manager rolls
the whole thing back and no half-written invoice or orphaned ledger row
survives.
"""

from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, require_role
from app.db import get_session
from app.models import DocStatus, LedgerTxnType, Party, Product, Sale, SaleLine, User, UserRole
from app.schemas.sale import SaleCancelRequest, SaleLineIn, SaleOut, SaleWrite
from app.services import ledger
from app.services.doc_numbering import allocate_doc_number

router = APIRouter(prefix="/sales", tags=["sales"], dependencies=[Depends(get_current_user)])

_TWO_PLACES = Decimal("0.01")


async def _price_lines(
    session: AsyncSession, lines: list[SaleLineIn]
) -> tuple[list[dict], Decimal]:
    """Validate each line's product and compute its amount server-side —
    the client sends quantity/rate, never amount, so a tampered or stale
    amount can't sneak into gross_amount."""
    priced: list[dict] = []
    gross_amount = Decimal("0.00")
    for line_no, line in enumerate(lines, start=1):
        product = await session.get(Product, line.product_id)
        if product is None or not product.is_active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Product {line.product_id} not found or inactive"
            )
        amount = (line.quantity * line.rate).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        gross_amount += amount
        priced.append(
            {
                "line_no": line_no,
                "product_id": line.product_id,
                "description": line.description,
                "quantity": line.quantity,
                "rate": line.rate,
                "amount": amount,
            }
        )
    return priced, gross_amount


async def _load_sale(session: AsyncSession, sale_id: int) -> Sale | None:
    result = await session.execute(
        select(Sale).where(Sale.id == sale_id).options(selectinload(Sale.lines))
    )
    return result.scalar_one_or_none()


@router.post("", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
async def create_sale(
    body: SaleWrite,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Sale:
    party = await session.get(Party, body.party_id)
    if party is None or not party.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Party not found or inactive")

    line_rows, gross_amount = await _price_lines(session, body.lines)

    if body.discount < 0 or body.discount > gross_amount:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "discount must be between 0 and the gross amount")
    net_amount = gross_amount - body.discount

    invoice_no = await allocate_doc_number(session, doc_type="sale", txn_date=body.invoice_date, prefix="KJ/")

    sale = Sale(
        invoice_no=invoice_no,
        invoice_date=body.invoice_date,
        party_id=body.party_id,
        gross_amount=gross_amount,
        discount=body.discount,
        net_amount=net_amount,
        narration=body.narration,
        created_by=current_user.id,
    )
    session.add(sale)
    await session.flush()  # populate sale.id for the lines and the ledger post

    for row in line_rows:
        session.add(SaleLine(sale_id=sale.id, **row))

    await ledger.post_to_ledger(
        session,
        party_id=body.party_id,
        txn_date=body.invoice_date,
        txn_type=LedgerTxnType.sale,
        source_table="sales",
        source_id=sale.id,
        doc_no=invoice_no,
        debit=net_amount,
        credit=Decimal("0"),
        narration=body.narration,
    )

    await session.commit()
    return await _load_sale(session, sale.id)


@router.get("", response_model=list[SaleOut])
async def list_sales(
    party_id: int | None = None,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> list[Sale]:
    stmt = select(Sale).options(selectinload(Sale.lines)).order_by(Sale.invoice_date.desc(), Sale.id.desc())
    if party_id is not None:
        stmt = stmt.where(Sale.party_id == party_id)
    if from_date is not None:
        stmt = stmt.where(Sale.invoice_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(Sale.invoice_date <= to_date)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{sale_id}", response_model=SaleOut)
async def get_sale(sale_id: int, session: AsyncSession = Depends(get_session)) -> Sale:
    sale = await _load_sale(session, sale_id)
    if sale is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sale not found")
    return sale


@router.patch("/{sale_id}", response_model=SaleOut)
async def update_sale(
    sale_id: int,
    body: SaleWrite,
    session: AsyncSession = Depends(get_session),
) -> Sale:
    sale = await session.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sale not found")
    if sale.status == DocStatus.cancelled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot edit a cancelled sale")

    party = await session.get(Party, body.party_id)
    if party is None or not party.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Party not found or inactive")

    line_rows, gross_amount = await _price_lines(session, body.lines)

    if body.discount < 0 or body.discount > gross_amount:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "discount must be between 0 and the gross amount")
    net_amount = gross_amount - body.discount

    # invoice_no is never reissued on edit — it was already handed to the
    # customer on the printed/shared copy.
    sale.party_id = body.party_id
    sale.invoice_date = body.invoice_date
    sale.gross_amount = gross_amount
    sale.discount = body.discount
    sale.net_amount = net_amount
    sale.narration = body.narration

    await session.execute(delete(SaleLine).where(SaleLine.sale_id == sale.id))
    await session.flush()
    for row in line_rows:
        session.add(SaleLine(sale_id=sale.id, **row))

    await ledger.repost_for_source(
        session,
        source_table="sales",
        source_id=sale.id,
        party_id=body.party_id,
        txn_date=body.invoice_date,
        txn_type=LedgerTxnType.sale,
        doc_no=sale.invoice_no,
        debit=net_amount,
        credit=Decimal("0"),
        narration=body.narration,
    )

    await session.commit()
    return await _load_sale(session, sale.id)


@router.post(
    "/{sale_id}/cancel",
    response_model=SaleOut,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def cancel_sale(
    sale_id: int,
    body: SaleCancelRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Sale:
    sale = await session.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sale not found")
    if sale.status == DocStatus.cancelled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Sale is already cancelled")

    sale.status = DocStatus.cancelled
    sale.cancelled_by = current_user.id
    sale.cancelled_at = datetime.now(timezone.utc)
    sale.cancel_reason = body.reason

    await ledger.remove_for_source(session, source_table="sales", source_id=sale.id)

    await session.commit()
    return await _load_sale(session, sale.id)
