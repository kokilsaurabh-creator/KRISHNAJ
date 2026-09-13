from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db import get_session
from app.models import Party, PartyType, UserRole
from app.schemas.party import OpeningBalanceRequest, OpeningBalanceResponse, PartyCreate, PartyOut, PartyUpdate
from app.services import ledger

router = APIRouter(prefix="/parties", tags=["parties"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[PartyOut])
async def list_parties(
    type: PartyType | None = None,
    q: str | None = None,
    active: bool | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[Party]:
    stmt = select(Party).order_by(Party.name)
    if type is not None:
        stmt = stmt.where(Party.party_type == type)
    if active is not None:
        stmt = stmt.where(Party.is_active == active)
    if q:
        stmt = stmt.where(Party.name.ilike(f"%{q}%"))
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "",
    response_model=PartyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def create_party(body: PartyCreate, session: AsyncSession = Depends(get_session)) -> Party:
    party = Party(**body.model_dump())
    session.add(party)
    await session.commit()
    await session.refresh(party)
    return party


@router.get("/{party_id}", response_model=PartyOut)
async def get_party(party_id: int, session: AsyncSession = Depends(get_session)) -> Party:
    party = await session.get(Party, party_id)
    if party is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Party not found")
    return party


@router.patch(
    "/{party_id}",
    response_model=PartyOut,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def update_party(party_id: int, body: PartyUpdate, session: AsyncSession = Depends(get_session)) -> Party:
    party = await session.get(Party, party_id)
    if party is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Party not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(party, field, value)
    await session.commit()
    await session.refresh(party)
    return party


@router.post(
    "/{party_id}/opening-balance",
    response_model=OpeningBalanceResponse,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def set_opening_balance(
    party_id: int, body: OpeningBalanceRequest, session: AsyncSession = Depends(get_session)
) -> OpeningBalanceResponse:
    party = await session.get(Party, party_id)
    if party is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Party not found")

    entry = await ledger.set_opening_balance(
        session,
        party_id=party_id,
        as_of_date=body.as_of_date,
        amount=body.amount,
        narration=body.narration,
    )
    await session.commit()

    balance = (entry.debit - entry.credit) if entry is not None else Decimal("0.00")
    return OpeningBalanceResponse(party_id=party_id, as_of_date=body.as_of_date, balance=balance)
