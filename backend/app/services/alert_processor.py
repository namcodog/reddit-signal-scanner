"""
告警处理服务 - 配置驱动的告警管理

基于Linus原则：
1. 单一职责 - 只负责告警检查和触发
2. 配置驱动 - 所有阈值可配置
3. 去重机制 - 防止告警风暴
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional
from uuid import uuid4

import redis

from app.core.config import get_settings
from app.schemas.task_monitor import (
    Alert,
    AlertConditionType,
    AlertConfig,
    AlertSeverity,
    QueueMetrics,
    WorkerStatus,
)

logger = logging.getLogger(__name__)


class AlertProcessor:
    """
    告警处理器 - 检查告警条件并触发通知

    职责：
    1. 根据配置检查告警条件
    2. 告警去重和冷却处理
    3. 触发告警通知
    """

    def __init__(self) -> None:
        settings = get_settings()
        # 使用同步 Redis 客户端，便于在同步上下文中使用
        redis_from_url: Any = redis.from_url
        self.redis = redis_from_url(settings.redis_url, decode_responses=True)
        self.cooldown_cache_prefix = "alert:cooldown:"
        self.active_alerts_key = "alert:active"
        self.alert_history_key = "alert:history"

        # 默认告警配置
        self.default_configs = self._get_default_configs()

    def _get_default_configs(self) -> List[AlertConfig]:
        """获取默认告警配置"""
        return [
            AlertConfig(
                rule_id="long_running_default",
                rule_name="长时间运行任务",
                condition_type=AlertConditionType.LONG_RUNNING,
                threshold=1800.0,  # 30分钟
                comparison="gt",
                severity=AlertSeverity.WARNING,
                check_interval=60,
                cooldown_period=300,
            ),
            AlertConfig(
                rule_id="worker_down_default",
                rule_name="Worker宕机",
                condition_type=AlertConditionType.WORKER_DOWN,
                threshold=1.0,  # 至少1个Worker宕机
                comparison="gte",
                severity=AlertSeverity.ERROR,
                check_interval=30,
                cooldown_period=180,
            ),
            AlertConfig(
                rule_id="queue_backlog_default",
                rule_name="队列积压",
                condition_type=AlertConditionType.QUEUE_BACKLOG,
                threshold=100.0,  # 超过100个待处理
                comparison="gt",
                severity=AlertSeverity.WARNING,
                check_interval=60,
                cooldown_period=300,
            ),
            AlertConfig(
                rule_id="high_failure_default",
                rule_name="高失败率",
                condition_type=AlertConditionType.HIGH_FAILURE_RATE,
                threshold=30.0,  # 失败率超过30%
                comparison="gt",
                severity=AlertSeverity.ERROR,
                check_interval=120,
                cooldown_period=600,
            ),
            AlertConfig(
                rule_id="memory_high_default",
                rule_name="内存占用高",
                condition_type=AlertConditionType.MEMORY_HIGH,
                threshold=80.0,  # 内存使用超过80%
                comparison="gt",
                severity=AlertSeverity.WARNING,
                check_interval=60,
                cooldown_period=300,
            ),
        ]

    # ==================== 告警检查 ====================

    def check_worker_alerts(
        self, workers: List[WorkerStatus], configs: Optional[List[AlertConfig]] = None
    ) -> List[Alert]:
        """检查Worker相关告警"""
        configs = configs or self.default_configs
        alerts = []

        # Worker宕机检查
        down_workers = [w for w in workers if not w.is_healthy]
        if down_workers:
            for config in configs:
                if config.condition_type == AlertConditionType.WORKER_DOWN:
                    if self._should_trigger_alert(config, len(down_workers)):
                        alert = self._create_alert(
                            config,
                            len(down_workers),
                            f"{len(down_workers)}个Worker不健康: {[w.worker_id for w in down_workers]}",
                        )
                        if alert:
                            alerts.append(alert)

        # 内存占用检查
        for worker in workers:
            if worker.memory_percent > 0:
                for config in configs:
                    if config.condition_type == AlertConditionType.MEMORY_HIGH:
                        if self._should_trigger_alert(config, worker.memory_percent):
                            alert = self._create_alert(
                                config,
                                worker.memory_percent,
                                f"Worker {worker.worker_id} 内存占用: {worker.memory_percent:.1f}%",
                            )
                            if alert:
                                alerts.append(alert)

        # CPU占用检查
        for worker in workers:
            if worker.cpu_percent > 0:
                for config in configs:
                    if config.condition_type == AlertConditionType.CPU_HIGH:
                        if self._should_trigger_alert(config, worker.cpu_percent):
                            alert = self._create_alert(
                                config,
                                worker.cpu_percent,
                                f"Worker {worker.worker_id} CPU占用: {worker.cpu_percent:.1f}%",
                            )
                            if alert:
                                alerts.append(alert)

        return alerts

    def check_queue_alerts(
        self, queues: List[QueueMetrics], configs: Optional[List[AlertConfig]] = None
    ) -> List[Alert]:
        """检查队列相关告警"""
        configs = configs or self.default_configs
        alerts = []

        for queue in queues:
            # 队列积压检查
            for config in configs:
                if config.condition_type == AlertConditionType.QUEUE_BACKLOG:
                    if self._should_trigger_alert(config, queue.pending_count):
                        alert = self._create_alert(
                            config,
                            queue.pending_count,
                            f"队列 {queue.queue_name} 积压: {queue.pending_count} 个任务",
                        )
                        if alert:
                            alerts.append(alert)

            # 高失败率检查
            for config in configs:
                if config.condition_type == AlertConditionType.HIGH_FAILURE_RATE:
                    if queue.success_rate < (100 - config.threshold):
                        alert = self._create_alert(
                            config,
                            100 - queue.success_rate,
                            f"队列 {queue.queue_name} 失败率: {100 - queue.success_rate:.1f}%",
                        )
                        if alert:
                            alerts.append(alert)

            # 长时间运行检查
            for config in configs:
                if config.condition_type == AlertConditionType.LONG_RUNNING:
                    if queue.max_processing_time > config.threshold:
                        alert = self._create_alert(
                            config,
                            queue.max_processing_time,
                            f"队列 {queue.queue_name} 存在长时间运行任务: {queue.max_processing_time:.0f}秒",
                        )
                        if alert:
                            alerts.append(alert)

        return alerts

    # ==================== 告警管理 ====================

    def _should_trigger_alert(self, config: AlertConfig, value: float) -> bool:
        """检查是否应该触发告警"""
        # 检查是否启用
        if not config.enabled:
            return False

        # 检查条件
        if not config.check_condition(value):
            return False

        # 检查冷却期
        if self._is_in_cooldown(config.rule_id):
            return False

        return True

    def _is_in_cooldown(self, rule_id: str) -> bool:
        """检查是否在冷却期内"""
        cooldown_key = f"{self.cooldown_cache_prefix}{rule_id}"
        try:
            return bool(self.redis.exists(cooldown_key))
        except redis.exceptions.RedisError:
            return False

    def _set_cooldown(self, rule_id: str, seconds: int) -> None:
        """设置冷却期"""
        cooldown_key = f"{self.cooldown_cache_prefix}{rule_id}"
        try:
            self.redis.setex(cooldown_key, seconds, "1")
        except redis.exceptions.RedisError as e:
            logger.warning("设置冷却期失败，已忽略", extra={"rule_id": rule_id, "seconds": seconds, "error": str(e)})

    def _create_alert(
        self, config: AlertConfig, current_value: float, message: str
    ) -> Optional[Alert]:
        """创建告警实例"""
        try:
            alert = Alert(
                alert_id=str(uuid4()),
                rule_id=config.rule_id,
                rule_name=config.rule_name,
                severity=config.severity,
                condition_type=config.condition_type,
                triggered_at=datetime.now(timezone.utc),
                current_value=current_value,
                threshold_value=config.threshold,
                message=message,
                context={
                    "comparison": config.comparison,
                    "check_interval": str(config.check_interval),
                },
            )

            # 设置冷却期
            self._set_cooldown(config.rule_id, config.cooldown_period)

            # 保存到活跃告警列表
            self._save_active_alert(alert)

            # 记录历史
            self._save_alert_history(alert)

            # 触发通知
            self._send_notifications(alert, config.notification_channels)

            logger.info(f"告警触发: {config.rule_name} - {message}")
            return alert

        except (TypeError, ValueError, KeyError) as e:
            logger.error(f"创建告警失败: {e}")
            return None

    def _save_active_alert(self, alert: Alert) -> None:
        """保存活跃告警"""
        alert_data = {
            "alert_id": alert.alert_id,
            "rule_id": alert.rule_id,
            "severity": alert.severity.value,
            "triggered_at": alert.triggered_at.isoformat(),
            "message": alert.message,
        }

        # 添加到活跃告警集合
        try:
            self.redis.hset(
                self.active_alerts_key, alert.alert_id, json.dumps(alert_data)
            )
            # 设置过期时间（24小时）
            self.redis.expire(self.active_alerts_key, 86400)
        except redis.exceptions.RedisError as e:
            logger.warning("写入活跃告警失败，已忽略", extra={"alert_id": alert.alert_id, "error": str(e)})

    def _save_alert_history(self, alert: Alert) -> None:
        """保存告警历史"""
        history_entry = {
            "alert_id": alert.alert_id,
            "rule_id": alert.rule_id,
            "severity": alert.severity.value,
            "triggered_at": alert.triggered_at.isoformat(),
            "message": alert.message,
            "current_value": alert.current_value,
            "threshold_value": alert.threshold_value,
        }

        # 添加到历史列表
        try:
            self.redis.lpush(self.alert_history_key, json.dumps(history_entry))
            self.redis.ltrim(self.alert_history_key, 0, 999)  # 保留最近1000条
        except redis.exceptions.RedisError as e:
            logger.warning("写入告警历史失败，已忽略", extra={"alert_id": alert.alert_id, "error": str(e)})

    def _send_notifications(self, alert: Alert, channels: List[str]) -> None:
        """发送告警通知"""
        for channel in channels:
            try:
                if channel == "log":
                    # 日志通知
                    if alert.severity == AlertSeverity.CRITICAL:
                        logger.critical(f"[告警] {alert.message}")
                    elif alert.severity == AlertSeverity.ERROR:
                        logger.error(f"[告警] {alert.message}")
                    else:
                        logger.warning(f"[告警] {alert.message}")

                elif channel == "redis":
                    # Redis发布通知（用于WebSocket推送）
                    self.redis.publish(
                        "alerts:notifications",
                        json.dumps(
                            {
                                "alert_id": alert.alert_id,
                                "severity": alert.severity.value,
                                "message": alert.message,
                                "timestamp": alert.triggered_at.isoformat(),
                            }
                        ),
                    )

                # 这里可以添加更多通知渠道（邮件、短信、Slack等）

            except redis.exceptions.RedisError as e:
                logger.error(f"发送通知失败(redis): {channel}, 错误: {e}")
            except (ValueError, TypeError) as e:
                logger.error(f"发送通知失败(payload): {channel}, 错误: {e}")

    # ==================== 告警查询 ====================

    def get_active_alerts(self) -> List[Alert]:
        """获取所有活跃告警"""
        alerts = []

        # 从Redis获取活跃告警
        try:
            alert_data = self.redis.hgetall(self.active_alerts_key)
        except redis.exceptions.RedisError:
            alert_data = {}

        for alert_id, data in alert_data.items():
            try:
                alert_dict = json.loads(data)
                alert = Alert(
                    alert_id=alert_dict["alert_id"],
                    rule_id=alert_dict["rule_id"],
                    rule_name=alert_dict.get("rule_name", ""),
                    severity=AlertSeverity(alert_dict["severity"]),
                    condition_type=AlertConditionType.WORKER_DOWN,  # 简化处理
                    triggered_at=datetime.fromisoformat(alert_dict["triggered_at"]),
                    current_value=0,
                    threshold_value=0,
                    message=alert_dict["message"],
                )
                alerts.append(alert)
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                logger.error(f"解析告警数据失败: {e}")

        return alerts

    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        try:
            # 从活跃告警中移除
            self.redis.hdel(self.active_alerts_key, alert_id)

            # 更新历史记录
            resolved_entry = {
                "alert_id": alert_id,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "action": "manually_resolved",
            }
            self.redis.lpush(
                f"{self.alert_history_key}:resolved", json.dumps(resolved_entry)
            )

            logger.info(f"告警已解决: {alert_id}")
            return True

        except redis.exceptions.RedisError as e:
            logger.error(f"解决告警失败: {alert_id}, 错误: {e}")
            return False

    def get_alert_history(self, limit: int = 100) -> List[Mapping[str, Any]]:
        """获取告警历史"""
        history: List[Mapping[str, Any]] = []

        # 从Redis获取历史
        try:
            history_data = self.redis.lrange(self.alert_history_key, 0, limit - 1)
        except redis.exceptions.RedisError:
            history_data = []

        for item in history_data:
            try:
                history.append(json.loads(item))
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.error(f"解析历史数据失败: {e}")

        return history


# 单例实例
_processor_instance: Optional[AlertProcessor] = None


def get_alert_processor() -> AlertProcessor:
    """获取告警处理器单例"""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = AlertProcessor()
    return _processor_instance
