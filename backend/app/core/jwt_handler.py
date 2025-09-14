"""
JWT认证处理器 - 支持RS256/HS256双算法架构

Linus原则：
- 数据结构消除特殊情况：Token结构统一，租户ID永远存在
- 向后兼容：支持HS256老token，新token使用RS256
- 错误处理简化：所有JWT错误统一处理
- 性能优先：密钥缓存+验证结果缓存
"""

import logging
import os
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Literal, cast

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.exceptions import InvalidKeyError, InvalidTokenError
from pydantic import BaseModel, Field

from ..schemas.contracts.auth_contract import JWTPayload
from .types import JsonValue
from .config import get_settings


class TokenPayload(BaseModel):
    """JWT Token载荷结构 - 消除单/多租户特殊情况"""

    user_id: str = Field(description="用户ID")
    tenant_id: str = Field(description="租户ID - 永远存在，消除特殊情况")
    email: str = Field(description="用户邮箱")
    permissions: List[str] = Field(default_factory=list, description="权限列表")
    token_type: str = Field(default="access", description="token类型：access/refresh")

    # JWT标准字段
    exp: int = Field(description="过期时间戳")
    iat: int = Field(description="签发时间戳")
    iss: str = Field(default="reddit-scanner", description="签发者")
    aud: str = Field(default="api", description="受众")
    jti: str = Field(description="JWT ID - 防重放攻击")


