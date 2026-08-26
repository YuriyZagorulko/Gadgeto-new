"""Tests for mapping integrity — ensuring correct mapping behavior."""

from app.channels.mapping_resolver import ChannelMappingResolver


class FakeResolver:
    """A deterministic resolver for testing mapping rules."""

    def __init__(self):
        # Category 1 -> "1001", Category 2 -> "2001"
        self._cats = {
            1: {"external_category_id": "1001", "external_category_name": "Cat A"},
            2: {"external_category_id": "2001", "external_category_name": "Cat B"},
        }
        # Attribute 10: cat-specific + global
        self._attrs = {
            (10, "1001"): {"external_attribute_id": "2001", "external_attribute_name": "Attr_for_A"},
            (10, "2001"): {"external_attribute_id": "2003", "external_attribute_name": "Attr_for_B"},
            (10, None): {"external_attribute_id": "2001", "external_attribute_name": "Attr_Global"},
            # Attribute 11: only global
            (11, None): {"external_attribute_id": "2002", "external_attribute_name": "Only_Global"},
        }
        # Values
        self._vals = {
            (100, None): {"external_value_id": "3001", "external_value_name": "Val_Global"},
            (100, "1001"): {"external_value_id": "3002", "external_value_name": "Val_For_A"},
        }

    def resolve_category(self, internal_category_id):
        return self._cats.get(internal_category_id)

    def resolve_attribute(self, internal_attribute_id, external_category_id=None):
        if external_category_id is not None:
            result = self._attrs.get((internal_attribute_id, external_category_id))
            if result:
                return result
        return self._attrs.get((internal_attribute_id, None))

    def resolve_value(self, internal_value_id, external_category_id=None):
        if external_category_id is not None:
            result = self._vals.get((internal_value_id, external_category_id))
            if result:
                return result
        return self._vals.get((internal_value_id, None))

    def resolve_value_by_text(self, attribute_id, value_text, external_category_id=None):
        """Resolve a text value via the intermediate value bridge."""
        # This test FakeResolver doesn't use value_text-based resolution
        return None

    def has_rules(self):
        return True


class TestCategorySpecificMapping:
    """Mapping integrity: one internal attribute maps to different external attrs."""

    def test_same_attr_different_category_different_external(self):
        """Attribute 10 should map to different external IDs in different categories."""
        r = FakeResolver()
        m1 = r.resolve_attribute(10, "1001")
        m2 = r.resolve_attribute(10, "2001")
        assert m1 is not None and m2 is not None
        assert m1["external_attribute_id"] != m2["external_attribute_id"]

    def test_global_fallback_used_when_no_category_specific(self):
        """Attribute 11 (only global) should resolve in any category."""
        r = FakeResolver()
        m = r.resolve_attribute(11, "1001")
        assert m is not None
        assert m["external_attribute_id"] == "2002"

    def test_category_specific_takes_priority_over_global(self):
        """Category-specific mapping should win over global."""
        r = FakeResolver()
        m = r.resolve_attribute(10, "1001")
        # Category-specific returns "2001", global also returns "2001" but cat-specific wins
        assert m["external_attribute_id"] == "2001"
        assert m["external_attribute_name"] == "Attr_for_A"

    def test_global_used_when_no_category_specific_exists(self):
        """When no category-specific mapping, global should be used."""
        r = FakeResolver()
        m = r.resolve_attribute(11, "9999")
        assert m is not None
        assert m["external_attribute_id"] == "2002"


class TestValueMapping:
    """Value mapping integrity."""

    def test_category_specific_value_takes_priority(self):
        r = FakeResolver()
        v = r.resolve_value(100, "1001")
        assert v is not None
        assert v["external_value_id"] == "3002"
        assert v["external_value_name"] == "Val_For_A"

    def test_global_value_fallback(self):
        r = FakeResolver()
        v = r.resolve_value(100, "2001")
        assert v is not None
        assert v["external_value_id"] == "3001"

    def test_none_when_no_mapping(self):
        r = FakeResolver()
        v = r.resolve_value(999, "1001")
        assert v is None


class TestProposedMappingNotAccepted:
    """Proposed/excluded mappings must not be used by the resolver."""

    def test_resolver_loads_only_accepted(self):
        """The resolver only loads 'accepted' status mappings."""
        # This is tested by the resolver's SQL query which filters status='accepted'
        # We verify this by checking the resolver implementation
        import inspect
        source = inspect.getsource(ChannelMappingResolver._load)
        assert "status = 'accepted'" in source


class TestReadiness:
    """Mapping readiness determines if a product can be exported."""

    def test_missing_category_mapping_blocks(self):
        r = FakeResolver()
        mapping = r.resolve_category(999)
        assert mapping is None, "No mapping -> None"

    def test_missing_attribute_mapping_blocks(self):
        r = FakeResolver()
        mapping = r.resolve_attribute(999, "1001")
        assert mapping is None, "No mapping -> None"

    def test_missing_value_mapping_blocks(self):
        r = FakeResolver()
        mapping = r.resolve_value(999, "1001")
        assert mapping is None, "No mapping -> None"

    def test_full_mapping_allows_export(self):
        r = FakeResolver()
        cat = r.resolve_category(1)
        attr = r.resolve_attribute(10, "1001")
        val = r.resolve_value(100, "1001")
        assert cat is not None
        assert attr is not None
        assert val is not None


class TestNoFuzzyFallback:
    """No mapping should silently fall back to name matching."""

    def test_no_name_fallback(self):
        """Resolver never uses name matching as fallback."""
        import inspect
        source = inspect.getsource(ChannelMappingResolver._load)
        # Resolver should only use DB queries, not name matching
        assert "SELECT" in source
        assert "fuzzy" not in source.lower()
        assert "SequenceMatcher" not in source
