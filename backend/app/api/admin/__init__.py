"""Admin API routes."""
from fastapi import APIRouter
from . import auth, products, categories, attributes, filters, brands
from . import suppliers, mappings, imports, orders, users, dashboard, settings
from . import media, pricing, export, export_mapping, category_attributes, content, rozetka_pricing, export_history
from . import automation

router = APIRouter(prefix="/admin")
from . import product_editor
router.include_router(product_editor.router, prefix="", tags=["admin-product-editor"])
router.include_router(auth.router, prefix="/auth", tags=["admin-auth"])
router.include_router(products.router, prefix="", tags=["admin-products"])
router.include_router(categories.router, prefix="", tags=["admin-categories"])
router.include_router(category_attributes.router, prefix="", tags=["admin-category-attributes"])
router.include_router(attributes.router, prefix="", tags=["admin-attributes"])
router.include_router(filters.router, prefix="", tags=["admin-filters"])
router.include_router(brands.router, prefix="", tags=["admin-brands"])
router.include_router(suppliers.router, prefix="", tags=["admin-suppliers"])
router.include_router(mappings.router, prefix="", tags=["admin-mappings"])
router.include_router(imports.router, prefix="", tags=["admin-imports"])
router.include_router(orders.router, prefix="", tags=["admin-orders"])
router.include_router(users.router, prefix="", tags=["admin-users"])
router.include_router(dashboard.router, prefix="", tags=["admin-dashboard"])
router.include_router(settings.router, prefix="", tags=["admin-settings"])
router.include_router(media.router, prefix="", tags=["admin-media"])
router.include_router(pricing.router, prefix="", tags=["admin-pricing"])
router.include_router(export.router, prefix="", tags=["admin-export"])
router.include_router(export_mapping.router, prefix="", tags=["admin-export-mapping"])
router.include_router(content.router, prefix="", tags=["admin-content"])
router.include_router(rozetka_pricing.router, prefix="", tags=["admin-rozetka-pricing"])
router.include_router(export_history.router, prefix="", tags=["admin-export-history"])
router.include_router(automation.router, prefix="", tags=["admin-automation"])
