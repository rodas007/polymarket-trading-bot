"""
Strategy Base Class - Foundation for Trading Strategies

Provides:
- Base class for all trading strategies
- Common lifecycle methods (start, stop, run)
- Integration with lib components (MarketManager, PriceTracker, PositionManager)
- Logging and status display utilities

Usage:
    from strategies.base import BaseStrategy, StrategyConfig

    class MyStrategy(BaseStrategy):
        async def on_book_update(self, snapshot):
            # Handle orderbook updates
            pass

        async def on_tick(self, prices):
            # Called each strategy tick
            pass
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, List

from lib.run_logger import TradeRunLogger

from lib.console import LogBuffer, log
from lib.market_manager import MarketManager, MarketInfo
from lib.price_tracker import PriceTracker
from lib.position_manager import Position, PositionManager
from src.bot import TradingBot
from src.websocket_client import OrderbookSnapshot


@dataclass
class StrategyConfig:
    """Base strategy configuration."""

    coin: str = "ETH"
    size: float = 5.0  # USDC size per trade
    max_positions: int = 1
    take_profit: float = 0.10
    stop_loss: float = 0.05

    # Market settings
    interval_minutes: int = 15
    market_check_interval: float = 30.0
    auto_switch_market: bool = True

    # Price tracking
    price_lookback_seconds: int = 10
    price_history_size: int = 100

    # Display settings
    update_interval: float = 0.1
    order_refresh_interval: float = 30.0  # Seconds between order refreshes

    # Run logging
    enable_run_log: bool = True
    run_log_dir: str = "logs/runs"
    run_log_snapshot_interval: float = 30.0

    # Risk controls
    size_percent: Optional[float] = None  # Percent of available bankroll per trade
    max_drawdown_percent: Optional[float] = None  # Kill-switch threshold from start bankroll


class BaseStrategy(ABC):
    """
    Base class for trading strategies.

    Provides common infrastructure:
    - MarketManager for WebSocket and market discovery
    - PriceTracker for price history
    - PositionManager for positions and TP/SL
    - Logging and status display
    """

    def __init__(self, bot: TradingBot, config: StrategyConfig):
        """
        Initialize base strategy.

        Args:
            bot: TradingBot instance for order execution
            config: Strategy configuration
        """
        self.bot = bot
        self.config = config

        # Core components
        self.market = MarketManager(
            coin=config.coin,
            market_check_interval=config.market_check_interval,
            auto_switch_market=config.auto_switch_market,
            interval_minutes=config.interval_minutes,
        )

        self.prices = PriceTracker(
            lookback_seconds=config.price_lookback_seconds,
            max_history=config.price_history_size,
        )

        self.positions = PositionManager(
            take_profit=config.take_profit,
            stop_loss=config.stop_loss,
            max_positions=config.max_positions,
        )

        # State
        self.running = False
        self._status_mode = False

        # Logging
        self._log_buffer = LogBuffer(max_size=5)

        # Open orders cache (refreshed in background)
        self._cached_orders: List[dict] = []
        self._last_order_refresh: float = 0
        self._order_refresh_task: Optional[asyncio.Task] = None

        # Run logger
        self._run_logger = TradeRunLogger(
            strategy_name=self.__class__.__name__,
            coin=config.coin,
            interval_minutes=config.interval_minutes,
            enabled=config.enable_run_log,
            log_dir=config.run_log_dir,
        )
        self._last_snapshot_log: float = 0.0

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.market.is_connected

    @property
    def current_market(self) -> Optional[MarketInfo]:
        """Get current market info."""
        return self.market.current_market

    @property
    def token_ids(self) -> Dict[str, str]:
        """Get current token IDs."""
        return self.market.token_ids

    @property
    def open_orders(self) -> List[dict]:
        """Get cached open orders."""
        return self._cached_orders

    def _refresh_orders_sync(self) -> List[dict]:
        """Refresh open orders synchronously (called via to_thread)."""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.bot.get_open_orders())
            finally:
                loop.close()
        except Exception:
            return []

    async def _do_order_refresh(self) -> None:
        """Background task to refresh orders without blocking."""
        try:
            orders = await asyncio.to_thread(self._refresh_orders_sync)
            self._cached_orders = orders
        except Exception:
            pass
        finally:
            self._order_refresh_task = None

    def _maybe_refresh_orders(self) -> None:
        """Schedule order refresh if interval has passed (fire-and-forget)."""
        now = time.time()
        if now - self._last_order_refresh > self.config.order_refresh_interval:
            # Don't start new refresh if one is already running
            if self._order_refresh_task is not None and not self._order_refresh_task.done():
                return
            self._last_order_refresh = now
            # Fire and forget - doesn't block main loop
            self._order_refresh_task = asyncio.create_task(self._do_order_refresh())

    def log(self, msg: str, level: str = "info") -> None:
        """
        Log a message.

        Args:
            msg: Message to log
            level: Log level (info, success, warning, error, trade)
        """
        if self._status_mode:
            self._log_buffer.add(msg, level)
        else:
            log(msg, level)

    async def start(self) -> bool:
        """
        Start the strategy.

        Returns:
            True if started successfully
        """
        self.running = True

        # Register callbacks on market manager
        @self.market.on_book_update
        async def handle_book(snapshot: OrderbookSnapshot):  # pyright: ignore[reportUnusedFunction]
            # Record price
            for side, token_id in self.token_ids.items():
                if token_id == snapshot.asset_id:
                    self.prices.record(side, snapshot.mid_price)
                    break

            # Delegate to subclass
            await self.on_book_update(snapshot)

        @self.market.on_market_change
        def handle_market_change(old_slug: str, new_slug: str):  # pyright: ignore[reportUnusedFunction]
            self.log(f"Market changed: {old_slug} -> {new_slug}", "warning")
            self.prices.clear()
            self.on_market_change(old_slug, new_slug)

        @self.market.on_connect
        def handle_connect():  # pyright: ignore[reportUnusedFunction]
            self.log("WebSocket connected", "success")
            self.on_connect()

        @self.market.on_disconnect
        def handle_disconnect():  # pyright: ignore[reportUnusedFunction]
            self.log("WebSocket disconnected", "warning")
            self.on_disconnect()

        # Start market manager
        if not await self.market.start():
            self.running = False
            return False

        # Wait for initial data
        if not await self.market.wait_for_data(timeout=5.0):
            self.log("Timeout waiting for market data", "warning")

        self._run_logger.event(
            "run_started",
            coin=self.config.coin,
            interval_minutes=self.config.interval_minutes,
            start_bankroll=self.get_start_bankroll(),
            log_path=self._run_logger.log_path,
        )
        if self._run_logger.log_path:
            self.log(f"Run log: {self._run_logger.log_path}", "info")

        return True

    def get_current_bankroll(self) -> Optional[float]:
        """Return current bankroll if strategy tracks one."""
        return None

    def get_start_bankroll(self) -> Optional[float]:
        """Return initial bankroll if strategy tracks one."""
        return None

    def get_available_bankroll(self) -> Optional[float]:
        """Return available bankroll (excluding reserves) if strategy tracks one."""
        return self.get_current_bankroll()

    def _log_run_snapshot(self, prices: Dict[str, float]) -> None:
        """Persist periodic run snapshot for later analysis."""
        now = time.time()
        if now - self._last_snapshot_log < self.config.run_log_snapshot_interval:
            return
        self._last_snapshot_log = now

        open_positions = self.positions.get_all_positions()
        winning_open = 0
        losing_open = 0
        for position in open_positions:
            current_price = prices.get(position.side, 0)
            if current_price <= 0:
                continue
            pnl = position.get_pnl(current_price)
            if pnl >= 0:
                winning_open += 1
            else:
                losing_open += 1

        stats = self.positions.get_stats()
        self._run_logger.event(
            "snapshot",
            bankroll=self.get_current_bankroll(),
            trades_opened=stats["trades_opened"],
            trades_closed=stats["trades_closed"],
            wins_closed=stats["winning_trades"],
            losses_closed=stats["losing_trades"],
            total_pnl=stats["total_pnl"],
            open_positions=len(open_positions),
            open_winning=winning_open,
            open_losing=losing_open,
            prices=prices,
        )

    def _resolve_stake_usd(self) -> float:
        """Resolve trade stake in USD based on fixed size or size_percent."""
        stake = float(self.config.size)
        available = self.get_available_bankroll()

        if self.config.size_percent is not None and self.config.size_percent > 0:
            if available is not None:
                stake = max(available * (self.config.size_percent / 100.0), 0.0)

        if available is not None:
            stake = min(stake, max(available, 0.0))

        return max(stake, 0.0)

    def _drawdown_triggered(self) -> tuple[bool, float]:
        """Check if max drawdown kill-switch should trigger."""
        if self.config.max_drawdown_percent is None or self.config.max_drawdown_percent <= 0:
            return (False, 0.0)

        start_bankroll = self.get_start_bankroll()
        current_bankroll = self.get_current_bankroll()
        if start_bankroll is None or current_bankroll is None or start_bankroll <= 0:
            return (False, 0.0)

        drawdown_pct = max((start_bankroll - current_bankroll) / start_bankroll * 100.0, 0.0)
        return (drawdown_pct >= self.config.max_drawdown_percent, drawdown_pct)

    async def _trigger_kill_switch(self, reason: str) -> None:
        """Stop trading, attempt cleanup, and close positions."""
        self.log(f"KILL SWITCH triggered: {reason}", "error")
        self._run_logger.event("kill_switch_triggered", reason=reason, bankroll=self.get_current_bankroll())

        try:
            result = await self.bot.cancel_all_orders()
            if result.success:
                self.log("Kill-switch: cancelled all open orders", "warning")
        except Exception:
            pass

        prices = self._get_current_prices()
        for position in list(self.positions.get_all_positions()):
            exit_price = prices.get(position.side, 0.0)
            if exit_price <= 0:
                exit_price = position.entry_price
            try:
                await self.execute_sell(position, exit_price)
            except Exception:
                pass

        self.running = False

    async def stop(self) -> None:
        """Stop the strategy."""
        self.running = False

        # Cancel order refresh task if running
        if self._order_refresh_task is not None:
            self._order_refresh_task.cancel()
            try:
                await self._order_refresh_task
            except asyncio.CancelledError:
                pass
            self._order_refresh_task = None

        await self.market.stop()

    async def run(self) -> None:
        """Main strategy loop."""
        try:
            if not await self.start():
                self.log("Failed to start strategy", "error")
                return

            self._status_mode = True

            while self.running:
                # Get current prices
                prices = self._get_current_prices()

                triggered, drawdown_pct = self._drawdown_triggered()
                if triggered:
                    await self._trigger_kill_switch(
                        f"drawdown {drawdown_pct:.2f}% >= {self.config.max_drawdown_percent:.2f}%"
                    )
                    break

                # Call tick handler
                await self.on_tick(prices)

                # Check position exits
                await self._check_exits(prices)

                # Refresh orders in background (fire-and-forget)
                self._maybe_refresh_orders()

                self._log_run_snapshot(prices)

                # Update display
                self.render_status(prices)

                await asyncio.sleep(self.config.update_interval)

        except KeyboardInterrupt:
            self.log("Strategy stopped by user")
        finally:
            await self.stop()
            self._print_summary()

    def _get_current_prices(self) -> Dict[str, float]:
        """Get current prices from market manager."""
        prices = {}
        for side in ["up", "down"]:
            price = self.market.get_mid_price(side)
            if price > 0:
                prices[side] = price
        return prices

    async def _check_exits(self, prices: Dict[str, float]) -> None:
        """Check and execute exits for all positions."""
        exits = self.positions.check_all_exits(prices)

        for position, exit_type, pnl in exits:
            if exit_type == "take_profit":
                self.log(
                    f"TAKE PROFIT: {position.side.upper()} PnL: +${pnl:.2f}",
                    "success"
                )
            elif exit_type == "stop_loss":
                self.log(
                    f"STOP LOSS: {position.side.upper()} PnL: ${pnl:.2f}",
                    "warning"
                )

            # Execute sell
            await self.execute_sell(position, prices.get(position.side, 0))

    async def execute_buy(self, side: str, current_price: float) -> bool:
        """
        Execute market buy order.

        Args:
            side: "up" or "down"
            current_price: Current market price

        Returns:
            True if order placed successfully
        """
        token_id = self.token_ids.get(side)
        if not token_id:
            self.log(f"No token ID for {side}", "error")
            return False

        stake_usd = self._resolve_stake_usd()
        if stake_usd <= 0:
            self.log("No bankroll available to open new position", "warning")
            return False

        size = stake_usd / current_price
        buy_price = min(current_price + 0.02, 0.99)

        self.log(
            f"BUY {side.upper()} @ {current_price:.4f} size={size:.2f} stake=${stake_usd:.2f}",
            "trade",
        )

        result = await self.bot.place_order(
            token_id=token_id,
            price=buy_price,
            size=size,
            side="BUY"
        )

        if result.success:
            self.log(f"Order placed: {result.order_id}", "success")
            position = self.positions.open_position(
                side=side,
                token_id=token_id,
                entry_price=current_price,
                size=size,
                order_id=result.order_id,
            )
            if position:
                self._run_logger.event(
                    "trade_opened",
                    side=side,
                    token_id=token_id,
                    entry_price=current_price,
                    size=size,
                    order_id=result.order_id,
                    bankroll=self.get_current_bankroll(),
                    stake_usd=stake_usd,
                )
            return True
        else:
            self.log(f"Order failed: {result.message}", "error")
            return False

    async def execute_sell(self, position: Position, current_price: float) -> bool:
        """
        Execute sell order to close position.

        Args:
            position: Position to close
            current_price: Current price

        Returns:
            True if order placed
        """
        sell_price = max(current_price - 0.02, 0.01)
        pnl = position.get_pnl(current_price)

        result = await self.bot.place_order(
            token_id=position.token_id,
            price=sell_price,
            size=position.size,
            side="SELL"
        )

        if result.success:
            self.log(f"Sell order: {result.order_id} PnL: ${pnl:+.2f}", "success")
            self.positions.close_position(position.id, realized_pnl=pnl)
            self._run_logger.event(
                "trade_closed",
                side=position.side,
                token_id=position.token_id,
                entry_price=position.entry_price,
                exit_price=current_price,
                size=position.size,
                pnl=pnl,
                result="win" if pnl >= 0 else "loss",
                entry_time=position.entry_time,
                hold_seconds=position.get_hold_time(),
                bankroll=self.get_current_bankroll(),
            )
            return True
        else:
            self.log(f"Sell failed: {result.message}", "error")
            return False

    def _print_summary(self) -> None:
        """Print session summary."""
        self._status_mode = False
        print()
        stats = self.positions.get_stats()
        self.log("Session Summary:")
        self.log(f"  Trades: {stats['trades_closed']}")
        self.log(f"  Total PnL: ${stats['total_pnl']:+.2f}")
        self.log(f"  Win rate: {stats['win_rate']:.1f}%")
        self._run_logger.event("run_finished", stats=stats, bankroll=self.get_current_bankroll())

    # Abstract methods to implement in subclasses

    @abstractmethod
    async def on_book_update(self, snapshot: OrderbookSnapshot) -> None:
        """
        Handle orderbook update.

        Called when new orderbook data is received.

        Args:
            snapshot: OrderbookSnapshot from WebSocket
        """
        pass

    @abstractmethod
    async def on_tick(self, prices: Dict[str, float]) -> None:
        """
        Handle strategy tick.

        Called on each iteration of the main loop.

        Args:
            prices: Current prices {side: price}
        """
        pass

    @abstractmethod
    def render_status(self, prices: Dict[str, float]) -> None:
        """
        Render status display.

        Called on each tick to update the display.

        Args:
            prices: Current prices
        """
        pass

    # Optional hooks (override as needed)

    def on_market_change(self, old_slug: str, new_slug: str) -> None:
        """Called when market changes."""
        pass

    def on_connect(self) -> None:
        """Called when WebSocket connects."""
        pass

    def on_disconnect(self) -> None:
        """Called when WebSocket disconnects."""
        pass
