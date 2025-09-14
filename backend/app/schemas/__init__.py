"""
Schemas模块 - 类型安全的数据模型

这个模块替代了项目中的Dict[str, Any]，提供：
1. 类型安全的数据结构
2. 自动API文档生成
3. 数据验证和序列化
4. 更好的IDE支持和错误检查

使用说明：
- 所有API响应应该使用这里定义的模型
- 避免直接使用Dict[str, Any]
- 对于复杂的嵌套结构，创建专门的子模型
"""

# 兼容性适配器
from .common.adapters import (
    TransitionResponse,
    adapt_auth_context,
    adapt_crawler_task,
    adapt_error_statistics,
    create_backward_compatible_response,
    ensure_json_serializable,
    ensure_pydantic_model,
)

# 基础模型
from .common.base import (
    BaseResponse,
    BaseStatisticsResponse,
    BaseStatusResponse,
    BaseTaskResponse,
    TemporaryDictResponse,
)

# 认证相关响应
from .responses.auth import (
    AuthenticationResponse,
    AuthorizationResponse,
    UnifiedAuthContextResponse,
)

# 爬虫专用响应模型
from .responses.crawler import (
    CrawlBatchResponse,
    CrawlerBeatConfigResponse,
    adapt_crawl_batch_result,
    adapt_crawler_beat_config,
    adapt_crawler_status,
)

# 错误相关响应
from .responses.error import (
    ErrorDetailResponse,
    ErrorStatisticsResponse,
    HealthCheckResponse,
)

# 任务相关响应
from .responses.task import (
    BatchTaskResponse,
    CleanupOperationResponse,
    CrawlerStatusResponse,
    CrawlerTaskResponse,
    TaskProgressResponse,
)

__all__ = [
    # 基础模型
    "BaseResponse",
    "BaseTaskResponse",
    "BaseStatusResponse",
    "BaseStatisticsResponse",
    "TemporaryDictResponse",
    # 兼容性适配器
    "ensure_pydantic_model",
    "ensure_json_serializable",
    "create_backward_compatible_response",
    "TransitionResponse",
    "adapt_error_statistics",
    "adapt_crawler_task",
    "adapt_auth_context",
    # 认证相关
    "UnifiedAuthContextResponse",
    "AuthenticationResponse",
    "AuthorizationResponse",
    # 错误相关
    "ErrorStatisticsResponse",
    "ErrorDetailResponse",
    "HealthCheckResponse",
    # 任务相关
    "CrawlerTaskResponse",
    "CrawlerStatusResponse",
    "CleanupOperationResponse",
    "TaskProgressResponse",
    "BatchTaskResponse",
    # 爬虫专用模型
    "CrawlBatchResponse",
    "CrawlerBeatConfigResponse",
    "adapt_crawl_batch_result",
    "adapt_crawler_beat_config",
    "adapt_crawler_status",
]
