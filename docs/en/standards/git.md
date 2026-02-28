# Git Workflow

## 1. Branch Strategy

### 1.1 Long-lived Branches

| Branch | Purpose |
|--------|---------|
| `main` | Stable releases; merge only |
| `develop` | Main development branch |

### 1.2 Short-lived Branches

| Type | Naming | Example |
|------|--------|---------|
| Feature | `feature/{description}` | `feature/intent-broadcast` |
| Bugfix | `bugfix/{description}` | `bugfix/merchant-subscribe` |
| Docs | `docs/{description}` | `docs/add-contribution-guide` |
| Hotfix | `hotfix/{description}` | `hotfix/critical-auth-fix` |

### 1.3 Branch Lifecycle

```
feature/xxx → done → merge to develop → delete feature branch
develop     → release → merge to main → tag
```

---

## 2. Commit Convention

### 2.1 Conventional Commits

```
<type>(<scope>): <subject>
```

- **type**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`
- **scope**: Optional, e.g. `core`, `example`, `spec`
- **subject**: Short description; Chinese or English OK

### 2.2 Examples

```
feat(core): implement NATS intent broadcast
fix(example): fix Consumer reconnect logic
docs(en): add English documentation
```

### 2.3 Do Not Commit

- `.env`, keys, tokens
- `node_modules`, `__pycache__`, build artifacts
- IDE personal config (shared `.vscode/` OK)

---

## 3. Version & Tags

- Semantic versioning: `v1.2.3`
- On release: `git tag -a v1.0.0 -m "Release v1.0.0"`
- Push tags: `git push --tags`
