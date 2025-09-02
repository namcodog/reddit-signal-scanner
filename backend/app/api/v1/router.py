"""
Reddit Signal Scanner - API v1主路由

Linus原则："组织决定架构"
- 清晰的模块分离
- 统一的路径前缀
- 简单的路由组合
"""

from typing import Any, Dict

from fastapi import APIRouter

from .endpoints import analyze, report, status, stream

# 创建v1路由实例
router = APIRouter(prefix="/v1", tags=["API v1"])

# 注册4个核心端点路由
# 路径结构：/api/v1/{endpoint}
router.include_router(analyze.router)  # /api/v1/analyze
router.include_router(stream.router)  # /api/v1/stream
router.include_router(status.router)  # /api/v1/status
router.include_router(report.router)  # /api/v1/report


# 版本信息端点
@router.get("/", summary="API版本信息", tags=["版本信息"])
async def get_api_version() -> Dict[str, Any]:
    """
    获取API版本信息

    返回当前v1版本的功能特性和端点列表
    """
    return {
        "version": "1.0.0",
        "name": "Reddit Signal Scanner API v1",
        "description": "商业信号分析工具API",
        "endpoints": {
            "analyze": {
                "path": "/api/v1/analyze",
                "methods": ["POST"],
                "description": "创建分析任务",
            },
            "stream": {
                "path": "/api/v1/stream/{task_id}",
                "methods": ["GET"],
                "description": "SSE实时状态推送",
            },
            "status": {
                "path": "/api/v1/status/{task_id}",
                "methods": ["GET"],
                "description": "查询任务状态",
            },
            "report": {
                "path": "/api/v1/report/{task_id}",
                "methods": ["GET"],
                "description": "获取分析报告",
            },
        },
        "features": ["异步任务处理", "实时状态推送", "结构化报告", "多格式导出"],
        "status": "stable",
    }
