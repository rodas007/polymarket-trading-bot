"""
Gamma API Client - Market Discovery for Polymarket

Provides access to the Gamma API for discovering active markets,
including 5-minute and 15-minute Up/Down markets for crypto assets.

Example:
    from src.gamma_client import GammaClient

    client = GammaClient()
    market = client.get_current_market("ETH", interval_minutes=15)
    print(market["slug"], market["clobTokenIds"])
"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from .http import ThreadLocalSessionMixin


class GammaClient(ThreadLocalSessionMixin):
    """
    Client for Polymarket's Gamma API.

    Used to discover markets and get market metadata.
    """

    DEFAULT_HOST = "https://gamma-api.polymarket.com"

    # Supported coin slug prefixes by interval
    COIN_SLUGS_BY_INTERVAL = {
        15: {
            "BTC": "btc-updown-15m",
            "ETH": "eth-updown-15m",
            "SOL": "sol-updown-15m",
            "XRP": "xrp-updown-15m",
        },
        5: {
            "BTC": "btc-updown-5m",
            "ETH": "eth-updown-5m",
            "SOL": "sol-updown-5m",
            "XRP": "xrp-updown-5m",
        },
    }

    def __init__(self, host: str = DEFAULT_HOST, timeout: int = 10):
        """
        Initialize Gamma client.

        Args:
            host: Gamma API host URL
            timeout: Request timeout in seconds
        """
        super().__init__()
        self.host = host.rstrip("/")
        self.timeout = timeout

    def get_market_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get market data by slug.

        Args:
            slug: Market slug (e.g., "eth-updown-15m-1766671200")

        Returns:
            Market data dictionary or None if not found
        """
        url = f"{self.host}/markets/slug/{slug}"

        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    def _get_coin_slug_prefix(self, coin: str, interval_minutes: int) -> str:
        """Get slug prefix for a coin and interval."""
        coin = coin.upper()
        mapping = self.COIN_SLUGS_BY_INTERVAL.get(interval_minutes, {})
        if coin not in mapping:
            supported = sorted(mapping.keys())
            raise ValueError(
                f"Unsupported market for coin={coin}, interval={interval_minutes}m. "
                f"Supported for this interval: {supported}"
            )
        return mapping[coin]

    def get_current_market(self, coin: str, interval_minutes: int = 15) -> Optional[Dict[str, Any]]:
        """Get the current active market for a coin/interval."""
        prefix = self._get_coin_slug_prefix(coin, interval_minutes)
        now = datetime.now(timezone.utc)
        interval_seconds = interval_minutes * 60

        current_ts = int(now.timestamp() // interval_seconds * interval_seconds)

        # Try current, next, then previous window
        for ts in (current_ts, current_ts + interval_seconds, current_ts - interval_seconds):
            slug = f"{prefix}-{ts}"
            market = self.get_market_by_slug(slug)
            if market and market.get("acceptingOrders"):
                return market

        return None

    def get_next_market(self, coin: str, interval_minutes: int = 15) -> Optional[Dict[str, Any]]:
        """Get the next upcoming market for a coin/interval."""
        prefix = self._get_coin_slug_prefix(coin, interval_minutes)
        now = datetime.now(timezone.utc)
        interval_seconds = interval_minutes * 60
        current_ts = int(now.timestamp() // interval_seconds * interval_seconds)
        next_ts = current_ts + interval_seconds
        slug = f"{prefix}-{next_ts}"
        return self.get_market_by_slug(slug)

    def get_current_15m_market(self, coin: str) -> Optional[Dict[str, Any]]:
        """Backward-compatible helper for 15-minute markets."""
        return self.get_current_market(coin, interval_minutes=15)

    def get_next_15m_market(self, coin: str) -> Optional[Dict[str, Any]]:
        """Backward-compatible helper for next 15-minute market."""
        return self.get_next_market(coin, interval_minutes=15)

    def parse_token_ids(self, market: Dict[str, Any]) -> Dict[str, str]:
        """
        Parse token IDs from market data.

        Args:
            market: Market data dictionary

        Returns:
            Dictionary with "up" and "down" token IDs
        """
        clob_token_ids = market.get("clobTokenIds", "[]")
        token_ids = self._parse_json_field(clob_token_ids)

        outcomes = market.get("outcomes", '["Up", "Down"]')
        outcomes = self._parse_json_field(outcomes)

        return self._map_outcomes(outcomes, token_ids)

    def parse_prices(self, market: Dict[str, Any]) -> Dict[str, float]:
        """
        Parse current prices from market data.

        Args:
            market: Market data dictionary

        Returns:
            Dictionary with "up" and "down" prices
        """
        outcome_prices = market.get("outcomePrices", '["0.5", "0.5"]')
        prices = self._parse_json_field(outcome_prices)

        outcomes = market.get("outcomes", '["Up", "Down"]')
        outcomes = self._parse_json_field(outcomes)

        return self._map_outcomes(outcomes, prices, cast=float)

    @staticmethod
    def _parse_json_field(value: Any) -> List[Any]:
        """Parse a field that may be a JSON string or a list."""
        if isinstance(value, str):
            return json.loads(value)
        return value

    @staticmethod
    def _map_outcomes(
        outcomes: List[Any],
        values: List[Any],
        cast=lambda v: v
    ) -> Dict[str, Any]:
        """Map outcome labels to values with optional casting."""
        result: Dict[str, Any] = {}
        for i, outcome in enumerate(outcomes):
            if i < len(values):
                result[str(outcome).lower()] = cast(values[i])
        return result

    def get_market_info(self, coin: str, interval_minutes: int = 15) -> Optional[Dict[str, Any]]:
        """Get comprehensive market info for current coin/interval market."""
        market = self.get_current_market(coin, interval_minutes=interval_minutes)
        if not market:
            return None

        token_ids = self.parse_token_ids(market)
        prices = self.parse_prices(market)

        return {
            "slug": market.get("slug"),
            "question": market.get("question"),
            "end_date": market.get("endDate"),
            "token_ids": token_ids,
            "prices": prices,
            "accepting_orders": market.get("acceptingOrders", False),
            "best_bid": market.get("bestBid"),
            "best_ask": market.get("bestAsk"),
            "spread": market.get("spread"),
            "raw": market,
        }
