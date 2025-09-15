"""
算法相关响应模型 - 替代algorithm模块中的Dict[str, Any]

遵循项目类型安全策略：
1. 为算法元数据提供结构化响应
2. 保持字段语义清晰和类型安全
3. 支持向后兼容和自动API文档
"""

from pydantic import BaseModel, Field

from ..common.base import BaseResponse


class AlgorithmMetadataResponse(BaseResponse):
    """算法元数据响应模型 - 替代KeywordExtractor.get_algorithm_metadata()的Dict返回值"""

    algorithm_name: str = Field(..., description="算法名称")
    version: str = Field(..., description="算法版本")
    tfidf_features: int = Field(default=0, ge=0, description="TF-IDF特征数量")
    domain_categories: int = Field(default=0, ge=0, description="领域类别数量")
    product_types: int = Field(default=0, ge=0, description="产品类型数量")
    synonym_mappings: int = Field(default=0, ge=0, description="同义词映射数量")


class AlgorithmPerformanceResponse(BaseResponse):
    """算法性能响应模型 - 为future扩展准备"""

    processing_time_ms: float = Field(..., ge=0, description="处理时间（毫秒）")
    memory_usage_mb: float = Field(..., ge=0, description="内存使用量（MB）")
    accuracy_score: float = Field(..., ge=0, le=1, description="准确率评分")
