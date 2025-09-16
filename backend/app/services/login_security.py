"""
Reddit Signal Scanner - 登录安全服务

Linus原则："简单胜过聪明"
- 统一的频率限制机制
- Redis缓存实现高性能检查
- 清晰的锁定和解锁逻辑
- 无特殊情况的处理流程
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from ..core.redis_client import get_redis_client
from redis.exceptions import RedisError
from ..schemas.auth import LoginSession

# 配置日志
logger = logging.getLogger(__name__)

# 安全配置常量（可从配置文件读取）
LOGIN_RATE_LIMIT = 5  # 每分钟最大尝试次数
RATE_LIMIT_WINDOW = 60  # 限制窗口（秒）
ACCOUNT_LOCK_THRESHOLD = 10  # 账户锁定阈值
ACCOUNT_LOCK_DURATION = 1800  # 锁定时长（秒，30分钟）


class LoginSecurityService:
    """登录安全服务

    职责：
    1. 登录频率限制
    2. 账户锁定机制
    3. 异常检测
    4. 审计日志记录
    """

    def __init__(self) -> None:
        """初始化登录安全服务"""
        self.redis = None  # 将在使用时异步获取
        logger.info("登录安全服务初始化完成")

    async def check_rate_limit(
        self, email: str, ip_address: str
    ) -> tuple[bool, Optional[int]]:
        """检查登录频率限制

        Args:
            email: 登录邮箱
            ip_address: 客户端IP

        Returns:
            tuple[bool, Optional[int]]: (是否允许登录, 重试等待秒数)
        """
        # 使用邮箱和IP组合作为限制键，防止分布式攻击
        rate_key = f"login_rate:{email}:{ip_address}"

        try:
            # 获取Redis客户端
            redis = await get_redis_client()

            # 获取当前尝试次数
            current_attempts = await redis.get(rate_key)

            if current_attempts is None:
                # 首次尝试，设置计数器
                await redis.set(rate_key, 1, RATE_LIMIT_WINDOW)
                return True, None

            attempts = int(current_attempts)

            if attempts >= LOGIN_RATE_LIMIT:
                # 超过频率限制
                ttl = await redis.ttl(rate_key)
                logger.warning(f"登录频率限制触发: {email} from {ip_address}, 剩余{ttl}秒")
                return False, ttl

            # 增加尝试次数
            await redis.incr(rate_key)
            return True, None

        except (RedisError, ValueError, TypeError) as e:
            logger.error(f"频率限制检查失败: {e}")
            # 失败时允许登录，避免Redis故障影响正常服务
            return True, None

    async def check_account_lock(self, email: str) -> tuple[bool, Optional[datetime]]:
        """检查账户锁定状态

        Args:
            email: 用户邮箱

        Returns:
            tuple[bool, Optional[datetime]]: (是否被锁定, 解锁时间)
        """
        lock_key = f"account_lock:{email}"

        try:
            redis = await get_redis_client()
            lock_info = await redis.get(lock_key)

            if lock_info:
                # 账户被锁定
                unlock_timestamp = float(lock_info)
                unlock_time = datetime.fromtimestamp(unlock_timestamp)

                if datetime.now() < unlock_time:
                    logger.warning(f"账户被锁定: {email}, 解锁时间: {unlock_time}")
                    return True, unlock_time
                else:
                    # 锁定已过期，删除键
                    await redis.delete(lock_key)

            return False, None

        except (RedisError, ValueError) as e:
            logger.error(f"账户锁定检查失败: {e}")
            # 失败时允许登录
            return False, None

    async def record_failed_attempt(self, session: LoginSession) -> None:
        """记录失败的登录尝试

        Args:
            session: 登录会话信息
        """
        attempt_key = f"login_attempts:{session.email}"

        try:
            # 增加失败次数
            redis = await get_redis_client()
            current_attempts = await redis.get(attempt_key)

            if current_attempts is None:
                await redis.set(attempt_key, 1, 3600)  # 1小时过期
                attempts = 1
            else:
                attempts = await redis.incr(attempt_key)

            # 检查是否需要锁定账户
            if attempts >= ACCOUNT_LOCK_THRESHOLD:
                await self._lock_account(session.email)
                logger.warning(f"账户因多次失败尝试被锁定: {session.email}")

            # 记录审计日志（这里可以写入数据库）
            logger.info(
                f"登录失败记录: email={session.email}, ip={session.ip_address}, "
                f"reason={session.failure_reason}, attempts={attempts}"
            )

        except (RedisError, ValueError, TypeError) as e:
            logger.error(f"记录失败尝试时出错: {e}")

    async def record_successful_login(self, session: LoginSession) -> None:
        """记录成功的登录

        Args:
            session: 登录会话信息
        """
        try:
            # 清除失败计数
            attempt_key = f"login_attempts:{session.email}"
            redis = await get_redis_client()
            await redis.delete(attempt_key)

            # 记录最后登录信息（用于异常检测）
            last_login_key = f"last_login:{session.email}"
            login_info = {
                "ip": session.ip_address,
                "time": session.login_time.isoformat(),
                "user_agent": session.user_agent,
            }
            await redis.set(last_login_key, str(login_info), 86400 * 30)  # 保留30天

            # 记录审计日志
            logger.info(
                f"登录成功记录: user_id={session.user_id}, email={session.email}, "
                f"ip={session.ip_address}"
            )

        except (RedisError, ValueError, TypeError) as e:
            logger.error(f"记录成功登录时出错: {e}")

    async def _lock_account(self, email: str) -> None:
        """锁定账户

        Args:
            email: 用户邮箱
        """
        lock_key = f"account_lock:{email}"
        unlock_time = datetime.now() + timedelta(seconds=ACCOUNT_LOCK_DURATION)

        try:
            redis = await get_redis_client()
            await redis.set(
                lock_key, str(unlock_time.timestamp()), ACCOUNT_LOCK_DURATION
            )
            logger.info(f"账户已锁定: {email}, 解锁时间: {unlock_time}")

        except (RedisError, ValueError, TypeError) as e:
            logger.error(f"锁定账户失败: {e}")

    async def detect_suspicious_activity(self, email: str, ip_address: str) -> bool:
        """检测可疑登录活动

        简单的异常检测：
        - IP地址突变
        - 短时间内多个IP登录

        Args:
            email: 用户邮箱
            ip_address: 当前登录IP

        Returns:
            bool: 是否检测到可疑活动
        """
        try:
            # 获取最后登录信息
            last_login_key = f"last_login:{email}"
            redis = await get_redis_client()
            last_login = await redis.get(last_login_key)

            if last_login:
                # 这里可以实现更复杂的异常检测逻辑
                # 比如：地理位置变化、设备指纹变化等
                pass

            # 检查短时间内多IP登录
            ip_key = f"login_ips:{email}"
            await redis.sadd(ip_key, ip_address)
            await redis.expire(ip_key, 300)  # 5分钟窗口

            ip_count = await redis.scard(ip_key)
            if ip_count > 3:  # 5分钟内超过3个不同IP
                logger.warning(f"检测到可疑活动: {email} 有 {ip_count} 个不同IP登录")
                return True

            return False

        except (RedisError, ValueError, TypeError) as e:
            logger.error(f"可疑活动检测失败: {e}")
            return False


# 全局实例
login_security = LoginSecurityService()
