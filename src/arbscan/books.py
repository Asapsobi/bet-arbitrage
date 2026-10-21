"""Latest snapshot of every venue's book, per market."""
from __future__ import annotations


class Books:
    """A snapshot replaces a venue's whole book for one market, so an empty
    snapshot is a fresh observation that the venue has no liquidity there."""

    def __init__(self):
        self._by_market = {}       # MarketKey -> {venue: (ts, offers)}

    def update(self, venue, market, ts, offers):
        self._by_market.setdefault(market, {})[venue] = (ts, tuple(offers))

    def offers(self, market):
        return [o for _, offs in self._by_market.get(market, {}).values() for o in offs]

    def fresh_venues(self, market, now, max_age):
        return {v for v, (ts, _) in self._by_market.get(market, {}).items() if now - ts <= max_age}
