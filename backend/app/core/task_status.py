"""
Reddit Signal Scanner - 统一任务状态管理

基于 Linus 设计原则：
1. 数据结构优先 - 统一状态定义消除混乱
2. 消除特殊情况 - 4状态机覆盖所有场景
3. 向后兼容 - 映射转换支持平滑迁移

解决问题：系统中存在4个不同的TaskStatus定义，造成严重的状态混乱
"""

import logging
from enum import Enum
from typing import Dict

logger = logging.getLogger(__name__)


class UnifiedTaskStatus(str, Enum):
    """
    统一任务状态枚举 - Linus式简洁设计

    基于现有Task模型的4状态机设计，消除系统中的4个不同定义：
    - task_manager.py: 7状态 → 统一为4状态
    - scheduler.py: 6状态 → 统一为4状态
    - models/task.py: 4状态 → 保持兼容
    - api/models.py: 5状态 → 统一为4状态

    状态流转规则:
    PENDING → PROCESSING → COMPLETED/FAILED
    """

    PENDING = "pending"  # 已创建，等待处理
    PROCESSING = "processing"  # 正在处理中
    COMPLETED = "completed"  # 处理完成
    FAILED = "failed"  # 处理失败

    @classmethod
    def is_terminal(cls, status: "UnifiedTaskStatus") -> bool:
        """判断是否为终止状态"""
        return status in {cls.COMPLETED, cls.FAILED}

    @classmethod
    def is_active(cls, status: "UnifiedTaskStatus") -> bool:
        """判断是否为活跃状态"""
        return status in {cls.PENDING, cls.PROCESSING}


class TaskStatusMapping:
    """
    任务状态映射器 - 支持各子系统的状态转换

    保证向后兼容性，支持渐进式迁移
    """

    # Celery状态映射 (scheduler.py)
    CELERY_TO_UNIFIED: Dict[str, UnifiedTaskStatus] = {
        "PENDING": UnifiedTaskStatus.PENDING,
        "STARTED": UnifiedTaskStatus.PROCESSING,
        "SUCCESS": UnifiedTaskStatus.COMPLETED,
        "FAILURE": UnifiedTaskStatus.FAILED,
        "RETRY": UnifiedTaskStatus.PROCESSING,
        "REVOKED": UnifiedTaskStatus.FAILED,
    }

    # 扩展状态映射 (task_manager.py)
    EXTENDED_TO_UNIFIED: Dict[str, UnifiedTaskStatus] = {
        "pending": UnifiedTaskStatus.PENDING,
        "queued": UnifiedTaskStatus.PENDING,
        "processing": UnifiedTaskStatus.PROCESSING,
        "completed": UnifiedTaskStatus.COMPLETED,
        "failed": UnifiedTaskStatus.FAILED,
        "cancelled": UnifiedTaskStatus.FAILED,
        "retrying": UnifiedTaskStatus.PROCESSING,
    }

    # API状态映射 (api/models.py)
    API_TO_UNIFIED: Dict[str, UnifiedTaskStatus] = {
        "pending": UnifiedTaskStatus.PENDING,
        "running": UnifiedTaskStatus.PROCESSING,
        "completed": UnifiedTaskStatus.COMPLETED,
        "failed": UnifiedTaskStatus.FAILED,
        "cancelled": UnifiedTaskStatus.FAILED,
    }

    # 反向映射 - 统一状态到各系统
    UNIFIED_TO_CELERY: Dict[UnifiedTaskStatus, str] = {
        UnifiedTaskStatus.PENDING: "PENDING",
        UnifiedTaskStatus.PROCESSING: "STARTED",
        UnifiedTaskStatus.COMPLETED: "SUCCESS",
        UnifiedTaskStatus.FAILED: "FAILURE",
    }

    UNIFIED_TO_EXTENDED: Dict[UnifiedTaskStatus, str] = {
        UnifiedTaskStatus.PENDING: "pending",
        UnifiedTaskStatus.PROCESSING: "processing",
        UnifiedTaskStatus.COMPLETED: "completed",
        UnifiedTaskStatus.FAILED: "failed",
    }

    @classmethod
    def normalize_status(cls, status: str, source: str = "task") -> UnifiedTaskStatus:
        """
        标准化任务状态

        Args:
            status: 原始状态字符串
            source: 状态来源系统 (celery/extended/api/task)

        Returns:
            统一的任务状态

        Raises:
            ValueError: 未知的状态值
        """
        status_clean = (
            status.strip().lower() if isinstance(status, str) else str(status)
        )

        try:
            if source == "celery":
                return cls.CELERY_TO_UNIFIED.get(
                    status.upper(), UnifiedTaskStatus.PENDING
                )
            elif source == "extended":
                return cls.EXTENDED_TO_UNIFIED.get(
                    status_clean, UnifiedTaskStatus.PENDING
                )
            elif source == "api":
                return cls.API_TO_UNIFIED.get(status_clean, UnifiedTaskStatus.PENDING)
            else:
                # 默认处理 - 直接匹配统一状态
                if status_clean in [s.value for s in UnifiedTaskStatus]:
                    return UnifiedTaskStatus(status_clean)
                return UnifiedTaskStatus.PENDING

        except Exception as e:
            logger.warning(f"状态映射失败: {status} from {source}, 错误: {e}")
            return UnifiedTaskStatus.PENDING

    @classmethod
    def to_legacy_format(
        cls, unified_status: UnifiedTaskStatus, target_system: str = "task"
    ) -> str:
        """
        转换统一状态到遗留系统格式

        Args:
            unified_status: 统一状态
            target_system: 目标系统 (celery/extended/task)

        Returns:
            目标系统格式的状态字符串
        """
        try:
            if target_system == "celery":
                return cls.UNIFIED_TO_CELERY.get(unified_status, "PENDING")
            elif target_system == "extended":
                return cls.UNIFIED_TO_EXTENDED.get(unified_status, "pending")
            else:
                return unified_status.value
        except Exception as e:
            logger.warning(f"状态转换失败: {unified_status} to {target_system}, 错误: {e}")
            return "pending"


