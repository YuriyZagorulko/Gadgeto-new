"""
Category repository.
"""

from typing import List, Optional

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, CategoryClosure


class CategoryRepository:
    """Repository for category operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, category_id: int) -> Optional[Category]:
        """Get category by ID."""
        result = await self.session.execute(
            select(Category).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Category]:
        """Get category by slug."""
        result = await self.session.execute(
            select(Category).where(Category.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_legacy_id(self, legacy_id: int) -> Optional[Category]:
        """Get category by legacy ID (WooCommerce term_id)."""
        result = await self.session.execute(
            select(Category).where(Category.legacy_id == legacy_id)
        )
        return result.scalar_one_or_none()

    async def get_all_active(self) -> List[Category]:
        """Get all active categories."""
        result = await self.session.execute(
            select(Category)
            .where(Category.is_active == True)
            .order_by(Category.sort_order, Category.name)
        )
        return result.scalars().all()

    async def get_root_categories(self) -> List[Category]:
        """Get root categories (parent_id is NULL)."""
        result = await self.session.execute(
            select(Category)
            .where(Category.parent_id == None)
            .where(Category.is_active == True)
            .order_by(Category.sort_order, Category.name)
        )
        return result.scalars().all()

    async def get_children(self, parent_id: int) -> List[Category]:
        """Get children of a category."""
        result = await self.session.execute(
            select(Category)
            .where(Category.parent_id == parent_id)
            .where(Category.is_active == True)
            .order_by(Category.sort_order, Category.name)
        )
        return result.scalars().all()

    async def get_descendants(self, ancestor_id: int) -> List[Category]:
        """Get all descendants of a category using closure table."""
        result = await self.session.execute(
            select(Category)
            .join(CategoryClosure, Category.id == CategoryClosure.descendant_id)
            .where(CategoryClosure.ancestor_id == ancestor_id)
            .where(Category.is_active == True)
            .order_by(Category.sort_order, Category.name)
        )
        return result.scalars().all()

    async def get_descendant_ids(self, ancestor_id: int) -> List[int]:
        """Get IDs of all descendants of a category."""
        result = await self.session.execute(
            select(CategoryClosure.descendant_id)
            .where(CategoryClosure.ancestor_id == ancestor_id)
        )
        return [row[0] for row in result.fetchall()]

    async def create(self, category: Category) -> Category:
        """Create a new category."""
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def update(self, category: Category) -> Category:
        """Update a category."""
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def delete(self, category: Category) -> None:
        """Delete a category."""
        await self.session.delete(category)
        await self.session.commit()

    async def rebuild_closure(self) -> None:
        """Rebuild category closure table (recursive CTE)."""
        # PostgreSQL recursive CTE
        cte = select(
            Category.id.label("ancestor_id"),
            Category.id.label("descendant_id"),
            func.cast(0, Integer).label("path_length")
        ).where(Category.parent_id == None)

        recursive = select(
            CategoryClosure.ancestor_id,
            Category.id.label("descendant_id"),
            (CategoryClosure.path_length + 1).label("path_length")
        ).join(
            Category, Category.id == CategoryClosure.descendant_id
        ).where(Category.parent_id == CategoryClosure.descendant_id)

        full_cte = cte.union_all(recursive)

        # Delete existing and insert new
        await self.session.execute(delete(CategoryClosure))
        await self.session.execute(
            CategoryClosure.__table__.insert().from_select(
                ["ancestor_id", "descendant_id", "path_length"],
                full_cte
            )
        )
        await self.session.commit()
