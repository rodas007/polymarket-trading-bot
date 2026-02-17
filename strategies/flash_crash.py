"""
Flash Crash Strategy - Volatility Trading for 5m/15m Markets

This strategy monitors short-duration Up/Down markets for sudden probability drops
and executes trades when probability crashes by a threshold within a lookback window.
"""

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from brokers import RealisticPaperBroker
from lib.console import Colors, format_countdown
from lib.position_manager import Position
from strategies.base import BaseStrategy, StrategyConfig
from src.bot import TradingBot
from src.websocket_client import OrderbookSnapshot


@dataclass
class FlashCrashConfig(StrategyConfig):
    """Flash crash strategy configuration."""

    drop_threshold: float = 0.30  # Absolute probability drop


@dataclass
class DemoFlashCrashConfig(FlashCrashConfig):
    """Paper/demo mode configuration persisted across restarts."""

    demo_hours: float = 24.0
    start_bankroll: float = 20.0
    state_file: str = "flash_crash_demo_state.json"
    resume: bool = True
    reset_state: bool = False


class FlashCrashStrategy(BaseStrategy):
    """Flash crash trading strategy."""

    def __init__(self, bot: TradingBot, config: FlashCrashConfig):
        super().__init__(bot, config)
        self.flash_config = config
        self.prices.drop_threshold = config.drop_threshold

    async def on_book_update(self, snapshot: OrderbookSnapshot) -> None:
        pass

    async def on_tick(self, prices: Dict[str, float]) -> None:
        if not self.positions.can_open_position:
            return

        event = self.prices.detect_flash_crash()
        if event:
            self.log(
                f"FLASH CRASH: {event.side.upper()} "
                f"drop {event.drop:.2f} ({event.old_price:.2f} -> {event.new_price:.2f})",
                "trade",
            )
            current_price = prices.get(event.side, 0)
            if current_price > 0:
                await self.execute_buy(event.side, current_price)

    def render_status(self, prices: Dict[str, float]) -> None:
        lines = []

        ws_status = f"{Colors.GREEN}WS{Colors.RESET}" if self.is_connected else f"{Colors.RED}REST{Colors.RESET}"
        countdown = self._get_countdown_str()
        stats = self.positions.get_stats()

        bankroll_text = ""
        if hasattr(self, "bankroll"):
            bankroll_text = f" | Bank: ${getattr(self, 'bankroll'):.2f}"

        lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
        lines.append(
            f"{Colors.CYAN}[{self.config.coin}]{Colors.RESET} [{ws_status}] "
            f"Ends: {countdown}{bankroll_text} | Trades: {stats['trades_closed']} | PnL: ${stats['total_pnl']:+.2f}"
        )
        lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")

        up_ob = self.market.get_orderbook("up")
        down_ob = self.market.get_orderbook("down")

        lines.append(f"{Colors.GREEN}{'UP':^39}{Colors.RESET}|{Colors.RED}{'DOWN':^39}{Colors.RESET}")
        lines.append(f"{'Bid':>9} {'Size':>9} | {'Ask':>9} {'Size':>9}|{'Bid':>9} {'Size':>9} | {'Ask':>9} {'Size':>9}")
        lines.append("-" * 80)

        up_bids = up_ob.bids[:5] if up_ob else []
        up_asks = up_ob.asks[:5] if up_ob else []
        down_bids = down_ob.bids[:5] if down_ob else []
        down_asks = down_ob.asks[:5] if down_ob else []

        for i in range(5):
            up_bid = f"{up_bids[i].price:>9.4f} {up_bids[i].size:>9.1f}" if i < len(up_bids) else f"{'--':>9} {'--':>9}"
            up_ask = f"{up_asks[i].price:>9.4f} {up_asks[i].size:>9.1f}" if i < len(up_asks) else f"{'--':>9} {'--':>9}"
            down_bid = f"{down_bids[i].price:>9.4f} {down_bids[i].size:>9.1f}" if i < len(down_bids) else f"{'--':>9} {'--':>9}"
            down_ask = f"{down_asks[i].price:>9.4f} {down_asks[i].size:>9.1f}" if i < len(down_asks) else f"{'--':>9} {'--':>9}"
            lines.append(f"{up_bid} | {up_ask}|{down_bid} | {down_ask}")

        lines.append("-" * 80)

        up_mid = up_ob.mid_price if up_ob else prices.get("up", 0)
        down_mid = down_ob.mid_price if down_ob else prices.get("down", 0)
        up_spread = self.market.get_spread("up")
        down_spread = self.market.get_spread("down")

        lines.append(
            f"Mid: {Colors.GREEN}{up_mid:.4f}{Colors.RESET}  Spread: {up_spread:.4f}           |"
            f"Mid: {Colors.RED}{down_mid:.4f}{Colors.RESET}  Spread: {down_spread:.4f}"
        )

        up_history = self.prices.get_history_count("up")
        down_history = self.prices.get_history_count("down")
        lines.append(
            f"History: UP={up_history}/100 DOWN={down_history}/100 | "
            f"Drop threshold: {self.flash_config.drop_threshold:.2f} in {self.config.price_lookback_seconds}s"
        )

        lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")

        lines.append(f"{Colors.BOLD}Open Orders:{Colors.RESET}")
        if self.open_orders:
            for order in self.open_orders[:5]:
                side = order.get("side", "?")
                price = float(order.get("price", 0))
                size = float(order.get("original_size", order.get("size", 0)))
                filled = float(order.get("size_matched", 0))
                order_id = order.get("id", "")[:8]
                token = order.get("asset_id", "")
                token_side = "UP" if token == self.token_ids.get("up") else "DOWN" if token == self.token_ids.get("down") else "?"
                color = Colors.GREEN if side == "BUY" else Colors.RED
                lines.append(f"  {color}{side:4}{Colors.RESET} {token_side:4} @ {price:.4f} Size: {size:.1f} Filled: {filled:.1f} ID: {order_id}...")
        else:
            lines.append(f"  {Colors.CYAN}(no open orders){Colors.RESET}")

        lines.append(f"{Colors.BOLD}Positions:{Colors.RESET}")
        all_positions = self.positions.get_all_positions()
        if all_positions:
            for pos in all_positions:
                current = prices.get(pos.side, 0)
                pnl = pos.get_pnl(current)
                pnl_pct = pos.get_pnl_percent(current)
                hold_time = pos.get_hold_time()
                color = Colors.GREEN if pnl >= 0 else Colors.RED

                lines.append(
                    f"  {Colors.BOLD}{pos.side.upper():4}{Colors.RESET} "
                    f"Entry: {pos.entry_price:.4f} | Current: {current:.4f} | "
                    f"Size: ${pos.size:.2f} | PnL: {color}${pnl:+.2f} ({pnl_pct:+.1f}%){Colors.RESET} | "
                    f"Hold: {hold_time:.0f}s"
                )
                lines.append(
                    f"       TP: {pos.take_profit_price:.4f} (+${self.config.take_profit:.2f}) | "
                    f"SL: {pos.stop_loss_price:.4f} (-${self.config.stop_loss:.2f})"
                )
        else:
            lines.append(f"  {Colors.CYAN}(no open positions){Colors.RESET}")

        if self._log_buffer.messages:
            lines.append("-" * 80)
            lines.append(f"{Colors.BOLD}Recent Events:{Colors.RESET}")
            for msg in self._log_buffer.get_messages():
                lines.append(f"  {msg}")

        output = "\033[H\033[J" + "\n".join(lines)
        print(output, flush=True)

    def _get_countdown_str(self) -> str:
        market = self.current_market
        if not market:
            return "--:--"

        mins, secs = market.get_countdown()
        return format_countdown(mins, secs)

    def on_market_change(self, old_slug: str, new_slug: str) -> None:
        self.prices.clear()


