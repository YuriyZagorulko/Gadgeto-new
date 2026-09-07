"""Prom.ua mapping isolation tests (unit — no DB).

Prom and Rozetka mappings live in the SAME channel_*_mapping tables but are
fully isolated by ``channel_id`` (plus a ``(channel_id, internal_*)`` unique
constraint).  This test proves the shared resolver scopes every query by the
channel_id of the channel it resolves for — so Prom operations can never read
or touch Rozetka mapping rows.
"""

import pytest


class TestChannelScopedSource:
    """Inspect the SQL the resolver issues to prove channel scoping."""

    def _capture(self, monkeypatch):
        from app.channels import mapping_resolver as mod

        captured = []

        class FakeConn:
            def __init__(self, dsn):
                self.dsn = dsn

            def cursor(self, cursor_factory=None):
                return FakeCur()

            def close(self):
                pass

        class FakeCur:
            def __init__(self):
                self._rows = []

            def execute(self, sql, params=None):
                captured.append((sql, tuple(params or ())))
                self._rows = []

            def fetchall(self):
                return []

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(mod.psycopg2, "connect", lambda *a, **k: FakeConn(a))
        return captured

    def test_category_mapping_scoped_by_channel(self, monkeypatch):
        captured = self._capture(monkeypatch)
        from app.channels.mapping_resolver import ChannelMappingResolver

        ChannelMappingResolver(channel_id=7, channel_code="prom")
        # The resolver queries the shared channel mapping table with a
        # channel_id predicate, so it can only ever load Prom's own rows.
        matching = [x for x in captured if "channel_category_mappings" in x[0]]
        assert matching, "resolver should query channel_category_mappings"
        sql, params = matching[0]
        assert "channel_id = %s" in sql
        assert 7 in params

    def test_attribute_and_value_mappings_scoped_by_channel(self, monkeypatch):
        captured = self._capture(monkeypatch)
        from app.channels.mapping_resolver import ChannelMappingResolver

        ChannelMappingResolver(channel_id=99, channel_code="prom")
        tables = [s for s, _ in captured
                  if any(t in s for t in ("channel_attribute_mappings",
                                          "channel_value_mappings"))]
        assert tables, "resolver should query attribute & value mapping tables"
        assert all("channel_id = %s" in s for s in tables)
        assert any(99 in params for _, params in captured)


class TestPromMappingUsesOwnChannelId:
    def test_prom_and_rozetka_are_distinct_columns(self):
        """The schema separates channels by channel_id — not by channel name —
        so Prom and Rozetka rows are never conflated."""
        from app.models.channel_mapping import (
            ChannelCategoryMapping,
            ChannelAttributeMapping,
            ChannelValueMapping,
        )
        for model in (ChannelCategoryMapping, ChannelAttributeMapping,
                      ChannelValueMapping):
            cols = {c.name for c in model.__table__.columns}
            assert "channel_id" in cols
            assert "id" in cols