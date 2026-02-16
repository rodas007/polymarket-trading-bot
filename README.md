# Polymarket Trading Bot

English | [简体中文](README_CN.md)

A beginner-friendly Python trading bot for Polymarket with gasless transactions and real-time WebSocket data.

## Features

- **Simple API**: Just a few lines of code to start trading
- **Gasless Transactions**: No gas fees with Builder Program credentials
- **Real-time WebSocket**: Live orderbook updates via WebSocket
- **5m + 15m Markets**: Built-in support for BTC/ETH/SOL/XRP 5-minute and 15-minute Up/Down markets
- **Flash Crash Strategy**: Pre-built strategy for volatility trading
- **Terminal UI**: Real-time orderbook display with in-place updates
- **Secure Key Storage**: Private keys encrypted with PBKDF2 + Fernet
- **Fully Tested**: 89 unit tests covering all functionality

## Quick Start (5 Minutes)

### Step 1: Install

```bash
git clone https://github.com/your-username/polymarket-trading-bot.git
cd polymarket-trading-bot
pip install -r requirements.txt
```

### Step 2: Configure

```bash
# Set your credentials
export POLY_PRIVATE_KEY=your_metamask_private_key
export POLY_SAFE_ADDRESS=0xYourPolymarketSafeAddress
```

