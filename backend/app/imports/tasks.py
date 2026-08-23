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
    try:
        entry = SUPPLIERS.get(supplier_code)
        if not entry:
            raise ValueError(f"Unknown supplier: {supplier_code}")

        importer = entry["importer"]()
        stats = importer.run(import_type)

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
