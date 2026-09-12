"""Unit tests for the Rozetka producer resolution business rule.

Business rule: a missing brand OR a brand unknown to the Rozetka producer
dictionary must resolve to ``Без бренда`` (``ROZETKA_NO_BRAND_PRODUCER_ID``)
— never ``producer_id=0`` and never a PRODUCER_NOT_FOUND failure.  Known
brands resolve to their real Rozetka producer ID.  The rule is identical for
CREATE and UPDATE: the payload builders simply receive the resolved values,
and ``resolve_producer_for_export`` is the single point that guarantees them.

No Rozetka API is contacted — the producer dictionary client is faked.
"""

from unittest.mock import MagicMock

from app.channels.export_run import resolve_producer_for_export
from app.channels.rozetka.payload import (
    ROZETKA_NO_BRAND_PRODUCER_ID,
    ROZETKA_NO_BRAND_PRODUCER_TITLE,
    build_basic_data_item,
    build_create_payload,
)


def _ctx(search_results=None, exc=None, cache=None):
    """Build a minimal export ctx with a faked producer dictionary client."""
    client = MagicMock()
    if exc is not None:
        client.search_producers.side_effect = exc
    else:
        client.search_producers.return_value = search_results or []
    adapter = MagicMock()
    adapter._client = client
    ctx = {"adapter": adapter}
    if cache is not None:
        ctx["_producer_map"] = cache
    return ctx, client


def _transformed(brand):
    return {"brand": brand}


class TestCaseAKnownProducer:
    """A brand known to Rozetka resolves to its real producer ID."""

    def test_known_producer_uses_real_id(self):
        ctx, client = _ctx(search_results=[{"id": 1980, "title": "Modecom"}])
        t = _transformed("Modecom")

        resolve_producer_for_export(ctx, t)

        assert t["producer_id"] == 1980
        assert t["producer_title"] == "Modecom"
        client.search_producers.assert_called_once_with(title="Modecom")

    def test_exact_match_preferred_over_partial_match(self):
        ctx, _ = _ctx(search_results=[
            {"id": 5, "title": "Sky"},
            {"id": 7, "title": "SkyDolphin"},
        ])
        t = _transformed("SkyDolphin")

        resolve_producer_for_export(ctx, t)

        assert t["producer_id"] == 7
        assert t["producer_title"] == "SkyDolphin"

    def test_partial_match_without_exact_keeps_first_hit(self):
        """No exact title match -> previous behaviour (first search hit)."""
        ctx, _ = _ctx(search_results=[{"id": 5, "title": "Sky"}])
        t = _transformed("SkyDolphin")

        resolve_producer_for_export(ctx, t)

        assert t["producer_id"] == 5
        assert t["producer_title"] == "SkyDolphin"


class TestCaseBMissingProducer:
    """A product without a brand resolves to 'Без бренда' (no API call)."""

    def test_missing_brand_resolves_to_no_brand(self):
        ctx, client = _ctx()
        t = _transformed("")

        resolve_producer_for_export(ctx, t)

        assert t["producer_id"] == ROZETKA_NO_BRAND_PRODUCER_ID
        assert t["producer_title"] == ROZETKA_NO_BRAND_PRODUCER_TITLE
        client.search_producers.assert_not_called()

    def test_whitespace_brand_resolves_to_no_brand(self):
        ctx, client = _ctx()
        t = _transformed("   ")

        resolve_producer_for_export(ctx, t)

        assert t["producer_id"] == ROZETKA_NO_BRAND_PRODUCER_ID
        assert t["producer_title"] == ROZETKA_NO_BRAND_PRODUCER_TITLE
        client.search_producers.assert_not_called()


class TestCaseCUnknownProducer:
    """A brand absent from the Rozetka dictionary resolves to 'Без бренда'."""

    def test_unknown_producer_resolves_to_no_brand(self):
        ctx, client = _ctx(search_results=[])
        t = _transformed("SkyDolphin")

        resolve_producer_for_export(ctx, t)

        assert t["producer_id"] == ROZETKA_NO_BRAND_PRODUCER_ID
        assert t["producer_title"] == ROZETKA_NO_BRAND_PRODUCER_TITLE
        client.search_producers.assert_called_once_with(title="SkyDolphin")

    def test_unknown_producer_result_is_cached(self):
        ctx, client = _ctx(search_results=[])
        t1 = _transformed("SkyDolphin")
        t2 = _transformed("SkyDolphin")

        resolve_producer_for_export(ctx, t1)
        resolve_producer_for_export(ctx, t2)

        assert client.search_producers.call_count == 1
        assert t2["producer_id"] == ROZETKA_NO_BRAND_PRODUCER_ID
        assert t2["producer_title"] == ROZETKA_NO_BRAND_PRODUCER_TITLE

    def test_known_producer_result_is_cached(self):
        ctx, client = _ctx(search_results=[{"id": 99, "title": "ASUS"}])
        t1 = _transformed("ASUS")
        t2 = _transformed("ASUS")

        resolve_producer_for_export(ctx, t1)
        resolve_producer_for_export(ctx, t2)

        assert client.search_producers.call_count == 1
        assert t2["producer_id"] == 99

    def test_api_failure_not_cached_and_not_silently_fallback(self):
        """A dictionary API failure is an infrastructure problem, not a
        dictionary miss: producer_id stays 0 with the real brand title and
        the lookup is retried for the next product."""
        ctx, client = _ctx(exc=RuntimeError("producer API down"))
        t1 = _transformed("SkyDolphin")
        t2 = _transformed("SkyDolphin")

        resolve_producer_for_export(ctx, t1)
        resolve_producer_for_export(ctx, t2)

        assert t1["producer_id"] == 0
        assert t1["producer_title"] == "SkyDolphin"
        assert client.search_producers.call_count == 2  # retried, not cached


