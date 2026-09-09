"""Unit tests for the BRAIN importer (backend/app/imports/brain.py).

Uses an in-memory fake client (no network) and patched pricing helpers
(no database).  Verifies streaming behaviour, normalization, category
mapping, realcat handling, archived products and error tolerance.
"""

import importlib.util
import types
from pathlib import Path

import pytest

_BRAIN_PATH = str(
    Path(__file__).resolve().parents[2] / "backend/app/imports/brain.py"
)


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def brain():
    return _load_module("_test_brain_importer_module", _BRAIN_PATH)


class FakeBrainClient:
    """In-memory stand-in for BrainClient (no network, no auth)."""

    def __init__(self, categories=None, vendors=None, flat_pages=None,
                 content=None, page_limit=100, content_error=None):
        self._sid = "fake-sid"
        self._page_limit = page_limit
        self.categories = categories or []
        self.vendors = vendors or []
        self.flat_pages = flat_pages or {}   # root_id -> [base product dicts]
        self.content = content or {}         # productID -> content dict
        self.content_error = content_error
        self.auth_calls = 0
        self.page_requests = []              # (category_id, limit, offset)
        self.content_requests = []           # [ids] per call
        self.logout_calls = 0

    def authenticate(self):
        self.auth_calls += 1
        self._sid = f"sid-{self.auth_calls}"
        return self._sid

    @property
    def page_limit(self):
        return self._page_limit

    def get_categories(self, lang="ua"):
        return self.categories

    def get_vendors(self, lang="ua"):
        return self.vendors

    def get_products_page(self, category_id, limit=None, offset=0, lang="ua"):
        limit = limit or self._page_limit
        self.page_requests.append((category_id, limit, offset))
        items = self.flat_pages.get(category_id, [])
        page = items[offset:offset + limit]
        return {"list": page, "count": len(items)}

    def get_products_content(self, product_ids, lang="ua", batch_size=None):
        self.content_requests.append(list(product_ids))
        if self.content_error is not None:
            raise self.content_error
        return [self.content[pid] for pid in product_ids if pid in self.content]

    def logout(self):
        self.logout_calls += 1
        self._sid = None


def make_categories():
    return [
        {"categoryID": 10, "parentID": 1, "realcat": 0, "name": "Ноутбуки"},
        {"categoryID": 11, "parentID": 1, "realcat": 0, "name": "Телефони"},
        {"categoryID": 12, "parentID": 10, "realcat": 0, "name": "Ігрові ноутбуки"},
        {"categoryID": 20, "parentID": 10, "realcat": 10, "name": "Віртуальна вкладена"},
        {"categoryID": 30, "parentID": 1, "realcat": 10, "name": "Віртуальний топ"},
    ]


def make_product(pid=1, cat=10, **overrides):
    item = {
        "productID": pid,
        "product_code": f"S{pid:07d}",
        "articul": f"ART{pid}",
        "name": f"Товар {pid}",
        "categoryID": cat,
        "vendorID": 77,
        "price": "100.00",                # USD
        "price_uah": "4400.00",
        "recommendable_price": 5000.0,
        "retail_price_uah": "5100.00",
        "is_archive": 0,
        "warranty": "24",
        "country": "Китай",
        "weight": "1.5",
        "volume": 0.02,
        "full_image": f"https://img.brain.test/{pid}_main.jpg",
        "large_image": f"https://img.brain.test/{pid}_big.jpg",
        "brief_description": "короткий опис",
    }
    item.update(overrides)
    return item


def make_content(pid):
    return {
        "productID": pid,
        "description": "повний опис",
        "options": [
            {"OptionID": "1", "OptionName": "Діагональ дисплея",
             "ValueID": "v1", "ValueName": '15.6"'},
        ],
        "images": [
            {"priority": 0,
             "full_image": f"https://img.brain.test/{pid}_main.jpg",
             "large_image": f"https://img.brain.test/{pid}_big.jpg"},
            {"priority": 1,
             "full_image": f"https://img.brain.test/{pid}_2main.jpg"},
        ],
    }


