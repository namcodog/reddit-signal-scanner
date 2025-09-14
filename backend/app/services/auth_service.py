"""
Reddit Signal Scanner - 认证服务层

Linus原则："数据结构决定一切"
- 基于User模型的完美多租户设计
- 复用现有JWT双算法支持
- 数据库约束作为最后防线
- 简洁的业务逻辑，无特殊情况
"""

import logging
from datetime import datetime
from typing import Optional, Tuple, cast
from uuid import UUID

import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..core.jwt_handler import JWTHandler
from ..models.user import User
from ..schemas.auth import (
    AuthTokenResponse,
    LoginSession,
    UserLoginRequest,
    UserRegisterRequest,
    UserRegisterResponse,
)
from .login_security import login_security

# 配置日志
logger = logging.getLogger(__name__)


class AuthService:
    """认证服务类

    核心职责：
    1. 用户注册和认证
    2. 密码安全处理（BCrypt）
    3. JWT token管理
    4. 多租户用户管理

    设计原则：
    - 数据库约束优先于应用验证
    - 统一处理个人用户和企业用户
    - 无状态设计，便于水平扩展
    """

    def __init__(self) -> None:
        """初始化认证服务"""
        self.jwt_handler = JWTHandler()
        logger.info("认证服务初始化完成")

    async def register_user(
        self, registration_data: UserRegisterRequest, db: Optional[AsyncSession] = None
    ) -> UserRegisterResponse:
        """注册新用户

        Args:
            registration_data: 用户注册数据
            db: 数据库会话（可选，用于测试）

        Returns:
            UserRegisterResponse: 注册响应，包含用户信息和JWT tokens

        Raises:
            ValueError: 输入数据验证失败
            IntegrityError: 邮箱已存在或数据库约束失败
            Exception: 其他系统错误
        """
        logger.info(f"开始注册用户: {registration_data.email}")

        # 使用传入的会话或创建新会话
        if db is None:
            db_session = await get_session()
            try:
                return await self._register_user_impl(registration_data, db_session)
            finally:
                await db_session.close()
        else:
            return await self._register_user_impl(registration_data, db)

    async def _register_user_impl(
        self, registration_data: UserRegisterRequest, db: AsyncSession
    ) -> UserRegisterResponse:
        """用户注册实现（内部方法）"""

        # 1. 检查邮箱是否已存在
        await self._check_email_exists(registration_data.email, db)

        # 2. 生成密码哈希
        password_hash = self._hash_password(registration_data.password)

        # 3. 创建用户记录
        new_user = User(
            email=registration_data.email,
            password_hash=password_hash,
            # tenant_id 由数据库自动生成（个人用户）
            # email_verified 默认为 False
            # is_active 默认为 True
        )

        try:
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            logger.info(
                f"用户创建成功: user_id={new_user.id}, tenant_id={new_user.tenant_id}"
            )

        except IntegrityError as e:
            await db.rollback()
            logger.error(f"用户注册失败，数据库约束错误: {e}")

            # 检查具体的约束错误
            error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "ix_users_tenant_email_unique" in error_msg:
                raise ValueError("该邮箱地址已被注册")
            elif "ck_users_email_format" in error_msg:
                raise ValueError("邮箱格式不符合要求")
            elif "ck_users_password_bcrypt" in error_msg:
                raise ValueError("密码哈希格式错误")
            else:
                raise ValueError(f"用户注册失败: {error_msg}")

        # 4. 生成JWT tokens
        access_token = self.jwt_handler.create_access_token(
            user_id=str(new_user.id),
            tenant_id=str(new_user.tenant_id),
            email=str(new_user.email),
        )

        refresh_token = self.jwt_handler.create_refresh_token(
            user_id=str(new_user.id),
            tenant_id=str(new_user.tenant_id),
            email=str(new_user.email),
        )

        # 5. 构建响应
        response = UserRegisterResponse(
            user_id=cast(UUID, new_user.id),
            tenant_id=cast(UUID, new_user.tenant_id),
            email=str(new_user.email),
            email_verified=bool(new_user.email_verified),
            is_active=bool(new_user.is_active),
            created_at=new_user.created_at.isoformat(),
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=3600,  # 1小时，与JWT配置一致
        )

        logger.info(f"用户注册完成: {new_user.email}")
        return response

    async def authenticate_user(
        self, email: str, password: str, db: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """用户认证（预留给后续登录功能）

        Args:
            email: 用户邮箱
            password: 用户密码
            db: 数据库会话（可选）

        Returns:
            Optional[User]: 认证成功返回用户对象，失败返回None
        """
        logger.info(f"用户认证: {email}")

        if db is None:
            db_session = await get_session()
            try:
                return await self._authenticate_user_impl(email, password, db_session)
            finally:
                await db_session.close()
        else:
            return await self._authenticate_user_impl(email, password, db)

    async def _authenticate_user_impl(
        self, email: str, password: str, db: AsyncSession
    ) -> Optional[User]:
        """用户认证实现（内部方法）"""

        try:
            # 查找活跃用户
            stmt = select(User).where(
                User.email == email.strip().lower(), User.is_active.is_(True)
            )
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"用户不存在或未激活: {email}")
                return None

            # 验证密码
            if not self._verify_password(password, cast(str, user.password_hash)):
                logger.warning(f"密码验证失败: {email}")
                return None

            logger.info(f"用户认证成功: {email}")
            return user

        except SQLAlchemyError as e:
            logger.error(f"用户认证异常: {email}, error: {e}")
            return None

    async def login_user(
        self,
        login_data: UserLoginRequest,
        ip_address: str,
        user_agent: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> AuthTokenResponse:
        """用户登录

        统一的登录处理流程，消除特殊情况

        Args:
            login_data: 登录请求数据
            ip_address: 客户端IP地址
            user_agent: 用户代理字符串
            db: 数据库会话

        Returns:
            AuthTokenResponse: JWT token响应

        Raises:
            ValueError: 登录失败的各种情况
        """
        logger.info(f"用户登录尝试: {login_data.email} from {ip_address}")

        # 创建登录会话对象
        session = LoginSession(
            email=login_data.email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            login_time=datetime.utcnow(),
        )

        # 1. 检查频率限制
        allowed, retry_after = await login_security.check_rate_limit(
            login_data.email, ip_address
        )
        if not allowed:
            session.failure_reason = "rate_limited"
            await login_security.record_failed_attempt(session)
            raise ValueError(f"登录请求过于频繁，请{retry_after}秒后重试")

        # 2. 检查账户锁定
        locked, unlock_time = await login_security.check_account_lock(login_data.email)
        if locked:
            session.failure_reason = "account_locked"
            await login_security.record_failed_attempt(session)
            raise ValueError(f"账户已被锁定，将于{unlock_time}解锁")

        # 3. 检测可疑活动
        suspicious = await login_security.detect_suspicious_activity(
            login_data.email, ip_address
        )
        if suspicious:
            logger.warning(f"检测到可疑登录活动: {login_data.email}")
            # 这里可以触发额外验证，比如验证码或邮件确认

        # 4. 认证用户
        if db is None:
            db_session = await get_session()
            try:
                user = await self._authenticate_user_impl(
                    login_data.email, login_data.password, db_session
                )
            finally:
                await db_session.close()
        else:
            user = await self._authenticate_user_impl(
                login_data.email, login_data.password, db
            )

        if not user:
            session.failure_reason = "invalid_credentials"
            await login_security.record_failed_attempt(session)
            raise ValueError("邮箱或密码错误")

        # 5. 生成JWT tokens
        access_token = self.jwt_handler.create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=str(user.email),
        )

        refresh_token = self.jwt_handler.create_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=str(user.email),
        )

        # 6. 记录成功登录
        session.user_id = cast(UUID, user.id)
        session.success = True
        await login_security.record_successful_login(session)

        # 7. 构建响应
        response = AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=3600,  # 1小时
            user_id=cast(UUID, user.id),
            tenant_id=cast(UUID, user.tenant_id),
            email=str(user.email),
        )

        logger.info(f"用户登录成功: {user.email}")
        return response

    async def _check_email_exists(self, email: str, db: AsyncSession) -> None:
        """检查邮箱是否已存在

        Args:
            email: 邮箱地址
            db: 数据库会话

        Raises:
            ValueError: 邮箱已存在
        """
        email = email.strip().lower()

        stmt = select(User).where(User.email == email, User.is_active.is_(True))
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.warning(f"邮箱已存在: {email}")
            raise ValueError("该邮箱地址已被注册")

    @staticmethod
    def _hash_password(password: str) -> str:
        """生成BCrypt密码哈希

        Args:
            password: 明文密码

        Returns:
            str: BCrypt哈希值
        """
        # 使用BCrypt默认rounds (12)，平衡安全性和性能
        salt = bcrypt.gensalt()
        password_bytes = password.encode("utf-8")
        hashed = bcrypt.hashpw(password_bytes, salt)

        # 返回字符串格式，符合数据库约束
        return hashed.decode("utf-8")

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """验证密码

        Args:
            password: 明文密码
            password_hash: BCrypt哈希值

        Returns:
            bool: 密码是否匹配
        """
        try:
            password_bytes = password.encode("utf-8")
            hash_bytes = password_hash.encode("utf-8")
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except (ValueError, TypeError, OSError) as e:
            logger.error(f"密码验证异常: {e}")
            return False

    def validate_password_strength(self, password: str) -> Tuple[bool, list[str]]:
        """验证密码强度

        注意：主要验证已在Pydantic Schema中实现
        这里提供独立验证功能，用于其他场景

        Args:
            password: 待验证密码

        Returns:
            Tuple[bool, list[str]]: (是否通过, 错误信息列表)
        """
        from ..schemas.auth import validate_password_strength_standalone

        return validate_password_strength_standalone(password)

    def validate_email_format(self, email: str) -> Tuple[bool, str]:
        """验证邮箱格式

        Args:
            email: 待验证邮箱

        Returns:
            Tuple[bool, str]: (是否通过, 错误信息)
        """
        from ..schemas.auth import validate_email_format_standalone

        return validate_email_format_standalone(email)

    async def get_user_by_id(
        self, user_id: UUID, db: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """根据ID获取用户（工具方法）

        Args:
            user_id: 用户ID
            db: 数据库会话（可选）

        Returns:
            Optional[User]: 用户对象或None
        """
        if db is None:
            db_session = await get_session()
            try:
                return await self._get_user_by_id_impl(user_id, db_session)
            finally:
                await db_session.close()
        else:
            return await self._get_user_by_id_impl(user_id, db)

    async def _get_user_by_id_impl(
        self, user_id: UUID, db: AsyncSession
    ) -> Optional[User]:
        """根据ID获取用户实现"""
        try:
            stmt = select(User).where(User.id == user_id, User.is_active.is_(True))
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"获取用户异常: user_id={user_id}, error: {e}")
            return None

    async def get_user_by_email(
        self, email: str, db: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """根据邮箱获取用户（工具方法）

        Args:
            email: 用户邮箱
            db: 数据库会话（可选）

        Returns:
            Optional[User]: 用户对象或None
        """
        if db is None:
            db_session = await get_session()
            try:
                return await self._get_user_by_email_impl(email, db_session)
            finally:
                await db_session.close()
        else:
            return await self._get_user_by_email_impl(email, db)

    async def _get_user_by_email_impl(
        self, email: str, db: AsyncSession
    ) -> Optional[User]:
        """根据邮箱获取用户实现"""
        try:
            email = email.strip().lower()
            stmt = select(User).where(User.email == email, User.is_active.is_(True))
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"获取用户异常: email={email}, error: {e}")
            return None


