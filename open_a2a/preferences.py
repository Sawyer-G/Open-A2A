"""
偏好存储抽象 (Phase 2)

为 Solid Pod 预留接口，当前提供基于文件的实现与 Solid Pod 实现。
Agent 从偏好存储读取用户约束（如口味、预算），而非硬编码。

Solid 认证：支持用户名/密码（solid-file）或 OAuth2 客户端凭证（推荐生产）。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional


def _ensure_trailing_slash(url: str) -> str:
    """确保 URL 以 / 结尾"""
    return url.rstrip("/") + "/" if url else "/"


class PreferencesProvider(ABC):
    """偏好存储抽象基类"""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """获取偏好值"""
        pass

    @abstractmethod
    def get_constraints(self) -> list[str]:
        """获取约束列表（如 No_Coriander, <30min）"""
        pass

    @abstractmethod
    def get_location(self) -> Optional[dict[str, float]]:
        """获取位置偏好，返回 {"lat": float, "lon": float} 或 None"""
        pass


class FilePreferencesProvider(PreferencesProvider):
    """
    基于 JSON 文件的偏好存储。

    文件格式示例 (profile.json):
        {
            "constraints": ["No_Coriander", "<30min"],
            "location": {"lat": 31.23, "lon": 121.47},
            "budget_max": 50
        }
    """

    def __init__(self, path: str | Path = "profile.json") -> None:
        self._path = Path(path)
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def get_constraints(self) -> list[str]:
        return self._data.get("constraints", [])

    def get_location(self) -> Optional[dict[str, float]]:
        loc = self._data.get("location")
        if loc and isinstance(loc, dict) and "lat" in loc and "lon" in loc:
            return {"lat": float(loc["lat"]), "lon": float(loc["lon"])}
        return None


class InMemoryPreferencesProvider(PreferencesProvider):
    """
    Default, dependency-free preferences provider.

    This makes the "preferences" feature usable out of the box while keeping Solid as an optional upgrade.
    """

    def __init__(self, data: Optional[dict[str, Any]] = None) -> None:
        self._data = dict(data or {})

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def get_constraints(self) -> list[str]:
        v = self._data.get("constraints", [])
        return list(v) if isinstance(v, list) else []

    def get_location(self) -> Optional[dict[str, float]]:
        loc = self._data.get("location")
        if loc and isinstance(loc, dict) and "lat" in loc and "lon" in loc:
            return {"lat": float(loc["lat"]), "lon": float(loc["lon"])}
        return None


def preferences_from_env(*, file_path: "str | Path" = "profile.json") -> PreferencesProvider:
    """
    Best-practice factory:
    - If Solid env vars are present, use SolidPodPreferencesProvider
    - Else if a local profile.json exists, use FilePreferencesProvider
    - Else fallback to InMemoryPreferencesProvider
    """
    import os

    if os.getenv("SOLID_POD_ENDPOINT", "").strip():
        return SolidPodPreferencesProvider()
    p = Path(file_path)
    if p.exists():
        return FilePreferencesProvider(p)
    return InMemoryPreferencesProvider()


def _oauth2_client_credentials_token(
    token_url: str, client_id: str, client_secret: str
) -> str:
    """OAuth2 client_credentials 获取 access_token（标准库实现）。"""
    body = (
        f"grant_type=client_credentials&client_id={urllib.parse.quote(client_id)}"
        f"&client_secret={urllib.parse.quote(client_secret)}"
    )
    req = urllib.request.Request(
        token_url,
        data=body.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    token = data.get("access_token")
    if not token:
        raise ValueError("OAuth2 响应中无 access_token")
    return token


def _oidc_token_endpoint(idp: str) -> str:
    """从 IdP 的 .well-known/openid-configuration 获取 token_endpoint。"""
    base = idp.rstrip("/")
    url = f"{base}/.well-known/openid-configuration"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    endpoint = data.get("token_endpoint")
    if not endpoint:
        raise ValueError("OpenID 配置中无 token_endpoint")
    return endpoint


class SolidPodPreferencesProvider(PreferencesProvider):
    """
    基于自托管 Solid Pod 的偏好存储（推荐，符合数据主权）。

    从用户 Pod 的 open-a2a/profile.json 读取偏好。

    认证方式（二选一，客户端凭证优先）：
    - **OAuth2 客户端凭证**（推荐生产）：SOLID_CLIENT_ID、SOLID_CLIENT_SECRET，
      可选 SOLID_TOKEN_URL 或由 SOLID_IDP 自动发现。
    - **用户名/密码**：SOLID_IDP、SOLID_USERNAME、SOLID_PASSWORD（需 solid-file）。

    共用：SOLID_POD_ENDPOINT。详见 docs/zh/08-solid-self-hosted.md。
    依赖：pip install open-a2a[solid]（用户名/密码路径；客户端凭证仅用标准库）
    """

    PROFILE_PATH = "open-a2a/profile.json"

    def __init__(
        self,
        *,
        idp: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        pod_endpoint: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token_url: Optional[str] = None,
    ) -> None:
        import os

        self._idp = (idp or os.getenv("SOLID_IDP", "")).rstrip("/")
        self._username = username or os.getenv("SOLID_USERNAME", "")
        self._password = password or os.getenv("SOLID_PASSWORD", "")
        self._pod_endpoint = _ensure_trailing_slash(
            pod_endpoint or os.getenv("SOLID_POD_ENDPOINT", "")
        )
        self._client_id = client_id or os.getenv("SOLID_CLIENT_ID", "")
        self._client_secret = client_secret or os.getenv("SOLID_CLIENT_SECRET", "")
        self._token_url = token_url or os.getenv("SOLID_TOKEN_URL", "").strip()
        self._api = None
        self._data: dict[str, Any] = {}
        self._use_client_credentials = bool(self._client_id and self._client_secret)
        self._access_token: Optional[str] = None
        self._load()

    def _get_token(self) -> str:
        """OAuth2 客户端凭证获取 access_token（带简单缓存）。"""
        if self._access_token:
            return self._access_token
        if not self._token_url and self._idp:
            self._token_url = _oidc_token_endpoint(self._idp)
        if not self._token_url:
            raise ValueError("需配置 SOLID_TOKEN_URL 或 SOLID_IDP 以自动发现 token 端点")
        self._access_token = _oauth2_client_credentials_token(
            self._token_url, self._client_id, self._client_secret
        )
        return self._access_token

    def _pod_request(
        self, method: str, url: str, body: Optional[bytes] = None
    ) -> tuple[int, bytes]:
        """使用 Bearer token 对 Pod 发起 HTTP 请求。"""
        token = self._get_token()
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read() if e.fp else b""

    def _load_via_client_credentials(self) -> None:
        if not self._pod_endpoint:
            self._data = {}
            return
        profile_url = self._pod_endpoint + self.PROFILE_PATH
        try:
            code, raw = self._pod_request("GET", profile_url)
            if code == 200 and raw:
                self._data = json.loads(raw.decode("utf-8"))
            else:
                self._data = {}
        except Exception:
            self._data = {}

    def _get_api(self):
        """延迟初始化 Solid API（仅用户名/密码路径，需 solid-file）"""
        if self._api is not None:
            return self._api
        try:
            from solid.auth import Auth
            from solid.solid_api import SolidAPI
        except ImportError as e:
            raise ImportError(
                "Solid Pod 用户名/密码方式需要安装 solid-file: pip install open-a2a[solid]"
            ) from e
        if not self._idp or not self._username or not self._password:
            raise ValueError(
                "Solid Pod 需要 SOLID_IDP、SOLID_USERNAME、SOLID_PASSWORD 环境变量或构造函数参数"
            )
        auth = Auth()
        auth.login(self._idp, self._username, self._password)
        self._api = SolidAPI(auth)
        return self._api

    def _load(self) -> None:
        if self._use_client_credentials:
            self._load_via_client_credentials()
            return
        if not self._pod_endpoint:
            self._data = {}
            return
        try:
            api = self._get_api()
            profile_url = self._pod_endpoint + self.PROFILE_PATH
            if api.item_exists(profile_url):
                resp = api.get(profile_url)
                self._data = json.loads(resp.text)
            else:
                self._data = {}
        except Exception:
            self._data = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def get_constraints(self) -> list[str]:
        return self._data.get("constraints", [])

    def get_location(self) -> Optional[dict[str, float]]:
        loc = self._data.get("location")
        if loc and isinstance(loc, dict) and "lat" in loc and "lon" in loc:
            return {"lat": float(loc["lat"]), "lon": float(loc["lon"])}
        return None

    def save(self, data: Optional[dict[str, Any]] = None) -> None:
        """
        将偏好写回 Pod（可选）。
        若 data 为 None，则写入当前内存中的 _data。
        """
        if not self._pod_endpoint:
            raise ValueError("未配置 SOLID_POD_ENDPOINT")
        to_save = data if data is not None else self._data
        profile_url = self._pod_endpoint + self.PROFILE_PATH
        content = json.dumps(to_save, ensure_ascii=False, indent=2).encode("utf-8")

        if self._use_client_credentials:
            code, _ = self._pod_request("PUT", profile_url, body=content)
            if code not in (200, 201, 204):
                raise RuntimeError(f"Pod PUT 失败: HTTP {code}")
            self._data = to_save
            return
        api = self._get_api()
        folder_url = self._pod_endpoint + "open-a2a/"
        if not api.item_exists(folder_url):
            api.create_folder(folder_url)
        api.put_file(profile_url, content, "application/json")
        self._data = to_save
