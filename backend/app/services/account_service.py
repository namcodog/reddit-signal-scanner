"""
Reddit Signal Scanner - 用户账户管理服务层

遵循Linus原则: "数据结构决定一切"
- 基于现有User模型的完美复用
- 统一的多租户数据隔离
- 数据库约束作为最后防线
- 简洁的业务逻辑，无特殊情况
遵循CLAUDE.md零容忍规范: 100%类型安全，79字符限制，日志%占位符
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional, cast
from uuid import UUID

import bcrypt
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..core.sqlalchemy_typing import as_bool_clause
from ..models.user import User
from ..schemas.user_management import (
    PasswordChangeRequest,
    UserAccountStatusResponse,
    UserProfileResponse,
    UserUpdateRequest,
)

# 配置日志
logger = logging.getLogger(__name__)


class AccountService:
    """
    用户账户管理服务

    提供用户个人信息管理、密码修改、账户状态查询等功能
    严格遵循多租户隔离和企业级安全要求
    """

    def __init__(self) -> None:
        """初始化账户管理服务"""
        logger.info("账户管理服务初始化完成")

    async def get_user_profile(
        self, user_id: UUID, tenant_id: UUID, db: Optional[AsyncSession] = None
    ) -> Optional[UserProfileResponse]:
        """
        获取用户个人信息 - GET /users/me

        Args:
            user_id: 用户ID
            tenant_id: 租户ID（多租户隔离）
            db: 数据库会话（可选）

        Returns:
            Optional[UserProfileResponse]: 用户信息或None
        """
        if db is None:
            db_session = await get_session()
            try:
                return await self._get_user_profile_impl(user_id, tenant_id, db_session)
            finally:
                await db_session.close()
        else:
            return await self._get_user_profile_impl(user_id, tenant_id, db)

    async def _get_user_profile_impl(
        self, user_id: UUID, tenant_id: UUID, db: AsyncSession
    ) -> Optional[UserProfileResponse]:
        """获取用户个人信息实现"""
        try:
            stmt = select(User).where(
                as_bool_clause(User.id == user_id),
                as_bool_clause(User.tenant_id == tenant_id),
                as_bool_clause(User.is_active.is_(True)),
            )
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning("用户不存在或已停用: user_id=%s", user_id)
                return None

            return UserProfileResponse(
                id=cast(UUID, user.id),
                tenant_id=cast(UUID, user.tenant_id),
                email=cast(str, user.email),
                email_verified=cast(bool, user.email_verified),
                is_active=cast(bool, user.is_active),
                created_at=cast(datetime, user.created_at),
                updated_at=cast(datetime, user.updated_at),
            )

        except SQLAlchemyError as e:
            logger.error("获取用户信息异常: user_id=%s, error=%s", user_id, e)
            return None

    async def update_user_profile(
        self,
        user_id: UUID,
        tenant_id: UUID,
        update_data: UserUpdateRequest,
        db: Optional[AsyncSession] = None,
    ) -> Optional[UserProfileResponse]:
        """
        更新用户个人信息 - PATCH /users/me

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            update_data: 更新数据
            db: 数据库会话（可选）

        Returns:
            Optional[UserProfileResponse]: 更新后的用户信息
        """
        if db is None:
            db_session = await get_session()
            try:
                return await self._update_user_profile_impl(
                    user_id, tenant_id, update_data, db_session
                )
            finally:
                await db_session.close()
        else:
            return await self._update_user_profile_impl(
                user_id, tenant_id, update_data, db
            )

    async def _update_user_profile_impl(
        self,
        user_id: UUID,
        tenant_id: UUID,
        update_data: UserUpdateRequest,
        db: AsyncSession,
    ) -> Optional[UserProfileResponse]:
        """更新用户个人信息实现"""
        try:
            # 构建更新字典，只包含非None字段
            update_fields: Dict[str, Any] = {}

            if update_data.email is not None:
                # 检查邮箱是否已被其他用户使用
                if await self._email_exists_for_other_user(
                    update_data.email, user_id, tenant_id, db
                ):
                    logger.warning(
                        "邮箱已存在: email=%s, user_id=%s",
                        update_data.email,
                        user_id,
                    )
                    return None
                update_fields["email"] = update_data.email
                update_fields["email_verified"] = False  # 需重新验证

            if not update_fields:
                # 没有需要更新的字段，直接返回当前信息
                return await self._get_user_profile_impl(user_id, tenant_id, db)

            # 更新时间戳
            update_fields["updated_at"] = datetime.utcnow()

            # 执行更新
            stmt = (
                update(User)
                .where(
                    as_bool_clause(User.id == user_id),
                    as_bool_clause(User.tenant_id == tenant_id),
                    as_bool_clause(User.is_active.is_(True)),
                )
                .values(**update_fields)
            )

            result = await db.execute(stmt)

            if result.rowcount == 0:
                logger.warning("用户不存在，无法更新: user_id=%s", user_id)
                return None

            await db.commit()

            # 返回更新后的用户信息
            return await self._get_user_profile_impl(user_id, tenant_id, db)

        except IntegrityError as e:
            await db.rollback()
            logger.error("数据完整性约束违规: user_id=%s, error=%s", user_id, e)
            return None
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error("更新用户信息异常: user_id=%s, error=%s", user_id, e)
            return None

    async def change_password(
        self,
        user_id: UUID,
        tenant_id: UUID,
        password_data: PasswordChangeRequest,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """
        修改用户密码 - POST /users/change-password

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            password_data: 密码修改数据
            db: 数据库会话（可选）

        Returns:
            bool: 是否修改成功
        """
        if db is None:
            db_session = await get_session()
            try:
                return await self._change_password_impl(
                    user_id, tenant_id, password_data, db_session
                )
            finally:
                await db_session.close()
        else:
            return await self._change_password_impl(
                user_id, tenant_id, password_data, db
            )

    async def _change_password_impl(
        self,
        user_id: UUID,
        tenant_id: UUID,
        password_data: PasswordChangeRequest,
        db: AsyncSession,
    ) -> bool:
        """修改用户密码实现"""
        try:
            # 获取用户当前信息
            stmt = select(User).where(
                as_bool_clause(User.id == user_id),
                as_bool_clause(User.tenant_id == tenant_id),
                as_bool_clause(User.is_active.is_(True)),
            )
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning("用户不存在，无法修改密码: user_id=%s", user_id)
                return False

            # 验证当前密码
            if not self._verify_password(
                password_data.current_password, cast(str, user.password_hash)
            ):
                logger.warning("当前密码验证失败: user_id=%s", user_id)
                return False

            # 生成新密码哈希
            new_password_hash = self._hash_password(password_data.new_password)

            # 更新密码
            update_stmt = (
                update(User)
                .where(
                    as_bool_clause(User.id == user_id),
                    as_bool_clause(User.tenant_id == tenant_id),
                )
                .values(
                    password_hash=new_password_hash,
                    updated_at=datetime.utcnow(),
                )
            )

            await db.execute(update_stmt)
            await db.commit()

            logger.info("密码修改成功: user_id=%s", user_id)
            return True

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error("修改密码异常: user_id=%s, error=%s", user_id, e)
            return False

    async def get_account_status(
        self, user_id: UUID, tenant_id: UUID, db: Optional[AsyncSession] = None
    ) -> Optional[UserAccountStatusResponse]:
        """
        获取用户账户状态

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            db: 数据库会话（可选）

        Returns:
            Optional[UserAccountStatusResponse]: 账户状态信息
        """
        if db is None:
            db_session = await get_session()
            try:
                return await self._get_account_status_impl(
                    user_id, tenant_id, db_session
                )
            finally:
                await db_session.close()
        else:
            return await self._get_account_status_impl(user_id, tenant_id, db)

    async def _get_account_status_impl(
        self, user_id: UUID, tenant_id: UUID, db: AsyncSession
    ) -> Optional[UserAccountStatusResponse]:
        """获取用户账户状态实现"""
        try:
            stmt = select(User).where(
                as_bool_clause(User.id == user_id),
                as_bool_clause(User.tenant_id == tenant_id),
            )
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return None

            return UserAccountStatusResponse(
                user_id=cast(UUID, user.id),
                is_active=cast(bool, user.is_active),
                email_verified=cast(bool, user.email_verified),
                last_login_at=None,  # 后续可扩展登录记录功能
            )

        except SQLAlchemyError as e:
            logger.error("获取账户状态异常: user_id=%s, error=%s", user_id, e)
            return None

    async def _email_exists_for_other_user(
        self,
        email: str,
        exclude_user_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
    ) -> bool:
        """检查邮箱是否被其他用户使用"""
        try:
            stmt = select(User).where(
                as_bool_clause(User.email == email),
                as_bool_clause(User.tenant_id == tenant_id),
                as_bool_clause(User.id != exclude_user_id),
                as_bool_clause(User.is_active.is_(True)),
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none() is not None

        except SQLAlchemyError as e:
            logger.error("检查邮箱存在性异常: email=%s, error=%s", email, e)
            return True  # 发生异常时返回True，避免重复邮箱

    def _hash_password(self, password: str) -> str:
        """生成密码哈希值"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except (ValueError, TypeError) as e:
            logger.error("密码验证异常: %s", e)
            return False
