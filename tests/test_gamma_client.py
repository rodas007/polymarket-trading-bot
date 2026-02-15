"""Unit tests for GammaClient interval-aware market discovery."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gamma_client import GammaClient


def test_get_current_market_checks_current_next_previous(monkeypatch):
    client = GammaClient()
    checked = []

    def fake_slug(slug: str):
        checked.append(slug)
        if slug.endswith("-1740138600"):
            return {"acceptingOrders": True, "slug": slug}
        return None

    monkeypatch.setattr(client, "get_market_by_slug", fake_slug)

    class _Now:
        def timestamp(self):
            return 1740138401

    class _Datetime:
        @staticmethod
        def now(_tz):
            return _Now()

    import src.gamma_client as mod

    monkeypatch.setattr(mod, "datetime", _Datetime)

    market = client.get_current_market("BTC", interval_minutes=5)

    assert market is not None
    assert checked == [
        "btc-updown-5m-1740138300",
        "btc-updown-5m-1740138600",
    ]


def test_get_current_market_unsupported_interval():
    client = GammaClient()
    with pytest.raises(ValueError):
        client.get_current_market("ETH", interval_minutes=1)


def test_get_market_info_uses_interval(monkeypatch):
    client = GammaClient()

    def fake_current_market(coin, interval_minutes=15):
        assert coin == "BTC"
        assert interval_minutes == 5
        return {
            "slug": "btc-updown-5m-123",
            "question": "Q",
            "endDate": "2025-01-01T00:05:00Z",
            "clobTokenIds": '["u","d"]',
            "outcomes": '["Up","Down"]',
            "outcomePrices": '["0.4","0.6"]',
            "acceptingOrders": True,
        }

    monkeypatch.setattr(client, "get_current_market", fake_current_market)

    market_info = client.get_market_info("BTC", interval_minutes=5)

    assert market_info is not None
    assert market_info["slug"] == "btc-updown-5m-123"
    assert market_info["token_ids"]["up"] == "u"


def test_get_current_market_supports_eth_5m(monkeypatch):
    client = GammaClient()

    def fake_slug(slug: str):
        if slug.endswith("-1740138300"):
            return {"acceptingOrders": True, "slug": slug}
        return None

    monkeypatch.setattr(client, "get_market_by_slug", fake_slug)

    class _Now:
        def timestamp(self):
            return 1740138401

    class _Datetime:
        @staticmethod
        def now(_tz):
            return _Now()

    import src.gamma_client as mod

    monkeypatch.setattr(mod, "datetime", _Datetime)

    market = client.get_current_market("ETH", interval_minutes=5)

    assert market is not None
    assert market["slug"].startswith("eth-updown-5m-")
