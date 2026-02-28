# 文档规范

## 1. 文档目录结构

```
docs/
├── README.md                   # 语言选择器
├── zh/                         # 中文文档
│   ├── 01-project-overview.md
│   ├── 02-requirements.md
│   ├── 03-architecture.md
│   ├── 04-roadmap.md
│   ├── 05-development-guide.md
│   ├── standards/
│   └── reference/
└── en/                         # 英文文档（与 zh 结构镜像）
    ├── 01-project-overview.md
    ├── ...
    ├── standards/
    └── reference/
```

---

## 2. 双语维护原则

- **同步更新**：中文与英文文档内容应对齐，重大更新时同时修改两处
- **结构一致**：`zh/` 与 `en/` 目录结构、文件名保持一致
- **链接**：同语言文档内使用相对路径，跨语言可链接到对应版本

---

## 3. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 主文档 | `{序号}-{主题}.md` | `01-project-overview.md` |
| 规范文档 | `{序号}-{主题}.md` 或 `{主题}.md` | `git.md` |
| 参考资料 | `{主题}.md`，置于 `reference/` | `legacy-design-consultation.md` |
| 协议文档 | 置于 `spec/`，`rfc-{编号}-{主题}.md` | `rfc-001-intent-protocol.md` |

---

## 4. 文档编写规范

### 4.1 结构

- 使用清晰的标题层级（H1 → H2 → H3）
- 每个文档应有 H1 标题作为文档标题
- 长文档建议在开头提供目录或摘要

### 4.2 格式

- 使用 Markdown 标准语法
- 代码块标明语言：` ```python `、` ```bash `
- 表格对齐，便于阅读
- 链接使用相对路径

### 4.3 更新原则

- 文档与代码同步更新，避免文档滞后
- 重大架构变更时，同步更新 `03-architecture.md`（中英）
- 新增规范时，更新 `docs/zh/README.md` 与 `docs/en/README.md` 导航
