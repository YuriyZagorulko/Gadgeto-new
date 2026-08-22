"""
Brand repository.
"""

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand


class BrandRepository:
    """Repository for brand operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, brand_id: int) -> Optional[Brand]:
        """Get brand by ID."""
        result = await self.session.execute(
            select(Brand).where(Brand.id == brand_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Brand]:
        """Get brand by slug."""
        result = await self.session.execute(
            select(Brand).where(Brand.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_all_active(self) -> List[Brand]:
        """Get all active brands."""
        result = await self.session.execute(
            select(Brand)
            .where(Brand.is_active == True)
            .order_by(Brand.name)
        )
        return result.scalars().all()

    async def create(self, brand: Brand) -> Brand:
        """Create a new brand."""
        self.session.add(brand)
        await self.session.commit()
        await self.session.refresh(brand)
        return brand

    async def update(self, brand: Brand) -> Brand:
        """Update a brand."""
        await self.session.commit()
        await self.session.refresh(brand)
        return brand

    async def delete(self, brand: Brand) -> None:
        """Delete a brand."""
        await self.session.delete(brand)
        await self.session.commit()
