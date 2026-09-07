"""Prom.ua pricing/commission resolver (infrastructure only).

Mirrors ``app.services.rozetka_pricing.RozetkaPricingResolver`` so the export
engine has a single injection point for Prom.ua pricing once it is wired in.

Because Prom.ua pricing data does not exist yet (no credentials / no Prom.ua
commission rules), the resolver always reports ``has_rules = False`` and its
``calculate_export_price`` returns ``None`` — i.e. it never modifies a price.
When Prom.ua documentation/commission data become available, implement the
lookup following the Rozetka resolver pattern.
"""

from __future__ import annotations

from typing import Optional


class PromPricingResolver:
    """Resolves a Prom.ua category pricing rule (commission/markup).

    API mirrors the Rozetka resolver:
      ``has_rules``          — whether any Prom.ua pricing rules are loaded;
      ``calculate_export_price(external_category_id, base_kopecks, brand)``
                             — return the adjusted price in kopecks or None.
    """

    def __init__(self, cur=None, channel_id: int = 0) -> None:
        self._cur = cur
        self.channel_id = channel_id
        self.has_rules = False  # no Prom.ua rules seeded; never invented

    def calculate_export_price(self, external_category_id, base_kopecks,
                               brand: Optional[str] = None) -> Optional[int]:
        """No Prom.ua pricing rules exist → never adjust the price."""
        return None