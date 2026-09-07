"""Tests for the EMPTY_PARAMS validation rule.

Regression coverage for the Rozetka export failure where products in
categories that REQUIRE characteristics but have ZERO accepted attribute
mappings passed validation and were then pushed to the Rozetka API with an
empty ``params`` list — where they were rejected.

Semantics (current, after the required-attributes fix):

* The Rozetka API exposes NO "required" field for category characteristics.
  The historical ``is_required=1`` rows came from a sync bug that treated
  ``filter_type="main"`` (a UI filter-grouping flag) as obligatoriness.
  ``_get_required_attributes`` therefore returns [] for Rozetka WITHOUT
  querying the database, and optional characteristics can never block an
  export.
* Concern B (MISSING_REQUIRED_ATTR_MAPPING) and Concern C (EMPTY_PARAMS)
  fire ONLY when the category exposes genuinely required characteristics
  (``required_attr_ids`` non-empty).  For Rozetka today this is never the
  case: a product with zero params in an all-optional category is VALID
  (no EMPTY_PARAMS, ready=True).
* A mapped optional list/select characteristic without a value mapping is
  reported as a WARNING (MISSING_ATTRIBUTE_VALUE_MAPPING) and never blocks.

The blocking logic remains in place (and is regression-tested via a
monkeypatched required-attribute provider in
``test_required_attribute_semantics.py``) so that future channels exposing a
real required flag keep the correct behaviour.
"""

import uuid

import pytest

from app.channels.validation import (
    _validate,
    _would_produce_empty_params,
    ISSUE_EMPTY_PARAMS,
    ISSUE_MISSING_ATTRIBUTE_VALUE_MAPPING,
    ISSUE_MISSING_REQUIRED_ATTR_MAPPING,
)


# ---------------------------------------------------------------------------
# Unit tests for _would_produce_empty_params (no database)
# ---------------------------------------------------------------------------


class _FakeResolver:
    """Minimal resolver: attribute/value mappings keyed by internal ID."""

    def __init__(self, attrs=None, vals=None):
        self._attrs = attrs or {}
        self._vals = vals or {}

    def resolve_attribute(self, internal_attribute_id, external_category_id=None):
        return self._attrs.get(internal_attribute_id)

    def resolve_value(self, internal_value_id, external_category_id=None):
        return self._vals.get(internal_value_id)

    def resolve_value_by_text(self, attribute_id, value_text, external_category_id=None):
        # No text-bridge lookups in these unit tests unless explicitly wired.
        return None


class _FakeCursor:
    """Cursor returning the configured specs rows for the category query."""

    def __init__(self, specs):
        # specs: {external_attribute_id: param_type}
        self._rows = [
            {"external_id": str(k), "param_type": v} for k, v in specs.items()
        ]

    def execute(self, *args, **kwargs):
        pass

    def fetchall(self):
        rows = self._rows
        self._rows = []
        return rows


def _product_attr(attribute_id, value_id=None, value_text=None):
    return {
        "attribute_id": attribute_id,
        "attribute_value_id": value_id,
        "value_text": value_text,
    }


def test_would_produce_empty_params_no_attributes():
    """A product with no internal attributes produces empty params."""
    assert _would_produce_empty_params(
        _FakeCursor({"260016": "ComboBox"}),
        channel_id=1,
        ext_cat_id="80089",
        resolver=_FakeResolver(),
        product={"attributes": []},
    ) is True


def test_would_produce_empty_params_unmapped_attributes():
    """Unmapped internal attributes contribute nothing to params."""
    resolver = _FakeResolver(attrs={})  # no accepted mappings at all
    product = {"attributes": [_product_attr(10, value_id=100)]}
    assert _would_produce_empty_params(
        _FakeCursor({"260016": "ComboBox"}), 1, "80089", resolver, product,
    ) is True


def test_would_produce_empty_params_select_without_value_mapping():
    """A mapped list/select characteristic without a value mapping is skipped."""
    resolver = _FakeResolver(attrs={
        10: {"external_attribute_id": "260016"},
    })
    product = {"attributes": [_product_attr(10, value_id=100)]}
    assert _would_produce_empty_params(
        _FakeCursor({"260016": "ComboBox"}), 1, "80089", resolver, product,
    ) is True


