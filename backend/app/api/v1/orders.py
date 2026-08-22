"""
Orders API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_session
from app.repositories.order import OrderRepository

router = APIRouter()


class CheckoutRequest(BaseModel):
    buyer_name: str
    email: str
    phone: str
    city_ref: str
    warehouse_ref: str
    warehouse_number: str
    delivery_address: str
    recipient_name: str


@router.post("/")
async def create_order(
    request: CheckoutRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new order."""
    # TODO: Implement order creation
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get order by ID."""
    order_repo = OrderRepository(session)
    order = await order_repo.get_by_id(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order.to_dict()


@router.get("/user/{user_id}")
async def get_user_orders(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_session),
):
    """Get orders for a user."""
    order_repo = OrderRepository(session)
    orders = await order_repo.get_user_orders(user_id, page, page_size)

    return {
        "items": [o.to_dict() for o in orders],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": len(orders),
        },
    }
