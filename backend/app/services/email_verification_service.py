"""邮箱验证服务 - 负责生成和发送邮箱验证链接"""

from __future__ import annotations

import logging
from typing import Any, Dict, NamedTuple, Optional, Type

from ..core.config import get_settings
from ..core.security import create_email_verification_token
from ..models.user import User

class _NotificationDeps(NamedTuple):
    channel: Type[Any]
    level: Type[Any]
    message_cls: Type[Any]
    service_cls: Type[Any]


def _load_notification_dependencies() -> Optional[_NotificationDeps]:
    """尝试加载通知服务依赖，缺失时返回None。"""
    try:
        from .notification_service import (
            NotificationChannel,
            NotificationLevel,
            NotificationMessage,
            NotificationService,
        )
    except Exception:  # noqa: BLE001 - 在缺失通知模块时降级为纯日志模式
        return None

    return _NotificationDeps(
        NotificationChannel,
        NotificationLevel,
        NotificationMessage,
        NotificationService,
    )


class EmailVerificationService:
    """负责生成邮箱验证token并将验证链接发送给用户"""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._logger = logging.getLogger(__name__)
        self._debug_tokens: Dict[str, str] = {}

    def _build_verification_link(self, token: str) -> str:
        base_url = getattr(self._settings, "frontend_base_url", "http://localhost:3008")
        return f"{base_url.rstrip('/')}/auth/verify-email?token={token}"

    def _remember_token_for_debug(self, email: str, token: str) -> None:
        if self._settings.debug:
            self._debug_tokens[email.lower()] = token

    async def send_verification_email(self, user: User) -> str:
        """生成并发送邮箱验证邮件，返回生成的token"""
        token = create_email_verification_token(str(user.email), max_age_hours=24)
        link = self._build_verification_link(token)
        self._remember_token_for_debug(str(user.email), token)

        deps = _load_notification_dependencies()

        if deps is None:
            self._logger.info("📧 邮箱验证链接已生成: email=%s link=%s", user.email, link)
            return token

        NotificationChannel, NotificationLevel, NotificationMessage, NotificationService = deps

        message = NotificationMessage(
            title="验证你的 Reddit Signal Scanner 账户",
            content=(
                "欢迎加入 Reddit Signal Scanner！请在24小时内点击以下链接完成邮箱验证：\n"
                f"{link}\n\n如果你没有注册该服务，请忽略此邮件。"
            ),
            level=NotificationLevel.INFO,
            category="auth.email_verification",
            data={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "email": str(user.email),
            },
            channels=[NotificationChannel.LOG_ONLY],
            source="auth_service",
        )

        try:
            service = NotificationService()
            service.send_notification(message, force_send=True)
            self._logger.info("📧 验证邮件已发送: email=%s", user.email)
        except Exception as exc:  # noqa: BLE001 - 通知失败时降级为日志
            self._logger.warning(
                "发送邮箱验证通知失败，将仅记录日志: email=%s error=%s",
                user.email,
                exc,
            )
            self._logger.info("📧 邮箱验证链接: %s", link)

        return token

    def get_debug_token(self, email: str) -> Optional[str]:
        """在DEBUG模式下获取最近发送的token，便于测试"""
        return self._debug_tokens.get(email.lower())


email_verification_service = EmailVerificationService()
