"""
DID 身份与消息签名/验签 (Phase 2)

MVP 最优解（现代、可互操作）：
- DID method: did:key
- Signature: JWS (Ed25519 / EdDSA)
- Canonical JSON hashing for stable interoperability
- Meta proof: sign meta hash to prove ownership (optional but recommended)

didlite 为可选依赖，未安装时身份功能不可用。
"""

import base64
import hashlib
import json
from typing import Any, Optional, Tuple

try:
    import didlite
    _DIDLITE_AVAILABLE = True
except ImportError:
    _DIDLITE_AVAILABLE = False


class IdentityNotAvailable(RuntimeError):
    pass


def identity_available() -> bool:
    return _DIDLITE_AVAILABLE


def require_identity() -> None:
    """
    Raise a consistent error when identity features are required but didlite is missing.
    """
    if not _DIDLITE_AVAILABLE:
        raise IdentityNotAvailable(
            "identity features require didlite. Install with: pip install open-a2a[identity]"
        )


class AgentIdentity:
    """
    Agent 身份 - 基于 did:key 的去中心化标识。

    使用示例:
        identity = AgentIdentity()
        print(identity.did)  # did:key:z6Mk...
        signed = identity.sign({"id": "123", "action": "Food_Order", ...})
    """

    def __init__(self, seed: Optional[bytes] = None) -> None:
        require_identity()
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


def canonical_json_bytes(obj: Any) -> bytes:
    """
    Deterministic JSON serialization for signing/verifying.

    Rules (MVP):
    - UTF-8
    - separators without spaces
    - sorted keys
    - ensure_ascii=False
    """
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def sha256_b64url(data: bytes) -> str:
    return b64url_nopad(hashlib.sha256(data).digest())


def build_meta_proof(
    identity: "AgentIdentity",
    meta: dict[str, Any],
    *,
    created_at: Optional[str] = None,
    purpose: str = "meta",
) -> dict[str, Any]:
    """
    Create a proof object for a meta document.

    We sign a stable hash of canonical JSON(meta_without_proof) to avoid cross-language
    canonicalization issues inside JWS libraries.
    """
    meta_to_sign = dict(meta)
    meta_to_sign.pop("proof", None)
    meta_canon = canonical_json_bytes(meta_to_sign)
    meta_hash = sha256_b64url(meta_canon)

    payload = {
        "purpose": purpose,
        "meta_hash_sha256_b64url": meta_hash,
        "created_at": created_at or "",
        "did": identity.did,
    }
    jws = identity.sign(payload)
    return {
        "type": "jws",
        "alg": "EdDSA",
        "purpose": purpose,
        "created_at": payload["created_at"],
        "jws": jws,
        "meta_hash_sha256_b64url": meta_hash,
        "did": identity.did,
    }


def verify_meta_proof(meta: dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
    """
    Verify meta.proof if present.

    Returns:
      (ok, reason, signer_did)
    """
    proof = meta.get("proof")
    if not proof:
        return False, "missing_proof", None
    if not isinstance(proof, dict):
        return False, "invalid_proof_type", None

    jws = proof.get("jws")
    if not isinstance(jws, str) or not jws:
        return False, "missing_jws", None

    if not _DIDLITE_AVAILABLE:
        return False, "identity_not_available", None

    try:
        payload, signer_did = AgentIdentity.verify(jws)
    except Exception:
        return False, "invalid_signature", None

    # Recompute hash from meta without proof
    meta_to_check = dict(meta)
    meta_to_check.pop("proof", None)
    meta_hash = sha256_b64url(canonical_json_bytes(meta_to_check))
    expected = payload.get("meta_hash_sha256_b64url")
    if expected != meta_hash:
        return False, "hash_mismatch", signer_did

    # Optional consistency checks
    did_in_meta = meta.get("did")
    did_in_payload = payload.get("did")
    if did_in_meta and did_in_payload and did_in_meta != did_in_payload:
        return False, "did_mismatch", signer_did

    return True, "ok", signer_did
