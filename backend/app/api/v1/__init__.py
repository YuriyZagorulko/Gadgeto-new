"""API v1 routes."""
from fastapi import APIRouter
from . import catalog_new as catalog
from . import auth, cart, orders, homepage
from app.shipping import np_router
from app.payments import liqpay_router

router = APIRouter()
router.include_router(catalog.router, prefix="", tags=["catalog"])
router.include_router(homepage.router, prefix="", tags=["homepage"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(cart.router, prefix="", tags=["cart"])
router.include_router(orders.router, prefix="", tags=["orders"])
router.include_router(np_router, prefix="", tags=["shipping"])
router.include_router(liqpay_router, prefix="", tags=["payments"])
