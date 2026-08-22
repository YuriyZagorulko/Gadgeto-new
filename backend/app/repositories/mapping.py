"""
Mapping repositories.
"""

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mapping import (
    CategoryMapping,
    AttributeMapping,
    AttributeValueMapping,
)


class CategoryMappingRepository:
    """Repository for category mapping operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_supplier_category(
        self,
        supplier_category_id: int,
    ) -> Optional[CategoryMapping]:
        """Get mapping by supplier category."""
        result = await self.session.execute(
            select(CategoryMapping)
            .where(CategoryMapping.supplier_category_id == supplier_category_id)
        )
        return result.scalar_one_or_none()

    async def get_active_mapping(
        self,
        supplier_category_id: int,
    ) -> Optional[CategoryMapping]:
        """Get active mapping for supplier category."""
        result = await self.session.execute(
            select(CategoryMapping)
            .where(CategoryMapping.supplier_category_id == supplier_category_id)
            .where(CategoryMapping.is_active == True)
        )
        return result.scalar_one_or_none()

    async def create(self, mapping: CategoryMapping) -> CategoryMapping:
        """Create a category mapping."""
        self.session.add(mapping)
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def update(self, mapping: CategoryMapping) -> CategoryMapping:
        """Update a category mapping."""
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping


class AttributeMappingRepository:
    """Repository for attribute mapping operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_supplier_attribute(
        self,
        supplier_attribute_id: int,
    ) -> Optional[AttributeMapping]:
        """Get mapping by supplier attribute."""
        result = await self.session.execute(
            select(AttributeMapping)
            .where(AttributeMapping.supplier_attribute_id == supplier_attribute_id)
        )
        return result.scalar_one_or_none()

    async def get_active_mapping(
        self,
        supplier_attribute_id: int,
    ) -> Optional[AttributeMapping]:
        """Get active mapping for supplier attribute."""
        result = await self.session.execute(
            select(AttributeMapping)
            .where(AttributeMapping.supplier_attribute_id == supplier_attribute_id)
            .where(AttributeMapping.is_active == True)
        )
        return result.scalar_one_or_none()

    async def create(self, mapping: AttributeMapping) -> AttributeMapping:
        """Create an attribute mapping."""
        self.session.add(mapping)
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def update(self, mapping: AttributeMapping) -> AttributeMapping:
        """Update an attribute mapping."""
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping


class AttributeValueMappingRepository:
    """Repository for attribute value mapping operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_supplier_value(
        self,
        supplier_attribute_value_id: int,
    ) -> Optional[AttributeValueMapping]:
        """Get mapping by supplier attribute value."""
        result = await self.session.execute(
            select(AttributeValueMapping)
            .where(AttributeValueMapping.supplier_attribute_value_id == supplier_attribute_value_id)
        )
        return result.scalar_one_or_none()

    async def get_active_mapping(
        self,
        supplier_attribute_value_id: int,
    ) -> Optional[AttributeValueMapping]:
        """Get active mapping for supplier attribute value."""
        result = await self.session.execute(
            select(AttributeValueMapping)
            .where(AttributeValueMapping.supplier_attribute_value_id == supplier_attribute_value_id)
            .where(AttributeValueMapping.is_active == True)
        )
        return result.scalar_one_or_none()

    async def create(self, mapping: AttributeValueMapping) -> AttributeValueMapping:
        """Create an attribute value mapping."""
        self.session.add(mapping)
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def update(self, mapping: AttributeValueMapping) -> AttributeValueMapping:
        """Update an attribute value mapping."""
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping
