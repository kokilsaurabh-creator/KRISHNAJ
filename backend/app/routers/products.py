from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db import get_session
from app.models import Product, UserRole
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ProductOut])
async def list_products(
    q: str | None = None,
    active: bool | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[Product]:
    stmt = select(Product).order_by(Product.name)
    if active is not None:
        stmt = stmt.where(Product.is_active == active)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def create_product(body: ProductCreate, session: AsyncSession = Depends(get_session)) -> Product:
    product = Product(**body.model_dump())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, session: AsyncSession = Depends(get_session)) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


@router.patch(
    "/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def update_product(
    product_id: int, body: ProductUpdate, session: AsyncSession = Depends(get_session)
) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await session.commit()
    await session.refresh(product)
    return product