# 全局认证服务实例
auth_service = AuthService()


# ===== 快捷函数 =====


async def register_new_user(
    registration_data: UserRegisterRequest, db: Optional[AsyncSession] = None
) -> UserRegisterResponse:
    """注册新用户的快捷函数

    Args:
        registration_data: 注册数据
        db: 数据库会话（可选）

    Returns:
        UserRegisterResponse: 注册响应
    """
    return await auth_service.register_user(registration_data, db)


async def authenticate_user_credentials(
    email: str, password: str, db: Optional[AsyncSession] = None
) -> Optional[User]:
    """用户认证的快捷函数

    Args:
        email: 用户邮箱
        password: 用户密码
        db: 数据库会话（可选）

    Returns:
        Optional[User]: 认证成功返回用户，失败返回None
    """
    return await auth_service.authenticate_user(email, password, db)


async def login_user(
    login_data: UserLoginRequest,
    ip_address: str,
    user_agent: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> AuthTokenResponse:
    """用户登录的快捷函数

    Args:
        login_data: 登录请求数据
        ip_address: 客户端IP地址
        user_agent: 用户代理字符串
        db: 数据库会话（可选）

    Returns:
        AuthTokenResponse: JWT token响应
    """
    return await auth_service.login_user(login_data, ip_address, user_agent, db)


def validate_password_strength_quick(password: str) -> Tuple[bool, list[str]]:
    """密码强度验证快捷函数

    Args:
        password: 待验证密码

    Returns:
        Tuple[bool, list[str]]: (是否通过, 错误信息列表)
    """
    return auth_service.validate_password_strength(password)


def validate_email_format_quick(email: str) -> Tuple[bool, str]:
    """邮箱格式验证快捷函数

    Args:
        email: 待验证邮箱

    Returns:
        Tuple[bool, str]: (是否通过, 错误信息)
    """
    return auth_service.validate_email_format(email)
