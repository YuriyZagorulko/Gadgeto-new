"""
Cart repository.
"""

from typing import Optional

from datetime import datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import Cart, CartItem


class CartRepository:
    """Repository for cart operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_cart(
        self,
        user_id: Optional[int] = None,
        session_token: Optional[str] = None,
    ) -> Cart:
        """Get existing cart or create new one."""
        if user_id:
            result = await self.session.execute(
                select(Cart).where(Cart.user_id == user_id)
            )
        elif session_token:
            result = await self.session.execute(
                select(Cart).where(Cart.session_token == session_token)
            )
        else:
            # Create guest cart
            cart = Cart(session_token=str(uuid4()))
            self.session.add(cart)
            await self.session.commit()
            await self.session.refresh(cart)
            return cart

        cart = result.scalar_one_or_none()
        if cart is None:
            if session_token:
                cart = Cart(session_token=session_token)
            else:
                cart = Cart(user_id=user_id)
            self.session.add(cart)
            await self.session.commit()
            await self.session.refresh(cart)

        return cart

    async def get_cart_items(self, cart_id: int) -> list[CartItem]:
        """Get all items in a cart."""
        result = await self.session.execute(
            select(CartItem).where(CartItem.cart_id == cart_id)
        )
        return result.scalars().all()

    async def add_item(
        self,
        cart_id: int,
        product_id: int,
        qty: int = 1,
        price: int = 0,
    ) -> CartItem:
        """Add item to cart or update quantity."""
        # Check if item exists
        result = await self.session.execute(
            select(CartItem)
            .where(CartItem.cart_id == cart_id)
            .where(CartItem.product_id == product_id)
        )
        cart_item = result.scalar_one_or_none()

        if cart_item:
            cart_item.qty += qty
        else:
            cart_item = CartItem(
                cart_id=cart_id,
                product_id=product_id,
                qty=qty,
                price_at_addition=price,
            )
            self.session.add(cart_item)

        await self.session.commit()
        await self.session.refresh(cart_item)
        return cart_item

    async def update_item(
        self,
        cart_item_id: int,
        qty: int,
    ) -> Optional[CartItem]:
        """Update cart item quantity."""
        result = await self.session.execute(
            select(CartItem).where(CartItem.id == cart_item_id)
        )
        cart_item = result.scalar_one_or_none()

        if cart_item:
            cart_item.qty = qty
            await self.session.commit()
            await self.session.refresh(cart_item)

        return cart_item

    async def remove_item(self, cart_item_id: int) -> bool:
        """Remove item from cart."""
        result = await self.session.execute(
            select(CartItem).where(CartItem.id == cart_item_id)
        )
        cart_item = result.scalar_one_or_none()

        if cart_item:
            await self.session.delete(cart_item)
            await self.session.commit()
            return True

        return False

    async def clear_cart(self, cart_id: int) -> None:
        """Clear all items from cart."""
        await self.session.execute(
            delete(CartItem).where(CartItem.cart_id == cart_id)
        )
        await self.session.commit()
