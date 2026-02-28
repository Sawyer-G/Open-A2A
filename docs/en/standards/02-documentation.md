# Documentation Standards

## 1. Doc Directory Structure

```
docs/
├── README.md                   # Language selector
├── zh/                         # Chinese docs
│   ├── 01-project-overview.md
│   ├── 02-requirements.md
│   ├── 03-architecture.md
│   ├── 04-roadmap.md
│   ├── 05-development-guide.md
│   ├── standards/
│   └── reference/
└── en/                         # English docs (mirrors zh structure)
    ├── 01-project-overview.md
    ├── ...
    ├── standards/
    └── reference/
```

---

## 2. Bilingual Maintenance

- **Sync updates**: Chinese and English content should stay aligned; update both on major changes
- **Consistent structure**: `zh/` and `en/` share the same layout and filenames
- **Links**: Use relative paths within same language; cross-language links point to the corresponding version

---

## 3. Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Main docs | `{number}-{topic}.md` | `01-project-overview.md` |
| Standards | `{number}-{topic}.md` or `{topic}.md` | `git.md` |
| Reference | `{topic}.md` in `reference/` | `legacy-design-consultation.md` |
| Protocol | In `spec/`, `rfc-{number}-{topic}.md` | `rfc-001-intent-protocol.md` |

---

## 4. Writing Guidelines

### 4.1 Structure

- Clear heading hierarchy (H1 → H2 → H3)
- Every doc has an H1 title
- Long docs: add TOC or summary at top

### 4.2 Format

- Standard Markdown
- Code blocks with language: ` ```python `, ` ```bash `
- Aligned tables
- Relative paths for links

### 4.3 Update Rules

- Keep docs in sync with code
- On major architecture changes, update `03-architecture.md` (both languages)
- On new standards, update `docs/zh/README.md` and `docs/en/README.md`
