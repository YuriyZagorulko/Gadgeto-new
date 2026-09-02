"""Focused tests for AttributeValue.value length sync (Phase 7.3).

The database column was widened VARCHAR(255) -> VARCHAR(500) by Alembic
migration 038_attribute_values_value_500. This module verifies:

1. The SQLAlchemy model declares String(500) for ``AttributeValue.value``
   (pure metadata — no DB required).
2. A 330-character value can be persisted without truncation
   (real DB, isolated transaction, rolled back at teardown).

All DB-touching tests use the ``db_connection`` fixture defined in
``conftest.py``. Tests must NOT call ``conn.commit()`` — see the
fixture's docstring.
"""
import pytest
from sqlalchemy import String
from sqlalchemy.exc import OperationalError

from app.models.attribute import AttributeValue  # noqa: E402

pytestmark = pytest.mark.integration

VALUE_330 = (
    "MB (20+4) pin - 620 мм; CPU (4+4) pin - 700 мм; CPU 8 pin - 700 мм; "
    "PCIE (6+2) pin - 3 х 650 мм; PCIE (6+2) pin - 650 + 100 мм; "
    "16 PIN PCIe GEN5 - 650 мм; SATA - 300 + 15 + 15 + 15 мм; "
    "SATA - 400 + 150 + 150 + 150 мм; SATA - 2 х (375 + 150 мм); "
    "Molex - 500 + 150 + 150 + 150 мм; USB 9 pin - 470 мм; "
    "USB 9 pin - USB Type A - 550 мм"
)


def test_model_value_column_is_string_500():
    """ORM declaration must mirror the applied DB schema (VARCHAR(500))."""
    col = AttributeValue.__table__.c.value
    assert isinstance(col.type, String)
    assert col.type.length == 500


def test_orm_persists_330_chars_without_truncation(db_connection):
    """Round-trip a synthetic unique 330-char value. Rolled back at teardown.

    Skips when the test database has no ``attributes`` rows to satisfy
    the FK constraint (the schema is bootstrapped but no seed data
    is loaded).
    """
    cur = db_connection.cursor()
    try:
        cur.execute("SELECT id FROM attributes LIMIT 1")
        row = cur.fetchone()
        if row is None:
            pytest.skip("no attributes seeded in the test database.")
        attribute_id = row[0]
        value = "Тест-ОRM-330-" + ("є" * (330 - len("Тест-ОRM-330-")))
        assert len(value) == 330
        cur.execute(
            "INSERT INTO attribute_values "
            "(attribute_id, value, slug, sort, is_active, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW(), NOW()) RETURNING id",
            (attribute_id, value, "phase7-3-orm-330-char-test", 0, True),
        )
        new_id = cur.fetchone()[0]
        cur.execute(
            "SELECT value FROM attribute_values WHERE id = %s", (new_id,)
        )
        row = cur.fetchone()
        assert row is not None
        v = row[0]
        assert len(v) == 330
        assert v == value
    except OperationalError as exc:
        pytest.skip(f"database not reachable: {exc}")


def test_orm_reads_real_phase72_value_9236(db_connection):
    """The real 330-char DC-Link value (AV 9236, attr 179) must be readable.

    Skips in ``gadgeto_test`` because AV 9236 is not seeded there.
    """
    cur = db_connection.cursor()
    try:
        cur.execute(
            "SELECT attribute_id, value, is_active FROM attribute_values WHERE id = 9236"
        )
        row = cur.fetchone()
        if row is None:
            pytest.skip("AV 9236 not seeded in the test database.")
        attribute_id, value, is_active = row[0], row[1], row[2]
        assert attribute_id == 179
        assert len(value) == 330
        assert value == VALUE_330
        assert is_active is True
    except OperationalError as exc:
        pytest.skip(f"database not reachable: {exc}")


def test_orm_rejects_501_chars_no_silent_truncation(db_connection):
    """A 501-char value must be rejected by the DB, not silently truncated.

    Skips when the test database has no ``attributes`` rows to satisfy
    the FK constraint.
    """
    cur = db_connection.cursor()
    try:
        cur.execute("SELECT id FROM attributes LIMIT 1")
        row = cur.fetchone()
        if row is None:
            pytest.skip("no attributes seeded in the test database.")
        attribute_id = row[0]
        value = "Z" * 501
        cur.execute(
            "INSERT INTO attribute_values "
            "(attribute_id, value, slug, sort, is_active, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW(), NOW())",
            (attribute_id, value, "phase7-3-orm-501-char-test", 0, True),
        )
        pytest.fail(
            "DB accepted a 501-char value — should have raised."
        )
    except OperationalError as exc:
        pytest.skip(f"database not reachable: {exc}")
    except Exception:
        # DB correctly rejected the too-long value.
        pass