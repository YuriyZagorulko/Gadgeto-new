"""
Cart API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Cookie
from typing import Optional
from uuid import uuid4

from app.core.database import get_session
from app.repositories.cart import CartRepository

router = APIRouter()


def get_session_token(session_token: Optional[str] = Cookie(None)) -> str:
    """Get or generate session token for guest cart."""
    if not session_token:
        session_token = str(uuid4())
    return session_token


@router.get("/")
async def get_cart(
    session_token: str = Depends(get_session_token),
    session: AsyncSession = Depends(get_session),
):
    """Get or create guest cart."""
    cart_repo = CartRepository(session)
    cart = await cart_repo.get_or_create_cart(session_token=session_token)

    items = await cart_repo.get_cart_items(cart.id)

    subtotal = sum(item.price_at_addition * item.qty for item in items)

    return {
        "cart_id": cart.id,
        "session_token": session_token,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "qty": item.qty,
                "price": item.price_at_addition,
            }
            for item in items
        ],
        "subtotal": subtotal,
    }


@router.post("/items")
async def add_to_cart(
    product_id: int,
    qty: int = 1,
    session_token: str = Depends(get_session_token),
    session: AsyncSession = Depends(get_session),
):
    """Add item to cart."""
    cart_repo = CartRepository(session)

    cart = await cart_repo.get_or_create_cart(session_token=session_token)

    # Get product price (will be implemented)
    from app.repositories.product import ProductRepository
    product_repo = ProductRepository(session)
    product = await product_repo.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart_item = await cart_repo.add_item(
        cart_id=cart.id,
        product_id=product_id,
        qty=qty,
        price=product.price,
    )

    return {
        "id": cart_item.id,
        "cart_id": cart_item.cart_id,
        "product_id": cart_item.product_id,
        "qty": cart_item.qty,
    }


@router.put("/items/{cart_item_id}")
async def update_cart_item(
    cart_item_id: int,
    qty: int,
    session: AsyncSession = Depends(get_session),
):
    """Update cart item quantity."""
    cart_repo = CartRepository(session)
    cart_item = await cart_repo.update_item(cart_item_id, qty)

    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    return {"id": cart_item.id, "qty": cart_item.qty}


@router.delete("/items/{cart_item_id}")
async def remove_from_cart(
    cart_item_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Remove item from cart."""
    cart_repo = CartRepository(session)
    success = await cart_repo.remove_item(cart_item_id)

    if not success:
        raise HTTPException(status_code=404, detail="Cart item not found")

    return {"deleted": True}
