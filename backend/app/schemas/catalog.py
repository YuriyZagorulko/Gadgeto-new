"""Pydantic schemas for catalog API."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AttributeValueItem(BaseModel):
    value: str
    count: int = 0


class FilterItem(BaseModel):
    attribute_id: int
    attribute_name: str
    attribute_slug: str
    filter_type: str = "multi-select"
    position: int = 0
    values: List[AttributeValueItem] = []


class CategoryFilterResponse(BaseModel):
    category_id: int
    category_name: str
    category_slug: str
    filters: List[FilterItem]


class ProductListItem(BaseModel):
    id: int
    sku: Optional[str] = None
    name: str
    slug: str
    price: int
    old_price: Optional[int] = None
    stock_status: str = "out_of_stock"
    brand: Optional[str] = None
    image: Optional[str] = None
    category: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    page_size: int
    total_pages: int


class ProductAttributeItem(BaseModel):
    id: int
    name: str
    value: str


class ProductImageItem(BaseModel):
    id: int
    url: str
    sort_order: int
    is_primary: bool


class CategoryBreadcrumb(BaseModel):
    id: int
    name: str
    slug: str


class ProductDetailResponse(BaseModel):
    id: int
    sku: Optional[str] = None
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    price: int
    old_price: Optional[int] = None
    currency: str = "UAH"
    stock_status: str
    stock_qty: Optional[int] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    breadcrumbs: List[CategoryBreadcrumb] = []
    images: List[ProductImageItem] = []
    attributes: List[ProductAttributeItem] = []
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None


class CategoryItem(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: Optional[int] = None
    product_count: int = 0
    children: List["CategoryItem"] = []


class CategoryDetailResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    parent_name: Optional[str] = None
    product_count: int = 0
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    children: List[CategoryItem] = []
    breadcrumbs: List[CategoryBreadcrumb] = []