@pytest.fixture
def fake_pricing(brain, monkeypatch):
    """Deterministic pricing without DB access; records supplier_code."""
    price_calls = []

    def fake_calculate_price(price_uah=None, price_usd=None, usd_rate=None,
                             supplier_code="*", category_path=None,
                             category_ids=None):
        price_calls.append({"supplier_code": supplier_code,
                            "price_uah": price_uah, "price_usd": price_usd})
        base = price_uah if price_uah else (price_usd or 0) * 44
        return int(round(base * 100))

    monkeypatch.setattr(brain, "calculate_price", fake_calculate_price)
    monkeypatch.setattr(brain, "find_markup_multiplier",
                        lambda base_price_uah, supplier_code="*",
                        category_path=None, category_ids=None: 1.3)
    monkeypatch.setattr(
        brain, "calculate_old_price",
        lambda source_old_price_uah=None, markup=None: (
            int(round(source_old_price_uah * (markup or 1) * 100))
            if source_old_price_uah else None
        ),
    )
    return price_calls


CATEGORY_MAP = {"Ноутбуки": "Ноутбуки", "Ігрові ноутбуки": "Ноутбуки",
                "Телефони": "Смартфони"}


def make_importer(brain, client, category_map=CATEGORY_MAP):
    importer = brain.BrainImporter(category_map=category_map, client=client)
    # Pre-seed the internal category-id cache so normalization never
    # touches a real database in unit tests.
    for internal in ("Ноутбуки", "Смартфони"):
        importer._internal_cat_ids[internal] = None
    return importer


def run_import(brain, client, category_map=CATEGORY_MAP):
    importer = make_importer(brain, client, category_map=category_map)
    stats = importer.run("full")
    products = list(stats.products)
    return importer, stats, products


# ------------------------------------------------------------ category roots


def test_select_fetch_roots_partition(brain):
    """Only real top-level categories are fetch roots — virtual top-level
    categories are covered by the real subtree they reference."""
    roots = brain.BrainImporter.select_fetch_roots(make_categories())
    assert roots == [10, 11]


def test_resolve_real_category_chain(brain):
    client = FakeBrainClient(categories=make_categories())
    importer = brain.BrainImporter(client=client)
    importer._load_categories(client)
    # real category resolves to itself
    assert importer._resolve_real_category(10) == 10
    # nested virtual resolves to the real target
    assert importer._resolve_real_category(20) == 10
    # top-level virtual resolves to the real target
    assert importer._resolve_real_category(30) == 10
    # unknown category
    assert importer._resolve_real_category(999) is None


def test_realcat_self_reference_is_safe(brain):
    client = FakeBrainClient(categories=[
        {"categoryID": 5, "parentID": 1, "realcat": 5, "name": "Self"},
    ])
    importer = brain.BrainImporter(client=client)
    importer._load_categories(client)
    assert importer._resolve_real_category(5) == 5


# ------------------------------------------------------------ normalization


def test_full_product_normalization(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        vendors=[{"vendorID": 77, "name": "TestBrand", "categoryID": "10"}],
        flat_pages={10: [make_product(1)]},
        content={1: make_content(1)},
    )
    importer, stats, products = run_import(brain, client)

    assert len(products) == 1
    p = products[0]
    assert p.supplier == "brain"
    assert p.supplier_sku == "S0000001"
    assert p.sku == "BRA-S0000001"
    assert p.name == "Товар 1"
    assert p.category_path == "Ноутбуки"
    # price_uah 4400 → 440000 kopecks (fake pricing)
    assert p.price == 440000
    # RRP 5000 × markup 1.3 → 650000 kopecks
    assert p.old_price == 650000
    assert p.brand == "TestBrand"
    assert p.in_stock is True
    assert p.description == "повний опис"
    assert p.short_description == "короткий опис"
    # images come from the content endpoint, in priority order
    assert p.images == [
        "https://img.brain.test/1_main.jpg",
        "https://img.brain.test/1_2main.jpg",
    ]
    assert ("Діагональ дисплея", '15.6"') in p.raw_attributes
    # no resolver installed → attribute recorded as unmapped, not mapped
    assert p.attributes == []
    assert stats.unmapped_attributes["Діагональ дисплея"].count == 1
    assert stats.total == 1
    assert stats.feed_count == 1
    assert stats.processed == 1
    # pricing is scoped to the brain supplier code
    assert fake_pricing[0]["supplier_code"] == "brain"
    assert fake_pricing[0]["price_uah"] == 4400.0