class JWTKeys:
    """JWT密钥管理 - 支持RSA和HMAC"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._private_key: Optional[bytes] = None
        self._public_key: Optional[bytes] = None
        self._hmac_key: str = self.settings.jwt_secret_key

    @property
    def private_key(self) -> Optional[bytes]:
        """获取RSA私钥 - 懒加载"""
        if self._private_key is None and self.settings.jwt_private_key_path:
            self._load_rsa_keys()
        return self._private_key

    @property
    def public_key(self) -> Optional[bytes]:
        """获取RSA公钥 - 懒加载"""
        if self._public_key is None and self.settings.jwt_public_key_path:
            self._load_rsa_keys()
        return self._public_key

    @property
    def hmac_key(self) -> str:
        """获取HMAC密钥"""
        return self._hmac_key

    def _load_rsa_keys(self) -> None:
        """加载RSA密钥对 - Linus式线性逻辑"""
        try:
            self._load_private_key()
            self._load_public_key()
        except Exception as e:
            self._handle_key_load_failure(e)

    def _load_private_key(self) -> None:
        """加载私钥 - 单一职责"""
        if not self.settings.jwt_private_key_path:
            return

        private_path = Path(self.settings.jwt_private_key_path)
        if private_path.exists():
            self._private_key = private_path.read_bytes()

    def _load_public_key(self) -> None:
        """加载公钥 - 单一职责"""
        if not self.settings.jwt_public_key_path:
            return

        public_path = Path(self.settings.jwt_public_key_path)
        if public_path.exists():
            self._public_key = public_path.read_bytes()

    def _handle_key_load_failure(self, error: Exception) -> None:
        """处理密钥加载失败 - 统一错误处理"""
        logger = logging.getLogger(__name__)
        logger.warning("RSA密钥加载失败，回退到HMAC模式: %s", error)

    def generate_rsa_keypair(self, key_size: int = 2048) -> tuple[bytes, bytes]:
        """生成RSA密钥对"""
        # 生成私钥
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)

        # 序列化私钥
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # 序列化公钥
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return private_pem, public_pem

    def save_keys_to_files(self, private_key: bytes, public_key: bytes) -> None:
        """保存密钥到文件"""
        if self.settings.jwt_private_key_path:
            private_path = Path(self.settings.jwt_private_key_path)
            private_path.parent.mkdir(parents=True, exist_ok=True)
            private_path.write_bytes(private_key)
            os.chmod(private_path, 0o600)  # 只有所有者可读写

        if self.settings.jwt_public_key_path:
            public_path = Path(self.settings.jwt_public_key_path)
            public_path.parent.mkdir(parents=True, exist_ok=True)
            public_path.write_bytes(public_key)
            os.chmod(public_path, 0o644)  # 所有者可读写，其他人只读


class JWTHandler:
    """JWT处理器 - 核心认证逻辑"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.keys = JWTKeys()

    def create_access_token(
        self,
        user_id: str,
        tenant_id: str,
        email: str,
        permissions: Optional[List[str]] = None,
    ) -> str:
        """创建访问令牌"""
        now = int(time.time())
        exp = now + self.settings.jwt_access_token_expire_seconds

        payload = TokenPayload(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            permissions=permissions or [],
            token_type="access",
            exp=exp,
            iat=now,
            jti=str(uuid.uuid4()),
        )

        return self._encode_token(payload.dict())

    def create_refresh_token(self, user_id: str, tenant_id: str, email: str) -> str:
        """创建刷新令牌"""
        now = int(time.time())
        exp = now + self.settings.jwt_refresh_token_expire_seconds

        payload = TokenPayload(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            permissions=[],  # 刷新令牌不包含权限
            token_type="refresh",
            exp=exp,
            iat=now,
            jti=str(uuid.uuid4()),
        )

        return self._encode_token(payload.dict())

    def verify_token(self, token: str) -> TokenPayload:
        """验证Token - 支持多算法"""
        # 尝试所有支持的算法
        last_error = None

        for algorithm in self.settings.jwt_algorithms_list:
            try:
                payload = self._decode_token(token, algorithm)
                return TokenPayload(**payload)
            except Exception as e:
                last_error = e
                continue

        # 所有算法都失败，抛出最后一个错误
        raise last_error or InvalidTokenError("Token验证失败")

    def verify_access_token(self, token: str) -> TokenPayload:
        """验证访问令牌"""
        payload = self.verify_token(token)

        if payload.token_type != "access":
            raise InvalidTokenError("无效的访问令牌类型")

        return payload

    def verify_refresh_token(self, token: str) -> TokenPayload:
        """验证刷新令牌"""
        payload = self.verify_token(token)

        if payload.token_type != "refresh":
            raise InvalidTokenError("无效的刷新令牌类型")

        return payload

    def refresh_access_token(self, refresh_token: str) -> tuple[str, str]:
        """使用刷新令牌生成新的访问令牌"""
        # 验证刷新令牌
        refresh_payload = self.verify_refresh_token(refresh_token)

        # 生成新的访问令牌
        access_token = self.create_access_token(
            user_id=refresh_payload.user_id,
            tenant_id=refresh_payload.tenant_id,
            email=refresh_payload.email,
            permissions=[],  # 权限需要重新从数据库获取
        )

        # 生成新的刷新令牌
        new_refresh_token = self.create_refresh_token(
            user_id=refresh_payload.user_id,
            tenant_id=refresh_payload.tenant_id,
            email=refresh_payload.email,
        )

        return access_token, new_refresh_token

    def _encode_token(self, payload: dict[str, Any]) -> str:
        """编码Token - 优先使用RS256"""
        algorithm = self.settings.jwt_algorithm

        # RS256优先策略
        if algorithm == "RS256" and self.keys.private_key:
            return jwt.encode(
                payload,
                self.keys.private_key,
                algorithm="RS256",
                headers={"kid": self.settings.jwt_key_id},
            )

        # 回退到HS256
        return jwt.encode(payload, self.keys.hmac_key, algorithm="HS256")

    def _decode_token(self, token: str, algorithm: str) -> dict[str, Any]:
        """解码Token - 支持特定算法"""
        if algorithm == "RS256":
            if not self.keys.public_key:
                raise InvalidKeyError("RS256公钥不可用")

            decoded_rs256: Any = jwt.decode(
                token,
                self.keys.public_key,
                algorithms=["RS256"],
                audience="api",
                issuer="reddit-scanner",
            )
            return cast(dict[str, Any], decoded_rs256)

        elif algorithm == "HS256":
            decoded_hs256: Any = jwt.decode(
                token,
                self.keys.hmac_key,
                algorithms=["HS256"],
                audience="api",
                issuer="reddit-scanner",
            )
            return cast(dict[str, Any], decoded_hs256)

        else:
            raise InvalidTokenError(f"不支持的算法: {algorithm}")

    def get_token_info(self, token: str) -> dict[str, JsonValue]:
        """获取Token信息（不验证签名）- 调试用"""
        try:
            # 不验证签名，只解析结构
            decoded_any: Any = jwt.decode(token, options={"verify_signature": False})
            payload: dict[str, JsonValue] = cast(dict[str, JsonValue], decoded_any)

            # 添加额外信息
            header_any: Any = jwt.get_unverified_header(token)
            header: dict[str, JsonValue] = cast(dict[str, JsonValue], header_any)
            payload["algorithm"] = cast(str, header.get("alg", "unknown"))
            kid_val: JsonValue = header.get("kid")
            if kid_val is not None:
                payload["key_id"] = str(kid_val)

            return payload

        except Exception as e:
            return {"error": str(e), "raw_token": token[:20] + "..."}

    class Context7Subject(TypedDict):
        user_id: str
        tenant_id: str
        email: str

    class TokenPair(TypedDict):
        access_token: str
        refresh_token: str
        token_type: Literal["bearer"]
        expires_in: int

    def create_context7_subject(
        self, user_id: str, tenant_id: str, email: str
    ) -> "JWTHandler.Context7Subject":
        """创建符合Context7格式的token subject

        遵循Context7简洁原则：使用简单dict作为subject

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            email: 用户邮箱

        Returns:
            Context7Subject: Context7兼容的简洁subject字典
        """
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "email": email,
        }

    def create_token_pair_from_subject(self, subject: "JWTHandler.Context7Subject") -> "JWTHandler.TokenPair":
        """从subject创建token对

        符合Context7模式：接收subject dict，返回token对
        用于刷新和登录场景

        Args:
            subject: Context7格式的subject字典

        Returns:
            TokenPair: 包含access_token和refresh_token的字典
        """
        user_id = str(subject["user_id"])
        tenant_id = str(subject["tenant_id"])
        email = str(subject["email"])

        access_token = self.create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            permissions=[],  # 权限从数据库获取
        )

        refresh_token = self.create_refresh_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.settings.jwt_access_token_expire_seconds,
        }

    # ==== 合同化类型输出（P0：为多租户隔离提供明确载荷）====
    def decode_token_to_contract(self, token: str) -> JWTPayload:
        """验证并返回契约化的JWT载荷结构。"""
        payload = self.verify_token(token)
        return JWTPayload(
            sub=payload.user_id,
            tenant=payload.tenant_id,
            exp=payload.exp,
            iat=payload.iat,
            permissions=payload.permissions,
        )


