"""
偏好存储抽象 (Phase 2)

为 Solid Pod 预留接口，当前提供基于文件的实现与 Solid Pod 实现。
Agent 从偏好存储读取用户约束（如口味、预算），而非硬编码。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

import json


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


class SolidPodPreferencesProvider(PreferencesProvider):
    """
    基于自托管 Solid Pod 的偏好存储（推荐，符合数据主权）。

    从用户 Pod 的 open-a2a/profile.json 读取偏好。
    需环境变量：SOLID_IDP、SOLID_USERNAME、SOLID_PASSWORD、SOLID_POD_ENDPOINT。
    或通过构造函数传入。详见 docs/zh/08-solid-self-hosted.md。

    依赖：pip install open-a2a[solid]
    """

    PROFILE_PATH = "open-a2a/profile.json"

    def __init__(
        self,
        *,
        idp: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        pod_endpoint: Optional[str] = None,
    ) -> None:
        import os

        self._idp = idp or os.getenv("SOLID_IDP", "")
        self._username = username or os.getenv("SOLID_USERNAME", "")
        self._password = password or os.getenv("SOLID_PASSWORD", "")
        self._pod_endpoint = _ensure_trailing_slash(
            pod_endpoint or os.getenv("SOLID_POD_ENDPOINT", "")
        )
        self._api = None
        self._data: dict[str, Any] = {}
        self._load()

    def _get_api(self):
        """延迟初始化 Solid API（仅在需要时导入并登录）"""
        if self._api is not None:
            return self._api
        try:
            from solid.auth import Auth
            from solid.solid_api import SolidAPI
        except ImportError as e:
            raise ImportError(
                "Solid Pod 支持需要安装 solid-file: pip install open-a2a[solid]"
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
        api = self._get_api()
        profile_url = self._pod_endpoint + self.PROFILE_PATH
        to_save = data if data is not None else self._data
        folder_url = self._pod_endpoint + "open-a2a/"
        if not api.item_exists(folder_url):
            api.create_folder(folder_url)
        content = json.dumps(to_save, ensure_ascii=False, indent=2).encode("utf-8")
        api.put_file(profile_url, content, "application/json")
        self._data = to_save
