#!/usr/bin/env python3
"""Create all database tables from SQLAlchemy models."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://gadgeto:gadgeto@localhost:5432/gadgeto")

async def main():
    from backend.app.models.base import Base, main_metadata
    from backend.app.models.user import User, UserRole, UserStatus
    from backend.app.models.session import UserSession
    from backend.app.models.category import Category
    from backend.app.models.attribute import Attribute, AttributeValue
    from backend.app.models.product import Product, ProductImage, ProductCategory, ProductAttribute, ProductStatus
    from backend.app.models.brand import Brand
    from backend.app.models.supplier import Supplier, SupplierCategory, SupplierAttribute, SupplierAttributeValue, SupplierProduct
    from backend.app.models.mapping import CategoryMapping, AttributeMapping, AttributeValueMapping, MappingSource
    from backend.app.models.cart import Cart, CartItem
    from backend.app.models.order import Order, OrderItem, OrderEvent, Payment, ShippingAddress, OrderStatus
    from backend.app.models.import_job import ImportJob, ImportLog, ImportJobStatus
    from backend.app.models.settings import Setting
    from backend.app.models.url_alias import URLAlias
    from backend.app.models.filter import CategoryFilter
    from backend.app.models.product_relations import ProductRelated

    print(f"Total tables in metadata: {len(main_metadata.sorted_tables)}")
    for t in main_metadata.sorted_tables:
        print(f"  {t.name}: {[c.name for c in t.columns]}")
    
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(main_metadata.drop_all)
        await conn.run_sync(main_metadata.create_all)
    await engine.dispose()
    print("\nAll tables created successfully!")

if __name__ == "__main__":
    asyncio.run(main())
