"""
重试策略模块

提供统一的任务失败重试决策与调度能力，满足以下需求：
- 基于异常类型映射失败分类
- 针对不同失败分类给出是否可重试、最大重试次数与退避策略
- 计算下一次重试延迟
- 到达上限后移动至死信队列

该实现遵循简洁可控的原则，并与现有测试用例的期望接口保持一致：
- EnhancedRetryPolicy
- RetryStrategy
- RetryPolicyConfig
- get_retry_policy
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from ..models.task import FailureCategory, Task, TaskStatus


class RetryStrategy(str, Enum):
    """重试退避策略。"""

    EXPONENTIAL_BACKOFF = "exponential"
    LINEAR_BACKOFF = "linear"
    NO_RETRY = "no_retry"


@dataclass
class RetryPolicyConfig:
    """重试策略配置。"""

    base_delay: int = 60
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True
    max_delay: Optional[int] = None


@dataclass
class RetryPolicy:
    """按失败分类生成的具体重试策略。"""

    failure_category: FailureCategory
    auto_recoverable: bool
    retry_config: RetryPolicyConfig


class EnhancedRetryPolicy:
    """统一重试策略决策器。"""

    def __init__(self) -> None:
        # 各失败分类的默认策略
        self._defaults: dict[FailureCategory, RetryPolicy] = {
            FailureCategory.NETWORK_ERROR: RetryPolicy(
                failure_category=FailureCategory.NETWORK_ERROR,
                auto_recoverable=True,
                retry_config=RetryPolicyConfig(
                    base_delay=60,
                    max_retries=3,
                    backoff_multiplier=2.0,
                    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                    jitter=False,
                ),
            ),
            FailureCategory.PROCESSING_ERROR: RetryPolicy(
                failure_category=FailureCategory.PROCESSING_ERROR,
                auto_recoverable=True,
                retry_config=RetryPolicyConfig(
                    base_delay=60,
                    max_retries=2,
                    strategy=RetryStrategy.LINEAR_BACKOFF,
                    jitter=False,
                ),
            ),
            FailureCategory.DATA_VALIDATION_ERROR: RetryPolicy(
                failure_category=FailureCategory.DATA_VALIDATION_ERROR,
                auto_recoverable=False,
                retry_config=RetryPolicyConfig(
                    base_delay=0,
                    max_retries=0,
                    strategy=RetryStrategy.NO_RETRY,
                    jitter=False,
                ),
            ),
            FailureCategory.SYSTEM_ERROR: RetryPolicy(
                failure_category=FailureCategory.SYSTEM_ERROR,
                auto_recoverable=False,
                retry_config=RetryPolicyConfig(
                    base_delay=0,
                    max_retries=0,
                    strategy=RetryStrategy.NO_RETRY,
                    jitter=False,
                ),
            ),
        }

    def get_policy_for_exception(
        self, exception: Exception
    ) -> Tuple[RetryPolicy, FailureCategory]:
        """根据异常类型获取策略与失败分类。"""
        category = self._map_exception_to_category(exception)
        policy = self._defaults.get(category)
        if policy is None:
            # 回退为处理错误策略
            policy = self._defaults[FailureCategory.PROCESSING_ERROR]
        return policy, category

    def should_retry(
        self, task: Task, exception: Exception
    ) -> Tuple[bool, int, FailureCategory]:
        """基于任务状态和异常判断是否应当重试。

        返回 (should_retry, delay_seconds, failure_category)
        """
        policy, category = self.get_policy_for_exception(exception)

        if (
            not policy.auto_recoverable
            or policy.retry_config.strategy == RetryStrategy.NO_RETRY
        ):
            return False, 0, category

        current = int(task.retry_count or 0)
        if current >= policy.retry_config.max_retries:
            return False, 0, category

        delay = self._calculate_retry_delay(current, policy.retry_config)
        return True, delay, category

    def handle_task_failure(
        self, task: Task, exception: Exception, db_session: Session
    ) -> bool:
        """处理任务失败：若可重试则安排下一次重试，否则移动至死信队列。

        返回 True 表示已安排重试；False 表示进入死信队列。
        """
        should_retry, delay, category = self.should_retry(task, exception)

        # 更新失败分类
        task.failure_category = category.value

        if should_retry:
            task.retry_count = int(task.retry_count or 0) + 1
            task.status = TaskStatus.PENDING.value
            # 模型具备 updated_at 字段；直接赋值
            task.updated_at = datetime.utcnow()
            db_session.add(task)
            db_session.flush()
            self._schedule_retry(task, delay, db_session)
            return True

        self._move_to_dead_letter_queue(task, exception, db_session)
        return False

    def _calculate_retry_delay(
        self, current_retry_count: int, config: RetryPolicyConfig
    ) -> int:
        """计算下一次重试延迟（秒）。

        - 指数退避: base * (multiplier ** count)
        - 线性退避: base * (count + 1)
        - NO_RETRY: 0
        """
        if config.strategy == RetryStrategy.NO_RETRY:
            return 0

        if config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = int(
                round(
                    config.base_delay
                    * (config.backoff_multiplier**current_retry_count)
                )
            )
        else:
            delay = int(config.base_delay * (current_retry_count + 1))

        if config.max_delay is not None:
            delay = min(delay, config.max_delay)

        if config.jitter and delay > 0:
            # 轻量抖动，±10%
            jitter_span = max(1, int(delay * 0.1))
            delay = max(1, delay + random.randint(-jitter_span, jitter_span))

        return delay

    def _schedule_retry(
        self, task: Task, delay_seconds: int, db_session: Session
    ) -> None:
        """安排任务在 delay_seconds 后重试。

        这里保留占位实现，实际调度由任务系统接管（例如Celery）。
        在测试中会对该方法进行打桩。"""
        return None

    def _move_to_dead_letter_queue(
        self, task: Task, exception: Exception, db_session: Session
    ) -> None:
        """将任务移动到死信队列。"""
        task.status = TaskStatus.DEAD_LETTER.value
        # 仅在模型具备该字段时设置
        try:
            task.dead_letter_at = datetime.utcnow()
        except AttributeError:
            # 模型没有 dead_letter_at 字段时忽略
            return None
        db_session.add(task)
        db_session.flush()

    def _map_exception_to_category(self, exception: Exception) -> FailureCategory:
        """异常到失败分类的映射。"""
        if isinstance(exception, (ConnectionError, TimeoutError)):
            return FailureCategory.NETWORK_ERROR
        if isinstance(exception, (MemoryError, OSError)):
            return FailureCategory.SYSTEM_ERROR
        if isinstance(exception, (ValueError, TypeError)):
            return FailureCategory.DATA_VALIDATION_ERROR
        return FailureCategory.PROCESSING_ERROR


# 全局策略实例
_GLOBAL_POLICY = EnhancedRetryPolicy()


def get_retry_policy() -> EnhancedRetryPolicy:
    """获取全局重试策略实例。"""
    return _GLOBAL_POLICY
