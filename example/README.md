# Open-A2A 示例

## 运行前准备

### 1. 创建虚拟环境并安装依赖（推荐，不污染系统环境）

```bash
make venv
make install
```

或手动：

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### 2. 启动 NATS 服务器

使用 Docker：

```bash
docker run -p 4222:4222 -p 8222:8222 nats:latest
```

或本地安装 [NATS](https://docs.nats.io/running-a-nats-service/introduction/installation)。

## 运行示例

### 终端 1：启动 Merchant（商家）

```bash
make run-merchant
# 或激活 venv 后: python example/merchant.py
```

### 终端 2：启动 Consumer（消费者）

```bash
make run-consumer
# 或激活 venv 后: python example/consumer.py
```

Consumer 会发布「想吃披萨」意图，Merchant 收到后自动回复报价。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NATS_URL` | NATS 服务器地址 | `nats://localhost:4222` |
| `MERCHANT_ID` | Merchant Agent ID | `merchant-001` |
