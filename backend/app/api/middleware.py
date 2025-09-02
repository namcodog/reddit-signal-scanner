"""
Reddit Signal Scanner - API中间件

Linus哲学："消除特殊情况"
- 统一的错误处理格式
- 统一的CORS策略
- 统一的请求日志
- 零配置，开箱即用
"""

import logging
import time
import uuid
from typing import Any, Callable, Dict

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..core.config import get_settings
from ..middleware.jwt_simple import JWTMiddleware

logger = logging.getLogger(__name__)
settings = get_settings()


# ===== 通用异常处理器 =====


def create_exception_handler(
    status_code: int, error_code: str
) -> Callable[..., JSONResponse]:
    """创建标准异常处理器 - 消除重复代码"""

    def handler(request: Request, exc: Exception) -> JSONResponse:
        """统一异常响应格式"""

        request_id = str(uuid.uuid4())[:8]

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "error",
                "message": (str(exc.detail) if hasattr(exc, "detail") else str(exc)),
                "error_code": error_code,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "request_id": request_id,
                "error_details": None,
            },
        )

    return handler


# ===== 通用异常处理器映射 =====

EXCEPTION_HANDLERS = {
    400: create_exception_handler(400, "BAD_REQUEST"),
    401: create_exception_handler(401, "UNAUTHORIZED"),
    403: create_exception_handler(403, "FORBIDDEN"),
    404: create_exception_handler(404, "NOT_FOUND"),
    422: create_exception_handler(422, "VALIDATION_ERROR"),
    429: create_exception_handler(429, "RATE_LIMITED"),
    500: create_exception_handler(500, "INTERNAL_ERROR"),
}


# ===== CORS配置 =====


def get_cors_config() -> Dict[str, Any]:
    """获取CORS配置 - 根据环境自动调整"""

    if settings.is_production:
        # 生产环境：严格的CORS策略
        return {
            "allow_origins": ["https://your-domain.com"],
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["*"],
        }
    else:
        # 开发环境：宽松的CORS策略
        return {
            "allow_origins": ["*"],
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }


# ===== 中间件注册函数 =====


def setup_middleware(app: Any) -> None:
    """
    设置应用中间件

    中间件执行顺序（重要！）：
    1. CORS（最外层）
    2. JWT认证中间件（安全层）
    3. 其他业务中间件
    """

    # 添加CORS中间件
    cors_config = get_cors_config()
    app.add_middleware(CORSMiddleware, **cors_config)

    # 添加JWT认证中间件
    app.add_middleware(JWTMiddleware)

    logger.info(f"Middleware setup completed for {settings.environment} environment")
    logger.info("JWT认证中间件已安装")


def setup_exception_handlers(app: Any) -> None:
    """设置全局异常处理器"""

    for status_code, handler in EXCEPTION_HANDLERS.items():
        app.add_exception_handler(status_code, handler)

    logger.info("Exception handlers registered")
