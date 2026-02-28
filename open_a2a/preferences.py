"""
偏好存储抽象 (Phase 2)

为 Solid Pod 预留接口，当前提供基于文件的实现。
Agent 从偏好存储读取用户约束（如口味、预算），而非硬编码。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

import json


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
