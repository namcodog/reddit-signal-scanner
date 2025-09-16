"""
Reddit Signal Scanner - FastAPI 主应用入口

Linus设计哲学实现：
- "数据结构优先"：统一的响应格式模型
- "消除特殊情况"：统一的错误处理和CORS策略
- "简洁胜过聪明"：清晰的模块组织和路由结构
- "永不破坏用户空间"：API版本管理，向后兼容

架构特点：
- FastAPI + Pydantic：类型安全，自动API文档
- 中间件分层：请求追踪 → CORS → 业务逻辑
- 异步优先：支持高并发场景
- 模块化设计：路由、中间件、模型分离
"""

from contextlib import asynccontextmanager
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Mapping, Sequence

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# 移除已删除的api.middleware依赖 - 功能已迁移到新架构
from .api.v1.router import router as v1_router
from .core.config import get_settings
from .core.logging_config import configure_logging
from .core.monitoring import get_monitoring_service
from .core.redis_client import close_redis_client, get_redis_client
from .middleware.analysis_monitor import (
    AnalysisMonitoringMiddleware,
    RateLimitMiddleware,
)
from .middleware.error_middleware import ErrorHandlingMiddleware
from .middleware.jwt_middleware import JWTMiddleware
from .middleware.performance_middleware import PerformanceMiddleware
from .schemas.common.responses import ResponseStatus
from .schemas.responses.health import HealthResponse, HealthStatus

