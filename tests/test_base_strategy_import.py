"""Regression test: importing BaseStrategy should not raise NameError on annotations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_base_strategy_imports_cleanly():
    from strategies.base import BaseStrategy, StrategyConfig  # noqa: F401

    assert BaseStrategy is not None
    assert StrategyConfig is not None
