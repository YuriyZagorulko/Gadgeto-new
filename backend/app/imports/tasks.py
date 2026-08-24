"""Import tasks — direct execution (no Celery/Redis dependency).
Importers run as normal Python processes, not background tasks."""

import json
from datetime import datetime
from typing import Optional

from app.imports.registry import SUPPLIERS


def run_import(supplier_code: str, import_type: str = "full") -> dict:
    """
    Run a supplier import synchronously.

    Args:
        supplier_code: one of the fixed system integrations ('itlink' or 'dclink')
        import_type: 'full' or delta types ('prices'/'stock')

    Returns:
        Import statistics dict
    """
    from app.imports.attribute_processor import set_db_resolver

    try:
        entry = SUPPLIERS.get(supplier_code)
        if not entry:
            raise ValueError(f"Unknown supplier: {supplier_code}")

        # DB mappings first: install resolver + DB-derived category map.
        # Empty/partial DB state falls back to legacy JSON behaviour inside
        # the pipeline itself (resolver only overrides where rules exist).
        db_category_map = None
        try:
            from app.imports.mapping_resolver import MappingResolver
            resolver = MappingResolver(supplier_code)
            if resolver.has_rules():
                set_db_resolver(resolver)
                cat_map = resolver.build_category_map()
                if cat_map:
                    db_category_map = cat_map
        except Exception:
            set_db_resolver(None)
            db_category_map = None

        try:
            importer = entry["importer"](category_map=db_category_map)
            stats = importer.run(import_type)
        finally:
            set_db_resolver(None)

        return {
            "success": True,
            "supplier": supplier_code,
            "import_type": import_type,
            "stats": stats,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def notify_import_complete(import_id: int, stats: dict) -> None:
    """Placeholder for future email/admin notification."""
    pass
