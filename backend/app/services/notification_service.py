"""
通知服务 - Reddit Signal Scanner
提供统一的告警通知机制，支持Slack、邮件、钉钉等多种通知方式

基于Linus设计原则：
- 简单的通知接口，复杂的逻辑在各适配器中
- 统一的消息格式，多种发送渠道
- 完整的错误处理和重试机制
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
import json
import asyncio
from dataclasses import dataclass

from ..core.config import settings

logger = logging.getLogger(__name__)


class NotificationLevel(Enum):
    """通知级别"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """通知渠道"""

    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    LOG_ONLY = "log_only"


@dataclass
class NotificationMessage:
    """通知消息数据结构"""

    title: str
    content: str
    level: NotificationLevel
    category: str = "system"

    # 可选的结构化数据
    data: Optional[Dict[str, Any]] = None

    # 通知目标
    channels: Optional[List[NotificationChannel]] = None

    # 元数据
    timestamp: datetime = None
    source: str = "reddit_signal_scanner"

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

        if self.channels is None:
            # 根据级别确定默认通知渠道
            if self.level in [NotificationLevel.ERROR, NotificationLevel.CRITICAL]:
                self.channels = [NotificationChannel.SLACK, NotificationChannel.EMAIL]
            elif self.level == NotificationLevel.WARNING:
                self.channels = [NotificationChannel.SLACK]
            else:
                self.channels = [NotificationChannel.LOG_ONLY]


class NotificationService:
    """
    统一通知服务

    功能：
    - 支持多种通知渠道
    - 消息格式标准化
    - 失败重试和降级
    - 通知历史记录
    """

    def __init__(self):
        self.adapters = self._initialize_adapters()
        self.enabled = getattr(settings, "NOTIFICATIONS_ENABLED", True)

    def _initialize_adapters(self) -> Dict[NotificationChannel, Any]:
        """初始化通知适配器"""
        adapters = {}

        # Slack适配器
        if hasattr(settings, "SLACK_WEBHOOK_URL") and settings.SLACK_WEBHOOK_URL:
            adapters[NotificationChannel.SLACK] = SlackNotificationAdapter(
                webhook_url=settings.SLACK_WEBHOOK_URL
            )

        # 邮件适配器
        if hasattr(settings, "SMTP_HOST") and settings.SMTP_HOST:
            adapters[NotificationChannel.EMAIL] = EmailNotificationAdapter(
                smtp_host=settings.SMTP_HOST,
                smtp_port=getattr(settings, "SMTP_PORT", 587),
                smtp_user=getattr(settings, "SMTP_USER", ""),
                smtp_password=getattr(settings, "SMTP_PASSWORD", ""),
                from_email=getattr(
                    settings, "NOTIFICATIONS_FROM_EMAIL", "noreply@reddit-scanner.com"
                ),
            )

        # Webhook适配器
        if (
            hasattr(settings, "NOTIFICATION_WEBHOOK_URL")
            and settings.NOTIFICATION_WEBHOOK_URL
        ):
            adapters[NotificationChannel.WEBHOOK] = WebhookNotificationAdapter(
                webhook_url=settings.NOTIFICATION_WEBHOOK_URL
            )

        # 日志适配器（始终可用）
        adapters[NotificationChannel.LOG_ONLY] = LogNotificationAdapter()

        logger.info(f"通知适配器初始化完成: {list(adapters.keys())}")
        return adapters

    def send_notification(
        self, message: NotificationMessage, force_send: bool = False
    ) -> Dict[NotificationChannel, bool]:
        """
        发送通知

        Args:
            message: 通知消息
            force_send: 是否强制发送（忽略全局开关）

        Returns:
            Dict: 各通道的发送结果
        """
        if not (self.enabled or force_send):
            logger.debug("通知功能已禁用，跳过发送")
            return {}

        results = {}

        for channel in message.channels:
            if channel not in self.adapters:
                logger.warning(f"通知渠道未配置: {channel}")
                results[channel] = False
                continue

            try:
                adapter = self.adapters[channel]
                success = adapter.send(message)
                results[channel] = success

                if success:
                    logger.debug(f"通知发送成功: {channel.value}")
                else:
                    logger.warning(f"通知发送失败: {channel.value}")

            except Exception as e:
                logger.error(f"通知发送异常 {channel.value}: {e}")
                results[channel] = False

        # 记录通知历史
        self._record_notification_history(message, results)

        return results

    def send_cleanup_failure_alert(
        self, task_id: str, error: str, task_type: str = "unknown"
    ):
        """发送清理失败告警"""
        message = NotificationMessage(
            title="🚨 数据清理任务失败",
            content=f"任务ID: {task_id}\n任务类型: {task_type}\n错误信息: {error}",
            level=NotificationLevel.ERROR,
            category="cleanup_failure",
            data={"task_id": task_id, "error": error, "task_type": task_type},
        )

        return self.send_notification(message)

    def send_cleanup_success_summary(
        self, results: Dict[str, Any], task_type: str = "daily_cleanup"
    ):
        """发送清理成功摘要"""
        total_cleaned = results.get("total_cleaned", 0)
        duration = results.get("duration_seconds", 0)

        # 只有清理了大量数据才发送摘要通知
        if total_cleaned > 1000:
            level = (
                NotificationLevel.WARNING
                if total_cleaned > 10000
                else NotificationLevel.INFO
            )

            message = NotificationMessage(
                title="✅ 数据清理任务完成",
                content=f"""清理摘要:
