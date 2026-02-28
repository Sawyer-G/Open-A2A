"""
DID 身份与消息签名 (Phase 2)

基于 did:key 的 Agent 身份与消息签名/验签。
didlite 为可选依赖，未安装时身份功能不可用。
"""

from typing import Any, Optional

try:
    import didlite
    _DIDLITE_AVAILABLE = True
except ImportError:
    _DIDLITE_AVAILABLE = False


class AgentIdentity:
    """
    Agent 身份 - 基于 did:key 的去中心化标识。

    使用示例:
        identity = AgentIdentity()
        print(identity.did)  # did:key:z6Mk...
        signed = identity.sign({"id": "123", "action": "Food_Order", ...})
    """

    def __init__(self, seed: Optional[bytes] = None) -> None:
        if not _DIDLITE_AVAILABLE:
            raise ImportError(
                "didlite is required for identity features. "
                "Install with: pip install open-a2a[identity]"
            )
        if seed:
            self._inner = didlite.AgentIdentity(seed=seed[:32])
        else:
            self._inner = didlite.AgentIdentity()

    @property
    def did(self) -> str:
        """did:key 标识符"""
        return self._inner.did

    def sign(self, payload: dict[str, Any]) -> str:
        """对消息进行签名，返回 JWS 紧凑格式"""
        return didlite.create_jws(self._inner, payload)

    @staticmethod
    def verify(jws: str) -> tuple[dict[str, Any], str]:
        """
        验证 JWS 签名，返回 (payload, signer_did)。

        Raises:
            Exception: 签名无效时
        """
        if not _DIDLITE_AVAILABLE:
            raise ImportError("didlite is required for verification")
        header, payload = didlite.verify_jws(jws)
        signer_did = header.get("kid", "")
        return payload, signer_did

    @staticmethod
    def is_available() -> bool:
        """检查 didlite 是否已安装"""
        return _DIDLITE_AVAILABLE


def parse_message(data: str) -> tuple[dict[str, Any], Optional[str]]:
    """
    解析消息：支持 JWS 或纯 JSON。

    返回 (payload, signer_did)。
    - 若为 JWS 且验签成功：signer_did 为签名者 DID
    - 若为纯 JSON：signer_did 为 None
    """
    import json

    data = data.strip()
    if not data:
        raise ValueError("Empty message")

    # JWS 紧凑格式通常以 eyJ 开头（base64url 的 {"）
    if _DIDLITE_AVAILABLE and data.startswith("eyJ") and "." in data:
        try:
            payload, signer_did = AgentIdentity.verify(data)
            return payload, signer_did
        except Exception:
            pass

    # 回退为纯 JSON
    payload = json.loads(data)
    return payload, None
