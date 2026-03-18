# Open-A2A 开发命令
# 使用 make 或 make help 查看可用命令

.PHONY: venv install install-full install-solid install-bridge install-relay install-dht install-e2e run-merchant run-merchant-2 run-merchant-3 run-consumer run-carrier run-bridge run-relay run-relay-e2e-verify run-multi-merchant-demo run-discovery-demo run-discovery-dht-demo run-dht-discovery-renew run-bridge-discovery-renew run-federation-xy down-federation-xy lint test help

# 默认使用 .venv
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help:
	@echo "Open-A2A 开发命令"
	@echo ""
	@echo "  make venv         - 创建虚拟环境"
	@echo "  make install      - 在虚拟环境中安装项目 (editable)"
	@echo "  make install-full - 安装项目及 identity、dev 等可选依赖"
	@echo "  make install-solid - 安装项目及自托管 Solid Pod 支持"
	@echo "  make run-merchant - 运行 Merchant 示例"
	@echo "  make run-merchant-2 / run-merchant-3 - 运行第 2/3 个 Merchant（多商家手动验证）"
	@echo "  make run-multi-merchant-demo - 多 Merchant 场景自动化验证（需 NATS 已启）"
	@echo "  make run-consumer - 运行 Consumer 示例"
	@echo "  make run-carrier  - 运行 Carrier 示例"
	@echo "  make run-bridge   - 运行 Open-A2A Bridge（需 make install-bridge）"
	@echo "  make run-discovery-demo  - 运行 Discovery 注册/发现示例（NATS）"
	@echo "  make run-discovery-dht-demo - 运行 DHT 发现示例（跨网络）"
	@echo "  make run-dht-discovery-renew - DHT 注册续租示例（跨节点 discover 客户端最佳实践）"
	@echo "  make run-bridge-discovery-renew - Bridge 注册续租示例（目录注册表/Directory Registry 客户端最佳实践，原 Path B）"
	@echo "  make run-federation-xy   - 运行 X↔Y subject-bridge 示例（Docker）"
	@echo "  make down-federation-xy  - 停止 X↔Y subject-bridge 示例（Docker）"
	@echo "  make install-relay       - 安装 Relay 依赖（websockets）"
	@echo "  make install-dht         - 安装 DHT 发现依赖（kademlia）"
	@echo "  make install-e2e         - 安装 Relay 负载 E2E 加密依赖（cryptography）"
	@echo "  make run-relay           - 运行 Relay 服务（WebSocket <-> NATS，可选 TLS：RELAY_WS_TLS=1）"
	@echo "  make run-relay-e2e-verify - 验证 Relay 负载 E2E 加密（需先 make install-e2e，NATS+Relay 已启）"
	@echo "  make lint                - 运行 ruff check（open_a2a/ relay/ tests/）"
	@echo "  make test                - 运行 pytest（需 make install 含 dev 依赖）"
	@echo ""
	@echo "首次使用: make venv && make install"

venv:
	@if [ ! -d $(VENV) ]; then \
		python3 -m venv $(VENV) && \
		$(PIP) install --upgrade pip && \
		echo "虚拟环境已创建: $(VENV)"; \
	else \
		echo "虚拟环境已存在: $(VENV)"; \
	fi

install: venv
	$(PIP) install -e .
	@echo "依赖已安装到虚拟环境"

install-full: venv
	$(PIP) install -e ".[identity,dev]"
	@echo "依赖（含 identity）已安装到虚拟环境"

install-solid: venv
	$(PIP) install -e ".[solid]"
	@echo "依赖（含 Solid Pod）已安装到虚拟环境"

install-bridge: venv
	$(PIP) install -e ".[bridge]"
	@echo "依赖（含 Bridge）已安装到虚拟环境"

install-relay: venv
	$(PIP) install -e ".[relay]"
	@echo "依赖（含 Relay）已安装到虚拟环境"

install-e2e: venv
	$(PIP) install -e ".[e2e]"
	@echo "依赖（含 E2E 负载加密）已安装到虚拟环境"

install-dht: venv
	$(PIP) install -e ".[dht]"
	@echo "依赖（含 DHT 发现）已安装到虚拟环境"

run-bridge:
	$(PYTHON) -m uvicorn bridge.main:app --host 0.0.0.0 --port 8080

run-merchant:
	$(PYTHON) example/merchant.py

run-merchant-2:
	MERCHANT_ID=merchant-002 $(PYTHON) example/merchant.py

run-merchant-3:
	MERCHANT_ID=merchant-003 $(PYTHON) example/merchant.py

run-multi-merchant-demo:
	$(PYTHON) example/multi_merchant_demo.py

run-consumer:
	$(PYTHON) example/consumer.py

run-carrier:
	$(PYTHON) example/carrier.py

run-discovery-demo:
	$(PYTHON) example/discovery_demo.py

run-discovery-dht-demo:
	$(PYTHON) example/discovery_dht_demo.py

run-dht-discovery-renew:
	$(PYTHON) example/dht_discovery_renew.py

run-bridge-discovery-renew:
	$(PYTHON) example/bridge_discovery_renew.py

run-federation-xy:
	docker compose -f deploy/federation/x-y/docker-compose.yml up -d --build

down-federation-xy:
	docker compose -f deploy/federation/x-y/docker-compose.yml down

run-relay:
	$(PYTHON) relay/main.py

run-relay-e2e-verify:
	$(PYTHON) example/relay_e2e_verify.py

lint:
	$(PYTHON) -m ruff check open_a2a/ relay/ tests/

test:
	$(PYTHON) -m pytest tests/ -v --tb=short
