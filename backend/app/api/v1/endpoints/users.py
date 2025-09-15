"""
Reddit Signal Scanner - 用户管理API端点

遵循Linus原则: "简洁胜过聪明"
- 直接的REST接口，无过度抽象
- 统一的错误处理格式
- 完整的类型注解
- 详细的API文档
遵循CLAUDE.md零容忍规范: 100%类型安全，79字符限制
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.auth import CurrentUser
from ....core.database import get_db
from ....core.dependencies import get_current_user
from ....schemas.user_management import (
    PasswordChangeRequest,
    SuccessResponse,
    UserAccountStatusResponse,
    UserManagementError,
    UserProfileResponse,
    UserUpdateRequest,
)
from ....services.account_service import AccountService

# 配置日志和路由
logger = logging.getLogger(__name__)
router = APIRouter()

# 创建服务实例
account_service = AccountService()


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="获取当前用户信息",
    description="获取当前认证用户的个人信息，包括邮箱、验证状态等",
    responses={
        200: {"description": "成功返回用户信息"},
        401: {
            "model": UserManagementError,
            "description": "用户未认证或认证已过期",
        },
        404: {
            "model": UserManagementError,
            "description": "用户不存在或已停用",
        },
    },
)
async def get_current_user_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """
    获取当前用户个人信息

    - **返回**: 用户完整个人信息
    - **权限**: 需要有效JWT token
    - **多租户**: 自动应用租户隔离
    """
    logger.info("获取用户信息: user_id=%s", current_user.user_id)

    try:
        user_profile = await account_service.get_user_profile(
            user_id=UUID(current_user.user_id),
            tenant_id=UUID(current_user.tenant_id),
            db=db,
        )

        if not user_profile:
            logger.warning("用户信息不存在: user_id=%s", current_user.user_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "USER_NOT_FOUND",
                    "error_message": "用户不存在或已停用",
                },
            )

        return user_profile

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取用户信息异常: user_id=%s, error=%s", current_user.user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_message": "服务器内部错误",
            },
        )


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="更新当前用户信息",
    description="更新当前认证用户的个人信息，如邮箱地址",
    responses={
        200: {"description": "成功更新用户信息"},
        400: {
            "model": UserManagementError,
            "description": "请求数据验证失败或邮箱已存在",
        },
        401: {
            "model": UserManagementError,
            "description": "用户未认证或认证已过期",
        },
        404: {
            "model": UserManagementError,
            "description": "用户不存在或已停用",
        },
    },
)
async def update_current_user_profile(
    update_data: UserUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """
    更新当前用户个人信息

    - **邮箱更改**: 需要重新验证邮箱
    - **权限**: 需要有效JWT token
    - **多租户**: 自动应用租户隔离
    """
    logger.info("更新用户信息: user_id=%s", current_user.user_id)

    try:
        updated_profile = await account_service.update_user_profile(
            user_id=UUID(current_user.user_id),
            tenant_id=UUID(current_user.tenant_id),
            update_data=update_data,
            db=db,
        )

        if not updated_profile:
            logger.warning("用户更新失败: user_id=%s", current_user.user_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "UPDATE_FAILED",
                    "error_message": "用户信息更新失败，可能是邮箱已存在",
                },
            )

        logger.info("用户信息更新成功: user_id=%s", current_user.user_id)
        return updated_profile

    except HTTPException:
        raise
    except Exception as e:
        logger.error("更新用户信息异常: user_id=%s, error=%s", current_user.user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_message": "服务器内部错误",
            },
        )


@router.post(
    "/change-password",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="修改用户密码",
    description="修改当前认证用户的登录密码",
    responses={
        200: {"description": "密码修改成功"},
        400: {
            "model": UserManagementError,
            "description": "当前密码错误或新密码验证失败",
        },
        401: {
            "model": UserManagementError,
            "description": "用户未认证或认证已过期",
        },
        404: {
            "model": UserManagementError,
            "description": "用户不存在或已停用",
        },
    },
)
async def change_user_password(
    password_data: PasswordChangeRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """
    修改用户密码

    - **安全验证**: 需要提供当前密码
    - **密码要求**: 8位以上，包含大小写字母和数字
    - **权限**: 需要有效JWT token
    - **多租户**: 自动应用租户隔离
    """
    logger.info("用户密码修改: user_id=%s", current_user.user_id)

    try:
        success = await account_service.change_password(
            user_id=UUID(current_user.user_id),
            tenant_id=UUID(current_user.tenant_id),
            password_data=password_data,
            db=db,
        )

        if not success:
            logger.warning("密码修改失败: user_id=%s", current_user.user_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "PASSWORD_CHANGE_FAILED",
                    "error_message": "密码修改失败，请检查当前密码是否正确",
                },
            )

        return SuccessResponse(success=True, message="密码修改成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("密码修改异常: user_id=%s, error=%s", current_user.user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_message": "服务器内部错误",
            },
        )


@router.get(
    "/me/status",
    response_model=UserAccountStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="获取用户账户状态",
    description="获取当前认证用户的账户状态信息",
    responses={
        200: {"description": "成功返回账户状态"},
        401: {
            "model": UserManagementError,
            "description": "用户未认证或认证已过期",
        },
        404: {"model": UserManagementError, "description": "用户不存在"},
    },
)
async def get_user_account_status(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserAccountStatusResponse:
    """
    获取用户账户状态

    - **状态信息**: 激活状态、邮箱验证状态等
    - **权限**: 需要有效JWT token
    - **多租户**: 自动应用租户隔离
    """
    logger.info("获取账户状态: user_id=%s", current_user.user_id)

    try:
        account_status = await account_service.get_account_status(
            user_id=UUID(current_user.user_id),
            tenant_id=UUID(current_user.tenant_id),
            db=db,
        )

        if not account_status:
            logger.warning("账户状态不存在: user_id=%s", current_user.user_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "ACCOUNT_NOT_FOUND",
                    "error_message": "用户账户不存在",
                },
            )

        return account_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取账户状态异常: user_id=%s, error=%s", current_user.user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_message": "服务器内部错误",
            },
        )