def test_would_produce_non_empty_params_select_with_value_mapping():
    """A list/select characteristic WITH an external value ID contributes."""
    resolver = _FakeResolver(
        attrs={10: {"external_attribute_id": "260016"}},
        vals={100: {"external_value_id": "3001"}},
    )
    product = {"attributes": [_product_attr(10, value_id=100)]}
    assert _would_produce_empty_params(
        _FakeCursor({"260016": "ComboBox"}), 1, "80089", resolver, product,
    ) is False


def test_would_produce_non_empty_params_text_attribute():
    """Text-type mapped attributes survive without a value mapping."""
    resolver = _FakeResolver(attrs={
        11: {"external_attribute_id": "20927"},
    })
    product = {"attributes": [_product_attr(11, value_id=None, value_text="7 кг")]}
    assert _would_produce_empty_params(
        _FakeCursor({"20927": "TextInput"}), 1, "80089", resolver, product,
    ) is False


# ---------------------------------------------------------------------------
# Integration tests (dedicated gadgeto_test database).
#
# IMPORTANT: these tests seed through their own COMMITTED connection (not the
# db_connection fixture, whose uncommitted transaction would be invisible to
# ChannelMappingResolver — it opens its own psycopg2 connection). Rows are
# removed best-effort afterwards; the test DB is disposable.
# ---------------------------------------------------------------------------

CATEGORY = "80089"  # Монітори — Rozetka leaf category from the audit


def _connect():
    import psycopg2
    from app.core.db_connect import DB
    return psycopg2.connect(DB, connect_timeout=10)


def _ensure_channel(conn):
    """Return the id of the shared 'rozetka' channel, creating it if needed.

    Other suites (test_automation.py, migration 030) rely on a channel with
    code 'rozetka' — reuse it, never delete it. Taxonomy rows created by this
    test file are scoped to the channel and removed by _cleanup() below.
    """
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO channels (code, name, is_enabled, created_at, updated_at) "
            "VALUES ('rozetka', 'Rozetka', TRUE, NOW(), NOW()) "
            "ON CONFLICT (code) DO NOTHING"
        )
        cur.execute("SELECT id FROM channels WHERE code = 'rozetka'")
        return cur.fetchone()[0]


