"""
Token黑名单服务 - 严格遵循Context7最佳实践

基于Flask-JWT-Extended的成熟模式，适配到FastAPI:
- 使用JTI作为唯一标识符
- Redis主存储 + 可选数据库审计
- 简洁的存在性检查逻辑
- TTL自动过期机制
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from ..core.redis_client import get_redis_client
from redis.exceptions import RedisError
from ..schemas.auth import BlacklistedToken


class TokenBlacklistService:
    """Token黑名单服务

    严格遵循Context7 Flask-JWT-Extended模式:
    1. 使用JTI作为主键
    2. Redis存储，TTL自动清理
    3. 简洁的exists检查
    4. 支持access和refresh token
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    async def is_token_revoked(self, jti: str) -> bool:
        """检查token是否被撤销

        对应Context7的 check_if_token_is_revoked 回调

        Args:
            jti: JWT唯一标识符

        Returns:
            bool: True表示已撤销，False表示有效
        """
        try:
            redis_client = await get_redis_client()
            return await redis_client.exists(f"blocklist:{jti}")
        except RedisError:
            # Context7模式：Redis错误时保守处理，假设未撤销
            return False

    async def revoke_token(
        self,
        jti: str,
        token_type: str,
        expires_delta: int,
        user_id: Optional[str] = None,
    ) -> bool:
        """撤销token

        对应Context7的logout端点逻辑

        Args:
            jti: JWT唯一标识符
            token_type: token类型 ("access" 或 "refresh")
            expires_delta: token剩余有效期（秒）
            user_id: 可选的用户ID，用于审计

        Returns:
            bool: 撤销是否成功
        """
        try:
            redis_client = await get_redis_client()

            # Context7模式：存储空字符串，使用TTL自动清理
            redis_key = f"blocklist:{jti}"

            # TTL设置为token剩余有效期
            ttl = max(expires_delta, 300)  # 最少5分钟，防止重放攻击

            await redis_client.set(redis_key, "", ttl=ttl)

            self.logger.info("Token已撤销: jti=%s, type=%s, ttl=%d", jti, token_type, ttl)
            return True

        except RedisError as e:
            self.logger.error("Token撤销失败: %s", str(e))
            return False

    async def revoke_token_with_audit(self, blacklist_record: BlacklistedToken) -> bool:
        """撤销token并记录审计日志

        对应Context7的数据库存储模式

        Args:
            blacklist_record: 完整的黑名单记录

        Returns:
            bool: 撤销是否成功
        """
        try:
            redis_client = await get_redis_client()

            # 1. Redis存储（主要检查）
            redis_key = f"blocklist:{blacklist_record.jti}"

            # 计算TTL
            now = datetime.now(timezone.utc)
            expires_at = blacklist_record.expires_at

            # Pydantic确保expires_at是datetime对象
            ttl = max(int((expires_at - now).total_seconds()), 300)

            await redis_client.set(redis_key, "", ttl=ttl)

            # 2. 审计日志存储（可选）
            audit_key = f"audit:token:{blacklist_record.jti}"
            audit_data = json.dumps(blacklist_record.dict(), default=str)
            await redis_client.set(audit_key, audit_data, ttl=ttl)

            self.logger.info(
                "Token已撤销(含审计): jti=%s, user_id=%s, reason=%s",
                blacklist_record.jti,
                blacklist_record.user_id,
                blacklist_record.reason,
            )
            return True

        except RedisError as e:
            self.logger.error("Token撤销(含审计)失败: %s", str(e))
            return False

    async def revoke_all_user_tokens(
        self, user_id: str, reason: str = "logout_all_devices"
    ) -> int:
        """撤销用户所有token

        对应Context7的全局撤销模式

        Args:
            user_id: 用户ID
            reason: 撤销原因

        Returns:
            int: 撤销的token数量
        """
        try:
            redis_client = await get_redis_client()

            # Context7模式：使用用户级别的全局撤销标记
            global_key = f"user_revoked:{user_id}"
            revoke_data = {
                "revoked_at": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
            }

            # 设置较长的TTL（30天，覆盖最长refresh token期限）
            await redis_client.set(
                global_key, json.dumps(revoke_data), ttl=30 * 24 * 3600  # 30天
            )

            self.logger.info(
                "用户所有token已全局撤销: user_id=%s, reason=%s",
                user_id,
                reason,
            )

            # 返回1表示全局撤销生效
            return 1

        except RedisError as e:
            self.logger.error("用户token全局撤销失败: %s", str(e))
            return 0

    async def is_user_globally_revoked(self, user_id: str) -> bool:
        """检查用户是否被全局撤销

        Args:
            user_id: 用户ID

        Returns:
            bool: 是否被全局撤销
        """
        try:
            redis_client = await get_redis_client()
            global_key = f"user_revoked:{user_id}"
            return await redis_client.exists(global_key)
        except RedisError:
            return False


# ===== 全局实例 =====

_token_blacklist_service: Optional[TokenBlacklistService] = None


def get_token_blacklist_service() -> TokenBlacklistService:
    """获取token黑名单服务单例"""
    global _token_blacklist_service
    if _token_blacklist_service is None:
        _token_blacklist_service = TokenBlacklistService()
    return _token_blacklist_service
