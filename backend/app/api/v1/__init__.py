"""
API v1 endpoints.
"""

from fastapi import APIRouter

from app.api.v1 import catalog, cart, auth, orders, search

router = APIRouter()

router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
router.include_router(cart.router, prefix="/cart", tags=["cart"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(orders.router, prefix="/orders", tags=["orders"])
router.include_router(search.router, prefix="/search", tags=["search"])

__all__ = ["router"]