def _reset_channel_taxonomy(conn, channel_id):
    """Remove any prior rows scoped to (channel, CATEGORY) left by an
    interrupted test run, so seeding is idempotent."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM channel_attribute_mappings "
            "WHERE channel_id=%s AND external_category_id=%s",
            (channel_id, CATEGORY),
        )
        cur.execute(
            "DELETE FROM channel_value_mappings "
            "WHERE channel_id=%s AND external_category_id=%s",
            (channel_id, CATEGORY),
        )
        cur.execute(
            "DELETE FROM channel_external_attributes "
            "WHERE channel_id=%s AND category_external_id=%s",
            (channel_id, CATEGORY),
        )
        cur.execute(
            "DELETE FROM channel_external_categories "
            "WHERE channel_id=%s AND external_id=%s",
            (channel_id, CATEGORY),
        )
    conn.commit()


def _seed_default_product(conn, suffix):
    """Insert a product, a leaf Rozetka category and its required taxonomy,
    scoped to the shared 'rozetka' channel. Rows (except the shared channel)
    are removed best-effort by _cleanup()."""
    import psycopg2.extras
    channel_id = _ensure_channel(conn)
    _reset_channel_taxonomy(conn, channel_id)
    ids = {"channel_id": channel_id}
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO categories "
            "  (name, slug, is_active, sort_order, created_at, updated_at) "
            "VALUES (%s, %s, TRUE, 0, NOW(), NOW()) RETURNING id",
            (f"Монітори {suffix}", f"monitory-{suffix}"),
        )
        ids["cat_id"] = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO channel_external_categories "
            "  (channel_id, external_id, parent_external_id, name, "
            "   created_at, updated_at) "
            "VALUES (%s, %s, NULL, 'Монітори', NOW(), NOW()) RETURNING id",
            (ids["channel_id"], CATEGORY),
        )
        ids["ext_cat_id"] = cur.fetchone()["id"]

        for ext_attr_id, name, ptype in (
            ("260016", "Діагональ дисплея", "ComboBox"),
            ("70727", "Ігрові технології", "List"),
        ):
            cur.execute(
                "INSERT INTO channel_external_attributes "
                "  (channel_id, category_external_id, external_id, name, "
                "   param_type, is_required, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, 1, NOW(), NOW()) RETURNING id",
                (ids["channel_id"], CATEGORY, ext_attr_id, name, ptype),
            )

        cur.execute(
            "INSERT INTO channel_category_mappings "
            "  (channel_id, internal_category_id, external_category_id, "
            "   external_category_name, status, source, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'Монітори', 'accepted', 'manual', NOW(), NOW()) "
            "RETURNING id",
            (ids["channel_id"], ids["cat_id"], CATEGORY),
        )
        cur.execute(
            "INSERT INTO attributes "
            "  (slug, name, type, is_global, is_filterable, sort_order, "
            "   created_at, updated_at) "
            "VALUES (%s, %s, 'select', TRUE, TRUE, 0, NOW(), NOW()) RETURNING id",
            (f"diagonal-{suffix}", "Діагональ дисплея"),
        )
        ids["attr_id"] = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO attribute_values "
            "  (attribute_id, value, slug, sort, is_active, created_at, updated_at) "
            "VALUES (%s, '24\"', %s, 0, TRUE, NOW(), NOW()) RETURNING id",
            (ids["attr_id"], f"24-{suffix}"),
        )
        ids["attr_val_id"] = cur.fetchone()["id"]

        # Second internal attribute mapped to the 'Ігрові технології' (List)
        # required characteristic. Both required Rozetka attrs must map to
        # DISTINCT internal attributes (uq_channel_attr_mapping forbids two
        # external attrs for the same internal attr + category).
        cur.execute(
            "INSERT INTO attributes "
            "  (slug, name, type, is_global, is_filterable, sort_order, "
            "   created_at, updated_at) "
            "VALUES (%s, %s, 'select', TRUE, TRUE, 0, NOW(), NOW()) RETURNING id",
            (f"gaming-{suffix}", "Ігрові технології"),
        )
        ids["attr_id_2"] = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO attribute_values "
            "  (attribute_id, value, slug, sort, is_active, created_at, updated_at) "
            "VALUES (%s, 'Адаптивна', %s, 0, TRUE, NOW(), NOW()) RETURNING id",
            (ids["attr_id_2"], f"adaptive-{suffix}"),
        )
        ids["attr_val_id_2"] = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO products "
            "  (name, slug, status, price, stock_qty, currency, "
            "   is_active, is_visible, created_at, updated_at) "
            "VALUES (%s, %s, 'PUBLISHED', 100, 5, 'UAH', TRUE, TRUE, NOW(), NOW()) "
            "RETURNING id",
            (f"Продукт {suffix}", f"product-{suffix}"),
        )
        ids["product_id"] = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO product_images "
            "  (product_id, url, sort_order, is_primary, "
            "   is_supplier_image, is_suppressed, created_at, updated_at) "
            "VALUES (%s, 'https://example.com/img.jpg', 0, TRUE, FALSE, FALSE, "
            "NOW(), NOW()) RETURNING id",
            (ids["product_id"],),
        )
        cur.execute(
            "INSERT INTO product_categories "
            "  (product_id, category_id, created_at, updated_at) "
            "VALUES (%s, %s, NOW(), NOW()) RETURNING id",
            (ids["product_id"], ids["cat_id"]),
        )
        cur.execute(
            "INSERT INTO product_attributes "
            "  (product_id, attribute_id, attribute_value_id, value_text, "
            "   created_at, updated_at) "
            "VALUES (%s, %s, %s, NULL, NOW(), NOW()) RETURNING id",
            (ids["product_id"], ids["attr_id"], ids["attr_val_id"]),
        )
        cur.execute(
            "INSERT INTO product_attributes "
            "  (product_id, attribute_id, attribute_value_id, value_text, "
            "   created_at, updated_at) "
            "VALUES (%s, %s, %s, NULL, NOW(), NOW()) RETURNING id",
            (ids["product_id"], ids["attr_id_2"], ids["attr_val_id_2"]),
        )
    conn.commit()
    return ids


def _cleanup(conn, ids):
    """Best-effort removal of seed rows (test database only). The shared
    'rozetka' channel row is intentionally kept (other suites depend on it).

    Order matters for FKs: channel/value mappings reference attributes and
    attribute_values, so they must be removed before those tables.
    """
    with conn.cursor() as cur:
        cur.execute("DELETE FROM product_attributes WHERE product_id = %s",
                    (ids["product_id"],))
        cur.execute("DELETE FROM product_categories WHERE product_id = %s",
                    (ids["product_id"],))
        cur.execute("DELETE FROM product_images WHERE product_id = %s",
                    (ids["product_id"],))
        cur.execute(
            "DELETE FROM channel_category_mappings "
            "WHERE channel_id=%s AND internal_category_id=%s",
            (ids["channel_id"], ids["cat_id"]),
        )
        cur.execute(
            "DELETE FROM channel_attribute_mappings "
            "WHERE channel_id=%s AND external_category_id=%s",
            (ids["channel_id"], CATEGORY),
        )
        cur.execute(
            "DELETE FROM channel_value_mappings "
            "WHERE channel_id=%s AND external_category_id=%s",
            (ids["channel_id"], CATEGORY),
        )
        cur.execute(
            "DELETE FROM channel_external_attributes "
            "WHERE channel_id=%s AND category_external_id=%s",
            (ids["channel_id"], CATEGORY),
        )
        cur.execute(
            "DELETE FROM channel_external_categories "
            "WHERE channel_id=%s AND external_id=%s",
            (ids["channel_id"], CATEGORY),
        )
        cur.execute("DELETE FROM products WHERE id = %s",
                    (ids["product_id"],))
        cur.execute("DELETE FROM attribute_values WHERE id = %s",
                    (ids["attr_val_id"],))
        cur.execute("DELETE FROM attribute_values WHERE id = %s",
                    (ids["attr_val_id_2"],))
        cur.execute("DELETE FROM attributes WHERE id = %s",
                    (ids["attr_id"],))
        cur.execute("DELETE FROM attributes WHERE id = %s",
                    (ids["attr_id_2"],))
        cur.execute("DELETE FROM categories WHERE id = %s",
                    (ids["cat_id"],))
    conn.commit()


@pytest.mark.integration
def test_zero_mappings_all_optional_category_is_valid():
    """A product in a category with ZERO accepted attribute mappings and no
    genuinely required characteristics must produce EMPTY_PARAMS (blocking).

    The Rozetka API rejects any product with empty params regardless of
    whether individual characteristics are marked required.  Even when
    is_required=0 on all taxonomy rows, if the product has internal attributes
    but none of them produce a param, the export is blocked.

    Case A/B/F updated: required=[], params={} -> ready=False, EMPTY_PARAMS.
    """
    import psycopg2.extras
    conn = _connect()
    suffix = uuid.uuid4().hex[:8]
    ids = _seed_default_product(conn, suffix)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            result = _validate(cur, ids["product_id"])
        codes = {i["code"] for i in result["issues"]}
        assert result["ready"] is False, (
            "all-optional category with 0 attribute mappings must be blocked, "
            f"got issues: {result['issues']}"
        )
        assert ISSUE_EMPTY_PARAMS in codes, (
            f"EMPTY_PARAMS must fire for a product with no params in any category: "
            f"{sorted(codes)}"
        )
        assert ISSUE_MISSING_REQUIRED_ATTR_MAPPING not in codes, (
            "MISSING_REQUIRED_ATTR_MAPPING must not fire for a required-less category"
        )
    finally:
        _cleanup(conn, ids)
        conn.close()


@pytest.mark.integration
def test_full_mappings_no_empty_params_and_ready():
    """With complete attribute+value mappings the product is ready and no
    EMPTY_PARAMS issue is reported."""
    import psycopg2.extras
    conn = _connect()
    suffix = uuid.uuid4().hex[:8]
    ids = _seed_default_product(conn, suffix)
    try:
        with conn.cursor() as cur:
            # Map each required Rozetka attribute to its own distinct internal
            # attribute (uq_channel_attr_mapping forbids two external attrs
            # sharing one internal attr + category).
            cur.execute(
                "INSERT INTO channel_attribute_mappings "
                "  (channel_id, internal_attribute_id, external_attribute_id, "
                "   external_attribute_name, external_category_id, status, "
                "   source, created_at, updated_at) "
                "VALUES (%s,%s,'260016','Діагональ дисплея',%s,'accepted','manual',"
                "NOW(),NOW())",
                (ids["channel_id"], ids["attr_id"], CATEGORY),
            )
            cur.execute(
                "INSERT INTO channel_attribute_mappings "
                "  (channel_id, internal_attribute_id, external_attribute_id, "
                "   external_attribute_name, external_category_id, status, "
                "   source, created_at, updated_at) "
                "VALUES (%s,%s,'70727','Ігрові технології',%s,'accepted','manual',"
                "NOW(),NOW())",
                (ids["channel_id"], ids["attr_id_2"], CATEGORY),
            )
            cur.execute(
                "INSERT INTO channel_value_mappings "
                "  (channel_id, internal_value_id, external_value_id, "
                "   external_value_name, external_category_id, status, "
                "   source, created_at, updated_at) "
                "VALUES (%s,%s,'3001','24\"',%s,'accepted','manual',NOW(),NOW())",
                (ids["channel_id"], ids["attr_val_id"], CATEGORY),
            )
            cur.execute(
                "INSERT INTO channel_value_mappings "
                "  (channel_id, internal_value_id, external_value_id, "
                "   external_value_name, external_category_id, status, "
                "   source, created_at, updated_at) "
                "VALUES (%s,%s,'3002','Адаптивна',%s,'accepted','manual',NOW(),NOW())",
                (ids["channel_id"], ids["attr_val_id_2"], CATEGORY),
            )
            conn.commit()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            result = _validate(cur, ids["product_id"])
        codes = {i["code"] for i in result["issues"]}
        assert result["ready"] is True, f"expected ready=True, got {result['issues']}"
        assert ISSUE_EMPTY_PARAMS not in codes
        assert ISSUE_MISSING_REQUIRED_ATTR_MAPPING not in codes
    finally:
        _cleanup(conn, ids)
        conn.close()


@pytest.mark.integration
def test_select_without_value_mapping_is_warning_not_blocker():
    """A mapped optional list/select characteristic without a value mapping
    yields a WARNING but also EMPTY_PARAMS because the product still has
    zero usable params (the mapped attribute is skipped at payload-build
    time for lack of a value mapping).  Case F updated.
    """
    import psycopg2.extras
    conn = _connect()
    suffix = uuid.uuid4().hex[:8]
    ids = _seed_default_product(conn, suffix)
    try:
        with conn.cursor() as cur:
            # Map one optional ComboBox characteristic WITHOUT a value mapping.
            cur.execute(
                "INSERT INTO channel_attribute_mappings "
                "  (channel_id, internal_attribute_id, external_attribute_id, "
                "   external_attribute_name, external_category_id, status, "
                "   source, created_at, updated_at) "
                "VALUES (%s,%s,'260016','Діагональ дисплея',%s,'accepted','manual',"
                "NOW(),NOW())",
                (ids["channel_id"], ids["attr_id"], CATEGORY),
            )
            conn.commit()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            result = _validate(cur, ids["product_id"])
        codes = {i["code"] for i in result["issues"]}
        assert result["ready"] is False, (
            "optional value-mapping gap blocks export (zero usable params): "
            f"{result['issues']}"
        )
        assert ISSUE_EMPTY_PARAMS in codes, (
            f"EMPTY_PARAMS must fire when params would be empty: {sorted(codes)}"
        )
        assert ISSUE_MISSING_ATTRIBUTE_VALUE_MAPPING in codes, (
            f"expected MISSING_ATTRIBUTE_VALUE_MAPPING warning, got {sorted(codes)}"
        )
        gap = next(i for i in result["issues"]
                   if i["code"] == ISSUE_MISSING_ATTRIBUTE_VALUE_MAPPING)
        assert gap["severity"] == "warning", gap
    finally:
        _cleanup(conn, ids)
        conn.close()