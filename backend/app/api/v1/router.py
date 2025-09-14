"""
Reddit Signal Scanner - API v1主路由

Linus原则："组织决定架构"
- 清晰的模块分离
- 统一的路径前缀
- 简单的路由组合
"""

from typing import Optional, Protocol, cast

from fastapi import APIRouter
from ...core.config import get_settings

from ...core.types import JsonValue

# 基础端点（强依赖，必须可用）
from .endpoints import analyze, auth, report, status, users


class HasRouter(Protocol):
    router: APIRouter


# 可选端点（在依赖缺失或环境不兼容时跳过注册，不阻塞应用启动）
try:
    from .endpoints import monitoring as _monitoring

    monitoring: Optional[HasRouter] = _monitoring
except ImportError:
    monitoring = None

try:
    from .endpoints import stream as _stream

    stream: Optional[HasRouter] = _stream
except ImportError:
    stream = None

try:
    from .endpoints import retry as _retry

    retry: Optional[HasRouter] = _retry
except ImportError:
    retry = None

# 创建v1路由实例
settings = get_settings()
router = APIRouter(prefix=f"/{settings.api_version}", tags=["API v1"])

# 注册核心端点路由
# 路径结构：/api/v1/{endpoint}
router.include_router(auth.router, prefix="/auth")  # /api/v1/auth
router.include_router(users.router, prefix="/users")  # /api/v1/users
router.include_router(analyze.router)  # /api/v1/analyze
if stream is not None:
    router.include_router(stream.router)  # /api/v1/stream
router.include_router(status.router)  # /api/v1/status
router.include_router(report.router)  # /api/v1/report
if monitoring is not None:
    router.include_router(monitoring.router)  # /api/v1/monitoring
if retry is not None:
    router.include_router(retry.router)  # /api/v1/retry

# Mock API路由（开发期间使用） - 已移除mock_discovery模块


# 版本信息端点
@router.get("/", summary="API版本信息", tags=["版本信息"])
async def get_api_version() -> dict[str, JsonValue]:
    """
    获取API版本信息

    返回当前v1版本的功能特性和端点列表
    """
    prefix = settings.api_prefix
    return {
        "version": "1.0.0",
        "name": "Reddit Signal Scanner API v1",
        "description": "商业信号分析工具API",
        "endpoints": cast(
            JsonValue,
            {
                "auth": {
                    "path": f"{prefix}/auth",
                    "methods": ["POST"],
                    "description": "用户认证（注册、登录）",
                    "endpoints": {
                        "register": f"{prefix}/auth/register",
                        "login": f"{prefix}/auth/login (开发中)",
                        "health": f"{prefix}/auth/health",
                    },
                },
                "users": {
                    "path": f"{prefix}/users",
                    "methods": ["GET", "PATCH", "POST"],
                    "description": "用户账户管理",
                    "endpoints": {
                        "profile": f"{prefix}/users/me",
                        "update": f"{prefix}/users/me",
                        "change_password": f"{prefix}/users/change-password",
                        "status": f"{prefix}/users/me/status",
                    },
                },
                "analyze": {
                    "path": f"{prefix}/analyze",
                    "methods": ["POST"],
                    "description": "创建分析任务",
                },
                "stream": {
                    "path": f"{prefix}/stream/{{task_id}}",
                    "methods": ["GET"],
                    "description": "SSE实时状态推送",
                },
                "status": {
                    "path": f"{prefix}/status/{{task_id}}",
                    "methods": ["GET"],
                    "description": "查询任务状态",
                },
                "report": {
                    "path": f"{prefix}/report/{{task_id}}",
                    "methods": ["GET"],
                    "description": "获取分析报告",
                },
                "monitoring": {
                    "path": f"{prefix}/monitoring",
                    "methods": ["GET", "POST"],
                    "description": "任务监控和系统健康",
                    "endpoints": {
                        "health": f"{prefix}/monitoring/health",
                        "workers": f"{prefix}/monitoring/workers",
                        "queues": f"{prefix}/monitoring/queues",
                        "alerts": f"{prefix}/monitoring/alerts",
                    },
                },
                "retry": {
                    "path": f"{prefix}/retry",
                    "methods": ["GET", "POST"],
                    "description": "任务重试和死信队列管理",
                    "endpoints": {
                        "dead_letter": f"{prefix}/retry/dead-letter",
                        "manual": f"{prefix}/retry/manual",
                        "statistics": f"{prefix}/retry/statistics",
                        "failure_analysis": f"{prefix}/retry/failure-analysis",
                        "cleanup": f"{prefix}/retry/cleanup",
                    },
                },
                "mock": {
                    "path": f"{prefix}/mock",
                    "methods": ["GET", "POST"],
                    "description": "Mock API（开发期间使用）",
                    "endpoints": {
                        "analyze": f"{prefix}/mock/analyze",
                        "status": f"{prefix}/mock/status/{{task_id}}",
                        "result": f"{prefix}/mock/result/{{task_id}}",
                    },
                },
            },
        ),
        "features": [
            "用户认证系统",
            "异步任务处理",
            "实时状态推送",
            "结构化报告",
            "多格式导出",
            "系统监控",
            "任务重试机制",
            "死信队列管理",
            "失败模式分析",
            "Mock开发模式",
        ],
        "status": "stable",
    }
