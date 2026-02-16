#!/usr/bin/env python3
"""Flash Crash Strategy Runner."""

import argparse
import asyncio
import logging
import os
import sys
import time
import uuid
from pathlib import Path

logging.getLogger("src.websocket_client").setLevel(logging.WARNING)
logging.getLogger("src.bot").setLevel(logging.WARNING)

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.console import Colors
from src.bot import OrderResult, TradingBot
from src.config import Config
from strategies.flash_crash import (
    DemoFlashCrashConfig,
    DemoFlashCrashStrategy,
    FlashCrashConfig,
    FlashCrashStrategy,
)


class PaperTradingBot:
    """Minimal bot interface for demo/paper mode."""

    def is_initialized(self) -> bool:
        return True

    async def place_order(self, token_id: str, price: float, size: float, side: str) -> OrderResult:
        return OrderResult(
            success=True,
            order_id=f"paper-{side.lower()}-{uuid.uuid4().hex[:8]}",
            status="filled",
            message="paper order simulated",
            data={"token_id": token_id, "price": price, "size": size, "side": side},
        )

    async def get_open_orders(self):
        return []

    async def cancel_all_orders(self) -> OrderResult:
        return OrderResult(success=True, message="paper cancel all simulated")


def parse_args():
    parser = argparse.ArgumentParser(description="Flash Crash Strategy for Polymarket 5m/15m markets")
    parser.add_argument("--coin", type=str, default="ETH", choices=["BTC", "ETH", "SOL", "XRP"], help="Coin to trade")
    parser.add_argument("--interval", type=int, default=15, choices=[5, 15], help="Market interval in minutes")
    parser.add_argument("--size", type=float, default=5.0, help="Trade size in USDC")
    parser.add_argument("--drop", type=float, default=0.30, help="Drop threshold as absolute probability change")
    parser.add_argument("--lookback", type=int, default=10, help="Lookback window in seconds")
    parser.add_argument("--take-profit", type=float, default=0.10, help="Take profit in dollars")
    parser.add_argument("--stop-loss", type=float, default=0.05, help="Stop loss in dollars")
    parser.add_argument("--size-percent", type=float, default=None, help="Position size as %% of available bankroll")
    parser.add_argument("--max-drawdown", type=float, default=None, help="Kill-switch max drawdown %% from start bankroll")

    parser.add_argument("--demo", action="store_true", help="Run in paper/demo mode (no real orders)")
    parser.add_argument("--hours", type=float, default=24.0, help="Demo duration in hours (default: 24)")
    parser.add_argument("--start-bankroll", type=float, default=20.0, help="Initial demo bankroll in USD")
    parser.add_argument("--state-file", type=str, default="flash_crash_demo_state.json", help="Demo state file")
    parser.add_argument("--reset-state", action="store_true", help="Delete saved demo state before starting")
    parser.add_argument("--no-resume", action="store_true", help="Do not resume demo state if state file exists")
    parser.add_argument("--reconnect-delay", type=int, default=10, help="Seconds before restarting after fatal error")

    parser.add_argument("--run-log-dir", type=str, default="logs/runs", help="Directory to store per-run trade logs")
    parser.add_argument("--no-run-log", action="store_true", help="Disable per-run trade logging")

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def build_real_bot() -> TradingBot:
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    safe_address = os.environ.get("POLY_SAFE_ADDRESS")

    if not private_key or not safe_address:
        print(f"{Colors.RED}Error: POLY_PRIVATE_KEY and POLY_SAFE_ADDRESS must be set{Colors.RESET}")
        print("Set them in .env file or export as environment variables")
        sys.exit(1)

    config = Config.from_env()
    bot = TradingBot(config=config, private_key=private_key)
    if not bot.is_initialized():
        print(f"{Colors.RED}Error: Failed to initialize bot{Colors.RESET}")
        sys.exit(1)
    return bot


def print_config(args):
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    mode = "DEMO" if args.demo else "LIVE"
    print(f"{Colors.BOLD}  Flash Crash Strategy [{mode}] - {args.coin.upper()} {args.interval}m{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")

    print("Configuration:")
    print(f"  Coin: {args.coin.upper()}")
    print(f"  Interval: {args.interval}m")
    print(f"  Size: ${args.size:.2f}")
    print(f"  Drop threshold: {args.drop:.2f}")
    print(f"  Lookback: {args.lookback}s")
    print(f"  Take profit: +${args.take_profit:.2f}")
    print(f"  Stop loss: -${args.stop_loss:.2f}")
    if args.size_percent is not None:
        print(f"  Size percent: {args.size_percent:.2f}% of available bankroll")
    if args.max_drawdown is not None:
        print(f"  Kill-switch drawdown: {args.max_drawdown:.2f}%")
    if args.demo:
        print(f"  Demo hours: {args.hours:.2f}h")
        print(f"  Start bankroll: ${args.start_bankroll:.2f}")
        print(f"  Resume state: {not args.no_resume}")
        print(f"  State file: {args.state_file}")
    print(f"  Run log enabled: {not args.no_run_log}")
    print(f"  Run log dir: {args.run_log_dir}")
    print()


def run_with_supervisor(strategy_factory, reconnect_delay: int):
    while True:
        try:
            strategy = strategy_factory()
            asyncio.run(strategy.run())
            break
        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"\n{Colors.RED}Fatal strategy error: {e}{Colors.RESET}")
            print(f"Restarting in {reconnect_delay}s...")
            time.sleep(max(1, reconnect_delay))


def main():
    args = parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("src.websocket_client").setLevel(logging.DEBUG)

    print_config(args)

    if args.demo:
        bot = PaperTradingBot()

        demo_cfg = DemoFlashCrashConfig(
            coin=args.coin.upper(),
            interval_minutes=args.interval,
            size=args.size,
            drop_threshold=args.drop,
            price_lookback_seconds=args.lookback,
            take_profit=args.take_profit,
            stop_loss=args.stop_loss,
            size_percent=args.size_percent,
            max_drawdown_percent=args.max_drawdown,
            demo_hours=args.hours,
            start_bankroll=args.start_bankroll,
            state_file=args.state_file,
            resume=not args.no_resume,
            reset_state=args.reset_state,
            enable_run_log=not args.no_run_log,
            run_log_dir=args.run_log_dir,
        )

        run_with_supervisor(
            strategy_factory=lambda: DemoFlashCrashStrategy(bot=bot, config=demo_cfg),
            reconnect_delay=args.reconnect_delay,
        )
        return

    bot = build_real_bot()
    cfg = FlashCrashConfig(
        coin=args.coin.upper(),
        interval_minutes=args.interval,
        size=args.size,
        drop_threshold=args.drop,
        price_lookback_seconds=args.lookback,
        take_profit=args.take_profit,
        stop_loss=args.stop_loss,
        size_percent=args.size_percent,
        max_drawdown_percent=args.max_drawdown,
        enable_run_log=not args.no_run_log,
        run_log_dir=args.run_log_dir,
    )

    run_with_supervisor(
        strategy_factory=lambda: FlashCrashStrategy(bot=bot, config=cfg),
        reconnect_delay=args.reconnect_delay,
    )


if __name__ == "__main__":
    main()