• 总清理记录: {total_cleaned:,} 条
• 执行时间: {duration} 秒
• 完成任务: {results.get('completed_tasks', 0)} 条
• 失败任务: {results.get('failed_tasks', 0)} 条
• 孤儿分析: {results.get('orphan_analyses', 0)} 条
• 过期缓存: {results.get('expired_cache', 0)} 条""",
                level=level,
                category="cleanup_success",
                data=results,
            )

            return self.send_notification(message)

    def send_emergency_cleanup_alert(self, reason: str, aggressive: bool = False):
        """发送紧急清理告警"""
        message = NotificationMessage(
            title="⚠️ 紧急数据清理已触发",
            content=f"触发原因: {reason}\n激进模式: {'是' if aggressive else '否'}\n请注意监控清理进度",
            level=NotificationLevel.CRITICAL,
            category="emergency_cleanup",
            data={"reason": reason, "aggressive": aggressive},
        )

        return self.send_notification(message)

    def send_database_size_alert(
        self, current_size_gb: float, threshold_gb: float = 100.0
    ):
        """发送数据库大小告警"""
        if current_size_gb > threshold_gb:
            message = NotificationMessage(
                title="💾 数据库大小告警",
                content=f"当前数据库大小: {current_size_gb:.2f}GB\n告警阈值: {threshold_gb}GB\n建议执行数据清理",
                level=NotificationLevel.WARNING,
                category="database_size",
                data={"current_size_gb": current_size_gb, "threshold_gb": threshold_gb},
            )

            return self.send_notification(message)

    def _record_notification_history(
        self, message: NotificationMessage, results: Dict[NotificationChannel, bool]
    ):
        """记录通知历史"""
        # TODO: 可以保存到数据库或文件
        logger.info(
            f"通知记录",
            extra={
                "category": message.category,
                "level": message.level.value,
                "title": message.title,
                "channels": [ch.value for ch in message.channels],
                "results": {ch.value: success for ch, success in results.items()},
                "timestamp": message.timestamp.isoformat(),
            },
        )


class BaseNotificationAdapter:
    """通知适配器基类"""

    def send(self, message: NotificationMessage) -> bool:
        """发送通知 - 子类必须实现"""
        raise NotImplementedError


class SlackNotificationAdapter(BaseNotificationAdapter):
    """Slack通知适配器"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, message: NotificationMessage) -> bool:
        """发送Slack通知"""
        try:
            import requests

            # Slack消息格式
            color_map = {
                NotificationLevel.INFO: "#36a64f",  # 绿色
                NotificationLevel.WARNING: "#ff9500",  # 橙色
                NotificationLevel.ERROR: "#ff0000",  # 红色
                NotificationLevel.CRITICAL: "#8B0000",  # 暗红色
            }

            payload = {
                "attachments": [
                    {
                        "color": color_map.get(message.level, "#36a64f"),
                        "title": message.title,
                        "text": message.content,
                        "footer": f"{message.source} | {message.category}",
                        "ts": int(message.timestamp.timestamp()),
                    }
                ]
            }

            response = requests.post(self.webhook_url, json=payload, timeout=10)

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Slack通知发送失败: {e}")
            return False


