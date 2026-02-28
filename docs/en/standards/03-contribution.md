# Contribution Guide

## 1. Collaboration Flow

### 1.1 Basic Flow

```
Fork → Create branch → Develop → Commit → Open Pull Request → Code Review → Merge
```

### 1.2 Branch Strategy

See [git.md](./git.md).

---

## 2. Commit Convention

### 2.1 Conventional Commits Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### 2.2 Type

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation change |
| `style` | Formatting (no logic change) |
| `refactor` | Refactor |
| `perf` | Performance |
| `test` | Tests |
| `chore` | Build, deps, etc. |

### 2.3 Examples

```
feat(core): add intent broadcast module
fix(example): fix Merchant subscribe topic
docs(en): add English documentation
```

---

## 3. Pull Request Guidelines

### 3.1 PR Title

- Match commit message format
- Concise description of changes

### 3.2 PR Template

```markdown
## Change Type
- [ ] New feature
- [ ] Bug fix
- [ ] Docs
- [ ] Other

## Description
(Brief summary)

## Related Issue
(If any, #123)

## Checklist
- [ ] Code follows project standards
- [ ] Tests added/updated
- [ ] Docs updated (if applicable, update both zh and en)
```

### 3.3 Code Review Expectations

- Correct logic, readable
- Matches project structure and naming
- No sensitive data
- Docs consistent with code

---

## 4. Issue Guidelines

### 4.1 Title

- Concise problem or suggestion
- Optional prefix: `[Bug]`, `[Feature]`, `[Docs]`

### 4.2 Content

- Clear problem or need
- Reproduction steps (Bug) or use case (Feature)
- Environment info if relevant

---

## 5. Communication

- Respect different views; discuss rationally
- Chinese or English both fine; stay consistent
- Thank contributors
