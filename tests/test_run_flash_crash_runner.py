"""Tests for run_flash_crash runner compatibility helpers."""

import sys
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
