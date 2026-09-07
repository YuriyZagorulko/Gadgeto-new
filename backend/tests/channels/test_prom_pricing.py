"""Tests for the Prom.ua pricing resolver (infrastructure only).

Prom.ua has no credentials / commission documentation yet, so the resolver is
a deliberate no-op: it must NEVER adjust a price and must report that no rules
exist.  These tests pin that contract so a future real implementation cannot
accidentally start mutating prices before Prom.ua rules are available.
"""

from app.services.prom_pricing import PromPricingResolver


class TestPromPricingResolver:
    """Verify the no-op contract of the placeholder resolver."""

    def test_has_rules_is_false(self):
        """No Prom.ua rules are seeded — resolver must report none."""
        resolver = PromPricingResolver()
        assert resolver.has_rules is False

    def test_calculate_export_price_returns_none(self):
        """Without rules the resolver never produces a price."""
        resolver = PromPricingResolver()
        assert resolver.calculate_export_price("100", 100000) is None

    def test_calculate_export_price_none_with_brand(self):
        """Brand argument accepted (API parity) but result stays None."""
        resolver = PromPricingResolver()
        assert resolver.calculate_export_price("100", 100000, brand="Logitech") is None

    def test_resolver_accepts_cursor_and_channel_id(self):
        """Constructor mirrors RozetkaPricingResolver(cur, channel_id)."""
        resolver = PromPricingResolver(cur=object(), channel_id=42)
        assert resolver.channel_id == 42
        assert resolver.has_rules is False

    def test_zero_and_negative_prices_return_none(self):
        """Even edge-case inputs never yield a price."""
        resolver = PromPricingResolver()
        assert resolver.calculate_export_price("100", 0) is None
        assert resolver.calculate_export_price("100", -100) is None