# 获取配置
settings = get_settings()
configure_logging(debug=settings.debug, log_level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理

    启动：
    - 初始化数据库连接池
    - 启动后台任务
    - 预热缓存

    关闭：
    - 优雅关闭连接
    - 清理临时资源
    """

    # 启动阶段
    logger.info("🚀 Reddit Signal Scanner API 启动中...")
    logger.info(f"📝 环境: {settings.environment}")
    logger.info(f"🔧 调试模式: {settings.debug}")

    # TODO: prd01-04完成后，添加数据库初始化
    # Redis连接初始化
    try:
        await get_redis_client()
        logger.info(f"✅ Redis连接成功: {settings.redis_url}")
    except Exception as e:
        logger.warning(f"⚠️ Redis连接失败: {e}")
    # TODO: prd02-02完成后，添加Celery任务队列启动

    yield  # 应用运行期间

    # 关闭阶段
    logger.info("⏹️ Reddit Signal Scanner API 正在关闭...")

    # Redis连接清理
    try:
        await close_redis_client()
        logger.info("✅ Redis连接已关闭")
    except Exception as e:
        logger.warning(f"⚠️ Redis关闭异常: {e}")

    # TODO: 添加其他资源清理逻辑


# ===== FastAPI应用初始化 =====

app = FastAPI(
    # 基础信息
    title=settings.app_name,
    description="30秒输入，5分钟分析，找到Reddit上的目标客户真实声音",
    version=settings.app_version,
    # OpenAPI文档配置
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    # 生产环境安全配置
    openapi_tags=[
        {"name": "健康检查", "description": "系统健康状态和版本信息"},
        {
            "name": "API v1",
            "description": "核心业务API，包含分析任务、实时推送、状态查询、报告生成",
        },
        {"name": "分析任务", "description": "创建和管理Reddit信号分析任务"},
        {"name": "实时推送", "description": "SSE服务器推送事件，实时任务状态更新"},
        {"name": "任务状态", "description": "任务状态查询和批量状态检查"},
        {"name": "分析报告", "description": "获取结构化分析报告和多格式导出"},
    ],
    # 生命周期管理
    lifespan=lifespan,
    # 安全头设置
    swagger_ui_parameters=(
        {
            "defaultModelsExpandDepth": 2,
            "defaultModelExpandDepth": 2,
            "displayRequestDuration": True,
        }
        if not settings.is_production
        else {}
    ),
)


# ===== 中间件和异常处理器设置 =====

# PRD02-08: 添加API性能监控中间件
app.add_middleware(PerformanceMiddleware)

# PRD03-07: 添加分析引擎监控中间件
app.add_middleware(AnalysisMonitoringMiddleware)
app.add_middleware(RateLimitMiddleware)

# PRD06-05: 添加多租户数据隔离中间件 - 基于Context7最佳实践
try:
    from .middleware.tenant_middleware import TenantIsolationMiddleware

    app.add_middleware(
        TenantIsolationMiddleware,
        skip_paths=["/", "/health", "/docs", "/openapi.json", "/favicon.ico"],
        require_tenant=False,  # 设为False以支持未认证用户访问部分API
    )
    logger.info("✅ 多租户数据隔离中间件已启用")
except ImportError as e:
    logger.warning(f"⚠️ 租户隔离中间件导入失败: {e}")

# 统一中间件（新架构优先）
# 使用默认CORS配置（可后续从配置中心/安全配置加载）
allow_origins: Sequence[str] = ["*"]
allow_methods: Sequence[str] = ["*"]
allow_headers: Sequence[str] = ["*"]
allow_credentials: bool = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=allow_methods,
    allow_headers=allow_headers,
)
app.add_middleware(JWTMiddleware)
app.add_middleware(ErrorHandlingMiddleware)


# ===== 核心路由注册 =====

# 注册API v1路由：/api/v1/*（前缀配置化）
app.include_router(v1_router, prefix=settings.api_base)


# ===== 根路径和健康检查 =====


@app.get("/", response_model=HealthResponse, tags=["健康检查"], summary="API根路径")
async def read_root(request: Request) -> HealthResponse:
    """
    API根路径，返回基本信息和健康状态

    提供：
    - API版本信息
    - 服务状态
    - 请求追踪ID
    - 系统时间戳
    """

    current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    request_id = getattr(request.state, "request_id", "unknown")

    health_data = HealthStatus(
        service="reddit-signal-scanner",
        status="healthy",
        version=settings.app_version,
        timestamp=current_time,
        dependencies={
            # TODO: prd01-04完成后添加数据库状态检查
            # "database": "healthy",
            # TODO: prd01-05完成后添加Redis状态检查
            # "redis": "healthy",
            # TODO: prd02-02完成后添加Celery状态检查
            # "task_queue": "healthy"
        },
    )

    return HealthResponse(
        status=ResponseStatus.SUCCESS,
        message=f"欢迎使用 {settings.app_name} v{settings.app_version}",
        timestamp=current_time,
        request_id=request_id,
        data=health_data,
    )


@app.get("/health", response_model=HealthResponse, tags=["健康检查"], summary="系统健康检查")
async def health_check(request: Request) -> HealthResponse:
    """
    系统健康检查端点

    用于：
    - 负载均衡器健康探测
    - 监控系统状态检查
    - 容器编排健康检查
    - CI/CD部署验证

    返回详细的系统状态和依赖服务状态
    """

    current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    request_id = getattr(request.state, "request_id", "unknown")

    # TODO: 实现真实的健康检查逻辑
    # 1. 检查数据库连接
    # 2. 检查Redis连接
    # 3. 检查Celery任务队列
    # 4. 检查磁盘空间
    # 5. 检查内存使用

    health_data = HealthStatus(
        service="reddit-signal-scanner",
        status="healthy",
        version=settings.app_version,
        timestamp=current_time,
        dependencies={
            "api_server": "healthy",
            "configuration": "loaded",
            # 真实依赖状态检查待实现
        },
    )

    return HealthResponse(
        status=ResponseStatus.SUCCESS,
        message="所有系统组件运行正常",
        timestamp=current_time,
        request_id=request_id,
        data=health_data,
    )


# ===== 监控告警端点 (Linus生产部署要求) =====


@app.get("/monitoring/health", tags=["监控"], summary="数据清理服务健康状态")
async def get_cleanup_monitoring_health() -> "Mapping[str, Any]":
    """
    获取数据清理服务的详细监控状态

    Linus生产部署要求：
    - 实时健康状态监控
    - 告警统计信息
    - 指标摘要
    """
    try:
        monitoring_service = get_monitoring_service()

        health_status = monitoring_service.get_health_status()
        metrics_summary = monitoring_service.get_metrics_summary(hours=1)

        return {
            "service": "data_cleanup_monitoring",
            "health": health_status,
            "metrics_summary": metrics_summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {
            "service": "data_cleanup_monitoring",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/monitoring/alerts", tags=["监控"], summary="获取活跃告警")
async def get_active_alerts() -> "Mapping[str, Any]":
    """获取当前活跃的告警信息"""
    try:
        monitoring_service = get_monitoring_service()

        active_alerts = [
            {
                "alert_id": alert.alert_id,
                "level": alert.level.value,
                "service": alert.service,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "resolved": alert.resolved,
            }
            for alert in monitoring_service.active_alerts.values()
            if not alert.resolved
        ]

        return {
            "active_alerts": active_alerts,
            "count": len(active_alerts),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ===== API信息端点 =====


@app.get("/api", tags=["API v1"], summary="API信息概览")
async def get_api_info(request: Request) -> "Mapping[str, Any]":
    """
    API信息概览，展示所有可用的端点和功能

    包含：
    - 版本信息
    - 端点列表
    - 功能特性
    - 使用示例
    """

    current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    request_id = getattr(request.state, "request_id", "unknown")

    return {
        "api_name": settings.app_name,
        "api_version": settings.app_version,
        "description": "Reddit商业信号扫描和分析API",
        "base_url": str(request.base_url).rstrip("/"),
        "documentation": {
            "interactive": "/api/docs",
            "redoc": "/api/redoc",
            "openapi_schema": "/api/openapi.json",
        },
        "endpoints": {
            "health": "/health",
            "api_info": "/api",
            "version_1": settings.api_prefix,
        },
        "features": [
            "异步任务处理",
            "实时SSE推送",
            "结构化数据分析",
            "多格式报告导出",
            "RESTful API设计",
            "自动API文档",
        ],
        "environment": settings.environment,
        "debug_mode": settings.debug,
        "timestamp": current_time,
        "request_id": request_id,
    }


# ===== 开发模式路由 =====

if settings.is_development:

    @app.get("/dev/config", tags=["开发工具"], summary="配置信息（仅开发环境）")
    async def get_dev_config() -> "Mapping[str, Any]":
        """开发环境专用：查看当前配置信息"""

        return {
            "environment": settings.environment,
            "debug": settings.debug,
            "database_url": (
                settings.database_url[:30] + "..." if settings.database_url else None
            ),
            "redis_url": (
                settings.redis_url[:20] + "..." if settings.redis_url else None
            ),
            "log_level": settings.log_level,
            "cors_enabled": True,
            "note": "⚠️ 此端点仅在开发环境可用",
        }

    @app.get("/dev/test-error", tags=["开发工具"], summary="错误处理测试（仅开发环境）")
    async def test_error_handling() -> None:
        """开发环境专用：测试全局异常处理器"""

        raise Exception("这是一个测试异常，用于验证错误处理中间件")


# ===== 启动信息 =====

if __name__ == "__main__":
    import uvicorn

    logger.info(
        f"""
🔥 Reddit Signal Scanner API Server
================================
Environment: {settings.environment}
Debug Mode: {settings.debug}
API Docs: http://localhost:8000/api/docs
Health Check: http://localhost:8000/health

Linus说: "简单的方案总是更好的方案" ✨
    """
    )

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
