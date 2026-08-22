"""
Order repository.
"""

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem, Payment


class OrderRepository:
    """Repository for order operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, order_id: int) -> Optional[Order]:
        """Get order by ID."""
        result = await self.session.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, number: str) -> Optional[Order]:
        """Get order by display number."""
        result = await self.session.execute(
            select(Order).where(Order.number == number)
        )
        return result.scalar_one_or_none()

    async def get_user_orders(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Order]:
        """Get orders for a user."""
        offset = (page - 1) * page_size

        result = await self.session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all()

    async def create(self, order: Order) -> Order:
        """Create a new order."""
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def update(self, order: Order) -> Order:
        """Update an order."""
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def add_item(self, order_item: OrderItem) -> OrderItem:
        """Add item to order."""
        self.session.add(order_item)
        await self.session.commit()
        await self.session.refresh(order_item)
        return order_item

    async def create_payment(
        self,
        order_id: int,
        payment_id: str,
        amount: int,
        status: str = "pending",
    ) -> Payment:
        """Create a payment record."""
        payment = Payment(
            order_id=order_id,
            payment_id=payment_id,
            amount=amount,
            status=status,
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_order_payments(self, order_id: int) -> List[Payment]:
        """Get payments for an order."""
        result = await self.session.execute(
            select(Payment).where(Payment.order_id == order_id)
        )
        return result.scalars().all()
