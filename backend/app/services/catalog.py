"""Catalog service - lazy imports for ORM."""
from typing import List, Optional, Tuple

class CatalogService:
    def __init__(self, product_repo=None, category_repo=None, attr_repo=None):
        self.product_repo = product_repo
        self.category_repo = category_repo
        self.attr_repo = attr_repo

    async def get_product_by_slug(self, slug: str) -> Optional[dict]:
        from app.repositories.product import ProductRepository
        return await self.product_repo.get_by_slug(slug)

    async def get_category_tree(self) -> List[dict]:
        return []

    async def get_category_filters(self, category_id: int) -> List[dict]:
        return []