def test_attribute_mapping_through_resolver(brain, fake_pricing, monkeypatch):
    """BRAIN Option → internal attribute via the shared mapping pipeline."""
    from app.imports.attribute_processor import set_db_resolver

    class StubResolver:
        def process_attribute(self, name, value, category_id=None,
                              supplier_attr_external_id=None,
                              supplier_value_external_id=None):
            if name == "Діагональ дисплея":
                return ("Діагональ екрану", value)
            return "UNKNOWN_NAME"

    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1)]},
        content={1: make_content(1)},
    )
    importer = make_importer(brain, client)
    set_db_resolver(StubResolver())
    try:
        stats = importer.run("full")
        products = list(stats.products)
    finally:
        set_db_resolver(None)

    assert products[0].attributes == [("Діагональ екрану", '15.6"')]
    assert stats.unmapped_attributes == {}


def test_brain_category_mapping_isolated(brain, fake_pricing):
    """Brain category mapping uses supplier-scoped map keys — a name mapped
    for IT-Link semantics does not leak: only names in the Brain map apply."""
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1)], 11: [make_product(2, cat=11)]},
    )
    # Only "Ноутбуки" mapped for Brain — "Телефони" intentionally not.
    importer, stats, products = run_import(
        brain, client, category_map={"Ноутбуки": "Ноутбуки"})
    assert [p.category_path for p in products] == ["Ноутбуки"]
    assert stats.skipped == 1
    assert "Телефони" in stats.unmapped_categories
    info = stats.unmapped_categories["Телефони"]
    assert info.supplier_item_id == "11"
    assert info.skus == ["BRA-S0000002"]


# -------------------------------------------------------- streaming & paging


def test_run_returns_streaming_generator(brain, fake_pricing):
    """stats.products must be a generator — the catalog is never
    accumulated in memory."""
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1)]},
    )
    importer = make_importer(brain, client)
    stats = importer.run("full")
    assert isinstance(stats.products, types.GeneratorType)
    list(stats.products)


def test_pagination_walks_all_pages(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1), make_product(2), make_product(3)]},
        page_limit=2,
    )
    importer, stats, products = run_import(brain, client)

    assert len(products) == 3
    assert stats.total == 3
    # discovery pass (limit=1 per root) + streaming pages for root 10
    # (limit=2: offsets 0 and 2) + one empty first page for root 11
    stream_calls = [c for c in client.page_requests if c[1] == 2]
    assert stream_calls == [(10, 2, 0), (10, 2, 2), (11, 2, 0)]


def test_content_batched_per_page(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1), make_product(2)]},
        content={1: make_content(1), 2: make_content(2)},
        page_limit=2,
    )
    run_import(brain, client)
    # one content request per page with all page product IDs
    assert client.content_requests == [[1, 2]]


# ---------------------------------------------------- stock / archive states


def test_archived_product_out_of_stock_and_counted(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1, is_archive=1)]},
    )
    importer, stats, products = run_import(brain, client)
    assert len(products) == 1
    assert products[0].in_stock is False
    assert stats.archived == 1
    assert stats.to_summary_dict()["archived"] == 1


def test_archived_string_flag_handled(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1, is_archive="1")]},
    )
    _, stats, products = run_import(brain, client)
    assert products[0].in_stock is False
    assert stats.archived == 1


def test_stock_fields_absent_defaults_available(brain, fake_pricing):
    """No OWN_LOGISTICS_MODE → no stocks fields → treated as available."""
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1)]},
    )
    _, _, products = run_import(brain, client)
    assert products[0].in_stock is True


def test_stock_fields_present_zero_qty_out_of_stock(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [
            make_product(1, stocks=[0], available={"1": 0}),
            make_product(2, stocks=[1, 2], available={"1": 3}),
        ]},
    )
    _, _, products = run_import(brain, client)
    assert products[0].in_stock is False
    assert products[1].in_stock is True


# ------------------------------------------------------- malformed & failure


def test_missing_sku_recorded_as_empty(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1, product_code="", articul="")]},
    )
    importer, stats, products = run_import(brain, client)
    assert products == []
    assert stats.empty_skus == 1