> **Where to find your Safe address?** Go to [polymarket.com/settings](https://polymarket.com/settings) and copy your wallet address.

### Step 3: Run

```bash
# Run the quickstart example
python examples/quickstart.py

# Or run the Flash Crash Strategy
python apps/run_flash_crash.py --coin BTC --interval 15
```

That's it! You're ready to trade.

## Windows Setup & Run (PowerShell)

Use these exact steps on Windows:

```powershell
# 1) Clone and enter repo
cd C:\
git clone https://github.com/your-username/polymarket-trading-bot.git
cd .\polymarket-trading-bot

# 2) Create virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3) Install dependencies
py -m pip install --upgrade pip
py -m pip install -r requirements.txt

# 4) Configure credentials in current terminal
$env:POLY_PRIVATE_KEY = "0xYOUR_PRIVATE_KEY"
$env:POLY_SAFE_ADDRESS = "0xYOUR_SAFE_ADDRESS"

# 5) Run strategy (examples)
# 15m BTC (live)
py apps\run_flash_crash.py --coin BTC --interval 15

# 5m ETH (demo 24h, bank 20 USD, resume state)
py apps\run_flash_crash.py --coin ETH --interval 5 --demo --hours 24 --start-bankroll 20 --state-file .\demo_state.json
```

If PowerShell blocks venv activation, run once as admin:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Trading Strategies

### Flash Crash Strategy (now supports 5m and 15m)

You can run the existing strategy code with either 15-minute markets (default) or 5-minute markets (BTC/ETH/SOL/XRP).

```bash
# 15m market (default)
python apps/run_flash_crash.py --coin BTC --interval 15

# 5m market
python apps/run_flash_crash.py --coin ETH --interval 5
```

Windows (PowerShell):

```powershell
py -m pip install -r requirements.txt
py apps\run_flash_crash.py --coin ETH --interval 5 --size 5 --drop 0.30
```

### Flash Crash Strategy

Monitors 5m/15m Up/Down markets for sudden probability drops and executes trades automatically.

```bash
# Run with default settings (15m)
python apps/run_flash_crash.py --coin BTC --interval 15

# Run ETH 5m
python apps/run_flash_crash.py --coin ETH --interval 5 --drop 0.25 --size 10

# Available options
--coin      BTC, ETH, SOL, XRP (default: ETH)
--interval  5 or 15 (default: 15)
--drop      Drop threshold as absolute change (default: 0.30)
--size      Trade size in USDC (default: 5.0)
--lookback  Detection window in seconds (default: 10)
--take-profit  TP in dollars (default: 0.10)
--stop-loss    SL in dollars (default: 0.05)
--size-percent position size as % of available bankroll (e.g. 5 = 5%)
--max-drawdown kill-switch % drawdown from start bankroll
--demo         run paper mode (no real orders)
--hours        demo duration in hours (default: 24)
--start-bankroll demo starting bankroll (default: 20)
--state-file   demo state path for resume
--reset-state  clear previous demo state
--no-resume    start demo without loading previous state
--run-log-dir  directory for per-run JSONL trade logs (default: logs/runs)
--no-run-log   disable per-run JSONL trade logs
```

### 24h Demo Mode (paper trading)

For 24-hour evaluation with automatic resume and reconnect:

```bash
python apps/run_flash_crash.py --coin ETH --interval 5 --demo --hours 24 --start-bankroll 20 --state-file demo_state.json
```

What this does:
- Starts demo with a virtual bankroll of **$20**.
- Persists state to disk so if process stops/restarts, bankroll and open demo positions are restored.
- Uses supervisor restart loop on fatal errors (`--reconnect-delay`, default 10s).
- Keeps the same 24h window using saved end timestamp, so you can evaluate performance for the full trial period.
- Creates a run log file per launch with timestamps, entry/exit prices, winners/losers, and bankroll snapshots over time.


### Safer 5m setup example

```bash
python apps/run_flash_crash.py --coin BTC --interval 5 --demo \
  --hours 24 --start-bankroll 20 --state-file demo_state.json --reset-state \
  --size-percent 5 --max-drawdown 30 --drop 0.22 --lookback 6 --take-profit 0.20 --stop-loss 0.05
```

- `--size-percent 5` risks ~5% of available bankroll per entry.
- `--max-drawdown 30` stops the strategy if bankroll drawdown reaches 30% from the session start.


### Realistic Paper Mode (conservative execution)

Demo mode now supports a realistic execution model (enabled by default) with:
- slippage and taker fees
- no-fill and partial-fill simulation
- liquidity cap near price
- entry price guards to avoid ultra-illiquid fills

You can tune it with environment variables:

```bash
REALISTIC_PAPER=1
STAKE_MODE=pct
STAKE_PCT=0.03
STAKE_FIXED_USD=2.0
MAX_STAKE_USD=5.0
MIN_ENTRY_PRICE=0.05
MAX_ENTRY_PRICE=0.95
TAKER_FEE_BPS=60
SLIPPAGE_BPS=80
NO_FILL_PROB=0.08
PARTIAL_FILL_MIN=0.35
PARTIAL_FILL_MAX=0.95
LIQUIDITY_USD_CAP=40.0
```

If you want legacy paper fills (no realism), set `REALISTIC_PAPER=0`.

**Strategy Logic:**
1. Auto-discover current market for selected interval (5m/15m)
2. Monitor orderbook prices via WebSocket in real-time
3. When probability drops by configured threshold, buy the crashed side
4. Exit at take-profit or stop-loss

## Strategy Development Guide

- See `docs/strategy_guide.md` for a step-by-step tutorial and templates.

### Real-time Orderbook TUI

View live orderbook data in a beautiful terminal interface:

```bash
python apps/orderbook_tui.py --coin BTC --levels 5
```

## Code Examples

### Simplest Example

```python
from src import create_bot_from_env
import asyncio

async def main():
    # Create bot from environment variables
    bot = create_bot_from_env()

    # Get your open orders
    orders = await bot.get_open_orders()
    print(f"You have {len(orders)} open orders")

asyncio.run(main())
```

### Place an Order

```python
from src import TradingBot, Config
import asyncio

async def trade():
    # Create configuration
    config = Config(safe_address="0xYourSafeAddress")

    # Initialize bot with your private key
    bot = TradingBot(config=config, private_key="0xYourPrivateKey")

    # Place a buy order
    result = await bot.place_order(
        token_id="12345...",   # Market token ID
        price=0.65,            # Price (0.65 = 65% probability)
        size=10.0,             # Number of shares
        side="BUY"             # or "SELL"
    )

    if result.success:
        print(f"Order placed! ID: {result.order_id}")
    else:
        print(f"Order failed: {result.message}")

asyncio.run(trade())
```

### Real-time WebSocket Data

```python
from src.websocket_client import MarketWebSocket, OrderbookSnapshot
import asyncio

async def main():
    ws = MarketWebSocket()

    @ws.on_book
    async def on_book_update(snapshot: OrderbookSnapshot):
        print(f"Mid price: {snapshot.mid_price:.4f}")
        print(f"Best bid: {snapshot.best_bid:.4f}")
        print(f"Best ask: {snapshot.best_ask:.4f}")

    await ws.subscribe(["token_id_1", "token_id_2"])
    await ws.run()

asyncio.run(main())
```

### Get 15-Minute Market Info

```python
from src.gamma_client import GammaClient

gamma = GammaClient()

# Get current BTC 15-minute market
market = gamma.get_market_info("BTC")
print(f"Market: {market['question']}")
print(f"Up token: {market['token_ids']['up']}")
print(f"Down token: {market['token_ids']['down']}")
print(f"Ends: {market['end_date']}")
```

### Cancel Orders

```python
# Cancel a specific order
await bot.cancel_order("order_id_here")

# Cancel all orders
await bot.cancel_all_orders()

# Cancel orders for a specific market
await bot.cancel_market_orders(market="condition_id", asset_id="token_id")
```

## Project Structure

```
polymarket-trading-bot/
├── src/                      # Core library
│   ├── bot.py               # TradingBot - main interface
│   ├── config.py            # Configuration handling
│   ├── client.py            # API clients (CLOB, Relayer)
│   ├── signer.py            # Order signing (EIP-712)
│   ├── crypto.py            # Key encryption
│   ├── utils.py             # Helper functions
│   ├── gamma_client.py      # 5m/15m market discovery
│   └── websocket_client.py  # Real-time WebSocket client
│
├── strategies/               # Trading strategies
│   ├── flash_crash.py      # Volatility trading strategy
│   └── (see apps/orderbook_tui.py)
│
├── examples/                 # Example code
│   ├── quickstart.py        # Start here!
│   ├── basic_trading.py     # Common operations
│   └── strategy_example.py  # Custom strategies
│
├── scripts/                  # Utility scripts
│   ├── setup.py             # Interactive setup
│   ├── run_bot.py           # Run the bot
│   └── full_test.py         # Integration tests
│
└── tests/                    # Unit tests
```

## Configuration Options

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POLY_PRIVATE_KEY` | Yes | Your wallet private key |
| `POLY_SAFE_ADDRESS` | Yes | Your Polymarket Safe address |
| `POLY_BUILDER_API_KEY` | For gasless | Builder Program API key |
| `POLY_BUILDER_API_SECRET` | For gasless | Builder Program secret |
| `POLY_BUILDER_API_PASSPHRASE` | For gasless | Builder Program passphrase |

### Config File (Alternative)

Create `config.yaml`:

```yaml
safe_address: "0xYourSafeAddress"

# For gasless trading (optional)
builder:
  api_key: "your_api_key"
  api_secret: "your_api_secret"
  api_passphrase: "your_passphrase"
```

Then load it:

```python
bot = TradingBot(config_path="config.yaml", private_key="0x...")
```

## Gasless Trading

To eliminate gas fees:

1. Apply for [Builder Program](https://polymarket.com/settings?tab=builder)
2. Set the environment variables:

```bash
export POLY_BUILDER_API_KEY=your_key
export POLY_BUILDER_API_SECRET=your_secret
export POLY_BUILDER_API_PASSPHRASE=your_passphrase
```

The bot will automatically use gasless mode when credentials are present.

## API Reference

### TradingBot Methods

| Method | Description |
|--------|-------------|
| `place_order(token_id, price, size, side)` | Place a limit order |
| `cancel_order(order_id)` | Cancel a specific order |
| `cancel_all_orders()` | Cancel all open orders |
| `cancel_market_orders(market, asset_id)` | Cancel orders for a specific market |
| `get_open_orders()` | List your open orders |
| `get_trades(limit=100)` | Get your trade history |
| `get_order_book(token_id)` | Get market order book |
| `get_market_price(token_id)` | Get current market price |
| `is_initialized()` | Check if bot is ready |

### MarketWebSocket Methods

| Method | Description |
|--------|-------------|
| `subscribe(asset_ids, replace=False)` | Subscribe to market data |
| `run(auto_reconnect=True)` | Start WebSocket connection |
| `disconnect()` | Close connection |
| `get_orderbook(asset_id)` | Get cached orderbook |
| `get_mid_price(asset_id)` | Get mid price |

### GammaClient Methods

| Method | Description |
|--------|-------------|
| `get_current_15m_market(coin)` | Get current 15-min market |
| `get_market_info(coin)` | Get market with token IDs |
| `get_all_15m_markets()` | List all 15-min markets |

## Security

Your private key is protected by:

1. **PBKDF2** key derivation (480,000 iterations)
2. **Fernet** symmetric encryption
3. File permissions set to `0600` (owner-only)

Best practices:
- Never commit `.env` files to git
- Use a dedicated wallet for trading
- Keep your encrypted key file private

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `POLY_PRIVATE_KEY not set` | Run `export POLY_PRIVATE_KEY=your_key` |
| `POLY_SAFE_ADDRESS not set` | Get it from polymarket.com/settings |
| `Invalid private key` | Check key is 64 hex characters |
| `Order failed` | Check you have sufficient balance |
| `WebSocket not connecting` | Check network/firewall settings |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new code
4. Run `pytest tests/ -v`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
