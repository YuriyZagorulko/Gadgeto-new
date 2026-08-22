"""
Product repository.
"""

from typing import List, Optional, Tuple

from sqlalchemy import delete, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductImage


class ProductRepository:
    """Repository for product operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        """Get product by ID."""
        result = await self.session.execute(
            select(Product).where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Product]:
        """Get product by slug."""
        result = await self.session.execute(
            select(Product).where(Product.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU."""
        result = await self.session.execute(
            select(Product).where(Product.sku == sku)
        )
        return result.scalar_one_or_none()

    async def get_by_supplier(self, supplier_id: int, supplier_sku: str) -> Optional[Product]:
        """Get product by supplier and supplier SKU."""
        result = await self.session.execute(
            select(Product)
            .where(Product.supplier_id == supplier_id)
            .where(Product.supplier_sku == supplier_sku)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Product], int]:
        """Search products by full-text search."""
        offset = (page - 1) * page_size

        # Full-text search query
        search_query = func.to_tsquery("simple", func.replace(query, " ", "&"))

        result = await self.session.execute(
            select(Product)
            .where(Product.search_vector.op("@@")(search_query))
            .where(Product.is_active == True)
            .order_by(func.ts_rank_cd(Product.search_vector, search_query).desc())
            .offset(offset)
            .limit(page_size)
        )
        products = result.scalars().all()

        # Count total
        count_result = await self.session.execute(
            select(func.count(Product.id))
            .where(Product.search_vector.op("@@")(search_query))
        )
        total = count_result.scalar_one()

        return products, total

    async def list_by_category(
        self,
        category_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Product], int]:
        """List products in a category (including subcategories)."""
        offset = (page - 1) * page_size

        # Get descendant category IDs
        desc_ids_result = await self.session.execute(
            select(CategoryClosure.descendant_id)
            .where(CategoryClosure.ancestor_id == category_id)
        )
        desc_ids = [row[0] for row in desc_ids_result.fetchall()]
        desc_ids.append(category_id)  # Include root category

        result = await self.session.execute(
            select(Product)
            .join(ProductCategory, Product.id == ProductCategory.product_id)
            .where(ProductCategory.category_id.in_(desc_ids))
            .where(Product.is_active == True)
            .order_by(Product.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        products = result.scalars().all()

        # Count total
        count_result = await self.session.execute(
            select(func.count(Product.id))
            .join(ProductCategory, Product.id == ProductCategory.product_id)
            .where(ProductCategory.category_id.in_(desc_ids))
        )
        total = count_result.scalar_one()

        return products, total

    async def create(self, product: Product) -> Product:
        """Create a new product."""
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def update(self, product: Product) -> Product:
        """Update a product."""
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def upsert_by_supplier(
        self,
        supplier_id: int,
        supplier_sku: str,
        defaults: dict,
    ) -> Product:
        """Upsert product by supplier + supplier SKU."""
        stmt = select(Product).where(
            Product.supplier_id == supplier_id,
            Product.supplier_sku == supplier_sku
        )
        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()

        if product is None:
            product = Product(
                supplier_id=supplier_id,
                supplier_sku=supplier_sku,
                **defaults
            )
            self.session.add(product)
        else:
            for key, value in defaults.items():
                setattr(product, key, value)

        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def hide_missing(
        self,
        supplier_id: int,
        supplier_skus: List[str],
    ) -> int:
        """Hide products that are not in the current feed."""
        result = await self.session.execute(
            update(Product)
            .where(Product.supplier_id == supplier_id)
            .where(Product.supplier_sku.not_in(supplier_skus))
            .values(is_active=False, is_visible=False)
        )
        await self.session.commit()
        return result.rowcount
