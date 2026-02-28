# Git 工作流规范

## 1. 分支策略

### 1.1 长期分支

| 分支 | 说明 |
|------|------|
| `main` | 稳定发布版本，仅接受合并 |
| `develop` | 开发主分支，功能合并到此 |

### 1.2 临时分支

| 类型 | 命名规范 | 示例 |
|------|----------|------|
| 功能 | `feature/{描述}` | `feature/intent-broadcast` |
| 修复 | `bugfix/{描述}` | `bugfix/merchant-subscribe` |
| 文档 | `docs/{描述}` | `docs/add-contribution-guide` |
| 热修复 | `hotfix/{描述}` | `hotfix/critical-auth-fix` |

### 1.3 分支生命周期

```
feature/xxx → 开发完成 → 合并到 develop → 删除 feature 分支
develop     → 发布时   → 合并到 main     → 打 Tag
```

---

## 2. 提交规范

### 2.1 Conventional Commits

```
<type>(<scope>): <subject>
```

- **type**：`feat`、`fix`、`docs`、`style`、`refactor`、`perf`、`test`、`chore`
- **scope**：可选，如 `core`、`example`、`spec`
- **subject**：简短描述，中文或英文均可

### 2.2 示例

```
feat(core): 实现 NATS 意图广播
fix(example): 修复 Consumer 重连逻辑
docs(en): add English documentation
```

### 2.3 不提交的内容

- `.env`、密钥、Token
- `node_modules`、`__pycache__`、构建产物
- IDE 个人配置（可提交 `.vscode/` 共享配置）

---

## 3. 版本与 Tag

- 采用语义化版本：`v1.2.3`
- 发布时：`git tag -a v1.0.0 -m "Release v1.0.0"`
- 推送 Tag：`git push --tags`
