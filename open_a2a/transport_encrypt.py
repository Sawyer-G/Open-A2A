"""
Relay 端到端负载加密（E2E）

在传输层之上对消息体进行加解密，Relay/NATS 仅能看到密文。
通信双方需共享同一密钥（或通过 OPEN_A2A_RELAY_PAYLOAD_SECRET 配置）。
可与 RelayClientTransport 或 NatsTransportAdapter 组合使用。
"""

from typing import Awaitable, Callable, Optional

from open_a2a.transport import MessageSubscription, TransportAdapter

try:
    import base64 as b64

    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore

# 固定 salt，保证同一 shared_secret 在不同进程中得到相同 Fernet key
_E2E_PBKDF2_SALT = b"open-a2a-relay-e2e-v1"


def _derive_fernet_key(shared_secret: bytes) -> bytes:
    if not _FERNET_AVAILABLE:
        raise ImportError("cryptography is required. Install with: pip install open-a2a[e2e]")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=_E2E_PBKDF2_SALT, iterations=100_000
    )
    key = kdf.derive(shared_secret)
    return b64.urlsafe_b64encode(key)


class _EncryptedSubscription(MessageSubscription):
    def __init__(self, inner_sub: MessageSubscription) -> None:
        self._inner = inner_sub

    async def unsubscribe(self) -> None:
        await self._inner.unsubscribe()


class EncryptedTransportAdapter(TransportAdapter):
    """
    对底层传输的消息体进行加解密的包装器（E2E：Relay 不可见明文）。

    底层传输（如 RelayClientTransport）仅收发密文；加解密在本地完成。
    通信双方必须使用相同的 shared_secret（或通过环境变量 OPEN_A2A_RELAY_PAYLOAD_SECRET 配置）。
    """

    def __init__(
        self,
        inner: TransportAdapter,
        shared_secret: Optional[bytes] = None,
    ) -> None:
        if not _FERNET_AVAILABLE:
            raise ImportError("cryptography is required. Install with: pip install open-a2a[e2e]")
        self._inner = inner
        secret = shared_secret
        if secret is None:
            import os
            env_secret = os.getenv("OPEN_A2A_RELAY_PAYLOAD_SECRET", "").strip()
            if not env_secret:
                raise ValueError("shared_secret or OPEN_A2A_RELAY_PAYLOAD_SECRET must be set")
            secret = env_secret.encode("utf-8")
        self._fernet = Fernet(_derive_fernet_key(secret))

    async def connect(self) -> None:
        await self._inner.connect()

    async def disconnect(self) -> None:
        await self._inner.disconnect()

    async def publish(self, subject: str, data: bytes) -> None:
        encrypted = self._fernet.encrypt(data)
        await self._inner.publish(subject, encrypted)

    async def subscribe(
        self,
        subject: str,
        cb: Callable[[bytes], Awaitable[None]],
    ) -> MessageSubscription:
        async def decrypted_cb(encrypted: bytes) -> None:
            try:
                plain = self._fernet.decrypt(encrypted)
            except InvalidToken:
                return  # 密钥不一致或篡改，静默丢弃
            await cb(plain)

        inner_sub = await self._inner.subscribe(subject, decrypted_cb)
        return _EncryptedSubscription(inner_sub)