class EmailNotificationAdapter(BaseNotificationAdapter):
    """邮件通知适配器"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email

    def send(self, message: NotificationMessage) -> bool:
        """发送邮件通知"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # 获取收件人列表
            to_emails = getattr(settings, "NOTIFICATION_EMAIL_RECIPIENTS", [])
            if not to_emails:
                logger.warning("未配置邮件通知收件人")
                return False

            # 构建邮件
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = f"[Reddit Scanner] {message.title}"

            # 邮件内容
            html_content = f"""
            <html>
            <body>
                <h3>{message.title}</h3>
                <p><pre>{message.content}</pre></p>
                <hr>
                <p>
                    <small>
                        分类: {message.category}<br>
                        级别: {message.level.value}<br>
                        时间: {message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
                    </small>
                </p>
            </body>
            </html>
            """

            msg.attach(MIMEText(html_content, "html"))

            # 发送邮件
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            return True

        except Exception as e:
            logger.error(f"邮件通知发送失败: {e}")
            return False


class WebhookNotificationAdapter(BaseNotificationAdapter):
    """Webhook通知适配器"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, message: NotificationMessage) -> bool:
        """发送Webhook通知"""
        try:
            import requests

            payload = {
                "title": message.title,
                "content": message.content,
                "level": message.level.value,
                "category": message.category,
                "timestamp": message.timestamp.isoformat(),
                "source": message.source,
                "data": message.data,
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            return response.status_code in [200, 201, 202]

        except Exception as e:
            logger.error(f"Webhook通知发送失败: {e}")
            return False


class LogNotificationAdapter(BaseNotificationAdapter):
    """日志通知适配器"""

    def send(self, message: NotificationMessage) -> bool:
        """记录到日志"""
        log_level_map = {
            NotificationLevel.INFO: logging.INFO,
            NotificationLevel.WARNING: logging.WARNING,
            NotificationLevel.ERROR: logging.ERROR,
            NotificationLevel.CRITICAL: logging.CRITICAL,
        }

        log_level = log_level_map.get(message.level, logging.INFO)

        logger.log(
            log_level,
            f"[NOTIFICATION] {message.title}: {message.content}",
            extra={"category": message.category, "notification_data": message.data},
        )

        return True


# 全局通知服务实例
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """获取全局通知服务实例"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# 便捷函数
def send_cleanup_failure_alert(task_id: str, error: str, task_type: str = "unknown"):
    """发送清理失败告警"""
    service = get_notification_service()
    return service.send_cleanup_failure_alert(task_id, error, task_type)


def send_cleanup_success_summary(
    results: Dict[str, Any], task_type: str = "daily_cleanup"
):
    """发送清理成功摘要"""
    service = get_notification_service()
    return service.send_cleanup_success_summary(results, task_type)


def send_emergency_cleanup_alert(reason: str, aggressive: bool = False):
    """发送紧急清理告警"""
    service = get_notification_service()
    return service.send_emergency_cleanup_alert(reason, aggressive)


# 导出接口
__all__ = [
    "NotificationService",
    "NotificationMessage",
    "NotificationLevel",
    "NotificationChannel",
    "get_notification_service",
    "send_cleanup_failure_alert",
    "send_cleanup_success_summary",
    "send_emergency_cleanup_alert",
]
