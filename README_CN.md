# Polymarket 交易机器人

[English](README.md) | 简体中文

一个新手友好的 Python 交易机器人，支持 Polymarket 无 Gas 交易。

## 特性

- **简单易用**：几行代码即可开始交易
- **零 Gas 费用**：使用 Builder Program 凭证免除 Gas 费
- **安全存储**：私钥使用 PBKDF2 + Fernet 加密保护
- **策略框架**：内置自定义交易策略支持
- **完整测试**：89 个单元测试覆盖所有功能

## 快速开始（5 分钟）

### 第一步：安装

```bash
git clone https://github.com/your-username/polymarket-trading-bot.git
cd polymarket-trading-bot
pip install -r requirements.txt
```

### 第二步：配置

```bash
# 设置你的凭证
export POLY_PRIVATE_KEY=你的MetaMask私钥
export POLY_SAFE_ADDRESS=0x你的Polymarket钱包地址
```

> **如何找到 Safe 地址？** 访问 [polymarket.com/settings](https://polymarket.com/settings)，复制你的钱包地址。

### 第三步：运行

```bash
# 运行快速入门示例
python examples/quickstart.py
```

就这么简单！你已经准备好开始交易了。

## 代码示例

### 最简单的例子

```python
from src import create_bot_from_env
import asyncio

async def main():
    # 从环境变量创建机器人
    bot = create_bot_from_env()

    # 获取你的挂单
    orders = await bot.get_open_orders()
    print(f"你有 {len(orders)} 个挂单")

asyncio.run(main())
```

### 下单交易

```python
from src import TradingBot, Config
import asyncio

async def trade():
    # 创建配置
    config = Config(safe_address="0x你的Safe地址")

    # 使用私钥初始化机器人
    bot = TradingBot(config=config, private_key="0x你的私钥")

    # 下一个买单
    result = await bot.place_order(
        token_id="12345...",   # 市场代币 ID
        price=0.65,            # 价格（0.65 = 65% 概率）
        size=10.0,             # 股数
        side="BUY"             # 或 "SELL"
    )

    if result.success:
        print(f"下单成功！订单号：{result.order_id}")
    else:
        print(f"下单失败：{result.message}")

asyncio.run(trade())
```

### 撤销订单

```python
# 撤销指定订单
await bot.cancel_order("订单ID")

# 撤销所有订单
await bot.cancel_all_orders()
```

### 获取市场数据

```python
# 获取订单簿
orderbook = await bot.get_order_book(token_id)
print(f"最高买价：{orderbook['bids'][0]}")

# 获取当前价格
price = await bot.get_market_price(token_id)
print(f"价格：{price}")

# 获取你的交易历史
trades = await bot.get_trades(limit=10)
```

## 项目结构

```
polymarket-trading-bot/
├── src/                      # 核心库
│   ├── bot.py               # TradingBot - 主接口
│   ├── config.py            # 配置管理
│   ├── client.py            # API 客户端
│   ├── signer.py            # 订单签名（EIP-712）
│   ├── crypto.py            # 私钥加密
│   └── utils.py             # 辅助函数
│
├── examples/                 # 示例代码
│   ├── quickstart.py        # 从这里开始！
│   ├── basic_trading.py     # 常用操作
│   └── strategy_example.py  # 自定义策略
│
├── scripts/                  # 工具脚本
│   ├── setup.py             # 交互式设置
│   ├── run_bot.py           # 运行机器人
│   └── full_test.py         # 集成测试
│
└── tests/                    # 单元测试
```

## 配置选项

### 环境变量

| 变量名 | 必需 | 说明 |
|--------|------|------|
| `POLY_PRIVATE_KEY` | 是 | 你的钱包私钥 |
| `POLY_SAFE_ADDRESS` | 是 | 你的 Polymarket Safe 地址 |
| `POLY_BUILDER_API_KEY` | 无 Gas 需要 | Builder Program API 密钥 |
| `POLY_BUILDER_API_SECRET` | 无 Gas 需要 | Builder Program 密钥 |
| `POLY_BUILDER_API_PASSPHRASE` | 无 Gas 需要 | Builder Program 口令 |

### 配置文件（另一种方式）

创建 `config.yaml`：

```yaml
safe_address: "0x你的Safe地址"

# 无 Gas 交易（可选）
builder:
  api_key: "你的api_key"
  api_secret: "你的api_secret"
  api_passphrase: "你的passphrase"
```

然后加载它：

```python
bot = TradingBot(config_path="config.yaml", private_key="0x...")
```

## 无 Gas 交易

要免除 Gas 费用：

1. 申请 [Builder Program](https://polymarket.com/settings?tab=builder)
2. 设置环境变量：

```bash
export POLY_BUILDER_API_KEY=你的密钥
export POLY_BUILDER_API_SECRET=你的密钥
export POLY_BUILDER_API_PASSPHRASE=你的口令
```

当凭证存在时，机器人会自动使用无 Gas 模式。

## API 参考

### TradingBot 方法

| 方法 | 说明 |
|------|------|
| `place_order(token_id, price, size, side)` | 下限价单 |
| `cancel_order(order_id)` | 撤销指定订单 |
| `cancel_all_orders()` | 撤销所有挂单 |
| `get_open_orders()` | 获取挂单列表 |
| `get_trades(limit=100)` | 获取交易历史 |
| `get_order_book(token_id)` | 获取市场订单簿 |
| `get_market_price(token_id)` | 获取当前市场价格 |
| `is_initialized()` | 检查机器人是否就绪 |

### 订单参数

| 参数 | 类型 | 示例 | 说明 |
|------|------|------|------|
| `token_id` | str | `"123..."` | 市场结果代币 ID |
| `price` | float | `0.65` | 价格 0-1（0.65 = 65%） |
| `size` | float | `10.0` | 股数 |
| `side` | str | `"BUY"` | "BUY" 或 "SELL" |

## 安全性

你的私钥受到以下保护：

1. **PBKDF2** 密钥派生（480,000 次迭代）
2. **Fernet** 对称加密
3. 文件权限设置为 `0600`（仅所有者可读）

最佳实践：
- 永远不要将 `.env` 文件提交到 git
- 使用专门的钱包进行交易
- 妥善保管你的加密密钥文件

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行并显示覆盖率
pytest tests/ -v --cov=src
```

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| `POLY_PRIVATE_KEY not set` | 运行 `export POLY_PRIVATE_KEY=你的私钥` |
| `POLY_SAFE_ADDRESS not set` | 从 polymarket.com/settings 获取 |
| `Invalid private key` | 检查私钥是否为 64 个十六进制字符 |
| `Order failed` | 检查是否有足够的余额 |

## 新手学习路径

1. 首先阅读 `examples/quickstart.py` - 最简单的示例
2. 然后看 `examples/basic_trading.py` - 常用操作
3. 研究 `src/bot.py` - 理解核心类
4. 最后看 `examples/strategy_example.py` - 自定义策略

## 贡献

1. Fork 本仓库
2. 创建功能分支
3. 为新代码编写测试
4. 运行 `pytest tests/ -v`
5. 提交 Pull Request

## 许可证

MIT 许可证 - 详见 LICENSE 文件。
