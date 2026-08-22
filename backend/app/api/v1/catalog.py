"""
Catalog API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.product import ProductRepository
from app.repositories.category import CategoryRepository
from app.repositories.attribute import AttributeRepository

router = APIRouter()


@router.get("/")
async def list_products(
    category_id: int = Query(None, description="Filter by category ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_session),
):
    """List products with optional category filter."""
    product_repo = ProductRepository(session)
    category_repo = CategoryRepository(session)

    if category_id:
        # Verify category exists
        category = await category_repo.get_by_id(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        products, total = await product_repo.list_by_category(category_id, page, page_size)
    else:
        offset = (page - 1) * page_size
        from sqlalchemy import select, func
        result = await session.execute(
            select(Product).order_by(Product.created_at.desc()).offset(offset).limit(page_size)
        )
        products = result.scalars().all()
        total_result = await session.execute(select(func.count(Product.id)))
        total = total_result.scalar_one()

    return {
        "items": [p.to_dict() for p in products],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/categories")
async def list_categories(
    session: AsyncSession = Depends(get_session),
):
    """List all categories (root level)."""
    category_repo = CategoryRepository(session)
    categories = await category_repo.get_root_categories()
    return [c.to_dict() for c in categories]


@router.get("/categories/{slug}")
async def get_category(
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    """Get category by slug with children and filters."""
    category_repo = CategoryRepository(session)
    attr_repo = AttributeRepository(session)

    category = await category_repo.get_by_slug(slug)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    children = await category_repo.get_children(category.id)
    filters = await attr_repo.get_category_filters(category.id)

    return {
        "category": category.to_dict(),
        "children": [c.to_dict() for c in children],
        "filters": [
            {
                "id": f.id,
                "name": f.name,
                "slug": f.slug,
            }
            for f in filters
        ],
    }


@router.get("/products/{slug}")
async def get_product(
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    """Get product by slug."""
    product_repo = ProductRepository(session)

    product = await product_repo.get_by_slug(slug)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return product.to_dict()
