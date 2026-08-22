"""Import tasks — direct execution (no Celery/Redis dependency).
Importers run as normal Python processes, not background tasks."""

import json
from datetime import datetime
from typing import Optional

from app.imports.itlink import ITLinkImporter
from app.imports.dclink import DCLinkImporter


def run_import(supplier_code: str, import_type: str = "full") -> dict:
    """
    Run a supplier import synchronously.

    Args:
        supplier_code: 'itlink' or 'dclink'
        import_type: 'full' or 'delta'

    Returns:
        Import statistics dict
    """
    try:
        if supplier_code == "itlink":
            importer = ITLinkImporter()
            stats = importer.run(import_type)
        elif supplier_code == "dclink":
            importer = DCLinkImporter()
            stats = importer.run(import_type)
        else:
            raise ValueError(f"Unknown supplier: {supplier_code}")

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
