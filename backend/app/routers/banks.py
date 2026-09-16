"""Bank master: create, edit, list. Same admin/owner-gated shape as
parties.py. Create additionally posts the opening balance in the same
transaction as the row itself, since a bank can't be edited into a
balance the way a party can (no separate opening-balance endpoint —
banks are few enough that getting it right once at creation is enough).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db import get_session
from app.models import Bank, User, UserRole
from app.schemas.bank import BankCreate, BankOut, BankUpdate
from app.services import bank_ledger

router = APIRouter(prefix="/banks", tags=["banks"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[BankOut])
async def list_banks(active: bool | None = None, session: AsyncSession = Depends(get_session)) -> list[Bank]:
    stmt = select(Bank).order_by(Bank.name)
    if active is not None:
        stmt = stmt.where(Bank.is_active == active)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "",
    response_model=BankOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def create_bank(
    body: BankCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Bank:
    bank = Bank(
        name=body.name,
        account_number=body.account_number,
        branch=body.branch,
        created_by=current_user.id,
    )
    session.add(bank)
    await session.flush()  # populate bank.id for the opening-balance post

    await bank_ledger.set_opening_balance(
        session,
        bank_id=bank.id,
        as_of_date=body.opening_balance_date,
        amount=body.opening_balance,
        narration="Opening balance",
    )

    await session.commit()
    await session.refresh(bank)
    return bank


@router.get("/{bank_id}", response_model=BankOut)
async def get_bank(bank_id: int, session: AsyncSession = Depends(get_session)) -> Bank:
    bank = await session.get(Bank, bank_id)
    if bank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bank not found")
    return bank


@router.patch(
    "/{bank_id}",
    response_model=BankOut,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def update_bank(bank_id: int, body: BankUpdate, session: AsyncSession = Depends(get_session)) -> Bank:
    bank = await session.get(Bank, bank_id)
    if bank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bank not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(bank, field, value)
    await session.commit()
    await session.refresh(bank)
    return bank
