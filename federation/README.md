# Federation（多运营者互联）

本目录存放 **federation 的实现代码**，用于在**两套独立运营的 NATS** 之间选择性同步部分 subject（更符合多运营者网状结构与数据边界）。

## 你该从哪里开始？

- **想直接跑起来（推荐）**：使用可复制部署示例
  - `deploy/federation-x-y/`：两套独立 NATS（X/Y）+ `subject-bridge`（默认桥接 `intent.>`）
- **想理解实现原理/做二次开发**：
  - `federation/subject_bridge.py`：subject bridge 的核心实现（环路/风暴保护、去重、观测端点）

## 与文档的对应关系

- 机制与最佳实践（桥接哪些 subject、如何避免环路/风暴、如何观测）：  
  - `docs/zh/16-multi-operator-federation-subject-bridge.md`  
  - `docs/en/16-multi-operator-federation-subject-bridge.md`

