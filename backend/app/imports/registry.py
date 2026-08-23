"""
Central registry of FIXED system supplier integrations.

Suppliers are developer-managed integrations, NOT user-created entities.
A new supplier is added here (plus its importer class) — never through the UI.
The matching rows in the `suppliers` table are SYSTEM DATA created by the
idempotent seed migration (012_system_suppliers).
"""

from app.imports.itlink import ITLinkImporter
from app.imports.dclink import DCLinkImporter

SUPPLIERS: dict[str, dict] = {
    "itlink": {"name": "IT-Link", "importer": ITLinkImporter},
    "dclink": {"name": "DC-Link", "importer": DCLinkImporter},
}


def get_supplier(code: str) -> dict | None:
    """Return the system definition for a supplier code, or None."""
    return SUPPLIERS.get(code)
