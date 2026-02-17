"""Tests for run_flash_crash runner compatibility helpers."""

import sys
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.run_flash_crash import build_config


class LegacyConfig:
    def __init__(self, coin: str, interval_minutes: int):
        self.coin = coin
        self.interval_minutes = interval_minutes


class ModernConfig:
    def __init__(self, coin: str, interval_minutes: int, size_percent=None):
        self.coin = coin
        self.interval_minutes = interval_minutes
        self.size_percent = size_percent


def test_build_config_drops_unsupported_kwargs_for_legacy_config():
    cfg = build_config(
        LegacyConfig,
        coin="BTC",
        interval_minutes=5,
        size_percent=5.0,
        max_drawdown_percent=30.0,
    )

    assert cfg.coin == "BTC"
    assert cfg.interval_minutes == 5


def test_build_config_passes_supported_kwargs_for_modern_config():
    cfg = build_config(
        ModernConfig,
        coin="ETH",
        interval_minutes=15,
        size_percent=3.0,
    )

    assert cfg.coin == "ETH"
    assert cfg.interval_minutes == 15
    assert cfg.size_percent == 3.0


def test_load_strategy_classes_prints_helpful_message_on_syntax_error(monkeypatch, capsys):
    from apps import run_flash_crash

    def boom(_name):
        raise SyntaxError("( was never closed", ("strategies/flash_crash.py", 438, 0, "self._run_logger.event("))

    monkeypatch.setattr(importlib, "import_module", boom)

    try:
        run_flash_crash.load_strategy_classes()
    except SystemExit as exc:
        assert exc.code == 1

    out = capsys.readouterr().out
    assert "Syntax error in strategies/flash_crash.py" in out
    assert "merge conflict markers" in out
