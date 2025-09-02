"""
Reddit Signal Scanner - 业务异常定义

PRD02-07要求：4个核心异常类型
- ValidationError: 输入验证错误
- TaskNotFoundError: 任务不存在错误
- RedditAPIError: Reddit API异常
- DatabaseError: 数据库异常

Linus设计哲学：
- "数据结构优先"：统一的异常数据模型
- "消除特殊情况"：所有异常都有相同的结构和接口
- "简洁胜过聪明"：继承HTTPException，复用FastAPI标准机制
"""

from fastapi import HTTPException
from typing import Optional, Dict, Any


class BaseApplicationError(HTTPException):
    """
    统一异常基类 - 消除异常处理的特殊情况

    所有业务异常都继承此类，确保：
    - 统一的错误响应格式
    - 统一的恢复提示机制
    - 统一的日志记录方式
    """

    def __init__(
        self,
        status_code: int,
        detail: str,
        recovery_hint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.recovery_hint = recovery_hint or "请稍后重试"
        self.context = context or {}


class ValidationError(BaseApplicationError):
    """
    输入验证错误 - HTTP 400

    场景：用户输入的参数格式错误、缺失必填字段等
    恢复策略：用户修正输入即可解决
    """

    def __init__(self, detail: str, field: Optional[str] = None):
        context = {"field": field} if field else {}
        super().__init__(
            status_code=400,
            detail=detail,
            recovery_hint="请检查输入格式和内容",
            context=context,
        )


class TaskNotFoundError(BaseApplicationError):
    """
    任务不存在错误 - HTTP 404

    场景：查询不存在的task_id、任务已被删除等
    恢复策略：验证task_id或创建新任务
    """

    def __init__(self, task_id: str):
        super().__init__(
            status_code=404,
            detail=f"Task {task_id} not found",
            recovery_hint="验证task_id或创建新任务",
            context={"task_id": task_id},
        )


class RedditAPIError(BaseApplicationError):
    """
    Reddit API异常 - HTTP 503

    场景：Reddit API限流、服务不可用、认证失败等
    恢复策略：启用缓存模式或稍后重试
    """

    def __init__(self, detail: str, api_status_code: Optional[int] = None):
        super().__init__(
            status_code=503,
            detail=f"Reddit API error: {detail}",
            recovery_hint="已启用缓存模式，数据可能稍有延迟",
            context={"reddit_status_code": api_status_code},
        )


class DatabaseError(BaseApplicationError):
    """
    数据库异常 - HTTP 500

    场景：数据库连接失败、SQL执行错误、事务回滚等
    恢复策略：自动重试机制，用户无需操作
    """

    def __init__(self, detail: str, operation: Optional[str] = None):
        super().__init__(
            status_code=500,
            detail=f"Database error: {detail}",
            recovery_hint="系统正在自动重试，请稍候",
            context={"operation": operation},
        )


class TaskProducerError(BaseApplicationError):
    """
    任务生产者错误 - HTTP 500

    场景：任务提交失败、队列连接异常、配置错误等
    恢复策略：自动重试机制，检查系统状态
    """

    def __init__(self, detail: str, task_type: Optional[str] = None):
        super().__init__(
            status_code=500,
            detail=f"Task producer error: {detail}",
            recovery_hint="任务提交异常，系统正在重试",
            context={"task_type": task_type},
        )
