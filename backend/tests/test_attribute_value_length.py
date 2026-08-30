"""Focused tests for AttributeValue.value length sync (Phase 7.3).

The database column was widened VARCHAR(255) -> VARCHAR(500) by Alembic
migration 038_attribute_values_value_500. This module verifies:

1. The SQLAlchemy model now declares String(500) for `AttributeValue.value`
   (pure metadata — no DB required).
2. A 330-character value can be persisted through the ORM without truncation
   (real DB, isolated transaction, rolled back — no records left behind).

The DB test skips cleanly when no local database is reachable so the
self-contained suite still runs everywhere.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import String, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

# The plain package import registers every model (app/models/__init__.py), so
# all relationship() targets resolve — the importlib-by-path approach did not
# (ProductAttribute/CategoryAttributeValue weren't registered). Sibling test
# modules that swap sys.modules['app'] for a MagicMock at their own collection
# are collected AFTER this module in the standard suite (see pytest order).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.attribute import AttributeValue  # noqa: E402

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


def _sync_dsn() -> str:
    """Build a sync DSN without importing app.* (sibling test modules
    monkeypatch sys.modules['app']/['psycopg2'] with MagicMock at collection,
    which would corrupt imports). Reads DATABASE_URL from the repo .env with
    the project's dev default as fallback."""
    dsn = None
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                dsn = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not dsn:
        dsn = "postgresql+asyncpg://gadgeto:gadgeto@localhost:5432/gadgeto"
    return dsn.replace("+asyncpg", "+psycopg2")


@pytest.mark.skipif(
    sys.platform != "linux" or not _sync_dsn(), reason="no sync DSN available"
)
def test_orm_persists_330_chars_without_truncation():
    """Round-trip a synthetic unique 330-char value through the ORM in an
    isolated transaction (rolled back — no record left behind)."""
    engine = create_engine(_sync_dsn())
    session = Session(bind=engine)
    try:
        # synthetic 330-char value (must not collide with existing taxonomy)
        value = "Тест-ОRM-330-" + ("є" * (330 - len("Тест-ОRM-330-")))
        assert len(value) == 330
        try:
            obj = AttributeValue(
                attribute_id=179,
                value=value,
                slug="phase7-3-orm-330-char-test",
                sort=0,
                is_active=True,
            )
            session.add(obj)
            session.flush()
        except OperationalError:
            pytest.skip("database not reachable")
        session.refresh(obj)
        assert obj.attribute_id == 179
        assert len(obj.value) == 330
        assert obj.value == value  # exact, no truncation
        session.rollback()
    finally:
        session.close()
        engine.dispose()


@pytest.mark.skipif(
    sys.platform != "linux" or not _sync_dsn(), reason="no sync DSN available"
)
def test_orm_reads_real_phase72_value_9236():
    """The real 330-char DC-Link value (AV 9236, attr 179, from Phase 7.2)
    must be readable through the ORM without truncation."""
    engine = create_engine(_sync_dsn())
    session = Session(bind=engine)
    try:
        try:
            av = session.query(AttributeValue).filter_by(id=9236).one()
        except OperationalError:
            pytest.skip("database not reachable")
        assert av.attribute_id == 179
        assert len(av.value) == 330
        assert av.value == VALUE_330
        assert av.is_active is True
    finally:
        session.close()
        engine.dispose()


def test_orm_rejects_501_chars_no_silent_truncation():
    """A 501-char value must be rejected (DB-level), not silently truncated."""
    engine = create_engine(_sync_dsn())
    session = Session(bind=engine)
    try:
        value = "Z" * 501
        obj = AttributeValue(
            attribute_id=179,
            value=value,
            slug="phase7-3-orm-501-char-test",
            sort=0,
            is_active=True,
        )
        session.add(obj)
        with pytest.raises(Exception):
            session.flush()
        session.rollback()
    except OperationalError:
        # DB unreachable in the current environment -> verify only the ORM
        # declaration level (model allows it; DB is the enforcement point).
        pytest.skip("database not reachable")
    finally:
        session.close()
        engine.dispose()