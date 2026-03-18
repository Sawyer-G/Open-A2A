# RFC-004: 身份与信任（Identity & Trust）

> 版本：0.1.0-draft | 状态：草稿  
> 目标：把“身份与信任”从概念升级为**可互操作**、**可实现**、**不绑定业务**的协议约定。

---

## 1. 范围与非目标

### 1.1 本 RFC 解决什么

- **身份唯一性**：用 DID 表达“我是谁”
- **消息验真**：用签名表达“这条声明/消息确实由该 DID 私钥持有者产生”
- **信任选择**：为“我信谁/信任哪些背书”提供协议位（策略由节点/应用决定）
- **目录/发现可用性**：为 discovery 返回的 `meta` 提供最小互操作字段与 proof

### 1.2 本 RFC 不做什么

- 不定义“信用评分/封禁/仲裁”等业务平台机制
- 不强制绑定某个中心化账号系统或某条区块链
- 不强制所有节点使用 VC；仅提供挂载与验证接口位

---

## 2. 术语

- **DID**：去中心化标识符（Decentralized Identifier）
- **did:key**：无需注册中心的 DID 方法（MVP 推荐）
- **JWS**：JSON Web Signature（本 RFC 采用紧凑序列化）
- **Meta**：用于发现/目录展示/路由决策的“Agent 名片”
- **Proof**：用于证明 Meta 或消息的签名材料

---

## 3. 最小互操作方案（MVP 最优解）

为减少生态分裂与互操作失败，本 RFC 的 MVP 推荐固定以下组合：

- **DID 方法**：`did:key`
- **签名格式**：JWS（compact）
- **算法**：Ed25519 / EdDSA（JWS `alg=EdDSA`）
- **签名对象**：canonical JSON 的哈希（见 §5）

> 未来可扩展 `did:web` / `did:ion` 等，但 MVP 先确保 `did:key` 全链路互通。

---

## 4. Meta（目录/发现）最小字段

`meta` 是 discovery 的响应载体（见 RFC-002），也是运营者/应用构建“目录式发现”时的最小可互操作对象。

### 4.1 必填字段（MVP）

- `agent_id`（string）：节点内可读标识（展示/路由辅助）
- `did`（string）：发送方 DID（推荐 `did:key:...`）
- `endpoints`（array）：可被联系的入口列表（不绑定传输）
- `capabilities`（array）：能力列表（与 subject/意图主题一致，例如 `intent.food.order`）
- `proof`（object）：对本 meta 的验真材料（见 §6）

### 4.2 `endpoints` 结构（建议）

`endpoints` 是一个数组，元素为对象：

```json
{ "type": "nats|relay|http|...", "url": "..." }
```

示例：

```json
[
  {"type":"relay","url":"wss://relay.example.org:8765"},
  {"type":"http","url":"https://bridge.example.org"}
]
```

### 4.3 可选字段（允许扩展）

允许加入但不强制的字段示例：

- `operator` / `region` / `tags`
- `expires_at`（便于目录缓存/过期）
- `credentials`（VC 挂载位，见 §8）

---

## 5. Canonical JSON（签名输入的确定性序列化）

为实现跨语言互操作，本 RFC 定义一个 MVP 级别的 canonical JSON 规则：

- UTF-8 编码
- key **排序**
- `,` `:` 分隔符**不带空格**
- `ensure_ascii=false`

伪代码：

```
canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
hash = base64url_no_pad(sha256(canonical))
```

> 注意：这是 MVP 规则，不等价于 JSON-LD canonicalization；但足以解决本项目当前的 meta/intent 互操作问题。

---

## 6. Proof（Meta 证明）的最小结构

### 6.1 设计原则

为降低实现复杂度并避免库差异，Proof 不直接签 `meta` 原文，而是签 `meta` 的 canonical hash。

### 6.2 `proof` 字段

`meta.proof` 为对象，最小字段如下：

- `type`：固定 `"jws"`
- `alg`：固定 `"EdDSA"`
- `purpose`：固定 `"meta"`（可扩展）
- `created_at`：ISO 8601 字符串（可为空）
- `did`：签名者 DID（应等于 `meta.did`）
- `meta_hash_sha256_b64url`：对 `meta_without_proof` 的 canonical hash
- `jws`：JWS compact，payload 至少包含 `meta_hash_sha256_b64url` 与 `did`

示例（示意）：

```json
{
  "type": "jws",
  "alg": "EdDSA",
  "purpose": "meta",
  "created_at": "2026-03-18T12:00:00Z",
  "did": "did:key:z6Mk...",
  "meta_hash_sha256_b64url": "p2a...xyz",
  "jws": "eyJ...<compact jws>..."
}
```

### 6.3 验证规则

验证方应：

1) 从 `meta` 中移除 `proof` 得到 `meta_without_proof`
2) 按 §5 计算 `meta_hash_sha256_b64url`
3) 验签 `proof.jws` 得到 payload 与 signer
4) 检查 payload 中的 `meta_hash_sha256_b64url` 与本地计算一致
5) 检查 `meta.did` 与 payload 中的 `did` 一致（若两者均存在）

---

## 7. 失败语义（必须可预测）

### 7.1 Discovery/目录场景

当 `meta.proof` 不存在或验签失败：

- 标记该 meta 为 `unverified`
- **默认不用于自动路由**（可展示给用户，但提示风险）

### 7.2 消息交互场景（Intent/Offer 等）

当消息签名（或关联身份）验证失败：

- 默认丢弃消息
- 记录安全日志
- 允许实现提供“降级接收但标红”的开关（不推荐默认启用）

---

## 8. 可选：VC 挂载位与验证接口（支持但不强制）

### 8.1 挂载位

建议在 `meta.credentials` 中挂载 VC 引用（推荐）或小型内嵌 VC：

```json
{
  "credentials": [
    { "type": "vc", "uri": "https://example.org/vc/123", "issuer": "did:key:..." }
  ]
}
```

### 8.2 验证接口位（不强制实现）

实现方可声明：

- 可信 `issuer` 列表
- 支持的 VC schema 列表

具体验证方式（链上/链下/HTTP）由运营者/应用决定。

---

## 9. 参考实现（本仓库）

- `open_a2a/identity.py`：
  - `canonical_json_bytes`
  - `build_meta_proof`
  - `verify_meta_proof`
- RFC-002 Discovery：发现请求/响应主题与 meta 承载