class DemoFlashCrashStrategy(FlashCrashStrategy):
    """Paper mode with persisted state and resumable 24h demo sessions."""

    def __init__(self, bot: TradingBot, config: DemoFlashCrashConfig):
        self.demo_config = config
        self.bankroll = float(config.start_bankroll)
        self.start_bankroll = float(config.start_bankroll)
        self.run_end_ts = time.time() + config.demo_hours * 3600
        self.paper_broker = RealisticPaperBroker()
        super().__init__(bot, config)

        if self.demo_config.reset_state and os.path.exists(self.demo_config.state_file):
            try:
                os.remove(self.demo_config.state_file)
            except Exception:
                pass

        self._load_state_if_needed()
        self._save_state()

    def _available_bankroll(self) -> float:
        if self.paper_broker.enabled:
            # In realistic mode we keep cash accounting directly in bankroll.
            return max(self.bankroll, 0.0)

        reserved = 0.0
        for pos in self.positions.get_all_positions():
            reserved += pos.entry_price * pos.size
        return max(self.bankroll - reserved, 0.0)

    def _save_state(self) -> None:
        data: Dict[str, Any] = {
            "bankroll": self.bankroll,
            "start_bankroll": self.start_bankroll,
            "run_end_ts": self.run_end_ts,
            "stats": {
                "trades_opened": self.positions.trades_opened,
                "trades_closed": self.positions.trades_closed,
                "total_pnl": self.positions.total_pnl,
                "winning_trades": self.positions.winning_trades,
                "losing_trades": self.positions.losing_trades,
            },
            "positions": [
                {
                    "id": p.id,
                    "side": p.side,
                    "token_id": p.token_id,
                    "entry_price": p.entry_price,
                    "size": p.size,
                    "entry_time": p.entry_time,
                    "order_id": p.order_id,
                }
                for p in self.positions.get_all_positions()
            ],
        }

        try:
            tmp = self.demo_config.state_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.demo_config.state_file)
        except Exception as exc:
            self.log(f"State save failed: {exc}", "warning")

    def _load_state_if_needed(self) -> None:
        if not self.demo_config.resume:
            return
        if not os.path.exists(self.demo_config.state_file):
            return

        try:
            with open(self.demo_config.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            self.log(f"State load failed: {exc}", "warning")
            return

        self.bankroll = float(data.get("bankroll", self.bankroll))
        self.start_bankroll = float(data.get("start_bankroll", self.start_bankroll))

        run_end = float(data.get("run_end_ts", 0.0))
        if run_end > time.time():
            self.run_end_ts = run_end

        stats = data.get("stats", {})
        self.positions.trades_opened = int(stats.get("trades_opened", 0))
        self.positions.trades_closed = int(stats.get("trades_closed", 0))
        self.positions.total_pnl = float(stats.get("total_pnl", 0.0))
        self.positions.winning_trades = int(stats.get("winning_trades", 0))
        self.positions.losing_trades = int(stats.get("losing_trades", 0))

        self.positions.clear()
        restored = 0
        for raw in data.get("positions", []):
            pos = Position(
                id=str(raw.get("id", "")) or f"restored-{restored}",
                side=str(raw.get("side", "up")),
                token_id=str(raw.get("token_id", "")),
                entry_price=float(raw.get("entry_price", 0.0)),
                size=float(raw.get("size", 0.0)),
                entry_time=float(raw.get("entry_time", time.time())),
                order_id=raw.get("order_id"),
                take_profit_delta=self.positions.take_profit,
                stop_loss_delta=self.positions.stop_loss,
            )
            if pos.size > 0 and pos.entry_price > 0:
                self.positions._positions[pos.id] = pos
                self.positions._positions_by_side[pos.side] = pos.id
                restored += 1

        self.log(
            f"Demo state loaded: bank=${self.bankroll:.2f}, restored_positions={restored}, "
            f"remaining={(self.run_end_ts - time.time())/3600:.2f}h",
            "warning",
        )

    def get_current_bankroll(self) -> Optional[float]:
        return self.bankroll

    def get_start_bankroll(self) -> Optional[float]:
        return self.start_bankroll

    def get_available_bankroll(self) -> Optional[float]:
        return self._available_bankroll()

    async def on_tick(self, prices: Dict[str, float]) -> None:
        if time.time() >= self.run_end_ts:
            self.log("Demo window reached (24h). Stopping.", "success")
            self.running = False
            self._save_state()
            return

        await super().on_tick(prices)
        self._save_state()

    async def execute_buy(self, side: str, current_price: float) -> bool:
        token_id = self.token_ids.get(side)
        if not token_id:
            self.log(f"No token ID for {side}", "error")
            return False

        available = self._available_bankroll()
        stake = self._resolve_stake_usd()
        if stake <= 0:
            self.log("No available bankroll to open new paper position", "warning")
            return False

        result = self.paper_broker.simulate_buy(
            price=current_price,
            bankroll=available,
            preferred_stake=stake,
        )
        if not result.filled or result.filled_shares <= 0:
            self.log(f"PAPER BUY skipped ({result.reason})", "warning")
            self._run_logger.event(
                "trade_open_skipped",
                side=side,
                token_id=token_id,
                price=current_price,
                reason=result.reason,
                bankroll=self.bankroll,
                mode="paper",
            )
            return False

        size = result.filled_shares
        fee_per_share = result.fee_usd / size if size > 0 else 0.0
        entry_price_effective = result.avg_price + fee_per_share

        # Realistic mode uses cash accounting; legacy mode keeps PnL accounting.
        if self.paper_broker.enabled:
            self.bankroll -= (size * result.avg_price + result.fee_usd)

        self.log(
            f"PAPER BUY {side.upper()} @ {entry_price_effective:.4f} shares={size:.2f} "
            f"stake=${size * entry_price_effective:.2f}",
            "trade",
        )

        pos = self.positions.open_position(
            side=side,
            token_id=token_id,
            entry_price=entry_price_effective,
            size=size,
            order_id=f"paper-{int(time.time())}",
        )
        if not pos:
            if self.paper_broker.enabled:
                self.bankroll += (size * result.avg_price + result.fee_usd)
            return False

        self._run_logger.event(
            "trade_opened",
            side=side,
            token_id=token_id,
            entry_price=entry_price_effective,
            raw_entry_price=current_price,
            size=size,
            order_id=pos.order_id,
            fee_usd=result.fee_usd,
            bankroll=self.bankroll,
            mode="paper",
        )

        self._save_state()
        return True

    async def execute_sell(self, position: Position, current_price: float) -> bool:
        result = self.paper_broker.simulate_sell(price=current_price, shares=position.size)
        if not result.filled or result.filled_shares <= 0:
            self.log(f"PAPER SELL skipped ({result.reason})", "warning")
            self._run_logger.event(
                "trade_close_skipped",
                side=position.side,
                token_id=position.token_id,
                price=current_price,
                reason=result.reason,
                bankroll=self.bankroll,
                mode="paper",
            )
            return False

        sold_shares = min(result.filled_shares, position.size)
        fee_per_share = result.fee_usd / sold_shares if sold_shares > 0 else 0.0
        exit_price_effective = result.avg_price - fee_per_share
        pnl = (exit_price_effective - position.entry_price) * sold_shares

        if self.paper_broker.enabled:
            self.bankroll += sold_shares * result.avg_price - result.fee_usd
        else:
            self.bankroll += pnl

        partial_close = sold_shares < position.size

        if partial_close:
            position.size -= sold_shares
            self.positions.total_pnl += pnl
            if pnl >= 0:
                self.positions.winning_trades += 1
            else:
                self.positions.losing_trades += 1
            self.log(
                f"PAPER PARTIAL SELL {position.side.upper()} @ {exit_price_effective:.4f} "
                f"shares={sold_shares:.2f} PnL: ${pnl:+.2f}",
                "warning",
            )
            event_type = "trade_partially_closed"
        else:
            self.positions.close_position(position.id, realized_pnl=pnl)
            self.log(f"PAPER SELL {position.side.upper()} @ {exit_price_effective:.4f} PnL: ${pnl:+.2f}", "success")
            event_type = "trade_closed"

        self._run_logger.event(
            event_type,
            side=position.side,
            token_id=position.token_id,
            entry_price=position.entry_price,
            exit_price=exit_price_effective,
            raw_exit_price=current_price,
            size=sold_shares,
            remaining_size=position.size if partial_close else 0.0,
            pnl=pnl,
            result="win" if pnl >= 0 else "loss",
            entry_time=position.entry_time,
            hold_seconds=position.get_hold_time(),
            fee_usd=result.fee_usd,
            bankroll=self.bankroll,
            mode="paper",
        )
        self._save_state()
        return True

    async def stop(self) -> None:
        self._save_state()
        await super().stop()

    def _print_summary(self) -> None:
        super()._print_summary()
        elapsed = max(self.run_end_ts - time.time(), 0)
        self.log(
            f"Demo bankroll: start=${self.start_bankroll:.2f} now=${self.bankroll:.2f} "
            f"remaining={elapsed/3600:.2f}h state={self.demo_config.state_file}"
        )
