# Open-A2A 项目文档（中文）

> 去中心化 Agent 间协作协议 —— 后互联网时代的 TCP/IP

## 文档导航

| 文档 | 说明 |
|------|------|
| [**00-design-principles.md**](./00-design-principles.md) | **设计原则**：核心目标、与示例场景的关系（必读） |
| [01-project-overview.md](./01-project-overview.md) | 项目概览：背景、愿景、目标用户 |
| [02-requirements.md](./02-requirements.md) | 产品需求：通用能力、示例场景、约束与边界 |
| [03-architecture.md](./03-architecture.md) | 系统架构：三层智能网格、技术栈实现 |
| [04-roadmap.md](./04-roadmap.md) | 开发路线图：MVP 落地步骤 |
| [05-development-guide.md](./05-development-guide.md) | 开发指南：资源栈、架构优化、竞品分析 |
| [06-progress.md](./06-progress.md) | **项目进度**：当前完成项与验证结果 |
| [07-multi-language-sdk.md](./07-multi-language-sdk.md) | 多语言 SDK 规划：未来扩展参考 |
| [08-solid-self-hosted.md](./08-solid-self-hosted.md) | **自托管 Solid Pod**：数据主权推荐方案 |
| [09-deployment-and-openclaw-integration.md](./09-deployment-and-openclaw-integration.md) | **服务器部署与 OpenClaw 集成**：与现有服务共存 |
| [09-openclaw-docker-quickstart.md](./09-openclaw-docker-quickstart.md) | **OpenClaw（Docker）环境快速集成指南**：在容器中运行的 OpenClaw 与 Open-A2A 的对接实践 |
| [10-nats-cluster-federation.md](./10-nats-cluster-federation.md) | NATS 集群与联邦：多机共享主题空间 |
| [11-relay-e2e-verify.md](./11-relay-e2e-verify.md) | Relay 端到端加密验证 |
| [12-cross-ip-testing.md](./12-cross-ip-testing.md) | **跨 IP 测试指南**：各自网络部署下的必要验证 |
| [13-security-considerations.md](./13-security-considerations.md) | **安全考量**：威胁模型、风险清单与最佳实践 |
| [openclaw-tool-example.md](./openclaw-tool-example.md) | OpenClaw Tool 配置示例 |

## 规范与标准

| 文档 | 说明 |
|------|------|
| [standards/01-project-structure.md](./standards/01-project-structure.md) | 项目结构、代码组织、命名规范 |
| [standards/02-documentation.md](./standards/02-documentation.md) | 文档编写与维护规范 |
| [standards/03-contribution.md](./standards/03-contribution.md) | 贡献指南、提交规范、PR 流程 |
| [standards/git.md](./standards/git.md) | Git 工作流、分支策略 |

## 参考资料

| 文档 | 说明 |
|------|------|
| [reference/legacy-design-consultation.md](./reference/legacy-design-consultation.md) | 归档：早期技术咨询文档 |

## 阅读顺序建议

1. **新成员**：00（设计原则）→ 01 → 02 → 03 → 04
2. **开发者**：00 → 03 → 05 → 04，并阅读 `standards/01-project-structure.md`
3. **贡献者**：全部文档 + `standards/` 下所有规范