class TestCaseDECreatePayload:
    """CREATE payload carries the resolved producer (unknown -> Без бренда)."""

    def _base(self, brand):
        return {
            "id": 1, "sku": "T-1", "title": "Чохол тест",
            "price": 100.0, "stock_qty": 5, "stock_status": "in_stock",
            "images": [{"url": "https://example.com/i.jpg"}],
            "category": {"external_id": "146229"},
            "attributes": [],
            "brand": brand,
        }

    def test_create_with_unknown_producer_sends_no_brand(self):
        # Mirrors the resolved transformed produced by
        # resolve_producer_for_export for an unknown brand.
        t = self._base("SkyDolphin")
        t["producer_title"] = ROZETKA_NO_BRAND_PRODUCER_TITLE
        payload, _ = build_create_payload(t, {},
                                          producer_id=ROZETKA_NO_BRAND_PRODUCER_ID)
        assert payload["producer"]["id"] == ROZETKA_NO_BRAND_PRODUCER_ID
        assert payload["producer"]["title"] == ROZETKA_NO_BRAND_PRODUCER_TITLE

    def test_create_with_known_producer_sends_real_id(self):
        payload, _ = build_create_payload(
            self._base("Modecom"), {}, producer_id=1980)
        assert payload["producer"]["id"] == 1980
        assert payload["producer"]["title"] == "Modecom"


class TestCaseEUpdatePayload:
    """UPDATE payload carries the resolved producer (unknown -> Без бренда)."""

    def _base(self, brand):
        return {
            "id": 1, "sku": "T-1", "title": "Чохол тест",
            "description": "Опис",
            "images": [{"url": "https://example.com/i.jpg"}],
            "attributes": [],
            "brand": brand,
        }

    def test_update_with_unknown_producer_sends_no_brand(self):
        # Mirrors the resolved transformed produced by
        # resolve_producer_for_export for an unknown brand.
        t = self._base("SkyDolphin")
        t["producer_title"] = ROZETKA_NO_BRAND_PRODUCER_TITLE
        item, _ = build_basic_data_item(
            {"item_id": 111, "rz_item_id": 222}, t, {},
            producer_id=ROZETKA_NO_BRAND_PRODUCER_ID)
        assert item["producer"]["id"] == ROZETKA_NO_BRAND_PRODUCER_ID
        assert item["producer"]["title"] == ROZETKA_NO_BRAND_PRODUCER_TITLE

    def test_update_with_known_producer_sends_real_id(self):
        item, _ = build_basic_data_item(
            {"item_id": 111, "rz_item_id": 222},
            self._base("Modecom"), {}, producer_id=1980)
        assert item["producer"]["id"] == 1980
        assert item["producer"]["title"] == "Modecom"


class TestPayloadBackwardCompatibility:
    """Callers without producer resolution (validation path) keep the old
    behaviour: the payload builder falls back to the raw brand title."""

    def test_payload_without_producer_title_falls_back_to_brand(self):
        payload, _ = build_create_payload(
            {
                "id": 1, "sku": "T-1", "title": "T",
                "price": 100.0, "stock_qty": 5, "stock_status": "in_stock",
                "images": [{"url": "https://example.com/i.jpg"}],
                "category": {"external_id": "146229"},
                "attributes": [],
                "brand": "UnknownBrandXYZ",
            },
            {}, producer_id=0)
        assert payload["producer"]["id"] == 0
        assert payload["producer"]["title"] == "UnknownBrandXYZ"

    def test_payload_without_brand_and_without_producer_title(self):
        payload, _ = build_create_payload(
            {
                "id": 1, "sku": "T-1", "title": "T",
                "price": 100.0, "stock_qty": 5, "stock_status": "in_stock",
                "images": [{"url": "https://example.com/i.jpg"}],
                "category": {"external_id": "146229"},
                "attributes": [],
                "brand": "",
            },
            {}, producer_id=0)
        assert payload["producer"]["title"] == ROZETKA_NO_BRAND_PRODUCER_TITLE

