# Open-A2A 开发命令
# 使用 make 或 make help 查看可用命令

.PHONY: venv install install-full run-merchant run-consumer run-carrier help

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
	@echo "  make run-consumer - 运行 Consumer 示例"
	@echo "  make run-carrier  - 运行 Carrier 示例"
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

run-merchant:
	$(PYTHON) example/merchant.py

run-consumer:
	$(PYTHON) example/consumer.py

run-carrier:
	$(PYTHON) example/carrier.py
