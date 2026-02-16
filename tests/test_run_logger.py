"""Tests for per-run structured logging."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.run_logger import TradeRunLogger


def test_trade_run_logger_writes_jsonl_events(tmp_path):
    logger = TradeRunLogger(
        strategy_name="DemoFlashCrashStrategy",
        coin="BTC",
        interval_minutes=5,
        enabled=True,
        log_dir=str(tmp_path),
    )

    assert logger.log_path is not None
    logger.event("run_started", start_bankroll=20.0)
    logger.event("trade_opened", side="up", entry_price=0.41, size=10)

    log_path = Path(logger.log_path)
    assert log_path.exists()

    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in rows] == ["run_started", "trade_opened"]
    assert rows[0]["start_bankroll"] == 20.0
    assert rows[1]["entry_price"] == 0.41
    assert isinstance(rows[1]["elapsed_s"], float)


def test_trade_run_logger_can_be_disabled(tmp_path):
    logger = TradeRunLogger(
        strategy_name="DemoFlashCrashStrategy",
        coin="BTC",
        interval_minutes=5,
        enabled=False,
        log_dir=str(tmp_path),
    )

    logger.event("run_started")
    assert logger.log_path is None
    assert list(tmp_path.iterdir()) == []
