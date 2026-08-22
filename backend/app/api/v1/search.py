"""
Search API endpoints.
"""

from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.core.database import get_session
from app.repositories.product import ProductRepository

router = APIRouter()


@router.get("/")
async def search_products(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Search products."""
    product_repo = ProductRepository(session)
    products, total = await product_repo.search(q, page, page_size)

    return {
        "query": q,
        "items": [p.to_dict() for p in products],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    }
