# 身份与信任（操作指南）：DID + 签名验真 + 可选 VC

> 本文是面向开发者/运营者的“如何用”指南。协议细节见：`spec/rfc-004-identity-and-trust.md`。

---

## 1. 你能得到什么能力？

- **身份唯一性**：用 `did:key` 表示“我是谁”
- **验真**：用签名证明“这张 meta 名片/这条消息确实由该 DID 私钥持有者产生”
- **信任策略可插拔**：协议层只提供验真能力；信任谁由节点/应用自行配置
- **VC 可选**：支持挂载背书，但不强制引入信用体系

---

## 2. Open-A2A 的最小互操作选择（推荐）

- DID：`did:key`
- 签名：JWS（`alg=EdDSA`，Ed25519）
- 签名输入：canonical JSON 的哈希（避免跨语言差异）

---

## 3. 在 Bridge 中启用 “meta proof”（推荐用于目录/发现）

Bridge 的 discovery meta 默认是“未验证”（unverified）的名片信息。  
当你启用 meta proof 后，Bridge 会在 `meta` 中生成：

- `did`：Bridge 的 did:key
- `proof`：对 `meta_without_proof` 的 canonical hash 做签名（JWS）

### 3.1 需要的环境变量

在 `.env`（或容器环境变量）中配置：

```bash
BRIDGE_ENABLE_META_PROOF=1

# 写入 meta.endpoints（便于展示/路由；可选）
BRIDGE_PUBLIC_URL=https://bridge.example.org

# 固定 DID（可选）：base64 seed，避免重启后 DID 变化
# 注意：不要把真实 seed 提交到仓库
BRIDGE_DID_SEED_B64=BASE64_SEED
```

> 若不提供 seed，Bridge 会生成临时身份（重启后可能变化）。生产建议固定 seed，并妥善保管。

---

## 4. 验签失败会怎样？

按照 RFC-004 的建议语义：

- **Discovery/目录场景**：验签失败的 meta 应标记为 `unverified`，默认不参与自动路由（但允许展示并提示风险）。
- **消息交互场景**：验签失败的消息默认丢弃，并记录安全日志（可选提供降级策略，但不建议默认开启）。

---

## 5. VC（可选）：如何挂载背书？

你可以在 `meta` 中增加（可选）字段，例如：

```json
{
  "credentials": [
    { "type": "vc", "uri": "https://issuer.example.org/vc/123", "issuer": "did:key:..." }
  ]
}
```

是否信任某个 VC（issuer/schema）由节点/应用策略决定，协议层不强制。