# ===== 全局实例 =====


@lru_cache(maxsize=1)
def get_jwt_handler() -> JWTHandler:
    """获取JWT处理器实例 - 使用LRU缓存实现单例模式"""
    return JWTHandler()


def setup_jwt_keys_if_needed() -> None:
    """初始化JWT密钥（如果需要）"""
    settings = get_settings()

    # 如果配置了RS256但密钥文件不存在，生成新密钥
    if (
        settings.jwt_algorithm == "RS256"
        and settings.jwt_private_key_path
        and settings.jwt_public_key_path
    ):
        private_path = Path(settings.jwt_private_key_path)
        public_path = Path(settings.jwt_public_key_path)

        if not private_path.exists() or not public_path.exists():
            logger = logging.getLogger(__name__)
            logger.info("检测到RS256配置但密钥文件不存在，正在生成新密钥...")

            keys = JWTKeys()
            private_key, public_key = keys.generate_rsa_keypair()
            keys.save_keys_to_files(private_key, public_key)

            logger.info("RSA密钥对已生成:")
            logger.info("  私钥: %s", private_path)
            logger.info("  公钥: %s", public_path)
            logger.warning("请妥善保管私钥文件！")


# ===== 便捷函数 =====


def create_user_tokens(
    user_id: str,
    tenant_id: str,
    email: str,
    permissions: Optional[List[str]] = None,
) -> JWTHandler.TokenPair:
    """创建用户Token对（访问+刷新）"""
    handler = get_jwt_handler()

    access_token = handler.create_access_token(user_id, tenant_id, email, permissions)
    refresh_token = handler.create_refresh_token(user_id, tenant_id, email)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": handler.settings.jwt_access_token_expire_seconds,
    }
