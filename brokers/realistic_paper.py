"""Realistic paper execution model for demo trading."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _get_env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None else str(value)


@dataclass
class ExecResult:
    filled: bool
    filled_shares: float
    avg_price: float
    fee_usd: float
    reason: str = ""


class RealisticPaperBroker:
    """Paper broker with conservative execution realism."""

    def __init__(self):
        self.enabled = _get_env_int("REALISTIC_PAPER", 1) == 1

        self.stake_mode = _get_env_str("STAKE_MODE", "pct")
        self.stake_pct = _get_env_float("STAKE_PCT", 0.03)
        self.stake_fixed = _get_env_float("STAKE_FIXED_USD", 2.0)
        self.max_stake = _get_env_float("MAX_STAKE_USD", 5.0)

        self.min_entry = _get_env_float("MIN_ENTRY_PRICE", 0.05)
        self.max_entry = _get_env_float("MAX_ENTRY_PRICE", 0.95)

        self.taker_fee_bps = _get_env_float("TAKER_FEE_BPS", 60.0)
        self.slippage_bps = _get_env_float("SLIPPAGE_BPS", 80.0)

        self.no_fill_prob = _get_env_float("NO_FILL_PROB", 0.08)
        self.partial_fill_min = _get_env_float("PARTIAL_FILL_MIN", 0.35)
        self.partial_fill_max = _get_env_float("PARTIAL_FILL_MAX", 0.95)

        self.liq_usd_cap = _get_env_float("LIQUIDITY_USD_CAP", 40.0)

    def _calc_stake(self, bankroll: float) -> float:
        if self.stake_mode.lower() == "fixed":
            stake = self.stake_fixed
        else:
            stake = bankroll * self.stake_pct
        return max(0.0, min(stake, self.max_stake, bankroll))

    def _fee(self, notional_usd: float) -> float:
        return notional_usd * (self.taker_fee_bps / 10000.0)

    def simulate_buy(self, price: float, bankroll: float, preferred_stake: float | None = None) -> ExecResult:
        if not self.enabled:
            stake = max(min(preferred_stake or bankroll, bankroll), 0.0)
            if price <= 0 or stake <= 0:
                return ExecResult(False, 0.0, 0.0, 0.0, "blocked: stake<=0")
            return ExecResult(True, stake / price, price, 0.0, "filled")

        if price < self.min_entry:
            return ExecResult(False, 0.0, 0.0, 0.0, f"blocked: price<{self.min_entry}")
        if price > self.max_entry:
            return ExecResult(False, 0.0, 0.0, 0.0, f"blocked: price>{self.max_entry}")

        stake = preferred_stake if preferred_stake is not None else self._calc_stake(bankroll)
        stake = max(0.0, min(stake, bankroll, self.max_stake))
        if stake <= 0:
            return ExecResult(False, 0.0, 0.0, 0.0, "blocked: stake<=0")

        if random.random() < self.no_fill_prob:
            return ExecResult(False, 0.0, 0.0, 0.0, "no_fill")

        max_shares_by_liq = max(0.0, self.liq_usd_cap / max(price, 1e-9))
        desired_shares = stake / price
        shares = min(desired_shares, max_shares_by_liq)
        if shares <= 0:
            return ExecResult(False, 0.0, 0.0, 0.0, "blocked: liq_cap")

        fill_ratio = random.uniform(self.partial_fill_min, self.partial_fill_max)
        filled_shares = shares * fill_ratio

        slip = self.slippage_bps / 10000.0
        avg_price = price * (1.0 + slip)

        notional = filled_shares * avg_price
        fee = self._fee(notional)

        total_cost = notional + fee
        if total_cost > bankroll and total_cost > 0:
            scale = bankroll / total_cost
            filled_shares *= scale
            notional = filled_shares * avg_price
            fee = self._fee(notional)

        return ExecResult(True, filled_shares, avg_price, fee, "filled")

    def simulate_sell(self, price: float, shares: float) -> ExecResult:
        if shares <= 0:
            return ExecResult(False, 0.0, 0.0, 0.0, "blocked: shares<=0")

        if not self.enabled:
            return ExecResult(True, shares, price, 0.0, "filled")

        if random.random() < self.no_fill_prob:
            return ExecResult(False, 0.0, 0.0, 0.0, "no_fill")

        max_shares_by_liq = max(0.0, self.liq_usd_cap / max(price, 1e-9))
        shares_to_sell = min(shares, max_shares_by_liq)

        fill_ratio = random.uniform(self.partial_fill_min, self.partial_fill_max)
        filled_shares = shares_to_sell * fill_ratio
        if filled_shares <= 0:
            return ExecResult(False, 0.0, 0.0, 0.0, "blocked: liq_cap")

        slip = self.slippage_bps / 10000.0
        avg_price = price * (1.0 - slip)

        notional = filled_shares * avg_price
        fee = self._fee(notional)

        return ExecResult(True, filled_shares, avg_price, fee, "filled")
