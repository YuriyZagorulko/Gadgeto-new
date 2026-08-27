# Rozetka Skill

## Overview

Rozetka is a sales channel (not a supplier). The project interfaces with Rozetka
through its seller API for taxonomy synchronization and product export/listing.

## Architecture

The Rozetka integration lives in:

- `backend/app/channels/rozetka/` — client, taxonomy, mapping, payload, validation
- `admin/src/app/export/rozetka/` — admin UI for mapping management
- `backend/tests/channels/` — tests for client, taxonomy, mapping, validation

Key modules:

| Module | Purpose |
|--------|---------|
| `client.py` | RozetkaAuthClient — OAuth2 authentication to Rozetka seller API |
| `taxonomy.py` | RozetkaTaxonomyService — fetch & cache categories, attributes, values |
| `taxonomy_run.py` | Orchestrated taxonomy refresh runs |
| `mapping_suggestions.py` | Auto-suggest internal ↔ Rozetka mappings |
| `payload.py` | Build product listing payloads for Rozetka |
| `rozetka_validation.py` | Validate product data against Rozetka requirements |
| `api.py` | FastAPI routes for Rozetka taxonomy and mapping |
| `mapping_resolver.py` (parent) | Shared mapping resolution across channels |

## Rozetka Mapping System

The Rozetka mapping system mirrors the internal mapping structure but maps
**internal entities → Rozetka external entities**:

### Category Mappings

Map internal product categories to Rozetka category IDs. Admin-editable via the
mapping UI at `/export/rozetka/mapping`.

### Attribute Mappings

Map internal attributes to Rozetka attributes (scoped to a Rozetka category).
Support search, sorting, pagination, create/edit/delete, enable/disable, and
unresolved mappings.

### Attribute Value Mappings

Map internal attribute values to Rozetka attribute values. Follow the same CRUD
and search semantics as attribute mappings.

### Exclusion

Not all internal entities need to map to Rozetka. Mappings can be toggled
active/inactive. Unresolved mappings remain visible for manual reconciliation.

## Mapping CRUD Behavior

- Deleting a mapping deletes **only the mapping rule**, never the underlying:
  category, attribute, attribute value, or Rozetka external entity.
- For imported/legacy mappings: preserve valid mappings, avoid duplicates,
  prefer idempotent upserts.
- Never overwrite valid mappings with empty values.
- Keep unresolved mappings visible and editable in the UI.

## Taxonomy

Rozetka taxonomy (categories, attributes, attribute values) is fetched from the
Rozetka seller API and cached locally. Taxonomy refresh runs are tracked and
viewable in the admin UI.

Key endpoints:

- `GET /export/channels/rozetka/taxonomy` — browse cached taxonomy
- `POST /export/channels/rozetka/taxonomy/refresh` — trigger refresh
- `GET /export/channels/rozetka/taxonomy/runs/<id>` — view run report
- `GET /export/channels/rozetka/mapping-coverage` — coverage stats
- `GET/POST/PUT/DELETE /export/channels/rozetka/mappings/<type>` — CRUD

## Product Export

Products are exported to Rozetka via the channel export system. The export
process validates products against Rozetka-specific requirements before sending.

## Known Implementation Details

- Rozetka auth uses OAuth2 with seller credentials (`ROZETKA_SELLER_LOGIN`,
  `ROZETKA_SELLER_PASSWORD`).
- Taxonomy data: categories, attributes (with required/optional flags), values.
- Mapping suggestions are based on name similarity between internal and Rozetka entities.
- The channel export run system (`export_run.py`) manages the full export lifecycle
  with status tracking and error reporting.

## Testing

Tests are in `backend/tests/channels/`:

- `test_rozetka_client.py` — auth client error handling
- `test_rozetka_taxonomy.py` — taxonomy service with HTTP mocking
- `test_rozetka_mapping.py` — mapping CRUD and resolution
- `test_validation.py` — Rozetka-specific validation
- `test_export_products_api.py` — product export API
- `test_export_taxonomy_api.py` — taxonomy export API
- `test_mapping_integrity.py` — mapping data integrity checks

Run with: `cd backend && pytest tests/channels/`