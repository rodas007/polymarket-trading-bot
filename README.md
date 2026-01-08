# Polymarket Trading Bot

English | [简体中文](README_CN.md)

A beginner-friendly Python trading bot for Polymarket with gasless transactions.

## Features

- **Simple API**: Just a few lines of code to start trading
- **Gasless Transactions**: No gas fees with Builder Program credentials
- **Secure Key Storage**: Private keys encrypted with PBKDF2 + Fernet
- **Strategy Framework**: Built-in support for custom trading strategies
- **Fully Tested**: 58 unit tests covering all functionality

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
```

That's it! You're ready to trade.

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

### Cancel Orders

```python
# Cancel a specific order
await bot.cancel_order("order_id_here")

# Cancel all orders
await bot.cancel_all_orders()
```

### Get Market Data

```python
# Get order book
orderbook = await bot.get_order_book(token_id)
print(f"Best bid: {orderbook['bids'][0]}")

# Get current price
price = await bot.get_market_price(token_id)
print(f"Price: {price}")

# Get your trade history
trades = await bot.get_trades(limit=10)
```

## Project Structure

```
polymarket-trading-bot/
├── src/                      # Core library
│   ├── bot.py               # TradingBot - main interface
│   ├── config.py            # Configuration handling
│   ├── client.py            # API clients
│   ├── signer.py            # Order signing (EIP-712)
│   ├── crypto.py            # Key encryption
│   └── utils.py             # Helper functions
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
| `get_open_orders()` | List your open orders |
| `get_trades(limit=100)` | Get your trade history |
| `get_order_book(token_id)` | Get market order book |
| `get_market_price(token_id)` | Get current market price |
| `is_initialized()` | Check if bot is ready |

### Order Parameters

| Parameter | Type | Example | Description |
|-----------|------|---------|-------------|
| `token_id` | str | `"123..."` | Market outcome token ID |
| `price` | float | `0.65` | Price 0-1 (0.65 = 65%) |
| `size` | float | `10.0` | Number of shares |
| `side` | str | `"BUY"` | "BUY" or "SELL" |

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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new code
4. Run `pytest tests/ -v`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
