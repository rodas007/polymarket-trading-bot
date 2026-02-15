"""Tests for MarketWebSocket subscription payloads."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.websocket_client import MarketWebSocket


class DummyWS:
    def __init__(self):
        self.sent = []

    async def send(self, msg: str):
        self.sent.append(msg)


def _make_connected_ws() -> MarketWebSocket:
    ws = MarketWebSocket()
    ws._ws = DummyWS()  # type: ignore[attr-defined]

    try:
        from websockets.protocol import State
        ws._ws.state = State.OPEN  # type: ignore[attr-defined]
    except Exception:
        ws._ws.open = True  # type: ignore[attr-defined]
    return ws


def test_subscribe_uses_lowercase_market_type():
    ws = _make_connected_ws()

    ok = asyncio.run(ws.subscribe(["tok1", "tok2"]))

    assert ok is True
    payload = json.loads(ws._ws.sent[-1])  # type: ignore[attr-defined]
    assert payload == {"assets_ids": ["tok1", "tok2"], "type": "market"}


def test_unsubscribe_payload_has_no_duplicate_keys():
    ws = _make_connected_ws()

    ws._subscribed_assets.update(["tok1", "tok2"])  # type: ignore[attr-defined]
    ok = asyncio.run(ws.unsubscribe(["tok1"]))

    assert ok is True
    payload = json.loads(ws._ws.sent[-1])  # type: ignore[attr-defined]
    assert payload == {"assets_ids": ["tok1"], "type": "market", "operation": "unsubscribe"}
