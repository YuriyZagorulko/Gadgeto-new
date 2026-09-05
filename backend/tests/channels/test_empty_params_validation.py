"""Tests for the EMPTY_PARAMS validation rule.

Regression coverage for the Rozetka export failure where products in
categories that REQUIRE characteristics but have ZERO accepted attribute
mappings passed validation (MISSING_REQUIRED_ATTR_MAPPING did NOT flip
``ready`` to False) and were then pushed to the Rozetka API with an empty
``params`` list — where they were rejected.

The rule has two guards:

* Concern B now sets ``ready=False`` for every required Rozetka attribute
  that has no internal mapping (previously it only appended the issue).
* Concern C (EMPTY_PARAMS) blocks when the category requires
  characteristics but the product would contribute zero usable params
  (no accepted mappings, or every mapped characteristic is a list/select
  with a missing value mapping).
"""

import uuid

import pytest

from app.channels.validation import (
    _validate,
    _would_produce_empty_params,
    ISSUE_EMPTY_PARAMS,
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
def test_required_attrs_with_zero_mappings_block_product():
    """Regression: a category that requires characteristics but has zero
    attribute mappings must yield ready=False + EMPTY_PARAMS (previously
    ready stayed True and the product was pushed with empty params)."""
    import psycopg2.extras
    conn = _connect()
    suffix = uuid.uuid4().hex[:8]
    ids = _seed_default_product(conn, suffix)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            result = _validate(cur, ids["product_id"])
        codes = {i["code"] for i in result["issues"]}
        assert result["ready"] is False, (
            "product in a required-characteristics category with 0 mappings "
            "must NOT be ready"
        )
        assert ISSUE_EMPTY_PARAMS in codes, (
            f"EMPTY_PARAMS missing from {sorted(codes)}"
        )
        assert ISSUE_MISSING_REQUIRED_ATTR_MAPPING in codes, (
            "MISSING_REQUIRED_ATTR_MAPPING must still be reported per "
            "required attribute"
        )
        ep = next(i for i in result["issues"] if i["code"] == ISSUE_EMPTY_PARAMS)
        assert ep["details"]["external_category_id"] == CATEGORY
        assert ep["details"]["required_attribute_count"] == 2
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
def test_select_attrs_without_value_mapping_trip_empty_params():
    """Mapped characteristics alone are not enough: if the only mapped
    characteristics are list/select with a missing value mapping, payload
    params are empty and validation must block with EMPTY_PARAMS."""
    import psycopg2.extras
    conn = _connect()
    suffix = uuid.uuid4().hex[:8]
    ids = _seed_default_product(conn, suffix)
    try:
        with conn.cursor() as cur:
            # Map one required ComboBox characteristic WITHOUT a value mapping.
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
        assert result["ready"] is False
        assert ISSUE_EMPTY_PARAMS in codes, (
            f"EMPTY_PARAMS missing from {sorted(codes)}"
        )
    finally:
        _cleanup(conn, ids)
        conn.close()