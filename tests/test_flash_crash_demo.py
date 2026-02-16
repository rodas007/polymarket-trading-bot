"""Tests for demo/paper flash crash strategy state persistence."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.market_manager import MarketInfo
from strategies.flash_crash import DemoFlashCrashConfig, DemoFlashCrashStrategy


class DummyBot:
    def is_initialized(self):
        return True

    async def place_order(self, **kwargs):
        class R:
            success = True
            order_id = "paper-order"
            message = "ok"

        return R()

    async def get_open_orders(self):
        return []

    async def cancel_all_orders(self):
        class R:
            success = True

        return R()


def _strategy(tmp_path, resume=True, reset_state=False, realistic=False):
    os.environ["REALISTIC_PAPER"] = "1" if realistic else "0"
    if not realistic:
        for key in [
            "NO_FILL_PROB",
            "PARTIAL_FILL_MIN",
            "PARTIAL_FILL_MAX",
            "MIN_ENTRY_PRICE",
            "MAX_ENTRY_PRICE",
            "LIQUIDITY_USD_CAP",
            "SLIPPAGE_BPS",
            "TAKER_FEE_BPS",
        ]:
            os.environ.pop(key, None)

    cfg = DemoFlashCrashConfig(
        coin="BTC",
        interval_minutes=5,
        size=5.0,
        demo_hours=24,
        start_bankroll=20.0,
        state_file=str(tmp_path / "demo_state.json"),
        resume=resume,
        reset_state=reset_state,
    )
    return DemoFlashCrashStrategy(bot=DummyBot(), config=cfg)


def test_demo_state_persists_and_restores(tmp_path):
    s1 = _strategy(tmp_path, resume=False, reset_state=True)
    s1.bankroll = 17.5
    s1.positions.open_position("up", "tok-up", entry_price=0.5, size=10.0, order_id="paper-a")
    s1._save_state()

    s2 = _strategy(tmp_path, resume=True, reset_state=False)
    assert s2.bankroll == 17.5
    assert len(s2.positions.get_all_positions()) == 1
    pos = s2.positions.get_all_positions()[0]
    assert pos.side == "up"
    assert pos.token_id == "tok-up"


def test_demo_execute_buy_uses_available_bankroll(tmp_path):
    s = _strategy(tmp_path, resume=False, reset_state=True)
    s.market.current_market = MarketInfo(
        slug="btc-updown-5m-1000",
        question="",
        end_date="",
        token_ids={"up": "tok-up", "down": "tok-down"},
        prices={},
        accepting_orders=True,
    )

    ok = asyncio.run(s.execute_buy("up", 0.5))
    assert ok is True
    assert len(s.positions.get_all_positions()) == 1

    # Bankroll is not decremented on open (PnL-based accounting), but available is reduced by reserved stake
    assert s._available_bankroll() <= s.bankroll


def test_demo_trade_events_are_written_to_run_log(tmp_path):
    s = _strategy(tmp_path, resume=False, reset_state=True)
    s.market.current_market = MarketInfo(
        slug="btc-updown-5m-1000",
        question="",
        end_date="",
        token_ids={"up": "tok-up", "down": "tok-down"},
        prices={},
        accepting_orders=True,
    )

    assert s._run_logger.log_path is not None

    opened = asyncio.run(s.execute_buy("up", 0.5))
    assert opened is True

    pos = s.positions.get_all_positions()[0]
    closed = asyncio.run(s.execute_sell(pos, 0.6))
    assert closed is True

    log_file = Path(s._run_logger.log_path)
    content = log_file.read_text(encoding="utf-8")

    assert '"event": "trade_opened"' in content
    assert '"event": "trade_closed"' in content
    assert '"entry_price": 0.5' in content
    assert '"exit_price": 0.6' in content


def test_demo_execute_buy_uses_size_percent_of_bankroll(tmp_path):
    os.environ["REALISTIC_PAPER"] = "0"

    cfg = DemoFlashCrashConfig(
        coin="BTC",
        interval_minutes=5,
        size=5.0,
        size_percent=10.0,
        demo_hours=24,
        start_bankroll=20.0,
        state_file=str(tmp_path / "demo_state.json"),
        resume=False,
        reset_state=True,
    )
    s = DemoFlashCrashStrategy(bot=DummyBot(), config=cfg)
    s.market.current_market = MarketInfo(
        slug="btc-updown-5m-1000",
        question="",
        end_date="",
        token_ids={"up": "tok-up", "down": "tok-down"},
        prices={},
        accepting_orders=True,
    )

    ok = asyncio.run(s.execute_buy("up", 0.5))
    assert ok is True
    pos = s.positions.get_all_positions()[0]
    # 10% of $20 = $2 stake => 4 shares at price 0.5
    assert pos.size == 4.0


def test_drawdown_kill_switch_triggers(tmp_path):
    os.environ["REALISTIC_PAPER"] = "0"

    cfg = DemoFlashCrashConfig(
        coin="BTC",
        interval_minutes=5,
        size=5.0,
        max_drawdown_percent=30.0,
        demo_hours=24,
        start_bankroll=20.0,
        state_file=str(tmp_path / "demo_state.json"),
        resume=False,
        reset_state=True,
    )
    s = DemoFlashCrashStrategy(bot=DummyBot(), config=cfg)

    s.bankroll = 13.5  # 32.5% drawdown
    triggered, drawdown = s._drawdown_triggered()

    assert triggered is True
    assert drawdown >= 30.0


def test_realistic_paper_buy_respects_price_guards_and_liquidity(tmp_path):
    os.environ["REALISTIC_PAPER"] = "1"
    os.environ["NO_FILL_PROB"] = "0"
    os.environ["PARTIAL_FILL_MIN"] = "1"
    os.environ["PARTIAL_FILL_MAX"] = "1"
    os.environ["MIN_ENTRY_PRICE"] = "0.05"
    os.environ["MAX_ENTRY_PRICE"] = "0.95"
    os.environ["LIQUIDITY_USD_CAP"] = "1.0"

    s = _strategy(tmp_path, resume=False, reset_state=True, realistic=True)
    s.market.current_market = MarketInfo(
        slug="btc-updown-5m-1000",
        question="",
        end_date="",
        token_ids={"up": "tok-up", "down": "tok-down"},
        prices={},
        accepting_orders=True,
    )

    blocked = asyncio.run(s.execute_buy("up", 0.03))
    assert blocked is False

    ok = asyncio.run(s.execute_buy("up", 0.5))
    assert ok is True
    pos = s.positions.get_all_positions()[0]
    # Liquidity cap 1 USD near price 0.5 => max 2 shares filled
    assert pos.size <= 2.0
