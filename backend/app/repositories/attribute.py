"""
Attribute repository.
"""

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attribute import Attribute, AttributeValue


class AttributeRepository:
    """Repository for attribute operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, attribute_id: int) -> Optional[Attribute]:
        """Get attribute by ID."""
        result = await self.session.execute(
            select(Attribute).where(Attribute.id == attribute_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Attribute]:
        """Get attribute by slug."""
        result = await self.session.execute(
            select(Attribute).where(Attribute.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_all_filterable(self) -> List[Attribute]:
        """Get all filterable attributes."""
        result = await self.session.execute(
            select(Attribute)
            .where(Attribute.is_filterable == True)
            .order_by(Attribute.sort_order, Attribute.name)
        )
        return result.scalars().all()

    async def get_category_filters(self, category_id: int) -> List[Attribute]:
        """Get filterable attributes for a category."""
        result = await self.session.execute(
            select(Attribute)
            .join(CategoryFilter, Attribute.id == CategoryFilter.attribute_id)
            .where(CategoryFilter.category_id == category_id)
            .where(CategoryFilter.enabled == True)
            .where(Attribute.is_filterable == True)
            .order_by(CategoryFilter.position, CategoryFilter.id)
        )
        return result.scalars().all()

    async def get_global_filters(self) -> List[Attribute]:
        """Get global default filters (NULL category_id)."""
        result = await self.session.execute(
            select(Attribute)
            .join(CategoryFilter, Attribute.id == CategoryFilter.attribute_id)
            .where(CategoryFilter.category_id == None)
            .where(CategoryFilter.enabled == True)
            .where(Attribute.is_filterable == True)
            .order_by(CategoryFilter.position, CategoryFilter.id)
        )
        return result.scalars().all()

    async def get_value_by_id(self, value_id: int) -> Optional[AttributeValue]:
        """Get attribute value by ID."""
        result = await self.session.execute(
            select(AttributeValue).where(AttributeValue.id == value_id)
        )
        return result.scalar_one_or_none()

    async def get_values_by_attribute(self, attribute_id: int) -> List[AttributeValue]:
        """Get all values for an attribute."""
        result = await self.session.execute(
            select(AttributeValue)
            .where(AttributeValue.attribute_id == attribute_id)
            .where(AttributeValue.is_active == True)
            .order_by(AttributeValue.sort, AttributeValue.value)
        )
        return result.scalars().all()

    async def create(self, attribute: Attribute) -> Attribute:
        """Create a new attribute."""
        self.session.add(attribute)
        await self.session.commit()
        await self.session.refresh(attribute)
        return attribute

    async def create_value(self, value: AttributeValue) -> AttributeValue:
        """Create a new attribute value."""
        self.session.add(value)
        await self.session.commit()
        await self.session.refresh(value)
        return value

    async def update(self, attribute: Attribute) -> Attribute:
        """Update an attribute."""
        await self.session.commit()
        await self.session.refresh(attribute)
        return attribute

    async def update_value(self, value: AttributeValue) -> AttributeValue:
        """Update an attribute value."""
        await self.session.commit()
        await self.session.refresh(value)
        return value

    async def delete(self, attribute: Attribute) -> None:
        """Delete an attribute."""
        await self.session.delete(attribute)
        await self.session.commit()

    async def delete_value(self, value: AttributeValue) -> None:
        """Delete an attribute value."""
        await self.session.delete(value)
        await self.session.commit()
