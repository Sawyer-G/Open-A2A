# 自托管 Solid Pod 指南

> 符合 Open-A2A 数据主权设计：偏好数据存储在用户自己的服务器，不依赖第三方平台。

## 1. 为何推荐自托管

| 方式 | 数据位置 | 与设计初衷 |
|------|----------|------------|
| **profile.json** | 本地文件 | ✅ 完全符合 |
| **自托管 Solid** | 用户自己的服务器 | ✅ 完全符合 |
| 第三方 Pod 提供商 | 他人服务器 | ❌ 与数据主权不符 |

自托管 Solid 在保持数据主权的同时，提供标准协议、细粒度访问控制，便于未来与 Solid 生态互通。

## 2. 快速部署（Docker）

```bash
# 启动自托管 Solid 服务
docker compose -f deploy/solid/docker-compose.solid.yml up -d

# 访问 https://localhost:8443 注册账号
# 自签名证书会提示「不安全」，本地开发可继续访问
```

**多用户模式**：若使用子域名（如 `alice.localhost`），需在 `/etc/hosts` 添加：
```
127.0.0.1 alice.localhost
```

## 3. 配置 Open-A2A

支持两种认证方式，**客户端凭证优先**（推荐生产环境）。

### 3.1 OAuth2 客户端凭证（推荐）

无需安装 solid-file，仅用标准库。在 `.env` 或环境中设置：

```bash
SOLID_CLIENT_ID=你的客户端 ID
SOLID_CLIENT_SECRET=你的客户端密钥
SOLID_POD_ENDPOINT=https://localhost:8443/你的用户名/
# 以下二选一：自动发现 token 端点 或 直接指定
SOLID_IDP=https://localhost:8443/
# SOLID_TOKEN_URL=https://localhost:8443/idp/credentials/token
```

客户端凭证需在 Solid 服务端注册（如 Community Solid Server 支持动态注册或管理端配置）。  
Token 端点可由 `SOLID_IDP` 的 `/.well-known/openid-configuration` 自动发现。

### 3.2 用户名/密码（开发/兼容）

需 `pip install open-a2a[solid]`：

```bash
SOLID_IDP=https://localhost:8443/
SOLID_POD_ENDPOINT=https://localhost:8443/你的用户名/
SOLID_USERNAME=你的用户名
SOLID_PASSWORD=你的密码
```

## 4. 上传偏好到 Pod

```bash
make install-solid   # 或 pip install open-a2a[solid]
python example/upload_profile_to_solid.py
```

## 5. 运行 Consumer

设置 `SOLID_POD_ENDPOINT` 后，Consumer 会从自托管 Pod 读取偏好：

```bash
make run-consumer
```

## 6. 生产环境

- 将 Solid 服务改为你的域名（如 `https://solid.yourdomain.com`），并配置 `SOLID_POD_ENDPOINT`、`SOLID_IDP` 或 `SOLID_TOKEN_URL`
- **推荐使用 OAuth2 客户端凭证**（`SOLID_CLIENT_ID`、`SOLID_CLIENT_SECRET`），避免在应用内保存用户密码
- 挂载 Let's Encrypt 等真实证书
- 参考 [docker-solid-server 示例](https://github.com/angelo-v/docker-solid-server/tree/main/examples)