def test_missing_name_skipped_not_failed(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1, name="")]},
    )
    importer, stats, products = run_import(brain, client)
    assert products == []
    assert stats.skipped == 1
    assert stats.failed == 0
    assert any("порожня назва" in w for w in stats.warnings)


def test_duplicate_sku_counted_once(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1), make_product(1)]},
    )
    importer, stats, products = run_import(brain, client)
    assert len(products) == 1
    assert stats.duplicate_skus == 1


def test_malformed_record_does_not_stop_import(brain, fake_pricing):
    """A product that raises inside normalization is counted as failed,
    and the rest of the category still imports."""
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1), make_product(2)]},
    )
    importer = make_importer(brain, client)
    original = importer._pick_price

    def boom_once(item, category_path=None):
        if item.get("productID") == 1:
            raise RuntimeError("boom")
        return original(item, category_path=category_path)

    importer._pick_price = boom_once
    stats = importer.run("full")
    products = list(stats.products)
    assert stats.failed == 1
    assert len(products) == 1
    assert products[0].supplier_sku == "S0000002"


def test_category_api_failure_does_not_stop_other_roots(brain, fake_pricing):
    """One failing root category is logged; the other roots still import."""

    class PartlyFailingClient(FakeBrainClient):
        def get_products_page(self, category_id, limit=None, offset=0, lang="ua"):
            if category_id == 11 and (limit or 0) > 1:
                raise brain.BrainAPIError("Помилка API BRAIN: код 21",
                                          error_code=21)
            return super().get_products_page(category_id, limit=limit,
                                             offset=offset, lang=lang)

    client = PartlyFailingClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1)],
                    11: [make_product(2, cat=11)]},
    )
    importer, stats, products = run_import(brain, client)
    assert len(products) == 1
    assert products[0].category_path == "Ноутбуки"
    assert any(e.get("root_category") == 11 for e in stats.errors)


def test_content_failure_falls_back_to_base_data(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1)]},
        content_error=brain.BrainAPIError("content down"),
    )
    importer, stats, products = run_import(brain, client)
    assert len(products) == 1
    # base list images are used as the fallback
    assert products[0].images == ["https://img.brain.test/1_main.jpg"]
    assert products[0].description == ""
    assert any("контент" in w for w in stats.warnings)


# ------------------------------------------------------------ images / prices


def test_image_sizes_not_duplicated(brain, fake_pricing):
    """Without content images only ONE base image URL is used (not both
    the full and large sizes of the same picture)."""
    item = make_product(1)
    assert item["full_image"] != item["large_image"]
    urls = brain.BrainImporter._collect_images(item)
    assert urls == ["https://img.brain.test/1_main.jpg"]


def test_duplicate_image_urls_removed(brain, fake_pricing):
    item = make_product(1, images=[
        {"priority": 0, "full_image": "https://img.brain.test/1_main.jpg"},
        {"priority": 1, "full_image": "https://img.brain.test/1_main.jpg"},
    ])
    urls = brain.BrainImporter._collect_images(item)
    assert urls == ["https://img.brain.test/1_main.jpg"]


def test_usd_only_price_used_as_fallback(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1, price="100.00", price_uah="")]},
    )
    _, _, products = run_import(brain, client)
    assert products[0].price == int(100 * 44 * 100)


def test_no_retail_price_means_no_old_price(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1, recommendable_price=0,
                                      retail_price_uah="0")]},
    )
    _, _, products = run_import(brain, client)
    assert products[0].old_price is None


def test_vendor_fallback_without_category_match(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        vendors=[{"vendorID": 77, "name": "GlobalBrand", "categoryID": "999"}],
        flat_pages={10: [make_product(1)]},
    )
    _, _, products = run_import(brain, client)
    assert products[0].brand == "GlobalBrand"


def test_logout_called_after_stream(brain, fake_pricing):
    client = FakeBrainClient(
        categories=make_categories(),
        flat_pages={10: [make_product(1)]},
    )
    importer = make_importer(brain, client)
    stats = importer.run("full")
    assert client.logout_calls == 0
    list(stats.products)
    assert client.logout_calls == 1