class StatusTransitionValidator:
    """
    状态转换验证器 - 确保状态流转的合法性
    """

    # 允许的状态转换规则
    VALID_TRANSITIONS: Dict[UnifiedTaskStatus, set[UnifiedTaskStatus]] = {
        UnifiedTaskStatus.PENDING: {
            UnifiedTaskStatus.PROCESSING,
            UnifiedTaskStatus.FAILED,
        },
        UnifiedTaskStatus.PROCESSING: {
            UnifiedTaskStatus.COMPLETED,
            UnifiedTaskStatus.FAILED,
            UnifiedTaskStatus.PENDING,  # 支持重置
        },
        UnifiedTaskStatus.COMPLETED: set(),  # 终止状态，不允许转换
        UnifiedTaskStatus.FAILED: {UnifiedTaskStatus.PENDING},  # 支持重试
    }

    @classmethod
    def is_valid_transition(
        cls, from_status: UnifiedTaskStatus, to_status: UnifiedTaskStatus
    ) -> bool:
        """
        验证状态转换是否合法

        Args:
            from_status: 当前状态
            to_status: 目标状态

        Returns:
            是否允许该状态转换
        """
        if from_status == to_status:
            return True  # 同状态转换总是允许

        allowed_transitions = cls.VALID_TRANSITIONS.get(from_status, set())
        return to_status in allowed_transitions

    @classmethod
    def validate_transition(
        cls,
        from_status: UnifiedTaskStatus,
        to_status: UnifiedTaskStatus,
        raise_error: bool = True,
    ) -> bool:
        """
        验证状态转换，可选择抛出异常

        Args:
            from_status: 当前状态
            to_status: 目标状态
            raise_error: 是否在验证失败时抛出异常

        Returns:
            验证结果

        Raises:
            ValueError: 非法状态转换（当raise_error=True时）
        """
        is_valid = cls.is_valid_transition(from_status, to_status)

        if not is_valid and raise_error:
            raise ValueError(f"非法状态转换: {from_status.value} → {to_status.value}")

        return is_valid


def get_status_progress_mapping() -> Dict[UnifiedTaskStatus, int]:
    """
    获取状态对应的进度百分比映射

    Returns:
        状态到进度百分比的映射字典
    """
    return {
        UnifiedTaskStatus.PENDING: 0,
        UnifiedTaskStatus.PROCESSING: 50,
        UnifiedTaskStatus.COMPLETED: 100,
        UnifiedTaskStatus.FAILED: 0,
    }


def get_status_display_name(status: UnifiedTaskStatus, language: str = "zh") -> str:
    """
    获取状态的显示名称

    Args:
        status: 统一状态
        language: 语言代码 (zh/en)

    Returns:
        本地化的状态显示名称
    """
    zh_names = {
        UnifiedTaskStatus.PENDING: "等待处理",
        UnifiedTaskStatus.PROCESSING: "处理中",
        UnifiedTaskStatus.COMPLETED: "已完成",
        UnifiedTaskStatus.FAILED: "处理失败",
    }

    en_names = {
        UnifiedTaskStatus.PENDING: "Pending",
        UnifiedTaskStatus.PROCESSING: "Processing",
        UnifiedTaskStatus.COMPLETED: "Completed",
        UnifiedTaskStatus.FAILED: "Failed",
    }

    if language == "zh":
        return zh_names.get(status, status.value)
    else:
        return en_names.get(status, status.value)
