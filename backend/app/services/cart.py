"""
Cart service.
"""

from typing import List, Optional

from app.models.cart import CartItem
from app.repositories.cart import CartRepository
from app.repositories.product import ProductRepository


class CartService:
    """Service for cart operations."""

    def __init__(self, cart_repo: CartRepository, product_repo: ProductRepository):
        self.cart_repo = cart_repo
        self.product_repo = product_repo

    async def get_or_create_cart(
        self,
        user_id: Optional[int] = None,
        session_token: Optional[str] = None,
    ) -> dict:
        """Get or create cart."""
        cart = await self.cart_repo.get_or_create_cart(user_id, session_token)
        return {
            "id": cart.id,
            "session_token": cart.session_token,
            "user_id": cart.user_id,
            "items": [],
            "subtotal": 0,
        }

    async def add_item(
        self,
        cart_id: int,
        product_id: int,
        qty: int = 1,
    ) -> dict:
        """Add item to cart."""
        # Get product price
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise ValueError("Product not found")

        cart_item = await self.cart_repo.add_item(
            cart_id=cart_id,
            product_id=product_id,
            qty=qty,
            price=product.price,
        )

        return {
            "id": cart_item.id,
            "cart_id": cart_item.cart_id,
            "product_id": cart_item.product_id,
            "qty": cart_item.qty,
            "price": cart_item.price_at_addition,
        }

    async def update_item(
        self,
        cart_item_id: int,
        qty: int,
    ) -> Optional[dict]:
        """Update cart item quantity."""
        cart_item = await self.cart_repo.update_item(cart_item_id, qty)
        if not cart_item:
            return None

        return {
            "id": cart_item.id,
            "qty": cart_item.qty,
        }

    async def remove_item(self, cart_item_id: int) -> bool:
        """Remove item from cart."""
        return await self.cart_repo.remove_item(cart_item_id)

    async def get_cart(self, cart_id: int) -> dict:
        """Get cart with items."""
        items = await self.cart_repo.get_cart_items(cart_id)

        subtotal = sum(item.price_at_addition * item.qty for item in items)

        return {
            "id": cart_id,
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
