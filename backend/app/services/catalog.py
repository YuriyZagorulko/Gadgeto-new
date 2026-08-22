"""
Catalog service.
"""

from typing import List, Optional, Tuple

from app.models.product import Product
from app.repositories.product import ProductRepository
from app.repositories.category import CategoryRepository
from app.repositories.attribute import AttributeRepository


class CatalogService:
    """Service for catalog operations."""

    def __init__(self, product_repo: ProductRepository, category_repo: CategoryRepository, attr_repo: AttributeRepository):
        self.product_repo = product_repo
        self.category_repo = category_repo
        self.attr_repo = attr_repo

    async def get_product_by_slug(self, slug: str) -> Optional[Product]:
        """Get product by slug."""
        return await self.product_repo.get_by_slug(slug)

    async def list_products_by_category(
        self,
        category_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Product], int]:
        """List products in a category with pagination."""
        return await self.product_repo.list_by_category(category_id, page, page_size)

    async def get_category_tree(self) -> List[dict]:
        """Get full category tree."""
        root_categories = await self.category_repo.get_root_categories()
        return [self._build_category_tree(cat) for cat in root_categories]

    def _build_category_tree(self, category, depth: int = 0) -> dict:
        """Build category tree dict."""
        return {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "children": [
                self._build_category_tree(child, depth + 1)
                for child in category.children or []
            ],
        }

    async def get_category_filters(self, category_id: int) -> List[dict]:
        """Get filterable attributes for a category."""
        attributes = await self.attr_repo.get_category_filters(category_id)
        return [
            {
                "id": attr.id,
                "name": attr.name,
                "slug": attr.slug,
                "values": [
                    {"id": v.id, "value": v.value, "slug": v.slug}
                    for v in attr.values or []
                    if v.is_active
                ],
            }
            for attr in attributes
        ]
